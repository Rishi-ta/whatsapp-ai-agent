import logging
import re
import os
import httpx
from pathlib import Path
from fastapi import APIRouter, Form, Response, Request
from twilio.twiml.messaging_response import MessagingResponse
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.services.rag_service import RAGService
from app.services.conversation_service import ConversationService
from app.services.tenant_service import TenantService
from app.services.pdf_service import PDFService
from app.services.chunking_service import ChunkingService
from app.services.vector_store import VectorStore
from app.core.config import get_settings

router = APIRouter()
logger = logging.getLogger(__name__)
settings = get_settings()
limiter = Limiter(key_func=get_remote_address)

conversation_service = ConversationService(max_history=10)
tenant_service = TenantService()

KEYWORD_PATTERN = re.compile(r"^(menu|join|connect)\s+([a-zA-Z0-9]+)$", re.IGNORECASE)
UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)


def _personal_collection(phone: str) -> str:
    """
    Each personal user gets their own ChromaDB collection
    named after their phone number (sanitized).
    e.g. whatsapp:+919876543210 → personal_919876543210
    """
    sanitized = re.sub(r"[^0-9]", "", phone)
    return f"personal_{sanitized}"


@router.post("/webhook")
@limiter.limit("30/minute")
async def whatsapp_webhook(
    request: Request,
    From: str = Form(...),
    Body: str = Form(""),
    NumMedia: int = Form(0),
    MediaUrl0: str = Form(None),
    MediaContentType0: str = Form(None),
):
    phone = From.strip()
    message = Body.strip()

    logger.info(f"Message from {phone}: '{message[:80]}' | media: {NumMedia}")

    # ── Reset command ──────────────────────────────────────────
    if message.lower() in ("reset", "clear", "start over"):
        conversation_service.clear(phone)
        return _twiml_reply("Conversation reset. Ask me anything!")

    # ── PDF sent directly on WhatsApp (Flow B) ─────────────────
    if NumMedia > 0 and MediaContentType0 == "application/pdf":
        return await _handle_pdf_upload(phone, MediaUrl0)

    # ── Non-PDF file sent ──────────────────────────────────────
    if NumMedia > 0 and MediaContentType0 != "application/pdf":
        return _twiml_reply(
            "I can only process PDF files. "
            "Please send a PDF document and I'll learn from it!"
        )

    # ── Check if phone is linked to a business tenant ──────────
    tenant_id = tenant_service.get_tenant_by_phone(phone)

    if tenant_id:
        # Flow A: linked to a business — answer from business collection
        collection_name = tenant_service.get_collection_name(tenant_id)
        return await _rag_reply(phone, message, collection_name)

    # ── Keyword command (connect to a business) ────────────────
    match = KEYWORD_PATTERN.match(message)
    if match:
        keyword = match.group(2)
        found_tenant_id = tenant_service.get_tenant_by_keyword(keyword)
        if found_tenant_id:
            tenant_service.register_phone(found_tenant_id, phone)
            tenant = tenant_service.get_tenant(found_tenant_id)
            return _twiml_reply(
                f"Connected to *{tenant['name']}*! 🎉\n\n"
                f"Ask me anything about their products or services."
            )
        else:
            return _twiml_reply(
                f"No business found with code '{keyword}'. "
                f"Please check the code and try again."
            )

    # ── Flow B: personal collection ────────────────────────────
    collection_name = _personal_collection(phone)

    # Check if they have any personal documents
    vs = VectorStore(collection_name=collection_name)
    if vs.collection.count() == 0:
        return _twiml_reply(
            "👋 Welcome to your Personal AI Assistant!\n\n"
            "You have two options:\n\n"
            "📄 *Upload your own PDF* — just send any PDF file here "
            "and I'll learn from it. Then ask me anything about it.\n\n"
            "🏢 *Connect to a business* — send:\n"
            "menu <BUSINESS_CODE>\n\n"
            "What would you like to do?"
        )

    # They have personal documents — answer from personal collection
    return await _rag_reply(phone, message, collection_name)


