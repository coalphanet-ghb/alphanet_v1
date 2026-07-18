"""
Deterministic screener.in parser (Phase 1) — ZERO LLM.

Fetches a company page and turns every table cell into a metric candidate
(same shape the s3 validation gate already consumes), plus the Documents
links (concall transcripts, annual reports) that replace ddgs transcript
hunting. This is the numeric backbone: multi-year P&L / BS / CF / ratios /
shareholding + the top-ratios card (CMP, market cap, P/E, ROE...).

Design: emit PRINTED strings (value_printed / period_printed) and let the
existing validation gate parse, dedup and prioritize — one gate, one set of
rules, whether numbers came from a model or from HTML.
"""

import re
from datetime import date

import requests
from bs4 import BeautifulSoup

from src.ingestion.metric_names import canon_name

_HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                   "AppleWebKit/537.36 (KHTML, like Gecko) "
                   "Chrome/126.0.0.0 Safari/537.36"),
    "Accept-Language": "en-IN,en;q=0.9",
}

_MONTHS = {m: i + 1 for i, m in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun",
     "jul", "aug", "sep", "oct", "nov", "dec"])}


class ScreenerParseError(RuntimeError):
    pass


def _fiscal_quarter_label(header: str) -> str | None:
    """'Dec 2025' -> 'Q3FY26' (Indian FY: Apr-Mar)."""
    m = re.match(r"([a-z]{3})\w*\s+(\d{4})", header.strip().lower())
    if not m or m.group(1) not in _MONTHS:
        return None
    mo, yr = _MONTHS[m.group(1)], int(m.group(2))
    if mo >= 4:
        q, fy = (mo - 4) // 3 + 1, yr + 1
    else:
        q, fy = 4, yr
    return f"Q{q}FY{fy % 100}"


def fetch_page(url: str, timeout: int = 20) -> str:
    r = requests.get(url, headers=_HEADERS, timeout=timeout)
    if r.status_code != 200:
        raise ScreenerParseError(f"HTTP {r.status_code} fetching {url}")
    if "data-table" not in r.text:
        raise ScreenerParseError(f"no data tables in response from {url} "
                                 f"(blocked or layout change?)")
    return r.text


def _cell_text(td) -> str:
    return td.get_text(" ", strip=True)


def _parse_section_table(section, quarterly: bool) -> list[dict]:
    """One screener data-table -> candidates. Column headers are periods;
    row label is the metric name. Quarterly tables get QxFYyy labels so the
    period parser types them as quarters (a 'Mar 2026' column means Q4FY26
    in #quarters but FY26 in #profit-loss)."""
    table = section.find("table", class_="data-table")
    if table is None:
        return []
    header_cells = table.find("thead").find_all("th")
    periods = []
    for th in header_cells[1:]:
        h = _cell_text(th)
        if quarterly:
            periods.append(_fiscal_quarter_label(h) or h)
        else:
            periods.append(h)          # "Mar 2025" -> annual FY25; "TTM" skipped by gate

    out = []
    for tr in table.find("tbody").find_all("tr"):
        tds = tr.find_all("td")
        if not tds:
            continue
        label = _cell_text(tds[0]).replace("+", "").strip()
        if not label:
            continue
        name = canon_name(label)
        if not name:
            continue
        for period, td in zip(periods, tds[1:]):
            val = _cell_text(td)
            if not val or val in ("-", "—", ""):
                continue
            out.append({"name": name, "label_printed": label,
                        "value_printed": val, "period_printed": period,
                        "ambiguous": False})
    return out


def _parse_top_ratios(soup) -> list[dict]:
    """The card at the top: CMP, market cap, P/E, book value, div yield,
    ROCE, ROE. These are point-in-time — carry an explicit day period."""
    ul = soup.find("ul", id="top-ratios")
    if ul is None:
        return []
    today = date.today().isoformat()
    out = []
    for li in ul.find_all("li"):
        name_el = li.find("span", class_="name")
        val_el = li.find("span", class_="value") or li.find("span", class_="nowrap")
        if not name_el or not val_el:
            continue
        label = _cell_text(name_el)
        name = canon_name(label)
        if not name:
            continue
        out.append({"name": name, "label_printed": label,
                    "value_printed": _cell_text(val_el),
                    "period_printed": None, "ambiguous": False,
                    "period_parsed": {"period_type": "day",
                                      "period_start": today,
                                      "period_end": today}})
    return out


def _parse_document_links(soup, base: str = "https://www.screener.in") -> dict:
    """Concall transcript + annual report links from the Documents section."""
    links = {"concall_transcripts": [], "annual_reports": [], "concall_ppts": []}
    docs = soup.find("section", id="documents")
    if docs is None:
        return links
    for div in docs.find_all("div", class_="documents"):
        classes = div.get("class") or []
        for a in div.find_all("a", href=True):
            href = a["href"]
            if href.startswith("/"):
                href = base + href
            text = _cell_text(a)
            if "concalls" in classes and "transcript" in text.lower():
                # the surrounding li usually carries the month label
                li = a.find_parent("li")
                label = _cell_text(li).split("Transcript")[0].strip() if li else ""
                links["concall_transcripts"].append({"url": href, "label": label})
            elif "concalls" in classes and text.strip().lower() == "ppt":
                # Phase 5.6: the quarterly investor deck (BSE-hosted) —
                # replaces ddgs presentation hunting, which kept landing
                # on aggregator list pages
                li = a.find_parent("li")
                label = _cell_text(li).split("Transcript")[0].split("Notes")[0] \
                    .split("PPT")[0].strip() if li else ""
                links["concall_ppts"].append({"url": href, "label": label})
            elif "annual-reports" in classes:
                links["annual_reports"].append({"url": href, "label": text})
    return links


def parse_company_page(url: str, html: str | None = None) -> dict:
    """-> {candidates: [...], doc_links: {...}, about: str, warnings: [...]}
    Candidate shape matches the s3 validation gate (doc_class/url attached
    by the caller)."""
    html = html or fetch_page(url)
    soup = BeautifulSoup(html, "html.parser")
    warnings = []
    candidates: list[dict] = []

    sections = {"quarters": True, "profit-loss": False, "balance-sheet": False,
                "cash-flow": False, "ratios": False, "shareholding": True}
    for sec_id, quarterly in sections.items():
        section = soup.find("section", id=sec_id)
        if section is None:
            warnings.append(f"section #{sec_id} not found")
            continue
        got = _parse_section_table(section, quarterly)
        if not got:
            warnings.append(f"section #{sec_id} yielded no rows")
        candidates += got

    top = _parse_top_ratios(soup)
    if not top:
        warnings.append("top-ratios card not found")
    candidates += top

    about_el = soup.find("div", class_="company-profile") or soup.find("p", class_="sub")
    about = about_el.get_text(" ", strip=True)[:1200] if about_el else ""

    if len(candidates) < 30:
        raise ScreenerParseError(
            f"only {len(candidates)} candidates parsed from {url} — layout "
            f"changed or page blocked; falling back to LLM extraction. "
            f"warnings: {warnings}")

    return {"candidates": candidates, "doc_links": _parse_document_links(soup),
            "about": about, "warnings": warnings}


def get_document_links(slug: str) -> dict:
    """Lightweight fetch used by s1 discovery: transcript + AR links only."""
    url = f"https://www.screener.in/company/{slug}/consolidated/"
    soup = BeautifulSoup(fetch_page(url), "html.parser")
    return _parse_document_links(soup)
