from __future__ import annotations
# at top with other imports
from fastapi.responses import FileResponse

import hashlib
import json
import numpy as np
import shutil
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Dict, Any

import fitz  # PyMuPDF
from fastapi import FastAPI, UploadFile, File, Depends, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from openai import OpenAI
from pydantic import BaseModel
from sqlalchemy.orm import Session

from .db import Base, engine, get_db
from .embeddings import get_embeddings
from .indexer import FaissIndex
from .models import Document, Chunk, FaissMap
from .processing import extract_text_from_pdf, clean_text, get_pdf_metadata, chunk_text_with_overlap

from .settings import settings
from fastapi import Body
import re

app = FastAPI(title="PDF AI Search API", version="0.1.0")

# Create DB tables
Base.metadata.create_all(bind=engine)


def read_pdf_meta(path: Path) -> dict:
    meta = {}
    try:
        with fitz.open(str(path)) as doc:
            info = doc.metadata or {}
            meta = {
                "title": info.get("title"),
                "author": info.get("author"),
                "subject": info.get("subject"),
                "keywords": info.get("keywords"),
                "creator": info.get("creator"),
                "producer": info.get("producer"),
                "creationDate": info.get("creationDate"),
                "modDate": info.get("modDate"),
                "pages": doc.page_count,
            }
    except Exception:
        # best-effort; don't crash if a file has odd metadata
        meta = {}
    try:
        stat = path.stat()
        meta["file_size"] = stat.st_size
        meta["file_size_mb"] = round(stat.st_size / (1024 * 1024), 2)
        meta["mtime"] = datetime.fromtimestamp(stat.st_mtime).isoformat()
    except Exception:
        pass
    return meta


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


