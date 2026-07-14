# s8_composer — report assembly (deterministic, zero LLM)

## Purpose
Assemble the final report from section envelopes: build A (snapshot) and
K (sources) in code, run citation-integrity checks, persist
report_versions, render markdown (one renderer of the block structure —
the blocks are the product).

## Inputs
- All section envelopes (B–J) from knowledge_entries (latest versions)
- `computed_financials`, `valuation_context`, sector pack (A vitals list)
- evidence + source_documents (for K), verification results (s9)
- run metadata (run_id, model, versions used)

## Behavior
1. **Section A build** (pure data): identity, price context, the four
   universal vitals (mcap, P/E, div yield, ROE), pack's ≤8 sector vitals —
   all from calc with provenance; last-updated stamp.
2. **Citation integrity** (the app-level FK check — non-negotiable):
   every citation in every block must resolve: evidence UUIDs → evidence
   rows; `calc:*` ids → computed_financials entries. Every claims[] row →
   `db.save_claims` with strict evidence-id verification. Unresolvable
   citation → the sentence/block is marked degraded; the count feeds the
   quality badge.
3. **Verification merge:** claims failed by s9 → their dependent blocks
   flagged; failed numeric claims REMOVE the number's sentence (never ship
   a known-bad number) and log to insufficiencies.
4. **Section K build:** sources grouped by layer with title/type/date/
   link; reproducibility line (knowledge versions, run_id, model);
   quality badge ("N/N citations resolved; M claims verified, K failed").
5. **Insufficiency rendering:** material gaps from all envelopes rendered
   as explicit "not disclosed / not found" lines in their sections.
6. **Persist:** report_versions row (sections_json = full block
   structure + rendered markdown), pinned to knowledge versions;
   markdown file to data/reports/.

## Quality checklist
- [ ] Zero unresolved citations shipped un-flagged
- [ ] No failed-verification number appears in prose
- [ ] A-vitals all provenanced to calc; no LLM text in A or K
- [ ] report_versions pins every upstream version + run_id
