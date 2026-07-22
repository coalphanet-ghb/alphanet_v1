"""
Thin data-access layer over Supabase (Postgres), using the service_role key
server-side (bypasses RLS — never expose this key to a frontend).

Design notes carried over from FOUNDATIONS.md §2:
- The schema is FROZEN. Nothing here alters tables.
- `claims.evidence_ids` is a uuid[] with no FK enforcement possible at the
  DB level, so `save_claims` performs the citation-integrity check in
  application code. That check is the safety net we consciously gave up in
  the schema — do not remove or weaken it.
- `evidence.embedding` stays null. Retrieval is structural (joins through
  entity_mentions), not semantic, at this scale.
"""

import hashlib
from typing import List, Optional

from src.config import SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY, supabase_configured


class DBError(RuntimeError):
    pass


class CitationIntegrityError(DBError):
    """A claim referenced an evidence UUID that does not exist."""


_client = None


def get_client():
    global _client
    if _client is None:
        if not supabase_configured():
            raise DBError(
                "SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY are not set (or are "
                "still placeholders). Copy .env.example to .env and fill them "
                "in from Supabase > Project Settings > API."
            )
        from supabase import create_client
        _client = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)
    return _client


def content_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


# --- entities ----------------------------------------------------------

def get_or_create_entity(name: str, entity_type: str, metadata: Optional[dict] = None) -> str:
    """Returns the entity id, creating the row if (name, type) is new."""
    client = get_client()
    existing = (client.table("entities").select("id")
                .eq("name", name).eq("type", entity_type).limit(1).execute())
    if existing.data:
        return existing.data[0]["id"]
    inserted = client.table("entities").insert({
        "name": name, "type": entity_type, "metadata": metadata or {},
    }).execute()
    return inserted.data[0]["id"]


def save_entity_relationship(from_entity_id: str, to_entity_id: str,
                             relationship_type: str,
                             evidence_id: Optional[str] = None) -> str:
    client = get_client()
    existing = (client.table("entity_relationships").select("id")
                .eq("from_entity_id", from_entity_id)
                .eq("to_entity_id", to_entity_id)
                .eq("relationship_type", relationship_type)
                .limit(1).execute())
    if existing.data:
        return existing.data[0]["id"]
    inserted = client.table("entity_relationships").insert({
        "from_entity_id": from_entity_id,
        "to_entity_id": to_entity_id,
        "relationship_type": relationship_type,
        "evidence_id": evidence_id,
    }).execute()
    return inserted.data[0]["id"]


def list_entities() -> List[dict]:
    client = get_client()
    return client.table("entities").select("id, name, type").execute().data or []


# --- source documents & evidence ---------------------------------------

def save_source_document(doc_type: str, title: str, url_or_path: Optional[str],
                         text_for_hash: str,
                         published_date: Optional[str] = None,
                         metadata: Optional[dict] = None) -> tuple[str, bool]:
    """
    Returns (source_document_id, created). Dedup by sha256 of the extracted
    text: if a document with the same content_hash exists, its id is
    returned and nothing is inserted.
    """
    client = get_client()
    h = content_hash(text_for_hash)
    existing = (client.table("source_documents").select("id")
                .eq("content_hash", h).limit(1).execute())
    if existing.data:
        return existing.data[0]["id"], False
    inserted = client.table("source_documents").insert({
        "type": doc_type,
        "title": title,
        "url_or_path": url_or_path,
        "published_date": published_date,
        "content_hash": h,
        "metadata": metadata or {},
    }).execute()
    return inserted.data[0]["id"], True


def save_evidence(source_document_id: str, text: str,
                  page_or_timestamp: Optional[str] = None) -> str:
    """Idempotent: re-extracting unchanged content returns the existing
    row's id instead of inserting a duplicate (append-only means facts
    accumulate, not repeat — --reingest runs were duplicating passages)."""
    client = get_client()
    existing = (client.table("evidence").select("id")
                .eq("source_document_id", source_document_id)
                .eq("text", text).limit(1).execute())
    if existing.data:
        return existing.data[0]["id"]
    inserted = client.table("evidence").insert({
        "source_document_id": source_document_id,
        "text": text,
        "page_or_timestamp": page_or_timestamp,
    }).execute()
    return inserted.data[0]["id"]


