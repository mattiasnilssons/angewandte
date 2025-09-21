
# Backend (FastAPI)

## Quickstart
```bash
cd backend
python -m venv .venv && source .venv/bin/activate  # on Windows: .venv\Scripts\activate
pip install -r requirements.txt

# optional: copy .env.example to .env and edit
cp .env.example .env

# run
uvicorn app:app --reload
```

The API will be at `http://localhost:8000`. Docs at `http://localhost:8000/docs`.

## Environment (.env)
```
# Where files and index live
DATA_DIR=storage
DB_URL=sqlite:///storage/db.sqlite3
FAISS_INDEX_PATH=storage/index/faiss.index

# Embeddings
EMBEDDING_PROVIDER=sentence-transformers  # or "openai"
EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2
OPENAI_API_KEY=
OPENAI_EMBEDDING_MODEL=text-embedding-3-small

# Chunking
CHUNK_SIZE=800
CHUNK_OVERLAP=120

# CORS origins (frontend dev server)
CORS_ORIGINS=http://localhost:5173
```

## Endpoints
- `POST /api/upload` – multipart PDF upload
- `GET /api/documents` – list uploaded docs
- `GET /api/search?q=...&top_k=8` – vector search
- `POST /api/ask` – RAG answer (requires OpenAI API key)
