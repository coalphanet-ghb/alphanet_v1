"""
S9 — claim verification (LLM, batched). Spec: nodes/s9_verifier.
Checks evidence-cited claims against their cited passages. calc-cited
values are not LLM-verified (deterministic lineage covers them).
"""

import json

from src import db
from src.llm import generate_json

_SYSTEM = """You are a verification instrument. For each (claim, evidence)
pair below, judge ONLY from the evidence excerpts provided:
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
Return ONLY JSON: {"verdicts": [{"idx": <int>, "verdict": "<one of the four>", "note": "<=20 words"}]}"""

_BATCH = 20
_MAX_CALLS = 8      # paid model: verification is the cheapest quality lever


def verifier_node(state) -> dict:
    if state.get("dry_run"):
        print("[s9_verifier] DRY RUN — skipped")
        return {"verification": {}}

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
        return f"{meta}\n{e['text'][:600]}"

    tasks = []
    for letter in "BCDEFGHIJ":
        env = state.get(f"envelope_{letter}") or {}
        for c in env.get("claims", []):
            ids = [i for i in c.get("evidence_ids", []) if i in ev_by_id]
            if ids:
                tasks.append({"letter": letter, "claim": c,
                              "evidence": [_excerpt(i) for i in ids[:3]]})
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
        user = "\n\n".join(
            f"idx {i}\nCLAIM: {t['claim'].get('text','')}\nEVIDENCE:\n" +
            "\n".join(f"- {x}" for x in t["evidence"])
            for i, t in enumerate(batch))
        try:
            result = generate_json(_SYSTEM, user, temperature=0.0, max_tokens=4096)
        except Exception as e:
            print(f"  [s9][warn] verification call failed: {e}")
            break
        calls += 1
        for v in result.get("verdicts", []):
            i = v.get("idx")
            if i is None or i >= len(batch):
                continue
            t = batch[i]
            verdict = v.get("verdict", "unsupported")
            claim_id = t["claim"].get("claim_id")
            verification[claim_id or f"{t['letter']}:{i+start}"] = {
                "verdict": verdict, "note": v.get("note", ""),
                "text": t["claim"].get("text", "")[:120], "section": t["letter"]}
            if state.get("persist") and claim_id:
                status = "verified" if verdict == "supported" else "failed"
                try:
                    db.update_claim_status(claim_id, status)
                except Exception:
                    pass

    failed = sum(1 for v in verification.values() if v["verdict"] != "supported")
    print(f"[s9_verifier] {len(verification)} claims checked, {failed} not fully supported")
    return {"verification": verification}
