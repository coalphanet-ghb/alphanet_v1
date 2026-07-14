"""
S0 — run planning (deterministic, zero LLM). Spec: nodes/s0_resolve.
Builds the company profile, loads the pack, resolves peer set and
freshness, and emits the read plan skeleton that s1 executes.
"""

from datetime import datetime, timezone, timedelta

from src import db
from src.packs import load_pack
from src.config import CONCALL_QUARTERS, MACRO_FRESH_DAYS, SECTOR_FRESH_DAYS


def _current_fiscal_quarters(n: int) -> list[dict]:
    """Last n completed Indian fiscal quarters, latest first.
    FY runs Apr-Mar; FY26 = Apr 2025 - Mar 2026."""
    now = datetime.now(timezone.utc)
    y, m = now.year, now.month
    # fiscal quarter containing 'now'
    fq = (m - 4) % 12 // 3 + 1          # 1..4
    fy = y + 1 if m >= 4 else y          # FY label year (ending year)
    # step back one: we want COMPLETED quarters
    out = []
    q, yy = fq, fy
    for _ in range(n):
        q -= 1
        if q == 0:
            q, yy = 4, yy - 1
        out.append({"q": f"Q{q}", "fy": f"FY{yy % 100}"})
    return out


def _layer_fresh(section: str, entity_id: str, days: int) -> bool:
    row = db.get_latest("macro" if section == "macro" else "industry",
                        entity_id, "layer_evidence")
    if not row:
        return False
    created = datetime.fromisoformat(row["created_at"].replace("Z", "+00:00"))
    return datetime.now(timezone.utc) - created < timedelta(days=days)


def resolve_node(state) -> dict:
    profile = dict(state["profile"])
    pack = load_pack(profile["pack_id"])

    if state.get("dry_run") or not state.get("persist"):
        profile["entity_id"] = "company_local"
        return {"profile": profile, "pack": pack, "peer_entities": [],
                "read_plan": {"quarters": _current_fiscal_quarters(CONCALL_QUARTERS),
                              "macro_fresh": False, "sector_fresh": False}}

    company_id = db.get_or_create_entity(profile["name"], "company",
                                         metadata={"ticker": profile["ticker"]})
    profile["entity_id"] = company_id

    peers = db.get_peers(company_id)
    if not peers:
        print("  [s0] WARNING: no peer_of edges for this company — peer table will be thin; "
              "seed peers in data/seed_entities.json")

    sector_entity = None
    for rel in db.get_relationships_for(company_id):
        if rel["relationship_type"] == "belongs_to_sector" and rel["from_entity_id"] == company_id:
            sector_entity = rel["to_entity_id"]
    india = db.get_or_create_entity("India", "geography")

    read_plan = {
        "quarters": _current_fiscal_quarters(CONCALL_QUARTERS),
        "macro_fresh": _layer_fresh("macro", india, MACRO_FRESH_DAYS),
        "sector_fresh": (_layer_fresh("industry", sector_entity, SECTOR_FRESH_DAYS)
                         if sector_entity else False),
        "sector_entity_id": sector_entity,
        "india_entity_id": india,
    }
    if read_plan["macro_fresh"]:
        print("  [s0] macro layer fresh — skipping macro reads")
    if read_plan["sector_fresh"]:
        print("  [s0] sector layer fresh — skipping sector reads")

    print(f"[s0_resolve] pack={pack['pack_id']} peers={len(peers)} "
          f"quarters={[q['q']+q['fy'] for q in read_plan['quarters']]}")
    return {"profile": profile, "pack": pack, "peer_entities": peers,
            "read_plan": read_plan}
