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
            names = [vital["metric_id"], calc_key]
            names += [f"{n}{suffix}" for n in (vital["metric_id"], calc_key)
                      for suffix in ("_series", "_pct_series", "_ttm", "_pct")]
            for k in dict.fromkeys(names):    # de-dup, keep order
                c = cf.get(k)
                if c and isinstance(c, dict) and ("points" in c or "value" in c):
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
        if b.get("title"):      # J rendered 3 untitled lists back-to-back
            out.append(f"**{b['title']}**")
            out.append("")
        for it in b.get("items", []):
            sev = f" `{it['severity']}`" if it.get("severity") else ""
            out.append(f"{it.get('rank','-')}. **{it.get('title','')}**{sev} — {it.get('md','')}")
            if it.get("monitorable"):
                out.append(f"   - *Watch:* {it['monitorable']}")
    elif t == "flag":
        icon = {"OK": "✅", "WATCH": "⚠️", "FLAG": "🚩"}.get(b.get("status", ""), "•")
        out.append(f"> {icon} **{b.get('check','')}** [{b.get('status')}] {b.get('md','')}")
    cites = list(b.get("citations") or []) + list(b.get("provenance") or [])
    if t == "metric_card":      # per-metric provenance was escaping the check
        cites += [m["provenance"] for m in b.get("metrics", []) if m.get("provenance")]
    bad = [c for c in dict.fromkeys(str(c) for c in cites) if not resolve(c)]
    if bad:
        out.append(f"> ⚠️ *unresolved citation(s): {', '.join(str(x) for x in bad)}*")
    out.append("")
    return out


# Round 5.6 — the envelope/block contract as CODE (the versioned API a
# future UI renders against; no external schema lib by design).
ENVELOPE_CONTRACT_VERSION = "1.0.0"

_BLOCK_REQUIRED = {
    "narrative": ("id", "md"),
    "metric_card": ("id", "metrics"),
    "table": ("id", "columns", "rows"),
    "ranked_list": ("id", "items"),
    "flag": ("id", "check", "status", "md"),
}


def validate_envelope(env: dict) -> list:
    """Structural contract check for one section envelope. Returns a
    list of human-readable issues (empty = conformant). Non-fatal at
    compose time — the report renders regardless (honest degradation),
    but every violation lands in the log and the run manifest."""
    issues = []
    if not isinstance(env, dict):
        return ["envelope is not an object"]
    if not env.get("section"):
        issues.append("missing 'section'")
    blocks = env.get("blocks")
    if not isinstance(blocks, list) or not blocks:
        issues.append("blocks missing or empty")
        blocks = []
    for i, b in enumerate(blocks):
        if not isinstance(b, dict):
            issues.append(f"block[{i}] not an object")
            continue
        t = b.get("type")
        req = _BLOCK_REQUIRED.get(t)
        if req is None:
            issues.append(f"block[{i}] unknown type '{t}'")
            continue
        for k in req:
            if not b.get(k):
                issues.append(f"block[{i}]({t}) missing '{k}'")
        if t == "flag" and b.get("status") not in ("OK", "WATCH", "FLAG"):
            issues.append(f"block[{i}] invalid flag status '{b.get('status')}'")
    for i, c in enumerate(env.get("claims") or []):
        if not isinstance(c, dict) or not c.get("text") \
                or not isinstance(c.get("evidence_ids"), list):
            issues.append(f"claim[{i}] missing text or evidence_ids list")
    if env.get("insufficiencies") is not None \
            and not isinstance(env["insufficiencies"], list):
        issues.append("insufficiencies not a list")
    return issues


