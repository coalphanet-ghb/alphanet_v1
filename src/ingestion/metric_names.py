"""
Canonical metric names — the single vocabulary shared by the screener
parser, the LLM extraction gate (s3 validation), the compute library, and
sector-pack KPI lookups. Matching is substring-based on lowercased labels.
"""

CANON = [
    # --- P&L ---------------------------------------------------------------
    (("sales", "revenue from operations", "revenue", "total income"), "revenue"),
    (("net profit", "profit after tax", "pat"), "net_profit"),
    (("operating profit", "ebitda"), "operating_profit"),
    (("opm", "operating margin", "ebitda margin"), "opm_pct"),
    (("other income",), "other_income"),
    (("interest", "finance cost"), "interest"),
    (("depreciation", "amortisation"), "depreciation"),
    (("profit before tax", "pbt"), "pbt"),
    (("tax %", "tax rate", "tax_pct", "tax"), "tax_pct"),
    (("eps",), "eps"),
    (("expenses",), "total_expenses"),
    (("dividend payout",), "dividend_payout_pct"),
    # --- balance sheet -------------------------------------------------------
    (("equity capital", "share capital"), "equity_capital"),
    (("reserves",), "reserves"),
    (("borrowing", "debt", "total debt"), "borrowings"),
    (("other liabilities",), "other_liabilities"),
    (("total liabilities",), "total_liabilities"),
    (("fixed assets", "net block", "property plant"), "fixed_assets"),
    (("cwip", "capital work"), "cwip"),
    (("investments",), "investments"),
    (("other assets",), "other_assets"),
    (("total assets",), "total_assets"),
    # NOTE: no bare "cash" key — it would swallow "free cash flow",
    # "net cash flow", "cash conversion cycle", "cash from operating"...
    (("cash equivalents", "cash and bank", "cash & bank", "cash balance"), "cash"),
    # --- cash flow -----------------------------------------------------------
    # "cfo/op" MUST precede "cfo" by length so screener's CFO/OP ratio row
    # is not mistaken for the CFO value itself (it overwrote real CFO with
    # percentages until this split existed).
    (("cash from operating", "cash generated from operations", "cfo"), "cfo"),
    (("cfo/op", "cfo/ebitda", "cfo to op"), "cfo_to_op_pct"),
    (("cash from investing",), "cfi"),
    (("cash from financing",), "cff"),
    (("net cash flow",), "net_cash_flow"),
    (("free cash flow", "fcf"), "fcf"),
    # --- working capital / ratios ---------------------------------------------
    (("debtor days", "receivable days", "dso"), "debtor_days"),
    (("inventory days", "dio"), "inventory_days"),
    (("payable days", "days payable", "dpo"), "payable_days"),
    (("cash conversion cycle", "ccc"), "ccc_days"),
    (("working capital days",), "working_capital_days"),
    (("roce",), "roce_pct"),
    (("roe", "return on equity"), "roe_pct"),
    # --- valuation / market ----------------------------------------------------
    # no bare "pe" key: it is a substring of "expenses"
    (("stock p/e", "price to earning", "pe ratio", "p/e"), "pe"),
    (("book value",), "book_value"),
    (("price to book", "p/b"), "pb"),
    (("dividend yield",), "dividend_yield_pct"),
    (("market cap",), "market_cap"),
    (("current price", "cmp", "stock price"), "price"),
    # --- holdings ---------------------------------------------------------------
    (("promoter holding", "promoters"), "promoter_holding_pct"),
    (("pledged",), "promoter_pledge_pct"),
    (("fiis",), "fii_holding_pct"),
    (("diis",), "dii_holding_pct"),
    # --- sector KPIs (Phase 1 extension: extracted candidates land instead of
    #     dying unmapped; feeds sector_kpis lookups) ------------------------------
    (("order book", "net order book", "order_book"), "order_book"),
    (("bev revenue share", "ev revenue share", "ev-linked revenue",
      "bev share"), "ev_revenue_share"),
    (("export share", "exports % of revenue", "export revenue share"), "export_share"),
    (("top customer", "customer concentration", "top-1 customer"), "customer_concentration"),
    (("aftermarket share", "aftermarket % of revenue"), "aftermarket_share"),
    (("capacity utilisation", "capacity utilization"), "capacity_utilization"),
]


CANON_NAMES = frozenset(c for _, c in CANON)


# --- unit-class guard (Phase 3) ---------------------------------------------
# Extraction now emits canon-NAMED candidates straight from AR/IP/concall
# text, and models sometimes attach a canon name to a related-but-different
# quantity ("order book: 70% EV-linked" -> order_book = 70 percent; revenue
# from >10% customers in Rs mn -> customer_concentration = 7894 inr_crore).
# A canon KPI therefore declares its expected unit CLASS and the validation
# gate drops mismatches: wrong numbers are worse than missing ones (§6.1).
_PERCENT_CLASS = frozenset({
    "ev_revenue_share", "export_share", "customer_concentration",
    "aftermarket_share", "capacity_utilization",
    "promoter_holding_pct", "promoter_pledge_pct",
    "fii_holding_pct", "dii_holding_pct", "dividend_yield_pct",
})
_CURRENCY_CLASS = frozenset({"order_book", "market_cap"})


def unit_mismatch(name: str, unit: str) -> bool:
    """True when a canon metric arrives with a unit its definition cannot
    have — the observation must be dropped, never stored."""
    if name in _PERCENT_CLASS:
        return unit != "percent"
    if name in _CURRENCY_CLASS:
        return unit not in ("inr_crore", "inr")
    return False


def _norm(s: str) -> str:
    """Lowercase; '-' and '_' both become spaces; collapse whitespace. Applied
    to BOTH keys and inputs so 'debtor_days', 'Debtor Days' and 'debtor-days'
    all normalize alike."""
    return " ".join((s or "").lower().replace("-", " ").replace("_", " ").split())


# Flattened (key, canon) pairs, longest key first, so specific names beat
# generic substrings ("bev revenue share" must not match "revenue"; and
# "debtor days" must be tried before "debt").
_PAIRS = sorted((( _norm(k), c) for keys, c in CANON for k in keys),
                key=lambda kc: -len(kc[0]))


def canon_name(raw: str) -> str | None:
    r = _norm(raw)
    if not r:
        return None
    # Already canonical (the parser canonicalizes before the validation gate
    # re-checks) -> identity. Without this, re-canonicalizing "debtor_days"
    # would substring-match the "debt" key and silently become "borrowings".
    already = r.replace(" ", "_")
    if already in CANON_NAMES:
        return already
    for key, canon in _PAIRS:
        if key in r:
            return canon
    return None
