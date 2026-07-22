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

import hashlib
import json

from src import db
from src.config import REUSE_MIN_PASSAGES
from src.pipeline.citations import build_label_map
from src.ingestion.fetcher import (
    fetch_document, looks_like_presentation, FetchError,
)
from src.llm import (
    read_urls, synthesize, parse_json_lenient, LLMError, CallDeadlineError,
    set_current_node, note_wasted_output,
)

_DOC_TYPE_MAP = {   # doc_class -> source_documents.type
    "concall": "concall_transcript", "annual_report": "annual_report",
    "investor_presentation": "other",
    "rating_rationale": "brokerage_report", "screener_page": "other",
    "news_batch": "news", "sector_page": "industry_report",
    "macro_page": "macro_data",
    # (Round 4.5 drops: results_pdf, shareholding, valuepickr)
}

_FOCUS = {
    "concall": "ALL forward-looking guidance statements (with speaker); volume/demand commentary; margin walk explanations; capex/order-book updates; every analyst question management dodged or answered defensively (verbatim Q and A); explanations of one-offs.",
    "annual_report": "Accounting-policy notes (revenue recognition, depreciation, capitalization); raw-material/cost-of-materials breakdown BY MATERIAL with amounts (each line a metric_candidate); segment tables — revenue, results, capital employed per segment, EVERY cell a metric_candidate; geography/export revenue split (each region a metric_candidate); top-customer disclosures under Ind-AS 108 (customer concentration % -> metric_candidate); forex earnings and spend; related-party transactions (amounts, counterparties); contingent liabilities; CWIP; borrowings schedule; auditor report language incl. CARO; MD&A demand/strategy passages; SPECIFIC risk factors (skip boilerplate); remuneration; pledge. SKIP standard P&L/BS/CF statement line-items entirely — they are supplied deterministically elsewhere and discarded here.",
    "investor_presentation": "EXHAUSTIVE one-shot: EVERY number, guidance, claim and projection — segment/revenue mix as numbers (each slice a metric_candidate); order book value and new wins (metric_candidates); EV/BEV revenue share; capacity and utilization per plant (metric_candidates); capex plans with amounts and timelines; export/geography mix; market-share claims; strategy targets with dates. Miss nothing quantitative.",
    "rating_rationale": "Rating, outlook, and any change; EVERY listed strength and weakness; leverage/coverage/liquidity numbers cited; customer/supplier concentration statements; the agency's forward expectations.",
    "screener_page": "The complete ratio and statement tables — EVERY row-year cell becomes a metric candidate (P&L, balance sheet, cash flow, ratios, shareholding, price/valuation numbers as displayed). Passages only for the 'about' text.",
    "news_batch": "Dated events and direct quotes only; note publication and date per item; skip opinion and anonymous speculation.",
    "sector_page": "Industry data points (volumes, prices, growth rates) with their periods; association/agency outlook statements — capture BOTH the recent view and any medium-term view.",
    "macro_page": "Indicator values with dates; official/institutional forecasts with horizon; policy decisions with effective dates.",
}

_SCHEMA = """Return ONLY this JSON (no commentary):
{"sources": [{"url": "<url>", "readable": true/false,
  "published_date": "<the document's publication/release date as YYYY-MM-DD if stated in it, else null>",
  "passages": [{"text": "<VERBATIM quote, max ~120 words>", "page_or_timestamp": "<as printed or null>",
                "entities_mentioned": ["<names>"], "tags": ["risk_signal"|"guidance_item"|"supply_chain_edge"|"peer_mention"|"event" ...],
                "sections": ["B"|"C"|"D1"|"D2"|"D3"|"E"|"F"|"G"|"H"|"I"]}],
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
"sections" maps each passage to every report section it can serve —
B business & products; C industry/macro; D1 P&L; D2 balance sheet;
D3 cash flow; E supply chain/sourcing; F management, governance &
guidance credibility; G peers/competition; H risks; I valuation.
Multiple sections per passage is normal (cross-section duplication is
by design); an empty list means general context.
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

# Round 4.3: the cross-quarter view is rebuilt by ONE cheap trails-pass
# over the per-quarter extraction OUTPUTS (the batched all-transcripts
# call it replaces shipped every transcript's full text in one prompt).
_TRAILS_SCHEMA = """Return ONLY this JSON:
{"guidance_evolution": [{"metric": "<what was guided>",
   "trail": [{"call": "<quarter label>", "guidance": "<verbatim>"}],
   "direction": "raised|maintained|lowered|dropped", "note": "<one line>"}],
 "recurring_themes": [{"theme": "", "calls": ["<quarter labels>"],
   "pattern": "consistent|evolving|dodged_repeatedly",
   "quote": "<one representative verbatim quote>"}]}
