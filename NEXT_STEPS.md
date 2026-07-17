# Phases 0–3 complete. Test, then Phase 4.

## Run it

```bash
python main.py --ticker SONACOMS --model M3
```

Optional: `--reingest` forces every company document to be re-read
(ignores stored extractions). Use it after an extraction-prompt or model
upgrade — it costs a full read budget, so not for routine runs.

## What Phase 3 changed (Extraction 2.0, vs the 2026-07-17 morning report)

| Before | Now |
|---|---|
| Gemini url_context reads (deadline expiries, unreadable domains) | Local fetch first (`src/ingestion/fetcher.py`: requests + pypdf + trafilatura), text inline on the synthesis model; url_context is the per-URL fallback; skip+log last. Gate run: zero url_context fallbacks needed |
| 4 concalls = 4 separate reads, no cross-quarter view | ONE batched call → `guidance_evolution[]` (7 trails) + `recurring_themes[]` (10), persisted as `concall_cross_quarter`, rehydrated on reuse, fed to section F |
| AR read shallow (~10 passages, no tables) | Both FY26 + FY-1 ARs read in full (194/213 pdf pages); segment, geography, customer-concentration, RM/COGS tables extracted; 338 passages total (was 133), 675 company observations (was ~350) |
| 26-read budget, 6 news URLs, 1 rating agency | 40 reads, 10 news URLs, 2 rating agencies (distinct domains), FY-1 AR |
| IP hunts landing on trendlyne news-list pages | s1 prefers direct PDFs/BSE; s2 validates the doc looks like a deck before extracting; failures log `mistarget` (counts against the domain score) |
| Canon-named extraction shipped mislabels (order_book=70% [EV share], export_share=41% [NA geography share], customer_concentration=51% [top-5]) | **Unit guard** (`metric_names.unit_mismatch`, applied in s3 validation) drops canon KPIs with impossible units; extraction schema now defines each canon name precisely and mandates descriptive names otherwise; corrupt rows deleted, stored pools patched |

**Watch for:** `[s3] N candidate(s) dropped by unit guard` — nonzero is the
guard working; inspect the listed name=value pairs for NEW mislabel forms
(semantic mislabels with the right unit can only be caught by the sharper
prompt + skeptical reading). `citations resolved` was 260/261; verifier
13/75 not-fully-supported. Snapshot must never show a % where a ₹ value
belongs.

## Known gaps (later phases, by design)

- **Phase 4** — per-statement forensic nodes (s4a/b/c) + concall
  cross-examination + s4d_followup + s4e synthesis (see HANDOFF2 §5).
- **Phase 5** — 1M-context budgets, C full-feed, peer evidence packs,
  valuation own-history percentile, cost telemetry.
- **Phase 6** — SONA reingest re-validation, M&M end-to-end, golden set +
  `scripts/diff_golden.py`.
- Backlog additions from Phase 3 runs: `edge:<id>` citation form emitted
  by C (mostly resolved now, 1 miss) — bless or map in composer resolver;
  B persisted 5 claims with dangling evidence ids (composer flags them,
  but worth a prompt nudge); evidence-row duplication on unchanged
  re-reads (pre-existing).

## Regression guards

```bash
python scripts/test_screener_parser.py --live   # after touching metric_names.py
python main.py --dry-run --ticker SONACOMS      # graph wiring, zero network
```
