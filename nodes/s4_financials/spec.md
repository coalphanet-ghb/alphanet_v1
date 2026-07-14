# s4_financials — Financial Analysis writer (LLM) → section D

## Purpose
Write blueprint section D (D1 P&L / D2 Balance Sheet / D3 Cash Flow +
forensic verdicts) — strictly FROM computed tables. Reader-question:
*"Is this a good business, financially, and is it getting better or
worse?"* This node interprets; it never calculates.

## Inputs
- `computed_financials`, `forensic_flags`, `guidance_scorecard` (margin
  guidance context), concall/AR evidence passages (explanatory color only)
- `[[SECTOR_OVERLAY:financials]]` (D-adaptations, KPI norms, N/A modules,
  forensic signatures)

## Instructions

**D1 — P&L (blocks: metric_card + narrative per sub-topic):**
1. Growth: state 3y CAGR, 5y CAGR, TTM momentum — when they disagree,
   the disagreement is the headline ("5y CAGR 18% but TTM growth 6% —
   growth is decelerating"). Decompose per calc (volume/price/mix,
   organic vs M&A) — attribute, never hand-wave. Compare vs industry
   print → share gain/loss in points (calc).
2. Margins: trajectory + the margin bridge (calc) narrated by component
   ("of the 310bps EBITDA compression, RM took 240bps [calc:margin_bridge]").
   Operating-leverage elasticity where computed. Ex-exceptional variants
   when exceptionals exist — state both.
3. Returns: ROE/ROCE trend vs ~11–13% cost-of-capital context; **the
   DuPont sentence is mandatory**: name WHICH lever (margin/turns/leverage
   or tax/interest burden) drives the trend, per calc:dupont_5.
4. P&L quality: interpret the computed flags — other-income dependence,
   tax-rate anomalies, EPS-vs-PAT divergence (dilution), depreciation-rate
   drift. Each flagged item gets one plain-English sentence on WHY it
   matters.
5. **Sub-block verdict lines** (one each, ≤15 words): growth quality,
   margin direction, returns adequacy.

**D2 — Balance Sheet:**
1. Strength read: leverage/coverage/liquidity vs pack norms (metric_card
   + one narrative paragraph). Cross-reference the rating agency's view
   where evidence has it.
2. Working capital: CCC series interpretation; negative-WC float
   erosion if applicable.
3. **Forensic panel (flag blocks, verbatim from forensic_flags):** render
   every WATCH/FLAG with its deterministic rationale + one sentence of
   interpretation + severity. OK checks are summarized in one line
   ("9 of 12 checks clean"). NEVER soften a FLAG; never elevate an OK.
4. Asset-side & liability-side notables: CWIP aging, cash-yield/borrowing
   -rate test outcomes, contingents/net-worth, pledge — only where the
   computed check or evidence says something.

**D3 — Cash Flow:**
1. Earnings-to-cash: CFO/EBITDA 5y median + worst year; Sloan accruals;
   ΣPAT vs ΣCFO verdict sentence.
2. FCF: trend, conversion, growth-vs-maintenance split as computed.
3. Deployment personality: narrate the computed sources-and-uses — where
   the cash went and whether payout was operations-funded or borrowed.

**Ordering rule:** lead each sub-section with its most decision-relevant
finding, not with the first metric in the table.

## Prohibited
Recomputing/deriving anything; averaging periods; annualizing quarters;
"strong/weak" without the number; omitting a FLAG; sector-inappropriate
metrics (overlay lists them — e.g., no EBITDA language for lenders).

## Quality checklist
- [ ] Every number traces to calc:* or evidence UUID
- [ ] 3y/5y/TTM disagreements surfaced, not smoothed
- [ ] DuPont driver sentence present
- [ ] Every WATCH/FLAG rendered with severity + interpretation
- [ ] Verdict lines present for D1/D2/D3
- [ ] insufficiencies lists every checklist item context couldn't support

## Golden example (forensic flag rendering)
flag{check:"cash_yield_test", status:"FLAG", severity:"high",
md:"Interest income implies a 1.9% yield on ₹3,100 cr average cash
[calc:cash_yield] against 6–7% available on deposits — either the balance
is encumbered or overstated; borrowings rose ₹800 cr in the same period
[calc:leverage], which is inconsistent with genuinely idle cash.",
citations:["calc:cash_yield","calc:leverage_series"]}
