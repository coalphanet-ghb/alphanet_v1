# ALL SIX PHASES COMPLETE (2026-07-18). Golden set frozen.

## Phase 6 results

- **SONA `--reingest`** (v18, golden): all docs fresh under current
  prompts; 513/515 citations (99.6%); 37 calls, $1.85. Semantic-mislabel
  verdict: sharpened canon defs reduce but don't eliminate (7 drops incl.
  one NEW form — customer COUNTS under the % KPI); the unit guard caught
  every instance — that's the durable equilibrium.
- **M&M end-to-end** (v3, golden): first auto_oem run; 522/526 citations
  (99.2%); zero pack leakage; full 5-peer table (Tata demerger handled:
  TATAMOTORS slug died → TMPV/TMCV; Hyundai added); verifier 12/200.
  M&M percentile = honest insufficiency (no text-borne PE-history source
  validated; watch item).
- **Golden set + `scripts/diff_golden.py`**: freeze/diff/list; per-section
  block/claim/insufficiency fingerprints + quality deltas + regression
  flags (section missing, blocks/claims −50%, unresolved% worsening,
  zero-verified). `diff_golden TICKER` after EVERY prompt/pack/model
  change. Goldens in `data/golden/`.
- Extraction budgets at 64K provider cap + truncation added to the
  reprompt-once budget (big-AR outputs genuinely overflow; M&M's FY-1
  conglomerate AR overflowed BOTH attempts → skipped, see backlog).
- instagram.com blocked (a reel landed in an M&M news batch).

## Backlog (post-Phase-6, in rough priority)

1. **Large-AR split extraction**: M&M FY-1 AR overflows 64K output even
   with the terse reprompt — split heavy ARs into two calls
   (statements+notes / MD&A+rest) or use a slimmer trends-only schema
   for FY-1 reads.
2. **Extraction-focus versioning**: focus-hash stamp on extraction
   entries; auto re-read on mismatch (today: --reingest or manual
   invalidation only).
3. **M&M valuation-history source**: no template validated; probe more
   text-borne sources or accept insufficiency.
4. Wisesheets fragility (single source for PE history; also
   connection-resets under probing) — second template source someday.
5. TMCV has no peer_of edge (obs parse but don't join M&M's peer table)
   — add the relationship if CV comparison wanted.
6. Sprint-6 era (old HANDOFF): update workflow — rule-based triggers for
   regeneration on new filings; UI/blocks rendering; NBFC pack;
   industry-series observations.

## Regression guards (the permanent loop)

```bash
python main.py --dry-run --ticker SONACOMS       # graph wiring, seconds
python scripts/test_screener_parser.py --live    # after touching parser/metric_names
python main.py --ticker <T> --model M3           # live run (~$1-1.4)
python scripts/diff_golden.py <T>                # vs frozen golden — ALWAYS after changes
```

## Valuation upgrade (owner-driven, 2026-07-18, validated live)

Section I now answers "what did the market reprice this year, and why":
- **1y PE path** (calc:pe_1y_path): monthly closes from Yahoo's chart API
  (zero LLM, identity-validated via longName — never another company's
  prices) ÷ TTM EPS from quarterly prints. SONA: PE 47.1→68.4 (+45%)
  vs price +59% — the rally was mostly re-rating, not earnings.
- **P/B** (calc:pb) from parsed price/book value.
- I receives H's risk register + labeled guidance-evolution trails; spec
  block "The year in the multiple" attributes each move to evidenced
  events by month (unattributed allowed; invented stories not).
- 9y percentile kept (range context) alongside the 1y path (narrative).
- New citation forms: valuation_context sub-ids (calc:pb, calc:pe_1y_path)
  registered; guidance trails citable as trail:<metric-slug> (same
  deterministic-label pattern as edge:). Live-proof of these two
  resolver additions rides on the first Phase 6 run (watch the badge).
- PE-history + price sources are ticker-derived templates with mandatory
  shape+identity validation (wisesheets once resolved "M&M.NS" to Macy's
  Inc — wrong-company pages must fail loudly, never ship).

---

## What Phase 5 changed (1M-context exploitation, 2026-07-17/18)

- **Cost telemetry live**: llm.py accumulates usage per provider;
  `runs.tokens_input/output/cost_usd` populated; console prints the cost
  line. Full run ≈ $0.85–1.05 on M3.
- **Context budgets**: evidence 40K chars for D-family/F/H/C; upstream
  summaries 10K for G/H/I; J receives FULL envelopes; C gets the whole
  macro+sector layers + complete labeled edge set.
- **G peer packs**: 8 peers (4 new slugs), per-peer passage packs
  (token-based name matching; peer screener 'about' always pooled), spec
  requires ≥3 QUANTITATIVE gap attributions — delivered (7pp/9pp/13pp/
  1,000bps attributions in gate reports).
- **I own-history percentile**: deterministic from extracted PE series.
  THE LESSON of the phase — the chain needed SIX fixes, each one layer
  deeper: alias query → period parsing (with poison-label rejection:
  averages/medians/ranges NEVER parse as a year) → entity mapping for the
  new doc_class → stale-extraction invalidation → and finally the SOURCE
  itself (smart-investing/trendlyne render history in JS charts; only
  wisesheets carries the table in HTML text). PE-history source is now a
  deterministic per-company config URL (`valuation_history_url`), ddgs
  fallback. Gate report renders: "67.4× — 44th percentile of its own
  9-year range... #7 of 9 in its peer set".
