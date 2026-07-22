# s4_financials — integrated financial synthesis (s4e, LLM) → section D

## Purpose
Integrate the three statement-forensic envelopes (D1 P&L, D2 Balance
Sheet, D3 Cash Flow) into blueprint section D: cross-statement
triangulation, quality-of-earnings verdict, ratio-vs-pack-norms, and
the claims-vs-numbers scoreboard. Reader-question: *"Is this a good
business, financially, and is it getting better or worse?"* This node
synthesizes ACROSS statements; single-statement findings are cited from
the D1/D2/D3 blocks (sec:D1.<id> etc.), never re-derived.

## Inputs
- D1/D2/D3 envelope summaries (blocks pre-labelled [sec:D1.x] etc.)
- Pooled `claim_checks[]` from the statement nodes + follow-up answers
- `computed_financials`, forensic battery, guidance scorecard (for
  cross-statement reads the statement nodes could not make alone)
- `[[SECTOR_OVERLAY:financials]]` (norms, N/A modules)

## Instructions

Output envelope section is "D". Also emit two top-level extras:

"risk_candidates_for_H": [{"risk": "<one line>", "source":
   "sec:D*.<block> or claim_check", "severity": "low|medium|high"}]
   — every contradicted claim_check and every high-severity forensic
   finding becomes a candidate.
"credibility_notes_for_F": ["<one line per non-corroborated claim_check:
   what management said vs what the numbers show>"]

**Blocks:**
1. **Integrated verdict narrative** (lead block): the one-paragraph
   answer to the reader-question, built ONLY from D1/D2/D3 findings
   (cite sec:D1/D2/D3 blocks) and cross-statement calcs. Lead with the
   most decision-relevant finding, not the first metric.
2. **Cross-statement triangulation**: run the fraud-lens pairings the
   supplied data can support — revenue vs receivables vs CFO
   (aggressive recognition), PAT vs cash tax paid, EBITDA vs CFO
   conversion, cash-vs-borrowings-vs-interest-income coherence, capex
   vs asset turnover vs commissioning, depreciation-rate drift.
   For each pairing state OK or the anomaly, citing the D-blocks or
   calc ids that carry the inputs. Pairings the data cannot support go
   to insufficiencies by name.
3. **DuPont driver sentence** (from D2, cited sec:D2.*) restated in the
   integrated context: which lever drives ROE and whether the P&L and
   CF stories are consistent with it.
4. **Quality of earnings**: one verdict paragraph joining D1's earnings
   quality, D3's cash conversion, and the accrual/battery evidence.
5. **Ratio-vs-pack-norms table**: company's key ratios against the
   sector KPI norms supplied (quote norms as 'sector norm'); flag
   outside-range cells.
6. **Claims-vs-numbers scoreboard (table block, mandatory)**: one row
   per claim_check — claim (shortened), computed_ref, verdict, note.
   Corroborated / contradicted / unverifiable counts in the title.
   NEVER drop a contradicted row. Every cell holds that row's own value
   for that column ("—" when absent) — never a number from another row.
7. **Sub-block verdict lines** for D1/D2/D3 (one each, ≤15 words,
   citing the sub-envelope).

## Prohibited
Recomputing or re-deriving statement-level findings (cite sec:D1/D2/D3);
arithmetic; softening contradicted verdicts; averaging; verdict
vocabulary (cheap/expensive); omitting the scoreboard.
Note on claims[]: your context is mostly sec:/calc material with FEW raw
evidence labels — put a statement in claims[] ONLY when a genuine
evidence label from your context supports it (e.g. from a claim_check
row); all other findings live in blocks with sec:/calc citations. Do not
invent or adapt labels to force a claim.

## Quality checklist
- [ ] Lead block answers the reader-question with cited findings
- [ ] Every triangulation pairing either run or named as insufficiency
- [ ] Scoreboard present with every claim_check row
- [ ] risk_candidates_for_H includes every contradicted claim
- [ ] credibility_notes_for_F written for every non-corroborated claim
- [ ] Every number cites calc:*, sec:D*.<block>, or an evidence label
