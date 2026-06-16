import uuid
import asyncio
import aiofiles
import logging
from fastapi import APIRouter, HTTPException, UploadFile, File, BackgroundTasks
from pydantic import BaseModel
from pathlib import Path
from typing import Optional
from app.services.tenant_service import TenantService
from app.services.pdf_service import PDFService
from app.services.chunking_service import ChunkingService
from app.services.vector_store import VectorStore
from app.services.job_service import JobService
from app.core.config import get_settings

router = APIRouter()
logger = logging.getLogger(__name__)
settings = get_settings()
tenant_service = TenantService()
job_service = JobService()

UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)


class CreateTenantRequest(BaseModel):
    tenant_id: str
    name: str
    keyword: Optional[str] = None  # auto-generated if not provided



class RegisterPhoneRequest(BaseModel):
    phone: str


@router.post("/tenants")
async def create_tenant(request: CreateTenantRequest):
    try:
        tenant = tenant_service.create_tenant(
            request.tenant_id,
            request.name,
            keyword=request.keyword,
        )
        return {
            "message": "Tenant created",
            "tenant": tenant,
            "whatsapp_instructions": (
                f"Customers should message 'menu {tenant['keyword']}' "
                f"to +14155238886 on WhatsApp"
            ),
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/tenants")
async def list_tenants():
    return tenant_service.list_tenants()


@router.post("/tenants/{tenant_id}/register-phone")
async def register_phone(tenant_id: str, request: RegisterPhoneRequest):
    try:
        tenant_service.register_phone(tenant_id, request.phone)
        return {"message": f"Phone {request.phone} registered to {tenant_id}"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/tenants/{tenant_id}/ingest")
async def tenant_ingest(
    tenant_id: str,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
):
    """
    Returns immediately with a job_id.
    Processing happens in the background.
    Poll /jobs/{job_id} to check status.
    """
    tenant = tenant_service.get_tenant(tenant_id)
    if not tenant:
        raise HTTPException(status_code=404, detail=f"Tenant '{tenant_id}' not found.")

    if not file.filename.endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files accepted.")

    # Save file to disk first
    job_id = str(uuid.uuid4())[:8]
    save_path = UPLOAD_DIR / f"{job_id}_{file.filename}"

    async with aiofiles.open(save_path, "wb") as buffer:
        content = await file.read()
        await buffer.write(content)

    # Create job record
    job_service.create_job(job_id, tenant_id, file.filename)

    # Schedule background processing
    background_tasks.add_task(
        _process_pdf,
        job_id=job_id,
        file_path=str(save_path),
        collection_name=tenant["collection_name"],
    )

    return {
        "message": "PDF upload received — processing in background",
        "job_id": job_id,
        "status_url": f"/api/v1/jobs/{job_id}",
    }


async def _process_pdf(job_id: str, file_path: str, collection_name: str):
    """Background task — runs after the API has already responded."""
    job_service.update_job(job_id, "processing")
    path = Path(file_path)

    try:
        # Run blocking operations in a thread pool
        loop = asyncio.get_event_loop()

        docs = await loop.run_in_executor(
            None, PDFService().load, file_path
        )
        chunks = await loop.run_in_executor(
            None,
            lambda: ChunkingService(
                chunk_size=settings.chunk_size,
                chunk_overlap=settings.chunk_overlap
            ).split(docs)
        )

        vs = VectorStore(collection_name=collection_name)
        stored = await loop.run_in_executor(
            None, vs.add_documents, chunks
        )

        job_service.update_job(job_id, "completed", result={
            "pages_processed": len(docs),
            "chunks_created": stored,
            "collection": collection_name,
        })
        logger.info(f"Job {job_id} completed: {stored} chunks")

    except Exception as e:
        logger.error(f"Job {job_id} failed: {e}")
        job_service.update_job(job_id, "failed", error=str(e))
    finally:
        if path.exists():
            path.unlink()


@router.get("/jobs/{job_id}")
async def get_job_status(job_id: str):
    """Poll this to check if your PDF has finished processing."""
    job = job_service.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found.")
    return job


@router.get("/tenants/{tenant_id}/stats")
async def tenant_stats(tenant_id: str):
    tenant = tenant_service.get_tenant(tenant_id)
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found.")
    vs = VectorStore(collection_name=tenant["collection_name"])
    return {
        "tenant_id": tenant_id,
        "name": tenant["name"],
        "collection": tenant["collection_name"],
        "total_chunks": vs.collection.count(),
        "whatsapp_numbers": tenant["whatsapp_numbers"],
    }