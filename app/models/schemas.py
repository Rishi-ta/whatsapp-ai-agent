from pydantic import BaseModel, Field
from typing import List, Optional


# ── Ingestion ──────────────────────────────────────────────

class IngestResponse(BaseModel):
    """
    Returned after a successful PDF upload and ingestion.
    Gives the caller visibility into what was processed.
    """
    message: str
    filename: str
    pages_processed: int
    chunks_created: int
    collection_name: str


# ── Query ──────────────────────────────────────────────────

class QueryRequest(BaseModel):
    """
    Body for the /query endpoint.
    """
    question: str = Field(
        ...,                          # ... means required
        min_length=3,
        max_length=1000,
        description="The question to answer from the documents"
    )
    top_k: Optional[int] = Field(
        default=5,
        ge=1,                         # greater than or equal to 1
        le=20,                        # less than or equal to 20
        description="Number of chunks to retrieve"
    )


class SourceChunk(BaseModel):
    """
    A single retrieved chunk returned alongside the answer.
    Lets the user verify where the answer came from.
    """
    content: str
    page: Optional[int] = None
    source: Optional[str] = None


class QueryResponse(BaseModel):
    """
    Returned after a successful RAG query.
    """
    question: str
    answer: str
    source_chunks: List[SourceChunk]