@app.get("/api/documents/{doc_id}/download")
def download_document(doc_id: str, db: Session = Depends(get_db)):
    """
    Stream the original PDF back to the browser.
    """
    doc = db.query(Document).filter(Document.id == doc_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    path = Path(doc.path)
    # basic safety & existence checks
    if not path.is_file() or path.suffix.lower() != ".pdf":
        raise HTTPException(status_code=404, detail="File not found on disk")

    # Return with a friendly filename; forces download in most browsers
    return FileResponse(
        path=path,
        media_type="application/pdf",
        filename=doc.filename,  # Content-Disposition
    )


@app.get("/api/config_status")
def config_status():
    return {
        "llm_provider": settings.LLM_PROVIDER,
        "chat_model": settings.OPENAI_CHAT_MODEL,
        "has_openai_key": bool(settings.OPENAI_API_KEY),
        "embedding_provider": settings.EMBEDDING_PROVIDER,
        "embedding_model": (
            settings.EMBEDDING_MODEL
            if settings.EMBEDDING_PROVIDER != "openai"
            else settings.OPENAI_EMBEDDING_MODEL
        ),
        "index_size": faiss_index.index.ntotal,
    }


def _sha256_of_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


@app.post("/api/upload")
async def upload_pdf(file: UploadFile = File(...), db: Session = Depends(get_db)):
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported.")

    # Save uploaded file
    dest = settings.DATA_DIR / "docs" / file.filename
    dest.parent.mkdir(parents=True, exist_ok=True)
    with open(dest, "wb") as f:
        shutil.copyfileobj(file.file, f)

    # Hash to detect duplicates
    sha = _sha256_of_file(dest)

    existing = db.query(Document).filter(Document.sha256 == sha).first()
    if existing:
        return {
            "document_id": existing.id,
            "filename": existing.filename,
            "title": existing.title,
            "author": getattr(existing, "author", None),
            "year": getattr(existing, "year", None),
            "pages": existing.pages,
            "chunks_indexed": db.query(Chunk).filter(Chunk.document_id == existing.id).count(),
            "meta": json.loads(getattr(existing, "meta_json", "") or "{}"),
            "note": "Duplicate file detected by SHA-256; using existing index."
        }

    # Extract page texts
    pages = extract_text_from_pdf(dest)
    pages_clean = [(pno, clean_text(txt)) for pno, txt in pages]

    # Read PDF metadata
    pdf_meta = get_pdf_metadata(dest)
    author = pdf_meta.get("author") or guess_author_from_pages(pages_clean)
    year = pdf_meta.get("year")

    # Create Document row
    doc = Document(
        filename=file.filename,
        title=pdf_meta.get("title") or file.filename,
        author=author,
        year=year,
        meta_json=json.dumps({
            **pdf_meta,
            "guessed_author": author if not pdf_meta.get("author") else None,
            "file_size": dest.stat().st_size,
            "file_size_mb": round(dest.stat().st_size / (1024 * 1024), 2),
        }),
        path=str(dest),
        pages=len(pages_clean),
        sha256=sha,
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)

    # Build chunks
    all_chunks: List[Chunk] = []
    for pno, text in pages_clean:
        for ci, (start, end, ctext) in enumerate(
            chunk_text_with_overlap(text, settings.CHUNK_SIZE, settings.CHUNK_OVERLAP)
        ):
            all_chunks.append(
                Chunk(
                    document_id=doc.id,
                    chunk_index=ci,
                    text=ctext,
                    page=pno,
                    start_char=start,
                    end_char=end,
                )
            )

    if all_chunks:
        db.add_all(all_chunks)
        db.commit()

        # Embed + normalize + index
        texts = [c.text for c in all_chunks]
        vectors = get_emb().embed_documents(texts)
        norms = np.linalg.norm(vectors, axis=1, keepdims=True) + 1e-12
        vectors = vectors / norms

        chunk_ids = [c.id for c in all_chunks]
        faiss_index.add_vectors(db, chunk_ids, vectors)

    return {
        "document_id": doc.id,
        "filename": doc.filename,
        "title": doc.title,
        "author": doc.author,
        "year": doc.year,
        "pages": doc.pages,
        "chunks_indexed": len(all_chunks),
        "meta": json.loads(doc.meta_json or "{}"),
    }





@app.get("/api/documents")
def list_documents(include_meta: bool = True, db: Session = Depends(get_db)):
    docs = db.query(Document).order_by(Document.uploaded_at.desc()).all()
    out = []
    for d in docs:
        item = {
            "id": d.id,
            "filename": d.filename,
            "title": d.title,
            "author": d.author,
            "year": d.year,
            "pages": d.pages,
            "uploaded_at": d.uploaded_at,
        }
        if include_meta:
            # Prefer meta stored in DB; fallback to file meta if empty
            stored = {}
            try:
                stored = json.loads(d.meta_json or "{}")
            except Exception:
                stored = {}
            if not stored:
                stored = read_pdf_meta(Path(d.path)) or {}
            # Normalize convenient fields for the UI
            stored.setdefault("title", d.title)
            stored.setdefault("author", d.author)
            stored.setdefault("pages", d.pages)
            item["meta"] = stored
        out.append(item)
    return out



@app.get("/api/search")
def search(
    q: str = Query(..., min_length=2), top_k: int = 8, db: Session = Depends(get_db)
):
    if faiss_index.index.ntotal == 0:
        return {"results": [], "note": "Index is empty. Upload PDFs first."}

    # embed + normalize
    qv = get_emb().embed_query(q)
    qv = qv / (np.linalg.norm(qv) + 1e-12)

    # over-fetch to allow de-duplication
    fetch_k = max(top_k * 10, 50)
    D, I = faiss_index.search(qv, top_k=fetch_k)

    seen_vector_ids: set[int] = set()
    best_by_filepage: dict[tuple[str, int], dict] = {}

    for score, fid in zip(
        np.array(D).flatten().tolist(), np.array(I).flatten().tolist()
    ):
        if fid is None or fid == -1:
            continue
        if fid in seen_vector_ids:
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

        key = (doc.filename, int(chunk.page or 0))  # <— dedupe by filename + page
        snippet = (chunk.text or "")[:400] + (
            "..." if chunk.text and len(chunk.text) > 400 else ""
        )

        item = {
            "score": float(score),
            "chunk_id": chunk.id,
            "page": int(chunk.page or 0),
            "document": {
                "id": doc.id,
                "title": doc.title,
                "filename": doc.filename,
                "author": doc.author,
                "year": doc.year,
            },
            "snippet": snippet,
        }

        prev = best_by_filepage.get(key)
        if (prev is None) or (item["score"] > prev["score"]):
            best_by_filepage[key] = item

    results = sorted(best_by_filepage.values(), key=lambda r: r["score"], reverse=True)[
        :top_k
    ]
    return {"results": results}


@app.post("/api/ask")
async def ask(req: AskRequest, db: Session = Depends(get_db)):
    if faiss_index.index.ntotal == 0:
        raise HTTPException(
            status_code=400, detail="Index is empty. Upload PDFs first."
        )

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
            "contexts": contexts,
        }

    # Build system messages
    system_msgs = []
    if req.personality:
        for stmt in req.personality:
            if stmt.strip():
                system_msgs.append({"role": "system", "content": stmt.strip()})
    # Default RAG instructions always included
    system_msgs.append(
        {
            "role": "system",
            "content": (
                "You are an assistant for a conservation/restoration department. "
                "Answer the user's question using ONLY the provided context from uploaded PDFs. "
                "Cite the filename and page in brackets like [filename p.12] when you use a passage. "
                "If the answer isn't in the context, say you don't know."
            ),
        }
    )

    # User message with question + contexts
    joined = "\n\n----\n\n".join(contexts[: req.top_k])
    user_msg = {
        "role": "user",
        "content": f"Question: {req.question}\n\nContext:\n{joined}",
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



@app.patch("/api/documents/{doc_id}")
def update_document_meta(
    doc_id: str,
    payload: Dict[str, Any] = Body(...),
    db: Session = Depends(get_db),
):
    """
    JSON body can contain:
    {
      "title": "New title",       # optional
      "author": "New author",     # optional
      "year": 2005,               # optional (int)
      "meta": { ... }             # optional dict, merged into meta_json
    }
    """
    doc = db.query(Document).filter(Document.id == doc_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    changed = False

    title = payload.get("title")
    author = payload.get("author")
    year = payload.get("year")
    extra_meta = payload.get("meta")

    if title is not None and title != doc.title:
        doc.title = title
        changed = True
    if author is not None and author != doc.author:
        doc.author = author
        changed = True
    if year is not None and year != doc.year:
        try:
            doc.year = int(year)
        except Exception:
            raise HTTPException(status_code=400, detail="year must be an integer")
        changed = True

    if extra_meta and isinstance(extra_meta, dict):
        current = {}
        try:
            current = json.loads(doc.meta_json or "{}")
        except Exception:
            current = {}
        current.update(extra_meta)
        doc.meta_json = json.dumps(current)
        changed = True

    if changed:
        db.add(doc)
        db.commit()
        db.refresh(doc)

    # Return the same shape as list_documents (for easy UI refresh)
    meta = {}
    try:
        meta = json.loads(doc.meta_json or "{}")
    except Exception:
        meta = {}
    meta.setdefault("title", doc.title)
    meta.setdefault("author", doc.author)
    meta.setdefault("pages", doc.pages)

    return {
        "ok": True,
        "document": {
            "id": doc.id,
            "filename": doc.filename,
            "title": doc.title,
            "author": doc.author,
            "year": doc.year,
            "pages": doc.pages,
            "uploaded_at": doc.uploaded_at,
            "meta": meta,
        },
    }


NAME_RE = re.compile(r"\b([A-ZÄÖÜ][a-zäöüß]+(?:[-\s][A-ZÄÖÜ][a-zäöüß]+){0,2})\b")

def guess_author_from_pages(pages_clean) -> str | None:
    """
    Very lightweight heuristic:
    - Scan first page lines
    - Prefer lines following cues like 'Autor', 'Author', 'by', 'von'
    - Otherwise pick a plausible capitalized name near the bottom half
    """
    if not pages_clean:
        return None

    page_no, text = pages_clean[0]
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    cues = ("autor", "author", "by", "von")

    # 1) cue-based search
    for i, ln in enumerate(lines):
        low = ln.lower()
        if any(c in low for c in cues):
            # try this line or the next line for a name
            for candidate in (ln, lines[i+1] if i+1 < len(lines) else ""):
                m = NAME_RE.search(candidate)
                if m:
                    return m.group(1)

    # 2) generic name-looking line from bottom half of the page
    half = len(lines) // 2
    for ln in lines[half:]:
        m = NAME_RE.search(ln)
        if m:
            return m.group(1)

    return None
