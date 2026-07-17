# HANDOFF 2 — AlphaNet session handoff (2026-07-17)

> For the next assistant session. The previous session took the project
> from a Gemini-only walking skeleton to the full S0–S9 pipeline with a
> deterministic numeric backbone, completed Phases 0–2 of the six-phase
> improvement plan, and validated everything on live SONA runs. This doc
> is the single entry point: reading order, current state, remaining
> phases in implementable detail, and hard-won working practices.

---

## 1. Reading order (30 minutes to full context)

1. **This file** — end to end.
2. **`REPORT_BLUEPRINT.md`** (FROZEN v0.3) — the 11-section report A–K the
   system produces. Never change the skeleton; sector packs carry variation.
3. **`nodes/README.md`** — the envelope contract every LLM node obeys
   (block types, citation forms, no-arithmetic/no-unit-conversion rules).
   Then skim 2–3 node specs (`nodes/s4_financials/spec.md`,
   `nodes/s5_risks/spec.md`) to see the pattern: specs ARE the prompts
   (parsed at runtime by `src/specs.py`).
4. **`ANALYST_KNOWLEDGE.md`** — how to analyze (universal + sector packs +
   compute library spec). Source for any new node spec.
5. **`REPORT_GEN_PLAYBOOK.md`** + **`DATA_SOURCES.md`** — workflow stages,
   URL/call budgets, source universe, query banks. Partially superseded in
   detail (screener parser replaced LLM screener reads; Fireworks replaced
   the free tiers) but the architecture holds.
6. **Code walk** (~1,500 lines that matter):
   `main.py` → `src/pipeline/graph.py` (stage wiring) → `s0_resolve` →
   `s1_discover` → `s2_extract` → `s3_compute` → `s4_synth` (generic
   synthesis runner + per-section context assemblers) → `s9_verifier` →
   `s8_composer`. Plus `src/llm.py` (provider registry), `src/db.py`
   (Supabase DAL + citation-integrity), `src/packs.py`/`src/specs.py`
   (pack loader / prompt assembler), `src/ingestion/screener_parser.py` +
   `metric_names.py` (the numeric backbone).
7. **Old `HANDOFF.md`** — historical context only (original architecture
   decisions, anti-hallucination principles). Its sprint plan is long
   superseded; its principles are not.
8. Latest reports in `data/reports/` — compare `SONACOMS_20260717_072338.md`
   (current best) against earlier ones to see the progression.

## 2. System snapshot (what exists and works)

**Pipeline:** LangGraph S0–S9: resolve → discover (ddgs + screener doc
links, domain tiers, learned scores, preflight) → extract (Gemini
url_context reads; deterministic screener parser; reuse-with-quality-gates;
cross-block tag pools) → compute (validation gate → metric_observations →
CAGRs/TTM/statement tables/forensic battery/Piotroski/guidance
scorecard/peer table/valuation) → synthesis waves B,D,E,F → G → H → C → I →
J (spec-driven prompts + sector-pack overlays) → verifier (batched,
metadata-aware) → composer (snapshot A, sources K, citation resolution,
quality badge, report_versions).

**Models** (`src/llm.py` `_OPENAI_PROVIDERS` registry):
- Synthesis/verification: `--model M3` = MiniMax-M3 via **Fireworks (PAID,
  FIREWORKS_API_KEY)** — the production choice. `--model GLM` = GLM-5.2 on
  NVIDIA trial (unusable queues; keep for comparison). Default `gemini`.
- Document reads: ALWAYS Gemini `gemini-3.1-flash-lite` url_context
  (until Phase 3 replaces with local fetch + M3).
- Policy: NO fallback, NO auto-retry. Documented exceptions: HTTP 429
  (retry ≤4, Retry-After), one extraction reprompt on malformed JSON,
  deadline-expired skips the URL. First error otherwise aborts; reruns are
  cheap (ingested URLs reuse free).

**Persistence:** Supabase, 9-table schema (FROZEN — in first user message
of old chat / applied in dashboard). Citation integrity lives in app code
(`db.save_claims`) because `claims.evidence_ids` is uuid[] with no FK.

