# Ready to test — lite-by-default, company menu, no fallback

What changed (driven by your quota panel: 3.5-flash free tier is only
**5 RPM / 20 RPD**, while 3.1-flash-lite gets **15 RPM / 500 RPD**):

- **Lite model is the default.** `python main.py` runs everything on
  `gemini-3.1-flash-lite`. `python main.py high` uses `gemini-3.5-flash`.
- **No fallback, no automatic retries.** The first error of any kind stops
  the run cleanly (marked `failed` in `runs`, with the error message).
  Retry = run `main.py` again yourself; already-ingested URLs are reused
  with zero LLM calls, so retries only spend quota on what's left.
- **Self-throttling.** Calls are paced to the active model's RPM
  (~12.5s/call on high, ~4.5s on lite) so the script no longer trips its
  own rate limit — that was a big part of your 503s. The `high` run being
  slow is intentional; it's the quota, not the code.
- **Company menu.** `main.py` now asks: `1. SONA  2. M&M`. M&M is wired
  through the same query templates and the auto sector bank.

## Test flow

```bash
python scripts/seed_entities.py    # re-run once — new M&M peers/relationships added
python main.py                     # pick 1 (SONA) or 2 (M&M), runs on lite
```

Budget per fresh company run: 2 macro + 2 sector + 4 company reads
+ 6 synthesis = **14 calls** (your tested caps, now the defaults in
`src/config.py`). On lite's 500 RPD you can raise `MAX_URLS_*` freely;
on `high` (20 RPD) a fresh run barely fits — see the pattern below.

**A pattern worth using:** ingest on lite first (`python main.py`), then
run `python main.py high` for the same company — the reads are all reused
from Supabase, so the high-quality model only spends ~6 synthesis calls.
Best report per unit of 3.5-flash quota.

Notes:
- SONA's macro/sector URLs from earlier successful runs will be reused
  (`URL already ingested — reusing N evidence rows`), so an M&M run mostly
  spends calls on M&M-specific pages.
- `runs.model_used` records which model produced each report — check it
  before judging output quality per HANDOFF.md §12.
- If model names go stale again: `python scripts/list_models.py --test`,
  then set `GEMINI_LITE_MODEL` / `GEMINI_MAIN_MODEL` in `.env`.
  (The old `GEMINI_SYNTHESIS_MODEL` / `GEMINI_FALLBACK_MODELS` env vars
  are no longer read — remove them from `.env` if you set them.)

## What to verify after a successful run

- Report in `data/reports/` (M&M's file is `M_M_<timestamp>.md` — ticker
  sanitized for the filename).
- Supabase: `source_documents` (`metadata.layer`), `evidence`,
  `entity_mentions`, `report_versions`, `runs` (status + `model_used`).
- Sources section: any ⚠️ unresolved citation = the model invented one.
- Which queries earned their keep: `source_documents.metadata.discovered_for`
  — prune weak ones in `src/ingestion/queries.py`.

## Caveats (unchanged)

- URL reuse is by exact URL, forever — delete a `source_documents` row to
  force a fresh read. Real freshness policy = Sprint 6 update workflow.
- ddgs sometimes rate-limits or returns junk; a failed query is logged
  and skipped, and reruns are cheap.

## After that: Sprint 2

Nodes emit structured `{claim, evidence_ids, confidence}` JSON into
`knowledge_entries`/`claims` (the integrity check in `src/db.py:save_claims`
is already built and waiting), plus the per-node `spec.md` files (HANDOFF.md §7).
