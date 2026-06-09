# RAG Engine

A local Retrieval-Augmented Generation (RAG) chatbot that answers questions
from your PDF documents. Built with FastAPI, LangChain, ChromaDB, and Google Gemini.

## What it does

1. You upload a PDF via the API
2. The engine extracts text, splits it into chunks, and stores embeddings in ChromaDB
3. You ask a question — the engine finds the most relevant chunks and sends them to Gemini
4. Gemini returns a grounded answer with page citations

## Tech stack

| Layer | Technology |
|---|---|
| API | FastAPI + Uvicorn |
| PDF processing | LangChain + PyPDF |
| Embeddings | Google text-embedding-004 |
| Vector store | ChromaDB (local, persistent) |
| LLM | Google Gemini 1.5 Flash |
| Config | Pydantic Settings |

## Setup

### 1. Clone and create virtual environment
```bash
git clone <your-repo-url>
cd rag-engine
python3 -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Configure environment
```bash
cp .env.example .env
# Open .env and add your GEMINI_API_KEY
```

Get your free Gemini API key at https://aistudio.google.com

### 3. Run the server
```bash
uvicorn app.main:app --reload --port 8000
```

API docs available at: http://localhost:8000/docs

## API endpoints

### POST /api/v1/ingest
Upload a PDF and store its embeddings.

```bash
curl -X POST http://localhost:8000/api/v1/ingest \
  -F "file=@your_document.pdf"
```

Response:
```json
{
  "message": "PDF ingested successfully",
  "filename": "your_document.pdf",
  "pages_processed": 12,
  "chunks_created": 47,
  "collection_name": "rag_documents"
}
```

### POST /api/v1/query
Ask a question about your uploaded documents.

```bash
curl -X POST http://localhost:8000/api/v1/query \
  -H "Content-Type: application/json" \
  -d '{"question": "What are the key findings?", "top_k": 3}'
```

Response:
```json
{
  "question": "What are the key findings?",
  "answer": "According to page 4, the key findings are...",
  "source_chunks": [
    {
      "content": "...",
      "page": 4,
      "source": "your_document.pdf"
    }
  ]
}
```

### GET /api/v1/ingest/stats
Check how many chunks are stored.

## Project structure