def get_source_document_by_url(url: str) -> Optional[str]:
    """Most recent source_documents id for a URL, or None. Lets a rerun skip
    the Gemini read entirely for pages already ingested."""
    client = get_client()
    rows = (client.table("source_documents").select("id")
            .eq("url_or_path", url)
            .order("ingested_at", desc=True).limit(1).execute())
    return rows.data[0]["id"] if rows.data else None


def get_source_document_by_fetch_hash(fetch_hash: str) -> Optional[str]:
    """Round 5: reuse lookup by the FETCHED text's hash — BSE rotates
    its Pname=<guid> URLs, so URL-keyed reuse misses and used to force
    full re-extractions of unchanged documents ($0.48 once)."""
    client = get_client()
    rows = (client.table("source_documents").select("id")
            .filter("metadata->>fetch_hash", "eq", fetch_hash)
            .order("ingested_at", desc=True).limit(1).execute())
    return rows.data[0]["id"] if rows.data else None


def get_evidence_for_document(source_document_id: str) -> List[dict]:
    """Existing evidence rows for a document, in insertion order. Used to
    reuse chunks when a rerun re-reads a page whose content hasn't changed."""
    client = get_client()
    rows = (client.table("evidence").select("id, text, page_or_timestamp")
            .eq("source_document_id", source_document_id)
            .order("created_at").execute())
    return rows.data or []


def get_layer_evidence(layer: str, limit: int = 80) -> List[dict]:
    """All stored evidence for a research layer ('macro'/'industry'), joined
    with its document's url/title/doc_class. Used to REHYDRATE a fresh layer
    that was skipped for re-reading — freshness must mean 'don't re-fetch',
    never 'run without the data' (Phase 0.3)."""
    client = get_client()
    docs = (client.table("source_documents")
            .select("id, title, url_or_path, metadata")
            .filter("metadata->>layer", "eq", layer)
            .order("ingested_at", desc=True).limit(40).execute()).data or []
    out: List[dict] = []
    for d in docs:
        doc_class = (d.get("metadata") or {}).get("doc_class", f"{layer}_page")
        rows = (client.table("evidence").select("id, text, page_or_timestamp")
                .eq("source_document_id", d["id"]).order("created_at").execute()).data or []
        for r in rows:
            out.append({"id": r["id"], "text": r["text"],
                        "url": d.get("url_or_path"), "title": d.get("title"),
                        "doc_class": doc_class, "page": r.get("page_or_timestamp")})
            if len(out) >= limit:
                return out
    return out


def link_evidence_entities(evidence_id: str, entity_ids: List[str]) -> None:
    if not entity_ids:
        return
    client = get_client()
    rows = [{"evidence_id": evidence_id, "entity_id": eid} for eid in entity_ids]
    # on_conflict matches the (evidence_id, entity_id) unique constraint
    client.table("entity_mentions").upsert(
        rows, on_conflict="evidence_id,entity_id", ignore_duplicates=True
    ).execute()


def evidence_ids_exist(evidence_ids: List[str]) -> set:
    """Returns the subset of the given ids that actually exist in `evidence`."""
    if not evidence_ids:
        return set()
    client = get_client()
    rows = (client.table("evidence").select("id")
            .in_("id", list(set(evidence_ids))).execute())
    return {r["id"] for r in rows.data or []}


# --- metric observations --------------------------------------------------

