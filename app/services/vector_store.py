import logging
from typing import List, Optional

import chromadb
from chromadb.config import Settings as ChromaSettings
from langchain_core.documents import Document

from app.core.config import get_settings
from app.services.embedding_service import EmbeddingService

logger = logging.getLogger(__name__)
settings = get_settings()


class VectorStore:
    """
    ChromaDB operations — now tenant-aware.
    Each tenant gets their own isolated collection.
    """

    def __init__(self, collection_name: Optional[str] = None):
        self.embedding_service = EmbeddingService()

        self.client = chromadb.PersistentClient(
            path=settings.chroma_persist_dir,
            settings=ChromaSettings(anonymized_telemetry=False),
        )

        # Use provided collection name or fall back to default
        name = collection_name or settings.chroma_collection_name

        self.collection = self.client.get_or_create_collection(
            name=name,
            metadata={"hnsw:space": "cosine"},
        )

        logger.info(f"ChromaDB collection '{name}' has {self.collection.count()} chunks")

    def add_documents(self, chunks: List[Document]) -> int:
        if not chunks:
            raise ValueError("No chunks to store.")

        texts = [chunk.page_content for chunk in chunks]
        metadatas = [chunk.metadata for chunk in chunks]
        embeddings = self.embedding_service.embed_documents(texts)

        existing_count = self.collection.count()
        ids = [f"doc_{existing_count + i}" for i in range(len(chunks))]

        self.collection.add(
            ids=ids,
            embeddings=embeddings,
            documents=texts,
            metadatas=metadatas,
        )

        logger.info(f"Stored {len(chunks)} chunks")
        return len(chunks)

    def query(self, question: str, top_k: int = 5) -> List[Document]:
        if self.collection.count() == 0:
            return []

        query_embedding = self.embedding_service.embed_query(question)

        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=min(top_k, self.collection.count()),
            include=["documents", "metadatas", "distances"],
        )

        return [
            Document(page_content=text, metadata=metadata)
            for text, metadata in zip(
                results["documents"][0],
                results["metadatas"][0],
            )
        ]