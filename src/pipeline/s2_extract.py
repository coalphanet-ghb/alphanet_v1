"""
S2 — document extraction. Spec: nodes/s2_extract.

Phase 3 (Extraction 2.0): documents are fetched LOCALLY (requests + pypdf/
trafilatura) and their text goes INLINE into one extraction call on the
active synthesis model (M3's 1M context). Gemini url_context remains the
per-URL fallback when local fetch fails; a URL failing both is skipped and
logged. All concall transcripts are batched into ONE call, which also
emits cross-quarter fields (guidance_evolution, recurring_themes).

Executes the url_plan: verbatim passages -> evidence rows; numbers ->
metric candidates; cross-block tags -> pools. Reuses already-ingested
URLs (evidence + pools reloaded from DB) at zero LLM cost. Extraction is
not analysis: the model quotes, records, and tags — nothing else.
"""

import json

from src import db
from src.config import REUSE_MIN_PASSAGES
from src.ingestion.fetcher import (
    fetch_document, looks_like_presentation, FetchError,
)
from src.llm import (
    read_urls, synthesize, parse_json_lenient, LLMError, CallDeadlineError,
)

_DOC_TYPE_MAP = {   # doc_class -> source_documents.type
    "concall": "concall_transcript", "annual_report": "annual_report",
    "investor_presentation": "other", "results_pdf": "regulatory_filing",
    "rating_rationale": "brokerage_report", "screener_page": "other",
    "shareholding": "regulatory_filing", "news_batch": "news",
    "valuepickr": "other", "sector_page": "industry_report",
    "macro_page": "macro_data", "valuation_history": "other",
}

_FOCUS = {
    "concall": "ALL forward-looking guidance statements (with speaker); volume/demand commentary; margin walk explanations; capex/order-book updates; every analyst question management dodged or answered defensively (verbatim Q and A); explanations of one-offs.",
    "annual_report": "Accounting-policy notes (revenue recognition, depreciation, capitalization); raw-material/cost-of-materials breakdown BY MATERIAL with amounts (each line a metric_candidate); segment tables — revenue, results, capital employed per segment, EVERY cell a metric_candidate; geography/export revenue split (each region a metric_candidate); top-customer disclosures under Ind-AS 108 (customer concentration % -> metric_candidate); forex earnings and spend; related-party transactions (amounts, counterparties); contingent liabilities; CWIP; borrowings schedule; auditor report language incl. CARO; MD&A demand/strategy passages; SPECIFIC risk factors (skip boilerplate); remuneration; pledge.",
    "investor_presentation": "Segment/revenue mix as numbers (each slice a metric_candidate); order book value and new wins (metric_candidates); EV/BEV revenue share; capacity and utilization per plant (metric_candidates); capex plans with amounts and timelines; export/geography mix; market-share claims; strategy targets with dates.",
    "results_pdf": "Every financial-statement line item as printed with quarter and YoY comparatives; exceptional items and their notes; segment tables; auditor limited-review remarks.",
    "rating_rationale": "Rating, outlook, and any change; EVERY listed strength and weakness; leverage/coverage/liquidity numbers cited; customer/supplier concentration statements; the agency's forward expectations.",
    "screener_page": "The complete ratio and statement tables — EVERY row-year cell becomes a metric candidate (P&L, balance sheet, cash flow, ratios, shareholding, price/valuation numbers as displayed). Passages only for the 'about' text.",
    "shareholding": "Category-wise holding percentages, quarterly trend, promoter pledge percentage.",
    "news_batch": "Dated events and direct quotes only; note publication and date per item; skip opinion and anonymous speculation.",
    "valuepickr": "Distinct bull arguments and bear arguments (verbatim, attribute as 'forum claim'); factual claims worth verifying. NEVER as fact — always as claims.",
    "sector_page": "Industry data points (volumes, prices, growth rates) with their periods; association/agency outlook statements — capture BOTH the recent view and any medium-term view.",
    "macro_page": "Indicator values with dates; official/institutional forecasts with horizon; policy decisions with effective dates.",
    "valuation_history": "THIS COMPANY's historical valuation multiple series ONLY: every year-to-P/E pair as a metric_candidate named 'pe' with that single year as period_printed (same for 'pb' and EV/EBITDA where shown). SKIP peer/other-company rows entirely; skip averages, medians and multi-year ranges (only single-period values); skip commentary and price targets.",
}

