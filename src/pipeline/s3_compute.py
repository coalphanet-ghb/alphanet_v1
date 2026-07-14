"""
S3 — deterministic computation (Python, zero LLM). Spec: nodes/s3_compute.

Validation gate (candidates -> metric_observations) then the calc
modules. Defensive throughout: anything uncomputable lands in
insufficiencies with the missing input named — never silent, never
guessed. Every computed value carries {formula_id, inputs, periods}.
"""

import re
from datetime import date

from src import db

# --- canonical metric names (screener rows and common prints) ---------------
_CANON = [
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
    (("equity capital", "share capital"), "equity_capital"),
    (("reserves",), "reserves"),
    (("borrowing", "debt", "total debt"), "borrowings"),
    (("fixed assets", "net block", "property plant"), "fixed_assets"),
    (("cwip", "capital work"), "cwip"),
    (("investments",), "investments"),
    (("cash equivalents", "cash and bank", "cash_"), "cash"),
    (("cash from operating", "cash generated from operations", "cfo"), "cfo"),
    (("cash from investing",), "cfi"),
    (("cash from financing",), "cff"),
    (("debtor days", "receivable days", "dso"), "debtor_days"),
    (("inventory days", "dio"), "inventory_days"),
    (("payable days", "days payable", "dpo"), "payable_days"),
    (("cash conversion cycle", "ccc"), "ccc_days"),
    (("roce",), "roce_pct"),
    (("roe", "return on equity"), "roe_pct"),
    (("stock p/e", "price to earning", "pe ratio", "p/e", "pe_"), "pe"),
    (("book value",), "book_value"),
    (("price to book", "p/b"), "pb"),
    (("dividend yield",), "dividend_yield_pct"),
    (("market cap",), "market_cap"),
    (("current price", "cmp", "stock price"), "price"),
    (("promoter holding", "promoters"), "promoter_holding_pct"),
    (("pledged",), "promoter_pledge_pct"),
    (("total assets",), "total_assets"),
]


def canon_name(raw: str) -> str | None:
    r = (raw or "").lower().replace("-", " ").strip()
    for keys, canon in _CANON:
        if any(k in r for k in keys):
            return canon
    return None


# --- value & period parsing --------------------------------------------------

def parse_value(printed: str, name: str) -> tuple[float, str] | None:
    """Returns (value, unit) or None if unparseable."""
    if printed is None:
        return None
    t = str(printed).strip().replace(",", "").replace("₹", "").replace("Rs.", "").replace("Rs", "")
    is_pct = "%" in t or name.endswith("_pct") or "yield" in name
    t = t.replace("%", "").strip()
    mult = 1.0
    low = t.lower()
    for token, m in (("crore", 1.0), ("cr.", 1.0), ("cr", 1.0), ("lakh", 0.01),
                     ("bn", 100.0), ("billion", 100.0), ("mn", 0.1), ("million", 0.1)):
        if token in low:
            t = re.sub(token, "", low, flags=re.I).strip()
            mult = m
            break
    m = re.search(r"-?\d+(\.\d+)?", t)
    if not m:
        return None
    val = float(m.group()) * mult
    if is_pct:
        return val, "percent"
    if name in ("pe", "pb"):
        return val, "x"
    if name in ("eps", "price", "book_value"):
        return val, "inr"
    if name.endswith("_days"):
        return val, "days"
    return val, "inr_crore"


