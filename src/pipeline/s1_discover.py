"""
S1 — URL discovery (deterministic: ddgs + rerank + pre-flight, zero LLM).
Spec: nodes/s1_discover. Emits the url_plan s2 executes.
"""

import json
import os
import time
from urllib.parse import urlparse

import requests

from src.config import (
    TIER1_DOMAINS, BLOCKED_DOMAINS, BLOCKED_URL_PATTERNS, LEGAL_DOMAINS,
    DOMAIN_SCORES_PATH, MAX_READ_CALLS, MAX_NEWS_URLS, MAX_URLS_MACRO,
    MAX_URLS_SECTOR, PREFLIGHT_TIMEOUT, MAX_RESULTS_DATA,
)
from src.pipeline.query_banks import (
    COMPANY_DOC_QUERIES, CONCALL_QUERY_TEMPLATES, COMPANY_NEWS_QUERIES,
    MACRO_THEMES, COMMODITY_QUERY_TEMPLATES,
)

_HEADERS = {"User-Agent": "Mozilla/5.0 (research-preflight)"}

# outcomes that mean "this domain wasted an LLM call" (mistarget = a
# doc-hunt hit that wasn't the document type it claimed — Phase 3.6)
_BAD_OUTCOMES = {"unreadable", "parse_failed", "deadline", "mistarget"}
_DEMOTE_AFTER = 2