def composer_node(state) -> dict:
    profile, comp = state["profile"], state.get("computed", {})
    citation_labels = state.get("citation_labels") or {}
    evidence_ids = {e["id"] for e in state.get("evidence_pool", [])}
    calc_ids = set(comp.get("computed_financials", {}).keys()) | {
        "peer_table", "valuation_context", "guidance_scorecard"} | {
        f"forensic.{f['check']}" for f in comp.get("forensic_flags", [])} | \
        set(comp.get("valuation_context", {}).keys())   # pb, pe_1y_path, ...

    # every block id from every section is citable as sec:<LETTER>.<block_id>
    # (D1/D2/D3 are the Phase 4 statement-forensic sub-sections)
    block_ids = set()
    for letter in ("B", "C", "D", "D1", "D2", "D3", "E", "F", "G", "H", "I", "J"):
        env = state.get(f"envelope_{letter}") or {}
        for b in env.get("blocks", []):
            if b.get("id"):
                block_ids.add(f"{letter}.{b['id']}")
                block_ids.add(str(b["id"]))
    # 8+ hex chars uniquely identify an evidence row in practice
    prefix_index: dict[str, int] = {}
    for e in evidence_ids:
        prefix_index[str(e)[:8]] = prefix_index.get(str(e)[:8], 0) + 1

    # edge:/trail: citations resolve against the same deterministic ids
    # the context renderers labelled them with
    from src.pipeline.s4_synth import edge_id, trail_id, event_id
    edge_ids = {edge_id(e) for e in state.get("supply_edges", [])}
    trail_ids = {trail_id(t) for t in state.get("guidance_evolution", [])}
    event_ids = {event_id(ev) for ev in state.get("events", [])}

    stats = {"total": 0, "unresolved": 0}

    def resolve(cite) -> bool:
        stats["total"] += 1
        # labels are shown as [edge:x]/[sec:x] — models sometimes cite the
        # brackets too; strip them before matching
        c = str(cite).strip().strip("[]")
        ok = False
        # Citation labels FIRST: "AR.17" has the same <X>.<y> shape as a
        # bare upstream block id, so the exact-match label lookup has to
        # win before the sec:/block-id paths get a chance at it.
        if c in citation_labels:
            ok = True
        elif c in evidence_ids or c.startswith("mem_"):
            ok = True                       # retained uuid fallback
        elif c.startswith("calc:"):
            body = c[5:]
            ok = body in calc_ids or body.split(".")[0] in calc_ids
        elif c.startswith("sec:"):
            body = c[4:]
            ok = body in block_ids or body.split(".", 1)[-1] in block_ids
        elif c.startswith("edge:"):
            ok = c[5:] in edge_ids
        elif c.startswith("trail:"):
            ok = c[6:] in trail_ids
        elif c.startswith("event:"):
            ok = c[6:] in event_ids
        elif c.startswith("evidence:"):
            # a label, a full uuid, OR a unique 8-hex prefix (models write
            # every form; the bare-prefix path below never saw prefixed ones)
            body = c.split(":", 1)[1]
            ok = body in citation_labels or body in evidence_ids or (
                re.fullmatch(r"[0-9a-f]{8,}", body) is not None
                and prefix_index.get(body[:8], 0) == 1)
        elif c in block_ids:
            ok = True                       # bare upstream block id
        elif re.fullmatch(r"[0-9a-f]{8,}", c):
            ok = prefix_index.get(c[:8], 0) == 1    # unique uuid prefix
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

    def _render_env(env, letter):
        for b in env.get("blocks", []):
            lines.extend(_render_block(b, resolve))
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

    _D_SUBS = (("D1", "Profit & Loss (forensic)"),
               ("D2", "Balance Sheet (forensic)"),
               ("D3", "Cash Flow (forensic)"))

    # Round 5.6: the envelope contract, VALIDATED at compose time —
    # this is the API a future UI renders; violations are reported
    # loudly (log + manifest) but never kill the report.
    schema_issues = {}
    for letter in ("B", "C", "D", "D1", "D2", "D3", "E", "F", "G", "H", "I", "J"):
        env = state.get(f"envelope_{letter}")
        if env:
            probs = validate_envelope(env)
            if probs:
                schema_issues[letter] = probs
                print(f"  [s8] envelope contract violation(s) in {letter}: "
                      f"{'; '.join(probs[:4])}"
                      + (f" (+{len(probs)-4} more)" if len(probs) > 4 else ""))

    for letter in "BCDEFGHIJ":
        env = state.get(f"envelope_{letter}")
        lines.append(f"## {letter}. {_SECTION_TITLES[letter]}")
        lines.append("")
        if letter == "D":
            # Phase 4: D = statement sub-sections + integrated synthesis
            any_sub = False
            for sub, subtitle in _D_SUBS:
                sube = state.get(f"envelope_{sub}")
                if not sube:
                    continue
                any_sub = True
                lines.append(f"### {sub}. {subtitle}")
                lines.append("")
                _render_env(sube, sub)
            if env:
                if any_sub:
                    lines.append("### Cross-statement synthesis & scoreboard")
                    lines.append("")
                _render_env(env, "D")
            elif not any_sub:
                lines.append("_Not generated._")
                lines.append("")
            continue
        if not env:
            lines.append("_Not generated._")
            lines.append("")
            continue
        _render_env(env, letter)

    # K — the citation LEGEND: every label in the report resolves here.
    # (Ordered by the label assignment, so company primaries come first
    # and the numbered tail follows in citation order.)
    lines.append("## K. Sources & Provenance")
    lines.append("")
    docs = state.get("citation_docs") or []
    if docs:
        for d in docs:
            lines.append(f"- **[{d['label']}]** {d['title']} "
                         f"({d['doc_class']}, {d['rows']} evidence rows) — "
                         f"{d['url']}")
    else:
        by_url = {}
        for e in state.get("evidence_pool", []):
            by_url.setdefault(e["url"], {"title": e["title"],
                                         "doc_class": e["doc_class"],
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
        sections_json = {f"section_{l}": state.get(f"envelope_{l}")
                         for l in ("B", "C", "D", "D1", "D2", "D3",
                                   "E", "F", "G", "H", "I", "J")}
        sections_json["claim_checks"] = state.get("claim_checks") or []
        sections_json["snapshot_md"] = "\n".join(_snapshot(state))
        sections_json["final_report_md"] = markdown
        sections_json["run_id"] = state.get("run_id") or None
        sections_json["quality"] = {**stats, "verified_supported": supported,
                                    "verified_total": len(verif)}
        sections_json["envelope_contract_version"] = ENVELOPE_CONTRACT_VERSION
        # The run's citation labels ride WITH the report: labels are
        # run-scoped (they depend on the whole pool), so without this a
        # stored report could not be re-resolved later — and the UI needs
        # exactly this map to render footnote markers. No DDL: jsonb.
        sections_json["citation_map"] = {
            "labels": citation_labels,           # label -> evidence uuid
            "documents": state.get("citation_docs") or [],
        }
        try:
            _, version = db.save_report_version(profile["entity_id"], sections_json)
            print(f"[s8_composer] saved report_versions v{version}")
        except Exception as e:
            print(f"  [s8][warn] report_versions persist failed: {e}")

    # Round 5.6: per-run report manifest — rides the telemetry sidecar
    # (a future product dashboard reads this, not the markdown)
    try:
        import src.llm as llm
        llm.telemetry_extra["manifest"] = {
            "report_path": path,
            "envelope_contract_version": ENVELOPE_CONTRACT_VERSION,
            "citations_total": stats["total"],
            "citations_unresolved": stats["unresolved"],
            "verified_supported": supported,
            "verified_total": len(verif),
            "schema_issues": schema_issues,
            "sections": {l: {"blocks": len((state.get(f"envelope_{l}") or {}).get("blocks", [])),
                             "claims": len((state.get(f"envelope_{l}") or {}).get("claims", []))}
                         for l in ("B", "C", "D", "D1", "D2", "D3",
                                   "E", "F", "G", "H", "I", "J")},
        }
    except Exception:
        pass

    print(f"[s8_composer] report written to {path} "
          f"({stats['total']-stats['unresolved']}/{stats['total']} citations resolved)")
    return {"final_report_md": markdown, "report_path": path}
