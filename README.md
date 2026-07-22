# AlphaNet — AI-native equity research for Indian equities

Generates an institutional-grade, evidence-cited research report per
company (no Buy/Sell/Hold — ever).

**Start here:** [HANDOFF4.md](HANDOFF4.md) (current state + work order)
and [FOUNDATIONS.md](FOUNDATIONS.md) (product identity, settled
decisions and why, principles, compliance).

Design docs, in dependency order:

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
cp .env.example .env            # GEMINI, Supabase, FIREWORKS (paid) keys
python scripts/seed_entities.py
python main.py --dry-run --ticker SONACOMS   # graph sanity, zero network
python main.py --ticker SONACOMS --model M3  # production run (~$1, ~25 min)
python main.py --ticker SONACOMS --model M3 --reingest  # re-read all docs
                                # (after extraction-prompt/model upgrades)
python scripts/diff_golden.py SONACOMS       # regression vs frozen golden
```

See [NEXT_STEPS.md](NEXT_STEPS.md) for current state and watch-lines.

## Ground rules (enforced in code, not vibes)

- **Models interpret, Python computes** — every number carries lineage
  (evidence UUID or calc:formula + input row ids); canon KPIs carry a
  unit-class guard, templated sources carry identity validation
- **Every block cites or it doesn't ship** — unresolved citations are
  flagged in the report; claims are verified against their evidence;
  claim evidence-ids are validated against the run's pool
- **Gaps are reported, never papered over** — "not disclosed / not
  computable yet" is first-class output
- **No fallback, no auto-retry** — first LLM error aborts cleanly; the
  documented exceptions are narrow and stochastic-only (HTTP 429,
  extraction reprompt/truncation-once, envelope spiral/JSON retry-once,
  verifier per-batch retry). Reruns reuse all ingested URLs at zero cost
- **Golden set** — SONA + M&M reports frozen in `data/golden/`; rerun +
  `diff_golden` after every prompt/pack/model change
- Keep billing DISABLED on the Gemini GCP project (free tier dies)
