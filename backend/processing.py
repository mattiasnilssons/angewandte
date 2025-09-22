from __future__ import annotations
from pathlib import Path
from typing import Dict, Any
import re
from datetime import datetime
import fitz  # PyMuPDF


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
            text_pages = [(i + 1, p) for i, p in enumerate(pages)]
        else:
            text_pages = [(i + 1, p) for i, p in enumerate(pages) if p.strip()]
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


def chunk_text_with_overlap(
    text: str, chunk_size: int = 800, overlap: int = 120
) -> list[tuple[int, int, str]]:
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


def _parse_pdf_date(val: str | None) -> str | None:
    # PDF dates often look like: D:YYYYMMDDHHmmSS+TZ
    if not val:
        return None
    m = re.match(r"D:(\d{4})(\d{2})?(\d{2})?", val)
    if not m:
        # sometimes plain ISO or other string — return as-is
        return val
    year = int(m.group(1))
    month = int(m.group(2) or "1")
    day = int(m.group(3) or "1")
    try:
        return datetime(year, month, day).isoformat()
    except Exception:
        return str(year)


def _year_from_dates(*vals: str | None) -> int | None:
    for v in vals:
        if not v:
            continue
        m = re.search(r"(\d{4})", v)
        if m:
            y = int(m.group(1))
            if 1400 <= y <= 2100:  # sanity
                return y
    return None


def get_pdf_metadata(path) -> Dict[str, Any]:
    meta: Dict[str, Any] = {}
    try:
        with fitz.open(str(path)) as doc:
            info = doc.metadata or {}
            meta["title"] = info.get("title") or info.get("Title")
            meta["author"] = info.get("author") or info.get("Author")
            meta["creationDate_raw"] = info.get("creationDate") or info.get(
                "CreationDate"
            )
            meta["modDate_raw"] = info.get("modDate") or info.get("ModDate")
            meta["creationDate"] = _parse_pdf_date(meta["creationDate_raw"])
            meta["modDate"] = _parse_pdf_date(meta["modDate_raw"])
            meta["pages"] = doc.page_count
    except Exception:
        # ignore metadata failures
        pass

    # Derive year
    meta["year"] = _year_from_dates(
        meta.get("creationDate_raw"),
        meta.get("modDate_raw"),
        meta.get("creationDate"),
        meta.get("modDate"),
    )
    return meta
