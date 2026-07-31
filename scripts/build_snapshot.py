"""
Builds the index snapshot the frontend list page renders.

    .venv\\Scripts\\python.exe scripts/build_snapshot.py --dry-run
    .venv\\Scripts\\python.exe scripts/build_snapshot.py

Reads Supabase, emits ONE `IndexSnapshot` JSON document covering every
registry constituent — market cap, report status, freshness, quality —
and stores it so the next run can tell whether anything changed. The
payload shape is fixed by `ui_bridge/SHARED_CONTRACT.md` §5; change it
there first, not here.

**Firestore transport is deliberately NOT in this script.** It needs a
service account and answers to `PIPELINE_ANSWERS.md` "what we need from
you"; the builder is useful and fully testable without it, and emits
the exact bytes that will later be uploaded.

Version discipline: `snapshotVersion` must increment ONLY when content
actually changed, because an unchanged rewrite busts every cached copy
for nothing. The previous payload is kept in `knowledge_entries` (whose
per-section version counter IS the snapshotVersion), so the check
survives an ephemeral Cloud Run filesystem.

Exit codes: 0 ok · 1 no market data · 2 refused to run.
"""

import argparse
import datetime
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
DEFAULT_OUT = os.path.join(ROOT, "data", "snapshots", "nifty_midcap_150.json")

REGISTRY_VERSION = "2026.07"        # bump ONLY on index rebalance (contract §3)
SNAPSHOT_SECTION = "index_snapshot"
FRESH_DAYS = 7                      # newer than this => "updated", else "stale"
MARKET_DATE_LOOKBACK = 14           # days of day-rows to consider
MIN_DATE_COVERAGE = 0.5             # a real market date covers >=50% of the index


def _page(query_fn, size: int = 1000) -> list:
    """PostgREST caps unbounded selects at 1,000 rows (DB_SCHEMA
    invariant 9) — page everything that must be complete."""
    out, off = [], 0
    while True:
        batch = query_fn(off, off + size - 1).execute().data or []
        out += batch
        if len(batch) < size:
            return out
        off += size


def _market_data(client, entity_ids: set) -> tuple:
    """(market_date, {entity_id: market_cap_cr}).

    The market date is NOT simply "the newest day row": the research
    pipeline also writes day-typed market_cap stamped with its own
    scrape date (HANDOFF4 §6.7), so a single stray row could masquerade
    as a trading day. The daily job writes ~150 rows at once, so we take
    the newest date whose coverage clears MIN_DATE_COVERAGE — which also
    skips holidays for free."""
    since = (datetime.date.today()
             - datetime.timedelta(days=MARKET_DATE_LOOKBACK)).isoformat()
    rows = _page(lambda a, b: client.table("metric_observations")
                 .select("entity_id, value, period_start")
                 .eq("metric_name", "market_cap").eq("period_type", "day")
                 .gte("period_start", since)
                 .order("period_start").order("id").range(a, b))
    by_date: dict = {}
    for r in rows:
        if r["entity_id"] in entity_ids:
            by_date.setdefault(r["period_start"], {})[r["entity_id"]] = r["value"]
    if not by_date:
        return None, {}
    need = max(1, int(len(entity_ids) * MIN_DATE_COVERAGE))
    good = [d for d, caps in by_date.items() if len(caps) >= need]
    if not good:
        # nothing with real coverage — fall back to the newest, and say so
        newest = max(by_date)
        print(f"  [snapshot][warn] no date covers >={need} companies; using "
              f"{newest} with only {len(by_date[newest])}")
        return newest, by_date[newest]
    best = max(good)
    return best, by_date[best]


def _latest_reports(client, entity_ids: set) -> dict:
    """{entity_id: {version, generated_at, quality, has_open_flags}}.

    Two-step on purpose: `sections_json` is ~430 KB per report, so the
    index is fetched WITHOUT it and only the winning rows are hydrated.
    At 150 covered companies a naive select would drag ~64 MB per run."""
    index = _page(lambda a, b: client.table("report_versions")
                  .select("id, company_id, version, generated_at")
                  .order("generated_at").order("id").range(a, b))
    latest: dict = {}
    for r in index:
        if r["company_id"] not in entity_ids:
            continue
        cur = latest.get(r["company_id"])
        if cur is None or (r["version"] or 0) > (cur["version"] or 0):
            latest[r["company_id"]] = r
    if not latest:
        return {}

    ids = [r["id"] for r in latest.values()]
    hydrated: dict = {}
    for i in range(0, len(ids), 20):        # keep the URL short
        for row in (client.table("report_versions")
                    .select("id, sections_json")
                    .in_("id", ids[i:i + 20]).execute().data or []):
            hydrated[row["id"]] = row.get("sections_json") or {}

    out = {}
    for eid, r in latest.items():
        sj = hydrated.get(r["id"], {})
        flags = False
        for key, val in sj.items():
            if not key.startswith("section_") or not isinstance(val, dict):
                continue
            for b in val.get("blocks") or []:
                if isinstance(b, dict) and b.get("type") == "flag" \
                        and b.get("status") == "FLAG":
                    flags = True
                    break
            if flags:
                break
        out[eid] = {"version": r["version"], "generated_at": r["generated_at"],
                    "quality": sj.get("quality"), "has_open_flags": flags}
    return out