_SCHEMA = """Return ONLY this JSON (no commentary):
{"sources": [{"url": "<url>", "readable": true/false,
  "passages": [{"text": "<VERBATIM quote, max ~120 words>", "page_or_timestamp": "<as printed or null>",
                "entities_mentioned": ["<names>"], "tags": ["risk_signal"|"guidance_item"|"supply_chain_edge"|"peer_mention"|"event" ...]}],
  "metric_candidates": [{"name": "<snake_case indicator>", "value_printed": "<exactly as printed>",
                "period_printed": "<as printed>", "basis": "consolidated"|"standalone"|null,
                "statement": "P&L"|"BS"|"CF"|"ratio"|"price"|"volume"|null, "ambiguous": true/false}],
  "guidance_items": [{"metric": "", "period": "", "value_or_direction": "", "quote": "", "speaker": null}],
  "supply_chain_edges": [{"from_entity": "", "relation": "supplies_to|customer_of|input_cost_for|single_source_from|exports_to", "to_entity": "", "quote": ""}],
  "peer_mentions": ["<company name>"],
  "events": [{"date": "", "what": "", "quote": ""}]}]}
Rules: quote VERBATIM, never paraphrase or summarize. No arithmetic, no
unit conversion — values exactly as printed. Ambiguous unit/period ->
"ambiguous": true, never guess. Cap ~15 passages per source (screener
pages: passages minimal, metric_candidates exhaustive). If a URL cannot
be read, {"url": ..., "readable": false} and move on.
Canonical indicator names — use one of these EXACT snake_case names ONLY
when the document states that PRECISE quantity (definition in brackets):
order_book [total order book VALUE in currency, never a % split of it],
ev_revenue_share [EV/BEV products' % of REVENUE],
export_share [exports as % of total revenue, stated as such — a single
  region's share (e.g. North America) is NOT export_share],
customer_concentration [the SINGLE largest customer's % of revenue —
  top-5/top-10 shares and revenue AMOUNTS from >10% customers are NOT this],
aftermarket_share [aftermarket/replacement channel % of revenue],
capacity_utilization [plant utilization %].
If the quantity differs from the bracketed definition in ANY way, use a
plain descriptive snake_case name instead (e.g. top_5_customer_share,
north_america_revenue_share, ev_share_of_order_book)."""

# Phase 3.3 — emitted ONLY when multiple concall transcripts share one call
_CROSS_QUARTER_SCHEMA = """
This call carries MULTIPLE concall transcripts (each opened by a
'=== SOURCE: <url> ===' line, with its quarter label). ALSO emit these
TOP-LEVEL keys (siblings of "sources"), built ACROSS the calls:
"guidance_evolution": [{"metric": "<what was guided>",
   "trail": [{"call": "<quarter label>", "guidance": "<verbatim>"}],
   "direction": "raised|maintained|lowered|dropped", "note": "<one line>"}],
"recurring_themes": [{"theme": "", "calls": ["<quarter labels>"],
   "pattern": "consistent|evolving|dodged_repeatedly",
   "quote": "<one representative verbatim quote>"}]
"dropped" = guidance silently stopped being mentioned in later calls.
Same rules: verbatim quotes, no arithmetic, no inference beyond the text."""

# Output budgets: provider cap (64K on Fireworks). Extraction output is
# genuinely long — a 213-page AR under the every-cell focus produced >32K
# tokens of VISIBLE output (not reasoning) and truncated mid-JSON on a
# reingest. Reasoning tokens also live inside this budget (HANDOFF2 §6.12).
_EXTRACT_MAX_TOKENS = 64000
_BATCH_EXTRACT_MAX_TOKENS = 64000


