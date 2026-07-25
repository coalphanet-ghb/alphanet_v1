# HANDOFF 4 — AlphaNet session handoff (2026-07-22)

> For the next assistant session. The previous sessions (2026-07-21/22)
> executed the FIVE-ROUND de-clutter plan end to end — telemetry,
> no-regret cuts, the sector pipeline, Extraction 3.0, synthesis
> slimming and the frozen envelope contract. **The plan is
> code-complete and SONA-validated: golden v22 (owner-frozen) at
> $0.53/run, 10.5 min, 99.8% citations, zero spirals.** Where this doc
> disagrees with HANDOFF3 or the memory file, THIS FILE WINS.
>
> **Since then (2026-07-22, in order):** M&M ran its final validation
> (§7.1 gates — analysed below, golden v4), then **CITATION LABELS**
> landed and were validated (§2b, golden **v5** — the current M&M
> baseline). Next up is the AR optimisation, then the UI era (§7).

---

## 1. Reading order (30 minutes to full context)

1. **This file** end to end.
2. **NEXT_STEPS.md** — "THE ROAD AHEAD" section at the bottom is the
   owner-sequenced work order; the five ROUND LOGS above it are the
   detailed history of what changed and why (waste-model framing).
3. **HANDOFF3.md** — still the best deep description of the base
   system (graph, gates, ethos); its §8 backlog is fully absorbed.
   §5 retry policy now has SIX exceptions (see §5 below).
3b. **FOUNDATIONS.md** — timeless layer: product identity and the
   no-Buy/Sell/Hold rule, settled architecture decisions WITH their
   rationale (why the citation check is app-code, why embeddings stay
   null, why no graph DB / no MCP), anti-hallucination principles, the
   12 best practices, the skeptical-read quality bar, and the
   **compliance risks (copyright + SEBI RA framework) that must be
   reviewed before the UI era ships to anyone but the owner**.
   Consolidated 2026-07-22 from the deleted HANDOFF.md + HANDOFF2.md.
4. **DB_SCHEMA.md** — frozen schema + invariants (unchanged, one
   convention added: extract:{doc_id} now carries passage_tags,
   passage_sections, published_date, focus_hash).
5. **GENERALIZATION_PLAN.md** — the LONG-TERM deliverable (Midcap 150
   audit + universe + G0–G4). Owner: do NOT execute yet.
6. Golden reports: `data/golden/SONACOMS.json` = v22
   (data/reports/SONACOMS_20260721_211916.md — read it end to end).

## 2. What changed since HANDOFF3 (the five rounds, compressed)

**R1 — Measure**: per-node telemetry in llm.py (thread-local node id;
sidecars `data/telemetry/{run_id}.json`; spiral/truncation counters;
verifier trend stats; end-of-run cost table). Tag-persistence FIX
(passage_tags in extract entries — reuse used to hard-set tags=[] and
starve H). Probes: Fireworks prefix caching ACTIVE (cache-write lags
~seconds-minutes); `reasoning_effort:"none"` fully disables M3
reasoning (52→2 tokens) — plumbed as REASONING_EFFORT_EXTRACT/_VERIFY
env knobs, DEFAULT OFF, never yet enabled.

**R2 — No-regret cuts**: inputs[] lineage stripped from all rendered
calc context (`_strip_lineage`); verifier excerpt dedup ([E<n>]
indexing); ENVELOPE_CONTRACT rule 9 (reason briefly — REASONING only,
envelope completeness explicitly protected after H once emitted 0
claims); wisesheets RETIRED — annual PE computed in s3 from Yahoo 10y
FY-end closes ÷ annual EPS (SONA n_years 9→5 is CORRECT: it listed
June 2021; M&M gets full 10y and its percentile stops being an
insufficiency).

**R3 — Sector pipeline**: pack JSONs carry `members` (registry) +
`sector_entity`; `src/ingestion/sector_backbone.py` refreshes
screener+price series for ALL members once per TTL
(SECTOR_BACKBONE_FRESH_DAYS=1) into backbone:{slug} knowledge entries;
s1 ensures it inline (`--refresh-sector` forces); s2 rehydrates —
zero screener fetches on a fresh backbone; member_of edges; peer_of
still governs the peer TABLE (TMCV parses but doesn't join — by
design). Sector .ingest.md skill docs exist (consumed in the future
sector-reads work via packs.ingest_doc).

