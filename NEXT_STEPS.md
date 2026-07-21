# ALL SIX PHASES COMPLETE (2026-07-18). Golden set frozen.

---

# THE FIVE-ROUND PLAN — de-clutter the pipeline end to end (owner-final 2026-07-21)

Absorbs the R0–R5 architecture plan (kept below for its target
architecture + storage table) wholesale — R0→Round 1 (plus the
tag-persistence fix found 2026-07-21), R1→Round 2, R2→Round 3,
R3→Round 4, R4+R5→Round 5 — and through it the O-plan (bottom of file,
kept for per-item mechanics). Locked directions, unchanged: product
for others; the report envelope is the future UI's API; the s9
verifier is a PRODUCT FEATURE (full coverage stays); the fixed
F→G→H→C→I→J flow stays; DB schema FROZEN (DB_SCHEMA.md); the
deterministic spine (unit guard, claims pool-gate, identity
validation) is untouchable. Discipline: every change lands ALONE →
dry-run → live run → diff_golden → owner green-flag or rollback. One
change in flight at a time.

## The waste model — the goal, stated measurably

Baseline: ~380K input / 300–500K output tokens, $0.8–1.4, ~25 min per
run. At M3 pricing (in $0.55/M, out $2.19/M) ONE OUTPUT TOKEN COSTS AS
MUCH AS FOUR INPUT TOKENS, and output (which includes all hidden
reasoning) is at least half the bill. Every plan item cuts one of
three waste classes — the test any future item must also pass:

**INPUT waste** — billed prompt tokens the model can never use:
- the computed-financials blob JSON-dumped into 8 prompts
  (B/D1/D2/D3/D/E/F/C), each copy carrying inputs[] uuid-lineage
  arrays models never cite (they cite calc:<id>, never the uuids);
- the same 40K evidence walls fed to several nodes (concall wall to
  D1+D3+F; AR wall to D2+D3+B+E), greedily head-first, no per-node
  relevance;
- J: 8 envelopes × up to 100K chars in, a 4-block section out — the
  worst input→output ratio in the graph;
- C: up to 200 edges ≈ 70K chars, far beyond what golden C cites;
- F: ten context feeds, six of them overlapping encodings of guidance;
- verifier: the same 1,200-char excerpt re-rendered for every claim
  citing it within a batch.

**MIDDLE waste** — machinery doing work the pipeline discards,
duplicates, or shouldn't own:
- wisesheets valuation-history scraping + its validators, replaceable
  by dividing two series already stored (closes ÷ EPS);
- reads that lose to screener in s3 dedup (_DOC_PRIORITY: screener
  90–100 vs results_pdf 80 vs annual_report 60): AR statement cells,
  results PDFs; plus FY-1 AR, valuepickr, separate shareholding —
  dropped by owner decision 2026-07-19;
- stale extractions silently reused after focus-prompt changes (no
  focus-hash);
- numeric-backbone work (screener parse, closes) re-done per stock run
  though it is sector-scoped by nature;
- the TAG-PERSISTENCE GAP (verified in code 2026-07-21): per-passage
  tags are never persisted and reuse hard-sets tags=[] — H's
  risk_signal 40K feed starves on reuse runs, tag-filtered feeds
  cannot be built on, and reuse-run diffs vs the (all-fresh) goldens
  lie.

**OUTPUT waste** — billed completion tokens that produce nothing:
- reasoning spirals: 1–2/run × a full 64K budget ≈ $0.15–0.30/run
  (hypothesis: correlates with large low-structure contexts — Round 1
  measures per node, Round 5 verdicts);
- the M&M FY-1 conglomerate AR: overflowed 64K output TWICE (paid
  both attempts), then skipped — extraction paid for and discarded;
- AR/results extraction of standard statement cells that s3 dedup
  throws away (screener outranks them);
- every spiral/truncation retry re-bills the input too.

