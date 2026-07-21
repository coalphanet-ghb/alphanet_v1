"""
S9 — claim verification (LLM, batched). Spec: nodes/s9_verifier.
Checks evidence-cited claims against their cited passages. calc-cited
values are not LLM-verified (deterministic lineage covers them).
"""

import json

from src import db
from src.llm import generate_json, set_current_node, note_wasted_output

_SYSTEM = """You are a verification instrument. The EXCERPTS section lists
evidence excerpts ONCE each, labelled [E1], [E2], ... The CLAIMS section
lists claims; each claim's EVIDENCE line names the excerpt ids that are
its cited evidence. Judge every claim ONLY from its named excerpts:
- "supported": the excerpts state or directly entail the claim
- "partial": direction right, but the claim adds precision or scope the
  excerpts do not contain
- "unsupported": the excerpts do not contain this
- "contradicted": the excerpts state otherwise
No world knowledge. No rounding forgiveness on numbers: a claim of 18.2%
against evidence saying "about 18%" is "partial".

Each excerpt is preceded by its SOURCE metadata (document class, title,
page/timestamp). That metadata is part of the evidence: if a claim says
"in the Q4 FY26 concall" and the excerpt comes from a document titled
"Concall transcript (May 2026)" for that quarter, the attribution IS
supported — do not mark it partial merely because the body text omits the
quarter. Judge the substance against text + metadata together.
Reason briefly: one pass per claim, then verdict.
Return ONLY JSON: {"verdicts": [{"idx": <int>, "verdict": "<one of the four>", "note": "<=20 words"}]}"""

_BATCH = 20
_MAX_CALLS = 12     # paid model: verification is the cheapest quality lever.
                    # Round 5: 10→12 — claims volume grew once the density
                    # floors were enforced (209 tasks once hit the old cap
                    # and left 9 claims unverified; full coverage is the
                    # product feature)


def verifier_node(state) -> dict:
    if state.get("dry_run"):
        print("[s9_verifier] DRY RUN — skipped")
        return {"verification": {}}
    set_current_node("s9_verifier")       # Round 1: per-node telemetry

    # Phase 2.5: excerpts carry their document metadata — most "partial"
    # verdicts were the verifier not knowing WHICH concall/date an excerpt
    # came from, and penalising correct attributions.
    ev_by_id = {e["id"]: e for e in state.get("evidence_pool", [])}

    def _excerpt(eid: str) -> str:
        e = ev_by_id[eid]
        meta = f"[SOURCE: {e.get('doc_class', '?')}"
        if e.get("title"):
            meta += f" | {e['title']}"
        if e.get("page"):
            meta += f" | {e['page']}"
        meta += "]"
        # 1200 chars: the Phase-5 audit found verdicts failing on numbers
        # that sat just past the old 600-char cut
        return f"{meta}\n{e['text'][:1200]}"

    tasks = []
    for letter in ("B", "C", "D", "D1", "D2", "D3", "E", "F", "G", "H", "I", "J"):
        env = state.get(f"envelope_{letter}") or {}
        for c in env.get("claims", []):
            ids = [i for i in c.get("evidence_ids", []) if i in ev_by_id]
            if ids:
                tasks.append({"letter": letter, "claim": c,
                              "ev_ids": ids[:3]})
    # Phase 5.5: the scoreboard's ATTRIBUTIONS are verified too — does the
    # cited passage actually carry the management claim? (The verdict math
    # itself is deterministic-calc territory; the attribution is not.)
    for i, cc in enumerate(state.get("claim_checks") or []):
        eid = cc.get("evidence_id")
        if eid and eid in ev_by_id:
            tasks.append({"letter": "D", "kind": "claim_check", "cc_index": i,
                          "claim": {"text": "Management stated: "
                                            + str(cc.get("mgmt_claim", ""))[:300]},
                          "ev_ids": [eid]})
    if not tasks:
        print("[s9_verifier] no evidence-cited claims to verify")
        return {"verification": {}}

    verification = {}
    calls = 0
    for start in range(0, len(tasks), _BATCH):
        if calls >= _MAX_CALLS:
            print(f"  [s9] budget cap — {len(tasks)-start} claims left unverified")
            break
        batch = tasks[start:start + _BATCH]
        # Round 2.2: excerpt dedup — claims cluster on the same passages,
        # and the old rendering re-billed each 1200-char excerpt once per
        # citing claim. Render every unique excerpt ONCE per batch; claims
        # reference E<n> ids. Coverage untouched (every claim is still
        # judged against every excerpt it cites).
        index: dict = {}
        for t in batch:
            for eid in t["ev_ids"]:
                if eid not in index:
                    index[eid] = len(index) + 1
        excerpts = "\n\n".join(f"[E{n}] {_excerpt(eid)}"
                               for eid, n in index.items())
        claims_txt = "\n\n".join(
            f"idx {i}\nCLAIM: {t['claim'].get('text', '')}\nEVIDENCE: " +
            ", ".join(f"E{index[eid]}" for eid in t["ev_ids"])
            for i, t in enumerate(batch))
        user = f"EXCERPTS:\n{excerpts}\n\nCLAIMS:\n{claims_txt}"
        # 16K budget (reasoning tokens count inside max_tokens) + one
        # retry per batch: the spiral once truncated batch 1 at 4K and the
        # old break-on-first-failure left the whole report unverified.
        result = None
        for attempt in range(2):
            try:
                from src.config import REASONING_EFFORT_VERIFY
                result = generate_json(_SYSTEM, user, temperature=0.0,
                                       max_tokens=16384,
                                       reasoning_effort=REASONING_EFFORT_VERIFY)
                break
            except Exception as e:
                if attempt == 0 and ("TRUNCATED" in str(e)
                                     or "timed out" in str(e).lower()):
                    print(f"  [s9] reasoning-spiral/timeout — retrying "
                          f"batch once")
                    note_wasted_output("spiral")
                    continue
                print(f"  [s9][warn] verification call failed: {e}")
        if result is None:
            continue    # skip this batch, keep verifying the rest
        calls += 1
        for v in result.get("verdicts", []):
            i = v.get("idx")
            if i is None or i >= len(batch):
                continue
            t = batch[i]
            verdict = v.get("verdict", "unsupported")
            claim_id = t["claim"].get("claim_id")
            key = claim_id or (f"cc:{t['cc_index']}" if t.get("kind") == "claim_check"
                               else f"{t['letter']}:{i + start}")
            verification[key] = {
                "verdict": verdict, "note": v.get("note", ""),
                "text": t["claim"].get("text", "")[:120], "section": t["letter"],
                "kind": t.get("kind", "claim")}
            if state.get("persist") and claim_id:
                status = "verified" if verdict == "supported" else "failed"
                try:
                    db.update_claim_status(claim_id, status)
                except Exception:
                    pass

    failed = sum(1 for v in verification.values() if v["verdict"] != "supported")
    print(f"[s9_verifier] {len(verification)} claims checked, {failed} not fully supported")
    # Round 1.2: verifier trend stats ride the telemetry sidecar so the
    # 6–16% not-fully-supported noise becomes a monitorable trend.
    import src.llm as llm
    by_verdict: dict = {}
    for v in verification.values():
        by_verdict[v["verdict"]] = by_verdict.get(v["verdict"], 0) + 1
    llm.telemetry_extra["verifier"] = {
        "claims_checked": len(verification), "not_fully_supported": failed,
        "by_verdict": by_verdict, "batches": calls, "tasks_total": len(tasks)}
    return {"verification": verification}
