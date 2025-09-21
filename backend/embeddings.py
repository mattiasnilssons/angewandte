
from __future__ import annotations
from typing import List
import numpy as np
from .settings import settings

class Embeddings:
    def embed_documents(self, texts: List[str]) -> np.ndarray: ...
    def embed_query(self, text: str) -> np.ndarray: ...

class SentenceTransformerEmbeddings(Embeddings):
    def __init__(self, model_name: str):
        from sentence_transformers import SentenceTransformer
        self.model = SentenceTransformer(model_name)

    def _encode(self, texts: List[str]) -> np.ndarray:
        vecs = self.model.encode(texts, show_progress_bar=False, normalize_embeddings=True)
        return np.array(vecs, dtype=np.float32)

    def embed_documents(self, texts: List[str]) -> np.ndarray:
        return self._encode(texts)

    def embed_query(self, text: str) -> np.ndarray:
        return self._encode([text])[0]

class OpenAIEmbeddings(Embeddings):
    def __init__(self, model: str):
        if not settings.OPENAI_API_KEY:
            raise RuntimeError("OPENAI_API_KEY missing")
        from openai import OpenAI
        self.client = OpenAI(api_key=settings.OPENAI_API_KEY)
        self.model = model

    def embed_documents(self, texts: List[str]) -> np.ndarray:
        # Batch with one request per 1000 tokens-ish; here we do simple loop for clarity
        out = []
        for t in texts:
            vec = self.embed_query(t)
            out.append(vec)
        return np.vstack(out).astype(np.float32)

    def embed_query(self, text: str) -> np.ndarray:
        resp = self.client.embeddings.create(model=self.model, input=text)
        return np.array(resp.data[0].embedding, dtype=np.float32)

def get_embeddings() -> Embeddings:
    if settings.EMBEDDING_PROVIDER.lower().startswith("openai"):
        return OpenAIEmbeddings(settings.OPENAI_EMBEDDING_MODEL)
    # default
    model = settings.EMBEDDING_MODEL.replace("sentence-transformers/", "")
    return SentenceTransformerEmbeddings(model)