def save_metric_observation(entity_id: str, metric_name: str, period_type: str,
                            period_start: str, period_end: str, value: float,
                            unit: Optional[str] = None,
                            source_document_id: Optional[str] = None) -> Optional[str]:
    """Upsert on the (entity, metric, period) unique constraint; returns the
    row id (existing row's id on conflict — observed facts are append-only,
    a re-read of the same print must not duplicate or overwrite)."""
    client = get_client()
    existing = (client.table("metric_observations").select("id")
                .eq("entity_id", entity_id).eq("metric_name", metric_name)
                .eq("period_start", period_start).eq("period_end", period_end)
                .limit(1).execute())
    if existing.data:
        return existing.data[0]["id"]
    inserted = client.table("metric_observations").insert({
        "entity_id": entity_id, "metric_name": metric_name,
        "period_type": period_type, "period_start": period_start,
        "period_end": period_end, "value": value, "unit": unit,
        "source_document_id": source_document_id,
    }).execute()
    return inserted.data[0]["id"]


def bulk_save_metric_observations(rows: List[dict]) -> None:
    """Upsert many observations in chunks against the (entity, metric,
    period) unique constraint. Existing rows are left untouched (observed
    facts are append-only); callers re-fetch to obtain row ids."""
    if not rows:
        return
    client = get_client()
    payload = [{"entity_id": r["entity_id"], "metric_name": r["metric_name"],
                "period_type": r["period_type"], "period_start": r["period_start"],
                "period_end": r["period_end"], "value": r["value"],
                "unit": r.get("unit"),
                "source_document_id": r.get("source_document_id")}
               for r in rows]
    for i in range(0, len(payload), 400):
        client.table("metric_observations").upsert(
            payload[i:i + 400],
            on_conflict="entity_id,metric_name,period_start,period_end",
            ignore_duplicates=True,
        ).execute()


def get_metric_observations(entity_id: str,
                            metric_names: Optional[List[str]] = None) -> List[dict]:
    client = get_client()
    q = (client.table("metric_observations").select("*")
         .eq("entity_id", entity_id).order("period_start"))
    if metric_names:
        q = q.in_("metric_name", metric_names)
    return q.execute().data or []


# --- graph helpers ----------------------------------------------------------

def get_peers(company_entity_id: str) -> List[dict]:
    """Entities with a peer_of edge pointing AT this company."""
    client = get_client()
    rels = (client.table("entity_relationships").select("from_entity_id")
            .eq("to_entity_id", company_entity_id)
            .eq("relationship_type", "peer_of").execute()).data or []
    ids = [r["from_entity_id"] for r in rels]
    if not ids:
        return []
    rows = client.table("entities").select("id, name, metadata").in_("id", ids).execute()
    return rows.data or []


def get_relationships_for(entity_id: str) -> List[dict]:
    """All edges touching an entity, with counterparty names resolved."""
    client = get_client()
    out = (client.table("entity_relationships").select("*")
           .or_(f"from_entity_id.eq.{entity_id},to_entity_id.eq.{entity_id}")
           .execute()).data or []
    ids = {r["from_entity_id"] for r in out} | {r["to_entity_id"] for r in out}
    if not ids:
        return []
    names = {e["id"]: e["name"] for e in
             (client.table("entities").select("id, name").in_("id", list(ids)).execute()).data or []}
    for r in out:
        r["from_name"] = names.get(r["from_entity_id"], "?")
        r["to_name"] = names.get(r["to_entity_id"], "?")
    return out


def update_claim_status(claim_id: str, status: str) -> None:
    client = get_client()
    client.table("claims").update({"verification_status": status}).eq("id", claim_id).execute()


# --- knowledge entries & claims -----------------------------------------

def _next_version(client, table: str, filters: dict) -> int:
    query = client.table(table).select("version")
    for col, val in filters.items():
        query = query.eq(col, val)
    rows = query.order("version", desc=True).limit(1).execute()
    return (rows.data[0]["version"] + 1) if rows.data else 1


def save_knowledge_entry(layer: str, entity_id: str, section: str,
                         content_json: dict,
                         based_on_versions_json: Optional[dict] = None,
                         generated_by_run_id: Optional[str] = None) -> str:
    client = get_client()
    version = _next_version(client, "knowledge_entries",
                            {"layer": layer, "entity_id": entity_id, "section": section})
    inserted = client.table("knowledge_entries").insert({
        "layer": layer,
        "entity_id": entity_id,
        "section": section,
        "version": version,
        "content_json": content_json,
        "based_on_versions_json": based_on_versions_json or {},
        "generated_by_run_id": generated_by_run_id,
    }).execute()
    return inserted.data[0]["id"]


