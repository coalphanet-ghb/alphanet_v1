# s3_compute — deterministic computation (Python, zero LLM)

## Purpose
Transform validated metric_observations into every derived number the
report uses. The LLM never computes; this node is the only source of
derived figures. Full lineage on every output.

## Inputs
- `metric_observations` (validated from s2 candidates: unit-normalized to
  ₹ crore / percent / units, period-typed, basis-tagged)
- sector pack (which sector_kpis formulas apply; which modules are N/A —
  e.g., banks skip working_capital/cashflow-industrial variants)
- peer set's metric_observations (for peers.py)
- guidance_items pool (for guidance.py join)
- price series / multiples inputs (screener extraction)

## Validation gate (before any computation)
1. Unit normalization with printed-unit audit trail; reject ambiguous
   candidates back to `insufficiencies`.
2. Same-basis guard: consolidated preferred; never mix in one series.
3. Period integrity: TTM built only from 4 same-basis quarters;
   CAGR endpoints recorded.
4. Outlier sanity: |YoY| > 200% on statement lines → cross-check against a
   second source before accepting; else flag `unverified_outlier`.

## Modules run (per ANALYST_KNOWLEDGE Part 3)
growth · margins · returns (DuPont 3/5-stage; RoA tree for lenders) ·
leverage (incl. implied-borrowing-rate & cash-yield tests) ·
working_capital (DSO/DIO/DPO/CCC series + divergence scores) ·
cashflow (CFO/EBITDA, Sloan accruals, ΣPAT vs ΣCFO, FCF, payout funding) ·
forensic (12-check battery + Piotroski/Altman-Z″/Beneish with components) ·
guidance (items × actuals join → scorecard) ·
peers (normalized table, ranks, gaps, worst-cells) ·
valuation (TTM multiples, own-history percentiles, peer rank, return
decomposition, normalized-earnings context if pack says cyclical) ·
sector_kpis (pack-registered formulas)

## Outputs (knowledge_entries, versioned)
- `computed_financials` — all series/ratios with {formula_id, input row
  ids, periods, basis}
- `forensic_flags` — each check {status OK/WATCH/FLAG, severity, inputs,
  one-line deterministic rationale}
- `guidance_scorecard` — per-item outcomes + delivery-rate stats
- `peer_table` — normalized comparison + worst_cells[] (→ s5_risks)
- `valuation_context` — multiples, percentiles, decomposition
- `compute_insufficiencies` — every metric that couldn't be computed and
  the missing input

## Quality checklist
- [ ] Every output value has complete lineage (formula + input ids)
- [ ] No mixed-basis series anywhere
- [ ] Flags carry deterministic rationales (template strings, not prose)
- [ ] Missing inputs produce insufficiencies, never silent NaN-drops
- [ ] Pack N/A modules actually skipped (no EBITDA for banks)
