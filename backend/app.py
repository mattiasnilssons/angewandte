
from __future__ import annotations
from fastapi import FastAPI, UploadFile, File, Depends, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from typing import List, Optional
from pathlib import Path
import shutil, os, numpy as np
from pydantic import BaseModel
from openai import OpenAI

from .settings import settings
from .db import Base, engine, get_db
from .models import Document, Chunk, FaissMap
from .processing import extract_text_from_pdf, clean_text, chunk_text_with_overlap
from .embeddings import get_embeddings
from .indexer import FaissIndex

app = FastAPI(title="PDF AI Search API", version="0.1.0")

# Create DB tables
Base.metadata.create_all(bind=engine)


class AskRequest(BaseModel):
    question: str
    top_k: int = 8
    personality: Optional[List[str]] = None


# CORS
origins = [o.strip() for o in settings.CORS_ORIGINS.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins or ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

emb = None
faiss_index = FaissIndex(settings.FAISS_INDEX_PATH)

def get_emb():
    global emb
    if emb is None:
        emb = get_embeddings()
    return emb

@app.get("/api/config_status")
def config_status():
    return {
        "llm_provider": settings.LLM_PROVIDER,
        "chat_model": settings.OPENAI_CHAT_MODEL,
        "has_openai_key": bool(settings.OPENAI_API_KEY),
        "embedding_provider": settings.EMBEDDING_PROVIDER,
        "embedding_model": settings.EMBEDDING_MODEL if settings.EMBEDDING_PROVIDER!="openai" else settings.OPENAI_EMBEDDING_MODEL,
        "index_size": faiss_index.index.ntotal
    }


@app.post("/api/upload")
async def upload_pdf(file: UploadFile = File(...), db: Session = Depends(get_db)):
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported.")
    # Save file
    dest = settings.DATA_DIR / "docs" / file.filename
    with open(dest, "wb") as f:
        shutil.copyfileobj(file.file, f)
    # Extract text
    pages = extract_text_from_pdf(dest)
    pages_clean = [(pno, clean_text(txt)) for pno, txt in pages]
    # Save document
    doc = Document(filename=file.filename, title=file.filename, path=str(dest), pages=len(pages_clean))
    db.add(doc); db.commit(); db.refresh(doc)

    # Chunk + record
    all_chunks: List[Chunk] = []
    for pno, text in pages_clean:
        for ci, (start, end, ctext) in enumerate(chunk_text_with_overlap(text, settings.CHUNK_SIZE, settings.CHUNK_OVERLAP)):
            ch = Chunk(document_id=doc.id, chunk_index=ci, text=ctext, page=pno, start_char=start, end_char=end)
            all_chunks.append(ch)
    db.add_all(all_chunks)
    db.commit()

    # Embed + index
    texts = [c.text for c in all_chunks]
    vectors = get_emb().embed_documents(texts)
    # normalize for cosine
    norms = np.linalg.norm(vectors, axis=1, keepdims=True) + 1e-12
    vectors = vectors / norms
    chunk_ids = [c.id for c in all_chunks]
    faiss_index.add_vectors(db, chunk_ids, vectors)

    return {
        "document_id": doc.id,
        "filename": doc.filename,
        "pages": doc.pages,
        "chunks_indexed": len(all_chunks)
    }

@app.get("/api/documents")
def list_documents(db: Session = Depends(get_db)):
    docs = db.query(Document).order_by(Document.uploaded_at.desc()).all()
    return [{"id": d.id, "filename": d.filename, "title": d.title, "pages": d.pages, "uploaded_at": d.uploaded_at} for d in docs]


from collections import defaultdict

@app.get("/api/search")
def search(q: str = Query(..., min_length=2), top_k: int = 8, db: Session = Depends(get_db)):
    if faiss_index.index.ntotal == 0:
        return {"results": [], "note": "Index is empty. Upload PDFs first."}

    qv = get_emb().embed_query(q)
    qv = qv / (np.linalg.norm(qv) + 1e-12)

    fetch_k = max(top_k * 10, 50)  # over-fetch to allow dedupe
    D, I = faiss_index.search(qv, top_k=fetch_k)

    seen_vector_ids = set()
    best_by_page: dict[tuple[str,int], dict] = {}  # (doc_id, page) -> result

    for score, fid in zip(D.flatten().tolist(), I.flatten().tolist()):
        if fid is None or fid == -1 or fid in seen_vector_ids:
            continue
        seen_vector_ids.add(fid)

        fmap = db.query(FaissMap).filter(FaissMap.vector_id == int(fid)).first()
        if not fmap:
            continue
        chunk = db.query(Chunk).filter(Chunk.id == fmap.chunk_id).first()
        if not chunk:
            continue
        doc = db.query(Document).filter(Document.id == chunk.document_id).first()
        if not doc:
            continue

        key = (doc.id, chunk.page)
        snippet = chunk.text[:400] + ("..." if len(chunk.text) > 400 else "")
        item = {
            "score": float(score),
            "chunk_id": chunk.id,
            "page": chunk.page,
            "document": {"id": doc.id, "title": doc.title, "filename": doc.filename},
            "snippet": snippet
        }

        prev = best_by_page.get(key)
        if (prev is None) or (item["score"] > prev["score"]):
            best_by_page[key] = item

    results = sorted(best_by_page.values(), key=lambda r: r["score"], reverse=True)[:top_k]
    return {"results": results}

@app.post("/api/ask")
async def ask(req: AskRequest, db: Session = Depends(get_db)):
    if faiss_index.index.ntotal == 0:
        raise HTTPException(status_code=400, detail="Index is empty. Upload PDFs first.")

    # Embed and search
    qv = get_emb().embed_query(req.question)
    qv = qv / (np.linalg.norm(qv) + 1e-12)
    D, I = faiss_index.search(qv, top_k=req.top_k)

    contexts = []
    for fid in I.tolist():
        fmap = db.query(FaissMap).filter(FaissMap.vector_id == int(fid)).first()
        if not fmap:
            continue
        chunk = db.query(Chunk).filter(Chunk.id == fmap.chunk_id).first()
        if not chunk:
            continue
        doc = db.query(Document).filter(Document.id == chunk.document_id).first()
        contexts.append(f"[{doc.filename} p.{chunk.page}] {chunk.text}")

    if not contexts:
        return {"answer": "No relevant context found.", "contexts": []}

    # If LLM not configured → return contexts only
    if settings.LLM_PROVIDER != "openai" or not settings.OPENAI_API_KEY:
        return {
            "answer": "LLM not configured. Showing top contexts only.",
            "contexts": contexts
        }

    # Build system messages
    system_msgs = []
    if req.personality:
        for stmt in req.personality:
            if stmt.strip():
                system_msgs.append({"role": "system", "content": stmt.strip()})
    # Default RAG instructions always included
    system_msgs.append({
        "role": "system",
        "content": (
            "You are an assistant for a conservation/restoration department. "
            "Answer the user's question using ONLY the provided context from uploaded PDFs. "
            "Cite the filename and page in brackets like [filename p.12] when you use a passage. "
            "If the answer isn't in the context, say you don't know."
        )
    })

    # User message with question + contexts
    joined = "\n\n----\n\n".join(contexts[:req.top_k])
    user_msg = {
        "role": "user",
        "content": f"Question: {req.question}\n\nContext:\n{joined}"
    }

    # Call OpenAI

    client = OpenAI(api_key=settings.OPENAI_API_KEY)
    resp = client.chat.completions.create(
        model=settings.OPENAI_CHAT_MODEL,
        messages=system_msgs + [user_msg],
        temperature=1,
    )
    answer = resp.choices[0].message.content
    return {"answer": answer, "contexts": contexts}

