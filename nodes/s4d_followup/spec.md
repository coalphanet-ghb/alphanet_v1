# s4d_followup — bounded follow-up answering (deterministic + ≤1 LLM call)

## Purpose
Answer the `followup_requests[]` emitted by the statement nodes
(s4a/s4b/s4c), one iteration only. `target: "computed"` requests are
answered by Python (keyword lookup over the computed tables — zero LLM).
`target: "evidence"` requests are batched into ONE call answering ONLY
from a keyword-filtered passage pool. Also gathers the three nodes'
`claim_checks[]` into shared state for s4e/F/H. This node must never
fail the run: an unanswerable request is answered "(not answerable)".

## Bounds (hard)
- ≤2 requests per statement node (extras dropped, logged)
- ≤1 LLM call total, one iteration; no follow-ups to follow-ups
- Evidence pool for the call: keyword-matched passages only, capped

## Instructions

You answer analyst follow-up questions STRICTLY from the numbered
passages supplied — no other knowledge, no arithmetic. For each
question return the direct answer plus the passage ids it rests on.
If the passages do not contain the answer, say exactly
"not in supplied passages".
Return ONLY JSON:
{"answers": [{"idx": <int>, "answer": "<=60 words",
              "evidence_ids": ["<uuid>", ...]}]}
