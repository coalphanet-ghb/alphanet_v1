"""
Sector pack registry loader (data/sector_packs/*.json).

A pack is ALL the sector-specific behavior in the system. Consumers:
s0 (macro commodity subset), s1 (sector queries), s3 (skip modules,
sector KPIs), the prompt assembler (overlay slots), s8 composer
(snapshot vitals, peer columns). See data/sector_packs/_SCHEMA.md.
"""

import json
import os
from functools import lru_cache

from src.config import PACKS_DIR

OVERLAY_SLOTS = [
    "business_model", "financials", "supply_chain", "governance",
    "peers", "risks", "industry", "valuation", "takeaways",
]


class PackError(RuntimeError):
    pass


@lru_cache(maxsize=None)
def load_pack(pack_id: str) -> dict:
    path = os.path.join(PACKS_DIR, f"{pack_id}.json")
    if not os.path.exists(path):
        raise PackError(f"Sector pack '{pack_id}' not found at {path}")
    with open(path, encoding="utf-8") as f:
        pack = json.load(f)
    for field in ("pack_id", "snapshot_vitals", "sector_queries", "compute",
                  "valuation", "overlays"):
        if field not in pack:
            raise PackError(f"Pack '{pack_id}' missing required field '{field}'")
    return pack


def overlay(pack: dict, slot: str) -> str:
    """Overlay prose for a [[SECTOR_OVERLAY:<slot>]] slot, with the pack's
    classic-mistakes guardrails appended to every synthesis slot."""
    text = pack.get("overlays", {}).get(slot, "")
    mistakes = pack.get("classic_mistakes", [])
    if mistakes:
        text += "\n\nSector-classic analytical mistakes you must NOT make:\n" + \
                "\n".join(f"- {m}" for m in mistakes)
    return text.strip()


def kpi_norms_text(pack: dict) -> str:
    """Sector KPI norms rendered for prompts (context, never company data)."""
    lines = []
    for k in pack.get("compute", {}).get("sector_kpis", []):
        norm = []
        if k.get("norm_healthy"):
            norm.append(f"healthy: {k['norm_healthy']}")
        if k.get("norm_warning"):
            norm.append(f"warning: {k['norm_warning']}")
        lines.append(f"- {k['label']}" + (f" ({'; '.join(norm)})" if norm else ""))
    return "\n".join(lines)
