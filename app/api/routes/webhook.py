import logging
import re
import os
import httpx
from pathlib import Path
from fastapi import APIRouter, Form, Response, Request, BackgroundTasks
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

# Track phones currently having their PDF processed so we can give
# a "still processing" reply instead of the confusing welcome prompt.
_processing: set[str] = set()


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
    background_tasks: BackgroundTasks,
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
        _processing.discard(phone)
        return _twiml_reply("✅ Conversation reset. Send me a PDF or ask me anything!")

    # ── PDF sent directly on WhatsApp (Flow B) ─────────────────
    if NumMedia > 0 and MediaContentType0 == "application/pdf":
        return await _handle_pdf_upload(phone, MediaUrl0, background_tasks)

    # ── Non-PDF file sent ──────────────────────────────────────
    if NumMedia > 0 and MediaContentType0 != "application/pdf":
        return _twiml_reply(
            "⚠️ I can only process *PDF* files.\n"
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
                f"✅ Connected to *{tenant['name']}*! 🎉\n\n"
                f"Ask me anything about their products or services."
            )
        else:
            return _twiml_reply(
                f"❌ No business found with code *{keyword}*.\n"
                f"Please check the code and try again."
            )

    # ── Flow B: personal collection ────────────────────────────
    collection_name = _personal_collection(phone)

    # User texting while PDF is still being processed
    if phone in _processing:
        return _twiml_reply(
            "⏳ Your PDF is still being processed...\n\n"
            "Please wait a moment and ask your question again once I confirm it's ready!"
        )

    # Check if they have any personal documents
    try:
        vs = VectorStore(collection_name=collection_name)
        doc_count = vs.collection.count()
    except Exception as e:
        logger.error(f"Error checking collection for {phone}: {e}")
        doc_count = 0

    if doc_count == 0:
        return _twiml_reply(
            "👋 *Welcome to your Personal AI Assistant!*\n\n"
            "━━━━━━━━━━━━━━━━━━\n"
            "📄 *Upload a PDF*\n"
            "Just send any PDF file here. I'll read it and you can ask me anything about it.\n\n"
            "🏢 *Connect to a business*\n"
            "Send: `menu <BUSINESS_CODE>`\n"
            "━━━━━━━━━━━━━━━━━━\n\n"
            "What would you like to do?"
        )

    # They have personal documents — answer from personal collection
    return await _rag_reply(phone, message, collection_name)


async def _handle_pdf_upload(
    phone: str, media_url: str, background_tasks: BackgroundTasks
) -> Response:
    """
    Immediately reply to the user, then kick off ingestion as a
    FastAPI BackgroundTask (which is the correct way to run async
    work after a response has been sent).
    """
    logger.info(f"PDF upload request from {phone}, url={media_url}")

    # Mark this phone as "processing" so follow-up texts get a
    # friendly wait message instead of the welcome prompt.
    _processing.add(phone)

    # Schedule background ingestion using FastAPI's BackgroundTasks —
    # this is reliable, unlike asyncio.create_task() inside a finally block.
    background_tasks.add_task(_ingest_whatsapp_pdf, phone, media_url)

    return _twiml_reply(
        "📄 *Got your PDF! Processing it now...*\n\n"
        "This usually takes 20–30 seconds.\n"
        "I'll send you a message as soon as it's ready — then you can ask me anything! 🚀"
    )


async def _ingest_whatsapp_pdf(phone: str, media_url: str):
    """Background task: download and ingest a WhatsApp PDF."""

    logger.info("========== PDF INGESTION STARTED ==========")
    logger.info(f"Phone: {phone}")
    logger.info(f"Media URL: {media_url}")

    file_path = UPLOAD_DIR / f"{re.sub(r'[^0-9]', '', phone)}_upload.pdf"

    try:
        auth = (settings.twilio_account_sid, settings.twilio_auth_token)

        logger.info("Downloading PDF from Twilio...")

        async with httpx.AsyncClient() as client:
            response = await client.get(media_url, auth=auth, timeout=60)
            response.raise_for_status()

        logger.info(f"PDF downloaded. Size={len(response.content)} bytes")

        with open(file_path, "wb") as f:
            f.write(response.content)

        logger.info(f"PDF saved to: {file_path}")

        # Load PDF
        docs = PDFService().load(str(file_path))
        logger.info(f"Pages extracted: {len(docs)}")

        # Chunk PDF
        chunker = ChunkingService(
            chunk_size=settings.chunk_size,
            chunk_overlap=settings.chunk_overlap,
        )
        chunks = chunker.split(docs)
        logger.info(f"Chunks created: {len(chunks)}")

        # Collection name for this user
        collection_name = _personal_collection(phone)
        logger.info(f"Collection name: {collection_name}")

        # Store in Chroma
        vs = VectorStore(collection_name=collection_name)
        logger.info(f"Collection count BEFORE insert: {vs.collection.count()}")

        stored = vs.add_documents(chunks)
        logger.info(f"Stored chunks: {stored}")
        logger.info(f"Collection count AFTER insert: {vs.collection.count()}")

        logger.info(f"Personal PDF ingested successfully for {phone}")

        # Send WhatsApp confirmation
        _send_whatsapp_message(
            phone,
            f"✅ *Done! Your PDF is ready.*\n\n"
            f"📊 Pages: {len(docs)} | Chunks: {stored}\n\n"
            f"Go ahead — ask me anything about it! 💬",
        )

        logger.info("Confirmation WhatsApp message sent")

    except Exception as e:
        logger.exception(f"PDF ingestion FAILED for {phone}: {e}")
        _send_whatsapp_message(
            phone,
            "❌ *Sorry, I couldn't process that PDF.*\n\n"
            "Possible reasons:\n"
            "• The file is password-protected\n"
            "• The PDF contains only scanned images (no text)\n"
            "• The file is corrupted\n\n"
            "Please try a different PDF file.",
        )

    finally:
        # Always remove from processing set so future messages work correctly
        _processing.discard(phone)

        if file_path.exists():
            file_path.unlink()
            logger.info(f"Deleted temporary file: {file_path}")


def _send_whatsapp_message(phone: str, body: str):
    """Send a proactive WhatsApp message via Twilio REST API."""
    try:
        from twilio.rest import Client

        client = Client(settings.twilio_account_sid, settings.twilio_auth_token)
        client.messages.create(
            from_=settings.twilio_whatsapp_number,
            to=phone,
            body=body,
        )
    except Exception as e:
        logger.exception(f"Failed to send WhatsApp message to {phone}: {e}")


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
        reply = "⚠️ Sorry, I ran into an issue. Please try again in a moment."

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