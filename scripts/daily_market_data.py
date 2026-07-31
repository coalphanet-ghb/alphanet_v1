"""
Daily market-data job: closing price + market cap for every constituent
of a universe registry. Zero LLM. Independent of the research swarm.

    .venv\\Scripts\\python.exe scripts/daily_market_data.py --dry-run --limit 5
    .venv\\Scripts\\python.exe scripts/daily_market_data.py

Writes exactly two metrics per company into `metric_observations`:

    price        inr         Yahoo's last daily close
    market_cap   inr_crore   screener top card

at `period_type='day'`, dated with **that company's own close date**
from Yahoo — never `date.today()`. A suspended stock legitimately
reports an older date, and writing it under its own date stays truthful
instead of inventing a trading day.

Only two metrics, deliberately: the screener top card also yields `pe`,
`book_value`, `dividend_yield_pct`, `roce_pct` and `roe_pct`, and
persisting all seven daily across 150 companies would be 262K rows/year
instead of 75K, for values that are screener-derived anyway
(HANDOFF4 §6.8).

**Idempotent by construction.** The unique constraint
(entity, metric, period_start, period_end) with ignore_duplicates means
a re-run writes nothing, so Cloud Scheduler retries are safe. The same
property is why the intraday guard below matters: a half-day price
written under today's date would be permanent — the evening run could
not correct it.

Exit codes: 0 ok · 1 coverage below --min-coverage · 2 refused to run.
"""

import argparse
import datetime
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(errors="replace")     # cp1252 guard (HANDOFF3 §4)
    except Exception:
        pass

from src import db  # noqa: E402
from src.ingestion.fetcher import FetchError  # noqa: E402
from src.ingestion.market_data import (  # noqa: E402
    company_tokens, fetch_daily_close, fetch_market_cap,
)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_UNIVERSE = os.path.join(ROOT, "data", "universe", "nifty_midcap150.json")

IST = datetime.timezone(datetime.timedelta(hours=5, minutes=30))
MARKET_CLOSE_IST = datetime.time(15, 40)    # 15:30 close + settle margin
PRICE_DRIFT_LIMIT = 0.02                    # screener vs yahoo


def _try(fn, *a, attempts: int = 2):
    """One retry on transient failure; returns (value, error_str)."""
    err = ""
    for i in range(attempts):
        try:
            return fn(*a), ""
        except FetchError as e:
            err = str(e)
        except Exception as e:                      # never kill the batch
            err = f"{type(e).__name__}: {e}"
        if i + 1 < attempts:
            time.sleep(1.5)
    return None, err


def main() -> int:
    ap = argparse.ArgumentParser(description="Daily close + market cap")
    ap.add_argument("--universe", default=DEFAULT_UNIVERSE)
    ap.add_argument("--dry-run", action="store_true", help="fetch, write nothing")
    ap.add_argument("--limit", type=int, default=0, help="first N companies")
    ap.add_argument("--delay", type=float, default=0.4, help="politeness seconds")
    ap.add_argument("--min-coverage", type=float, default=0.90)
    ap.add_argument("--allow-intraday", action="store_true",
                    help="permit writing a close dated today before the "
                         "market has settled (default: refuse)")
    args = ap.parse_args()

    with open(args.universe, encoding="utf-8") as f:
        uni = json.load(f)
    companies = uni["companies"][:args.limit] if args.limit else uni["companies"]
    started = time.monotonic()
    print(f"[daily] {uni.get('index')} — {len(companies)} companies"
          + ("  [DRY RUN]" if args.dry_run else ""))

    rows, dates = [], []
    ok_close = ok_mcap = stale = 0
    problems: list[str] = []

    for i, c in enumerate(companies, 1):
        ticker, name = c["ticker"], c["name"]
        ent = db.get_entity_by_ticker(ticker)
        if not ent:
            problems.append(f"{ticker}: no entity — run scripts/seed_universe.py")
            continue
        toks = company_tokens(name)

        got, err = _try(fetch_daily_close, ticker, toks)
        if not got:
            problems.append(f"{ticker}: close — {err[:90]}")
            continue
        close, close_date, _ = got
        ok_close += 1
        dates.append(close_date)
        rows.append({"entity_id": ent["id"], "metric_name": "price",
                     "period_type": "day", "period_start": close_date,
                     "period_end": close_date, "value": close, "unit": "inr"})

        got, err = _try(fetch_market_cap, c["screener_slug"], toks)
        if not got:
            problems.append(f"{ticker}: mcap — {err[:90]}")
        else:
            mcap, scr_price = got
            drift = abs(scr_price - close) / close if close else 1.0
            if drift > PRICE_DRIFT_LIMIT:
                # a stale screener page would ship a market cap that does
                # not correspond to this close — omit it rather than store
                # a wrong number (the row's absence IS the UI's null)
                stale += 1
                problems.append(f"{ticker}: mcap skipped — screener price "
                                f"{scr_price} vs close {close} ({drift:.1%})")
            else:
                ok_mcap += 1
                rows.append({"entity_id": ent["id"], "metric_name": "market_cap",
                             "period_type": "day", "period_start": close_date,
                             "period_end": close_date, "value": mcap,
                             "unit": "inr_crore"})

        if i % 25 == 0:
            print(f"  ... {i}/{len(companies)}  ({ok_close} close, {ok_mcap} mcap)")
        time.sleep(args.delay)

    if not dates:
        print("[daily] FATAL: not a single close was fetched — aborting")
        return 2

    market_date = max(set(dates), key=dates.count)      # modal trading date
    now_ist = datetime.datetime.now(IST)
    if (market_date == now_ist.date().isoformat()
            and now_ist.time() < MARKET_CLOSE_IST and not args.allow_intraday):
        print(f"[daily] REFUSED: {market_date} is today and it is "
              f"{now_ist:%H:%M} IST — that price is intraday, and "
              f"append-only means a wrong row could never be corrected. "
              f"Re-run after {MARKET_CLOSE_IST:%H:%M} IST or pass "
              f"--allow-intraday.")
        return 2

    # Report rows INSERTED, not rows submitted. The upsert ignores
    # duplicates, so a re-run submits the same 300 rows and inserts
    # none — logging "300 rows written" there would be a lie, and this
    # log line is the job's dashboard.
    def _count_at(date_iso: str) -> int:
        return (db.get_client().table("metric_observations")
                .select("id", count="exact").eq("period_start", date_iso)
                .in_("metric_name", ["price", "market_cap"]).execute().count or 0)

    inserted = 0
    if rows and not args.dry_run:
        before_rows = _count_at(market_date)
        db.bulk_save_metric_observations(rows)
        inserted = _count_at(market_date) - before_rows

    cov = ok_close / len(companies) if companies else 0.0
    if problems:
        print(f"\n  {len(problems)} problem(s):")
        for p in problems[:20]:
            print(f"    {p}")
        if len(problems) > 20:
            print(f"    ... and {len(problems) - 20} more")
    print(f"\n[daily] {market_date}: {ok_close}/{len(companies)} close, "
          f"{ok_mcap}/{len(companies)} mcap, {stale} stale-price skip(s), "
          + (f"{len(rows)} rows prepared [DRY RUN — nothing written]"
             if args.dry_run else
             f"{len(rows)} rows submitted, {inserted} newly inserted"
             + (" (already up to date)" if rows and not inserted else ""))
          + f", {time.monotonic() - started:.0f}s")

    if cov < args.min_coverage:
        print(f"[daily] FAIL: close coverage {cov:.0%} < "
              f"{args.min_coverage:.0%} — not filling the list page silently")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
