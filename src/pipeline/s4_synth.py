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


def edge_id(e: dict) -> str:
    """Deterministic citable id for a supply-chain edge. The composer
    recomputes the same ids from state to validate edge: citations, so
    this MUST stay pure content-derived (no counters)."""
    def slug(s):
        return re.sub(r"[^a-z0-9]+", "_", str(s or "").lower()).strip("_")[:32]
    return f"{slug(e.get('from_entity'))}__{slug(e.get('relation'))}__{slug(e.get('to_entity'))}"


def _edges_labeled(state, cap=40) -> str:
    """Entity-graph edges rendered with their citable [edge:<id>] labels
    (models were inventing edge: shorthand; now the label is supplied and
    the composer resolves exactly these)."""
    edges = state.get("supply_edges", [])[:cap]
    return "\n".join(f"[edge:{edge_id(e)}] {json.dumps(e, default=str)[:350]}"
                     for e in edges) or "(none)"


def _peer_packs(state, per_peer_chars=2000) -> str:
    """Phase 5.3: per-peer evidence packs — every pool passage mentioning
    the peer (screener 'about', sector prints, news) grouped under its
    name, so G can attribute gaps numerically AND cite sources."""
    out = []
    for p in state.get("peer_entities", [])[:8]:
        name = p["name"].split("(")[0].strip()
        # distinctive word tokens, not a raw prefix — passages say
        # "Motherson", never "Samvardhana Motherson Internatio..."
        keys = [w for w in name.lower().split() if len(w) >= 5][:2] \
            or [name.lower()]
        hits, used = [], 0
        for e in state.get("evidence_pool", []):
            hay = e["text"].lower() + " " + (e.get("title") or "").lower()
            if any(k in hay for k in keys):
                entry = f"  [{e['id']}] {e['text'][:400]}"
                if used + len(entry) > per_peer_chars:
                    break
                hits.append(entry)
                used += len(entry)
        if hits:
            out.append(f"PEER {name}:\n" + "\n".join(hits))
    return "\n\n".join(out) or "(none)"


def trail_id(t: dict) -> str:
    """Deterministic citable id for a guidance-evolution trail (same
    pattern as edge_id — the composer recomputes the set)."""
    return re.sub(r"[^a-z0-9]+", "_",
                  str(t.get("metric") or "").lower()).strip("_")[:40] or "unnamed"


def _trails_labeled(state, cap=20) -> str:
    trails = state.get("guidance_evolution", [])[:cap]
    return "\n".join(f"[trail:{trail_id(t)}] {json.dumps(t, default=str)[:400]}"
                     for t in trails) or "(none)"


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
        # Provider max (64K on Fireworks): reasoning models spend hidden
        # thinking tokens inside this budget before the visible envelope.
        # M3 occasionally enters a stochastic reasoning death-spiral and
        # exhausts ANY budget (observed: 167K then 230K chars of reasoning,
        # different nodes each time, same nodes fine on other runs) — so
        # truncation gets ONE retry with a fresh sample (documented
        # exception to the no-retry policy, alongside the extraction
        # reprompt-once: the failure is a sampling accident, not a
        # model/quota/input problem).
        # Two retryable-once failure shapes, both sampling accidents (same
        # documented-exception family as the extraction reprompt-once):
        # TRUNCATED (reasoning spiral) and "unparseable envelope" (a JSON
        # slip mid-document — longer envelopes under the claims-density
        # floor raised the odds). Anything else still aborts first-error.
        from src.llm import LLMError
        try:
            env = generate_json(system, user, max_tokens=64000)
        except LLMError as e:
            msg = str(e)
            if "TRUNCATED" in msg:
                reason = "reasoning-spiral truncation"
            elif "unparseable envelope" in msg:
                reason = "malformed JSON envelope"
            else:
                raise
            print(f"  [synth_{letter}] {reason} — retrying once with a "
                  f"fresh sample")
            env = generate_json(system, user, max_tokens=64000)
        env["section"] = letter

    if state.get("persist"):
        entry_id = db.save_knowledge_entry(
            "company", state["profile"]["entity_id"], f"section_{letter}",
            env, generated_by_run_id=state.get("run_id") or None)
        # Contract rule 3: a claim may only cite uuids it was GIVEN — the
        # run's evidence pool, not merely any row that exists in the DB.
        # Mangled/invented ids are stripped; a claim left without a single
        # valid id is not persisted (nothing to verify it against).
        pool_ids = {str(e["id"]) for e in state.get("evidence_pool", [])}
        claims, sources, stripped, skipped_claims = [], [], 0, 0
        for c in env.get("claims", []):
            ev_ids = [i for i in c.get("evidence_ids", []) if _UUID_RE.match(str(i))]
            valid = [i for i in ev_ids if str(i) in pool_ids]
            stripped += len(ev_ids) - len(valid)
            if not valid:
                skipped_claims += 1
                continue
            claims.append({"text": c.get("text", ""), "evidence_ids": valid,
                           "confidence": c.get("confidence")})
            sources.append(c)      # env claim behind each persisted row
        if stripped or skipped_claims:
            print(f"  [synth_{letter}] {stripped} claim evidence id(s) not in "
                  f"pool stripped; {skipped_claims} claim(s) left id-less — "
                  f"not persisted")
        if claims:
            try:
                ids = db.save_claims(entry_id, claims, strict=False)
                for c, cid in zip(sources, ids):
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