_MONTHS = {m: i + 1 for i, m in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"])}


def parse_period(printed: str) -> dict | None:
    """-> {period_type, period_start, period_end} or None (ambiguous)."""
    if not printed:
        return None
    t = str(printed).strip().lower()
    m = re.match(r"q([1-4])\s*fy\s*(\d{2,4})", t.replace("-", "").replace(" ", ""))
    if m:
        q, yy = int(m.group(1)), int(m.group(2)) % 100
        ey = 2000 + yy    # fiscal year ENDS Mar of this calendar year
        # Indian FY quarters: Q1 Apr-Jun, Q2 Jul-Sep, Q3 Oct-Dec (all in
        # ey-1); Q4 Jan-Mar (in ey itself)
        bounds = {1: ((ey - 1, 4, 1), (ey - 1, 6, 30)),
                  2: ((ey - 1, 7, 1), (ey - 1, 9, 30)),
                  3: ((ey - 1, 10, 1), (ey - 1, 12, 31)),
                  4: ((ey, 1, 1), (ey, 3, 31))}
        (s, e) = bounds[q]
        return {"period_type": "quarter",
                "period_start": date(*s).isoformat(),
                "period_end": date(*e).isoformat()}
    m = re.match(r"fy\s*(\d{2,4})", t.replace(" ", ""))
    if m:
        yy = int(m.group(1)) % 100
        end_year = 2000 + yy
        return {"period_type": "year",
                "period_start": date(end_year - 1, 4, 1).isoformat(),
                "period_end": date(end_year, 3, 31).isoformat()}
    m = re.match(r"([a-z]{3})\w*\s+(\d{4})", t)
    if m and m.group(1) in _MONTHS:
        mo, yr = _MONTHS[m.group(1)], int(m.group(2))
        if mo == 3:   # "Mar 2025" on screener = FY25 annual column
            return {"period_type": "year",
                    "period_start": date(yr - 1, 4, 1).isoformat(),
                    "period_end": date(yr, 3, 31).isoformat()}
        return {"period_type": "month",
                "period_start": date(yr, mo, 1).isoformat(),
                "period_end": date(yr, mo, 28).isoformat()}
    return None


# --- series helpers ----------------------------------------------------------

def _series(obs: list[dict], name: str) -> list[dict]:
    s = [o for o in obs if o["metric_name"] == name and o["period_type"] == "year"]
    return sorted(s, key=lambda o: o["period_start"])


def _latest(obs, name, period_type=None):
    s = [o for o in obs if o["metric_name"] == name and
         (period_type is None or o["period_type"] == period_type)]
    return max(s, key=lambda o: o["period_end"]) if s else None


def _cagr(series: list[dict], years: int) -> dict | None:
    if len(series) < years + 1:
        return None
    a, b = series[-years - 1], series[-1]
    if not a["value"] or a["value"] <= 0 or b["value"] <= 0:
        return None
    val = ((b["value"] / a["value"]) ** (1 / years) - 1) * 100
    return {"value": round(val, 1), "unit": "percent",
            "from": a["period_end"], "to": b["period_end"],
            "inputs": [a["id"], b["id"]]}


# --- validation gate -----------------------------------------------------------

def validate_candidates(state) -> tuple[list[dict], list[str]]:
    """candidates -> normalized observation dicts (+ insufficiencies)."""
    insuff = []
    out = []
    profile = state["profile"]
    peer_by_slug = {}
    for p in state.get("peer_entities", []):
        t = (p.get("metadata") or {}).get("ticker", "")
        if t:
            peer_by_slug[t.upper().replace("&", "%26")] = p["id"]
            peer_by_slug[t.upper()] = p["id"]

    from src.pipeline.query_banks import MACRO_METRIC_ENTITY_MAP
    entity_cache = {}

    def macro_entity(name_raw: str):
        low = name_raw.lower()
        for key, ent_name in MACRO_METRIC_ENTITY_MAP.items():
            if key in low:
                if ent_name not in entity_cache and state["persist"]:
                    for e in db.list_entities():
                        entity_cache[e["name"]] = e["id"]
                return entity_cache.get(ent_name)
        return None

    skipped = 0
    for c in state.get("metric_candidates", []):
        if c.get("ambiguous"):
            continue
        # One malformed candidate must never kill the run — parsing is
        # best-effort, failures are skipped and counted.
        try:
            name = canon_name(c.get("name", "")) or c.get("name", "").strip().lower().replace(" ", "_")
            parsed_v = parse_value(c.get("value_printed"), name)
            parsed_p = parse_period(c.get("period_printed"))
        except Exception:
            skipped += 1
            continue
        if not parsed_v or not parsed_p:
            skipped += 1
            continue
        url = c.get("url", "")
        if c.get("doc_class") == "macro_page":
            ent = macro_entity(c.get("name", ""))
            if not ent:
                continue
        elif c.get("doc_class") == "screener_page" and "screener.in" in url:
            slug = url.rstrip("/").split("/")[-2].upper() if url.endswith("/consolidated/") else \
                   url.rstrip("/").split("/")[-1].upper()
            if slug == profile.get("screener_slug", "").upper():
                ent = profile.get("entity_id")
            else:
                ent = peer_by_slug.get(slug)
                if not ent:
                    continue
        elif c.get("doc_class") in ("concall", "annual_report", "results_pdf",
                                    "investor_presentation", "rating_rationale",
                                    "shareholding", "screener_page"):
            ent = profile.get("entity_id")
        else:
            # sector_page / news / valuepickr numbers are NOT company
            # observations — they stay as evidence only
            skipped += 1
            continue
        if not ent:
            skipped += 1
            continue
        out.append({"entity_id": ent, "metric_name": name,
                    "value": parsed_v[0], "unit": parsed_v[1],
                    "source_document_id": c.get("source_document_id"),
                    **parsed_p})
    if skipped:
        print(f"  [s3] {skipped} candidate(s) skipped (unparseable value/period/entity)")
    if not out:
        insuff.append("metric extraction yielded no valid observations — "
                      "numeric sections will be thin (check screener readability)")
    return out, insuff


# --- forensic battery ------------------------------------------------------------

def _flag(check, status, md, inputs, severity="medium"):
    return {"check": check, "status": status, "severity": severity,
            "md": md, "inputs": inputs}


def forensic_battery(obs: list[dict]) -> tuple[list[dict], list[str]]:
    flags, insuff = [], []

    def need(*names):
        missing = [n for n in names if not _series(obs, n) and not _latest(obs, n)]
        return missing

    # 1. receivables vs revenue (debtor days drift)
    dd = _series(obs, "debtor_days")
    if len(dd) >= 3:
        drift = dd[-1]["value"] - dd[-3]["value"]
        st = "FLAG" if drift > 20 else ("WATCH" if drift > 10 else "OK")
        flags.append(_flag("receivables_vs_revenue", st,
                           f"Debtor days moved {drift:+.0f} over 2 years "
                           f"({dd[-3]['value']:.0f} -> {dd[-1]['value']:.0f}).",
                           [dd[-3]["id"], dd[-1]["id"]],
                           "high" if st == "FLAG" else "medium"))
    else:
        insuff.append("forensic receivables check: needs 3y of debtor days")

    # 2. cumulative PAT vs CFO
    np_s, cfo_s = _series(obs, "net_profit"), _series(obs, "cfo")
    common = min(len(np_s), len(cfo_s))
    if common >= 3:
        sp = sum(o["value"] for o in np_s[-common:])
        sc = sum(o["value"] for o in cfo_s[-common:])
        ratio = sc / sp if sp else 0
        st = "FLAG" if ratio < 0.5 else ("WATCH" if ratio < 0.75 else "OK")
        flags.append(_flag("cum_pat_vs_cfo", st,
                           f"Cumulative {common}y CFO / PAT = {ratio:.2f} "
                           f"(CFO Rs {sc:,.0f} cr vs PAT Rs {sp:,.0f} cr).",
                           [o["id"] for o in np_s[-common:] + cfo_s[-common:]],
                           "high" if st == "FLAG" else "medium"))
    else:
        insuff.append("quality-of-earnings check: needs 3y of PAT and CFO")

    # 3. implied borrowing rate
    b, i = _series(obs, "borrowings"), _series(obs, "interest")
    if len(b) >= 2 and i:
        avg_debt = (b[-1]["value"] + b[-2]["value"]) / 2
        if avg_debt > 0:
            rate = i[-1]["value"] / avg_debt * 100
            st = "WATCH" if (rate < 4 or rate > 14) else "OK"
            flags.append(_flag("implied_borrowing_rate", st,
                               f"Interest / avg gross debt implies {rate:.1f}% "
                               f"(sanity band 7-11% for most corporates).",
                               [b[-1]["id"], b[-2]["id"], i[-1]["id"]]))

    # 4. other income dependence
    oi, pbt = _series(obs, "other_income"), _series(obs, "pbt")
    if oi and pbt and pbt[-1]["value"]:
        dep = oi[-1]["value"] / pbt[-1]["value"] * 100
        st = "FLAG" if dep > 25 else ("WATCH" if dep > 15 else "OK")
        flags.append(_flag("other_income_dependence", st,
                           f"Other income is {dep:.0f}% of PBT.",
                           [oi[-1]["id"], pbt[-1]["id"]]))

    # 5. depreciation rate drift
    dep, fa = _series(obs, "depreciation"), _series(obs, "fixed_assets")
    if len(dep) >= 3 and len(fa) >= 3 and fa[-1]["value"] and fa[-3]["value"]:
        r_now = dep[-1]["value"] / fa[-1]["value"] * 100
        r_then = dep[-3]["value"] / fa[-3]["value"] * 100
        st = "WATCH" if r_now < r_then - 1.5 else "OK"
        flags.append(_flag("depreciation_rate_drift", st,
                           f"Depreciation rate {r_then:.1f}% -> {r_now:.1f}% of net block.",
                           [dep[-1]["id"], fa[-1]["id"], dep[-3]["id"], fa[-3]["id"]]))

    # 6. CWIP hideout
    cwip, fa2 = _series(obs, "cwip"), _series(obs, "fixed_assets")
    if len(cwip) >= 3 and fa2:
        share = cwip[-1]["value"] / max(fa2[-1]["value"], 1) * 100
        stuck = all(c["value"] >= 0.8 * cwip[-1]["value"] for c in cwip[-3:])
        st = "WATCH" if (share > 25 and stuck) else "OK"
        flags.append(_flag("cwip_aging", st,
                           f"CWIP is {share:.0f}% of net block"
                           + (" and has not commissioned for 3 years." if stuck else "."),
                           [cwip[-1]["id"], fa2[-1]["id"]]))

    # 7. tax rate anomaly
    tax = _series(obs, "tax_pct")
    if tax:
        st = "WATCH" if tax[-1]["value"] < 18 else "OK"
        flags.append(_flag("tax_rate", st,
                           f"Effective tax rate {tax[-1]['value']:.0f}% "
                           f"(statutory ~25%; check stated exemption if low).",
                           [tax[-1]["id"]]))

    # 8. promoter pledge
    pl = _latest(obs, "promoter_pledge_pct")
    if pl is not None:
        v = pl["value"]
        st = "FLAG" if v > 50 else ("WATCH" if v > 20 else "OK")
        flags.append(_flag("promoter_pledge", st,
                           f"Promoter pledge at {v:.1f}% of holding.",
                           [pl["id"]], "high" if st == "FLAG" else "medium"))

    return flags, insuff


# --- guidance scorecard -------------------------------------------------------

def guidance_scorecard(items: list[dict], obs: list[dict]) -> dict:
    scored, pending = [], []
    for g in items:
        period = parse_period(g.get("period", ""))
        metric = canon_name(g.get("metric", "")) if g.get("metric") else None
        if not period or not metric:
            pending.append({**g, "status": "unmatchable"})
            continue
        actual = next((o for o in obs if o["metric_name"] == metric and
                       o["period_end"] == period["period_end"]), None)
        if actual is None:
            pending.append({**g, "status": "pending_or_unmeasured"})
        else:
            scored.append({**g, "status": "actual_available",
                           "actual_value": actual["value"], "actual_unit": actual["unit"],
                           "actual_input": actual["id"]})
    return {"scored": scored, "pending": pending,
            "note": "verdicts on scored items are written by s4_management "
                    "against guided ranges (text) vs actual (number)"}


# --- peer table -----------------------------------------------------------------

_PEER_METRICS = [("revenue_cagr_3y", None), ("opm_pct", "latest"),
                 ("roe_pct", "latest"), ("roce_pct", "latest"),
                 ("pe", "latest"), ("market_cap", "latest"),
                 ("debtor_days", "latest")]


def peer_table(company_id: str, company_label: str, peers: list[dict],
               all_obs_by_entity: dict) -> dict:
    rows, worst = [], []
    universe = [(company_label, company_id)] + \
               [(p["name"], p["id"]) for p in peers]
    for label, eid in universe:
        obs = all_obs_by_entity.get(eid, [])
        row = {"name": label}
        rev = _series(obs, "revenue")
        c3 = _cagr(rev, 3)
        row["revenue_cagr_3y"] = c3["value"] if c3 else None
        for metric, _ in _PEER_METRICS[1:]:
            latest = _latest(obs, metric)
            row[metric] = latest["value"] if latest else None
        rows.append(row)
    cols = ["revenue_cagr_3y", "opm_pct", "roe_pct", "roce_pct", "pe"]
    me = rows[0]
    for col in cols:
        vals = [(r["name"], r[col]) for r in rows if r[col] is not None]
        if len(vals) >= 3 and me.get(col) is not None:
            ordered = sorted(vals, key=lambda x: x[1], reverse=(col != "pe"))
            pos = [n for n, _ in ordered].index(me["name"]) + 1
            if pos == len(ordered) and col != "pe":
                worst.append({"dimension": col, "value": me[col],
                              "peer_best": ordered[0][1], "attribution": "unattributed"})
    return {"rows": rows, "columns": ["name"] + [m for m, _ in _PEER_METRICS],
            "worst_cells": worst, "formula_id": "peer_table"}


# --- node ------------------------------------------------------------------------

def compute_node(state) -> dict:
    insufficiencies: list[str] = []
    persist = state.get("persist")
    profile = state["profile"]
    pack = state["pack"]

    normalized, ins0 = validate_candidates(state)
    insufficiencies += ins0

    # persist observations + collect (with row ids for lineage)
    obs_by_entity: dict[str, list] = {}
    for n in normalized:
        row_id = None
        if persist:
            row_id = db.save_metric_observation(**n)
        rec = {**n, "id": row_id or f"mem_{len(obs_by_entity)}_{n['metric_name']}_{n['period_end']}"}
        obs_by_entity.setdefault(n["entity_id"], []).append(rec)

    company_id = profile.get("entity_id", "company")
    obs = obs_by_entity.get(company_id, [])
    print(f"[s3_compute] {len(normalized)} observations validated "
          f"({len(obs)} for company, {len(obs_by_entity)-1 if len(obs_by_entity) else 0} other entities)")

    cf = {}   # computed_financials {formula_id: {...}}
    rev = _series(obs, "revenue")
    np_s = _series(obs, "net_profit")
    for years in (3, 5):
        c = _cagr(rev, years)
        if c:
            cf[f"revenue_cagr_{years}y"] = c
        cn = _cagr(np_s, years)
        if cn:
            cf[f"net_profit_cagr_{years}y"] = cn
    if len(rev) >= 2 and rev[-2]["value"]:
        cf["revenue_yoy"] = {"value": round((rev[-1]["value"] / rev[-2]["value"] - 1) * 100, 1),
                             "unit": "percent", "to": rev[-1]["period_end"],
                             "inputs": [rev[-2]["id"], rev[-1]["id"]]}
    for name in ("opm_pct", "roe_pct", "roce_pct", "debtor_days", "inventory_days",
                 "payable_days", "eps", "promoter_holding_pct"):
        s = _series(obs, name) or ([_latest(obs, name)] if _latest(obs, name) else [])
        s = [x for x in s if x]
        if s:
            cf[f"{name}_series"] = {"points": [{"period": o["period_end"], "value": o["value"]}
                                               for o in s[-6:]],
                                    "unit": s[-1]["unit"], "inputs": [o["id"] for o in s[-6:]]}
    # margins/net margin
    if rev and np_s and rev[-1]["value"]:
        pairs = [(r, n) for r in rev for n in np_s if r["period_end"] == n["period_end"]]
        if pairs:
            r, n = pairs[-1]
            cf["net_margin"] = {"value": round(n["value"] / r["value"] * 100, 1),
                                "unit": "percent", "period": r["period_end"],
                                "inputs": [r["id"], n["id"]]}
    # leverage
    b, eqc, res = _series(obs, "borrowings"), _series(obs, "equity_capital"), _series(obs, "reserves")
    if b and eqc and res:
        eq = eqc[-1]["value"] + res[-1]["value"]
        if eq > 0:
            cf["debt_to_equity"] = {"value": round(b[-1]["value"] / eq, 2), "unit": "x",
                                    "period": b[-1]["period_end"],
                                    "inputs": [b[-1]["id"], eqc[-1]["id"], res[-1]["id"]]}
    op, i_s = _series(obs, "operating_profit"), _series(obs, "interest")
    if op and i_s and i_s[-1]["value"]:
        cf["interest_coverage"] = {"value": round(op[-1]["value"] / i_s[-1]["value"], 1),
                                   "unit": "x", "period": op[-1]["period_end"],
                                   "inputs": [op[-1]["id"], i_s[-1]["id"]],
                                   "note": "operating profit / interest (EBITDA-based approx)"}
    # cash quality
    cfo_s = _series(obs, "cfo")
    if cfo_s and np_s:
        pairs = [(c, n) for c in cfo_s for n in np_s if c["period_end"] == n["period_end"]]
        if pairs:
            vals = [round(c["value"] / n["value"], 2) for c, n in pairs[-5:] if n["value"]]
            if vals:
                cf["cfo_to_pat"] = {"points": vals, "unit": "x",
                                    "median": sorted(vals)[len(vals) // 2],
                                    "inputs": [x["id"] for pr in pairs[-5:] for x in pr]}

    flags, ins1 = forensic_battery(obs)
    insufficiencies += ins1

    scorecard = guidance_scorecard(state.get("guidance_items", []), obs)

    ptable = peer_table(company_id, profile["name"].split("(")[0].strip(),
                        state.get("peer_entities", []), obs_by_entity)
    if len([r for r in ptable["rows"] if any(v is not None for k, v in r.items() if k != "name")]) < 3:
        insufficiencies.append("peer table thin: peer screener pages yielded "
                               "insufficient observations")

    # valuation context
    val = {}
    for name in ("pe", "pb", "market_cap", "price", "dividend_yield_pct", "book_value"):
        latest = _latest(obs, name)
        if latest:
            val[name] = {"value": latest["value"], "unit": latest["unit"],
                         "period": latest["period_end"], "inputs": [latest["id"]]}
    pe_col = [(r["name"], r.get("pe")) for r in ptable["rows"] if r.get("pe") is not None]
    if val.get("pe") and len(pe_col) >= 3:
        ordered = sorted(pe_col, key=lambda x: x[1])
        val["pe_peer_rank"] = {"rank": [n for n, _ in ordered].index(ptable["rows"][0]["name"]) + 1
                               if ptable["rows"][0].get("pe") is not None else None,
                               "of": len(ordered), "peers": ordered}
    insufficiencies.append("valuation own-history percentile: needs multiple "
                           "history (not yet ingested) — current multiple and peer rank only")

    # sector KPIs (generic: look for the metric; else insufficiency)
    skpis = {}
    for k in pack.get("compute", {}).get("sector_kpis", []):
        fid = k["formula_id"]
        hit = _latest(obs, fid) or _latest(obs, fid.replace("_pct", ""))
        if hit:
            skpis[fid] = {"value": hit["value"], "unit": hit["unit"],
                          "period": hit["period_end"], "inputs": [hit["id"]]}
        else:
            insufficiencies.append(f"sector KPI '{fid}' not computable from "
                                   f"extracted observations")

    computed = {"computed_financials": cf, "forensic_flags": flags,
                "guidance_scorecard": scorecard, "peer_table": ptable,
                "valuation_context": val, "sector_kpis": skpis,
                "insufficiencies": insufficiencies,
                "skipped_modules": pack.get("compute", {}).get("skip_modules", [])}

    if persist:
        for section in ("computed_financials", "forensic_flags", "guidance_scorecard",
                        "peer_table", "valuation_context"):
            db.save_knowledge_entry("company", company_id, section,
                                    {"data": computed[section]},
                                    generated_by_run_id=state.get("run_id") or None)

    print(f"[s3_compute] {len(cf)} computed metrics, {len(flags)} forensic checks, "
          f"{len(insufficiencies)} insufficiencies")
    return {"computed": computed}