- **Verifier**: audit-driven fixes (atomic-claims contract rule 3a +
  8–20 density floor; excerpts 600→1200 chars); claim_check ATTRIBUTIONS
  verified in the same batches; 16K budget + per-batch spiral retry
  (batch failure no longer kills all verification — proven need: one
  report shipped 0-verified when batch 1 spiraled at 4K). not-fully-
  supported rate: 27% → 6–16% run-to-run.
- **Investor presentation**: screener concall PPT links (BSE-hosted,
  trusted — validation failure falls back to url_context, never skips).
- **M3 reasoning spiral**: ~1–2 per run at Phase-5 context sizes, node-
  agnostic (hit 6 different nodes), retry-once converged 8/8 times.

**Watch for:** `[s9] reasoning-spiral truncation` (verifier retry is
live-unproven — first Phase 6 run confirms); `pe_own_history` present in
valuation_context; wisesheets layout changes (valuation read yielding <4
annual rows again).

## Backlog additions from Phase 5

- **Extraction-focus versioning**: changing a doc-class _FOCUS silently
  leaves stale stored extractions (only --reingest or manual invalidation
  fixes today). Stamp extraction entries with a focus hash; auto re-read
  on mismatch.
- ~~Claim-stripping variance~~ → D1 spec nudge added (2026-07-18).
- ~~M&M valuation_history_url~~ → SUPERSEDED: PE-history URLs are now
  ticker-derived templates in s1 with mandatory shape+IDENTITY validation
  (wisesheets resolved ticker "M&M.NS" to Macy's Inc — a wrong-company
  page passes any shape-only check; validator requires the company name
  in the page text). Config `valuation_history_url` remains as a rare
  escape hatch only. NOTE: wisesheets was connection-resetting probes on
  2026-07-18 — if M&M's Phase 6 run logs "candidate unreachable/failed
  validation", the percentile degrades to an honest insufficiency;
  consider a second template source then.

---

## Pre-Phase-5 batch (2026-07-17, validated live: 442/443 citations)

- `db.save_evidence` idempotent (reuse-on-text-match); 2 legacy duplicate
  rows deleted; 0 stuck runs found.
- `edge:<id>` is a blessed citation form: edges rendered with
  deterministic `[edge:from__relation__to]` labels (s4_synth.edge_id),
  resolver recomputes the set, contract documents it. 25 edge citations
  resolved in the gate run.
- Claims pool-gate in run_section: evidence ids not in THIS RUN's pool
  are stripped (logged per section); id-less claims not persisted. The
  `[db] WARNING dangling` class is gone.
- Table-cell discipline rules in F/s4e specs; s4e told to prefer blocks
  over claims[] (stripping went 19 → 0 immediately).
- **NEW documented no-retry exceptions:** (a) M3 reasoning death-spiral —
  stochastic, node-random (F at 48K, C at 64K, each fine other runs; up
  to 230K chars of reasoning with no content); envelope calls run at the
  64K provider cap and retry ONCE on TRUNCATED ("reasoning-spiral" log
  line). (b) cp1252 print crashes: main.py reconfigures stdout/stderr
  errors="replace" — a ₹ in a URL slug once killed a run mid-s2.

---

## What Phase 4 changed (financial forensic architecture, 2026-07-17)

New graph: `s3 → [B, E, D1(s4a_pl), D2(s4b_bs), D3(s4c_cf)] →
s4d_followup → s4e(synth_D) → F → G → H → C → I → J → s9 → s8`.
Statement nodes analyze their statement AND cross-examine every
management claim against computed numbers (`claim_checks[]`, strict
corroborated/contradicted/unverifiable). s4d pools the checks, validates
their evidence ids against the pool, and answers ≤2 follow-ups per node
(computed = Python lookup; evidence = ONE keyword-filtered call). s4e
writes integrated section D with the mandatory claims-vs-numbers
scoreboard; contradicted claims auto-feed F (credibility) and H (risk
candidates). Composer renders D as D1/D2/D3 sub-sections + synthesis.

Gate run (SONA, M3, 23 calls): 21 claims tested, 2 contradicted (the
>45% Low-Carbon-Mobility share → actual 19%; the 45%-EV-by-2026 target →
actual 35%); F's credibility read quantifies the bias ("conservative on
margins, over-states EV transition by 10–26pp"); H's #1 ranked risk is
the credibility gap. 359/369 citations resolved.

**Hard-won facts:** LangGraph list-form `add_edge([a,b],c)` is a join;
individual edges are TRIGGERS and re-ran the whole tail twice (caught in
dry-run — watch for doubled `[synth_X]` lines that are NOT interleaving).
M3 can exhaust max_tokens entirely inside `reasoning_content` (Fireworks
then omits `content`); llm.py now reports that as TRUNCATED; envelope
budget is 48K.

---

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

- **Phase 5** — 1M-context budgets, C full-feed, peer evidence packs,
  valuation own-history percentile, cost telemetry.
- **Phase 6** — SONA reingest re-validation, M&M end-to-end, golden set +
  `scripts/diff_golden.py`.
- Backlog additions from Phase 3/4 runs: `edge:<id>` citation form
  emitted by C — bless or map in composer resolver; several sections
  persist claims with dangling evidence ids (composer flags them; claim
  evidence ids could get the same s4d-style validation); verifier
  26/97 not-fully-supported worth a read-through (richer claim surface);
  evidence-row duplication on unchanged re-reads (pre-existing).

## Regression guards

```bash
python scripts/test_screener_parser.py --live   # after touching metric_names.py
python main.py --dry-run --ticker SONACOMS      # graph wiring, zero network
```