"dropped" = guidance silently stopped being mentioned in later calls.
Verbatim quotes only; no arithmetic; no inference beyond the text."""

# Output budgets: provider cap (64K on Fireworks). Extraction output is
# genuinely long — a 213-page AR under the every-cell focus produced >32K
# tokens of VISIBLE output (not reasoning) and truncated mid-JSON on a
# reingest. Reasoning tokens also live inside this budget (FOUNDATIONS §5.12).
_EXTRACT_MAX_TOKENS = 64000


# --- Round 4.1: the AR conversation --------------------------------------
# Latest AR only, extracted in THEMATIC BUNDLES: every bundle is one call
# sharing an IDENTICAL [system, document] prefix (Fireworks prefix-cache
# serves the re-sent document at a discount — probe-verified 2026-07-21;
# generation time of each bundle covers the cache-write lag) and gets a
# FRESH 64K output budget — which structurally removes the big-AR output
# overflow that used to skip M&M's conglomerate AR.

_AR_CONVERSATION_NOTE = """
This annual report is extracted in MULTIPLE PASSES (bundles). You will
receive ONE bundle instruction after the document; extract ONLY what
that bundle asks for. Style: POINTERS, NOT PARAGRAPHS — for each fact
take the SHORTEST verbatim snippet that carries it (a clause suffices;
<=40 words per passage; never paraphrase — evidence must be verbatim
for downstream verification). Numbers belong in metric_candidates, not
prose. No boilerplate, no repetition inside a pass; cross-bundle
duplication is fine. The passage cap never limits metric_candidates —
capture every number in the bundle's scope."""

# Owner-designed bundles (2026-07-22): four business-understanding
# passes + the statement-disclosures pass that feeds the D1/D2/D3
# forensic architecture (the AR is the ONLY notes-level source).
_AR_BUNDLES = [
    ("company_and_scale",
     "FOCUS THIS PASS: what the company IS — what it does, makes and "
     "sells; the sectors/segments it operates in; scale of operations "
     "(revenue by segment/geography, volumes, plants, capacities, "
     "employees — every number a metric_candidate); who the customers "
     "and end-markets are (names -> entities_mentioned/peer_mentions; "
     "concentration numbers -> metric_candidates)."),
    ("business_model",
     "FOCUS THIS PASS: HOW the company makes money — position in the "
     "value chain; pricing / content-per-unit / mix economics; moats and "
     "entry barriers as stated; key inputs and cost structure; supplier "
     "and customer relationships (-> supply_chain_edges); JVs, "
     "partnerships, licences. These pointers feed the business overview "
     "AND other sections — map sections generously."),
    ("growth_outlook",
     "FOCUS THIS PASS: growth — expansion plans, new capacities/plants, "
     "new products/technologies, order wins, acquisitions, with amounts "
     "and timelines (metric_candidates); guidance and outlook for the "
     "coming year(s) — EVERY forward-looking statement also emitted as a "
     "guidance_item with its verbatim quote."),
    ("management_commentary",
     "FOCUS THIS PASS: management's commentary — business landscape and "
     "demand environment; supply-chain commentary; opportunities and "
     "threats (SWOT-type statements); strategy and investments; SPECIFIC "
     "risks called out (tag risk_signal; skip boilerplate); governance "
     "notes worth knowing (board changes, remuneration, pledge)."),
    ("statement_disclosures",
     "FOCUS THIS PASS: financial-statement DISCLOSURES the standard tables "
     "lack — raw-material/cost-of-materials breakdown BY MATERIAL with "
     "amounts (each line a metric_candidate); segment tables: revenue, "
     "results, capital employed per segment, EVERY cell a metric_candidate; "
     "geography/export revenue split (each region a metric_candidate); "
     "top-customer disclosures under Ind-AS 108; forex earnings and spend; "
     "related-party transactions (amounts, counterparties); contingent "
     "liabilities; CWIP; borrowings schedule; accounting-policy notes "
     "(revenue recognition, depreciation, capitalization); auditor report "
     "language incl. CARO. SKIP standard P&L/BS/CF statement line-items "
     "entirely — they are supplied deterministically elsewhere and "
     "discarded here."),
]


