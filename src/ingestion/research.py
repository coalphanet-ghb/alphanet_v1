"""
Source gathering for the company research loop. Two-step, per HANDOFF.md §4
— only the discovery engine changed after Google closed gemini-2.5-flash
(the one card-free google_search path) to new users:

  Step 1 — DISCOVER (ddgs, deterministic Python, zero LLM calls):
           hand-curated finance queries per layer (macro -> sector ->
           stock, see queries.py) find candidate URLs. URLs are the ONLY
           output of this step.
  Step 2 — READ (gemini-3.5-flash + url_context):
           extract verbatim passages from those URLs. THIS is what
           populates evidence.text.

Persistence happens inline: each read URL becomes a source_documents row
(deduped by content hash), each passage an evidence row, and each chunk_id
IS the evidence row's UUID — so a citation tag in the report resolves
directly to a citable evidence row. If Supabase isn't configured, we warn
and keep chunks in-memory only.

Downstream contract is unchanged: every analysis node only ever sees
state["raw_chunks"].
"""

import re
import time
from typing import List

from src.config import (
    MAX_RESULTS_PER_QUERY, MAX_URLS_MACRO, MAX_URLS_SECTOR, MAX_URLS_COMPANY,
    MAX_CHUNKS_PER_RUN, CHUNK_SIZE_CHARS, supabase_configured,
)
from src.llm import read_urls, LLMError, CallDeadlineError
from src.workflow.state import SourceChunk
from src.ingestion.queries import MACRO_QUERIES, SECTOR_AUTO_QUERIES, COMPANY_QUERY_TEMPLATES
from src import db

_READ_INSTRUCTIONS = {
    "macro": (
        "You are an ingestion tool for an equity research platform. From the "
        "URL below, extract the substantive passages about macroeconomic "
        "indicators: the actual numbers (rates, prices, growth figures), their "
        "dates/periods, direction of change, and any institutional forecasts "
        "or guidance. Quote passages VERBATIM from the source — do not "
        "summarize, paraphrase, or add analysis. Include section headings or "
        "dates present. If the URL cannot be read, say so."
    ),
    "industry": (
        "You are an ingestion tool for an equity research platform. From the "
        "URL below, extract the substantive passages about the industry: "
        "sales volumes, market share, growth rates, pricing, input costs, "
        "policy impacts, and named companies' positions. Quote passages "
        "VERBATIM from the source — do not summarize, paraphrase, or add "
        "analysis. Include section headings or dates present. If the URL "
        "cannot be read, say so."
    ),
    "company": (
        "You are an ingestion tool for an equity research platform. From the "
        "URL below, extract the substantive passages relevant to the "
        "company's business, financial results, management commentary, "
        "guidance, risks, valuation commentary, and competitive position. "
        "Quote passages VERBATIM from the source — do not summarize, "
        "paraphrase, or add your own analysis. Include any page numbers, "
        "section headings, or timestamps present. If the URL cannot be "
        "read, say so."
    ),
}


def _split_into_chunks(text: str, chunk_size: int = CHUNK_SIZE_CHARS) -> List[str]:
    text = re.sub(r"[ \t]+", " ", text).strip()
    if len(text) < 200:
        return []
    pieces = []
    for i in range(0, len(text), chunk_size):
        piece = text[i:i + chunk_size].strip()
        if len(piece) >= 200:
            pieces.append(piece)
    return pieces


def _match_entities(text: str, entities: List[dict]) -> List[str]:
    """Naive substring entity linking against the hand-seeded entity set.
    Deliberately not NER (HANDOFF.md §10)."""
    lowered = text.lower()
    return [e["id"] for e in entities if e["name"].lower() in lowered]


