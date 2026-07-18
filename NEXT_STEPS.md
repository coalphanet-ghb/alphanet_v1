# ALL SIX PHASES COMPLETE (2026-07-18). Golden set frozen.

---

# ARCHITECTURE PLAN — three-layer pipelines + Extraction 3.0 (owner-decided 2026-07-19)

Supersedes the O-plan below (its items are absorbed into phases R0–R5;
disposition at the end of this section). Direction unchanged: product
for others; report envelope = the future UI's contract; verifier =
product feature (full coverage stays); every change lands alone →
live run → diff_golden → owner green-flag or rollback.

## Target architecture

**MACRO PIPELINE** (unchanged): macro-layer reads, freshness-stamped,
rehydrated into stock runs.

**SECTOR PIPELINE** (elevated to first-class; auto-refreshed INLINE by
a stock run when its sector data is stale — one command still produces
a report):
- Sector registry: member stocks (= the peer set) + sector pack
  (synthesis overlay — already exists) + NEW sector ingestion skill
  doc (trusted sources, what to extract, how to analyse the sector).
- Numeric backbone for ALL member stocks, stored per stock and
  freshness-stamped: screener parse (zero-LLM), Yahoo closes, and
  computed PE history (annual closes ÷ annual EPS — correct formula,
  replaces wisesheets scraping entirely).
- Sector trusted-source reads → sector evidence layer, date-tagged.

**STOCK PIPELINE** (first-report generation; the update pipeline is a
later era). Ingestion = **Extraction 3.0** — every extracted line kept
VERBATIM with its evidence uuid (the citation spine is non-negotiable),
SECTION-MAPPED at ingestion (cross-section duplication is by design)
and DATE-TAGGED (e.g. AR release date). Storage (schema stays FROZEN —
verified against live schema 2026-07-19, see DB_SCHEMA.md):
- `evidence` has NO tags/section column — line-level attributes
  (tags, and now section maps) live in the `extract:{doc_id}`
  knowledge-entry JSON, exactly as tags do today, and are rehydrated
  into the run-time pool on reuse.
- Dates: `source_documents.published_date` exists — R3 must POPULATE
  it per doc class (AR release, concall quarter, PPT date, news pub
  date) and join it into the evidence pool; today it is often null.
- Per-node telemetry (R0): `runs` is scalar-only (no jsonb) — the
  per-node breakdown goes to local sidecar files
  (data/telemetry/{run_id}.json); `runs` keeps the aggregates.
- Sector membership (R2): `entity_relationships` with a new
  relationship_type value `member_of` (stock → sector entity) — text
  column, no schema change; sector trusted-source config + skill docs
  live in the repo (git-versioned), not the DB.
- Computed PE history stays DERIVED: raw closes + EPS are the stored
  metric_observations; the PE series is computed at run time in s3
  (no derived values in the observed-facts table).
1. **Latest AR only** (FY-1 dropped — owner 2026-07-19; the latest
   AR's prior-year comparatives + screener's 9y statements cover
   trends): ONE /chat/completions conversation, **3–5 thematic query
   bundles** (owner-picked), each with a FRESH 64K output budget —
   structurally kills the big-AR output overflow; no splitter needed.
   Terse-but-info-rich output demanded per bundle. The R0
   prefix-caching probe decides the exact bundle count (input is
   re-billed per query unless Fireworks discounts cached prefixes).
2. **Concalls ×4**: PARALLEL per-call extraction (shared skill doc;
   projections/guidance emphasized — feeds guidance tracking) + ONE
   cheap trails-pass over the four extraction outputs →
   guidance_evolution/recurring_themes (the batched call's
   cross-quarter view must not be lost in the split).
3. **Latest investor PPT**: one-shot, exhaustive — every
   number/guidance/claim/projection, section-mapped.
4. **Rating rationales (1–2)**: KEPT (owner green-flag) — unique
   leverage/liquidity/concentration view for D2/F/H.
5. **News batch**: as today (ddgs past-month, within the owner's ≤1y
   cap); open-source news sources parked for a later phase.

