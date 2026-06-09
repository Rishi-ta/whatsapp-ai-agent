import os
import logging
from pathlib import Path
from typing import List

from langchain_community.document_loaders import PyPDFLoader
from langchain_core.documents import Document

logger = logging.getLogger(__name__)


class PDFService:
    """
    Responsible for loading a PDF from disk and returning
    a list of LangChain Document objects (one per page).
    """

    def load(self, file_path: str) -> List[Document]:
        """
        Load a PDF and extract text page by page.

        Args:
            file_path: Absolute or relative path to the PDF file.

        Returns:
            List of Document objects. Each Document contains:
            - page_content: the raw text of that page
            - metadata: dict with 'source' (filename) and 'page' (page number)

        Raises:
            FileNotFoundError: if the path doesn't exist
            ValueError: if the PDF has no extractable text
        """
        path = Path(file_path)

        if not path.exists():
            raise FileNotFoundError(f"PDF not found at path: {file_path}")

        if path.suffix.lower() != ".pdf":
            raise ValueError(f"Expected a .pdf file, got: {path.suffix}")

        logger.info(f"Loading PDF: {path.name}")

        loader = PyPDFLoader(str(path))
        documents = loader.load()

        if not documents:
            raise ValueError(f"No text could be extracted from: {path.name}")

        # Filter out blank pages — they add noise to the vector store
        documents = [
            doc for doc in documents
            if doc.page_content.strip()
        ]

        logger.info(f"Extracted {len(documents)} non-empty pages from {path.name}")

        return documents