def _discover_urls(query_specs: List[tuple], max_urls: int, seen_urls: set) -> List[dict]:
    """
    Step 1. query_specs: [(query, source_type, doc_type), ...].
    Returns up to max_urls candidates, interleaved across queries so a
    single query can't hog the whole budget.
    """
    from ddgs import DDGS

    per_query: List[List[dict]] = []
    with DDGS() as ddgs:
        for query, source_type, doc_type in query_specs:
            try:
                results = list(ddgs.text(query, region="in-en",
                                         max_results=MAX_RESULTS_PER_QUERY))
            except Exception as e:
                print(f"  [warn] search failed for '{query}': {e}")
                continue
            bucket = []
            for r in results:
                url = r.get("href") or r.get("url")
                if not url or url in seen_urls:
                    continue
                seen_urls.add(url)
                bucket.append({
                    "url": url,
                    "title": r.get("title", "untitled"),
                    "source_type": source_type,
                    "doc_type": doc_type,
                    "query": query,
                })
            per_query.append(bucket)
            time.sleep(1)  # be polite to the search backend

    # round-robin across queries: 1st result of each, then 2nd of each, ...
    picked = []
    for rank in range(MAX_RESULTS_PER_QUERY):
        for bucket in per_query:
            if rank < len(bucket):
                picked.append(bucket[rank])
                if len(picked) >= max_urls:
                    return picked
    return picked


def _read_and_persist(candidates: List[dict], layer: str, persist: bool,
                      entities: List[dict], ticker: str) -> List[SourceChunk]:
    """Step 2: url_context read per URL, chunk, and persist as evidence."""
    chunks: List[SourceChunk] = []
    instruction = _READ_INSTRUCTIONS[layer]

    for cand in candidates:
        url, title = cand["url"], cand["title"]

        # Rerun shortcut: if this exact URL was already ingested, reuse its
        # evidence rows and spend zero LLM calls on it. (To force a fresh
        # read of a URL, delete its source_documents row.)
        if persist:
            known_doc_id = db.get_source_document_by_url(url)
            if known_doc_id:
                rows = db.get_evidence_for_document(known_doc_id)
                if rows:
                    print(f"  [gather_sources] URL already ingested — reusing "
                          f"{len(rows)} evidence rows (no LLM call): {url}")
                    for row in rows:
                        chunks.append(SourceChunk(
                            chunk_id=row["id"],
                            source_title=title,
                            source_url=url,
                            source_type=cand["source_type"],
                            published_date=None,
                            text=row["text"],
                            evidence_id=row["id"],
                            source_document_id=known_doc_id,
                        ))
                    continue

        try:
            extracted = read_urls([url], instruction)
        except CallDeadlineError as e:
            # This URL was too slow/heavy for Google's request deadline —
            # a property of the page, not the model. Skip it and move on.
            print(f"  [warn] skipping slow/heavy URL (deadline expired): {url}")
            continue
        except LLMError:
            # Model-level failure (busy/quota/bad model). Calls are strictly
            # sequential — the next URL is only attempted after a success —
            # so abort the whole run rather than burn time URL by URL.
            raise
        except Exception as e:
            print(f"  [warn] failed to read {url}: {e}")
            continue

        pieces = _split_into_chunks(extracted)
        if not pieces:
            print(f"  [warn] nothing substantive extracted from {url}")
            continue

        source_document_id = None
        existing_evidence = None
        if persist:
            source_document_id, created = db.save_source_document(
                doc_type=cand["doc_type"], title=title, url_or_path=url,
                text_for_hash=extracted,
                metadata={"discovered_for": cand["query"], "layer": layer,
                          "ticker": ticker},
            )
            if not created:
                # Rerun on unchanged content: reuse the evidence rows from
                # the first ingestion instead of inserting duplicates.
                existing_evidence = db.get_evidence_for_document(source_document_id)
                print(f"  [gather_sources] already ingested (hash match), "
                      f"reusing {len(existing_evidence)} evidence rows: {url}")

        if existing_evidence:
            for row in existing_evidence:
                chunks.append(SourceChunk(
                    chunk_id=row["id"],
                    source_title=title,
                    source_url=url,
                    source_type=cand["source_type"],
                    published_date=None,
                    text=row["text"],
                    evidence_id=row["id"],
                    source_document_id=source_document_id,
                ))
            continue

        safe_title = re.sub(r"[^a-zA-Z0-9]+", "_", title[:24]).strip("_") or "src"
        for i, piece in enumerate(pieces):
            if persist:
                evidence_id = db.save_evidence(source_document_id, piece)
                db.link_evidence_entities(evidence_id, _match_entities(piece, entities))
                chunk_id = evidence_id      # citations resolve to evidence rows
            else:
                evidence_id = None
                chunk_id = f"{cand['source_type']}_{safe_title}_{i}"
            chunks.append(SourceChunk(
                chunk_id=chunk_id,
                source_title=title,
                source_url=url,
                source_type=cand["source_type"],
                published_date=None,
                text=piece,
                evidence_id=evidence_id,
                source_document_id=source_document_id,
            ))
    return chunks


