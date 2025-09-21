
# Backend (FastAPI)

## Quickstart (Poetry)
from the repo root, then: 
```
cd backend
```
if you don't have Poetry yet:
```
curl -sSL https://install.python-poetry.org | python3 -

poetry install            # installs all deps into a Poetry venv
poetry run python -m pip install --upgrade pip setuptools wheel  # optional

# env
cp .env.example .env      # then edit .env (API keys, etc.)

# run the API (either form works)
poetry run uvicorn backend.app:app --reload
# or, if you kept the script in pyproject.toml:
# poetry run api

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
