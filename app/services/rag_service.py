import logging
import time
from typing import List, Tuple

import google.generativeai as genai
from langchain.schema import Document

from app.core.config import get_settings
from app.services.vector_store import VectorStore
from app.models.schemas import SourceChunk

logger = logging.getLogger(__name__)
settings = get_settings()

genai.configure(api_key=settings.gemini_api_key)


class RAGService:
    def __init__(self, collection_name: str = None):
        self.vector_store = VectorStore(collection_name=collection_name)
        self.model = genai.GenerativeModel("gemini-2.5-flash")

    def answer(self, question: str, top_k: int = 5) -> Tuple[str, List[SourceChunk]]:
        chunks = self.vector_store.query(question, top_k=top_k)

        if not chunks:
            return (
                "I couldn't find relevant information in the uploaded documents.",
                [],
            )

        prompt = self._build_prompt(question, chunks)

        # Retry up to 3 times on quota errors
        for attempt in range(3):
            try:
                response = self.model.generate_content(prompt)
                answer_text = response.text
                break
            except Exception as e:
                error_msg = str(e).lower()
                if "quota" in error_msg or "rate" in error_msg or "429" in error_msg:
                    wait = (attempt + 1) * 10  # wait 10s, 20s, 30s
                    logger.warning(f"Gemini quota hit, waiting {wait}s (attempt {attempt+1})")
                    time.sleep(wait)
                    if attempt == 2:
                        return (
                            "I'm temporarily busy due to high demand. "
                            "Please try again in a minute.",
                            [],
                        )
                else:
                    raise

        source_chunks = [
            SourceChunk(
                content=doc.page_content[:500],
                page=doc.metadata.get("page"),
                source=doc.metadata.get("source"),
            )
            for doc in chunks
        ]

        return answer_text, source_chunks

    def _build_prompt(self, question: str, chunks: List[Document]) -> str:
        context = "\n\n---\n\n".join(
            f"[Page {doc.metadata.get('page', '?')}]\n{doc.page_content}"
            for doc in chunks
        )
        return f"""You are a helpful assistant answering questions based strictly on the provided document context.

CONTEXT FROM DOCUMENTS:
{context}

QUESTION:
{question}

INSTRUCTIONS:
- Answer using ONLY the information in the context above.
- If the context doesn't contain enough information, say so clearly.
- Be concise and specific.
- Mention which page the information came from when relevant.

ANSWER:"""