# --- Phase 4: statement-forensic wave (D1/D2/D3) + followup + synthesis ------

def d1_node(state):
    return run_section(state, "s4a_pl", "D1", {
        "COMPANY": state["profile"]["name"],
        "COMPUTED FINANCIALS (your ONLY source of numbers; P&L table = calc:pl_table)":
            _computed(state),
        "GUIDANCE SCORECARD (past guidance vs actuals)":
            _computed(state, keys=("guidance_scorecard",)),
        "OPEN GUIDANCE ITEMS (cross-examine every P&L-touching claim)":
            _pool(state, "guidance_items"),
        "GUIDANCE EVOLUTION (cross-quarter trails)":
            _trails_labeled(state),
        "CONCALL / RESULTS / RATING EVIDENCE (color + claims to test)":
            _evidence(state, ["concall", "results_pdf", "rating_rationale"], 40000),
        "COMPUTE INSUFFICIENCIES (state these as not-computable)": _insufficiencies(state),
    })


def d2_node(state):
    return run_section(state, "s4b_bs", "D2", {
        "COMPANY": state["profile"]["name"],
        "COMPUTED FINANCIALS (your ONLY source of numbers; BS table = calc:bs_table)":
            _computed(state),
        "FORENSIC BATTERY (render every WATCH/FLAG)": _flags(state),
        "AR / RATING / SHAREHOLDING EVIDENCE (borrowings, contingents, CWIP, pledge)":
            _evidence(state, ["annual_report", "rating_rationale", "shareholding"], 40000),
        "CONCALL COLOR (capex/debt/WC claims to cross-examine)":
            _evidence(state, ["concall"], 12000),
        "OPEN GUIDANCE ITEMS (capex/debt/WC claims live here too)":
            _pool(state, "guidance_items"),
        "COMPUTE INSUFFICIENCIES (state these as not-computable)": _insufficiencies(state),
    })


def d3_node(state):
    return run_section(state, "s4c_cf", "D3", {
        "COMPANY": state["profile"]["name"],
        "COMPUTED FINANCIALS (your ONLY source of numbers; CF table = calc:cf_table)":
            _computed(state),
        "FORENSIC BATTERY (cash-relevant checks)": _flags(state),
        "CONCALL / AR EVIDENCE (capex plans, payout intent, funding claims)":
            _evidence(state, ["concall", "annual_report"], 40000),
        "OPEN GUIDANCE ITEMS (FCF/capex/payout claims to cross-examine)":
            _pool(state, "guidance_items"),
        "GUIDANCE EVOLUTION (cross-quarter trails)":
            _trails_labeled(state),
        "COMPUTE INSUFFICIENCIES (state these as not-computable)": _insufficiencies(state),
    })


