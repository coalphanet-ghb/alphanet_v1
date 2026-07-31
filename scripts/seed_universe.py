"""
Seeds one company entity per index constituent from a universe registry
(data/universe/*.json). Idempotent — safe to re-run.

TICKER-FIRST resolution, and that is the whole point of this script.
`db.get_or_create_entity` dedups on (name, type), but the NSE
constituent list and the hand-seeded entities disagree on names —
'Bharat Forge Ltd.' vs 'Bharat Forge', 'UNO Minda Ltd.' vs 'Uno Minda'
(6 such cases measured 2026-07-26). Seeding by name would create
duplicate entities and silently split those companies' observations.
So: resolve by metadata.ticker, then by exact name, and only then
create. An existing entity is never renamed; its metadata is enriched,
never overwritten.

Usage (from the repo root, with .env filled in):
    .venv\\Scripts\\python.exe scripts/seed_universe.py --dry-run
    .venv\\Scripts\\python.exe scripts/seed_universe.py
"""

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(errors="replace")     # cp1252 guard (HANDOFF3 §4)
    except Exception:
        pass

from src import db  # noqa: E402
from src.db import get_client  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_UNIVERSE = os.path.join(ROOT, "data", "universe", "nifty_midcap150.json")

_META_KEYS = ("ticker", "screener_slug", "isin", "nse_industry")


def _wanted_metadata(c: dict) -> dict:
    return {k: c[k] for k in _META_KEYS if c.get(k)}


def main() -> int:
    ap = argparse.ArgumentParser(description="Seed index-constituent entities")
    ap.add_argument("--universe", default=DEFAULT_UNIVERSE)
    ap.add_argument("--dry-run", action="store_true",
                    help="resolve and report, write nothing")
    args = ap.parse_args()

    with open(args.universe, encoding="utf-8") as f:
        uni = json.load(f)
    companies = uni["companies"]
    print(f"universe: {uni.get('index')} — {len(companies)} companies "
          f"({os.path.relpath(args.universe, ROOT)})")

    client = get_client()
    before = client.table("entities").select("id", count="exact") \
        .eq("type", "company").execute().count

    by_ticker, by_name, created, enriched = [], [], [], []
    for c in companies:
        ticker, name = c["ticker"], c["name"]
        hit = db.get_entity_by_ticker(ticker)
        how = "ticker"
        if not hit:
            rows = (client.table("entities").select("id, name, metadata")
                    .eq("type", "company").eq("name", name)
                    .limit(1).execute()).data
            hit = rows[0] if rows else None
            how = "name"

        if hit:
            (by_ticker if how == "ticker" else by_name).append((ticker, hit["name"]))
            # enrich metadata only where a key is MISSING; never overwrite,
            # never rename the entity
            meta = dict(hit.get("metadata") or {})
            add = {k: v for k, v in _wanted_metadata(c).items() if not meta.get(k)}
            if add and not args.dry_run:
                meta.update(add)
                client.table("entities").update({"metadata": meta}) \
                    .eq("id", hit["id"]).execute()
            if add:
                enriched.append((ticker, sorted(add)))
            continue

        if not args.dry_run:
            db.get_or_create_entity(name, "company", _wanted_metadata(c))
        created.append((ticker, name))

    print(f"\n  resolved by ticker : {len(by_ticker)}")
    for t, n in by_ticker:
        print(f"      {t:<12} -> existing entity {n!r}")
    if by_name:
        print(f"  resolved by name   : {len(by_name)}")
        for t, n in by_name:
            print(f"      {t:<12} -> existing entity {n!r}")
    if enriched:
        print(f"  metadata enriched  : {len(enriched)} "
              f"(e.g. {enriched[0][0]} += {enriched[0][1]})")
    print(f"  created            : {len(created)}"
          + ("  [DRY RUN — nothing written]" if args.dry_run else ""))

    if args.dry_run:
        print(f"\nDRY RUN: company entities would go {before} -> "
              f"{before + len(created)}")
        return 0

    after = client.table("entities").select("id", count="exact") \
        .eq("type", "company").execute().count
    print(f"\n  company entities: {before} -> {after}")

    # GATE: ticker is the join key across this repo, the universe registry
    # and the frontend — a duplicate would split a company's observations.
    rows, off = [], 0
    while True:
        b = (client.table("entities").select("name, metadata")
             .eq("type", "company").order("id")
             .range(off, off + 999).execute()).data
        rows += b
        if len(b) < 1000:
            break
        off += 1000
    seen: dict = {}
    for r in rows:
        t = (r.get("metadata") or {}).get("ticker")
        if t:
            seen.setdefault(t, []).append(r["name"])
    dupes = {t: n for t, n in seen.items() if len(n) > 1}
    missing = [c["ticker"] for c in companies if c["ticker"] not in seen]

    if dupes:
        print(f"\n  FAIL: {len(dupes)} duplicated ticker(s): {dupes}")
        return 1
    if missing:
        print(f"\n  FAIL: {len(missing)} universe ticker(s) unresolved: {missing[:10]}")
        return 1
    print(f"  GATE PASS: {len(seen)} distinct tickers, zero duplicates, "
          f"all {len(companies)} universe tickers resolve")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
