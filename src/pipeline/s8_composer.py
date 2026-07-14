"""
S8 — report assembly (deterministic, zero LLM). Spec: nodes/s8_composer.
Builds section A (snapshot) and K (sources) in code, checks citation
integrity, renders markdown, persists report_versions.
"""

import os
import re
from datetime import datetime, timezone

from src import db
from src.config import REPORTS_DIR
from src.llm import get_active_model

_UUID_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")

_SECTION_TITLES = {
    "B": "Business Overview", "C": "Industry & Macro Context",
    "D": "Financial Analysis", "E": "Supply Chain",
    "F": "Management, Governance & Guidance", "G": "Peer Comparison",
    "H": "Risks", "I": "Valuation Context", "J": "Key Takeaways",
}


def _fmt_value(v, unit=""):
    if v is None:
        return "—"
    if isinstance(v, float):
        v = f"{v:,.1f}".rstrip("0").rstrip(".")
    u = {"percent": "%", "x": "×", "inr_crore": " Cr", "inr": "", "days": " days"}.get(unit, "")
    return f"{v}{u}"


def _snapshot(state) -> list[str]:
    comp = state.get("computed", {})
    val, cf = comp.get("valuation_context", {}), comp.get("computed_financials", {})
    skpis = comp.get("sector_kpis", {})
    pack = state["pack"]
    lines = ["## A. Snapshot", ""]
    lines.append(f"**{state['profile']['name']}** ({state['profile']['ticker']}) · "
                 f"{pack['label']} · last updated "
                 f"{datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
    lines.append("")
    lines.append("| Universal vitals | Value |")
    lines.append("|---|---|")
    uni = [("Market cap", val.get("market_cap")), ("P/E (TTM)", val.get("pe")),
           ("Dividend yield", val.get("dividend_yield_pct"))]
    roe = cf.get("roe_pct_series")
    uni.append(("ROE", {"value": roe["points"][-1]["value"], "unit": roe["unit"]} if roe else None))
    for label, v in uni:
        lines.append(f"| {label} | {_fmt_value(v['value'], v.get('unit')) if v else '—'} |")
    lines.append("")
    lines.append(f"| Sector vitals ({pack['label']}) | Value |")
    lines.append("|---|---|")
    for vital in pack.get("snapshot_vitals", [])[:8]:
        hit = skpis.get(vital["metric_id"])
        if not hit:
            calc_key = vital["calc"].split(".")[-1]
            for k in (vital["metric_id"], calc_key, f"{calc_key}_series"):
                c = cf.get(k)
                if c:
                    hit = ({"value": c["points"][-1]["value"], "unit": c.get("unit")}
                           if "points" in c else c)
                    break
            if not hit and vital["metric_id"] in ("pe", "pb"):
                hit = val.get(vital["metric_id"])
        lines.append(f"| {vital['label']} | "
                     f"{_fmt_value(hit['value'], hit.get('unit')) if hit else 'not computable yet'} |")
    lines.append("")
    return lines


def _render_block(b: dict, resolve) -> list[str]:
    t = b.get("type")
    out = []
    if t == "narrative":
        if b.get("title"):
            out.append(f"**{b['title']}**")
        out.append(b.get("md", ""))
    elif t == "metric_card":
        out.append("| Metric | Value | Period |")
        out.append("|---|---|---|")
        for m in b.get("metrics", []):
            out.append(f"| {m.get('name','')} | {_fmt_value(m.get('value'), m.get('unit',''))} "
                       f"| {m.get('period','')} |")
    elif t == "table":
        cols = b.get("columns", [])
        if cols:
            out.append("| " + " | ".join(str(c) for c in cols) + " |")
            out.append("|" + "---|" * len(cols))
            for row in b.get("rows", []):
                out.append("| " + " | ".join(_fmt_value(c) if isinstance(c, (int, float))
                                             else str(c if c is not None else "—")
                                             for c in row) + " |")
    elif t == "ranked_list":
        for it in b.get("items", []):
            sev = f" `{it['severity']}`" if it.get("severity") else ""
            out.append(f"{it.get('rank','-')}. **{it.get('title','')}**{sev} — {it.get('md','')}")
            if it.get("monitorable"):
                out.append(f"   - *Watch:* {it['monitorable']}")
    elif t == "flag":
        icon = {"OK": "✅", "WATCH": "⚠️", "FLAG": "🚩"}.get(b.get("status", ""), "•")
        out.append(f"> {icon} **{b.get('check','')}** [{b.get('status')}] {b.get('md','')}")
    cites = b.get("citations") or b.get("provenance") or []
    bad = [c for c in cites if not resolve(c)]
    if bad:
        out.append(f"> ⚠️ *unresolved citation(s): {', '.join(str(x) for x in bad)}*")
    out.append("")
    return out


def composer_node(state) -> dict:
    profile, comp = state["profile"], state.get("computed", {})
    evidence_ids = {e["id"] for e in state.get("evidence_pool", [])}
    calc_ids = set(comp.get("computed_financials", {}).keys()) | {
        "peer_table", "valuation_context", "guidance_scorecard"} | {
        f"forensic.{f['check']}" for f in comp.get("forensic_flags", [])}

    stats = {"total": 0, "unresolved": 0}

    def resolve(cite) -> bool:
        stats["total"] += 1
        c = str(cite)
        ok = (c in evidence_ids or _UUID_RE.match(c) and c in evidence_ids or
              (c.startswith("calc:") and (c[5:] in calc_ids or
                                          c[5:].split(".")[0] in calc_ids)) or
              c.startswith("mem_"))
        if not ok:
            stats["unresolved"] += 1
        return bool(ok)

    lines = [f"# {profile['name']} ({profile['ticker']}) — AlphaNet Research Report", ""]
    lines.append("> Automated research synthesis, not investment advice. No "
                 "Buy/Sell/Hold view is expressed or implied. Verify figures "
                 "against primary sources.")
    lines.append("")
    lines += _snapshot(state)

    failed_by_section = {}
    for v in (state.get("verification") or {}).values():
        if v["verdict"] not in ("supported",):
            failed_by_section.setdefault(v["section"], []).append(v)

    for letter in "BCDEFGHIJ":
        env = state.get(f"envelope_{letter}")
        lines.append(f"## {letter}. {_SECTION_TITLES[letter]}")
        lines.append("")
        if not env:
            lines.append("_Not generated._")
            lines.append("")
            continue
        for b in env.get("blocks", []):
            lines += _render_block(b, resolve)
        insuff = env.get("insufficiencies") or []
        if insuff:
            lines.append("<details><summary>Not found in sources</summary>")
            lines.append("")
            for i in insuff:
                lines.append(f"- {i}")
            lines.append("</details>")
            lines.append("")
        fails = failed_by_section.get(letter, [])
        if fails:
            lines.append(f"> ⚠️ *{len(fails)} claim(s) in this section failed "
                         f"verification against cited evidence:*")
            for f in fails[:5]:
                lines.append(f"> - \"{f['text']}\" — {f['verdict']}: {f['note']}")
            lines.append("")

    # K
    lines.append("## K. Sources & Provenance")
    lines.append("")
    by_url = {}
    for e in state.get("evidence_pool", []):
        by_url.setdefault(e["url"], {"title": e["title"], "doc_class": e["doc_class"],
                                     "count": 0})["count"] += 1
    for url, meta in sorted(by_url.items(), key=lambda kv: kv[1]["doc_class"]):
        lines.append(f"- **{meta['title']}** ({meta['doc_class']}, "
                     f"{meta['count']} evidence rows) — {url}")
    verif = state.get("verification") or {}
    supported = sum(1 for v in verif.values() if v["verdict"] == "supported")
    lines.append("")
    lines.append(f"**Quality badge:** {stats['total'] - stats['unresolved']}/"
                 f"{stats['total']} citations resolved · "
                 f"{supported}/{len(verif)} verified claims supported · "
                 f"model {get_active_model()} · run {state.get('run_id') or 'local'}")

    markdown = "\n".join(lines)

    os.makedirs(REPORTS_DIR, exist_ok=True)
    safe = re.sub(r"[^A-Za-z0-9_-]+", "_", profile["ticker"]).strip("_")
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    path = os.path.join(REPORTS_DIR, f"{safe}_{ts}.md")
    with open(path, "w", encoding="utf-8") as f:
        f.write(markdown)

    if state.get("persist"):
        sections_json = {f"section_{l}": state.get(f"envelope_{l}") for l in "BCDEFGHIJ"}
        sections_json["snapshot_md"] = "\n".join(_snapshot(state))
        sections_json["final_report_md"] = markdown
        sections_json["run_id"] = state.get("run_id") or None
        sections_json["quality"] = {**stats, "verified_supported": supported,
                                    "verified_total": len(verif)}
        try:
            _, version = db.save_report_version(profile["entity_id"], sections_json)
            print(f"[s8_composer] saved report_versions v{version}")
        except Exception as e:
            print(f"  [s8][warn] report_versions persist failed: {e}")

    print(f"[s8_composer] report written to {path} "
          f"({stats['total']-stats['unresolved']}/{stats['total']} citations resolved)")
    return {"final_report_md": markdown, "report_path": path}