def _focus_hash(doc_class: str) -> str:
    """Round 4.6: extraction prompts are content-versioned. The hash of
    (focus + schema) is stamped into every extract:{doc_id} entry; reuse
    compares and RE-READS on mismatch — changing a focus used to strand
    stale stored extractions silently (Phase-5 lesson, --reingest was
    the only cure). Pre-R4 entries carry no hash → first run under R4
    re-reads everything once and stamps them."""
    body = _FOCUS.get(doc_class, "") + _SCHEMA
    if doc_class == "annual_report":
        body += "".join(f for _, f in _AR_BUNDLES)
    return hashlib.sha256(body.encode("utf-8")).hexdigest()[:16]


def _instruction(doc_class: str, inline: bool = False, n_sources: int = 1) -> str:
    head = "You are an ingestion instrument for an equity research platform. "
    if inline:
        head += (f"Below are {n_sources} fetched document(s), each opened by a "
                 "line '=== SOURCE: <url> ==='. Emit one entry in \"sources\" "
                 "per URL, in the order given, echoing each url exactly. ")
    head += (f"Extract with this focus: {_FOCUS[doc_class]}\n\n" + _SCHEMA)
    return head


def _url_title(read: dict, url: str) -> str:
    return (read.get("titles_by_url", {}).get(url)
            or read.get("title") or read["target"])


_DATE_RE = None


def _clean_date(raw) -> str | None:
    """Round 4.2: accept only strict YYYY-MM-DD from the extraction —
    anything else (quarters, prose, guesses) stays null."""
    global _DATE_RE
    import re as _re
    if _DATE_RE is None:
        _DATE_RE = _re.compile(r"^\d{4}-\d{2}-\d{2}$")
    s = str(raw or "").strip()
    return s if _DATE_RE.match(s) else None