def _instruction(doc_class: str, inline: bool = False, n_sources: int = 1,
                 cross_quarter: bool = False) -> str:
    head = "You are an ingestion instrument for an equity research platform. "
    if inline:
        head += (f"Below are {n_sources} fetched document(s), each opened by a "
                 "line '=== SOURCE: <url> ==='. Emit one entry in \"sources\" "
                 "per URL, in the order given, echoing each url exactly. ")
    head += (f"Extract with this focus: {_FOCUS[doc_class]}\n\n" + _SCHEMA)
    if cross_quarter:
        head += "\n" + _CROSS_QUARTER_SCHEMA
    return head


def _url_title(read: dict, url: str) -> str:
    return (read.get("titles_by_url", {}).get(url)
            or read.get("title") or read["target"])


def _persist_source(read: dict, url: str, raw: dict,
                    layer: str, ticker: str) -> tuple:
    doc_id, created = db.save_source_document(
        doc_type=_DOC_TYPE_MAP[read["doc_class"]],
        title=_url_title(read, url),
        url_or_path=url,
        text_for_hash=json.dumps(raw, sort_keys=True)[:100000],
        metadata={"doc_class": read["doc_class"], "layer": layer,
                  "ticker": ticker, "discovered_for": read["target"]},
    )
    return doc_id, created


def _pool_entry_section(doc_id: str) -> str:
    return f"extract:{doc_id}"


def _layer_of(doc_class: str) -> str:
    if doc_class == "macro_page":
        return "macro"
    if doc_class == "sector_page":
        return "industry"
    return "company"


def _batch_concall_reads(url_plan: list) -> list:
    """Phase 3.3: merge every concall read into ONE read so all transcripts
    share a single extraction call (enables cross-quarter fields). Keeps
    per-URL titles so evidence provenance stays quarter-specific."""
    concalls = [r for r in url_plan if r["doc_class"] == "concall"]
    if len(concalls) <= 1:
        return url_plan
    merged = {
        "target": "concalls_batch", "doc_class": "concall", "priority": 1,
        "batch": True,
        "urls": [u for r in concalls for u in r["urls"]],
        "titles_by_url": {u: r.get("title") or r["target"]
                          for r in concalls for u in r["urls"]},
        "title": "Concall transcripts (batched)",
    }
    out, inserted = [], False
    for r in url_plan:
        if r["doc_class"] == "concall":
            if not inserted:
                out.append(merged)
                inserted = True
            continue
        out.append(r)
    return out


def _screener_via_parser(read, pools, state, entities) -> bool:
    """Phase 1: screener pages are parsed deterministically (zero LLM),
    fresh every run. Returns False to fall back to the reuse/LLM path."""
    import json as _json
    from src.ingestion.screener_parser import parse_company_page

    persist = state["persist"]
    for url in list(read["urls"]):
        try:
            parsed = parse_company_page(url)
        except Exception as e:
            print(f"  [s2][warn] screener parser failed for {url}: {e} — "
                  f"falling back to reuse/LLM path")
            return False
        candidates = parsed["candidates"]
        # hash only the periodic tables (not the daily-moving top card) so
        # the source_documents row stays stable between result seasons
        stable = [c for c in candidates if not c.get("period_parsed")]
        doc_id, created = None, False
        if persist:
            doc_id, created = db.save_source_document(
                doc_type="other", title=read.get("title") or f"screener:{url}",
                url_or_path=url,
                text_for_hash=_json.dumps(stable, sort_keys=True),
                metadata={"doc_class": "screener_page", "layer": "company",
                          "parser": "screener_parser",
                          "ticker": state["profile"]["ticker"]})
        # ALWAYS pooled (save_evidence is idempotent since Phase 5): on
        # reuse runs the peers' 'about' passages were skipped, leaving G's
        # peer evidence packs empty
        if parsed["about"]:
            ev_id = db.save_evidence(doc_id, parsed["about"]) if persist else \
                f"mem_{len(pools['evidence_pool'])}"
            pools["evidence_pool"].append({
                "id": ev_id, "text": parsed["about"], "url": url,
                "doc_class": "screener_page", "title": read.get("title") or "screener",
                "tags": [], "page": None})
        basis = "consolidated" if "/consolidated/" in url else "standalone"
        for c in candidates:
            c["doc_class"] = "screener_page"
            c["url"] = url
            c["source_document_id"] = doc_id
            c["basis"] = basis
        pools["metric_candidates"] += candidates
        links = parsed["doc_links"]
        pools.setdefault("screener_doc_links", {})[url] = links
        pools["read_log"].append({"url": url, "outcome": "parsed",
                                  "metrics": len(candidates),
                                  "transcripts": len(links["concall_transcripts"])})
        print(f"  [s2] screener parsed (no LLM): {len(candidates)} metric "
              f"candidates, {len(links['concall_transcripts'])} transcript links "
              f"— {url}")
    return True


