
# PDF AI Search (Python + Svelte)

An MVP for uploading PDFs and running AI-powered search (RAG).  
Backend: FastAPI + FAISS + sentence-transformers or OpenAI.  
Frontend: SvelteKit.

## Dev Setup

### 1) Backend
```bash
cd backend
python -m venv .venv && source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env  # edit if needed
uvicorn app:app --reload
```
By default the backend uses a local embedding model (`all-MiniLM-L6-v2`).  
You can switch to OpenAI embeddings + chat by setting `OPENAI_API_KEY` and `EMBEDDING_PROVIDER=openai` in `.env`.

### 2) Frontend
Open a second terminal:
```bash
cd frontend
npm install
# point the frontend to the backend origin (optional). Default: http://localhost:8000
echo 'VITE_API_BASE=http://localhost:8000' > .env
npm run dev
```
Visit http://localhost:5173

## Notes
- PDFs are saved to `backend/storage/docs`.
- The vector index is persisted to `backend/storage/index/faiss.index`.
- Metadata and chunk texts are stored in SQLite (`backend/storage/db.sqlite3`).

## License
MIT for the scaffold code. Uploaded PDFs remain your content. 
