"""
Round 3 — the sector-scoped numeric backbone.

The registry (pack["members"], data/sector_packs/*.json) lists every
member stock of a sector; the peer set = members minus the run company
(peer_of edges still decide who joins the peer TABLE — TMCV parses but
does not join, exactly as before). refresh_backbone() does the
deterministic zero-LLM work ONCE per sector per TTL window — screener
parse + Yahoo price series (13 monthly closes + 10y FY-end closes) per
member — and stores one knowledge entry per member
(section backbone:{slug}, layer 'industry', on the sector entity) plus
a backbone_stamp freshness marker. A stock run with a fresh backbone
REHYDRATES in s2 instead of re-fetching; a stale backbone is refreshed
INLINE so one command still produces a report. member_of edges (stock →
sector entity) are ensured at refresh. Per-member failures degrade to a
thin peer row, never abort — and if the RUN COMPANY itself is missing
from the backbone, s1 falls back to the classic per-run screener reads.
"""

import json
from datetime import datetime, timezone, timedelta

from src import db
from src.config import SECTOR_BACKBONE_FRESH_DAYS


def _member_tokens(name: str) -> list:
    """Identity-validation tokens for the Yahoo longName check."""
    return [w for w in name.lower().split() if len(w) >= 4] or [name.lower()]


def backbone_fresh(sector_entity_id: str) -> bool:
    row = db.get_latest("industry", sector_entity_id, "backbone_stamp")
    if not row:
        return False
    created = datetime.fromisoformat(row["created_at"].replace("Z", "+00:00"))
    return datetime.now(timezone.utc) - created < \
        timedelta(days=SECTOR_BACKBONE_FRESH_DAYS)


def load_backbone(sector_entity_id: str, members: list) -> dict:
    """Latest stored backbone entry per member; missing members simply
    absent from the result (caller decides whether that forces refresh)."""
    out = {}
    for m in members:
        row = db.get_latest("industry", sector_entity_id,
                            f"backbone:{m['screener_slug']}")
        if row:
            out[m["screener_slug"]] = row["content_json"]
    return out


def refresh_backbone(sector_entity_id: str, pack: dict,
                     run_id: str | None = None) -> dict:
    """Fetch + parse + store the numeric backbone for every member.
    Zero LLM. Returns {slug: content} for the members that succeeded."""
    from src.ingestion.screener_parser import parse_company_page
    from src.ingestion.fetcher import fetch_price_history

    members = pack.get("members") or []
    out, ok_slugs = {}, []
    for m in members:
        slug, name, ticker = m["screener_slug"], m["name"], m.get("ticker", "")
        url = f"https://www.screener.in/company/{slug}/consolidated/"
        try:
            parsed = parse_company_page(url)
        except Exception as e:
            print(f"  [sector] backbone parse failed for {slug}: {e} — "
                  f"member skipped (thin peer row this window)")
            continue
        # hash only the periodic tables (not the daily-moving top card) so
        # the source_documents row stays stable between result seasons —
        # same convention as the in-run parser path
        stable = [c for c in parsed["candidates"] if not c.get("period_parsed")]
        doc_id, _ = db.save_source_document(
            doc_type="other", title=f"screener:{slug}", url_or_path=url,
            text_for_hash=json.dumps(stable, sort_keys=True),
            metadata={"doc_class": "screener_page", "layer": "company",
                      "ticker": ticker, "sector_backbone": True})
        about_ev_id = db.save_evidence(doc_id, parsed["about"]) \
            if parsed.get("about") else None

        # price series (both zero-LLM, identity-validated; optional —
        # a failed/mismatched Yahoo resolution degrades, never aborts)
        closes_1y, closes_fy, price_urls, price_doc_ids, long_name = \
            [], [], {}, {}, ""
        if ticker:
            tokens = _member_tokens(name)
            try:
                pts, purl, long_name = fetch_price_history(ticker, tokens)
                closes_1y = [list(p) for p in pts]
                price_urls["1y"] = purl
                pdoc, _ = db.save_source_document(
                    doc_type="other", title=f"Price history 1y ({long_name})",
                    url_or_path=purl, text_for_hash=json.dumps(closes_1y),
                    metadata={"doc_class": "price_history", "layer": "company",
                              "ticker": ticker})
                price_doc_ids["1y"] = pdoc
            except Exception as e:
                print(f"  [sector] 1y prices unavailable for {slug}: {e}")
            try:
                pts10, purl10, ln10 = fetch_price_history(
                    ticker, _member_tokens(name), range_="10y", interval="1mo")
                closes_fy = [list(p) for p in pts10
                             if str(p[0]).startswith("Mar ")]
                if closes_fy:
                    price_urls["10y"] = purl10
                    pdoc10, _ = db.save_source_document(
                        doc_type="other",
                        title=f"Price history 10y FY-end closes ({ln10})",
                        url_or_path=purl10 + "#range=10y",
                        text_for_hash=json.dumps(closes_fy),
                        metadata={"doc_class": "price_history",
                                  "layer": "company", "ticker": ticker})
                    price_doc_ids["10y"] = pdoc10
            except Exception as e:
                print(f"  [sector] 10y prices unavailable for {slug}: {e}")

        content = {
            "name": name, "ticker": ticker, "screener_slug": slug, "url": url,
            "candidates": parsed["candidates"], "about": parsed.get("about"),
            "about_ev_id": about_ev_id, "doc_id": doc_id,
            "doc_links": parsed.get("doc_links") or {},
            "closes_1y": closes_1y, "closes_fy": closes_fy,
            "price_urls": price_urls, "price_doc_ids": price_doc_ids,
            "long_name": long_name,
        }
        db.save_knowledge_entry("industry", sector_entity_id,
                                f"backbone:{slug}", content,
                                generated_by_run_id=run_id)
        # registry mirrored into the entity graph (schema-frozen: text value)
        eid = db.get_or_create_entity(name, "company",
                                      metadata={"ticker": ticker})
        db.save_entity_relationship(eid, sector_entity_id, "member_of")
        out[slug] = content
        ok_slugs.append(slug)
        print(f"  [sector] backbone refreshed: {slug} "
              f"({len(parsed['candidates'])} candidates"
              + (f", {len(closes_1y)}+{len(closes_fy)} closes" if ticker else "")
              + ")")

    if ok_slugs:
        db.save_knowledge_entry("industry", sector_entity_id, "backbone_stamp",
                                {"refreshed_at":
                                 datetime.now(timezone.utc).isoformat(),
                                 "members": ok_slugs},
                                generated_by_run_id=run_id)
    return out


def ensure_backbone(sector_entity_id: str, pack: dict,
                    run_id: str | None = None, force: bool = False) -> dict | None:
    """The single entry point: fresh → load; stale/forced/incomplete →
    refresh inline. Returns {"members": {slug: content}} or None when
    the sector has no registry or nothing could be served."""
    members = pack.get("members") or []
    if not (sector_entity_id and members):
        return None
    slugs = {m["screener_slug"] for m in members}
    if not force and backbone_fresh(sector_entity_id):
        loaded = load_backbone(sector_entity_id, members)
        if slugs <= set(loaded):
            print(f"  [sector] backbone fresh — {len(loaded)} members "
                  f"rehydrated, no screener/price fetches")
            return {"members": loaded}
        print("  [sector] backbone stamp fresh but entries incomplete — "
              "refreshing")
    refreshed = refresh_backbone(sector_entity_id, pack, run_id)
    return {"members": refreshed} if refreshed else None