def _persist_source(read: dict, url: str, raw: dict,
                    layer: str, ticker: str) -> tuple:
    doc_id, created = db.save_source_document(
        doc_type=_DOC_TYPE_MAP[read["doc_class"]],
        title=_url_title(read, url),
        url_or_path=url,
        text_for_hash=json.dumps(raw, sort_keys=True)[:100000],
        published_date=_clean_date(raw.get("published_date")),
        metadata={"doc_class": read["doc_class"], "layer": layer,
                  "ticker": ticker, "discovered_for": read["target"],
                  "fetch_hash": (read.get("_fetch_hashes") or {}).get(url)},
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


def _concall_trails_pass(pools) -> None:
    """Round 4.3: ONE call over the per-quarter extraction outputs
    (guidance items grouped by quarter label + guidance-tagged concall
    passages) rebuilds guidance_evolution/recurring_themes — the
    cross-quarter view survives the batched-call split at ~1/10th the
    input. Failure degrades to the stored trails (rehydrated later)."""
    from src.llm import generate_json, set_current_node
    items = [g for g in pools["guidance_items"] if g.get("quarter_label")]
    if not items:
        return
    by_q: dict = {}
    for g in items:
        by_q.setdefault(g["quarter_label"], []).append(g)
    parts = []
    for q in sorted(by_q):
        rows = "\n".join(
            "- " + json.dumps({k: v for k, v in g.items()
                               if k != "quarter_label"}, default=str)[:400]
            for g in by_q[q][:25])
        parts.append(f"=== CALL: {q} ===\n{rows}")
    tagged, used = [], 0
    for e in pools["evidence_pool"]:
        if e["doc_class"] == "concall" and "guidance_item" in (e.get("tags") or []):
            t = f"[{e['title']}] {e['text'][:300]}"
            if used + len(t) > 12000:
                break
            tagged.append(t)
            used += len(t)
    user = "PER-QUARTER GUIDANCE ITEMS:\n" + "\n\n".join(parts) + \
           ("\n\nGUIDANCE-TAGGED CONCALL PASSAGES:\n" + "\n".join(tagged)
            if tagged else "")
    set_current_node("s2:concall_trails")
    try:
        result = generate_json(
            "You build the cross-quarter guidance view for an equity "
            "research platform from per-quarter concall extraction outputs "
            "(=== CALL: <label> === groups one quarter).\n" + _TRAILS_SCHEMA,
            user, temperature=0.1, max_tokens=16384)
    except Exception as e:
        print(f"  [s2][warn] trails-pass failed — stored trails rehydrate "
              f"if present: {e}")
        return
    pools["guidance_evolution"] = result.get("guidance_evolution") or []
    pools["recurring_themes"] = result.get("recurring_themes") or []
    print(f"  [s2] cross-quarter trails-pass: "
          f"{len(pools['guidance_evolution'])} trails, "
          f"{len(pools['recurring_themes'])} themes (1 call over outputs)")


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


def _ar_conversation(read: dict, url: str, doc: dict) -> dict | None:
    """Round 4.1: bundle-wise AR extraction. Each bundle re-sends the
    identical [system, document] prefix (cache-served) with only the
    bundle instruction differing, and parses/merges its own JSON. A
    bundle failing twice is skipped alone — the other bundles' yield
    still lands (the old single-call path lost the WHOLE document on
    overflow)."""
    from src.llm import raw_chat
    label = _url_title(read, url)
    base_system = ("You are an ingestion instrument for an equity research "
                   "platform. Below is one fetched document, opened by a "
                   "line '=== SOURCE: <url> ==='. Emit one entry in "
                   "\"sources\" for it, echoing the url exactly.\n\n"
                   + _SCHEMA + "\n" + _AR_CONVERSATION_NOTE)
    doc_msg = f"=== SOURCE: {url} ===\n({label})\n{doc['text']}"
    merged = {"url": url, "readable": True, "published_date": None,
              "passages": [], "metric_candidates": [], "guidance_items": [],
              "supply_chain_edges": [], "peer_mentions": [], "events": []}
    seen_texts: set = set()
    ok_bundles = 0
    for name, focus in _AR_BUNDLES:
        parsed = None
        for extra in ("", "\nYour previous response was invalid or "
                          "truncated JSON. Be MUCH terser: fewer and "
                          "shorter passages; output ONLY the JSON."):
            msgs = [{"role": "system", "content": base_system},
                    {"role": "user", "content": doc_msg},
                    {"role": "user", "content":
                     f"BUNDLE '{name}': {focus}{extra}\n"
                     f"Return ONLY the JSON object for THIS bundle."}]
            try:
                data = raw_chat(msgs, max_tokens=_EXTRACT_MAX_TOKENS,
                                temperature=0.1)
            except CallDeadlineError:
                print(f"  [s2][warn] deadline — skipping bundle '{name}'")
                break
            except LLMError as e:
                from src.llm import ModelOverloadedError
                if isinstance(e, ModelOverloadedError) or \
                        "timed out" not in str(e).lower():
                    raise
                print(f"  [s2][warn] AR bundle '{name}' transport timeout — "
                      f"{'retrying once' if not extra else 'skipping bundle'}")
                continue
            choice = (data.get("choices") or [{}])[0]
            content = (choice.get("message") or {}).get("content") or ""
            if choice.get("finish_reason") == "length" or not content:
                print(f"  [s2][warn] AR bundle '{name}' truncated — "
                      f"reprompting once" if not extra else
                      f"  [s2][warn] AR bundle '{name}' truncated twice")
                note_wasted_output("truncation")
                continue
            cand = parse_json_lenient(content)
            if cand and cand.get("sources"):
                parsed = cand
                cached = ((data.get("usage") or {})
                          .get("prompt_tokens_details") or {}).get("cached_tokens", 0)
                src0 = parsed["sources"][0]
                print(f"  [s2] AR bundle '{name}': "
                      f"{len(src0.get('passages') or [])} passages, "
                      f"{len(src0.get('metric_candidates') or [])} candidates "
                      f"(cached {cached:,} tok)")
                break
            print(f"  [s2][warn] AR bundle '{name}' unparseable — "
                  f"{'reprompting once' if not extra else 'skipping bundle'}")
        if not parsed:
            continue
        src = parsed["sources"][0]
        merged["published_date"] = merged["published_date"] or \
            src.get("published_date")
        for p in src.get("passages") or []:
            key = (p.get("text") or "").strip()[:200]
            if key and key not in seen_texts:
                seen_texts.add(key)
                merged["passages"].append(p)
        for field in ("metric_candidates", "guidance_items",
                      "supply_chain_edges", "peer_mentions", "events"):
            merged[field] += src.get(field) or []
        ok_bundles += 1
    if not ok_bundles:
        return None
    print(f"  [s2] AR conversation done: {ok_bundles}/{len(_AR_BUNDLES)} "
          f"bundles, {len(merged['passages'])} passages, "
          f"{len(merged['metric_candidates'])} candidates")
    return {"sources": [merged]}


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
                note_wasted_output("truncation")   # Round 1: burned budget
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
        passage_tags = {}   # evidence_id -> tags (Round 1.3: tags used to
                            # die at reuse — evidence has no tags column,
                            # so the per-passage map persists HERE)
        passage_sections = {}   # evidence_id -> report sections (Round 4.2)
        pub_date = _clean_date(src.get("published_date"))
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
                     "tags": p.get("tags") or [], "page": p.get("page_or_timestamp"),
                     "sections": p.get("sections") or [], "date": pub_date}
            pools["evidence_pool"].append(entry)
            if entry["tags"]:
                passage_tags[str(entry["id"])] = entry["tags"]
            if entry["sections"]:
                passage_sections[str(entry["id"])] = entry["sections"]
            if "risk_signal" in entry["tags"]:
                pools["risk_signals"].append({"evidence_id": entry["id"],
                                              "text": ptext[:300], "url": url})
                risk_ev_ids.append(entry["id"])

        for c in candidates:
            c["source_document_id"] = doc_id
            c["doc_class"] = read["doc_class"]
            c["url"] = url
        pools["metric_candidates"] += candidates
        g_items = src.get("guidance_items") or []
        if read["doc_class"] == "concall":
            # Round 4.3: per-quarter attribution survives the batched-call
            # split — the trails-pass groups guidance by these labels
            for g in g_items:
                g["quarter_label"] = _url_title(read, url)
        pools["guidance_items"] += g_items
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
                 "risk_evidence_ids": risk_ev_ids,
                 "passage_tags": passage_tags,
                 "passage_sections": passage_sections,
                 "published_date": pub_date,
                 "focus_hash": _focus_hash(read["doc_class"])},
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

    # Round 2.4: 10y monthly series -> FY-end (March) closes for the
    # COMPUTED annual-PE history in s3 (replaces the retired wisesheets
    # scrape). "Mar YYYY" labels parse as that FY's annual period. Same
    # zero-LLM, identity-validated source; absence degrades to an
    # honest insufficiency in the percentile, never fails the run.
    try:
        pts10, url10, _ = fetch_price_history(profile["ticker"], tokens,
                                              range_="10y", interval="1mo")
    except Exception as e:
        print(f"  [s2][warn] 10y price history unavailable ({e}) — "
              f"own-history PE percentile may degrade to insufficiency")
        return
    fy_points = [(label, close) for label, close in pts10
                 if label.startswith("Mar ")]
    if not fy_points:
        return
    doc_id10 = None
    if state["persist"]:
        doc_id10, _ = db.save_source_document(
            doc_type="other",
            title=f"Price history 10y FY-end closes ({long_name})",
            url_or_path=url10 + "#range=10y",
            text_for_hash=json.dumps(fy_points),
            metadata={"doc_class": "price_history", "layer": "company",
                      "ticker": profile["ticker"]})
    for label, close in fy_points:
        pools["metric_candidates"].append({
            "name": "price", "value_printed": str(close),
            "period_printed": label, "basis": None, "statement": "price",
            "ambiguous": False, "doc_class": "price_history", "url": url10,
            "source_document_id": doc_id10})
    pools["read_log"].append({"url": url10 + "#range=10y", "outcome": "parsed",
                              "metrics": len(fy_points)})
    print(f"  [s2] price history (no LLM): {len(fy_points)} FY-end closes "
          f"for computed PE history")