**Latest run quality (SONA, M3):** 133 passages, 2,602 observations, 25
computed metrics, 7 forensic checks, 324/325 citations resolved, verifier
10/69 not-fully-supported, 17 LLM calls, ~$1.

**Companies:** SONA (auto_ancillaries pack) + M&M (auto_oem pack) in
`config.COMPANIES`. Packs in `data/sector_packs/` (+ banks.json as
generality proof). M&M has NOT been run since the rebuild — see Phase 6.

## 3. How to run and verify (the session's working discipline)

```bash
python main.py --dry-run --ticker SONACOMS   # graph sanity, zero network, SECONDS — run after EVERY change
python scripts/test_screener_parser.py --live # after touching metric_names.py / parser / screener layout changes
python main.py --ticker SONACOMS --model M3   # live run (~17-25 calls, ~10 min)
python main.py --ticker SONACOMS --model M3 --reingest  # force re-extraction (after prompt/model upgrades)
python scripts/list_models.py --test          # if Gemini model names go stale
```

**Log lines that ARE the gates:**
- `[s3_compute] N observations validated` — numeric backbone health (~2,600
  incl. peers). A `deduped X -> Y` gap larger than ~15 = new label
  collision in `metric_names.py` (see §6.1 — this class ships WRONG numbers).
- `[s2] screener parsed (no LLM)` — parser alive; `parser failed …falling
  back` = layout change → fix parser, LLM fallback covers meanwhile.
- `[s1] 4 concall transcripts via screener doc links` — authoritative BSE
  PDFs; `[s2] stored extraction thin — re-reading` — quality gate working.
- Composer line `N/M citations resolved` and verifier `X not fully
  supported` — quality badge; also printed at report end.

## 4. Environment quirks (will bite you if unknown)

