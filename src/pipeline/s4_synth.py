"""
Synthesis nodes S4–S8 (LLM). One generic runner; per-section context
assemblers mirror each node spec's Inputs. Prompts = envelope contract +
spec Instructions (+ sector overlays) + rendered context.
"""

import json
import re

from src import db
from src.llm import generate_json
from src.specs import assemble_prompt

_UUID_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")


# --- context renderers -------------------------------------------------------

def _evidence(state, doc_classes, max_chars=15000, tagged=None) -> str:
    out, used = [], 0
    for e in state.get("evidence_pool", []):
        if doc_classes and e["doc_class"] not in doc_classes:
            continue
        if tagged and not (set(tagged) & set(e.get("tags", []))):
            continue
        entry = f"[{e['id']}] ({e['doc_class']}; {e['title']}" + \
                (f"; {e['page']}" if e.get("page") else "") + f")\n{e['text']}\n"
        if used + len(entry) > max_chars:
            break
        out.append(entry)
        used += len(entry)
    return "\n".join(out) or "(none)"


def _computed(state, keys=("computed_financials",)) -> str:
    comp = state.get("computed", {})
    lines = []
    for key in keys:
        data = comp.get(key)
        if not data:
            continue
        lines.append(f"-- {key} (cite values as calc:<id>) --")
        if key == "computed_financials":
            for fid, v in data.items():
                lines.append(f"calc:{fid} = {json.dumps(v, default=str)}")
        else:
            lines.append(f"calc:{key} = {json.dumps(data, default=str)[:6000]}")
    return "\n".join(lines) or "(no computed data)"


def _flags(state) -> str:
    fl = state.get("computed", {}).get("forensic_flags", [])
    if not fl:
        return "(battery not computable)"
    return "\n".join(
        f"calc:forensic.{f['check']} [{f['status']}/{f['severity']}] {f['md']}"
        for f in fl)


def _pool(state, key, cap=30) -> str:
    items = state.get(key, [])[:cap]
    return "\n".join(f"- {json.dumps(i, default=str)[:400]}" for i in items) or "(none)"


def _envelope_summary(env: dict, max_chars=4000) -> str:
    """Upstream findings, each labelled with the exact citation form the
    reader must use (sec:<LETTER>.<block_id>) — models were citing these
    numbers to evidence uuids they never read (Phase 2.1/3b)."""
    if not env:
        return "(missing)"
    letter = env.get("section", "?")
    parts = []
    for b in env.get("blocks", []):
        ref = f"sec:{letter}.{b.get('id')}"
        if b.get("type") == "narrative":
            parts.append(f"[{ref}] {b.get('md', '')}")
        elif b.get("type") == "ranked_list":
            for it in b.get("items", []):
                parts.append(f"[{ref}] #{it.get('rank')} {it.get('title')}: "
                             f"{it.get('md', '')}")
        elif b.get("type") == "flag":
            parts.append(f"[{ref}] FLAG({b.get('status')}) {b.get('md', '')}")
        elif b.get("type") == "metric_card":
            for m in b.get("metrics", []):
                parts.append(f"[{ref}] {m.get('name')}: {m.get('value')} "
                             f"{m.get('unit', '')} ({m.get('period', '')})")
    return "\n".join(parts)[:max_chars] or "(empty)"


def _insufficiencies(state) -> str:
    return "\n".join(f"- {i}" for i in
                     state.get("computed", {}).get("insufficiencies", [])) or "(none)"


# --- generic runner ------------------------------------------------------------

def run_section(state, node_id: str, letter: str, context: dict) -> dict:
    if state.get("dry_run"):
        from src.pipeline.dry_run import synthetic_envelope
        env = synthetic_envelope(letter)
    else:
        system, user = assemble_prompt(node_id, state["pack"], context)
        # 32K: reasoning models spend hidden thinking tokens inside this
        # budget before the visible envelope — 16K truncated long sections.
        env = generate_json(system, user, max_tokens=32768)
        env["section"] = letter

    if state.get("persist"):
        entry_id = db.save_knowledge_entry(
            "company", state["profile"]["entity_id"], f"section_{letter}",
            env, generated_by_run_id=state.get("run_id") or None)
        claims = []
        for c in env.get("claims", []):
            ev_ids = [i for i in c.get("evidence_ids", []) if _UUID_RE.match(str(i))]
            claims.append({"text": c.get("text", ""), "evidence_ids": ev_ids,
                           "confidence": c.get("confidence")})
        if claims:
            try:
                ids = db.save_claims(entry_id, claims, strict=False)
                for c, cid in zip(env.get("claims", []), ids):
                    c["claim_id"] = cid
            except Exception as e:
                print(f"  [s4][warn] claims persist failed for {letter}: {e}")
    print(f"[synth_{letter}] done ({len(env.get('blocks', []))} blocks, "
          f"{len(env.get('claims', []))} claims)")
    return {f"envelope_{letter}": env}


# --- section nodes ---------------------------------------------------------------

def b_node(state):
    return run_section(state, "s4_business", "B", {
        "COMPANY": state["profile"]["name"],
        "EVIDENCE (annual report / presentation / screener / concall / news)":
            _evidence(state, ["annual_report", "investor_presentation",
                              "screener_page", "concall", "news_batch"]),
        "COMPUTED (margin stability, mix where available)": _computed(state),
        "COMPUTE INSUFFICIENCIES": _insufficiencies(state),
    })


