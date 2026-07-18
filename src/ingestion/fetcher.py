"""
Local document fetch layer (Phase 3.1). requests + browser UA; PDF text
via pypdf, HTML text via trafilatura. First rung of the per-URL fallback
chain: local fetch -> Gemini url_context -> skip+log. Fetched text goes
INLINE into the extraction prompt (M3's 1M context), which removes the
dependence on Gemini's fetcher (deadline expiries, unreadable domains).
"""

import io

import requests

_HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                   "AppleWebKit/537.36 (KHTML, like Gecko) "
                   "Chrome/126.0.0.0 Safari/537.36"),
    "Accept-Language": "en-IN,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/pdf,*/*;q=0.8",
}

FETCH_TIMEOUT = 45          # seconds per URL
# Per-document character cap. ~1.2M chars =~ 300K tokens — a 194-page
# annual report measured ~800K chars, and its segment/RM tables sit in the
# later notes, so the cap must not cut them. Still leaves most of M3's 1M
# context free; a 4-concall batch (~150K chars each) stays well under it.
MAX_DOC_CHARS = 1_200_000
_MIN_TEXT_CHARS = 200       # below this the "document" is a stub/error page


class FetchError(RuntimeError):
    """Local fetch/parse failed for ONE URL — caller falls back to
    Gemini url_context for that URL, never aborts the run."""


def fetch_document(url: str, timeout: int = FETCH_TIMEOUT) -> dict:
    """Fetch a URL and return {"text", "kind": "pdf"|"html", "pages",
    "char_count"}. Raises FetchError on any failure."""
    try:
        r = requests.get(url, headers=_HEADERS, timeout=timeout,
                         allow_redirects=True)
    except requests.RequestException as e:
        raise FetchError(f"request failed: {e}") from e
    if r.status_code != 200:
        raise FetchError(f"HTTP {r.status_code}")

    ctype = (r.headers.get("content-type") or "").lower()
    if "pdf" in ctype or r.content[:5] == b"%PDF-" or \
            url.lower().split("?")[0].endswith(".pdf"):
        doc = _pdf_to_text(r.content)
    else:
        doc = _html_to_text(r.text)

    if len(doc["text"]) < _MIN_TEXT_CHARS:
        raise FetchError(f"only {len(doc['text'])} chars of text extracted "
                         f"(stub, scan, or blocked page)")
    if len(doc["text"]) > MAX_DOC_CHARS:
        doc["text"] = doc["text"][:MAX_DOC_CHARS] + "\n[TRUNCATED]"
        doc["truncated"] = True
    doc["char_count"] = len(doc["text"])
    return doc


def _pdf_to_text(body: bytes) -> dict:
    from pypdf import PdfReader
    try:
        reader = PdfReader(io.BytesIO(body))
        pages = []
        for i, page in enumerate(reader.pages):
            text = page.extract_text() or ""
            if text.strip():
                # page markers let extraction fill page_or_timestamp
                pages.append(f"[page {i + 1}]\n{text}")
    except Exception as e:
        raise FetchError(f"pypdf failed: {e}") from e
    return {"text": "\n\n".join(pages), "kind": "pdf", "pages": len(reader.pages)}


def _html_to_text(html: str) -> dict:
    try:
        import trafilatura
        text = trafilatura.extract(html, include_tables=True,
                                   include_comments=False) or ""
    except Exception as e:
        raise FetchError(f"trafilatura failed: {e}") from e
    return {"text": text, "kind": "html", "pages": None}


# --- Phase 3.6: investor-presentation target validation ---------------------
# Observed mis-target: "investor presentation" hunts sometimes land on
# aggregator news-list pages; spending an extraction call there is waste.

_PRESENTATION_KEYWORDS = (
    "investor presentation", "earnings presentation", "investor deck",
    "order book", "capacity", "revenue mix", "market share", "capex",
)


def fetch_price_history(ticker: str, company_tokens: list,
                        range_: str = "1y", interval: str = "1mo"):
    """Monthly closes from Yahoo's public chart API (no auth). Returns
    ([(period_label, close)], url, long_name). Identity-validated via the
    response's longName — a mis-resolved ticker must fail loudly, never
    return another company's prices (the wisesheets/Macy's lesson)."""
    import datetime
    from urllib.parse import quote
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{quote(ticker, safe='')}.NS"
    r = requests.get(url, params={"range": range_, "interval": interval},
                     headers=_HEADERS, timeout=30)
    if r.status_code != 200:
        raise FetchError(f"yahoo chart HTTP {r.status_code}")
    try:
        res = r.json()["chart"]["result"][0]
        closes = res["indicators"]["quote"][0]["close"]
        stamps = res["timestamp"]
    except (KeyError, IndexError, TypeError, ValueError) as e:
        raise FetchError(f"yahoo chart shape: {e}") from e
    long_name = (res.get("meta") or {}).get("longName") or ""
    if company_tokens and not any(t in long_name.lower() for t in company_tokens):
        raise FetchError(f"identity mismatch: yahoo resolved '{ticker}.NS' "
                         f"to '{long_name}'")
    points = []
    for t, c in zip(stamps, closes):
        if c:
            points.append((datetime.date.fromtimestamp(t).strftime("%b %Y"),
                           round(float(c), 2)))
    if len(points) < 6:
        raise FetchError(f"only {len(points)} price points returned")
    return points, url, long_name


def looks_like_valuation_history(doc: dict, company_tokens: list) -> bool:
    """Validation BEFORE spending extraction on a multiple-history page:
    (a) the text carries >=4 year->multiple pairs, AND (b) it mentions
    THIS company. (b) is non-negotiable: wisesheets once resolved the
    ticker 'M&M.NS' to Macy's Inc — a wrong-company page passes any
    shape-only check and would ship another company's numbers."""
    import re as _re
    text = doc["text"]
    pairs = _re.findall(r"20\d\d\D{0,15}\d{1,3}\.\d{1,2}", text)
    if len(pairs) < 4:
        return False
    low = text[:20000].lower()
    return any(t in low for t in company_tokens)


def looks_like_presentation(doc: dict) -> bool:
    """Cheap validation BEFORE spending extraction: a real deck is a
    multi-page PDF, or a page whose text carries presentation vocabulary."""
    if doc["kind"] == "pdf":
        return (doc.get("pages") or 0) >= 5
    text = doc["text"][:20000].lower()
    hits = sum(1 for k in _PRESENTATION_KEYWORDS if k in text)
    return hits >= 2
