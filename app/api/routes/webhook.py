import logging
from fastapi import APIRouter, Form, Response
from twilio.twiml.messaging_response import MessagingResponse
from functools import lru_cache
from datetime import datetime, timedelta

from app.services.rag_service import RAGService
from app.services.conversation_service import ConversationService
from app.services.tenant_service import TenantService
from app.core.config import get_settings
from slowapi import Limiter
from slowapi.util import get_remote_address
from fastapi import Request

limiter = Limiter(key_func=get_remote_address)

router = APIRouter()
logger = logging.getLogger(__name__)
settings = get_settings()

conversation_service = ConversationService(max_history=10)
tenant_service = TenantService()

# Simple rate limiting: track last request per phone
_last_request = {}
RATE_LIMIT_SECONDS = 2  # Minimum 2 seconds between requests per user


@router.post("/webhook")
@limiter.limit("30/minute")
async def whatsapp_webhook(
    request: Request,          # add this first
    From: str = Form(...),
    Body: str = Form(...),
):
    phone = From.strip()
    message = Body.strip()

    logger.info(f"Message from {phone}: {message[:80]}")

    # Rate limiting
    now = datetime.now()
    if phone in _last_request:
        last_time = _last_request[phone]
        if (now - last_time).total_seconds() < RATE_LIMIT_SECONDS:
            return _twiml_reply("Please wait a moment before sending another message.")
    
    _last_request[phone] = now

    # Reset command
    if message.lower() in ("reset", "clear", "start over"):
        conversation_service.clear(phone)
        return _twiml_reply("Conversation reset. Ask me anything!")

    # Look up which tenant this phone number belongs to
    tenant_id = tenant_service.get_tenant_by_phone(phone)

    if not tenant_id:
        # Phone not registered to any tenant yet
        return _twiml_reply(
            "Welcome! You're not connected to any business yet. "
            "Please contact your service provider to activate this bot."
        )

    # Get this tenant's ChromaDB collection
    collection_name = tenant_service.get_collection_name(tenant_id)

    # Build question with conversation history
    history = conversation_service.get_history(phone)
    enriched_question = _build_question_with_history(message, history)

    try:
        rag_service = RAGService(collection_name=collection_name)
        answer, source_chunks = rag_service.answer(
            question=enriched_question,
            top_k=3,
        )
        reply = _format_whatsapp_reply(answer, source_chunks)

    except Exception as e:
        error_msg = str(e)
        
        # Handle quota exceeded error
        if "429" in error_msg or "quota" in error_msg.lower():
            logger.warning(f"Gemini quota exceeded for tenant {tenant_id}")
            reply = "I've reached my daily request limit. Please try again tomorrow. 🔄"
        else:
            logger.error(f"RAG error for tenant {tenant_id}: {error_msg}", exc_info=True)
            reply = "Sorry, I ran into an issue. Please try again."

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