def d_node(state):
    return run_section(state, "s4_financials", "D", {
        "COMPANY": state["profile"]["name"],
        "COMPUTED FINANCIALS (your ONLY source of numbers)": _computed(state),
        "FORENSIC BATTERY (render every WATCH/FLAG)": _flags(state),
        "GUIDANCE SCORECARD (margin/capex context)":
            _computed(state, keys=("guidance_scorecard",)),
        "CONCALL / RATING COLOR (explanatory evidence only — numbers still come from calc)":
            _evidence(state, ["concall", "rating_rationale", "results_pdf"], 10000),
        "COMPUTE INSUFFICIENCIES (state these as not-computable)": _insufficiencies(state),
    })


def e_node(state):
    return run_section(state, "s4_supply_chain", "E", {
        "COMPANY": state["profile"]["name"],
        "EVIDENCE (AR / rating / presentation)":
            _evidence(state, ["annual_report", "rating_rationale",
                              "investor_presentation", "concall"]),
        "SUPPLY-CHAIN EDGE CANDIDATES (tagged during ingestion)":
            _pool(state, "supply_edges"),
        "COMPUTED (RM share if available)": _computed(state),
    })


def f_node(state):
    return run_section(state, "s4_management", "F", {
        "COMPANY": state["profile"]["name"],
        "GUIDANCE SCORECARD (calc — the join of past guidance vs actuals)":
            _computed(state, keys=("guidance_scorecard",)),
        "OPEN GUIDANCE ITEMS": _pool(state, "guidance_items"),
        "CONCALL EVIDENCE (4 quarters, incl. dodged questions)":
            _evidence(state, ["concall"], 14000),
        "GOVERNANCE EVIDENCE (AR / shareholding / rating / news)":
            _evidence(state, ["annual_report", "shareholding",
                              "rating_rationale", "news_batch"], 8000),
        "EVENTS": _pool(state, "events"),
        "COMPUTED (capital allocation inputs)": _computed(state),
    })


def g_node(state):
    return run_section(state, "s5_peers", "G", {
        "COMPANY": state["profile"]["name"],
        "PEER TABLE (calc:peer_table — your only numeric source)":
            _computed(state, keys=("peer_table",)),
        "PEER MENTIONS (tagged in sources)": _pool(state, "peer_mentions"),
        "SECTOR PRINTS (share data)": _evidence(state, ["sector_page"], 6000),
        "SECTION D SUMMARY (company-side consistency)":
            _envelope_summary(state.get("envelope_D")),
    })


def h_node(state):
    worst = state.get("computed", {}).get("peer_table", {}).get("worst_cells", [])
    g_env = state.get("envelope_G", {})
    g_risk = json.dumps(g_env.get("risk_candidates_for_H", worst), default=str)
    return run_section(state, "s5_risks", "H", {
        "COMPANY": state["profile"]["name"],
        "RISK-TAGGED EVIDENCE (pooled from ALL reads)":
            _evidence(state, None, 12000, tagged=["risk_signal"]),
        "RATING RATIONALE / RISK READS": _evidence(
            state, ["rating_rationale", "valuepickr", "news_batch"], 8000),
        "FORENSIC FLAGS": _flags(state),
        "PEER WORST-CELLS (from G)": g_risk,
        "SECTION G SUMMARY": _envelope_summary(state.get("envelope_G")),
        "SECTION D SUMMARY": _envelope_summary(state.get("envelope_D")),
        "ENTITY GRAPH EDGES": _pool(state, "supply_edges"),
    })


def c_node(state):
    edges = _pool(state, "supply_edges")
    return run_section(state, "s6_industry_macro", "C", {
        "COMPANY": state["profile"]["name"],
        "SECTOR EVIDENCE (association prints, outlooks)":
            _evidence(state, ["sector_page"], 10000),
        "MACRO EVIDENCE (recent + medium-term views per indicator)":
            _evidence(state, ["macro_page"], 10000),
        "ENTITY GRAPH (this company's dependencies — from E and seeds)": edges,
        "SECTION E SUMMARY (dependencies found)":
            _envelope_summary(state.get("envelope_E")),
        "SECTION D SUMMARY (computed sensitivities context)":
            _envelope_summary(state.get("envelope_D")),
        "COMPUTED": _computed(state),
    })


def i_node(state):
    return run_section(state, "s7_valuation", "I", {
        "COMPANY": state["profile"]["name"],
        "VALUATION CONTEXT (calc — your only multiples source)":
            _computed(state, keys=("valuation_context",)),
        "PEER TABLE": _computed(state, keys=("peer_table",)),
        "SECTION D SUMMARY (growth/returns)": _envelope_summary(state.get("envelope_D")),
        "SECTION G SUMMARY": _envelope_summary(state.get("envelope_G")),
        "SECTION C SUMMARY (cycle position)": _envelope_summary(state.get("envelope_C")),
        "KNOWN GAPS": _insufficiencies(state),
    })


def j_node(state):
    sections = {}
    for letter in "BCDEFGHI":
        sections[f"SECTION {letter}"] = _envelope_summary(
            state.get(f"envelope_{letter}"), 2500)
    sections["COMPANY"] = state["profile"]["name"]
    return run_section(state, "s8_takeaways", "J", sections)
