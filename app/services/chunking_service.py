import logging
from typing import List

from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.documents import Document

logger = logging.getLogger(__name__)


class ChunkingService:
    """
    Splits large Document pages into smaller, overlapping chunks.

    Why chunk at all?
    - Embedding models have token limits (~8k tokens for most)
    - Smaller chunks = more precise embeddings
    - A 20-page PDF as one chunk would produce a vague, averaged embedding
      that matches nothing well
    """

    def __init__(self, chunk_size: int = 1000, chunk_overlap: int = 200):
        """
        Args:
            chunk_size:    Target character count per chunk.
            chunk_overlap: How many characters the next chunk
                           shares with the previous one.
        """
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

        self.splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            # These separators are tried in order.
            # The splitter uses the first one that fits.
            # This keeps semantic units (paragraphs, sentences) intact.
            separators=["\n\n", "\n", ". ", " ", ""],
            length_function=len,
        )

    def split(self, documents: List[Document]) -> List[Document]:
        """
        Split a list of Documents into smaller chunks.

        Metadata (source filename, page number) is automatically
        carried forward into every chunk by LangChain.

        Args:
            documents: Output from PDFService.load()

        Returns:
            List of smaller Document chunks, each with inherited metadata.
        """
        if not documents:
            raise ValueError("No documents provided to chunk.")

        chunks = self.splitter.split_documents(documents)

        if not chunks:
            raise ValueError("Chunking produced no output. Check your PDF content.")

        logger.info(
            f"Split {len(documents)} pages into {len(chunks)} chunks "
            f"(size={self.chunk_size}, overlap={self.chunk_overlap})"
        )

        return chunks