def load_domain_scores() -> dict:
    """{domain: {"ok": n, "bad": n}} accumulated across runs (playbook §0:
    domains that repeatedly fail url_context get demoted automatically)."""
    try:
        with open(DOMAIN_SCORES_PATH, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def update_domain_scores(read_log: list[dict]) -> None:
    scores = load_domain_scores()
    for entry in read_log or []:
        url = entry.get("url")
        if not url or url.startswith("internal://"):
            continue
        d = _domain(url)
        if not d:
            continue
        rec = scores.setdefault(d, {"ok": 0, "bad": 0})
        if entry.get("outcome") in _BAD_OUTCOMES:
            rec["bad"] += 1
        elif entry.get("outcome") in ("read", "parsed", "reused"):
            rec["ok"] += 1
    try:
        os.makedirs(os.path.dirname(DOMAIN_SCORES_PATH) or ".", exist_ok=True)
        with open(DOMAIN_SCORES_PATH, "w", encoding="utf-8") as f:
            json.dump(scores, f, indent=2, sort_keys=True)
    except OSError as e:
        print(f"  [s1][warn] could not persist domain scores: {e}")


def _demoted(scores: dict) -> set:
    return {d for d, r in scores.items()
            if r.get("bad", 0) >= _DEMOTE_AFTER and r.get("bad", 0) > r.get("ok", 0)}


def _domain(url: str) -> str:
    try:
        return urlparse(url).netloc.lower().removeprefix("www.")
    except Exception:
        return ""


def _tier(url: str, allow_legal: bool = False, demoted: set = frozenset()) -> int:
    """0 = tier-1 authority, 1 = ordinary, 2 = learned-unreliable, 99 = blocked."""
    d = _domain(url)
    low = (url or "").lower()
    if any(p in low for p in BLOCKED_URL_PATTERNS):
        return 99
    if any(d.endswith(b) for b in BLOCKED_DOMAINS):
        return 99
    if any(d.endswith(x) for x in LEGAL_DOMAINS) and not allow_legal:
        return 99      # legal DBs pollute news; only the litigation query wants them
    if d in demoted:
        return 2
    if any(d.endswith(t) for t in TIER1_DOMAINS):
        return 0
    return 1


def _search(queries: list, seen: set, timelimit: str | None = None,
            allow_legal: bool = False) -> list[dict]:
    """queries: [(query, doc_class, n_results)] -> reranked url dicts.
    timelimit: ddgs recency filter ('m' = past month for news, 'y' = past
    year for document hunts) — ddgs has no date field worth trusting."""
    from ddgs import DDGS
    scores = load_domain_scores()
    demoted = _demoted(scores)
    buckets = []
    with DDGS() as ddgs:
        for query, doc_class, n in queries:
            try:
                kw = {"region": "in-en", "max_results": n}
                if timelimit:
                    kw["timelimit"] = timelimit
                results = list(ddgs.text(query, **kw))
            except Exception as e:
                print(f"  [s1][warn] search failed '{query}': {e}")
                continue
            bucket = []
            for r in results:
                url = r.get("href") or r.get("url")
                if not url or url in seen:
                    continue
                t = _tier(url, allow_legal=allow_legal, demoted=demoted)
                if t == 99:
                    continue
                seen.add(url)
                bucket.append({"url": url, "title": r.get("title", "untitled"),
                               "doc_class": doc_class, "query": query, "tier": t})
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
             # short alias for queries where the full legal name drowns the
             # intent ("... Limited (Sona Comstar) historical pe" returned
             # only generic quote pages)
             "company_short": (profile.get("aliases") or [profile["name"]])[0],
             "fy": plan["quarters"][0]["fy"]}
    seen: set = set()
    reads: list[dict] = []

    # --- Round 3.2: sector-scoped numeric backbone first. When the
    # sector backbone (screener parse + price series for ALL members) is
    # fresh, this run rehydrates it in s2 and emits NO screener reads;
    # stale → refreshed INLINE here (zero LLM either way). Any failure
    # falls back to the classic per-run screener reads below.
    from src.packs import sector_members
    backbone = None
    members = sector_members(pack)
    if state.get("persist") and plan.get("sector_entity_id") and members:
        try:
            from src.ingestion.sector_backbone import ensure_backbone
            backbone = ensure_backbone(plan["sector_entity_id"], pack,
                                       run_id=state.get("run_id") or None,
                                       force=bool(state.get("refresh_sector")))
        except Exception as e:
            print(f"  [s1][warn] sector backbone unavailable ({e}) — "
                  f"falling back to per-run screener reads")
            backbone = None
    own_slug = profile["screener_slug"]
    if backbone and own_slug not in backbone.get("members", {}):
        # the run company itself failed refresh — a peers-only backbone
        # cannot serve this run; use the classic path wholesale
        print(f"  [s1][warn] backbone lacks {own_slug} — classic screener reads")
        backbone = None
    if not backbone:
        # --- classic path: deterministic screener URLs (no search needed)
        reads.append({"target": "screener", "doc_class": "screener_page", "priority": 1,
                      "urls": [f"https://www.screener.in/company/{profile['screener_slug']}/consolidated/"],
                      "batch": False})
        # Phase 5.3: full peer set — screener parses are free (zero LLM);
        # peers = sector registry members minus the run company
        peer_urls = [f"https://www.screener.in/company/{m['screener_slug']}/consolidated/"
                     for m in members if m["screener_slug"] != own_slug][:8]
        if peer_urls:
            reads.append({"target": "peer_screeners", "doc_class": "screener_page",
                          "priority": 2, "urls": peer_urls, "batch": True})

    # --- concalls + AR: screener's Documents links are authoritative (BSE
    # PDFs) and replace ddgs hunting entirely when available (Phase 1)
    from src.config import CONCALL_QUARTERS
    ar_covered = ip_covered = False
    transcripts = []
    try:
        from src.ingestion.screener_parser import get_document_links
        links = get_document_links(profile["screener_slug"])
        transcripts = links.get("concall_transcripts", [])[:CONCALL_QUARTERS]
        # Phase 5.6: latest concall PPT = the authoritative investor deck
        ppts = links.get("concall_ppts", [])
        if ppts:
            # trusted=screener-sourced: a failed local validation falls back
            # to url_context instead of being skipped as a mis-target
            reads.append({"target": "investor_presentation",
                          "doc_class": "investor_presentation", "priority": 1,
                          "urls": [ppts[0]["url"]], "batch": False, "trusted": True,
                          "title": f"Investor presentation ({ppts[0]['label']})"})
            seen.add(ppts[0]["url"])
            ip_covered = True
        ars = links.get("annual_reports", [])
        if ars:
            reads.append({"target": "annual_report", "doc_class": "annual_report",
                          "priority": 1, "urls": [ars[0]["url"]], "batch": False,
                          "title": f"Annual report ({ars[0]['label']})"})
            seen.add(ars[0]["url"])
            ar_covered = True
        # (Round 4.5: the FY-1 AR read is DROPPED — the latest AR's
        # prior-year comparatives + screener's 9y statements cover trends,
        # and the M&M FY-1 conglomerate AR was the chronic 64K overflow.)
    except Exception as e:
        print(f"  [s1] screener doc links unavailable ({e}) — using ddgs for "
              f"transcripts/AR")

    if transcripts:
        for i, t in enumerate(transcripts):
            reads.append({"target": f"concall_{t['label'] or i}", "doc_class": "concall",
                          "priority": 1 if i < 2 else 2, "urls": [t["url"]],
                          "batch": False,
                          "title": f"Concall transcript ({t['label']})"})
            seen.add(t["url"])
        print(f"  [s1] {len(transcripts)} concall transcripts via screener doc links")
    else:
        for i, qq in enumerate(plan["quarters"]):
            qslots = dict(slots, q=qq["q"], fy=qq["fy"])
            queries = [(t.format(**qslots), "concall", 5) for t in CONCALL_QUERY_TEMPLATES[:1]]
            found = _search(queries, seen, timelimit="y")
            if found:
                reads.append({"target": f"concall_{qq['q']}{qq['fy']}", "doc_class": "concall",
                              "priority": 1 if i < 2 else 2, "urls": [found[0]["url"]],
                              "batch": False, "title": found[0]["title"]})
            else:
                print(f"  [s1] no transcript found for {qq['q']}{qq['fy']}")

    # (Round 2.4: the valuation_history read — wisesheets PE-history
    # scraping + shape/identity validation — is RETIRED. The own-history
    # PE series is now computed in s3 from Yahoo FY-end closes ÷ annual
    # EPS, both already observed deterministically.)

    # --- company docs
    for tmpl, doc_class, prio, n in COMPANY_DOC_QUERIES:
        if doc_class == "annual_report" and ar_covered:
            continue
        if doc_class == "investor_presentation" and ip_covered:
            continue
        found = _search([(tmpl.format(**slots), doc_class, n)], seen, timelimit="y")
        if not found:
            continue
        # Phase 3.6: presentation hunts often surface aggregator list pages
        # — prefer direct PDFs / exchange-hosted files within tier order
        if doc_class == "investor_presentation":
            found.sort(key=lambda f: (
                0 if (f["url"].lower().split("?")[0].endswith(".pdf")
                      or "bseindia" in f["url"]) else 1,
                f["tier"]))
        # Phase 3.4: a second rating agency's rationale (distinct domain)
        # gives an independent forward view — one solo read per rationale
        if doc_class == "rating_rationale":
            picked, domains = [], set()
            for f in found:
                d = _domain(f["url"])
                if d in domains:
                    continue
                domains.add(d)
                picked.append(f)
                if len(picked) == 2:
                    break
            for i, f in enumerate(picked):
                reads.append({"target": doc_class if i == 0 else f"{doc_class}_2",
                              "doc_class": doc_class, "priority": prio,
                              "urls": [f["url"]], "batch": False,
                              "title": f["title"]})
            continue
        reads.append({"target": doc_class, "doc_class": doc_class,
                      "priority": prio, "urls": [found[0]["url"]],
                      "batch": False, "title": found[0]["title"]})

    # --- company news (batched 3/call). Past-month only: stale hits were
    # polluting the pool (a 2023 trademark judgment became a "moat").
    # Phase 3.4: budget raised 6 -> MAX_NEWS_URLS (10).
    news_urls = _search([(t.format(**slots), dc, 5)
                         for t, dc, p, n in COMPANY_NEWS_QUERIES[:2]],
                        seen, timelimit="m")
    for i in range(0, min(len(news_urls), MAX_NEWS_URLS), 3):
        reads.append({"target": f"news_{i//3}", "doc_class": "news_batch", "priority": 2,
                      "urls": [u["url"] for u in news_urls[i:i+3]], "batch": True})

    # --- litigation: the ONLY query allowed to surface legal databases
    lit_t, lit_dc, _, lit_n = COMPANY_NEWS_QUERIES[2]
    lit = _search([(lit_t.format(**slots), lit_dc, lit_n)], seen,
                  timelimit="y", allow_legal=True)
    if lit:
        reads.append({"target": "litigation", "doc_class": "news_batch",
                      "priority": 2, "urls": [u["url"] for u in lit[:2]],
                      "batch": True, "title": "Litigation / regulatory action"})

    # (Round 4.5: the valuepickr read is DROPPED — forum claims added
    # little cited value; H keeps rating/news breadth.)

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
          f"({sum(len(r['urls']) for r in reads)} URLs, {len(seen)} discovered)"
          + (" + sector backbone" if backbone else ""))
    out = {"url_plan": reads}
    if backbone:
        out["backbone"] = backbone
    return out
