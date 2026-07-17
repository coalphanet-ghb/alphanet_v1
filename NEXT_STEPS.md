# Phases 0–2 complete. Test, then Phase 3.

## Run it

```bash
python main.py --ticker SONACOMS --model M3
```

Optional: `--reingest` forces every company document to be re-read
(ignores stored extractions). Use it after an extraction-prompt or model
upgrade — it costs a full read budget, so not for routine runs.

## What Phase 2 changed (vs the 2026-07-16 report)

| Defect then | Fix |
|---|---|
| 8 claims with dangling evidence ids; J citing numbers to evidence it never read | Contract rule 3b: upstream numbers must cite `sec:<LETTER>.<block_id>`; upstream blocks are now shown pre-labelled with that exact ref |
| ₹237B order book rendered `2370` in B and `23700` in E | Contract rule 2b: **no unit conversion** — quote the unit as given |
| `evidence:<uuid>` / `3d114efa` forms unresolvable (1 miss) | Resolver accepts `sec:`, `evidence:`, bare block ids, unique 8-hex prefixes |
| 28/79 verifier "partials" mostly = missing quarter/date context | Verifier excerpts now carry `[SOURCE: doc_class | title | page]`; budget 4→8 calls |
| 2023 trademark judgment surfaced as a "moat" via news | ddgs `timelimit`: news = past month, doc-hunts = past year; legal DBs allowed **only** on the litigation query (now its own read) |
| gurufocus/marketscreener/moneycontrol wasting reads | Blocked; alphaspread/trendlyne/concall.in promoted to tier-1; **learned scores** (`data/domain_scores.json`) auto-demote domains after 2 failures |
| Thin early extractions frozen forever by reuse | Re-read when stored passages < floor (concall 5, AR 10, IP 4) |
| J rendered 3 untitled lists back-to-back | `ranked_list` titles rendered; metric_card provenance now checked |
| One malformed JSON killed a whole read | Extraction reprompts once (documented no-retry exception) |

**Watch for:** `citations resolved` should approach 100% *with* the stricter
metric_card check now included; verifier "not fully supported" should drop
well below 28/79; no `indiankanoon`/`casemine` outside the litigation read.

## Known gaps (later phases, by design)

- **Phase 3** — extraction 2.0: local fetch + PDF (`pypdf`), extraction on
  M3 (1M ctx) instead of Gemini url_context, batch all 4 concalls in one
  call, richer AR/IP schemas (segment/geography/customer/RM tables → the
  sector KPIs whose canon names already exist), read budget 26→40.
- **Phase 4** — per-statement forensic nodes (s4a/b/c) + concall
  cross-examination + s4d_followup + s4e synthesis.
- **Phase 5** — 1M-context budgets, C full-feed, peer evidence packs,
  valuation own-history percentile, cost telemetry.
- **Phase 6** — golden set + `scripts/diff_golden.py`.

## Regression guards

```bash
python scripts/test_screener_parser.py --live   # after touching metric_names.py
python main.py --dry-run --ticker SONACOMS      # graph wiring, zero network
```