**DROPPED from stock ingestion** (owner 2026-07-19): FY-1 AR; results
PDFs (screener #quarters covers — revisit in the update pipeline);
separate shareholding read (screener parses the table incl. pledge);
valuepickr; wisesheets valuation_history.

**SYNTHESIS** (runs after all ingestion): per-section skills (specs) +
sector-pack overlay — shape unchanged; context assembly moves from
generic 40K doc-class walls to section-mapped evidence slices +
per-node calc slices. s9 verifier full coverage (excerpt-deduped) →
composer.

## Implementation phases

**R0 — Measure & probe** (no behavior change): per-call/per-node
telemetry incl. spiral rate per node; verifier trend stats; Fireworks
prefix-caching probe (repeated-prefix billing → sets AR bundle count);
reasoning-effort/thinking-budget param probe.
Gate: per-node cost table from one live run; probe verdicts written.

**R1 — No-regret cuts under STABLE goldens** (each green-flagged):
strip inputs[] from rendered calcs; verifier excerpt dedup;
reasoning-brevity line; computed PE history replaces wisesheets (fixes
the M&M percentile). Gate: diff_golden clean; cost drop measured.

**R2 — Sector pipeline elevation**: registry formalized; numeric
backbone moved to sector scope, stored per stock; inline auto-refresh
with freshness TTL; sector ingestion skill docs (auto_ancillaries +
auto_oem first). Gate: SONA stock run pulls its backbone from
sector-stored data; M&M peer table intact; dry-run wiring clean.

**R3 — Extraction 3.0** (the big rebuild; goldens RE-FROZEN after):
AR conversation extraction (bundles, section-mapped, date-tagged);
concalls parallel + trails-pass; PPT one-shot; the source drops
applied; extraction skill docs focus-hashed → auto re-read on change
(absorbs old focus-versioning). Gate: SONA + M&M full runs; M&M AR
ingested zero skips; citations ≥98%; goldens re-frozen as the new
baseline.

**R4 — Synthesis adaptation & slimming** (each cut vs the NEW goldens):
assemblers consume section-mapped evidence (the 40K walls collapse);
per-node calc slicing; F guidance-feed consolidation (six encodings →
scorecard + trails); J on summaries (selective full-D+H if quality
drops); C edge-cap audit; s4d_followup keep/simplify/remove per
evidence; TMPV non-comparability spec note; spiral-rate before/after
(the low-structure-context hypothesis test).
Gate: toward ~$0.5–0.7/run; goldens hold; spiral trend down.

**R5 — Product bridge** (next era entry): envelope JSON-schema
contract validated at compose time; per-run report manifest
(cost/citations/verifier stats); parked: open-source news ingestion,
update pipeline, UI rendering, NBFC pack.

## O-plan disposition (absorbed 2026-07-19)

O0→R0 · O1a→R1 · O1b/c/d/e→R4 · O2-wisesheets→R1 · O2-verifier-dedup→R1
· O2-spiral-levers→R0/R1/R4 · O2-s4d/news-audits→R4 · O3a/O3b
(AR-focus rewrite / splitter)→SUPERSEDED by R3's bundle design ·
O3-focus-versioning→R3 · O4→R5.

---

# [ABSORBED 2026-07-19 into the ARCHITECTURE PLAN above — kept for its per-item detail] NEXT ERA — Pipeline Optimization toward Product (drafted 2026-07-18, owner-reviewed)

**Direction (owner-set):** AlphaNet is heading toward a product for
others. This phase makes the pipeline lean, measured, and reliable.
The report envelope (typed blocks in `sections_json`) is the contract a
future UI will render — treat it as the API. Cost optimization matters,
but flow/functionality first. The s9 verifier is a PRODUCT FEATURE
(trust story) — full coverage stays; optimize only its efficiency.
Graph parallelization is OFF the table for now (sections deliberately
feed each other in a fixed flow); revisit only as a last step.

**Working discipline for every change in this era:** plan the cut →
implement it ALONE → dry-run → live run → `diff_golden` → **owner
green-flags or it rolls back**. One change in flight at a time.

## O0. Per-node telemetry (the measuring stick — do FIRST)

Attribute every LLM call in `src/llm.py` to its node id; persist
per-run, per-node tokens/cost/latency (runs table or JSON sidecar) and
print a per-node cost table at end of run. Fold in verifier trend
tracking (old backlog #5): persist per-run verifier stats so the 6–16%
not-fully-supported noise becomes a monitorable trend.
**Gate:** one live run prints the per-node cost/latency table; every
later cut in this era is justified by this data, not guesswork.

## O1. Context-duplication cuts (biggest expected cost win)

Baseline telemetry (prior session): ~380K input / 300–500K OUTPUT
tokens per run — output (which includes reasoning tokens) is at least
half the bill, so output-side cuts (O2 spiral work, O3 AR focus) weigh
as much as input dedup.

Ranked by effort-to-savings (verified against s4_synth.py):
- **O1a. Strip `inputs` arrays from rendered calc context** (keep in
  state/DB — lineage is persistence, not prompting). Every computed
  value carries observation-uuid lists (pe_1y_path alone carries
  dozens); models cite calc:<id>, never those uuids; the blob ships to
  ~8 prompts. One-line change in `_computed`'s rendering, zero quality
  risk, likely 30–50% of the computed blob × 8.
- **O1b. Slice `_computed` per node**: P&L calcs to D1, BS+battery to
  D2, CF to D3, small vitals subset to B/E/C; FULL blob only to s4e.
  Calc ids are already statement-prefixed — mechanical.
- **O1c. J back to summaries** (~10–15K/section instead of full
  envelopes at 100K). If diff_golden shows J degrading, go selective
  (full D+H, summaries elsewhere) — not full-everything.
- **O1d. Consolidate F's guidance feeds**: F currently receives SIX
  overlapping encodings (scorecard, claim-checks, open items, trails,
  themes, 40K raw concall). Load-bearing two = computed scorecard +
  labeled trails; open items largely duplicate trails; shrink the raw
  concall wall to guidance-tagged passages (tags exist from s2).
- **O1e. C's edge cap**: c_node renders up to 200 edges × ~350 chars
  (~70K) — audit how many golden C actually cites; cap accordingly.
- Audit the 40K evidence budgets: count which evidence classes each
  golden section actually CITES; shrink feeds nobody cites. KEEP H and
  C breadth (risk register + sensitivities demonstrably use it).

## O2. Remove fragile / low-value machinery (audit, then cut)

- **Retire valuation_history scraping** (wisesheets — Macy's incident,
  connection resets): compute the annual PE series from Yahoo yearly
  closes ÷ annual EPS (both already in hand). Fixes the M&M percentile
  gap (old #3) AND deletes the fragile source + its validators.
  **Gate:** M&M percentile renders from the computed series.
- **Verifier excerpt dedup** (coverage UNTOUCHED — efficiency only):
  claims cluster on the same passages, and s9 re-renders each 1200-char
  excerpt per claim within a batch. Render unique excerpts once with an
  index; claims reference indices. Roughly halves verifier input.
- **Audit s4d_followup:** count how many follow-up answers materially
  surface in golden D sections. Keep/simplify/remove per evidence.
- **Audit the news budget** (10 URLs): count news citations in goldens;
  reduce if low-value.
- **Reasoning-spiral mitigation:** (a) reasoning-brevity line in the
  ENVELOPE_CONTRACT preamble; (b) ONE-call probe of whether Fireworks'
  M3 endpoint accepts a reasoning-effort/thinking-budget param (never
  tried); (c) working hypothesis — spirals correlate with large
  low-structure contexts (frequency rose when Phase-5's 40K walls
  landed), so O1's cuts are plausibly also the spiral fix; O0 tracks
  spiral rate per node before/after to prove or kill it. Each
  spiral+retry burns a full 64K output budget (~$0.15–0.30/run).

## O3. Reliability — "any company just works" (reshaped old #1/#2)

A product cannot skip a company's main annual report or require the
operator to remember `--reingest`.
- **O3a FIRST — AR-focus rewrite (prompt edit, try BEFORE building the
  splitter)**: screener already supplies 9y of standard P&L/BS/CF
  deterministically at higher dedup authority (s3 `_obs_priority` —
  AR-extracted standard cells lose the dedup anyway). Add an explicit
  "SKIP standard statement line-items (supplied elsewhere); extract
  only what screener lacks — segment/geography/customer/RM tables,
  notes, disclosures" to the annual_report _FOCUS (and review
  results_pdf's "every line item" focus vs screener #quarters the same
  way). If M&M's FY-1 AR then fits in 64K output, the splitter is
  unnecessary. NUANCE: the current AR focus targets mostly disclosures
  already — the skip-list's value is stopping the model from ALSO
  dumping the statements it finds salient; measure via O0.
- **O3b. Large-AR split extraction** (old #1) — ONLY if O3a is
  insufficient: docs >~600K chars split into two calls
  (statements+notes / MD&A+prose), merged.
  **Gate:** M&M FY-1 AR ingested, zero skips.
- **Extraction-focus versioning** (old #2): focus-hash stamped on
  stored extractions; auto re-read on mismatch.
  **Gate:** change a focus, watch only affected docs re-read.
- **TMPV non-comparability note** in G's spec (old #4, shrunk to a spec
  note; TMCV peer edge dropped unless CV comparison is wanted later).

## O4. Report-contract hardening (the bridge to the UI phase)

- Freeze the envelope/block-type contract as a versioned JSON Schema,
  validated at compose time — this becomes the UI renderer's API
  (today it's prose in nodes/README.md).
- Verify `sections_json` + citations + per-claim verifier verdicts are
  complete enough to render a report without re-parsing markdown.
- Per-run report manifest (cost, citations resolved, verifier stats)
  for a future product dashboard.

## Old backlog disposition (owner-reviewed 2026-07-18)

| Old item | Disposition |
|---|---|
| #1 Large-AR split | KEEP → O3 (reliability, not optimization) |
| #2 Focus versioning | KEEP → O3 |
| #3 M&M valuation source | MODIFY → O2: compute PE internally, retire scraping |
| #4 TMPV note / TMCV edge | SHRINK → O3: spec note only; TMCV edge dropped |
| #5 Verifier trend tracking | MERGE → O0 telemetry |
| #6 Sprint-6 era (update workflow, sectors, UI) | NEXT PHASE — starts from the lean, contract-hardened base this era produces |

**Sequencing logic:** O0 measures → O1/O2 cut with per-change owner
green-flags → O3 makes any-company reliable → O4 freezes the contract
the UI phase will build on. Parallelization only after all of that, if
ever.

---

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
