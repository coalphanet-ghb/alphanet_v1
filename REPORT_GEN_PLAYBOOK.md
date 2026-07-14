# AlphaNet — First-Time Report Generation Playbook (v0.1 draft)

> The operational distillation of DATA_SOURCES.md for ONE job: generating
> a company's report for the first time. Organized by the ordered workflow
> graph. Query banks are defined at UNIVERSAL and SECTOR level only —
> stock-level specificity comes from `{company}`/`{ticker}` slots, never
> hand-written per stock.
>
> Companion docs: REPORT_BLUEPRINT.md (frozen v0.3 — what we produce),
> DATA_SOURCES.md (the full source universe this is distilled from).

---

## 0. Budget & mechanics (read this first)

**API budget per first-time report (lite model, 15 RPM / 500 RPD):**

| Phase | LLM calls | Notes |
|---|---|---|
| Discovery (ddgs) | 0 | free, ~25-30 searches, 1s apart |
| Read/extract (url_context) | ~19 company + ~7 shared | shared = macro+industry, amortized across every stock in the sector |
| Compute (Python) | 0 | ratios, CAGRs, percentiles, forensic checks, peer table |
| Synthesis | ~10 | one per narrative block + takeaways |
| **Total** | **~36 fresh / ~29 amortized** | ≈ 12–18 min wall-clock at lite RPM; well inside 500 RPD; **do not run on `high` (20 RPD) — a first-time gen doesn't fit** |

**url_context mechanics that shape the design:**
- One call can carry **up to 20 URLs** — but every URL's full content lands
  in the prompt, so batching is limited by tokens/deadline, not by the 20-cap.
- **Batch rule: 2–3 small same-block URLs per call** (news, rationales,
  sector pages), with a required output format `=== SOURCE: <url> ===` per
  section so evidence attribution survives parsing. If the delimiter parse
  fails → automatic fallback to one-URL-per-call for that batch.
- **Solo rule: every heavy PDF gets its own call** (annual report,
  concall transcripts, results PDFs, investor presentation). This is also
  our deadline-expiry containment: one slow doc only kills its own call
  (we already skip-and-flag those).
- **Extraction calls do double duty:** each read call emits (a) verbatim
  passages → evidence rows, (b) any structured numbers found →
  metric_observation candidates, (c) **cross-block tags** (see §2) — all
  in one strict-JSON response. No second pass over the same document.

**ddgs settings by query intent:**
- Document-hunt queries (concall/AR/presentation/rationale): fetch
  **5 results** — the right link is often 2nd/3rd behind aggregator spam.
- Data/news queries: 3 results (current default).
- **Domain priority reranking** (deterministic, before URL selection):
  - Tier-1 domains first: `bseindia.com`, company's own domain,
    `screener.in`, `researchbytes.com`, `icra.in`, `crisilratings.com`,
    `careratings.com`, `indiaratings.co.in`, association domains
    (`siam.in`, `fada.in`, `acma.in`, ...)
  - Deprioritize: generic aggregators, SEO farms
  - Skip always: `nseindia.com` (bot-hostile), known-paywalled domains
    (body unreadable), social media
- **URL pre-flight (deterministic, free):** a `requests.head/get` check
  drops obvious corpses (404s, redirect loops, login walls) before any
  Gemini call. Advisory only — Gemini's fetcher differs — but catches the
  cheap failures. Maintain a small learned table: domains that repeatedly
  fail url_context get demoted; this table is updated from run logs
  (`nothing substantive extracted` warnings).

---

## 1. The ordered workflow graph

```
S0  RESOLVE      company → sector → pack, peer set from entity graph      (0 LLM)
S1  DISCOVER     all ddgs searches for every block, dedupe, rerank,
                 pre-flight → final URL plan within budget                (0 LLM)
S2  READ         url_context calls per §3 → evidence + metric candidates
                 + cross-block tags                                       (~19+7)
S3  COMPUTE      Python only: ratios, CAGRs, valuation percentiles,
                 forensic checks, peer table, guidance-vs-actual join     (0 LLM)
S4  SYNTH-1      B business · D interpretation · E supply chain ·
                 F management/guidance          — parallel, independent   (4)
S5  SYNTH-2      G peers (uses D + peer table)  → then
                 H risks (risk-tag pool + G's relative-weakness findings) (2)
S6  SYNTH-3      C industry & macro w/ sensitivities — LAST narrative:
                 needs the completed entity graph (E fed it) and the
                 macro entities' recent+medium-term views                 (1)
S7  SYNTH-4      I valuation (compute + G + C)                            (1)
S8  ASSEMBLE     J takeaways (1 call, reads all sections) ·
                 A snapshot (0 — pure compute) · K sources (0)            (1)
```