def _extract_call(get_text, label: str) -> dict | None:
    """One extraction call + lenient parse, with the documented
    reprompt-once exception on malformed JSON (Phase 2.7). get_text is
    called with the extra reprompt suffix ('' first time). Returns the
    parsed dict or None (skip)."""
    def _attempt(extra):
        """One extraction attempt. Truncation is retry-worthy (shares the
        single reprompt budget); deadline skips; other LLM errors abort."""
        try:
            return parse_json_lenient(get_text(extra)), False
        except CallDeadlineError:
            print(f"  [s2][warn] deadline expired — skipping {label}")
            return None, True
        except LLMError as e:
            if "TRUNCATED" in str(e):
                print(f"  [s2][warn] extraction output truncated for {label}")
                return None, False
            raise

    parsed, fatal = _attempt("")
    if fatal:
        return None
    if parsed and "sources" in parsed:
        return parsed
    print(f"  [s2][warn] unusable extraction for {label} — reprompting once")
    parsed, fatal = _attempt(
        "\n\nYour previous response was NOT usable (invalid or truncated "
        "JSON). Return ONLY the JSON object described above — no prose, no "
        "markdown fences; be terse in passage selection if space is tight.")
    if not fatal and parsed and "sources" in parsed:
        return parsed
    print(f"  [s2][warn] still unusable — skipping {label}")
    return None


def _ingest_sources(parsed: dict, read: dict, ordered_urls: list, pools: dict,
                    state, entities: list, layer: str) -> None:
    """Persist one parsed extraction envelope: evidence rows, metric
    candidates, tag pools, per-document knowledge entry."""
    persist = state["persist"]
    profile = state["profile"]
    company_id = profile.get("entity_id")

    for idx, src in enumerate(parsed["sources"]):
        url = src.get("url") or (ordered_urls[idx] if idx < len(ordered_urls)
                                 else read["urls"][0])
        if not src.get("readable", True):
            print(f"  [s2][warn] unreadable: {url}")
            pools["read_log"].append({"url": url, "outcome": "unreadable"})
            continue

        passages = src.get("passages") or []
        candidates = src.get("metric_candidates") or []
        doc_id = None
        risk_ev_ids = []
        if persist:
            doc_id, _ = _persist_source(read, url, src, layer,
                                        profile["ticker"])
        for p in passages:
            ptext = (p.get("text") or "").strip()
            if len(ptext) < 30:
                continue
            ev_id = None
            if persist:
                ev_id = db.save_evidence(doc_id, ptext, p.get("page_or_timestamp"))
                named = [e["id"] for e in entities
                         if e["name"].lower() in ptext.lower()]
                db.link_evidence_entities(ev_id, named)
            entry = {"id": ev_id or f"mem_{len(pools['evidence_pool'])}",
                     "text": ptext, "url": url, "doc_class": read["doc_class"],
                     "title": _url_title(read, url),
                     "tags": p.get("tags") or [], "page": p.get("page_or_timestamp")}
            pools["evidence_pool"].append(entry)
            if "risk_signal" in entry["tags"]:
                pools["risk_signals"].append({"evidence_id": entry["id"],
                                              "text": ptext[:300], "url": url})
                risk_ev_ids.append(entry["id"])

        for c in candidates:
            c["source_document_id"] = doc_id
            c["doc_class"] = read["doc_class"]
            c["url"] = url
        pools["metric_candidates"] += candidates
        pools["guidance_items"] += src.get("guidance_items") or []
        pools["supply_edges"] += src.get("supply_chain_edges") or []
        pools["peer_mentions"] += src.get("peer_mentions") or []
        pools["events"] += src.get("events") or []
        pools["read_log"].append({"url": url, "outcome": "read",
                                  "passages": len(passages),
                                  "metrics": len(candidates)})

        if persist and doc_id:
            db.save_knowledge_entry(
                layer if layer != "company" else "company",
                company_id, _pool_entry_section(doc_id),
                {"metric_candidates": candidates,
                 "guidance_items": src.get("guidance_items") or [],
                 "supply_chain_edges": src.get("supply_chain_edges") or [],
                 "peer_mentions": src.get("peer_mentions") or [],
                 "events": src.get("events") or [],
                 "risk_evidence_ids": risk_ev_ids},
                generated_by_run_id=state.get("run_id") or None)


