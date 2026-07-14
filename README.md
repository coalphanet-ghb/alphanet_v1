# AlphaNet — Company Research Workflow (Sprint 1: Gemini + Supabase)

A minimal, real LangGraph pipeline that proves out the core AlphaNet loop
for one company (defaults to **Sona BLW Precision Forgings / Sona Comstar**,
NSE: SONACOMS) before any of the scheduler/orchestrator/multi-company
infrastructure gets built.

What it does, end to end:

1. **Gathers sources** with the two-step pattern from HANDOFF.md §4:
   - **Discover** (ddgs — deterministic Python, zero LLM calls):
     hand-curated finance queries per layer (macro → auto sector → stock,
     see `src/ingestion/queries.py`) find candidate URLs. URLs are the
     *only* thing taken from this step.
   - **Read** (`gemini-3.5-flash` + `url_context`): extract verbatim
     passages from those URLs. These become `evidence` rows in Supabase,
     and each chunk's citation ID **is** its evidence row UUID.

   > Grounded `google_search` discovery was dropped: it required
   > `gemini-2.5-flash`, which Google closed to new users (404), and on
   > 3.x models grounding needs billing enabled. ddgs replaces it.
2. **Runs 5 parallel, grounded analysis nodes** — Financial Analysis,
   Business Overview, Management & Guidance, Risks, Peer & Market
   Positioning — each citing its claims back to specific chunk IDs.
3. **Synthesizes valuation & key takeaways** from all five sections.
4. **Composes the final markdown report** deterministically (no LLM),
   flags any citation that doesn't match a real gathered source, writes
   the file to `data/reports/`, and saves a pinned `report_versions` row.

Every non-dry run is logged to the `runs` table (status, model, errors).

Macro and industry context are hand-written stubs for now
(`src/knowledge/stubs.py`). Real, automated Macro and Industry workflows
are Sprint 3 — see HANDOFF.md §9.

## Call routing (updated from HANDOFF.md §3)

| Step | Engine | Notes |
|---|---|---|
| URL discovery | ddgs (Python, no LLM) | keyword banks in `src/ingestion/queries.py` |
| `src/llm.py: read_urls()` | active model + `url_context` | 1 call per URL read |
| `src/llm.py: synthesize()` | active model, no tools | 6 calls per run (5 sections + valuation) |

The **active model** is `gemini-3.1-flash-lite` by default (15 RPM /
500 RPD free tier); `python main.py high` switches to `gemini-3.5-flash`
(5 RPM / 20 RPD — tight). Calls are self-throttled to the model's RPM.
**No fallback and no automatic retries** — the first error aborts the run
cleanly and retrying is manual (cheap: ingested URLs are reused).

**Keep billing DISABLED on the GCP project** — enabling it kills the free
tier. The per-layer URL caps in `src/config.py` (`MAX_URLS_*`) are the main
quota lever: a full fresh run = `2 + 2 + 4` reads + 6 synthesis calls.

## Project layout

```
alphanet/
  main.py                        # CLI entrypoint + run bookkeeping
  requirements.txt
  .env.example
  scripts/
    seed_entities.py             # idempotent pilot entity/relationship seeding
  src/
    config.py                    # env vars, model name, URL/chunk caps
    llm.py                       # Gemini wrapper: read_urls / synthesize
    db.py                        # Supabase data access + citation-integrity check
    ingestion/
      queries.py                 # hand-curated finance queries per layer
      research.py                # ddgs discover -> url_context read -> persist evidence
    knowledge/
      stubs.py                   # hardcoded macro & industry context (until Sprint 3)
    workflow/
      state.py                   # LangGraph state schema
      prompts.py                 # all prompt templates
      nodes.py                   # the 5 analysis nodes + valuation synthesis
      graph.py                   # StateGraph wiring (fan-out / fan-in)
    output/
      report_writer.py           # deterministic markdown + citation check + report_versions
  data/
    seed_entities.json           # hand-curated pilot entity set
    reports/                     # generated .md reports land here
```

## Setup

1. **Create and activate a virtual environment**

   ```bash
   python -m venv .venv
   source .venv/bin/activate        # Windows: .venv\Scripts\activate
   ```

2. **Install dependencies**

   ```bash
   pip install -r requirements.txt
   ```

3. **Sanity-check the pipeline with zero network/API calls**

   ```bash
   python main.py --dry-run
   ```

   Runs the full graph on synthetic data in seconds, touching neither
   Gemini nor Supabase. If this produces a report in `data/reports/`,
   the code and graph wiring are good.

4. **Add credentials** — see [NEXT_STEPS.md](NEXT_STEPS.md) for the full
   checklist (Gemini key on a no-billing project, Supabase service_role key,
   entity seeding).

5. **Run it for real**

   ```bash
   python main.py          # lite model; asks which company (SONA / M&M)
   python main.py high     # main model (gemini-3.5-flash) — slow by design (RPM throttle)
   python main.py --ticker SONACOMS --company "Sona BLW Precision Forgings Limited (Sona Comstar)"   # skip the menu
   ```

6. **Read the output** in `data/reports/<TICKER>_<timestamp>.md` — like a
   skeptical analyst, per HANDOFF.md §12 — and check the Supabase tables
   (`source_documents`, `evidence`, `entity_mentions`, `report_versions`, `runs`).

## Graceful degradation

- No `GEMINI_API_KEY` → real runs exit immediately with a clear message;
  `--dry-run` always works.
- Gemini key set but no Supabase creds → the pipeline runs, chunks stay
  in-memory, nothing is persisted (a warning is printed).

## Known simplifications (deliberate)

- **No vector search.** Nodes get chunks filtered by source type. Swap in
  semantic ranking only when structural retrieval returns too much
  (HANDOFF.md §5) — `format_chunks_for_prompt()` is the only seam.
- **Nodes still emit prose with inline citation tags.** Structured
  `{claim, evidence_ids, confidence}` JSON output is Sprint 2; the
  application-level citation-integrity check it needs already exists in
  `src/db.py:save_claims`.
- **Entity linking is substring matching** against the hand-seeded set in
  `data/seed_entities.json`. No NER, deliberately.
- **Valuation is qualitative only.** No live price/multiples feed yet, and
  the model is explicitly told not to invent one.
