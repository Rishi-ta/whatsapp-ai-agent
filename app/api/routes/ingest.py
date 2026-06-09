import os
import shutil
import logging
from pathlib import Path

from fastapi import APIRouter, UploadFile, File, HTTPException

from app.services.pdf_service import PDFService
from app.services.chunking_service import ChunkingService
from app.services.vector_store import VectorStore
from app.models.schemas import IngestResponse
from app.core.config import get_settings

router = APIRouter()
logger = logging.getLogger(__name__)
settings = get_settings()

UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)


@router.post("/ingest", response_model=IngestResponse)
async def ingest_pdf(file: UploadFile = File(...)):
    # Validate file type
    if file.content_type != "application/pdf":
        raise HTTPException(status_code=400, detail="Only PDF files are accepted.")

    if not file.filename.endswith(".pdf"):
        raise HTTPException(status_code=400, detail="File must have a .pdf extension.")

    # Save to disk (PyPDFLoader needs a file path)
    save_path = UPLOAD_DIR / file.filename
    try:
        with save_path.open("wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        # Run ingestion pipeline
        pdf_service = PDFService()
        chunking_service = ChunkingService(
            chunk_size=settings.chunk_size,
            chunk_overlap=settings.chunk_overlap,
        )
        vector_store = VectorStore()

        docs = pdf_service.load(str(save_path))
        chunks = chunking_service.split(docs)
        stored = vector_store.add_documents(chunks)

        return IngestResponse(
            message="PDF ingested successfully",
            filename=file.filename,
            pages_processed=len(docs),
            chunks_created=stored,
            collection_name=settings.chroma_collection_name,
        )

    except Exception as e:
        logger.error(f"Ingestion failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

    finally:
        # Clean up temp file
        if save_path.exists():
            os.remove(save_path)
@router.get("/ingest/stats")
async def collection_stats():
    """Returns how many chunks are currently stored in ChromaDB."""
    try:
        vector_store = VectorStore()
        count = vector_store.collection.count()
        return {
            "collection": settings.chroma_collection_name,
            "total_chunks": count,
            "status": "empty" if count == 0 else "ready",
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))