**R4 — Extraction 3.0**: focus-hash versioning (prompt changes
auto-re-read affected docs — the stale-extraction class is dead);
drops: FY-1 AR, results_pdf, shareholding hunt, valuepickr; every
passage SECTION-MAPPED (sections:[B..I]) + docs DATE-TAGGED
(published_date, strict ISO); **the AR conversation** — 5
owner-designed bundles (company_and_scale / business_model /
growth_outlook / management_commentary / statement_disclosures), each
one call sharing an identical [system, document] prefix (bundles 2–5
hit 286,272 cached tokens on SONA) with a FRESH 64K output budget and
a ≤40-word verbatim-pointer style; concalls read per-transcript + ONE
trails-pass over outputs (23 trails vs the old batch's 6).

**R5 — Synthesis slim + contract**: `_evidence(..., section=)`
two-pass fill (section-matched → unmapped filler; other-section-only
excluded) — D-family walls 40K→24K, F 16K/12K, H+C keep breadth BY
DESIGN; `_computed(..., slice_=)` statement slices (full blob only to
s4e); F's ten feeds consolidated (open guidance items dropped); C edge
cap 60; TMPV/post-restructuring non-comparability in G's spec;
`[event:<id>]` deterministic labels (+resolver+contract) killed the
invented events: shorthand; verifier _MAX_CALLS 12 (full coverage);
`validate_envelope` at compose time — **ENVELOPE_CONTRACT_VERSION
1.0.0** — violations logged non-fatally; per-run MANIFEST in the
sidecar (citations/verifier/schema/sections stats); content-hash reuse
(fetch_hash in doc metadata — rotated BSE Pname URLs no longer force
re-reads).

## 2b. Citation labels (2026-07-22, after the five rounds)

**Nodes no longer see or cite evidence UUIDs.** Every passage in a run's
pool gets a short run-scoped LABEL and models cite that:

```
AR.17        annual report          CC-May26.4   that quarter's call
IP.9         investor presentation  CR.2         rating rationale
S-MARUTI     screener page          47           news / sector / macro tail
```

`src/pipeline/citations.py` owns it: `build_label_map(pool)` stamps
`label` on every row and returns (label → uuid, ordered doc index);
`to_uuid()` resolves a citation. Labels are assigned ONCE, at the very
end of `extract_node` — **after** the fresh-layer rehydration, or those
~150 macro/industry passages would be unlabelled and uncitable.
Single-passage docs drop the index (`IP`, not `IP.1`); same-class
collisions uniquify (`AR`, `AR2`). **Concall labels carry the quarter**
deliberately — two of M&M v4's verifier verdicts were period
mis-attributions between transcripts, so the model now re-reads the
quarter every time it reads the id.

The UUID **stays the storage and verification currency**:
`claims.evidence_ids` is uuid[] and the schema is frozen, so
`run_section` resolves labels → uuids before `save_claims`. Section K
became the citation LEGEND, and the run's map persists to
`report_versions.sections_json["citation_map"]` (jsonb, no DDL) so
stored reports stay re-resolvable and the UI gets footnote markers for
free. UUID citation paths are KEPT everywhere as the fallback and are
commented as such — delete them only after a few more clean runs.

Two traps, both closed: `_strip_inline_evidence` matches labels
**exactly against the run's map** (not by shape), so a bare `[47]` is
stripped only when 47 is really a label while `[sec:]/[calc:]/[edge:]`
survive; and the composer's label lookup runs BEFORE the `sec:`/bare
block-id paths, because `AR.17` shares their `<X>.<y>` shape. s9 dropped
its per-batch `[E<n>]` indirection entirely (one less mapping, and
verdict notes now read "CC-Aug25.3 is from the Aug 2025 call").

**Validated on M&M v5** (reuse run, $0.54): raw citation uuids in report
prose **193 → 0**; **zero invented labels** across 499 citations;
citations 493/499 = 98.8%; verifier 27/187 = 14.4%; `schema_issues {}`;
`diff_golden` — *no regression flags*. All 6 unresolved citations are
pre-existing non-label classes (see §6).

**Cross-round fixes** (each found by a live run, fixed same day):
resolver accepts `evidence:<8-hex>` prefixes; `_strip_inline_evidence`
removes [uuid]/[evidence:x] markers from upstream summaries (section I
once copied H's ids wholesale); `_checks_json` strips evidence_id_raw
from D/F/H prompts (models re-cited a mangled uuid two runs straight).

## 3. How to run and verify

```powershell
# ALWAYS the venv python — bare `python` lacks langgraph:
.venv\Scripts\python.exe main.py --dry-run --ticker SONACOMS   # after EVERY change, seconds
.venv\Scripts\python.exe -u main.py --ticker SONACOMS --model M3   # live ~$0.5-0.7, ~10-15 min
.venv\Scripts\python.exe -u main.py --ticker "M&M" --model M3      # quote the & in PowerShell
.venv\Scripts\python.exe scripts\diff_golden.py SONACOMS           # ALWAYS after changes
.venv\Scripts\python.exe scripts\diff_golden.py --freeze <TICKER>  # owner green-flag only
# --reingest ignores stored extractions; --refresh-sector forces the backbone
```

**Log lines that ARE the gates** (additions to HANDOFF3 §3): the
per-node telemetry table + sidecar path at end of run; `[sector]
backbone fresh — N members rehydrated`; `[s2] AR bundle '<name>': …
(cached N tok)`; `[s2] cross-quarter trails-pass: N trails`; `[s2]
extraction focus changed … re-reading` (expected exactly once after
any focus edit); `[s2] citation labels: N passages across M documents`;
`[synth_X] N claim citation(s) did not resolve to a pooled passage`
(**expect 0** — a non-zero count is a model inventing labels, the one
risk the label scheme carries); `[s8] envelope contract violation(s)`
(expect NONE); `schema_issues: {}` in the sidecar manifest; composer
citations ≥98%.
Tee-Object writes UTF-16 logs — read them with
`iconv -f UTF-16LE -t UTF-8` or PowerShell-native tools.

## 4. Cost model (measured, 2026-07-22)

Reuse run: **$0.53 / ~10.5 min** (era baseline was $1.0–1.4 / 25 min).
Output tokens = ~69% of cost (M3: in $0.55/M, out $2.19/M — 1 out ≈ 4
in). Verifier is now the TOP cost node (~$0.09) — correct end-state:
the trust feature is the biggest line item. Fresh-extraction runs
(new company / focus change) ~$1.4–2.0; our telemetry prices cached
input at FULL rate, so real Fireworks bills run lower (cached input is
discounted — confirm the exact rate on an invoice sometime).

## 5. Retry policy — complete exception list

HANDOFF3 §5 items 1–5 unchanged, PLUS:
6. **Transport read timeout** (>600s generation; slow-spiral shape,
   hit synth_I once): retry-once with a fresh sample in envelope
   calls, verifier batches, and AR bundles (a bundle failing twice is
   skipped ALONE — other bundles' yield still lands).
All retries are COUNTED in telemetry (spir/trunc columns) — if the
trend rises, investigate cause; never widen the exception list
without a documented incident.

## 6. Watch list (open items, in priority order)

1. **Rating-rationale discovery pulls the WRONG ENTITY.** M&M v5
   ingested 15 evidence rows as `rating_rationale`: `[CR.1–CR.4]` is a
   GoldenPi bond page for **Mahindra & Mahindra *Financial Services***
   (the listed NBFC subsidiary, a different company) and `[CR2.1–CR2.11]`
   is a CRISIL rationale dated **30-09-2019** — six years stale. This is
   an identity failure of exactly the class the deterministic spine
   guards against elsewhere (the wisesheets "M&M.NS → Macy's"
   precedent), and wrong-entity evidence is worse than missing
   evidence. Needs an identity + recency gate on the rating hunt in s1.
   (SONA has 1 rating doc / 4 rows; on the M&M v4 run both agency URLs
   404'd — so this class is thin AND unreliable.)
2. **AR extraction is the cost and data-loss centre** — see §7.2. On the
   v4 fresh run: $1.95 = 72% of run cost, 1054s = 39% of wall, 9 calls
   for 5 bundles, and `growth_outlook` skipped outright.
3. **Claims-per-section ceiling (8–20) is not holding** — v4: B 27,
   D1 25, E 25, C 24, H 22; v5: C 29, E 29, F 25. Not F-specific (F was
   18 on v4), so it is the contract line, not one spec. Re-assert it.
4. **Claims that cite `calc:`/`sec:` instead of evidence** are generated,
   silently dropped at persist and never verified: v4 67/238 = 28%
   (sections I and J at 100%), v5 47/222 = 21%. `validate_envelope`
   does NOT catch this — it checks `evidence_ids` is a *list*, not that
   entries resolve. Cheapest real fix on the board: a uuid/label check
   in the validator so it lands in `schema_issues`, plus a contract line
   for I/J (whose support genuinely is mostly calc/sec — the fix is
   "don't emit claims you can't back", not "find more claims").
5. **Citation volume jumped 397 → 499 (+26%) when labels landed** —
   short ids are cheap to write, so attribution got denser. Probably a
   quality gain; watch that it does not inflate verifier load.
6. Two unresolved-citation classes survive (~6/run, 1.2%), neither
   label-related: an invented `event:` shorthand (`27_mam_japan_…`,
   `26_sml_acquisition_complete`) and models using prose
   (`insufficiency: no promoter holding % disclosed…`) as a
   metric_card provenance. Floor-ish; revisit if the rate climbs.
7. synth_I output variance (15K–27K run to run) — prose-heavy spec.
8. metric_names canon is auto-flavored (order_book etc.) — fine (unit
   guard + descriptive-name fallback), relevant only at generalization.
9. Cosmetic: M&M's own screener label renders `S-M26M` (URL-encoded
   `M%26M` slug). One line in `citations._doc_mnemonic` whenever.

Added 2026-07-26 while planning the daily market-data job (see
`DAILY_MARKET_DATA_PLAN.md`); both are **deferred, not fixed** —
neither blocks that job, and each needs its own `diff_golden` cycle:

7. **`screener_parser.py:110` stamps `date.today()`** on the seven
   top-card values (`price`, `market_cap`, `pe`, `book_value`,
   `dividend_yield_pct`, `roce_pct`, `roe_pct`) — the date the scraper
   ran, not the market close it reflects. A weekend or pre-close run
   therefore records a phantom trading day. Harmless where it is used
   today (s3 reads this run's own candidates, so "current price" is
   simply the price as scraped) and **the daily job sidesteps it
   entirely** by dating rows from Yahoo's last bar. The residue is that
   the two writers can disagree by a day or two for the same close.
   Contained because every consumer that cares queries an explicit
   `period_end`. Real fix: have the research path resolve its close
   date from the price series it already fetches.
8. **Screener-derived ratios are stored as observations.** `pe`,
   `roce_pct`, `roe_pct` and `dividend_yield_pct` are computed BY
   screener, yet land in `metric_observations`, which sits awkwardly
   against invariant 3 (derived ≠ observed). Defensible — screener
   *prints* them, so they are observed-from-a-source rather than
   derived-by-us — but if the distinction is ever tightened, these are
   the rows to revisit. Note they are also the bulk of the day-row
   churn: 7 rows per research run versus the daily job's 2.

**Closed since the last handoff:** the mangled-uuid class (§2b — models
cannot transpose hex they are never shown; v5 had zero label failures)
and the ≤40-word AR-pointer suspicion (M&M v4 came in at 15.1%
not-fully-supported, back inside the 6–16% band, so the pointer style
is exonerated — SONA's 3-run elevation was pool-specific. Do NOT ship
the queued counters: neighbouring excerpts, per-bundle length caps).

## 7. THE ROAD AHEAD (owner-sequenced, updated 2026-07-26)

**IN FLIGHT — daily market data.** The UI era started, and its first
backend dependency is a daily close + market cap for all 150 Midcap
constituents, independent of the research swarm (today only ~15
companies have any price at all, at monthly granularity, and only when
a run happens to touch their sector). Plan, probes, landmine ledger
and implementation detail: **`DAILY_MARKET_DATA_PLAN.md`**. It is
additive — no report changes — except its D0.1 prerequisite, which
fixes the 1,000-row truncation bug and therefore lands alone with its
own `diff_golden`. Frontend's asks live in `ui_bridge/PIPELINE_TASKS.md`.

### The standing sequence

**7.1 M&M final validation — DONE (golden v4, then v5).** Result: 6 of
8 gates passed. PASSED: auto_oem backbone inline (TMCV/HYUNDAI Yahoo
identity-refusals as expected — refused rather than mis-resolved);
PE percentile computed from 10y closes ÷ EPS (70th pct, median 21.5×,
was an insufficiency); TMPV non-comparability in G (narrative + gap +
dedicated FLAG + insufficiency); envelope contract clean; citations
99.0%; verifier 15.1% (settled the pointer-style question — §6).
FAILED, both pre-existing and both now tracked in §6: the AR bundle
skip (4/5 — `growth_outlook` truncated → reprompted → unparseable →
skipped) and the claims ceiling. Caveat for the percentile: the 10y
range high of 279.4× is a near-zero-EPS-year artifact, so the *band*
is meaningless as a bound even though the median is sane.

**7.2 AR optimisation — NEXT (owner: "we will look to optimise more").**
The numbers to beat, from the v4 fresh run: 9 calls for 5 bundles
(3 truncations + 2 unparseable), $1.95 = 72% of run cost, 1054s = 39%
of wall, one bundle lost. It is NOT a size problem — SONA's AR prefix
is *larger* (286K vs 268K cached tokens) and ran 5/5 clean in 5 calls
at $0.88/227s. It is conglomerate breadth: each bundle has more to say
and blows the 64K output budget. Note the retry ladder's real cost —
the "be MUCH terser" reprompt only fires AFTER a wasted 64K generation,
and when it succeeds it roughly halves yield (54 AR passages vs SONA's
136; 111 candidates vs 307). Likely direction: start the wide bundles
terse instead of paying a truncation first, or split `growth_outlook`.

**7.3 UI + MAPPING ERA** (after 7.2): renderer against
`report_versions.sections_json` — envelope contract v1.0.0, the run
manifest, and now `citation_map` are the API; NEVER re-parse markdown.
The label scheme was built with this in mind: `citation_map.labels`
gives footnote markers and `citation_map.documents` gives the legend,
so the UI never touches a uuid. The mapping exercise IS the next
optimization audit: the report is still too big, and pruning (needed /
not needed / missing / waste) is decided by mapping blocks to UI
surfaces, not by another blind cost pass.

**7.4 Then**: update GENERALIZATION_PLAN.md to the post-UI pipeline and
execute it (Midcap 150 → Nifty 500). Universe registry already built:
data/universe/nifty_midcap150.json (36/150 are financials — the hard
cohort; 10 auto constituents are already pack-covered).

## 8. Bootstrap for the new session

Suggested first message:
> Read HANDOFF4.md fully, then NEXT_STEPS.md ("THE ROAD AHEAD" + the
> five Round logs + the citation-labels log), then skim
> GENERALIZATION_PLAN.md. Confirm your understanding of the current
> state and the watch list. Goldens: SONA v22, M&M v5 (both frozen).
> The next action is the AR optimisation (§7.2), then the UI + mapping
> era.

Note for that session: SONA's golden v22 predates citation labels. It
is still a valid baseline (the fingerprint is block/claim counts, not
citation text), but the first SONA run after any further change will
show its citations relabelled — that is expected, not drift.

The project memory (auto-loaded) carries the compressed state; where
memory and this file disagree, this file wins (newer and complete).
