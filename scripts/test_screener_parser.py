"""
Regression tests for the deterministic screener parser + metric vocabulary.

Run offline (fixture only):   python scripts/test_screener_parser.py
Include the live page:        python scripts/test_screener_parser.py --live

Guards the bug class that silently corrupted the numeric backbone: a SHORT
canonical key swallowing a LONGER label ("debt" in "debtor_days", "cfo" in
"CFO/OP", "cash" in "Free Cash Flow"). Those produced plausible-looking but
wrong numbers, which is worse than missing ones — hence these assertions.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.ingestion.metric_names import canon_name, CANON_NAMES  # noqa: E402
from src.ingestion.screener_parser import (  # noqa: E402
    parse_company_page, _fiscal_quarter_label,
)

FIXTURE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                       "data", "fixtures", "screener_sample.html")
URL = "https://www.screener.in/company/SONACOMS/consolidated/"


def test_vocabulary():
    # 1. idempotency: re-canonicalizing the parser's own output must not remap
    bad = [n for n in CANON_NAMES if canon_name(n) != n]
    assert not bad, f"canon_name not idempotent for: {bad}"

    # 2. the known collision traps (each one shipped a wrong number once)
    traps = {
        "Debtor Days": "debtor_days",          # was -> borrowings (via "debt")
        "debtor_days": "debtor_days",
        "CFO/OP": "cfo_to_op_pct",             # was -> cfo (ratio as value!)
        "Free Cash Flow": "fcf",               # was -> cash
        "Net Cash Flow": "net_cash_flow",
        "Cash from Operating Activity": "cfo",
        "Cash Conversion Cycle": "ccc_days",
        "Expenses": "total_expenses",          # contains "pe"
        "Borrowings": "borrowings",
        "Total Debt": "borrowings",
        "Sales": "revenue",
        "BEV revenue share": "ev_revenue_share",
        "Net order book": "order_book",
        "ebitda_margin": "opm_pct",
    }
    for label, expected in traps.items():
        got = canon_name(label)
        assert got == expected, f"canon_name({label!r}) = {got!r}, want {expected!r}"

    # 3. no canonical name may be swallowed by a shorter key from another entry
    for name in CANON_NAMES:
        pretty = name.replace("_", " ").title()
        assert canon_name(pretty) == name, f"{pretty!r} -> {canon_name(pretty)!r} != {name!r}"
    print("vocabulary: idempotent, %d canonical names, %d traps held"
          % (len(CANON_NAMES), len(traps)))


def test_quarter_labels():
    for header, want in (("Jun 2025", "Q1FY26"), ("Sep 2025", "Q2FY26"),
                         ("Dec 2025", "Q3FY26"), ("Mar 2026", "Q4FY26")):
        got = _fiscal_quarter_label(header)
        assert got == want, f"{header} -> {got}, want {want}"
    print("quarter labels: Indian FY mapping OK")


def _check_parse(res, where):
    c = res["candidates"]
    names = {x["name"] for x in c}
    assert len(c) >= 150, f"{where}: only {len(c)} candidates"
    for required in ("revenue", "net_profit", "cfo", "borrowings", "debtor_days",
                     "equity_capital", "reserves", "total_assets", "eps", "roce_pct"):
        assert required in names, f"{where}: missing {required}"
    # CFO must be a rupee flow, never the CFO/OP percentage
    cfo_vals = [x["value_printed"] for x in c if x["name"] == "cfo"]
    assert not any("%" in v for v in cfo_vals), f"{where}: CFO contaminated by ratio: {cfo_vals}"
    # borrowings must not have been overwritten by debtor days
    bor = [x["value_printed"] for x in c if x["name"] == "borrowings"]
    dd = [x["value_printed"] for x in c if x["name"] == "debtor_days"]
    assert bor != dd, f"{where}: borrowings == debtor_days (collision!)"
    print(f"{where}: {len(c)} candidates, {len(names)} distinct metrics, "
          f"{len(res['doc_links']['concall_transcripts'])} transcripts, "
          f"{len(res['doc_links']['annual_reports'])} ARs, warnings={res['warnings']}")


def test_fixture():
    with open(FIXTURE, encoding="utf-8") as f:
        res = parse_company_page(URL, html=f.read())
    _check_parse(res, "fixture")
    assert len(res["doc_links"]["concall_transcripts"]) == 3
    assert res["doc_links"]["concall_transcripts"][0]["url"].endswith("q4fy26_transcript.pdf")


def test_live():
    res = parse_company_page(URL)
    _check_parse(res, "LIVE screener")
    assert res["doc_links"]["concall_transcripts"], "no transcript links on live page"


if __name__ == "__main__":
    test_vocabulary()
    test_quarter_labels()
    test_fixture()
    if "--live" in sys.argv:
        test_live()
    print("\nAll screener parser tests passed.")