def _pool_stored_extraction(read, url, rows, content, pools) -> None:
    """Mirror of the URL-reuse rehydration (evidence with
    tags/sections/date + all candidate pools) for the content-hash
    reuse path (Round 5: rotated BSE URLs must not force re-reads)."""
    ptags = {str(k): v for k, v in (content.get("passage_tags") or {}).items()}
    if not ptags:
        ptags = {str(i): ["risk_signal"]
                 for i in content.get("risk_evidence_ids") or []}
    psecs = {str(k): v for k, v in
             (content.get("passage_sections") or {}).items()}
    pdate = content.get("published_date")
    for r in rows:
        pools["evidence_pool"].append({
            "id": r["id"], "text": r["text"], "url": url,
            "doc_class": read["doc_class"], "title": _url_title(read, url),
            "tags": ptags.get(str(r["id"]), []),
            "sections": psecs.get(str(r["id"]), []), "date": pdate,
            "page": r.get("page_or_timestamp")})
    pools["metric_candidates"] += content.get("metric_candidates", [])
    g_items = content.get("guidance_items", [])
    if read["doc_class"] == "concall":
        for g in g_items:
            g.setdefault("quarter_label", _url_title(read, url))
    pools["guidance_items"] += g_items
    pools["supply_edges"] += content.get("supply_chain_edges", [])
    pools["peer_mentions"] += content.get("peer_mentions", [])
    pools["events"] += content.get("events", [])
    for ev_id in content.get("risk_evidence_ids", []):
        pools["risk_signals"].append({"evidence_id": ev_id, "url": url})