def _computed_lookup(comp: dict, req: dict) -> str:
    """Deterministic answer for target:'computed' follow-ups: match the
    request's keywords against calc ids and return the matching entries."""
    words = set()
    for w in (req.get("keywords") or []) + str(req.get("request", "")).split():
        w = w.strip(" ?.,()").lower().replace("-", "_")
        if len(w) >= 3:
            words.add(w)
    hits = []
    for fid, v in comp.items():
        fid_low = fid.lower()
        if any(w in fid_low or fid_low in w for w in words):
            hits.append(f"calc:{fid} = {json.dumps(v, default=str)[:600]}")
        if len(hits) >= 3:
            break
    return "\n".join(hits) if hits else "(no matching computed value exists)"


def s4d_node(state):
    """Bounded follow-up answering + claim_checks pooling. One iteration,
    <=2 requests per statement node, <=1 LLM call total. Never fails the
    run — an unanswerable request is answered as such."""
    checks, followups = [], []
    pool_ids = {e["id"] for e in state.get("evidence_pool", [])}
    bad_ids = 0
    for sub in ("D1", "D2", "D3"):
        env = state.get(f"envelope_{sub}") or {}
        for c in env.get("claim_checks") or []:
            c["statement"] = sub
            # models occasionally mangle an evidence uuid; a bad id here
            # propagates into F/H citations and fails resolution — null it
            # (keep the raw value for the audit trail)
            if c.get("evidence_id") and c["evidence_id"] not in pool_ids:
                c["evidence_id_raw"] = c.pop("evidence_id")
                c["evidence_id"] = None
                bad_ids += 1
            checks.append(c)
        reqs = env.get("followup_requests") or []
        if len(reqs) > 2:
            print(f"  [s4d] {sub} emitted {len(reqs)} follow-ups — keeping 2 (bound)")
        for r in reqs[:2]:
            r["statement"] = sub
            followups.append(r)
    if bad_ids:
        print(f"  [s4d] {bad_ids} claim-check evidence id(s) not in pool — "
              f"nulled (kept as evidence_id_raw)")

    comp = state.get("computed", {}).get("computed_financials", {})
    for r in followups:
        if r.get("target") == "computed":
            r["answer"] = _computed_lookup(comp, r)

    ev_reqs = [r for r in followups if r.get("target") == "evidence"]
    if ev_reqs and state.get("dry_run"):
        for r in ev_reqs:
            r["answer"] = "(dry run — no LLM)"
    elif ev_reqs:
        # keyword-filter the pool; ONE call answers all evidence requests
        pool = state.get("evidence_pool", [])
        selected, seen_ids = [], set()
        for r in ev_reqs:
            kws = [k.lower() for k in (r.get("keywords") or []) if len(str(k)) >= 3]
            for e in pool:
                if e["id"] in seen_ids or len(selected) >= 40:
                    continue
                text_low = e["text"].lower()
                if any(k in text_low for k in kws):
                    selected.append(e)
                    seen_ids.add(e["id"])
        if not selected:
            for r in ev_reqs:
                r["answer"] = "(no passages matched the keywords)"
        else:
            from src.specs import load_instructions
            passages = "\n\n".join(f"[{e['id']}] ({e['doc_class']}; {e['title']})\n"
                                   f"{e['text'][:500]}" for e in selected)
            questions = "\n".join(f"idx {i}: {r.get('request', '')}"
                                  for i, r in enumerate(ev_reqs))
            try:
                # 16K: the visible answers are small but reasoning tokens
                # count inside max_tokens on reasoning models
                result = generate_json(
                    load_instructions("s4d_followup"),
                    f"QUESTIONS:\n{questions}\n\nPASSAGES:\n{passages}",
                    temperature=0.0, max_tokens=16384)
                by_idx = {a.get("idx"): a for a in result.get("answers", [])}
                for i, r in enumerate(ev_reqs):
                    a = by_idx.get(i) or {}
                    r["answer"] = a.get("answer", "(no answer returned)")
                    r["evidence_ids"] = a.get("evidence_ids", [])
            except Exception as e:
                print(f"  [s4d][warn] follow-up call failed (continuing): {e}")
                for r in ev_reqs:
                    r["answer"] = "(follow-up call failed)"

    non_corr = sum(1 for c in checks if c.get("verdict") != "corroborated")
    print(f"[s4d_followup] {len(checks)} claim checks pooled "
          f"({non_corr} non-corroborated), {len(followups)} follow-ups answered")
    return {"claim_checks": checks, "followups": followups}


