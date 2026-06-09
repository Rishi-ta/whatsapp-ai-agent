import logging
from typing import List

from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_core.documents import Document

from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class EmbeddingService:
    """
    Wraps Google's text-embedding-004 model.
    Converts text into high-dimensional vectors.
    """

    def __init__(self):
        self.embeddings = GoogleGenerativeAIEmbeddings(
    model="models/gemini-embedding-001",
    google_api_key=settings.gemini_api_key,
)

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """
        Embed a list of text strings (used during ingestion).
        Returns a list of vectors — one per text.
        """
        logger.info(f"Embedding {len(texts)} chunks...")
        vectors = self.embeddings.embed_documents(texts)
        logger.info(f"Generated {len(vectors)} vectors, dimension={len(vectors[0])}")
        return vectors

    def embed_query(self, query: str) -> List[float]:
        """
        Embed a single query string (used during retrieval).
        Uses a slightly different internal prompt than embed_documents
        — LangChain handles this distinction automatically.
        """
        return self.embeddings.embed_query(query)