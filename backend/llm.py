# llm.py
from openai import OpenAI
from .settings import settings  # make sure this has OPENAI_API_KEY

_client = None

def client():
    global _client
    if _client is None:
        _client = OpenAI(api_key=settings.OPENAI_API_KEY)
    return _client

def generate_answer(question: str, contexts: list[dict]) -> str:
    """
    contexts: [{ "source": "file.pdf", "page": 30, "text": "..." }, ...]
    """
    # (Optional) de-dupe highly similar items
    seen = set()
    deduped = []
    for c in contexts:
        key = (c.get("source"), c.get("page"), (c.get("text") or "")[:200])
        if key in seen:
            continue
        seen.add(key)
        deduped.append(c)

    context_block = "\n\n---\n\n".join(
        f"[{i+1}] {c.get('source','?')} p.{c.get('page','?')}\n{c.get('text','')}"
        for i, c in enumerate(deduped)
    )

    system = (
        "You are a careful, citation-style assistant for cultural heritage conservation. "
        "Use ONLY the provided context. If the answer isn't in context, say so. "
        "Cite sources like [1], [2] corresponding to the provided list."
    )
    user = f"Question:\n{question}\n\nContext:\n{context_block}"

    resp = client().responses.create(
        model="gpt-5-nano",
        input=[{"role":"system","content":system},
               {"role":"user","content":user}]
    )
    return resp.output_text