Rounds 1–2 cut waste while the CURRENT goldens are still a fair
baseline; Round 3 restructures ownership of shared work; Round 4
rebuilds ingestion (goldens RE-FROZEN — after it the old baseline is
no longer a fair diff); Round 5 slims synthesis against the NEW
goldens and freezes the product contract. That ordering is
load-bearing.

## Round 1 — Baseline: measure, probe, un-poison the diff  [CODE LANDED 2026-07-21 — gate runs DEFERRED by owner]

Goal: every later cut justified by a table, not a guess — and repair
the one defect that makes reuse-run diffs unusable as arbitration.

| # | Item | Waste class hit |
|---|---|---|
| 1.1 | Per-node telemetry in llm.py: THREAD-LOCAL node id (the B/E/D1/D2/D3 wave runs parallel — a global would misattribute); per-node calls/tokens/cached-tokens/latency/cost + spiral & truncation counters at the three retry sites (run_section, s2 _extract_call, s9 batches); sidecar data/telemetry/{run_id}.json (runs table stays scalar — DB_SCHEMA.md); end-of-run per-node cost table | enabler for ALL — turns input+output waste into line items |
| 1.2 | Verifier trend stats into the sidecar (claims checked, by-verdict, batches) — the 6–16% noise becomes a monitorable trend | enabler — protects the verifier product feature while it is optimized |
| 1.3 | TAG-PERSISTENCE FIX (the round's one deliberate behavior change): persist per-passage evidence_id→tags in extract:{doc_id}; rehydrate on reuse; backfill risk_signal from stored risk_evidence_ids for pre-fix entries | MIDDLE — reuse runs stop starving H's risk feed; prerequisite for Round 5's tag-filtered feeds AND for trusting every diff_golden verdict from Round 2 on |
| 1.4 | Fireworks prefix-caching probe (via the new raw multi-turn chat helper — the conversation API Round 4 needs did not exist in llm.py) — does usage report cached_tokens, is it discounted? → sets Round 4's AR bundle count (3 vs 5) | INPUT — prices the AR-conversation design before committing to it |
| 1.5 | Reasoning-effort / thinking-budget param probe on the M3 endpoint (never tried) | OUTPUT — a param capping reasoning would attack spirals directly |

Gate: SONA --reingest run (repopulates tags under 1.3 + telemetry on
the heaviest path) AND one normal run (reuse path) — per-node cost
tables from both, diff_golden clean on both, probe verdicts logged
below.

## Round 2 — No-regret cuts  [CODE LANDED 2026-07-21 — see Round 2 log]

Goal: the cheap 80% of input/output cuts whose quality risk is ~zero,
taken while the frozen goldens are still a fair baseline.

| # | Item | Waste class hit |
|---|---|---|
| 2.1 | Strip inputs[] uuid arrays from rendered calc context (_computed in s4_synth; lineage stays in state/DB — persistence concern, not prompt concern) | INPUT — est. 30–50% of the calc blob × 8 prompts; best effort-to-savings ratio in the pipeline |
| 2.2 | Verifier excerpt dedup: render each unique excerpt once per batch with an index; claims reference indices. Coverage UNTOUCHED | INPUT — ~half of verifier input; the trust story keeps full coverage |
| 2.3 | Reasoning-brevity line in ENVELOPE_CONTRACT (+ apply the effort param if probe 1.5 said yes) | OUTPUT — attacks the $0.15–0.30/run spiral burn |
| 2.4 | Retire wisesheets: compute annual PE (yearly closes ÷ annual EPS, both already stored) in s3; delete the valuation_history read, focus and validators | MIDDLE — deletes a fragile source (Macy's incident, connection resets) and FIXES the M&M own-history percentile insufficiency |

Gate: per-node tables show the drop cut-by-cut; M&M percentile
renders from the computed series; diff_golden clean after EVERY single
cut. Expected: ~$1.0 → ~$0.7.

## Round 3 — Sector pipeline elevation  [CODE LANDED 2026-07-21 — see Round 3 log]

Goal: move sector-scoped work out of the per-stock hot path so Round
4's stock pipeline can assume it. Structure, not cuts — lands before
the rebuild that depends on it.

| # | Item | Waste class hit |
|---|---|---|
| 3.1 | Sector registry: member stocks (= the peer set) migrate OUT of config.COMPANIES peer_screener_slugs; member_of entity_relationships (text value — schema stays frozen) | MIDDLE — peer sets become sector data, not per-company hardcode |
| 3.2 | Numeric backbone sector-scoped: screener parse + Yahoo closes (+ computed-PE inputs) run per SECTOR, stored per member stock, freshness-TTL'd, auto-refreshed INLINE by a stale stock run (one command still produces a report) | MIDDLE — N member stocks stop re-doing the same deterministic work; peers' data is already there when any member runs |
| 3.3 | Sector ingestion skill docs (trusted sources, what to extract, how to analyse) for auto_ancillaries + auto_oem — repo files, git-versioned | enabler — the sector layer gets first-class inputs, not just a synthesis overlay |

Gate: SONA stock run pulls its backbone from sector-stored data; M&M
5-peer table intact; dry-run wiring clean.

## Round 4 — Extraction 3.0  [CODE LANDED 2026-07-22 — see Round 4 log; goldens RE-FROZEN at gate]

Goal: restructure ingestion so extraction spends output tokens only on
what downstream keeps — and never overflows.

| # | Item | Waste class hit |
|---|---|---|
| 4.1 | Latest-AR-only conversation: ONE /chat/completions conversation (chat API productionized from probe 1.4's helper), 3–5 thematic bundles (count = 1.4's verdict), each with a FRESH 64K output budget; terse-but-info-rich demanded; SKIP standard statement line-items (screener supplies them at higher dedup authority) | OUTPUT — structurally kills the big-AR overflow (no splitter ever built) + stops paying for statement cells dedup discards. INPUT — bundle count set by measured caching economics |
| 4.2 | Every extracted line verbatim + uuid (citation spine untouchable), SECTION-MAPPED at ingestion (cross-section duplication by design), DATE-TAGGED (source_documents.published_date populated per doc class, joined into the pool) | enabler for Round 5's INPUT cuts — per-section slices replace the 40K walls |
| 4.3 | Concalls ×4 PARALLEL per-call + ONE cheap trails-pass over the four extraction outputs → guidance_evolution / recurring_themes (cross-quarter view preserved; trails-pass input = extractions, not transcripts) | MIDDLE — isolation per call; the trails-pass reads ~10K instead of 4 transcripts |
| 4.4 | PPT one-shot exhaustive (every number/guidance/claim/projection, section-mapped); rating rationales kept; news as today (≤1y cap) | kept-value items, no waste added |
| 4.5 | DROPS: FY-1 AR, results_pdf, valuepickr, separate shareholding read (owner 2026-07-19) | MIDDLE — four read classes whose content loses dedup or adds little |
| 4.6 | Focus-hash stamped in extract:{doc_id} → auto re-read on prompt change | MIDDLE — kills the stale-extraction class (today: --reingest or manual invalidation only) |

Gate: SONA + M&M full runs; M&M AR ingested ZERO skips; citations
≥98%; goldens RE-FROZEN as the new baseline.

## Round 5 — Synthesis slimming + contract freeze  [CODE LANDED 2026-07-22 — see Round 5 log]

Goal: collapse the generic context walls into targeted slices, prove
or kill the spiral hypothesis, freeze the contract the product phase
builds on.

| # | Item | Waste class hit |
|---|---|---|
| 5.1 | Section-mapped context assembly: _evidence consumes 4.2's section maps — the generic 40K doc-class walls collapse into per-section slices | INPUT — the single biggest wall-cut, quality-safe because mapping happened at ingestion |
| 5.2 | Per-node calc slicing: P&L→D1, BS+battery→D2, CF→D3, vitals→B/E/C; FULL blob only to s4e (calc ids are statement-prefixed — mechanical) | INPUT — ends the ×8 blob duplication that Round 2 only thinned |
| 5.3 | F feed consolidation: ten feeds → computed scorecard + labeled trails + guidance-tagged passages (tags persist since 1.3) | INPUT — six overlapping guidance encodings → two-plus-slice |
| 5.4 | J on 10–15K summaries (selective full D+H ONLY if diff_golden shows degradation); C edge-cap set to what goldens actually cite; s4d_followup + news budget keep/cut per citation-count evidence; TMPV non-comparability spec note | INPUT (J, C) + MIDDLE (s4d/news audits) |
| 5.5 | Spiral verdict: Round-1 vs Round-5 per-node spiral rates — proves or kills the low-structure-context hypothesis (KEEP H+C breadth either way: risk register + sensitivities demonstrably use it) | OUTPUT — if confirmed, the input cuts double as the spiral fix |
| 5.6 | Contract freeze: envelope/block JSON Schema validated at compose time; per-run report manifest (cost, citations, verifier stats) | product bridge — the UI phase renders THIS, never re-parses markdown |

Gate: ~$0.5–0.7/run; NEW goldens hold; spiral trend down; schema
validation live. Exit = product era (UI, update pipeline, NBFC pack).

## Round 1 log (verdicts land here as they happen)

- **1.4 prefix caching: ACTIVE** (probed 2026-07-21,
  scripts/probe_fireworks.py). Serverless M3 reports
  usage.prompt_tokens_details.cached_tokens; a 16,652-token repeated
  prefix hit 16,651 cached. CAVEAT: cache-write lags — two identical-
  prefix calls 2.5s apart both missed (cached=0); minutes later the
  same prefix fully hit. Round 4 implication: the AR conversation is
  viable at 4–5 bundles, but bundle calls should be modestly PACED
  (~30s+) so bundles 2+ hit the cached AR prefix; billing discount on
  cached tokens to be confirmed on the Fireworks invoice after the
  first real run.
- **1.5 reasoning effort: SUPPORTED, and "none" is a real switch**
  (probed 2026-07-21). `reasoning_effort` is accepted;
  `"none"` disabled reasoning entirely (completion 52 → 2 tokens on
  the test task); `"low"` was indistinguishable from default on a
  trivial task. `max_reasoning_tokens` rejected (HTTP 400).
  Round 2.3 candidates for `"none"`: s2 extraction (quote-and-record,
  not analysis) and possibly s9 verification — each lands alone under
  diff_golden like any other cut.
- (pending) per-node baseline tables (reingest + normal runs) →
  data/telemetry/{run_id}.json

## Round 2 log

All four cuts implemented 2026-07-21 (compile + dry-run clean).
**DISCIPLINE DEVIATION (owner-decided): the Round-1 gate runs were
skipped, so Rounds 1+2 will be validated TOGETHER on the next live
runs — per-cut diff_golden attribution is lost for this batch; if the
diff flags, bisect by reverting cuts one at a time.**

- **2.1** inputs[] stripped from rendered calc context
  (`_strip_lineage` in s4_synth; also applied to s4d computed lookups).
  Lineage stays in state/DB.
- **2.2** verifier excerpt dedup: unique excerpts rendered once per
  batch as [E<n>], claims reference ids; _SYSTEM rewritten accordingly
  + a brevity line. Coverage untouched.
- **2.3** ENVELOPE_CONTRACT rule 9 (reason briefly, one pass).
  reasoning_effort plumbed llm→config: REASONING_EFFORT_EXTRACT /
  REASONING_EFFORT_VERIFY env vars, DEFAULT OFF — activate one at a
  time via .env on a validated run ("none" disables M3 reasoning
  per probe 1.5).
- **2.4** wisesheets RETIRED (s1 read + validators + focus + query-bank
  hunt deleted). s2 now also pulls Yahoo 10y monthly → FY-end (March)
  closes (zero LLM, identity-validated, "Mar YYYY" parses as the FY);
  s3 computes annual PE = FY close ÷ annual EPS and derives
  pe_own_history + re_rating_3y from the computed series.
  Verified live (free): SONA = 5 FY closes (listed June 2021 — the old
  "9-year" wisesheets range was always suspect for a 2021 IPO; expect
  diff_golden to flag percentile n_years 9→5, defensible). M&M gets
  the full 10 years → its percentile insufficiency becomes computed.

**Run 1 verdict (SONA v19, 2026-07-21, $1.25 — first validation run):**
- Telemetry table LIVE (run 20f1b2c9). Headlines: `s2:annual_report`
  $0.48 = 38% of the run — the FY26 AR re-read FRESH because BSE's
  `Pname=<guid>` URL rotated, so URL-keyed reuse missed (and the fetch
  hit the 1.2M-char cap; extraction truncated once then converged).
  Adjusted reuse-run cost ≈ $0.77 (was $0.8–1.4). Synth+verifier input
  ≈ 293K tokens vs ~380K baseline (~23% cut from 2.1+2.2). ZERO
  spirals in 36 calls (baseline 1–2/run; contract rule 9's first
  outing). Verifier ~2.7K tokens/batch (dedup working). Cache
  confirmed in production: D3's retry hit 22,853 cached tokens.
- **Measured correction to the plan: J was an overestimated target** —
  its real input is 26.7K tokens ($0.083), not ~200K; envelope
  summaries sit far under their 100K caps. Round 5.4's J-summaries cut
  is demoted to minor. F (36.5K in) confirmed as the input heavyweight
  → 5.3 stands.
- **Regression found + fixed same day: 512/550 citations (6.9%
  unresolved; golden 0.4%), diff_golden FLAG.** Root causes: (a)
  resolver gap — `evidence:<8-hex>` shorthand (copied by I from H's
  inline prose via _envelope_summary) resolved as neither the
  `evidence:` branch (full-uuid only) nor the bare-prefix branch →
  FIXED, prefix accepted; (b) upstream-summary contagion — FIXED
  deterministically: `_strip_inline_evidence` removes [uuid]/
  [evidence:8hex] markers from summary md (sec:/calc:/edge:/trail:
  labels kept), so downstream nodes physically cannot copy evidence
  ids they were not given (best-practice #4: fix renderers, not
  prompts); (c) 2–3 model-mangled uuids (c4656c73-**6c9a** vs golden
  …-**c6a9**, transposed) — known low-rate class, block citations
  have no pool-gate; watch.
- Also observed: 85 id-less claims stripped (C 20/57, I 24/24 —
  rule-3 drift; verifier coverage 183 vs 192); D claims 20→9
  (-50% heuristic flag; within the 8–20 contract floor — variance,
  watch). NEW BACKLOG (middle waste): reuse-by-content-hash after the
  FREE local fetch, so rotated BSE URLs stop forcing $0.48 re-reads
  (today reuse is URL-keyed only).

**Next: rerun SONA (~$0.8 — the AR is now stored under its new URL,
so full reuse) → expect citations ≥98% and no FLAG beyond the known
percentile n_years 9→5. Then M&M (percentile computed, was
insufficiency).**

## Round 3 log

Implemented 2026-07-21; compile + dry-run clean; the zero-LLM parts
LIVE-TESTED (free) — Auto Components backbone refreshed for all 9
members, stamp fresh, fresh-path load + s2 rehydration asserts pass
(4,635 screener candidates, 18 own price points, 9 about passages, 9
doc-link sets), 9 member_of edges written.

- **3.1 registry**: `members` (+`sector_entity`) added to
  auto_ancillaries.json (9) and auto_oem.json (6, incl. TMCV);
  `peer_screener_slugs` REMOVED from config.COMPANIES — s1's fallback
  path now derives peer URLs from the registry too. peer_of edges
  still decide the peer TABLE (TMCV parses, doesn't join — unchanged).
  `packs.sector_members()` + `packs.ingest_doc()` accessors.
- **3.2 backbone**: new `src/ingestion/sector_backbone.py` —
  ensure/refresh/load; per-member `backbone:{slug}` knowledge entries
  (layer industry, on the sector entity) + `backbone_stamp` TTL marker
  (SECTOR_BACKBONE_FRESH_DAYS=1, env-overridable); refresh stores
  screener candidates + about + doc links + 13 monthly closes + 10y
  FY-end closes per member and ensures `member_of` edges. s1 ensures
  the backbone inline (stale → refresh; one command still produces a
  report) and emits NO screener reads when it serves; s2
  `_rehydrate_backbone` pours it into the pools in the exact in-run
  parser shape (s3 untouched). Fallbacks at every step → classic
  per-run screener reads. `--refresh-sector` CLI forces refresh.
  Graceful-degradation proof from the live test: HAPPYFORGE's Yahoo
  lookup returned an empty longName → identity check refused, member
  stored candidates-only. BONUS: peers' FY-close series now stored →
  peer PE history computable later for free.
- **3.3 skill docs**: `auto_ancillaries.ingest.md` + `auto_oem.ingest.md`
  (trusted sources, what to extract, sector analysis judgement notes) —
  consumed by Round 4's sector trusted-source reads via
  `packs.ingest_doc`.

Gate remainder (needs the next PAID run): SONA full run pulling its
backbone from sector storage end-to-end + M&M peer table intact +
diff_golden — folded into the combined Rounds 1+2+3 validation run.

## Combined validation run verdict (SONA v20, 2026-07-21, $0.60)

**Cost: $1.0–1.4 baseline → $0.60** (24 calls, 340K in / 189K out;
wall 19 min). Backbone served 9 member screeners with zero fetches;
AR fully reused; ZERO spirals AND zero truncations (2nd consecutive
spiral-free run); citations 463/466 = 99.4% (unresolved-rate FLAG
cleared; two of the three leftovers are junk citation strings, one is
the recurring mangled uuid). Output halved vs v19 (189K vs 340K) —
rule 9 working hard.

**Residual defects found + fixed same day (validate on next run):**
1. **Envelope over-compression**: H packed a full, high-quality 8-risk
   register into one ranked_list but emitted 0 claims[] and 0
   insufficiencies (J: 3 claims) — the verifier had NOTHING to check
   in H. Rule 9 amended: brevity is REASONING-ONLY; required blocks +
   rule-3a claims floor + insufficiencies are never sacrificed ("a
   thin envelope is a defect, not efficiency").
2. **evidence_id_raw leak**: f4ba4117… (confirmed NOT in DB — a
   mangled id) cited in v19's H and v20's F. Vector: s4d keeps nulled
   ids as evidence_id_raw for audit, and the checks JSON was rendered
   verbatim into D/F/H prompts. New `_checks_json` renderer strips it
   (audit trail stays in state).

diff_golden v18→v20 flags, dispositioned: H BLOCKS/CLAIMS −50% =
defect #1 above (content itself full-quality); D 8 and J 3 claims =
same class; C 30 claims healthy. Expect all three to clear next run.

## Round 4 log

All six items implemented 2026-07-22 (compile + dry-run clean; hashes/
date-cleaning unit-checked). Owner decision recorded: prompt-level
optimization of SYNTHESIS nodes is deferred to after Round 5 (no point
tuning prompts whose context is about to be re-sliced); extraction
terseness lands here (the AR bundle contract demands terse-but-rich).

- **4.6 focus-hash** (landed first — makes the rest safe): sha256 of
  (focus+schema[+AR bundles])[:16] stamped in every extract:{doc_id};
  reuse compares and re-reads on mismatch. Pre-R4 entries are unhashed
  → the NEXT RUN RE-READS ALL COMPANY DOCS ONCE (that IS the gate
  reingest) and stamps them.
- **4.5 drops**: FY-1 AR (the chronic 64K overflow), results_pdf,
  shareholding hunt, valuepickr — s1 emission + query banks + s2
  focuses/type-map all removed.
- **4.2 section maps + dates**: extraction schema now demands
  per-passage `sections` ([B..I], multi allowed, duplication by
  design) and per-source `published_date` (strict YYYY-MM-DD or null →
  source_documents.published_date). Persisted as passage_sections +
  published_date in extract:{doc_id}; pool entries carry
  sections/date; rehydrated on reuse. Round 5.1 consumes these.
- **4.1 AR conversation**: `_ar_conversation` — 5 bundles,
  OWNER-DESIGNED 2026-07-22: company_and_scale / business_model /
  growth_outlook / management_commentary + statement_disclosures (kept
  as the 5th: the AR is the only notes-level source and D1/D2/D3
  forensics feed on it). Each bundle = ONE call sharing the identical
  [system, document] prefix (cache-served; generation time covers the
  cache-write lag) with a FRESH 64K output budget. Style contract:
  POINTERS NOT PARAGRAPHS — shortest VERBATIM snippet (≤40 words;
  paraphrase forbidden, the verifier needs verbatim evidence), numbers
  → metric_candidates. statement_disclosures carries the explicit
  SKIP-standard-line-items rule; per-bundle truncation reprompt-once;
  a failing bundle is skipped ALONE (the old single call lost the
  whole doc); passages deduped across bundles; per-bundle cached-token
  logging. url_context fallback keeps the single-call path.
  COST NOTE (owner asked): the conversation re-sends the AR per bundle
  — worst case (no cache discount) ~$0.70 input for a 250K-token AR vs
  $0.14 single-call; probe-verified prefix caching makes the real
  figure far lower (gate run's per-bundle `cached N tok` lines prove
  it), bought for: fresh 64K per theme (kills the M&M skip), lower
  truncation/spiral odds, and terser output on the expensive side.
- **4.3 concall split + trails-pass**: batching machinery deleted;
  per-transcript reads; guidance_items carry quarter_label (fresh AND
  reused paths); any fresh concall triggers `_concall_trails_pass` —
  ONE 16K call over per-quarter OUTPUTS (grouped items + tagged
  passages, ≤12K chars) rebuilding guidance_evolution/recurring_themes;
  all-reused runs rehydrate the stored entry as before.
- **4.4 PPT**: focus upgraded to explicit exhaustive one-shot ("miss
  nothing quantitative").

**GATE (paid, owner-triggered): SONA run (~$1.5–2: focus-hash forces
the one-time full re-read) then M&M run — M&M AR zero skips via
bundles; citations ≥98%; then `diff_golden --freeze` BOTH as the new
golden baseline (old goldens stop being a fair diff after this).**

**R4 gate outcome (2026-07-22):** first SONA attempt aborted at synth_I
on a 600s transport read-timeout (slow-spiral shape) → retry-once added
for envelope calls / verifier batches / AR bundles (HANDOFF3 §5 #6).
Retry run = SONA v21: NO diff_golden regression flags, 98.1%
citations, 0 spirals/truncations, AR conversation 5/5 bundles with
286,272 cached tokens per repeat bundle (cache economics PROVEN),
trails-pass 23 trails, PPT recovered, $0.70. **v21 FROZEN as the new
SONA golden.** Owner: M&M deferred to the VERY END (after Round 5).
Watch items from v21: verifier partials elevated (25 — possible
≤40-word-pointer effect; M&M decides), 2 mangled uuids, invented
`events:` citation shorthand (fixed in Round 5 below).

## Round 5 log

All items implemented 2026-07-22 (compile + dry-run clean; validator,
event labels, section/calc slicing unit-checked). Baseline = golden
v21. Owner sequencing: SONA validation run next, M&M at the very end.

- **5.1 section-sliced evidence**: `_evidence(..., section=)` consumes
  Round-4.2 maps — two-pass fill (section-matched first, unmapped
  legacy as filler, other-section-only EXCLUDED); evidence headers now
  also carry the doc date. Applied: B/E (15K), D1 (40K→24K), D2
  (40K→24K + concall 12K→10K), D3 (40K→24K), F (below). H and C keep
  full breadth BY DESIGN (risk register + sensitivities earn it).
- **5.2 calc slices**: `_computed(..., slice_=)` — statement slices to
  D1/D2/D3 (substring membership, overlap fine), vitals to B/E/C/F;
  FULL blob only to s4e. The ×8 blob duplication is ended.
- **5.3 F consolidation**: open guidance items DROPPED (duplicate
  trails); concall wall 40K→16K F-sliced; governance 20K→12K F-sliced;
  calc → vitals. Scorecard + trails + themes remain the guidance record.
- **5.4**: C edge cap 200→60 (~50K chars cut); TMPV/post-restructuring
  non-comparability rule added to G's spec (instruction 6); audits
  closed with verdicts — s4d_followup KEEP ($0.004/run, measured
  harmless), news budget KEEP (owner's ≤1y stance; citations do land
  in F/H), J KEEP as-is (measured 26.7K in — the 100K-cap fear was
  disproven by telemetry).
- **5.5 spiral verdict**: post-rule-9 + input cuts: 0 spirals in ~90
  calls across 3 full runs (baseline 1–2/run × 64K burns). One slow
  variant hit the transport ceiling once (now retryable). VERDICT:
  the low-structure-context hypothesis + reasoning-brevity rule are
  jointly confirmed as the fix; per-node spiral telemetry continues as
  the regression tripwire.
- **5.6 contract freeze**: `validate_envelope` in s8_composer —
  ENVELOPE_CONTRACT_VERSION 1.0.0, per-block-type required fields,
  validated at compose time, violations logged + recorded (non-fatal);
  per-run MANIFEST rides the telemetry sidecar (report path, contract
  version, citation/verifier stats, per-section block/claim counts,
  schema issues); report_versions.sections_json carries the contract
  version.
- **Backlog swept**: `[event:<id>]` deterministic labels for the
  events pool + resolver branch + contract citation form (kills the
  invented `events:` shorthand); verifier _MAX_CALLS 10→12 (209 tasks
  once exceeded 200 — full coverage restored); **content-hash reuse**
  — fetched text hashed (`fetch_hash` in doc metadata), rotated URLs
  (BSE Pname guids) now reuse the stored extraction when the focus
  matches instead of paying for a re-read ($0.48 + $0.047 observed
  losses of this class).

**GATE: SONA run vs golden v21** — expect: slimmer synth inputs
(D-family/F), C input down ~12K tokens, citations ≥98%, envelope
contract violations = 0 or explained, verifier coverage complete
(no budget-cap line). Then owner green-flag → freeze v22 if diff is
clean-or-better → **M&M as the final validation** (auto_oem backbone
build + AR zero-skips + percentile computed + verifier-partials
comparison for the pointer-style question).

**GATE RESULT (SONA v22, 2026-07-22): PASSED — best run in project
history.** $0.53 (era baseline $1.0–1.4), wall 10.5 min (was 19–25),
citations 579/580 = 99.8% (project record; the 1 miss is a single
mangled uuid), NO diff flags vs v21, schema_issues {} (contract v1.0.0
clean on all 12 sections), verifier FULL coverage (231/231, 12
batches), 0 spirals/truncations, invented-events shorthand GONE.
Measured input cuts vs v21: D2 −66%, D3 −63%, F −41%, D1 −30%, total
input −31%, output −22%. Verifier is now the top cost node ($0.092) —
the trust feature as the biggest line item is the correct end-state.
WATCHES: (1) verifier not-fully-supported 22.5% (43 partial) — 3rd
elevated run since the terse AR; M&M is the decider; (2) E 31 / F 34
claims exceed the 8–20 band's ceiling — feeds verifier load; consider
re-asserting the ceiling if M&M repeats it.

## THE PLAN IS CODE-COMPLETE. What remains after the SONA+M&M gates:
product era (update pipeline, UI renderer on the frozen contract,
more sectors/NBFC pack, open-source news sources), the restatement
policy decision for metric_observations, and the watch list (verifier
partial rate, mangled-uuid rate, I's output variance).

---

# [ABSORBED 2026-07-21 into the FIVE-ROUND PLAN above — kept for its target architecture + storage decisions] ARCHITECTURE PLAN — three-layer pipelines + Extraction 3.0 (owner-decided 2026-07-19)

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
