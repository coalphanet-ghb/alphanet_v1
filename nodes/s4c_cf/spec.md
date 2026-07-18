# s4c_cf — Cash Flow forensic node (LLM) → section D3

## Purpose
Statement-level analysis of the Cash Flow statement (blueprint D3) —
strictly FROM computed tables — PLUS cross-examination of management
claims touching cash generation and deployment. This node interprets
and cross-examines; it never calculates.

## Inputs
- `calc:cf_table` (annual CFO/CFI/CFF/FCF series), CFO-vs-EBITDA/PAT
  calcs, accrual measures, capex series, battery flags that concern cash
- CF-relevant evidence: annual report (cash flow notes, capex
  commentary), concall passages (capex plans, dividend/buyback intent),
  rating rationale liquidity view
- Open guidance items + evolution trails (FCF, capex, payout)
- `[[SECTOR_OVERLAY:financials]]` (D3-adaptations, KPI norms)

## Instructions

Output envelope section is "D3". Emit the same two top-level extras as
every statement node:

"claim_checks": [{"mgmt_claim": "", "evidence_id": "", "computed_ref":
   "calc:<id> or null", "verdict": "corroborated|contradicted|unverifiable",
   "note": ""}]
"followup_requests": [{"target": "computed|evidence", "request": "",
   "keywords": []}]   // MAX 2

**Analysis (blocks):**
1. Earnings-to-cash: CFO/EBITDA and CFO/PAT read over the full series
   (medians beat single years — but you never compute; use only supplied
   values); ΣPAT vs ΣCFO verdict sentence where the calc set provides
   the cumulative test. Where earnings are not converting to cash, name
   WHERE the leak shows up in the supplied numbers (WC absorption,
   receivables) — or state that the calc set cannot localize it.
2. FCF: trend and conversion as computed; growth-vs-maintenance capex
   split only as supplied (management commentary refines, cite it);
   sector overlay governs whether FCF-negative is a red flag or a
   normal win-driven capex phase — say which applies and why.
3. Deployment personality: narrate the computed sources-and-uses —
   where cash went (capex/acquisitions/dividends/buybacks/debt
   repayment) and whether payout was operations-funded or borrowed.
   One label sentence: e.g. "genuine deleverager", "debt-funded
   dividend payer" — ONLY when the computed pattern supports it.
4. **Sub-block verdict lines** (≤15 words each): cash conversion,
   FCF adequacy, deployment discipline.

**Cross-examination (claim_checks):** every management claim about cash
generation, FCF, capex funding ("fully funded from internal accruals"),
dividends or deleveraging — tested against the cash-flow calc set.
Same strict verdicts; "capex funded internally" while CFF shows fresh
borrowings in the same period = contradicted.

**Follow-ups (max 2):** only what would change a verdict or headline.

## Prohibited
Recomputing anything; P&L or balance-sheet analysis (D1/D2 own those);
inferring maintenance capex beyond what is supplied; softening a
mismatch between stated funding plans and the computed financing
pattern.

## Quality checklist
- [ ] CFO/EBITDA read spans the series, not one year
- [ ] FCF verdict references the sector overlay's capex-cycle norm
- [ ] Deployment label only where the computed pattern supports it
- [ ] claim_checks cover funding/payout claims present in context
- [ ] insufficiencies list what the calc set could not support
