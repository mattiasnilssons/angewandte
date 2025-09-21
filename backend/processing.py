
from __future__ import annotations
import re
from typing import List, Tuple
from pathlib import Path

def extract_text_from_pdf(path: Path) -> list[tuple[int, str]]:
    """
    Returns list of (page_number_1_based, text) for each page.
    Prefers PyMuPDF; falls back to pdfminer.six.
    """
    text_pages: list[tuple[int, str]] = []
    try:
        import fitz  # PyMuPDF
        with fitz.open(path) as doc:
            for i, page in enumerate(doc, start=1):
                text = page.get_text("text") or ""
                text_pages.append((i, text))
        return text_pages
    except Exception:
        pass

    # Fallback to pdfminer
    try:
        from pdfminer.high_level import extract_text
        full_text = extract_text(str(path)) or ""
        # naive split by form feed or page markers if any
        pages = re.split(r"\f|\n?\s*Page\s+\d+\s*\n", full_text)
        if len(pages) == 1:
            text_pages = [(i+1, p) for i, p in enumerate(pages)]
        else:
            text_pages = [(i+1, p) for i, p in enumerate(pages) if p.strip()]
        return text_pages
    except Exception as e:
        raise RuntimeError(f"Failed to extract text from {path}: {e}")

def clean_text(s: str) -> str:
    # remove hyphenation at line breaks: "conser-\nvation" -> "conservation"
    s = re.sub(r"(\w)-\n(\w)", r"\1\2", s)
    # normalize line breaks to spaces
    s = re.sub(r"\s*\n\s*", " ", s)
    # collapse whitespace
    s = re.sub(r"\s{2,}", " ", s)
    return s.strip()

def chunk_text_with_overlap(text: str, chunk_size: int = 800, overlap: int = 120) -> list[tuple[int,int,str]]:
    """
    Returns list of (start_char, end_char, chunk_text)
    """
    if not text:
        return []
    chunks = []
    n = len(text)
    start = 0
    while start < n:
        end = min(n, start + chunk_size)
        chunk = text[start:end]
        chunks.append((start, end, chunk))
        if end == n:
            break
        start = max(end - overlap, 0)
    return chunks
