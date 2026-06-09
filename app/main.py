import logging
import sys
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from app.api.routes import ingest, query, webhook, tenant, portal, auth, billing
from app.core.config import get_settings

limiter = Limiter(key_func=get_remote_address)

# Configure logging once at startup — all other files use getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)

settings = get_settings()
logger = logging.getLogger(__name__)

app = FastAPI(
    title="RAG Engine",
    description="Local RAG chatbot powered by Gemini and ChromaDB",
    version="0.1.0",
)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.include_router(ingest.router, prefix="/api/v1", tags=["Ingestion"])
app.include_router(query.router, prefix="/api/v1", tags=["Query"])
app.include_router(webhook.router, prefix="/api/v1", tags=["WhatsApp"])
app.include_router(tenant.router, prefix="/api/v1", tags=["Tenants"])
app.include_router(portal.router, prefix="/api/v1", tags=["Portal"])
app.include_router(auth.router, prefix="/api/v1", tags=["Auth"])
app.include_router(billing.router, prefix="/api/v1", tags=["Billing"])

@app.on_event("startup")
async def startup():
    logger.info("RAG Engine starting up...")
    logger.info(f"ChromaDB path: {settings.chroma_persist_dir}")
    logger.info(f"Chunk size: {settings.chunk_size}, overlap: {settings.chunk_overlap}")

@app.get("/health", tags=["Health"])
@limiter.limit("60/minute")
async def health_check(request: Request):
    return {"status": "ok", "version": "0.1.0"}