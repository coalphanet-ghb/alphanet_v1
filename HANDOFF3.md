# HANDOFF 3 — AlphaNet session handoff (2026-07-18)

> For the next assistant session. The previous session (2026-07-17/18)
> completed Phases 3–6 of the six-phase improvement plan — Extraction 2.0,
> the financial forensic architecture, 1M-context exploitation, and the
> golden set — plus an owner-driven valuation redesign and two hardening
> batches. **The plan that began 2026-07-15 is CLOSED.** The pipeline now
> produces two frozen golden reports (SONA + M&M) at ~99.5% citation
> resolution, ~$1–2/run, fully generalized (add a company = ticker + slug
> + pack). The next era is optimization, issue-ironing, and the old
> HANDOFF's Sprint-6 territory (update workflow, more sectors, UI).
> This doc is the single entry point; where it disagrees with the memory
> file or older docs, THIS FILE WINS.

---

## 1. Reading order (30 minutes to full context)

1. **This file** — end to end.
2. **REPORT_BLUEPRINT.md** (FROZEN v0.3) — the 11-section skeleton A–K.
   Never change the skeleton; sector packs carry variation.
3. **nodes/README.md** — the envelope contract (block types, ALL citation
   forms incl. edge:/trail:, no-arithmetic rules, statement-node extras).
   Then skim `nodes/s4a_pl/spec.md` + `nodes/s4_financials/spec.md` (the
   forensic architecture) and `nodes/s7_valuation/spec.md` (the year-in-
   the-multiple block). Specs ARE the prompts (`src/specs.py`).
4. **Code walk** (~2,000 lines that matter): `main.py` →
   `src/pipeline/graph.py` (Phase-4 order) → `s2_extract` (local-fetch
   inline extraction, concall batching, price history) → `s3_compute`
   (validation gate + unit guard + PE path/percentile) → `s4_synth`
   (context assemblers, retry logic, labeled edges/trails, peer packs)
   → `s9_verifier` → `s8_composer` (D sub-sections, resolver). Plus
   `src/llm.py` (providers, usage telemetry, truncation handling),
   `src/ingestion/fetcher.py` (fetch + validators),
   `src/ingestion/screener_parser.py`, `scripts/diff_golden.py`.
5. **NEXT_STEPS.md** — current state, watch-lines, the prioritized
   backlog. Its top "ARCHITECTURE PLAN" section (2026-07-19) is the
   LIVE plan and supersedes §8 below.
5b. **DB_SCHEMA.md** — the frozen Supabase schema + persistence
   invariants (citation integrity, append-only facts, where the
   architecture plan touches storage). Read before touching db.py or
   anything that persists.
6. **HANDOFF2.md / HANDOFF.md** — historical context only. Their plans
   are fully executed; their principles (§6 best practices in HANDOFF2,
   anti-hallucination in HANDOFF) still hold and are extended by §7 below.
7. Golden reports: `data/reports/SONACOMS_20260718_095433.md` (v18) and
   `data/reports/M_M_20260718_151030.md` (v3) — read one end-to-end.

## 2. System snapshot (what exists and works)

**Graph** (LangGraph, list-form joins — individual edges are TRIGGERS
and once double-ran the whole tail):
```
s0_resolve → s1_discover → s2_extract → s3_compute
  → [B, E, D1(s4a_pl), D2(s4b_bs), D3(s4c_cf)]   parallel wave
  → s4d_followup (claim_checks pooling + evidence-id validation + ≤1 call)
  → synth_D (s4e: integrated D + claims-vs-numbers scoreboard)
  → F → G → H → C → I → J → s9_verifier → s8_composer
```

**Data acquisition (s2)** — all deterministic-first:
- Screener pages: parsed zero-LLM (company + up to 8 peers), fresh every
  run; supplies doc links (concall transcripts + PPT decks + ARs).
- Documents: local fetch (requests + pypdf/trafilatura, 1.2M-char cap) →
  text INLINE to M3 → per-URL fallback Gemini url_context → skip+log.
- All concalls in ONE batched call → guidance_evolution[] +
  recurring_themes[] (persisted as `concall_cross_quarter`, rehydrated
  on reuse).
