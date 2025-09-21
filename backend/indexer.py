
from __future__ import annotations
from pathlib import Path
from typing import List, Tuple
import faiss, numpy as np
from sqlalchemy.orm import Session
from .settings import settings
from .models import FaissMap, Chunk

class FaissIndex:
    def __init__(self, index_path: Path):
        self.index_path = Path(index_path)
        self._index = None

    @property
    def index(self) -> faiss.Index:
        if self._index is None:
            if self.index_path.exists():
                self._index = faiss.read_index(str(self.index_path))
            else:
                # Use cosine similarity via inner product on normalized vectors
                self._index = faiss.IndexFlatIP(384)  # default dimension for MiniLM; will work for OpenAI small (1536) if rebuilt
        return self._index

    def save(self):
        self.index_path.parent.mkdir(parents=True, exist_ok=True)
        faiss.write_index(self.index, str(self.index_path))

    def add_vectors(self, db: Session, chunk_ids: List[str], vectors: np.ndarray) -> List[int]:
        # If index is empty with wrong dimension, rebuild with correct dim
        if self.index.ntotal == 0 and self.index.d != vectors.shape[1]:
            self._index = faiss.IndexFlatIP(vectors.shape[1])
        start_ntotal = self.index.ntotal
        self.index.add(vectors)
        self.save()
        # Map FAISS ids to chunk_ids
        ids = list(range(start_ntotal, start_ntotal + vectors.shape[0]))
        for fid, cid in zip(ids, chunk_ids):
            db.add(FaissMap(vector_id=fid, chunk_id=cid))
        db.commit()
        return ids

    def search(self, query_vec: np.ndarray, top_k: int = 5) -> Tuple[np.ndarray, np.ndarray]:
        query_vec = np.asarray(query_vec, dtype=np.float32)
        if query_vec.ndim == 1:
            query_vec = query_vec[None, :]
        D, I = self.index.search(query_vec, top_k)
        return D[0], I[0]