def d_node(state):
    """s4e — integrated financial synthesis (writes envelope_D)."""
    checks = state.get("claim_checks", [])
    followups = state.get("followups", [])
    return run_section(state, "s4_financials", "D", {
        "COMPANY": state["profile"]["name"],
        "SECTION D1 FINDINGS (P&L — cite as sec:D1.<block_id>)":
            _envelope_summary(state.get("envelope_D1"), 8000),
        "SECTION D2 FINDINGS (Balance Sheet — cite as sec:D2.<block_id>)":
            _envelope_summary(state.get("envelope_D2"), 8000),
        "SECTION D3 FINDINGS (Cash Flow — cite as sec:D3.<block_id>)":
            _envelope_summary(state.get("envelope_D3"), 8000),
        "CLAIM CHECKS (pooled — the scoreboard's rows, render ALL)":
            json.dumps(checks, default=str)[:8000],
        "FOLLOW-UP ANSWERS":
            json.dumps(followups, default=str)[:4000],
        "COMPUTED FINANCIALS (cross-statement calcs)": _computed(state),
        "FORENSIC BATTERY": _flags(state),
        "COMPUTE INSUFFICIENCIES": _insufficiencies(state),
    })


def e_node(state):
    return run_section(state, "s4_supply_chain", "E", {
        "COMPANY": state["profile"]["name"],
        "EVIDENCE (AR / rating / presentation)":
            _evidence(state, ["annual_report", "rating_rationale",
                              "investor_presentation", "concall"]),
        "SUPPLY-CHAIN EDGE CANDIDATES (tagged during ingestion)":
            _edges_labeled(state),
        "COMPUTED (RM share if available)": _computed(state),
    })


def f_node(state):
    checks = state.get("claim_checks", [])
    cred = (state.get("envelope_D") or {}).get("credibility_notes_for_F") or []
    return run_section(state, "s4_management", "F", {
        "COMPANY": state["profile"]["name"],
        "CLAIMS-VS-NUMBERS SCOREBOARD (statement forensics tested management "
        "claims against computed numbers — weigh non-corroborated verdicts "
        "in the credibility assessment, citing sec:D.<scoreboard block>)":
            json.dumps(checks, default=str)[:6000] or "(none)",
        "CREDIBILITY NOTES (from financial synthesis)":
            "\n".join(f"- {n}" for n in cred) or "(none)",
        "SECTION D SUMMARY (integrated financials)":
            _envelope_summary(state.get("envelope_D")),
        "GUIDANCE SCORECARD (calc — the join of past guidance vs actuals)":
            _computed(state, keys=("guidance_scorecard",)),
        "OPEN GUIDANCE ITEMS": _pool(state, "guidance_items"),
        "GUIDANCE EVOLUTION (cross-quarter trails from batched concall read)":
            _trails_labeled(state),
        "RECURRING CONCALL THEMES (incl. repeatedly dodged topics)":
            _pool(state, "recurring_themes", 15),
        "CONCALL EVIDENCE (4 quarters, incl. dodged questions)":
            _evidence(state, ["concall"], 40000),
        "GOVERNANCE EVIDENCE (AR / shareholding / rating / news)":
            _evidence(state, ["annual_report", "shareholding",
                              "rating_rationale", "news_batch"], 20000),
        "EVENTS": _pool(state, "events"),
        "COMPUTED (capital allocation inputs)": _computed(state),
    })


def g_node(state):
    return run_section(state, "s5_peers", "G", {
        "COMPANY": state["profile"]["name"],
        "PEER TABLE (calc:peer_table — your only numeric source)":
            _computed(state, keys=("peer_table",)),
        "PEER EVIDENCE PACKS (per-peer passages — use for numeric gap attribution)":
            _peer_packs(state),
        "PEER MENTIONS (tagged in sources)": _pool(state, "peer_mentions"),
        "SECTOR PRINTS (share data)": _evidence(state, ["sector_page"], 6000),
        "SECTION D SUMMARY (company-side consistency)":
            _envelope_summary(state.get("envelope_D"), 10000),
    })


