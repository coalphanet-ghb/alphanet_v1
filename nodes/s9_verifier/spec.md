# s9_verifier — claim verification (LLM, cheap, batched)

## Purpose
The anti-hallucination backstop: check that claims are actually supported
by the evidence they cite. Narrow judgments, batched — far cheaper than
the generation that produced them.

## Inputs
- claims[] from all envelopes, each with its cited evidence texts inlined
- Verification policy (below)

## Policy (what gets verified)
- **100%:** every claim carrying a number; every claim under a FLAG
  block; every guidance-scorecard row; every H risk's evidence field
- **Sampled (~25%):** remaining narrative claims
- calc:* citations are NOT LLM-verified (deterministic lineage already
  guarantees them) — only evidence-cited claims

## Instructions (prompt body)
For each (claim, evidence excerpts) pair, answer ONLY from the excerpts:
- `supported` — the excerpts state or directly entail the claim
- `partial` — direction right, but the claim adds precision/scope the
  excerpts don't contain (say what exceeds)
- `unsupported` — the excerpts do not contain this
- `contradicted` — the excerpts state otherwise
No world knowledge. No benefit of the doubt on numbers: a claim of
"18.2%" against evidence of "about 18%" = partial, not supported.
Output per claim: {claim_id, verdict, offending_span?, note ≤20 words}.

## Batching
20–30 claims per call, grouped by source document so shared excerpts are
sent once. Budget ≈ 2–4 calls per report.

## Downstream
Verdicts → claims.verification_status (verified / failed:partial /
failed:unsupported / failed:contradicted). Composer removes or flags
dependent sentences (its spec §3). Failure PATTERNS (a node repeatedly
producing unsupported claims) are logged per node — that's the signal a
spec/prompt needs tightening.

## Quality checklist
- [ ] Numeric strictness applied (no rounding forgiveness)
- [ ] Verdicts based solely on provided excerpts
- [ ] Every 100%-tier claim covered before any sampling
- [ ] Per-node failure rates logged to runs metadata
