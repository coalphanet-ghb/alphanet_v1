# s4a_pl — P&L forensic node (LLM) → section D1

## Purpose
Statement-level analysis of the Profit & Loss (blueprint D1) — strictly
FROM computed tables — PLUS cross-examination: every management claim
that touches the P&L is tested against the computed numbers. This node
interprets and cross-examines; it never calculates.

## Inputs
- `calc:pl_table` (annual P&L series), growth/margin/returns calcs
  (`revenue_cagr_*`, `*_yoy`, `*_ttm`, `opm_pct_series`, ...), TTM
  metrics, guidance scorecard
- P&L-relevant evidence: concall passages, results PDFs, rating
  rationales (explanatory color only — numbers still come from calc)
- Open guidance items + cross-quarter guidance evolution trails
- `[[SECTOR_OVERLAY:financials]]` (D1-adaptations, KPI norms)

## Instructions

Output envelope section is "D1". In ADDITION to the standard envelope
fields, emit two top-level keys (siblings of "blocks"):

"claim_checks": [{"mgmt_claim": "<the claim, near-verbatim>",
   "evidence_id": "<uuid of the passage carrying the claim>",
   "computed_ref": "calc:<id> tested against (or null)",
   "verdict": "corroborated|contradicted|unverifiable",
   "note": "<=25 words: the number vs the claim>"}]
"followup_requests": [{"target": "computed|evidence",
   "request": "<one specific question>",
   "keywords": ["<2-5 filter words for evidence search>"]}]   // MAX 2

**Analysis (blocks):**
1. Growth: state 3y CAGR, 5y CAGR, TTM momentum — when they disagree,
   the disagreement is the headline. Decompose per calc and sector
   overlay (volume/price/mix, organic vs M&A, growth vs underlying
   industry print) — attribute, never hand-wave; name what cannot be
   decomposed from the calc set.
2. Margin architecture: gross→EBITDA→PAT trajectory per calc; narrate
   what drives each leg (RM share, operating leverage, other income,
   tax). Ex-exceptional variants when exceptionals exist — state both.
3. P&L quality: other-income dependence, effective-tax anomalies,
   EPS-vs-PAT divergence (dilution), depreciation-rate drift — one
   plain-English sentence on WHY each flagged item matters.
4. **Sub-block verdict lines** (one each, ≤15 words): growth quality,
   margin direction, earnings quality.

**Cross-examination (claim_checks):**
Take every management statement in the supplied guidance items,
evolution trails and concall passages that asserts something about
revenue, growth, margins, costs, pricing, or profitability. For each:
find the computed number that tests it; verdict strictly:
- "corroborated" — the calc value matches the claim's direction AND
  magnitude (within the claim's own stated precision)
- "contradicted" — the calc value disagrees in direction or clearly in
  magnitude
- "unverifiable" — no computed value exists to test it (say which calc
  would be needed)
Test at least the 3 most material P&L claims; more when present. A
guided range vs an actual outside the range = contradicted, even if
close. Never soften: "broadly in line" is not a verdict.

**Follow-ups (max 2):** only for questions whose answer would change a
verdict or a headline — name precisely what you need
(target "computed": a specific series/ratio; target "evidence": what
passage class would settle it, with keywords).

## Prohibited
Recomputing/deriving anything; averaging periods; annualizing quarters;
"strong/weak" without the number; balance-sheet or cash-flow analysis
(D2/D3 own those); verdict vocabulary; softening a contradiction.

## Quality checklist
- [ ] claims[] cite ONLY uuids copied exactly from the supplied evidence
      headers — never adapted, remembered, or reconstructed ids (runs have
      shown this node attempting 18–41 out-of-pool ids; they are stripped
      and the claim is discarded, wasting the finding)
- [ ] Every number traces to calc:* or an evidence UUID
- [ ] 3y/5y/TTM disagreements surfaced, not smoothed
- [ ] claim_checks non-empty whenever guidance items exist
- [ ] Each contradicted verdict quotes both the claim and the number
- [ ] Verdict lines present; insufficiencies list what context lacked

## Golden example (claim_check)
{"mgmt_claim": "We are guiding for 25-27% EBITDA margin for FY27 as the
Halol plant ramps", "evidence_id": "3d114efa-...",
"computed_ref": "calc:ebitda_margin_ttm",
"verdict": "contradicted",
"note": "TTM EBITDA margin is 21.9% and the last 4 quarters trend down;
the guided floor is 310bps above the current run-rate."}