Key deviations from today's flat fan-out, per the frozen blueprint:
- **Reading and writing are decoupled.** B's sources are read in S2, but B
  is *written* in S4 — by then extraction from AR + presentation +
  concalls has landed, so the overview can use all of it.
- **Risks are accumulated, not searched-for-once.** Every S2 extraction
  call tags risk-relevant passages; H consolidates the pool + G's findings
  + one dedicated risk read of its own.
- **C is written last** among narratives (sensitivities need the full
  entity graph).

## 2. Cross-block tagging (the "keep gathering all along" mechanism)

Every S2 extraction call's JSON schema includes optional tag arrays. Tags
become pooled context, stored as accumulating knowledge entries — the
frozen DB schema supports this as `knowledge_entries` sections; no schema
change:

| Tag emitted during ANY read | Pooled into | Consumed by |
|---|---|---|
| `risk_signal` (passage + why) | section `risk_candidates` | H |
| `guidance_item` (metric, period, stated value/direction) | section `guidance_candidates` | F (track record), compute joins actuals |
| `supply_chain_edge` (entity A →relation→ entity B) | section `supply_edge_candidates` + `entity_relationships` | E, C sensitivities |
| `metric_candidate` (name, value, unit, period) | `metric_observations` (after unit/period validation) | D/G/I/A compute |
| `peer_mention` (company named as competitor) | `peer_candidates` | G (peer-set sanity check) |

## 3. Read plan per block (what to fetch, how many calls, priority)

Universal plan — sector overlays in §4. **Priority = what survives if the
URL budget must shrink** (P1 never cut, P3 first to go).

### Company docs (S2, ~19 calls)

| # | Read target | Calls | Batch? | Priority | Feeds |
|---|---|---|---|---|---|
| 1 | Concall transcripts, **last 4 quarters** | 4 | solo each | P1 (latest 2) / P2 (older 2) | F guidance track record, D color, H, tags |
| 2 | Annual report (latest FY) | 1 | solo (deadline risk accepted) | P1 | B, E, D2 forensic inputs, F governance, H risk factors |
| 3 | Investor presentation (latest) | 1 | solo | P1 | B, E, F capex/orders |
| 4 | Quarterly results PDF (latest) + FY results PDF | 2 | solo each | P1 | D, A |
| 5 | Credit rating rationale (latest, any agency) | 1 | solo | **P1 — do not cut** | D, E, F, H (best structured risk source) |
| 6 | screener.in company page | 1 | solo | P1 | metric_observations backbone (10y statements, ratios, price, shareholding) |
| 7 | Shareholding pattern / pledge page | 1 | batch w/ #8 | P2 | F governance, A |
| 8 | Recent company news (top 4-6 URLs) | 2 | 2-3/call | P2 | B, F, H |
| 9 | Dedicated risk read (litigation/regulatory/short-thesis news) | 1 | 2-3/call | P2 | H |
| 10 | Peer screener pages (3-5 peers) | 2 | 2-3/call | P2 (skip peers already in DB) | G peer table |
| 11 | Older annual report (FY-1) for forensic trend depth | 1 | solo | P3 | D2 |
| 12 | ValuePickr / bull-bear thread | 1 | solo | P3 (arguments to check, never cite) | H, I framing |

**Concall query handling (4 quarters):** templates are quarter-slotted and
the orchestrator expands them: for q in [Q_latest .. Q-3]:
`"{company} {q} {fy} earnings call transcript"` + fallbacks
`"{company} concall transcript {month year}"`, `"{company} transcript
researchbytes"`. The screener concall tab (one URL listing all transcript
PDFs) is fetched first — if readable, it supplies all four BSE PDF links
in one shot and the per-quarter searches are skipped.

### Shared layers (S2, ~7 calls, amortized across all stocks / all runs)

| Read target | Calls | Refresh policy |
|---|---|---|
| Macro entities (repo, GDP, CPI, crude, INR, steel/relevant commodities, Fed, trade) — recent + medium-term view pairs from DATA_SOURCES §4 | ~4 (batched 3-4 URLs/call, grouped by theme) | reuse if < 7 days old; refresh only stale entities |
| Sector data pages (association prints + outlook, from sector bank) | ~3 (batched 2-3/call) | reuse if < 30 days old or since last data release |

## 4. Query banks by workflow stage — universal + sector overlay

Format: `query → target block(s) [results-count]`. Universal bank ships
with slots; each sector adds its overlay. Two pilot overlays written out;
other sectors follow DATA_SOURCES §6 banks reshaped into this structure
when onboarded.

### S1-U · Universal company bank (every stock, every sector)

