# s5_risks — Risks writer (LLM) → section H

## Purpose
Write blueprint section H: the ranked risk register. Reader-question:
*"What kills this thesis?"* Runs AFTER s5_peers by design — relative
weakness is a risk source. Five fields per risk, all mandatory.

## Inputs
- risk_candidates pool (risk_signal tags from ALL S2 reads)
- s5_peers `risk_candidates_for_H` (worst-cells)
- `forensic_flags` (WATCH/FLAG items from calc)
- Evidence: rating_rationale weakness sections (pre-triaged by
  professionals — weight highest), AR risk factors (skip boilerplate),
  concall dodged-questions, dedicated risk read, valuepickr bear claims
  (verify against evidence before using; label origin)
- Entity graph (transmission chains), section D/E/F envelopes
- `[[SECTOR_OVERLAY:risks]]` (sector risk signatures + cycle position)

## Instructions
1. **Assemble the candidate set** from all inputs; deduplicate into
   THEMES (ten receivables-adjacent signals = one risk, well-evidenced).
2. **Coverage sweep** — before ranking, check every category for a
   candidate: demand cycle · input costs · customer concentration ·
   supplier/single-source · competition/disruption (incl. technology
   transition) · regulatory/policy · leverage/liquidity/refinancing ·
   governance/promoter · execution (capex, M&A integration) · FX ·
   litigation/contingents · key person. A category with no candidate and
   no reassuring evidence → consider whether silence is itself notable.
3. **Write each risk (ranked_list items, max 8):**
   - **name** — specific, not generic ("EU OEM order deferrals", not
     "demand risk")
   - **transmission** — the causal chain through named graph entities:
     "China rare-earth export curbs [entity] → magnet cost/availability →
     traction-motor margin → EV segment profitability"
   - **evidence** — citations; strongest first (rating rationale >
     forensic flag > concall > news > forum-claim-verified)
   - **severity** — order-of-magnitude quantification wherever calc/
     evidence allows ("EU is 31% of revenue [calc]; a 10% order cut ≈
     3% of consolidated revenue") + likelihood language (structural /
     live / tail)
   - **monitorable** — a SPECIFIC print/date/event: "FADA tractor
     registrations, monthly", "Q4 concall commentary on EU schedules",
     "RBI divergence report in FY26 AR". Test: if you can't name where
     and when to look, it's not a monitorable — rewrite.
4. **Rank** by severity × nearness. Structural slow-burners that didn't
   make the top 8 → one-line "structural watch" tail (max 4).
5. **Symmetry duty** (narrative closer): where a top risk is already
   visibly priced/acknowledged (per I's percentile context or company
   disclosures), say so in one sentence. A risk register is not a short
   thesis.

## Prohibited
Boilerplate ("macroeconomic headwinds may impact performance");
unranked laundry lists; risks without transmission chains; copying AR
risk-factor language verbatim as analysis; forum claims without
verification labeling; padding to reach 8.

## Quality checklist
- [ ] Every item: 5 fields present; monitorable passes the where-and-when
      test
- [ ] Peer worst-cells and forensic FLAGs all either appear or are
      consciously dismissed (state why in insufficiencies)
- [ ] ≥1 non-obvious risk beyond current headlines
- [ ] Severity quantified where calc allows; no fake precision where not
- [ ] Register would read fair to both bull and bear