def get_latest(layer: str, entity_id: str, section: str) -> Optional[dict]:
    """Most recent knowledge entry for (layer, entity, section), or None."""
    client = get_client()
    rows = (client.table("knowledge_entries").select("*")
            .eq("layer", layer).eq("entity_id", entity_id).eq("section", section)
            .order("version", desc=True).limit(1).execute())
    return rows.data[0] if rows.data else None


def save_claims(knowledge_entry_id: str, claims: List[dict],
                strict: bool = True) -> List[str]:
    """
    claims: [{"text": ..., "evidence_ids": [...], "confidence": ...}, ...]

    THE citation-integrity check (FOUNDATIONS.md §2/§3): Postgres cannot enforce
    FKs on uuid[] elements, so before persisting we verify every referenced
    evidence UUID resolves to a real evidence row. strict=True raises on any
    dangling id; strict=False persists the offending claims with
    verification_status='failed' instead, so the failure is visible in-band.
    """
    client = get_client()
    all_ids = [eid for c in claims for eid in c.get("evidence_ids", [])]
    valid = evidence_ids_exist(all_ids)

    rows, bad_claims = [], []
    for c in claims:
        dangling = [eid for eid in c.get("evidence_ids", []) if eid not in valid]
        if dangling:
            bad_claims.append((c["text"], dangling))
        rows.append({
            "knowledge_entry_id": knowledge_entry_id,
            "text": c["text"],
            "evidence_ids": c.get("evidence_ids", []),
            "confidence": c.get("confidence"),
            "verification_status": "failed" if dangling else "pending",
        })

    if bad_claims and strict:
        detail = "; ".join(f"claim '{t[:80]}...' cites missing evidence {d}"
                           for t, d in bad_claims)
        raise CitationIntegrityError(
            f"{len(bad_claims)} claim(s) reference evidence rows that do not "
            f"exist — refusing to persist. {detail}"
        )

    inserted = client.table("claims").insert(rows).execute()
    if bad_claims:
        print(f"  [db] WARNING: {len(bad_claims)} claim(s) persisted with "
              f"verification_status='failed' (dangling evidence ids)")
    return [r["id"] for r in inserted.data]


# --- report versions -----------------------------------------------------

def save_report_version(company_id: str, sections_json: dict,
                        based_on_macro_version: Optional[int] = None,
                        based_on_industry_version: Optional[int] = None,
                        based_on_company_version: Optional[int] = None) -> tuple[str, int]:
    client = get_client()
    version = _next_version(client, "report_versions", {"company_id": company_id})
    inserted = client.table("report_versions").insert({
        "company_id": company_id,
        "version": version,
        "sections_json": sections_json,
        "based_on_macro_version": based_on_macro_version,
        "based_on_industry_version": based_on_industry_version,
        "based_on_company_version": based_on_company_version,
    }).execute()
    return inserted.data[0]["id"], version


# --- runs (observability) -------------------------------------------------

def start_run(workflow_name: str, entity_id: Optional[str] = None) -> str:
    client = get_client()
    inserted = client.table("runs").insert({
        "workflow_name": workflow_name,
        "entity_id": entity_id,
        "status": "running",
    }).execute()
    return inserted.data[0]["id"]


def finish_run(run_id: str, status: str, model_used: Optional[str] = None,
               tokens_input: Optional[int] = None, tokens_output: Optional[int] = None,
               cost_usd: Optional[float] = None, error_message: Optional[str] = None) -> None:
    client = get_client()
    client.table("runs").update({
        "finished_at": "now()",
        "status": status,
        "model_used": model_used,
        "tokens_input": tokens_input,
        "tokens_output": tokens_output,
        "cost_usd": cost_usd,
        "error_message": error_message,
    }).eq("id", run_id).execute()