def _running(client, entity_ids: set) -> set:
    rows = (client.table("runs").select("entity_id")
            .eq("status", "running").limit(200).execute().data or [])
    return {r["entity_id"] for r in rows if r["entity_id"] in entity_ids}


def _status(report: dict | None, is_running: bool) -> str:
    if is_running:
        return "updating"
    if not report or not report.get("generated_at"):
        return "not_initiated"
    gen = datetime.datetime.fromisoformat(
        report["generated_at"].replace("Z", "+00:00"))
    age = datetime.datetime.now(datetime.timezone.utc) - gen
    return "updated" if age.days < FRESH_DAYS else "stale"


def main() -> int:
    ap = argparse.ArgumentParser(description="Build the index snapshot")
    ap.add_argument("--universe", default=DEFAULT_UNIVERSE)
    ap.add_argument("--out", default=DEFAULT_OUT)
    ap.add_argument("--dry-run", action="store_true",
                    help="write the file, but do not store/version it")
    args = ap.parse_args()

    with open(args.universe, encoding="utf-8") as f:
        uni = json.load(f)
    companies = uni["companies"]
    client = get_client()

    ents = _page(lambda a, b: client.table("entities")
                 .select("id, metadata").eq("type", "company")
                 .order("id").range(a, b))
    by_ticker = {(e.get("metadata") or {}).get("ticker"): e["id"]
                 for e in ents if (e.get("metadata") or {}).get("ticker")}
    ids = {by_ticker[c["ticker"]] for c in companies if c["ticker"] in by_ticker}
    missing = [c["ticker"] for c in companies if c["ticker"] not in by_ticker]
    if missing:
        print(f"  [snapshot][warn] {len(missing)} ticker(s) have no entity — "
              f"run scripts/seed_universe.py: {missing[:8]}")

    market_date, caps = _market_data(client, ids)
    if not market_date:
        print("[snapshot] FATAL: no market_cap day rows found — run "
              "scripts/daily_market_data.py first")
        return 1
    reports = _latest_reports(client, ids)
    running = _running(client, ids)

    dynamics = []
    for c in companies:
        eid = by_ticker.get(c["ticker"])
        rep = reports.get(eid)
        cap = caps.get(eid)
        dynamics.append({
            "ticker": c["ticker"],
            # null, NEVER 0 — a zero renders as a real market cap
            "marketCapCr": round(cap, 2) if cap is not None else None,
            "status": _status(rep, eid in running),
            "lastUpdatedISO": rep["generated_at"] if rep else None,
            "latestVersion": rep["version"] if rep else None,
            "quality": rep["quality"] if rep else None,
            "hasOpenFlags": bool(rep["has_open_flags"]) if rep else False,
            # locked until the compliance review — contract §7
            "verdict": {"status": "coming_soon", "version": 0},
        })

    payload = {"manifest": {"registryVersion": REGISTRY_VERSION,
                            "snapshotVersion": 1,
                            "marketDataDate": market_date,
                            "verdictEpoch": 0},
               "dynamics": dynamics}

    # --- version discipline: bump ONLY on real change
    # type='other', not 'index': entities.type carries a CHECK constraint
    # (company/sector/commodity/policy/person/macro_factor/geography/other)
    # — DB_SCHEMA invariant 8's "new entities.type values" escape hatch is
    # NOT actually open. 'other' is the sanctioned catch-all.
    index_entity = db.get_or_create_entity(
        uni.get("index", "NIFTY Midcap 150"), "other",
        metadata={"registry_version": REGISTRY_VERSION, "kind": "index"})
    prev = db.get_latest("macro", index_entity, SNAPSHOT_SECTION)
    prev_payload = (prev or {}).get("content_json") or {}
    prev_version = ((prev_payload.get("manifest") or {})
                    .get("snapshotVersion")) or 0

    def _comparable(p):
        q = json.loads(json.dumps(p))
        q.get("manifest", {}).pop("snapshotVersion", None)
        return q

    changed = _comparable(payload) != _comparable(prev_payload)
    payload["manifest"]["snapshotVersion"] = \
        (prev_version + 1) if changed else prev_version or 1

    body = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        f.write(body)

    if changed and not args.dry_run:
        db.save_knowledge_entry("macro", index_entity, SNAPSHOT_SECTION, payload)

    counts: dict = {}
    for d in dynamics:
        counts[d["status"]] = counts.get(d["status"], 0) + 1
    covered = sum(1 for d in dynamics if d["marketCapCr"] is not None)
    print(f"[snapshot] {market_date} · registry {REGISTRY_VERSION} · "
          f"v{payload['manifest']['snapshotVersion']}"
          + ("" if changed else " (unchanged — version held)")
          + f" · {len(dynamics)} companies, {covered} with market cap · "
          + ", ".join(f"{v} {k}" for k, v in sorted(counts.items()))
          + f" · {len(body) / 1024:.1f} KB -> {os.path.relpath(args.out, ROOT)}"
          + (" [DRY RUN — not stored]" if args.dry_run else ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
