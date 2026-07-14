"""
S1 — URL discovery (deterministic: ddgs + rerank + pre-flight, zero LLM).
Spec: nodes/s1_discover. Emits the url_plan s2 executes.
"""

import time
from urllib.parse import urlparse

import requests

from src.config import (
    TIER1_DOMAINS, BLOCKED_DOMAINS, MAX_READ_CALLS, MAX_URLS_MACRO,
    MAX_URLS_SECTOR, PREFLIGHT_TIMEOUT, MAX_RESULTS_DATA,
)
from src.pipeline.query_banks import (
    COMPANY_DOC_QUERIES, CONCALL_QUERY_TEMPLATES, COMPANY_NEWS_QUERIES,
    MACRO_THEMES, COMMODITY_QUERY_TEMPLATES,
)

_HEADERS = {"User-Agent": "Mozilla/5.0 (research-preflight)"}


def _domain(url: str) -> str:
    try:
        return urlparse(url).netloc.lower().removeprefix("www.")
    except Exception:
        return ""


def _tier(url: str) -> int:
    d = _domain(url)
    if any(d.endswith(b) for b in BLOCKED_DOMAINS):
        return 99
    if any(d.endswith(t) for t in TIER1_DOMAINS):
        return 0
    return 1


def _search(queries: list, seen: set) -> list[dict]:
    """queries: [(query, doc_class, n_results)] -> reranked url dicts."""
    from ddgs import DDGS
    buckets = []
    with DDGS() as ddgs:
        for query, doc_class, n in queries:
            try:
                results = list(ddgs.text(query, region="in-en", max_results=n))
            except Exception as e:
                print(f"  [s1][warn] search failed '{query}': {e}")
                continue
            bucket = []
            for r in results:
                url = r.get("href") or r.get("url")
                if not url or url in seen or _tier(url) == 99:
                    continue
                seen.add(url)
                bucket.append({"url": url, "title": r.get("title", "untitled"),
                               "doc_class": doc_class, "query": query,
                               "tier": _tier(url)})
            bucket.sort(key=lambda x: x["tier"])
            buckets.append(bucket)
            time.sleep(1)
    # round-robin across queries, tier-sorted within each
    picked = []
    rank = 0
    while True:
        added = False
        for b in buckets:
            if rank < len(b):
                picked.append(b[rank])
                added = True
        if not added:
            return picked
        rank += 1


def _preflight(urls: list[dict]) -> list[dict]:
    ok = []
    for u in urls:
        try:
            r = requests.head(u["url"], timeout=PREFLIGHT_TIMEOUT,
                              headers=_HEADERS, allow_redirects=True)
            if r.status_code in (404, 410):
                print(f"  [s1] preflight drop ({r.status_code}): {u['url']}")
                continue
            size = int(r.headers.get("content-length") or 0)
            if size > 35_000_000:
                print(f"  [s1] preflight drop (too large): {u['url']}")
                continue
        except requests.RequestException:
            pass  # advisory only — Gemini's fetcher differs
        ok.append(u)
    return ok