def _stub_chunks(macro_context: str, industry_context: str) -> List[SourceChunk]:
    return [
        SourceChunk(
            chunk_id="macro_stub_0",
            source_title="AlphaNet macro research stub",
            source_url="internal://macro_stub",
            source_type="macro_stub",
            published_date=None,
            text=macro_context,
        ),
        SourceChunk(
            chunk_id="industry_stub_0",
            source_title="AlphaNet industry research stub",
            source_url="internal://industry_stub",
            source_type="industry_stub",
            published_date=None,
            text=industry_context,
        ),
    ]


def _synthetic_dry_run_chunks(company_name: str) -> List[SourceChunk]:
    """Small canned corpus so the whole graph can be exercised with zero
    network calls and zero LLM calls, for --dry-run."""
    return [
        SourceChunk(
            chunk_id="concall_synthetic_0",
            source_title="(synthetic) Q-latest concall excerpt",
            source_url="internal://dry_run",
            source_type="concall",
            published_date=None,
            text=(f"[Synthetic dry-run text] Management of {company_name} discussed "
                  "order-book momentum in the BEV driveline segment and reiterated "
                  "capacity expansion plans for the next fiscal year."),
        ),
        SourceChunk(
            chunk_id="news_synthetic_0",
            source_title="(synthetic) recent news excerpt",
            source_url="internal://dry_run",
            source_type="news",
            published_date=None,
            text=(f"[Synthetic dry-run text] {company_name} announced a new order "
                  "win from a global OEM for a differential assembly platform."),
        ),
    ]


def gather_sources_node(state) -> dict:
    company_name = state["company_name"]
    ticker = state["ticker"]

    if state.get("dry_run"):
        print("[gather_sources] DRY RUN — using synthetic chunks, skipping search, Gemini, and Supabase")
        chunks = _stub_chunks(state["macro_context"], state["industry_context"])
        chunks += _synthetic_dry_run_chunks(company_name)
        return {"raw_chunks": chunks}

    persist = supabase_configured()
    entities: List[dict] = []
    if persist:
        entities = db.list_entities()
        if not entities:
            print("  [gather_sources] note: entities table is empty — run "
                  "scripts/seed_entities.py to enable entity linking")
    else:
        print("  [gather_sources] WARNING: Supabase not configured — chunks will "
              "stay in-memory only (no evidence rows persisted)")

    all_chunks: List[SourceChunk] = _stub_chunks(state["macro_context"], state["industry_context"])
    seen_urls: set = set()

    layers = [
        ("macro",
         [(q, "macro", dt) for q, dt in MACRO_QUERIES],
         MAX_URLS_MACRO),
        ("industry",
         [(q, "industry", dt) for q, dt in SECTOR_AUTO_QUERIES],
         MAX_URLS_SECTOR),
        ("company",
         [(tmpl.format(company=company_name, ticker=ticker), st, dt)
          for tmpl, st, dt in COMPANY_QUERY_TEMPLATES],
         MAX_URLS_COMPANY),
    ]

    for layer, query_specs, max_urls in layers:
        print(f"[gather_sources] {layer}: discovering URLs via ddgs "
              f"({len(query_specs)} queries, reading up to {max_urls})...")
        candidates = _discover_urls(query_specs, max_urls, seen_urls)
        if not candidates:
            print(f"  [warn] no URLs discovered for the {layer} layer")
            continue
        print(f"[gather_sources] {layer}: reading {len(candidates)} URLs via url_context...")
        all_chunks += _read_and_persist(candidates, layer, persist, entities, ticker)
        if len(all_chunks) >= MAX_CHUNKS_PER_RUN:
            print("  [gather_sources] chunk cap reached, stopping ingestion")
            break

    all_chunks = all_chunks[:MAX_CHUNKS_PER_RUN]
    print(f"[gather_sources] collected {len(all_chunks)} chunks from {len(seen_urls)} discovered URLs")
    return {"raw_chunks": all_chunks}