- **Network TLS weirdness on this machine/sandbox:** NVIDIA + Fireworks
  endpoints TLS-reset Python's stack → `llm.py` auto-falls back to
  Git-for-Windows curl (`_find_curl`, override `NVIDIA_CURL`). The
  assistant sandbox itself cannot reach screener.in at all — but the
  USER's machine can; test screener live via `scripts/test_screener_parser.py
  --live` (works from assistant Bash too when network permits — it did).
- Windows cp1252 consoles: never print non-ASCII (Δ, →) from pipeline code.
- `.env` holds real keys (GEMINI, SUPABASE, NVIDIA, FIREWORKS) and is
  gitignored. Never commit keys; `.env.example` carries placeholders.
- Keep billing DISABLED on the Gemini GCP project (free tier dies).
- Failure handlers must never throw (a DNS outage once masked its own
  error by crashing the mark-failed DB write — now hardened in main.py).
- LangGraph runs B/D/E/F in parallel → all provider calls are serialized
  via per-provider locks in llm.py. Don't remove them.
- Console shows duplicated `[synth_X]` lines sometimes — parallel print
  interleaving artifact, NOT double execution (check `LLM calls this run`).

## 5. REMAINING PLAN — Phases 3–6 (+ backlog)

### PHASE 3 — Extraction 2.0 (next up; feeds Phase 4)
1. **Local fetch layer** `src/ingestion/fetcher.py`: `requests` + browser
   UA; PDF→text via `pypdf` (add to requirements); HTML→text via
   `trafilatura` (re-add). Per-URL fallback chain: local fetch → Gemini
   url_context → skip+log. Kills deadline-expiries and unreadable-domain
   dependence on Gemini's fetcher.
2. **Extraction on M3** (1M ctx, 83% IFBench): same JSON schema
   (`s2_extract._SCHEMA`), document text inline instead of url_context.
   Route via the fireworks provider; keep Gemini as per-URL fallback.
3. **Batch all 4 concall transcripts in ONE M3 call** (per-source
   delimiters) → new cross-quarter fields: `guidance_evolution[]`,
   `recurring_themes[]`, repeated-dodge patterns.
4. **Richer AR/IP schemas:** segment tables, geography splits, top-customer
   %, RM/COGS breakdown, forex spend, order book, EV-mix, capacity — the
   exact fields every insufficiency list begs for. Canon names already
   exist (`order_book`, `ev_revenue_share`, `export_share`,
   `customer_concentration`, `aftermarket_share`, `capacity_utilization`)
   so extracted candidates auto-land in sector KPIs.
5. **Budget up (paid):** `MAX_READ_CALLS` 26→40; add FY-1 annual report
   (forensic trends), second rating agency, news URLs 6→10.
6. Fix observed mis-target: "investor_presentation" reads sometimes land on
   trendlyne news-list pages — prefer company-IR/BSE URLs; validate the
   fetched doc looks like a presentation (page count / keywords) before
   spending extraction.
**Gate:** zero deadline skips; 4/4 concalls in ONE call with
guidance_evolution populated; AR yields ≥5 distinct sections incl. RM/COGS
+ segment tables; ≥3 sector KPIs move from "not computable yet" to values;
≥150 passages.

### PHASE 4 — Financial forensic architecture (the flagship)
New graph order:
`s3 → [B, E, s4a_pl, s4b_bs, s4c_cf] → s4d_followup → s4e_fin_synthesis → F → G → H → C → I → J → s9 → s8`
(F moves after s4e to consume the claim-check scoreboard.)
1. **s4a/b/c statement-forensic nodes** (new specs from ANALYST_KNOWLEDGE
   D1/D2/D3): inputs = `calc:pl_table`/`bs_table`/`cf_table` + battery
   checks + statement-relevant evidence + guidance items. Dual job:
   statement analysis + **cross-examination**: every management claim
   touching the statement tested against computed numbers →
   `claim_checks[]: {mgmt_claim, quote evidence_id, computed_ref,
   verdict: corroborated|contradicted|unverifiable, note}`.
2. **s4d_followup** (bounded, ≤3 LLM calls, one iteration): statement nodes
   emit ≤2 `followup_requests[]` each (`target: computed|evidence`);
   Python answers computed ones; evidence ones = keyword-filtered pool +
   one M3 call answering ONLY from those passages.
3. **s4e_fin_synthesis** (rewrite `nodes/s4_financials/spec.md`):
   integrated D — cross-statement triangulation (the 12-check lens),
   DuPont driver sentence, quality-of-earnings, ratio-vs-pack-norms, and
   the **claims-vs-numbers scoreboard**. Contradicted claims auto-feed H
   (risk candidates) and F (credibility).
4. State adds `envelope_D1/D2/D3`, `claim_checks`, `followups`; D1–D3
   persist as knowledge_entries sections; composer renders D from s4e.
**Gate:** D renders D1/D2/D3 + synthesis; scoreboard tests ≥5 management
claims; ≥1 non-corroborated verdict surfaced in F and H.

### PHASE 5 — Cross-context & node-skill upgrades (1M ctx exploitation)
1. Context budgets: `_evidence()` 15K→40K chars for D-family/F/H/C;
   `_envelope_summary` 4K→10K for G/H/I; **J receives full envelopes**.
2. C full-feed: entire macro+sector layers + complete entity-graph edges +
   D's computed sensitivities.
3. G upgrade: peer evidence packs (peers' parsed KPIs + passages) → numeric
   gap attribution; worst-cells become quantitative.
4. I upgrade: multiple own-history percentile — from parsed price + own EPS
   series (P/E history), or screener chart endpoints if accessible;
   3y re-rating decomposition (EPS growth × multiple change).
5. Claims density floor (8–20/section) in contract; verifier
   contradicted-verdicts exported to H/F (needs verifier before synthesis
   OR a targeted second pass — design choice for implementer).
6. Cost telemetry: API usage fields → `runs.tokens_input/output/cost_usd`
   (columns exist, unused).
**Gate:** C sensitivities ≥5 entities with recent+medium-term views; G
attributes ≥3 gaps numerically; I has percentile sentence; run cost logged.

### PHASE 6 — Validation, golden set, M&M
1. SONA full `--reingest` run → re-check all phase gates.
2. **M&M end-to-end** (auto_oem pack — first post-rebuild run; expect pack
   overlay issues to surface; M&M screener slug is `M%26M`).
3. Freeze both reports as golden set + write `scripts/diff_golden.py`
   (section-level block/claim/citation-count diffs). Rerun + diff after
   every prompt/model change (old HANDOFF §8 principle).
4. Update NEXT_STEPS.md, README.md, nodes/README.md, memory file.

### Backlog (not in phases, noted during runs)
- Stuck `running` rows in `runs` table from pre-hardening crashes — one-off
  SQL cleanup (`update runs set status='failed' ... where status='running'`).
- Evidence-row duplication when a re-read hits unchanged content
  (created=False still inserts new rows) — dedupe or reuse-on-hash-match.
- Peer table: Sona's own row shows some nulls (metric mapping between
  parsed obs and `_PEER_METRICS` names) — verify after Phase 3.
- NBFC sector pack (deliberately NOT folded into banks.json).
- Sector-page numbers stay evidence-only (correct); industry-series
  observations attributed to sector entities is a future refinement.
- UI/blocks rendering (blueprint's "blocks not prose" is stored in
  report_versions.sections_json — UI is the last step, per user).

## 6. Best practices learned (violate at your peril)

1. **Wrong numbers are worse than missing ones — and they look plausible.**
   Three substring collisions in canon matching shipped corrupted values
   (debtor days as borrowings; a CFO/OP *ratio* overwrote CFO and produced
   a FALSE earnings-manipulation flag). Guards now exist
   (`scripts/test_screener_parser.py`: idempotency + trap labels + "CFO
   never contains %"). Whenever touching `metric_names.py`: keys are
   substring-matched longest-first; short keys are landmines ("debt",
   "cash", "pe", "cfo"); add a trap test per new key.
2. **Fixtures lie; live data tells the truth.** Two of three collisions
   were invisible to the hand-built fixture and only appeared on the real
   screener page. Always test parsers against the live page (`--live`),
   then backport the surprising rows INTO the fixture.
3. **Verify with the exact failing case.** Every bug fix in this session
   was proven by reproducing the precise artifact first (dup FY26 → 0.0%
   YoY; Q4FY26 month-13 crash; truncated envelope), then asserting the
   fix on it. Unit-test files under scripts/ or inline `python - << EOF`.
4. **Models interpret, Python computes** — held firm and paid off
   repeatedly. Also: models must NOT convert units (contract rule 2b
   exists because hand-converted crore/billion contradicted across
   sections).
5. **Freshness ≠ absence.** "Layer fresh, skip reads" once meant "run
   without the data" (empty section C). Any skip-optimization must
   rehydrate from storage.
6. **Reuse needs quality gates or it freezes your worst extraction
   forever** (`REUSE_MIN_PASSAGES`, `--reingest`).
7. **Failure handlers must never throw** — the DB write inside the failure
   path crashed during a DNS outage and masked the real error.
8. **Free tiers lie about limits; measure them.** 3.5-flash's 5 RPM/20 RPD
   and NVIDIA trial's bursty 429s/504 queues were discovered empirically.
   Paid Fireworks removed a whole class of engineering. Probe endpoints
   with tiny curl calls before wiring providers.
9. **Every design decision lives in a versioned doc** (blueprint → sources
   → playbook → knowledge → specs → packs). Specs are the prompts; editing
   a spec/pack changes the product with zero code changes. Keep it so.
10. **Insufficiencies are a feature.** The M3 model audited OUR compute
    artifacts because the honesty discipline exposed them. Never paper
    over gaps; the "Not found in sources" sections drive the next phase's
    priorities.
11. **Read the run log as a dashboard** (§3): observation counts, dedup
    gaps, reuse/parse lines, quality badge. Anomalies there caught every
    real bug before the report was even opened.
12. Model routing facts (verified): MiniMax-M3 = best non-hallucination
    (84%) + IF (83%) — the workhorse. DeepSeek V4 Pro disqualified (6%
    non-hallucination). Reasoning models spend hidden thinking tokens
    INSIDE max_tokens — envelope calls need 32K budget, and truncation must
    be detected via finish_reason=="length", not parse failure.

## 7. Bootstrap for the new session

Suggested first message:
> Read HANDOFF2.md fully, then REPORT_BLUEPRINT.md, nodes/README.md and
> skim the src/pipeline modules. Confirm your understanding of the current
> state and the Phase 3–6 plan, then start implementing Phase 3
> (Extraction 2.0), verifying each step per HANDOFF2 §3 and §6.

The project memory (auto-loaded) also carries the compressed state; where
memory and this file disagree, this file wins (it is newer and complete).
