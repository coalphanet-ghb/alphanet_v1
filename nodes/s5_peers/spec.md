# s5_peers — Peer Comparison writer (LLM) → section G

## Purpose
Write blueprint section G from the computed peer table. Reader-question:
*"Why own this one instead of its rivals?"* Core discipline: **explain
gaps or don't state them.** Also: hand H its risk candidates
(worst-cells).

## Inputs
- `peer_table` (calc: normalized metrics, ranks, gaps, worst_cells[])
- peer evidence passages (peer_mentions pool, sector prints with shares)
- section D envelope (for consistency of company-side numbers)
- `[[SECTOR_OVERLAY:peers]]` (pack columns, comparison conventions,
  known non-comparabilities)

## Instructions
1. **Peer-set declaration** (narrative, 2–3 sentences): who's in, why,
   and the mismatches (size, mix, listing history). Global reference peer
   labeled "context only — excluded from Indian stats". If the graph
   peer-set was thin/odd, say what's missing.
2. **The table** (table block, verbatim from calc:peer_table): universal
   columns (3y growth, margin-or-sector-equivalent, ROE/ROCE, leverage,
   CCC, capex intensity, primary multiple TTM) + pack columns. All same-
   period, same-basis — the calc guarantees it; you state it.
3. **Gap attribution** (narrative — the heart): for each material gap
   (top 3–4): WHY does it exist? Acceptable attributions: mix, scale,
   integration, geography, accounting policy (name it), cycle position,
   execution. Each attribution needs evidence or calc backing. A gap you
   cannot attribute is stated as unexplained — "the 9-point margin gap vs
   X is not explained by mix or scale in available disclosures" is a
   legitimate, valuable sentence.
4. **Honest ranking** (metric_card or short narrative): best-in-class /
   mid-pack / laggard per dimension. Every LAGGARD cell must appear —
   these are H's inputs. No burying.
5. **Share dynamics** (narrative, where sector prints exist): who is
   gaining/losing share per industry data (calc vs SIAM/FADA/sector
   series), stated in points with periods.

## Output additions
`"risk_candidates_for_H": [{"dimension":"EBITDA margin","gap":"-480bps vs
peer median","attribution":"unexplained","calc":"peer_table"}]`

## Prohibited
League-table prose without attribution; cherry-picked comparison periods;
mixing consolidated/standalone across the table (calc prevents it —
don't override); valuation VERDICTS from the multiple column (that's I's
percentile framing, and even I never renders verdicts).

## Quality checklist
- [ ] Every stated gap has attribution or an explicit "unexplained"
- [ ] Worst-cells all surfaced and exported to H
- [ ] Non-comparabilities declared (size, mix, accounting)
- [ ] Share gain/loss quantified in points where prints exist
