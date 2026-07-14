# Rebuild complete — S0–S9 pipeline is live. Your test path.

The old 5-node prose pipeline is replaced by the full design-chain
implementation: staged workflow (resolve → discover → extract → compute →
synthesis waves → verify → compose), spec-driven prompts, sector packs,
metric observations + deterministic calc, evidence-UUID citations,
claim verification, and a blueprint-shaped report (A–K).

## Run it

```bash
pip install -r requirements.txt        # deps unchanged + requests
python main.py --dry-run --ticker SONACOMS   # sanity (zero network) — should pass in seconds
python main.py --ticker SONACOMS             # live, lite model
python main.py --ticker "M&M"                # then M&M
```

(Or `python main.py` for the menu. `high` mode: do NOT use for a first
generation — ~35–40 calls won't fit 20 RPD. After a lite run has ingested
everything, `high` reruns spend only ~13 synthesis/verify calls.)

Budget per fresh company run: ~20–26 url_context reads + 9 synthesis +
up to 4 verification calls ≈ **35–40 calls, 15–25 min** on lite
(self-throttled ~4.5s/call + read latency). The run prints its call
count at the end.

## What to expect / watch on the first live runs

This first live run doubles as the **screener-readability spike** — the
metric backbone depends on it:

1. **`[s3_compute] N observations validated`** — the single most important
   log line. Healthy: 150+ observations from the screener pages. Near
   zero → url_context couldn't read screener tables → A/D/G/I will be
   thin and honest about it (every gap lands in insufficiencies, visible
   in the report's "Not found in sources" sections).
2. **Extraction parse warnings** (`unparseable extraction`) — lite-model
   JSON discipline is the other open risk. Occasional single-doc failures
   are fine (skip-and-continue); if MOST reads fail parsing, stop and
   tell me — the extraction prompt needs tightening.
3. **Concall discovery** — watch `[s1] no transcript found for QxFYyy`;
   4 quarters found is the target, 2 is acceptable for a first pass.
4. **Verification results** — the end of the report carries a quality
   badge (citations resolved, claims supported). Failed claims appear
   per-section with reasons.
5. Reruns stay cheap: every ingested URL is reused with zero LLM calls
   (`[s2] reuse (N evidence, no LLM call)`), including across the
   SONA → M&M pair (shared macro/sector pages).

## Comparing vs the old reports

Old reports are in `data/reports/` (pre-2026-07-14 timestamps). Compare:
- **Structure:** 6 prose sections → 11 blueprint sections incl. snapshot,
  supply chain, forensic flags, guidance scorecard, peer table, monitorables
- **Numbers:** old = whatever prose the model wrote; new = only computed
  values with `calc:` lineage or evidence-cited prints
- **Honesty:** the new report says "not computable yet" / "not found in
  sources" instead of narrating around gaps
- **Trust:** quality badge + per-claim verification vs a bare citation list

## Known first-run rough edges (by design, fix after seeing real output)

- Sector KPIs (order book, EV revenue share, volume growth) mostly need
  presentation/AR extraction to hit; expect several "not computable yet"
  cells in the snapshot on run one.
- Valuation own-history percentile needs multiple history we don't ingest
  yet — the section states it.
- Guidance scorecard verdicts need quarters to pass; first runs show
  "pending" for most items — the table fills as history accumulates.
- If a section's envelope comes back as invalid JSON the run aborts (by
  design, no retry) — rerun is cheap; if it repeats on the same section,
  that spec's prompt needs work: tell me which one.