def _price_history_via_yahoo(state, pools) -> None:
    """Deterministic monthly price series (zero LLM, fresh every run) —
    feeds s3's 1y PE-path computation. Never fails the run: absence
    becomes an insufficiency downstream."""
    profile = state["profile"]
    try:
        from src.ingestion.fetcher import fetch_price_history
        tokens = [t.lower() for t in ([profile["name"].split()[0]] +
                                      list(profile.get("aliases") or []))
                  if len(t) >= 4]
        points, url, long_name = fetch_price_history(profile["ticker"], tokens)
    except Exception as e:
        print(f"  [s2][warn] price history unavailable ({e}) — "
              f"1y PE path will be an insufficiency")
        return
    doc_id = None
    if state["persist"]:
        doc_id, _ = db.save_source_document(
            doc_type="other", title=f"Price history 1y ({long_name})",
            url_or_path=url, text_for_hash=json.dumps(points),
            metadata={"doc_class": "price_history", "layer": "company",
                      "ticker": profile["ticker"]})
    for label, close in points:
        pools["metric_candidates"].append({
            "name": "price", "value_printed": str(close),
            "period_printed": label, "basis": None, "statement": "price",
            "ambiguous": False, "doc_class": "price_history", "url": url,
            "source_document_id": doc_id})
    pools["read_log"].append({"url": url, "outcome": "parsed",
                              "metrics": len(points)})
    print(f"  [s2] price history (no LLM): {len(points)} monthly closes "
          f"({long_name})")