def h_node(state):
    worst = state.get("computed", {}).get("peer_table", {}).get("worst_cells", [])
    g_env = state.get("envelope_G", {})
    g_risk = json.dumps(g_env.get("risk_candidates_for_H", worst), default=str)
    non_corr = [c for c in state.get("claim_checks", [])
                if c.get("verdict") != "corroborated"]
    d_risk = (state.get("envelope_D") or {}).get("risk_candidates_for_H") or []
    return run_section(state, "s5_risks", "H", {
        "COMPANY": state["profile"]["name"],
        "NON-CORROBORATED MANAGEMENT CLAIMS (from statement forensics — "
        "contradicted claims are risk candidates; cite the claim's evidence "
        "uuid or sec:D block)": json.dumps(non_corr, default=str)[:4000] or "(none)",
        "D RISK CANDIDATES (from financial synthesis)":
            json.dumps(d_risk, default=str)[:3000] or "(none)",
        "RISK-TAGGED EVIDENCE (pooled from ALL reads)":
            _evidence(state, None, 40000, tagged=["risk_signal"]),
        "RATING RATIONALE / RISK READS": _evidence(
            state, ["rating_rationale", "valuepickr", "news_batch"], 20000),
        "FORENSIC FLAGS": _flags(state),
        "PEER WORST-CELLS (from G)": g_risk,
        "SECTION G SUMMARY": _envelope_summary(state.get("envelope_G"), 10000),
        "SECTION D SUMMARY": _envelope_summary(state.get("envelope_D"), 10000),
        "ENTITY GRAPH EDGES": _edges_labeled(state),
    })


def c_node(state):
    edges = _edges_labeled(state, cap=200)
    return run_section(state, "s6_industry_macro", "C", {
        "COMPANY": state["profile"]["name"],
        "SECTOR EVIDENCE (association prints, outlooks)":
            _evidence(state, ["sector_page"], 40000),
        "MACRO EVIDENCE (recent + medium-term views per indicator)":
            _evidence(state, ["macro_page"], 40000),
        "ENTITY GRAPH (this company's dependencies — from E and seeds)": edges,
        "SECTION E SUMMARY (dependencies found)":
            _envelope_summary(state.get("envelope_E"), 10000),
        "SECTION D SUMMARY (computed sensitivities context)":
            _envelope_summary(state.get("envelope_D"), 10000),
        "COMPUTED": _computed(state),
    })


def i_node(state):
    return run_section(state, "s7_valuation", "I", {
        "COMPANY": state["profile"]["name"],
        "VALUATION CONTEXT (calc — your only multiples source; includes "
        "pe_1y_path, pb, pe_own_history)":
            _computed(state, keys=("valuation_context",)),
        "SECTION H SUMMARY (the year's risk events — candidate explanations "
        "for multiple moves)": _envelope_summary(state.get("envelope_H"), 8000),
        "GUIDANCE EVOLUTION (cross-quarter management guidance trail)":
            _trails_labeled(state),
        "PEER TABLE": _computed(state, keys=("peer_table",)),
        "SECTION D SUMMARY (growth/returns)": _envelope_summary(state.get("envelope_D"), 10000),
        "SECTION G SUMMARY": _envelope_summary(state.get("envelope_G"), 10000),
        "SECTION C SUMMARY (cycle position)": _envelope_summary(state.get("envelope_C"), 10000),
        "KNOWN GAPS": _insufficiencies(state),
    })


def j_node(state):
    sections = {}
    # Phase 5.1: J receives the FULL envelopes (1M-context budget)
    for letter in "BCDEFGHI":
        sections[f"SECTION {letter}"] = _envelope_summary(
            state.get(f"envelope_{letter}"), 100000)
    sections["COMPANY"] = state["profile"]["name"]
    return run_section(state, "s8_takeaways", "J", sections)
