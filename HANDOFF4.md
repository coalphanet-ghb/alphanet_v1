# HANDOFF 4 — AlphaNet session handoff (2026-07-22)

> For the next assistant session. The previous sessions (2026-07-21/22)
> executed the FIVE-ROUND de-clutter plan end to end — telemetry,
> no-regret cuts, the sector pipeline, Extraction 3.0, synthesis
> slimming and the frozen envelope contract. **The plan is
> code-complete and SONA-validated: golden v22 (owner-frozen) at
> $0.53/run, 10.5 min, 99.8% citations, zero spirals.** Where this doc
> disagrees with HANDOFF3 or the memory file, THIS FILE WINS.

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
any focus edit); `[s8] envelope contract violation(s)` (expect NONE);
`schema_issues: {}` in the sidecar manifest; composer citations ≥98%.
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

1. **Verifier not-fully-supported elevated 3 runs straight** (21%,
   21%, 22.5% vs the historical 6–16%; partials dominate). Suspect:
   the ≤40-word AR pointer style gives the verifier thinner excerpts.
   **The M&M run is the decider** — fresh evidence pool, same style.
   Counters if confirmed: allow 2 neighboring excerpts per claim, or
   per-bundle length caps (disclosures 40 / commentary 70).
2. **E and F exceeded the 8–20 claims ceiling** (31/34) — inflates
   verifier load; if M&M repeats it, re-assert the ceiling in the
   contract (one line).
3. Mangled-uuid citations: ~1/run survives (transposed hex; block
   citations have no pool-gate). Floor reached; revisit only if >2.
4. synth_I output variance (15K–27K run to run) — prose-heavy spec.
5. metric_names canon is auto-flavored (order_book etc.) — fine (unit
   guard + descriptive-name fallback), relevant only at generalization.

## 7. THE ROAD AHEAD (owner-sequenced 2026-07-22)

1. **M&M final validation** — owner runs it, assistant analyzes the
   log. Gates: auto_oem backbone builds inline (TMPV/TMCV Yahoo
   identity-refusals are EXPECTED degradations); AR through 5 bundles
   ZERO skips (this was THE unsolvable — M&M's FY-1 conglomerate AR
   used to overflow 64K twice and get skipped); percentile computed
   from 10y closes ÷ EPS; TMPV declared non-comparable in G; verifier
   partials compared to SONA's (watch #1). Old M&M golden v3 is
   PRE-R4 — not a fair diff; review on gates, then freeze the new M&M
   golden. Passing = current pipeline declared WORKING.
2. **UI + MAPPING ERA** (starts after M&M): renderer against
   report_versions.sections_json — envelope contract v1.0.0 + the run
   manifest are the API; NEVER re-parse markdown. The mapping exercise
   IS the next optimization audit: the report is still too big, and
   pruning (needed / not needed / missing / waste) is decided by
   mapping blocks to UI surfaces, not by another blind cost pass.
3. **Then**: update GENERALIZATION_PLAN.md to the post-UI pipeline and
   execute it (Midcap 150 → Nifty 500). Universe registry already
   built: data/universe/nifty_midcap150.json (36/150 are financials —
   the hard cohort; 10 auto constituents are already pack-covered).

## 8. Bootstrap for the new session

Suggested first message:
> Read HANDOFF4.md fully, then NEXT_STEPS.md ("THE ROAD AHEAD" + the
> five Round logs), then skim GENERALIZATION_PLAN.md. Confirm your
> understanding of the current state and the watch list. The next
> action is analyzing the M&M validation run log when I share it —
> against the gates in HANDOFF4 §7.1 — then freezing the M&M golden
> and opening the UI + mapping era.

The project memory (auto-loaded) carries the compressed state; where
memory and this file disagree, this file wins (newer and complete).
