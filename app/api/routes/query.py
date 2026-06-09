import logging
from fastapi import APIRouter, HTTPException 
from app.services.rag_service import RAGService
from app.models.schemas import QueryRequest, QueryResponse
from app.core.config import get_settings

router = APIRouter()
logger = logging.getLogger(__name__)
settings = get_settings()


@router.post("/query", response_model=QueryResponse)
async def query_documents(request: QueryRequest):
    if not request.question.strip():
        raise HTTPException(status_code=400, detail="Question cannot be empty.")

    try:
        rag_service = RAGService()
        top_k = request.top_k or settings.top_k_results

        answer, source_chunks = rag_service.answer(
            question=request.question,
            top_k=top_k,
        )

        return QueryResponse(
            question=request.question,
            answer=answer,
            source_chunks=source_chunks,
        )

    except Exception as e:
        logger.error(f"Query failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))