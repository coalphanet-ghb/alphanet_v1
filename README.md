# AlphaNet — AI-native equity research for Indian equities

Generates an institutional-grade, evidence-cited research report per
company (no Buy/Sell/Hold — ever). Design docs, in dependency order:

1. [REPORT_BLUEPRINT.md](REPORT_BLUEPRINT.md) — the 11-section report (frozen v0.3)
2. [DATA_SOURCES.md](DATA_SOURCES.md) — source universe, sector taxonomy, query banks
3. [REPORT_GEN_PLAYBOOK.md](REPORT_GEN_PLAYBOOK.md) — the ordered workflow + budgets
4. [ANALYST_KNOWLEDGE.md](ANALYST_KNOWLEDGE.md) — how to analyze (universal + sector packs)
5. [nodes/](nodes/README.md) — per-node specs (the prompts' source of truth)
6. [data/sector_packs/](data/sector_packs/_SCHEMA.md) — machine-readable sector variation

## Pipeline (implements playbook S0–S9)

```
s0_resolve    company -> pack, peers, freshness, read plan        (0 LLM)
s1_discover   ddgs queries -> rerank -> pre-flight -> URL plan    (0 LLM)
s2_extract    url_context -> verbatim evidence + metric
              candidates + cross-block tags (risk/guidance/
              supply-edges); ingested URLs reused for free        (~20-26)
s3_compute    validation gate -> metric_observations -> CAGRs,
              margins, forensic battery, guidance scorecard,
              peer table, valuation context                       (0 LLM)
synth B,D,E,F -> G (peers) -> H (risks) -> C (industry/macro,
              needs E's graph edges) -> I (valuation) -> J        (9)
s9_verifier   claims vs cited evidence, batched                   (2-4)
s8_composer   snapshot A + sources K + citation integrity +
              markdown + report_versions                          (0 LLM)
```

Prompts are assembled at runtime from `nodes/<node>/spec.md` + the
company's sector pack overlays — changing a spec or pack changes the
product; no code edit needed.

## Layout

```
main.py                     # CLI: company menu, lite|high, --dry-run
nodes/                      # node specs (source of truth for prompts)
data/sector_packs/          # sector pack registry (JSON)
data/seed_entities.json     # pilot entity graph seed
scripts/seed_entities.py    # idempotent seeding
scripts/list_models.py      # what models this key can use (--test)
src/
  config.py                 # env, models, companies, budgets, domains
  llm.py                    # read_urls / synthesize / generate_json + throttle
  db.py                     # Supabase DAL + citation-integrity + metrics
  packs.py / specs.py       # pack loader / prompt assembler
  pipeline/                 # s0..s9 nodes + graph + state + dry-run fixtures
```

## Running

```bash
python -m venv .venv && .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env        # GEMINI_API_KEY (no-billing project), Supabase keys
python scripts/seed_entities.py
python main.py --dry-run    # graph sanity, zero network
python main.py              # live (lite model; 'high' only for reruns)
```

See [NEXT_STEPS.md](NEXT_STEPS.md) for the current test checklist.

## Ground rules (enforced in code, not vibes)

- **Models interpret, Python computes** — every number carries lineage
  (evidence UUID or calc:formula + input row ids)
- **Every block cites or it doesn't ship** — unresolved citations are
  flagged in the report; claims are verified against their evidence
- **Gaps are reported, never papered over** — "not disclosed / not
  computable yet" is first-class output
- **No fallback, no auto-retry** — first LLM error aborts cleanly;
  reruns reuse all ingested URLs at zero cost
- Keep billing DISABLED on the GCP project (free tier dies otherwise)
