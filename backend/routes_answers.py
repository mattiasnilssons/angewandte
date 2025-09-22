# routes_answer.py
from fastapi import APIRouter
from pydantic import BaseModel
from .llm import generate_answer
from .search import retrieve_top_k  # your existing vector search

router = APIRouter()


class AskBody(BaseModel):
    question: str
    k: int = 6


@router.post("/answer")
def answer(body: AskBody):
    # 1) retrieve
    contexts = retrieve_top_k(body.question, k=body.k)
    # contexts must be list[{"source":..., "page":..., "text":...}]
    if not contexts:
        return {"answer": "No matching context found.", "contexts": []}
    # 2) generate
    try:
        out = generate_answer(body.question, contexts)
        return {"answer": out, "contexts": contexts}
    except Exception as e:
        # preserve your earlier debug output if you want
        return {
            "answer": f"LLM not configured ({e}). Here are the top contexts:",
            "contexts": contexts,
        }