def _rehydrate_backbone(state, pools) -> bool:
    """Round 3.2: pour the sector-stored numeric backbone (screener
    candidates + about evidence + doc links for every member; price
    series for the run company) into this run's pools — the exact shape
    the in-run parser path produces, zero fetches. Returns True when the
    run company's price series came from the backbone."""
    bb = (state.get("backbone") or {}).get("members") or {}
    if not bb:
        return False
    persist = state["persist"]
    own_slug = state["profile"]["screener_slug"]
    own_prices = False
    for slug, m in bb.items():
        url = m["url"]
        for c in m.get("candidates") or []:
            c = dict(c)
            c["doc_class"] = "screener_page"
            c["url"] = url
            c["source_document_id"] = m.get("doc_id")
            c["basis"] = "consolidated" if "/consolidated/" in url else "standalone"
            pools["metric_candidates"].append(c)
        if m.get("about"):
            ev_id = m.get("about_ev_id") or (
                db.save_evidence(m["doc_id"], m["about"]) if persist
                else f"mem_{len(pools['evidence_pool'])}")
            pools["evidence_pool"].append({
                "id": ev_id, "text": m["about"], "url": url,
                "doc_class": "screener_page", "title": f"screener:{slug}",
                "tags": [], "page": None})
        pools.setdefault("screener_doc_links", {})[url] = m.get("doc_links") or {}
        pools["read_log"].append({"url": url, "outcome": "backbone",
                                  "metrics": len(m.get("candidates") or [])})
        if slug == own_slug:
            series = (("1y", m.get("closes_1y")), ("10y", m.get("closes_fy")))
            for key, pts in series:
                for label, close in pts or []:
                    pools["metric_candidates"].append({
                        "name": "price", "value_printed": str(close),
                        "period_printed": label, "basis": None,
                        "statement": "price", "ambiguous": False,
                        "doc_class": "price_history",
                        "url": (m.get("price_urls") or {}).get(key),
                        "source_document_id": (m.get("price_doc_ids") or {}).get(key)})
            own_prices = bool(m.get("closes_1y"))
    print(f"  [s2] sector backbone rehydrated: {len(bb)} member screeners, "
          f"0 fetches" + (", incl. own price series" if own_prices else ""))
    return own_prices