- Yahoo chart API: 13 monthly closes, identity-validated via longName.
- valuation_history: ticker-template URLs (wisesheets) with shape AND
  identity validation in s1 before the read is emitted; ddgs fallback.
- Reuse: ingested URLs free; quality gates re-read thin extractions.

**Compute (s3)**: ~4,800 observations/run; unit-class guard on canon
KPIs (drops impossible units loudly); TTM, statement tables, forensic
battery, Piotroski, guidance scorecard, peer table (9 rows for SONA),
P/B, 1y PE path (price÷TTM-EPS monthly), 9y PE percentile, re-rating.

**Synthesis**: spec-driven prompts + pack overlays; 40K-char evidence
budgets (D-family/F/H/C), C full-feed, J full envelopes; peer evidence
packs in G; claims density floor 8–20; claims pool-gate (ids not in the
run's pool stripped; id-less claims unpersisted); labeled citable
context: [sec:X.id], [edge:from__rel__to], [trail:metric_slug].

**Verification**: s9 batches (16K budget, per-batch spiral retry) over
~200 claims incl. scoreboard attributions; composer renders failures
per section; citation resolver handles uuid/calc(+valuation sub-ids)/
sec/edge/trail/evidence:/8-hex-prefix, brackets stripped.

**Models**: `--model M3` = MiniMax-M3 via Fireworks (PAID) for
everything except the url_context fallback reads (Gemini
3.1-flash-lite). Cost telemetry live: runs.tokens_input/output/cost_usd.
Typical: normal run 24–29 calls $0.8–1.4; reingest 37+ calls ~$1.9.

**Quality (golden runs)**: citations 99.2–99.6% resolved; verifier
not-fully-supported 6–16% (sampling-noisy); claim checks 17–30/run with
non-corroborated verdicts feeding F (credibility) + H (risk register).

**Companies**: SONA (auto_ancillaries, golden v18) + M&M (auto_oem,
golden v3). Peer sets: SONA 8 slugs; M&M = TMPV/TMCV/MARUTI/ESCORTS/
HYUNDAI (Tata Motors demerged 2025 — old TATAMOTORS slug 404s; seed
entity renamed "Tata Motors Passenger Vehicles" ticker TMPV; TMCV
entity exists but has NO peer_of edge yet).

## 3. How to run and verify (the working discipline)

```bash
python main.py --dry-run --ticker SONACOMS      # graph sanity, SECONDS — after EVERY change
python scripts/test_screener_parser.py --live   # after touching parser/metric_names
python main.py --ticker SONACOMS --model M3     # live (~25 min, ~$1)
python main.py --ticker SONACOMS --model M3 --reingest  # re-read ALL docs (~$2; after extraction-prompt changes)
python scripts/diff_golden.py SONACOMS          # vs golden — ALWAYS after prompt/pack/model changes
python scripts/diff_golden.py --freeze TICKER   # promote a trusted report to golden
```

**Log lines that ARE the gates:**
- `[s3] N candidate(s) dropped by unit guard` — read the name=value list
  for NEW mislabel forms (prompts reduce, guard catches; steady state).
- `[s2] price history (no LLM): 13 monthly closes (<LongName>)` — PE
  path feed + identity check.
- `[s2] cross-quarter: N trails` / `[s1] N concall transcripts via
  screener doc links` — concall machinery.
- `[synth_X] ... stripped; N id-less — not persisted` — claims pool-gate
  (normal: a few; D1 occasionally spikes to 20–40, absorbed safely).
- `reasoning-spiral truncation — retrying once` — see §5; retry has
  converged 10+/10+ so far; a retry that ALSO fails aborts the run.
- Composer `N/M citations resolved` (expect ≥98%) + verifier `N not
  fully supported` + `~$X paid` cost line.
- `diff_golden` output: any FLAG line is a stop-and-look.

**Verification ethos that paid off all session**: reproduce the exact
failing artifact, fix, assert on it (unit tests inline or scripts/);
then a live run — every phase's gates were log lines, and every abort
converted into a permanent fix. Wrong numbers are worse than missing
ones: when in doubt, drop to insufficiency, never guess.

## 4. Environment quirks (will bite you if unknown)

- Fireworks/NVIDIA TLS-reset Python on this network → llm.py auto-falls
  back to Git-for-Windows curl. Screener/BSE/Yahoo reachable from the
  assistant sandbox (verified repeatedly).
- Windows cp1252: main.py reconfigures stdout/stderr errors="replace" —
  but AD-HOC scripts must do it themselves (`sys.stdout.reconfigure`)
  or a ₹ in output crashes them.
- Background runs: launch with `python -u` or output buffers until exit
  (a 30-min run once looked dead while healthy).
- ddgs is NONDETERMINISTIC — never let a gate depend on a search hit;
  deterministic URL templates + validation, ddgs as fallback only.
- wisesheets connection-resets under repeated probing; screener's chart
  API is login-gated (404); smart-investing/trendlyne render PE history
  in JS charts (2 values in HTML text) — SOURCE MATERIAL CAN BE THE BUG.
- Supabase schema FROZEN (9 tables); citation integrity is app-code.
  Keep billing DISABLED on the Gemini GCP project.

## 5. The retry policy (complete list of documented exceptions)

Baseline: NO fallback, NO auto-retry — first error aborts; reruns are
cheap. Exceptions (all narrow, all stochastic-only):
1. HTTP 429: ≤4 attempts, Retry-After (deterministic rate limiting).
2. Extraction (s2): ONE reprompt on malformed JSON **or truncation**
   (big-AR output genuinely overflows 64K; the reprompt says "be terse").
   Second failure skips the doc (M&M FY-1 conglomerate AR does this —
   backlog #1).
3. Envelope calls (run_section): ONE fresh-sample retry on TRUNCATED
   ("reasoning spiral") or "unparseable envelope".
4. Verifier: per-batch retry-once on TRUNCATED; failed batch skipped,
   loop continues (break-on-first-failure once shipped a 0-verified
   report).
5. CallDeadlineError (Gemini): that URL is skipped, never retried.
6. Transport read timeout (added 2026-07-22): a generation exceeding
   the 600s HTTP ceiling (slow-spiral shape — synth_I hit it once) is
   retried ONCE with a fresh sample in envelope calls, verifier
   batches, and AR bundles (bundle skipped alone if it repeats).

**The M3 reasoning spiral**: the model stochastically burns the ENTIRE
max_tokens budget inside reasoning_content (observed up to 230K chars)
and emits no content. Node-agnostic (hit B/C/D2/E/F/H across runs; same
nodes fine other runs), budget-independent (32K→64K all exhausted),
frequency ~1–2/run at current context sizes, fresh-sample retry has
ALWAYS converged. If a retry ever spirals too: trim that node's context
or add a reasoning-brevity instruction — do NOT raise budgets (64K is
the Fireworks ceiling).

## 6. What's working vs known limitations

**Validated working**: everything in §2; both golden reports read like
institutional research (owner's Phase-3 §12 skeptical-read standard);
cross-examination catches real management contradictions (SONA: ">45%
Low Carbon" claim vs computed 19%); the year-in-the-multiple block
attributes re-rating phases to evidenced events (SONA: +59% price =
mostly multiple expansion, PE 47→68, EPS +10%).

**Known limitations (all honest-degradation, none ship wrong numbers)**:
- M&M FY-1 AR skipped (output overflow both attempts) → forensic trends
  thinner for M&M.
- M&M own-history percentile = insufficiency (no text-borne PE-history
  source validated for it).
- TMPV's post-demerger peer-table numbers are weird-but-real (PE 1.4×,
  ROE 76%) — G should treat as non-comparable; consider a spec note.
- Semantic mislabels persist at low rate under the guard (counts/shares/
  amounts confused); unit guard is the load-bearing defense.
- Verifier not-fully-supported is sampling-noisy (6–16% run to run) —
  treat the trend, not single runs.

## 7. Best practices learned (extends HANDOFF2 §6 — all still valid)

1. **Identity-validate every templated source.** wisesheets resolved
   ticker "M&M.NS" to Macy's Inc — a wrong-company page passes any
   shape-only check. Every template fetch must prove the page/response
   mentions THIS company (fetcher.looks_like_valuation_history,
   fetch_price_history longName check). This is now an invariant.
2. **Poison-label rejection**: period labels containing average/median/
   ranges must NEVER parse as a single period — a naive regex fix would
   have filed a 5-year average as FY26's value.
3. **Stacked defects hide behind each other.** The percentile needed SIX
   fixes in six layers (query alias → period parsing → entity mapping →
   stale extraction → search nondeterminism → JS-chart source). Verify
   layer by layer with the exact artifact; expect the next layer.
4. **Deterministic citable labels** are the cure for invented citation
   shorthand: render context items as [edge:x]/[trail:x]/[sec:X.y], have
   the composer RECOMPUTE the id set (content-derived, no counters), and
   strip brackets when resolving. Applied three times; works every time.
5. **Changing an extraction focus silently strands stale stored
   extractions** (reuse serves the old ones). Until focus-versioning
   (backlog #2) exists: --reingest, or surgically invalidate the doc row
   (only if nothing references its evidence).
6. **Listings change under you**: Tata Motors' demerger killed its slug
   mid-project. Preflight caught it as a 404; the peer went silently
   null. When a peer row is all-null, check the slug first.
7. **Gates are log lines; the run log is the dashboard.** Every real bug
   this session was visible in the log before the report was opened.
8. **LangGraph fan-in**: `add_edge(["a","b"],"c")` is a join;
   individual edges are triggers (doubled-execution trap, caught in
   dry-run — doubled `[synth_X]` lines CAN be real double execution).
9. **Cost discipline**: ~$1/run means verification-by-running is cheap;
   six runs to close a gate was the right trade because every failure
   became a permanent fix. Telemetry (runs table) now proves it.
10. **The unit-class guard + pool-gate + identity checks are the spine.**
    Prompts drift, models mangle, sources lie; the deterministic layers
    are what keep wrong numbers out of reports. Extend them before
    trusting any new data path.

## 8. THE NEXT ERA — backlog in implementable detail

(Prioritized; NEXT_STEPS.md mirrors this.)

1. **Large-AR split extraction** (unblocks M&M forensic trends): when a
   doc's text exceeds ~600K chars, split the extraction into two calls —
   (a) financial statements + notes tables, (b) MD&A/policy/risk prose —
   with per-part focus subsets; merge candidate/passage lists. Gate:
   M&M FY-1 AR ingested, zero skips.
2. **Extraction-focus versioning**: hash the doc-class _FOCUS text into
   extract:{doc_id} entries; s2 reuse compares hashes and re-reads on
   mismatch. Kills the stale-extraction class. Gate: change a focus,
   watch only affected docs re-read.
3. **M&M valuation-history source** (percentile gap): probe more
   text-borne sources; else compute annual PE from Yahoo yearly closes ÷
   annual EPS (both already available!) — likely the CLEANEST fix and
   removes the wisesheets dependency entirely. Consider doing this
   instead of #3-as-probing and retiring valuation_history reads.
4. **TMPV non-comparability note in G's spec** + TMCV peer edge if CV
   comparison wanted.
5. **Verifier trend tracking**: persist per-run verifier stats
   (runs table or golden fingerprints) so the 6–16% noise becomes a
   monitorable trend.
6. **Sprint-6 era** (old HANDOFF §9): update workflow — rule-based
   triggers first (new filing → regen affected sections; the
   knowledge_entries versioning + freshness stamps already support it);
   scheduler later; NBFC + more sector packs (pack registry is proven);
   UI/blocks rendering (report_versions.sections_json already stores
   typed blocks — UI is a renderer, last).

## 9. Bootstrap for the new session

Suggested first message:
> Read HANDOFF3.md fully, then NEXT_STEPS.md, then skim nodes/README.md
> and src/pipeline/. Confirm your understanding of the current state and
> the backlog, then start with backlog item #1 (large-AR split
> extraction), verifying per HANDOFF3 §3 — dry-run after every change,
> live run + diff_golden before calling anything done.

The project memory (auto-loaded) carries the compressed state; where
memory and this file disagree, this file wins (newer and complete).
