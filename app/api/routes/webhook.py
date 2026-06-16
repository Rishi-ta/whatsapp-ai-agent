import logging
import re
from fastapi import APIRouter, Form, Response, Request
from twilio.twiml.messaging_response import MessagingResponse
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.services.rag_service import RAGService
from app.services.conversation_service import ConversationService
from app.services.tenant_service import TenantService
from app.core.config import get_settings

router = APIRouter()
logger = logging.getLogger(__name__)
settings = get_settings()
limiter = Limiter(key_func=get_remote_address)

conversation_service = ConversationService(max_history=10)
tenant_service = TenantService()

# Matches messages like: "menu RESTAURANT123" or "MENU restaurant123"
KEYWORD_PATTERN = re.compile(r"^(menu|join|connect)\s+([a-zA-Z0-9]+)$", re.IGNORECASE)


@router.post("/webhook")
@limiter.limit("30/minute")
async def whatsapp_webhook(
    request: Request,
    From: str = Form(...),
    Body: str = Form(...),
):
    phone = From.strip()
    message = Body.strip()

    logger.info(f"Message from {phone}: {message[:80]}")

    # Reset command
    if message.lower() in ("reset", "clear", "start over"):
        conversation_service.clear(phone)
        return _twiml_reply("Conversation reset. Ask me anything!")

    # Check if this phone is already linked to a tenant
    tenant_id = tenant_service.get_tenant_by_phone(phone)

    if not tenant_id:
        # Not linked yet — check if this message is a keyword command
        match = KEYWORD_PATTERN.match(message)

        if match:
            keyword = match.group(2)
            found_tenant_id = tenant_service.get_tenant_by_keyword(keyword)

            if found_tenant_id:
                tenant_service.register_phone(found_tenant_id, phone)
                tenant = tenant_service.get_tenant(found_tenant_id)
                return _twiml_reply(
                    f"Connected to {tenant['name']}! 🎉\n\n"
                    f"Ask me anything about their products, services, or FAQs."
                )
            else:
                return _twiml_reply(
                    f"Sorry, I couldn't find a business with code '{keyword}'. "
                    f"Please check the code and try again."
                )

        # Not linked, not a keyword command — show instructions
        return _twiml_reply(
            "👋 Welcome! To get started, send:\n\n"
            "menu <BUSINESS_CODE>\n\n"
            "Use the code provided by the business you want to chat with."
        )

    # Phone is linked — proceed with normal RAG flow
    collection_name = tenant_service.get_collection_name(tenant_id)
    history = conversation_service.get_history(phone)
    enriched_question = _build_question_with_history(message, history)

    try:
        rag_service = RAGService(collection_name=collection_name)
        answer, source_chunks = rag_service.answer(enriched_question, top_k=3)
        reply = _format_whatsapp_reply(answer, source_chunks)
    except Exception as e:
        logger.error(f"RAG error for tenant {tenant_id}: {e}")
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