def extract_node(state) -> dict:
    if state.get("dry_run"):
        from src.pipeline.dry_run import synthetic_extraction
        print("[s2_extract] DRY RUN — synthetic extraction")
        pools = synthetic_extraction(state)
        pools["citation_labels"], pools["citation_docs"] = \
            build_label_map(pools["evidence_pool"])
        return pools

    persist = state["persist"]
    profile = state["profile"]
    entities = db.list_entities() if persist else []
    company_id = profile.get("entity_id")

    pools = {"evidence_pool": [], "metric_candidates": [], "guidance_items": [],
             "risk_signals": [], "supply_edges": [], "peer_mentions": [],
             "events": [], "read_log": [],
             "guidance_evolution": [], "recurring_themes": []}
    seen_doc_ids: set = set()   # a doc reachable via >1 URL loads once (Phase 0.4)

    # Round 3.2: a fresh sector backbone supplies screener + price data
    # for all members; the live Yahoo fetch runs only when it didn't.
    if not _rehydrate_backbone(state, pools):
        _price_history_via_yahoo(state, pools)

    # Round 4.3: concalls are read PER TRANSCRIPT (isolation, smaller
    # contexts); the cross-quarter view comes from the trails-pass below.
    url_plan = state["url_plan"]
    fresh_concalls = False

    for read in url_plan:
        layer = _layer_of(read["doc_class"])
        set_current_node(f"s2:{read['target']}")   # Round 1: per-node telemetry

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
                pool_entry = db.get_latest("company" if layer == "company" else layer,
                                           company_id or profile.get("entity_id"),
                                           _pool_entry_section(doc_id))
                # Round 4.6: a stored extraction made under a different
                # focus/schema is STALE — re-read instead of reusing it
                stored_hash = ((pool_entry or {}).get("content_json")
                               or {}).get("focus_hash")
                if stored_hash != _focus_hash(read["doc_class"]):
                    print(f"  [s2] extraction focus changed (stored: "
                          f"{stored_hash or 'pre-R4, unhashed'}) — re-reading "
                          f"{read['doc_class']}: {url}")
                    continue
                seen_doc_ids.add(doc_id)
                if rows:
                    print(f"  [s2] reuse ({len(rows)} evidence, no LLM call): {url}")
                    # Round 1.3: rehydrate per-passage tags (reuse used to
                    # hard-set tags=[], starving H's risk_signal feed and
                    # every tag-filtered slice). Pre-fix entries carry no
                    # passage_tags — backfill at least risk_signal from
                    # risk_evidence_ids (the load-bearing tag).
                    content = (pool_entry or {}).get("content_json") or {}
                    ptags = {str(k): v for k, v in
                             (content.get("passage_tags") or {}).items()}
                    if not ptags:
                        ptags = {str(i): ["risk_signal"]
                                 for i in content.get("risk_evidence_ids") or []}
                    psecs = {str(k): v for k, v in
                             (content.get("passage_sections") or {}).items()}
                    pdate = content.get("published_date")
                    for r in rows:
                        pools["evidence_pool"].append({
                            "id": r["id"], "text": r["text"], "url": url,
                            "doc_class": read["doc_class"],
                            "title": _url_title(read, url),
                            "tags": ptags.get(str(r["id"]), []),
                            "sections": psecs.get(str(r["id"]), []),
                            "date": pdate,
                            "page": r.get("page_or_timestamp")})
                    if pool_entry:
                        c = pool_entry["content_json"]
                        pools["metric_candidates"] += c.get("metric_candidates", [])
                        g_items = c.get("guidance_items", [])
                        if read["doc_class"] == "concall":
                            for g in g_items:
                                g.setdefault("quarter_label",
                                             _url_title(read, url))
                        pools["guidance_items"] += g_items
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
            # Round 5: reuse-by-content-hash — the fetch is free, so a
            # rotated URL serving ALREADY-EXTRACTED content (BSE Pname
            # guids) reuses the stored extraction instead of paying for
            # a re-read; only honored when the stored extraction was
            # made under the CURRENT focus (4.6 hash).
            fh = hashlib.sha256(
                doc["text"][:500000].encode("utf-8", "replace")).hexdigest()[:32]
            read.setdefault("_fetch_hashes", {})[url] = fh
            if persist and not state.get("reingest"):
                known = db.get_source_document_by_fetch_hash(fh)
                if known and known not in seen_doc_ids:
                    entry = db.get_latest(
                        "company" if layer == "company" else layer,
                        company_id or profile.get("entity_id"),
                        _pool_entry_section(known))
                    content = (entry or {}).get("content_json") or {}
                    rows = db.get_evidence_for_document(known) \
                        if content.get("focus_hash") == _focus_hash(read["doc_class"]) \
                        else []
                    if rows:
                        print(f"  [s2] reuse by content-hash ({len(rows)} "
                              f"evidence, no LLM call — url rotated): {url}")
                        _pool_stored_extraction(read, url, rows, content, pools)
                        seen_doc_ids.add(known)
                        pools["read_log"].append({"url": url,
                                                  "outcome": "reused_hash"})
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
            n_pages = sum(d.get("pages") or 0 for d in inline_docs.values())
            print(f"[s2_extract] read {read['target']} "
                  f"({len(inline_urls)} url, local fetch, "
                  f"{sum(d['char_count'] for d in inline_docs.values())} chars"
                  + (f", {n_pages} pdf pages" if n_pages else "") + ") ...")
            if read["doc_class"] == "annual_report" and len(inline_urls) == 1:
                # Round 4.1: bundle-wise conversation, fresh 64K per bundle
                parsed = _ar_conversation(read, inline_urls[0],
                                          inline_docs[inline_urls[0]])
            else:
                system = _instruction(read["doc_class"], inline=True,
                                      n_sources=len(inline_urls))
                doc_blocks = []
                for url in inline_urls:
                    label = _url_title(read, url)
                    doc_blocks.append(f"=== SOURCE: {url} ===\n({label})\n"
                                      f"{inline_docs[url]['text']}")
                user = "\n\n".join(doc_blocks)

                def _inline_call(extra, _system=system, _user=user):
                    from src.config import REASONING_EFFORT_EXTRACT
                    return synthesize(
                        [{"role": "system", "content": _system + extra},
                         {"role": "user", "content": _user}],
                        temperature=0.1, max_tokens=_EXTRACT_MAX_TOKENS,
                        reasoning_effort=REASONING_EFFORT_EXTRACT)

                parsed = _extract_call(_inline_call, read["target"])
            if parsed:
                _ingest_sources(parsed, read, inline_urls, pools, state,
                                entities, layer)
                if read["doc_class"] == "concall":
                    fresh_concalls = True
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
                if read["doc_class"] == "concall":
                    fresh_concalls = True
            else:
                for url in fallback_urls:
                    pools["read_log"].append({"url": url, "outcome": "parse_failed"})

    if persist:
        plan = state["read_plan"]

        # --- Round 4.3: any FRESH concall extraction rebuilds the
        # cross-quarter view via the trails-pass (over outputs, not
        # transcripts); all-reused runs rehydrate the stored one —
        # freshness must never mean "run without the data" (§6.5).
        if fresh_concalls:
            _concall_trails_pass(pools)
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

    # Citation labels are assigned LAST — the pool is only final after the
    # fresh-layer rehydration above, and a passage stamped before that
    # would be unlabelled and therefore uncitable.
    pools["citation_labels"], pools["citation_docs"] = \
        build_label_map(pools["evidence_pool"])

    print(f"[s2_extract] done: {len(pools['evidence_pool'])} passages, "
          f"{len(pools['metric_candidates'])} metric candidates, "
          f"{len(pools['guidance_items'])} guidance items, "
          f"{len(pools['risk_signals'])} risk signals, "
          f"{len(pools['guidance_evolution'])} guidance trails")
    print(f"  [s2] citation labels: {len(pools['citation_labels'])} passages "
          f"across {len(pools['citation_docs'])} documents")
    return pools