**Doc-hunt (5 results each):**
- `{company} screener.in` → A,D,G,I
- `{company} annual report {fy} pdf` → B,D,E,F,H
- `{company} investor presentation {quarter} pdf` → B,E,F
- `{company} {q} {fy} earnings call transcript` (×4 quarters, with fallbacks per §3) → F,D,H
- `{company} quarterly results {quarter} press release pdf` → D,A
- `{company} credit rating rationale icra OR crisil OR care` → D,E,F,H
- `{company} shareholding pattern promoter pledge` → F,A

**Data/news (3 results each):**
- `{company} latest news` → B,F,H
- `{company} order win capex expansion announcement` → F
- `{company} litigation OR penalty OR regulatory action` → H
- `{company} valuepickr` → H,I
- `{company} historical PE valuation` → I

### S1-M · Universal macro bank (shared; pairs = recent + outlook)

As DATA_SOURCES §4 (13 pairs), grouped for batched reads into 4 themes:
rates & growth (repo, Fed, GDP, CPI) · commodities ({sector-relevant
commodity set} + crude + gold) · external (INR, trade policy) · fiscal &
rural (budget/GST, monsoon). **The commodity sub-set is selected by the
sector pack** — auto pulls steel/alu/rare-earths; FMCG pulls palm
oil/crude derivatives; cables pulls copper.

### S1-S · Sector overlay: **auto OEM** (pilot — M&M)

- `siam monthly auto sales data latest press release` → C,G [3]
- `fada vehicle retail data latest month press release` → C,G [3]
- `india {segment} sales market share latest month` (segment slots from
  company profile: PV / tractor / CV / 2W) → C,G [3]
- `india ev sales penetration vahan latest month` → C [3]
- `auto sector outlook {fy} icra OR crisil` → C,H [5]
- `pm e-drive ev incentive scheme update` → C [3]
- `auto loan rates india trend` → C [3]
- `india car discounts inventory dealer latest` → C,H [3]
- Sensitivity commodities for macro bank: steel, aluminium, rare earths,
  crude (fuel prices→demand), copper (EV)

### S1-S · Sector overlay: **auto ancillaries** (pilot — Sona)

- `acma auto component industry performance latest` → C,G [3]
- `auto component exports india latest data` → C [3]
- `india auto ancillary outlook {fy} icra OR crisil` → C,H [5]
- `oem ev platform sourcing india suppliers` → C,F [3]
- `rare earth magnet supply china export india auto` → C,E,H [3]
- `auto components pli beneficiaries update` → C [3]
- OEM demand prints reused from auto-OEM overlay (SIAM/FADA) — same
  sector-layer knowledge entry serves both packs
- Sensitivity commodities: steel, specialty alloys, rare earths, copper, INR

### Remaining named sectors

The DATA_SOURCES §6 banks (auto ER&D, EV, power EPC, transformers,
cables, FMCG, FMEG, durables, EMS, pharma, specialty chem) drop into the
same overlay shape: each query gets `→ blocks [results]` annotations at
pack-authoring time (when that sector's first company onboards).

## 5. Synthesis call plan (S4–S8, ~10 calls)

| Call | Writes | Context assembled from |
|---|---|---|
| B | Business Overview | AR/IP/screener evidence + revenue-mix metrics |
| D | Financial narrative (D1/D2/D3 verdicts) | **computed table only** + flagged forensic anomalies + concall color |
| E | Supply Chain | AR/rationale evidence + supply_edge pool |
| F | Mgmt/Governance/Guidance | 4-quarter concall evidence + guidance_candidates joined vs actuals (computed) + governance flags |
| G | Peer comparison | computed peer table + peer evidence |
| H | Risks | risk_candidates pool + G findings + dedicated risk evidence + rating rationale |
| C | Industry & Macro + sensitivities | sector layer + macro pairs + entity graph edges (post-E) |
| I | Valuation context | computed multiples/percentiles + G + C |
| J | Takeaways | all section outputs (compressed) |
| — | A, K | zero LLM — compute + assembly |

## 6. Failure fallbacks (first-gen specific)

- **Annual report deadline-expires** → proceed; B/E lean on investor
  presentation + rating rationale; report carries an explicit gap flag
  ("AR unreadable — sections B/E on secondary sources").
- **screener.in unreadable** (the §7 spike in DATA_SOURCES decides this
  once) → metric backbone falls back to results PDFs (#4) + rating
  rationale numbers; A/D/I still compute, with shorter history.
- **A concall quarter not found** → guidance track record renders with
  gaps marked "transcript unavailable", never silently shortened.
- **Under RPD pressure** (other runs same day): drop P3, then P2 reads in
  reverse priority; never drop P1; never drop the compute stage (free).

## Changelog
- v0.1 (2026-07-14): initial draft distilled from DATA_SOURCES.md v0.1.
