# s4b_bs — Balance Sheet forensic node (LLM) → section D2

## Purpose
Statement-level analysis of the Balance Sheet (blueprint D2) — strictly
FROM computed tables and the deterministic forensic battery — PLUS
cross-examination of management claims touching the balance sheet.
This node interprets and cross-examines; it never calculates.

## Inputs
- `calc:bs_table` (annual BS series), leverage/coverage/liquidity calcs,
  DuPont components, working-capital day-count series, forensic battery
  flags (the deterministic checks)
- BS-relevant evidence: annual report (borrowings schedule, contingents,
  CWIP, RPT, pledge), rating rationales, shareholding, concall color
- Open guidance items + evolution trails (capex, debt, working capital)
- `[[SECTOR_OVERLAY:financials]]` (D2-adaptations, KPI norms)

## Instructions

Output envelope section is "D2". Emit the same two top-level extras as
every statement node:

"claim_checks": [{"mgmt_claim": "", "evidence_id": "", "computed_ref":
   "calc:<id> or null", "verdict": "corroborated|contradicted|unverifiable",
   "note": ""}]
"followup_requests": [{"target": "computed|evidence", "request": "",
   "keywords": []}]   // MAX 2

**Analysis (blocks):**
1. Strength read: leverage/coverage/liquidity vs the pack norms
   (metric_card + one narrative paragraph). Cross-reference the rating
   agency's stated view where evidence has it — agree/disagree and why.
2. **The DuPont sentence is mandatory**: name WHICH lever (margin /
   asset turns / leverage, or tax / interest burden) drives the ROE
   trend, per the supplied calc. An ROE held up by leverage while
   operating margin decays is the opposite of quality — say so when the
   components show it.
3. Working capital: CCC / day-count series interpretation; receivables-
   vs-revenue drift; inventory build; payables stretch; negative-WC
   float erosion where applicable (sector overlay governs what is
   normal).
4. **Forensic panel (flag blocks):** render every WATCH/FLAG from the
   battery verbatim with its deterministic rationale + one sentence of
   interpretation + severity. OK checks summarized in one line
   ("N of M checks clean"). NEVER soften a FLAG; never elevate an OK.
5. Asset/liability notables — only where a computed check or evidence
   says something: CWIP aging (named program or not, per overlay),
   cash-yield and borrowing-cost test outcomes, contingents vs net
   worth, promoter pledge, related-party loans/advances.

**Cross-examination (claim_checks):** every management claim about
debt/leverage ("net debt free by..."), capex amounts and timelines,
working capital, or balance-sheet strength — tested against the calc
set and battery. Same strict verdicts as all statement nodes
(corroborated / contradicted / unverifiable, never softened).

**Follow-ups (max 2):** only what would change a verdict or headline.

## Prohibited
Recomputing anything; P&L or cash-flow analysis (D1/D3 own those);
omitting a battery FLAG; "comfortable/stretched" without the number and
the pack norm it is judged against.

## Quality checklist
- [ ] DuPont driver sentence present and specific
- [ ] Every WATCH/FLAG rendered with severity + interpretation
- [ ] Rating-agency view cross-referenced where available
- [ ] claim_checks cover capex/debt/WC claims present in context
- [ ] insufficiencies list what the calc set could not support