def discover_node(state) -> dict:
    if state.get("dry_run"):
        print("[s1_discover] DRY RUN — no searches")
        return {"url_plan": []}

    profile, pack, plan = state["profile"], state["pack"], state["read_plan"]
    slots = {"company": profile["name"], "ticker": profile["ticker"],
             "fy": plan["quarters"][0]["fy"]}
    seen: set = set()
    reads: list[dict] = []

    # --- company: deterministic screener URLs first (no search needed)
    reads.append({"target": "screener", "doc_class": "screener_page", "priority": 1,
                  "urls": [f"https://www.screener.in/company/{profile['screener_slug']}/consolidated/"],
                  "batch": False})
    peer_urls = [f"https://www.screener.in/company/{s}/consolidated/"
                 for s in profile.get("peer_screener_slugs", [])[:4]]
    if peer_urls:
        reads.append({"target": "peer_screeners", "doc_class": "screener_page",
                      "priority": 2, "urls": peer_urls, "batch": True})

    # --- concalls: one search per quarter (latest 2 = P1, older = P2)
    for i, qq in enumerate(plan["quarters"]):
        qslots = dict(slots, q=qq["q"], fy=qq["fy"])
        queries = [(t.format(**qslots), "concall", 5) for t in CONCALL_QUERY_TEMPLATES[:1]]
        found = _search(queries, seen)
        if found:
            reads.append({"target": f"concall_{qq['q']}{qq['fy']}", "doc_class": "concall",
                          "priority": 1 if i < 2 else 2, "urls": [found[0]["url"]],
                          "batch": False, "title": found[0]["title"]})
        else:
            print(f"  [s1] no transcript found for {qq['q']}{qq['fy']}")

    # --- company docs
    for tmpl, doc_class, prio, n in COMPANY_DOC_QUERIES:
        found = _search([(tmpl.format(**slots), doc_class, n)], seen)
        if found:
            take = 1 if doc_class != "shareholding" else 1
            reads.append({"target": doc_class, "doc_class": doc_class,
                          "priority": prio, "urls": [f["url"] for f in found[:take]],
                          "batch": False, "title": found[0]["title"]})

    # --- company news (batched 3/call)
    news_urls = _search([(t.format(**slots), dc, n) for t, dc, p, n in COMPANY_NEWS_QUERIES[:3]], seen)
    for i in range(0, min(len(news_urls), 6), 3):
        reads.append({"target": f"news_{i//3}", "doc_class": "news_batch", "priority": 2,
                      "urls": [u["url"] for u in news_urls[i:i+3]], "batch": True})
    vp = _search([(COMPANY_NEWS_QUERIES[3][0].format(**slots), "valuepickr", MAX_RESULTS_DATA)], seen)
    if vp:
        reads.append({"target": "valuepickr", "doc_class": "valuepickr", "priority": 3,
                      "urls": [vp[0]["url"]], "batch": False})

    # --- macro themes (skipped if fresh); commodities from pack subset
    if not plan.get("macro_fresh"):
        themes = dict(MACRO_THEMES)
        commodity_qs = []
        for c in pack.get("macro_commodity_subset", []):
            for t in COMMODITY_QUERY_TEMPLATES:
                commodity_qs.append((t.format(commodity=c), "macro_page"))
        themes["commodities"] = commodity_qs
        macro_reads = 0
        for theme, qs in themes.items():
            if macro_reads >= MAX_URLS_MACRO:
                break
            found = _search([(q, dc, 2) for q, dc in qs], seen)
            urls = [f["url"] for f in found[:3]]
            if urls:
                reads.append({"target": f"macro_{theme}", "doc_class": "macro_page",
                              "priority": 2, "urls": urls, "batch": True})
                macro_reads += 1

    # --- sector pages (skipped if fresh)
    if not plan.get("sector_fresh"):
        sq = [(q["q"].format(**slots, segment=profile.get("segments", [""])[0]),
               "sector_page", q.get("results", 3))
              for q in pack.get("sector_queries", [])]
        found = _search(sq, seen)
        urls = [f["url"] for f in found]
        for i in range(0, min(len(urls), MAX_URLS_SECTOR * 2), 2):
            reads.append({"target": f"sector_{i//2}", "doc_class": "sector_page",
                          "priority": 2, "urls": urls[i:i+2], "batch": True})

    # --- pre-flight + budget trim (P3 first, then P2 from the tail)
    for r in reads:
        r["urls"] = [u["url"] if isinstance(u, dict) else u for u in _preflight(
            [{"url": u} for u in r["urls"]])]
    reads = [r for r in reads if r["urls"]]

    def total(rs):
        return len(rs)
    while total(reads) > MAX_READ_CALLS:
        cut = next((r for r in reversed(reads) if r["priority"] == 3), None) or \
              next((r for r in reversed(reads) if r["priority"] == 2), None)
        if cut is None:
            break
        print(f"  [s1] over budget — dropping {cut['target']} (P{cut['priority']})")
        reads.remove(cut)

    print(f"[s1_discover] url plan: {len(reads)} read calls "
          f"({sum(len(r['urls']) for r in reads)} URLs, {len(seen)} discovered)")
    return {"url_plan": reads}
