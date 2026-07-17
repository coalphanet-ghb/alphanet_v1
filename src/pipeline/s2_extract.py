"""
S2 — document extraction (LLM + url_context). Spec: nodes/s2_extract.

Executes the url_plan: verbatim passages -> evidence rows; numbers ->
metric candidates; cross-block tags -> pools. Reuses already-ingested
URLs (evidence + pools reloaded from DB) at zero LLM cost. Extraction is
not analysis: the model quotes, records, and tags — nothing else.
"""

import json

from src import db
from src.config import REUSE_MIN_PASSAGES
from src.llm import read_urls, parse_json_lenient, LLMError, CallDeadlineError
from src.pipeline.query_banks import MACRO_METRIC_ENTITY_MAP

_DOC_TYPE_MAP = {   # doc_class -> source_documents.type
    "concall": "concall_transcript", "annual_report": "annual_report",
    "investor_presentation": "other", "results_pdf": "regulatory_filing",
    "rating_rationale": "brokerage_report", "screener_page": "other",
    "shareholding": "regulatory_filing", "news_batch": "news",
    "valuepickr": "other", "sector_page": "industry_report",
    "macro_page": "macro_data",
}

_FOCUS = {
    "concall": "ALL forward-looking guidance statements (with speaker); volume/demand commentary; margin walk explanations; capex/order-book updates; every analyst question management dodged or answered defensively (verbatim Q and A); explanations of one-offs.",
    "annual_report": "Accounting-policy notes (revenue recognition, depreciation, capitalization); raw-material/cost-of-materials breakdown; segment revenue/results/capital employed; top-customer disclosures; related-party transactions (amounts, counterparties); contingent liabilities; CWIP; borrowings schedule; auditor report language incl. CARO; MD&A demand/strategy passages; SPECIFIC risk factors (skip boilerplate); remuneration; pledge.",
    "investor_presentation": "Segment/revenue mix as numbers; order book / new wins; capacity and utilization; capex plans with amounts and timelines; market-share claims; strategy targets.",
    "results_pdf": "Every financial-statement line item as printed with quarter and YoY comparatives; exceptional items and their notes; segment tables; auditor limited-review remarks.",
    "rating_rationale": "Rating, outlook, and any change; EVERY listed strength and weakness; leverage/coverage/liquidity numbers cited; customer/supplier concentration statements; the agency's forward expectations.",
    "screener_page": "The complete ratio and statement tables — EVERY row-year cell becomes a metric candidate (P&L, balance sheet, cash flow, ratios, shareholding, price/valuation numbers as displayed). Passages only for the 'about' text.",
    "shareholding": "Category-wise holding percentages, quarterly trend, promoter pledge percentage.",
    "news_batch": "Dated events and direct quotes only; note publication and date per item; skip opinion and anonymous speculation.",
    "valuepickr": "Distinct bull arguments and bear arguments (verbatim, attribute as 'forum claim'); factual claims worth verifying. NEVER as fact — always as claims.",
    "sector_page": "Industry data points (volumes, prices, growth rates) with their periods; association/agency outlook statements — capture BOTH the recent view and any medium-term view.",
    "macro_page": "Indicator values with dates; official/institutional forecasts with horizon; policy decisions with effective dates.",
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
be read, {"url": ..., "readable": false} and move on."""


def _instruction(doc_class: str) -> str:
    return ("You are an ingestion instrument for an equity research platform. "
            f"From the document(s) below, extract with this focus: {_FOCUS[doc_class]}\n\n"
            + _SCHEMA)


def _persist_source(read: dict, url: str, extracted_len: int, raw: dict,
                    layer: str, ticker: str) -> tuple:
    doc_id, created = db.save_source_document(
        doc_type=_DOC_TYPE_MAP[read["doc_class"]],
        title=read.get("title") or read["target"],
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
        if parsed["about"] and (created or not persist):
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
             "events": [], "read_log": []}
    seen_doc_ids: set = set()   # a doc reachable via >1 URL loads once (Phase 0.4)

    for read in state["url_plan"]:
        layer = _layer_of(read["doc_class"])

        # --- Phase 1: screener pages parse deterministically, fresh each run
        if read["doc_class"] == "screener_page":
            if _screener_via_parser(read, pools, state, entities):
                continue

        # --- reuse shortcut: URL already ingested -> reload evidence + pools
        if persist and not state.get("reingest"):
            reused = True
            for url in list(read["urls"]):
                doc_id = db.get_source_document_by_url(url)
                if not doc_id:
                    reused = False
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
                            "title": read.get("title") or read["target"],
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

        # --- fresh read
        print(f"[s2_extract] read {read['target']} ({len(read['urls'])} url) ...")
        try:
            text = read_urls(read["urls"], _instruction(read["doc_class"]))
        except CallDeadlineError:
            print(f"  [s2][warn] deadline expired — skipping {read['target']}")
            pools["read_log"].append({"target": read["target"], "outcome": "deadline"})
            continue
        except LLMError:
            raise      # model-level failure: abort run (no-retry policy)

        parsed = parse_json_lenient(text)
        if not parsed or "sources" not in parsed:
            # Phase 2.7: ONE reprompt on malformed JSON (documented exception
            # to the no-retry policy — extraction is expensive to re-fetch and
            # the failure is a formatting slip, not a model/quota failure).
            print(f"  [s2][warn] unparseable extraction for {read['target']} — "
                  f"reprompting once")
            try:
                text = read_urls(read["urls"], _instruction(read["doc_class"]) +
                                 "\n\nYour previous response was NOT valid JSON. "
                                 "Return ONLY the JSON object described above — "
                                 "no prose, no markdown fences.")
                parsed = parse_json_lenient(text)
            except CallDeadlineError:
                parsed = None
            if not parsed or "sources" not in parsed:
                print(f"  [s2][warn] still unparseable — skipping {read['target']}")
                pools["read_log"].append({"target": read["target"],
                                          "url": read["urls"][0] if read["urls"] else None,
                                          "outcome": "parse_failed"})
                continue

        for src in parsed["sources"]:
            url = src.get("url") or read["urls"][0]
            if not src.get("readable", True):
                print(f"  [s2][warn] unreadable: {url}")
                pools["read_log"].append({"url": url, "outcome": "unreadable"})
                continue

            passages = src.get("passages") or []
            candidates = src.get("metric_candidates") or []
            doc_id = None
            risk_ev_ids = []
            if persist:
                doc_id, _ = _persist_source(read, url, len(text), src, layer,
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
                         "title": read.get("title") or read["target"],
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

    if persist:
        plan = state["read_plan"]

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
          f"{len(pools['risk_signals'])} risk signals")
    return pools
