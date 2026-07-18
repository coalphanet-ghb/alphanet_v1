"""
Golden-set regression tool (Phase 6, HANDOFF2 §5 / old HANDOFF §8.7).

Freeze a trusted report as the golden baseline, then diff any later run
against it — section-level block/claim/citation fingerprints, so quality
drift after a prompt/model change is visible BEFORE a user catches it.

Usage:
    python scripts/diff_golden.py --freeze SONACOMS   # latest report -> golden
    python scripts/diff_golden.py SONACOMS            # diff latest vs golden
    python scripts/diff_golden.py --list              # show frozen goldens

Rerun + diff after EVERY prompt/model/pack change.
"""

import argparse
import json
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(errors="replace")

from src.config import COMPANIES                      # noqa: E402
from src.db import get_client                         # noqa: E402

GOLDEN_DIR = os.path.join("data", "golden")

_SECTIONS = ["B", "C", "D", "D1", "D2", "D3", "E", "F", "G", "H", "I", "J"]


def _entity_id(ticker: str) -> str:
    company = next((c for c in COMPANIES
                    if c["ticker"].lower() == ticker.lower()), None)
    if not company:
        sys.exit(f"Unknown ticker '{ticker}' — not in config.COMPANIES")
    rows = (get_client().table("entities").select("id")
            .eq("name", company["name"]).limit(1).execute().data)
    if not rows:
        sys.exit(f"No entity row for '{company['name']}' — run the pipeline first")
    return rows[0]["id"]


def _latest_report(entity_id: str) -> dict:
    rows = (get_client().table("report_versions")
            .select("id, version, sections_json, generated_at")
            .eq("company_id", entity_id)
            .order("version", desc=True).limit(1).execute().data)
    if not rows:
        sys.exit("No report_versions rows for this entity yet")
    return rows[0]


def fingerprint(sections_json: dict) -> dict:
    """The comparable shape of a report: per-section block-type counts,
    claim/insufficiency counts, plus the composer's quality stats."""
    fp = {"sections": {}, "quality": sections_json.get("quality") or {},
          "claim_checks": len(sections_json.get("claim_checks") or [])}
    for letter in _SECTIONS:
        env = sections_json.get(f"section_{letter}")
        if not env:
            fp["sections"][letter] = None
            continue
        by_type: dict = {}
        for b in env.get("blocks", []):
            by_type[b.get("type", "?")] = by_type.get(b.get("type", "?"), 0) + 1
        fp["sections"][letter] = {
            "blocks": by_type,
            "claims": len(env.get("claims") or []),
            "insufficiencies": len(env.get("insufficiencies") or []),
        }
    return fp


def freeze(ticker: str) -> None:
    report = _latest_report(_entity_id(ticker))
    os.makedirs(GOLDEN_DIR, exist_ok=True)
    path = os.path.join(GOLDEN_DIR, f"{ticker.upper().replace('&', '_')}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump({
            "ticker": ticker.upper(),
            "report_version_id": report["id"],
            "version": report["version"],
            "frozen_at": datetime.now(timezone.utc).isoformat(),
            "fingerprint": fingerprint(report["sections_json"]),
        }, f, indent=2, sort_keys=True)
    q = (report["sections_json"].get("quality") or {})
    print(f"FROZEN {ticker.upper()} golden = report v{report['version']} "
          f"({q.get('total', '?')} citations, "
          f"{q.get('unresolved', '?')} unresolved) -> {path}")


def diff(ticker: str) -> int:
    path = os.path.join(GOLDEN_DIR, f"{ticker.upper().replace('&', '_')}.json")
    if not os.path.exists(path):
        sys.exit(f"No golden frozen for {ticker} — run --freeze first")
    with open(path, encoding="utf-8") as f:
        golden = json.load(f)
    latest = _latest_report(_entity_id(ticker))
    if latest["version"] == golden["version"]:
        print(f"Latest report IS the golden (v{golden['version']}) — nothing to diff")
        return 0
    g_fp, l_fp = golden["fingerprint"], fingerprint(latest["sections_json"])

    print(f"{ticker.upper()}: golden v{golden['version']} vs latest v{latest['version']}\n")
    print(f"{'sec':4} {'blocks g->l':>14} {'claims g->l':>13} "
          f"{'insuff g->l':>13}  flags")
    regressions = 0
    for letter in _SECTIONS:
        g, l = g_fp["sections"].get(letter), l_fp["sections"].get(letter)
        if g is None and l is None:
            continue
        if l is None:
            print(f"{letter:4} {'-':>14} {'-':>13} {'-':>13}  SECTION MISSING")
            regressions += 1
            continue
        gb = sum((g or {}).get("blocks", {}).values()) if g else 0
        lb = sum(l["blocks"].values())
        gc = (g or {}).get("claims", 0)
        gi = (g or {}).get("insufficiencies", 0)
        flags = []
        if g and lb < gb * 0.5:
            flags.append("BLOCKS -50%")
        if g and gc and l["claims"] < gc * 0.5:
            flags.append("CLAIMS -50%")
        if flags:
            regressions += 1
        print(f"{letter:4} {f'{gb} -> {lb}':>14} "
              f"{f'{gc} -> {l['claims']}':>13} "
              f"{f'{gi} -> {l['insufficiencies']}':>13}  {' '.join(flags)}")

    gq, lq = g_fp.get("quality") or {}, l_fp.get("quality") or {}

    def unresolved_pct(q):
        t = q.get("total") or 0
        return round(100 * (q.get("unresolved") or 0) / t, 1) if t else None

    gu, lu = unresolved_pct(gq), unresolved_pct(lq)
    print(f"\nquality: citations {gq.get('total')} ({gu}% unresolved) -> "
          f"{lq.get('total')} ({lu}% unresolved); verified supported "
          f"{gq.get('verified_supported')}/{gq.get('verified_total')} -> "
          f"{lq.get('verified_supported')}/{lq.get('verified_total')}")
    print(f"claim_checks: {g_fp.get('claim_checks')} -> {l_fp.get('claim_checks')}")
    if lu is not None and (gu is None or lu > (gu + 2)):
        print("FLAG: unresolved-citation rate worsened materially")
        regressions += 1
    lv = lq.get("verified_total") or 0
    if (gq.get("verified_total") or 0) > 0 and lv == 0:
        print("FLAG: latest report has ZERO verified claims (verifier died?)")
        regressions += 1

    print(f"\n{regressions} regression flag(s)." if regressions
          else "\nNo regression flags.")
    return 1 if regressions else 0


def main():
    ap = argparse.ArgumentParser(description="Golden-set regression diff")
    ap.add_argument("ticker", nargs="?")
    ap.add_argument("--freeze", metavar="TICKER")
    ap.add_argument("--list", action="store_true")
    args = ap.parse_args()

    if args.list:
        if not os.path.isdir(GOLDEN_DIR):
            print("(no goldens frozen)")
            return
        for f in sorted(os.listdir(GOLDEN_DIR)):
            with open(os.path.join(GOLDEN_DIR, f), encoding="utf-8") as fh:
                g = json.load(fh)
            print(f"{g['ticker']}: report v{g['version']} frozen {g['frozen_at'][:19]}")
        return
    if args.freeze:
        freeze(args.freeze)
        return
    if not args.ticker:
        ap.error("give a TICKER to diff, --freeze TICKER, or --list")
    sys.exit(diff(args.ticker))


if __name__ == "__main__":
    main()