async def _handle_pdf_upload(phone: str, media_url: str) -> Response:
    """
    Downloads a PDF sent on WhatsApp and ingests it into
    the user's personal ChromaDB collection.
    """
    try:
        return _twiml_reply(
            "📄 Got your PDF! Processing it now...\n"
            "This takes 20-30 seconds. I'll be ready to answer "
            "questions about it right after."
        )
    finally:
        # Process in background after replying
        import asyncio
        asyncio.create_task(
            _ingest_whatsapp_pdf(phone, media_url)
        )


async def _ingest_whatsapp_pdf(phone: str, media_url: str):
    """Background task: download and ingest a WhatsApp PDF."""
    file_path = UPLOAD_DIR / f"{re.sub(r'[^0-9]', '', phone)}_upload.pdf"

    try:
        # Download PDF from Twilio's media URL
        # Twilio requires auth to download media
        auth = (settings.twilio_account_sid, settings.twilio_auth_token)

        async with httpx.AsyncClient() as client:
            response = await client.get(media_url, auth=auth, timeout=30)
            response.raise_for_status()

        with open(file_path, "wb") as f:
            f.write(response.content)

        # Ingest into personal collection
        docs = PDFService().load(str(file_path))
        chunks = ChunkingService(
            chunk_size=settings.chunk_size,
            chunk_overlap=settings.chunk_overlap,
        ).split(docs)

        collection_name = _personal_collection(phone)
        vs = VectorStore(collection_name=collection_name)
        stored = vs.add_documents(chunks)

        logger.info(f"Personal PDF ingested for {phone}: {stored} chunks")

        # Send follow-up message confirming it's ready
        from twilio.rest import Client
        client = Client(settings.twilio_account_sid, settings.twilio_auth_token)
        client.messages.create(
            from_=settings.twilio_whatsapp_number,
            to=phone,
            body=(
                f"✅ Done! I've read your PDF ({len(docs)} pages, {stored} chunks).\n\n"
                f"Ask me anything about it!"
            ),
        )

    except Exception as e:
        logger.error(f"PDF ingestion failed for {phone}: {e}")
        try:
            from twilio.rest import Client
            client = Client(settings.twilio_account_sid, settings.twilio_auth_token)
            client.messages.create(
                from_=settings.twilio_whatsapp_number,
                to=phone,
                body="❌ Sorry, I couldn't process that PDF. Please try a smaller file (under 5MB).",
            )
        except Exception:
            pass
    finally:
        if file_path.exists():
            file_path.unlink()


async def _rag_reply(phone: str, message: str, collection_name: str) -> Response:
    """Run RAG pipeline and return TwiML response."""
    history = conversation_service.get_history(phone)
    enriched_question = _build_question_with_history(message, history)

    try:
        rag_service = RAGService(collection_name=collection_name)
        answer, source_chunks = rag_service.answer(enriched_question, top_k=3)
        reply = _format_whatsapp_reply(answer, source_chunks)
    except Exception as e:
        logger.error(f"RAG error for {phone}: {e}")
        reply = "Sorry, I ran into an issue. Please try again in a moment."

    conversation_service.add_message(phone, "user", message)
    conversation_service.add_message(phone, "assistant", reply)
    return _twiml_reply(reply)


def _build_question_with_history(current_message: str, history: list) -> str:
    if not history:
        return current_message
    history_text = "\n".join(
        f"{'User' if h['role'] == 'user' else 'Assistant'}: {h['content']}"
        for h in history[-4:]
    )
    return f"Previous conversation:\n{history_text}\n\nCurrent question: {current_message}"


def _format_whatsapp_reply(answer: str, source_chunks: list) -> str:
    reply = answer.strip()
    pages = set(chunk.page for chunk in source_chunks if chunk.page is not None)
    if pages:
        reply += f"\n\n_(Source: page {', '.join(str(p+1) for p in sorted(pages))})_"
    if len(reply) > 1500:
        reply = reply[:1497] + "..."
    return reply


def _twiml_reply(message: str) -> Response:
    resp = MessagingResponse()
    resp.message(message)
    return Response(content=str(resp), media_type="application/xml")