def extract_node(state) -> dict:
    if state.get("dry_run"):
        from src.pipeline.dry_run import synthetic_extraction
        print("[s2_extract] DRY RUN — synthetic extraction")
        return synthetic_extraction(state)

    persist = state["persist"]
    profile = state["profile"]
    entities = db.list_entities() if persist else []
    company_id = profile.get("entity_id")

    pools = {"evidence_pool": [], "metric_candidates": [], "guidance_items": [],
             "risk_signals": [], "supply_edges": [], "peer_mentions": [],
             "events": [], "read_log": [],
             "guidance_evolution": [], "recurring_themes": []}
    seen_doc_ids: set = set()   # a doc reachable via >1 URL loads once (Phase 0.4)

    _price_history_via_yahoo(state, pools)

    url_plan = _batch_concall_reads(state["url_plan"])

    for read in url_plan:
        layer = _layer_of(read["doc_class"])

        # --- Phase 1: screener pages parse deterministically, fresh each run
        if read["doc_class"] == "screener_page":
            if _screener_via_parser(read, pools, state, entities):
                continue

        # --- reuse shortcut: URL already ingested -> reload evidence + pools
        if persist and not state.get("reingest"):
            for url in list(read["urls"]):
                doc_id = db.get_source_document_by_url(url)
                if not doc_id:
                    continue
                if doc_id in seen_doc_ids:
                    read["urls"].remove(url)
                    continue
                rows = db.get_evidence_for_document(doc_id)
                # Phase 2.4 quality gate: a thin stored extraction (from an
                # earlier, weaker model/prompt) must not be frozen forever —
                # re-read instead of reusing it.
                floor = REUSE_MIN_PASSAGES.get(read["doc_class"])
                if floor and len(rows) < floor:
                    print(f"  [s2] stored extraction thin ({len(rows)} < {floor} "
                          f"passages) — re-reading {read['doc_class']}: {url}")
                    continue
                seen_doc_ids.add(doc_id)
                pool_entry = db.get_latest("company" if layer == "company" else layer,
                                           company_id or profile.get("entity_id"),
                                           _pool_entry_section(doc_id))
                if rows:
                    print(f"  [s2] reuse ({len(rows)} evidence, no LLM call): {url}")
                    for r in rows:
                        pools["evidence_pool"].append({
                            "id": r["id"], "text": r["text"], "url": url,
                            "doc_class": read["doc_class"],
                            "title": _url_title(read, url),
                            "tags": [], "page": r.get("page_or_timestamp")})
                    if pool_entry:
                        c = pool_entry["content_json"]
                        pools["metric_candidates"] += c.get("metric_candidates", [])
                        pools["guidance_items"] += c.get("guidance_items", [])
                        pools["supply_edges"] += c.get("supply_chain_edges", [])
                        pools["peer_mentions"] += c.get("peer_mentions", [])
                        pools["events"] += c.get("events", [])
                        for ev_id in c.get("risk_evidence_ids", []):
                            pools["risk_signals"].append({"evidence_id": ev_id, "url": url})
                    read["urls"].remove(url)
                    pools["read_log"].append({"url": url, "outcome": "reused"})
            if not read["urls"]:
                continue

        # --- Phase 3.1/3.2 fresh read: local fetch -> inline extraction on
        # the active synthesis model; per-URL fallback to Gemini url_context
        inline_urls, inline_docs, fallback_urls = [], {}, []
        for url in read["urls"]:
            try:
                doc = fetch_document(url)
            except FetchError as e:
                print(f"  [s2] local fetch failed ({e}) — "
                      f"url_context fallback: {url}")
                fallback_urls.append(url)
                continue
            # Phase 3.6: don't spend extraction on a mis-targeted "deck"
            # (news-list pages posing as investor presentations). A TRUSTED
            # URL (screener-sourced) failing validation means the server
            # served us junk this attempt — fall back to url_context
            # instead of skipping (a real BSE deck was once rejected on a
            # transient interstitial).
            if read["doc_class"] == "investor_presentation" and \
                    not looks_like_presentation(doc):
                if read.get("trusted"):
                    print(f"  [s2] trusted deck failed local validation — "
                          f"url_context fallback: {url}")
                    fallback_urls.append(url)
                else:
                    print(f"  [s2][warn] not a presentation (mis-target) — "
                          f"skipping: {url}")
                    pools["read_log"].append({"url": url, "outcome": "mistarget"})
                continue
            inline_urls.append(url)
            inline_docs[url] = doc

        if inline_urls:
            cross_quarter = read["doc_class"] == "concall" and len(inline_urls) > 1
            n_pages = sum(d.get("pages") or 0 for d in inline_docs.values())
            print(f"[s2_extract] read {read['target']} "
                  f"({len(inline_urls)} url, local fetch, "
                  f"{sum(d['char_count'] for d in inline_docs.values())} chars"
                  + (f", {n_pages} pdf pages" if n_pages else "") + ") ...")
            system = _instruction(read["doc_class"], inline=True,
                                  n_sources=len(inline_urls),
                                  cross_quarter=cross_quarter)
            doc_blocks = []
            for url in inline_urls:
                label = _url_title(read, url)
                doc_blocks.append(f"=== SOURCE: {url} ===\n({label})\n"
                                  f"{inline_docs[url]['text']}")
            user = "\n\n".join(doc_blocks)
            max_out = _BATCH_EXTRACT_MAX_TOKENS if cross_quarter \
                else _EXTRACT_MAX_TOKENS

            def _inline_call(extra, _system=system, _user=user, _mo=max_out):
                return synthesize(
                    [{"role": "system", "content": _system + extra},
                     {"role": "user", "content": _user}],
                    temperature=0.1, max_tokens=_mo)

            parsed = _extract_call(_inline_call, read["target"])
            if parsed:
                _ingest_sources(parsed, read, inline_urls, pools, state,
                                entities, layer)
                if cross_quarter:
                    pools["guidance_evolution"] += parsed.get("guidance_evolution") or []
                    pools["recurring_themes"] += parsed.get("recurring_themes") or []
                    print(f"  [s2] cross-quarter: "
                          f"{len(parsed.get('guidance_evolution') or [])} guidance "
                          f"trails, {len(parsed.get('recurring_themes') or [])} "
                          f"recurring themes")
            else:
                for url in inline_urls:
                    pools["read_log"].append({"url": url, "outcome": "parse_failed"})

        if fallback_urls:
            print(f"[s2_extract] read {read['target']} "
                  f"({len(fallback_urls)} url via url_context) ...")

            def _urlctx_call(extra, _read=read, _urls=fallback_urls):
                return read_urls(_urls, _instruction(_read["doc_class"]) + extra)

            parsed = _extract_call(_urlctx_call, read["target"])
            if parsed:
                _ingest_sources(parsed, read, fallback_urls, pools, state,
                                entities, layer)
            else:
                for url in fallback_urls:
                    pools["read_log"].append({"url": url, "outcome": "parse_failed"})

    if persist:
        plan = state["read_plan"]

        # --- Phase 3.3: persist cross-quarter concall synthesis; if every
        # transcript was reused (no fresh batch call), rehydrate the stored
        # one — freshness must never mean "run without the data" (§6.5).
        if pools["guidance_evolution"] or pools["recurring_themes"]:
            db.save_knowledge_entry(
                "company", company_id, "concall_cross_quarter",
                {"guidance_evolution": pools["guidance_evolution"],
                 "recurring_themes": pools["recurring_themes"]},
                generated_by_run_id=state.get("run_id") or None)
        else:
            try:
                stored = db.get_latest("company", company_id,
                                       "concall_cross_quarter")
                if stored:
                    c = stored["content_json"]
                    pools["guidance_evolution"] = c.get("guidance_evolution", [])
                    pools["recurring_themes"] = c.get("recurring_themes", [])
                    if pools["guidance_evolution"] or pools["recurring_themes"]:
                        print(f"  [s2] rehydrated cross-quarter concall entry "
                              f"({len(pools['guidance_evolution'])} trails)")
            except Exception as e:
                print(f"  [s2][warn] cross-quarter rehydrate failed: {e}")

        # --- Phase 0.3: rehydrate SKIPPED-because-fresh layers from storage.
        # s1 emitted no URLs for a fresh layer, so without this the macro /
        # sector evidence never reaches the pool and section C starves.
        have = {e["id"] for e in pools["evidence_pool"]}
        for fresh_key, layer in (("macro_fresh", "macro"), ("sector_fresh", "industry")):
            if not plan.get(fresh_key):
                continue
            try:
                stored = db.get_layer_evidence(layer)
            except Exception as e:
                print(f"  [s2][warn] could not rehydrate {layer} layer: {e}")
                continue
            rehydrated = [e for e in stored if e["id"] not in have]
            for e in rehydrated:
                e["tags"] = []
                pools["evidence_pool"].append(e)
                have.add(e["id"])
            if rehydrated:
                print(f"  [s2] rehydrated {len(rehydrated)} {layer} evidence rows "
                      f"from storage (layer fresh, reads skipped)")

        # freshness stamps for shared layers
        if not plan.get("macro_fresh") and plan.get("india_entity_id"):
            db.save_knowledge_entry("macro", plan["india_entity_id"], "layer_evidence",
                                    {"stamp": "refreshed"}, generated_by_run_id=state.get("run_id") or None)
        if not plan.get("sector_fresh") and plan.get("sector_entity_id"):
            db.save_knowledge_entry("industry", plan["sector_entity_id"], "layer_evidence",
                                    {"stamp": "refreshed"}, generated_by_run_id=state.get("run_id") or None)

    # Phase 2.2: feed this run's outcomes back into the learned domain table
    try:
        from src.pipeline.s1_discover import update_domain_scores
        update_domain_scores(pools["read_log"])
    except Exception as e:
        print(f"  [s2][warn] domain score update skipped: {e}")

    print(f"[s2_extract] done: {len(pools['evidence_pool'])} passages, "
          f"{len(pools['metric_candidates'])} metric candidates, "
          f"{len(pools['guidance_items'])} guidance items, "
          f"{len(pools['risk_signals'])} risk signals, "
          f"{len(pools['guidance_evolution'])} guidance trails")
    return pools
