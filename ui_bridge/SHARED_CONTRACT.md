# SHARED CONTRACT — pipeline ⇄ frontend

> **Both repos treat this file as authoritative for anything crossing
> the boundary.** It is a living document, not a dated handoff: when
> something here changes, it changes here first and both sides follow.
>
> Started 2026-07-26 from the pipeline repo. Point-in-time replies live
> in `PIPELINE_ANSWERS.md` / `PIPELINE_TASKS.md`; durable agreements
> live here.
>
> Rule of thumb: **if a change would break the other repo silently, it
> belongs in this file.** Silent drift across two repos is the failure
> mode this document exists to prevent.

---

## 1. The two data paths (do not blur them)

| Surface | Payload | Path | Who builds it |
|---|---|---|---|
| Company list (`/reports`) | ~25–30 KB, all 150 | Supabase → **snapshot** → Firestore → edge cache → browser | pipeline writes the snapshot |
| Report detail (`/reports/:ticker`) | ~430 KB, one company | Supabase → Cloudflare Pages Function (service-role key) → browser | pipeline builds **nothing**; frontend reads directly |

Consequences that are settled and should not be revisited casually:
reports are **never** mirrored into Firestore (430 KB × 150 breaks the
document limit and the free tier); the frontend **never** parses
`final_report_md` (`sections_json` is the API); RLS stays fully closed
and the service-role key is server-side only, never in a browser bundle
or a `VITE_`-prefixed var.

## 2. The join key

**`ticker` — the NSE symbol, uppercase, no suffix — is the sole
identifier across both repos, the registry and the snapshot.**

- `entityId` is **dropped** (owner decision 2026-07-26). It meant
  different things on each side (frontend slug `"sona-blw"` vs the
  pipeline's Supabase UUID), and a second identifier is drift waiting
  to happen. Need a pretty URL? Derive the slug from the ticker at
  render time.
- Supabase entity UUIDs are **internal** and never cross the boundary.
- On the pipeline side the ticker lives in `entities.metadata.ticker`,
  and `db.get_entity_by_ticker()` is the only sanctioned resolver.
  Resolving companies **by name is forbidden**: the NSE list says
  `'Bharat Forge Ltd.'` where the seeded entity says `'Bharat Forge'`
  (6 such mismatches), so name-keyed lookups create duplicate entities
  and split a company's data.

## 3. The registry — which 150 companies

**Canonical source: `data/universe/nifty_midcap150.json` in the
pipeline repo** (generated from the official NSE Indices CSV, which is
committed alongside it). The frontend regenerates its bundled registry
from this file; neither side hand-maintains a list.

Per-company fields the pipeline supplies:

| Field | Notes |
|---|---|
| `ticker` | the join key (§2) |
| `name` | NSE constituent name, e.g. `"Sona BLW Precision Forgings Ltd."` |
| `screener_slug` | pipeline-internal, ignore on the frontend |
| `nse_industry` | NSE's single classification field |
| `isin` | offered for any future data-vendor join |

**`sector` vs `industry`.** NSE publishes ONE classification
(`Industry`: "Financial Services", "Capital Goods", …). There is no
source here for GICS-style sectors ("Consumer Discretionary") and we
will not invent an unmaintained mapping. Agreement:
- `industry` = NSE Industry — available now
- `sector` = the pipeline's `pack_id` once sector packs exist, since
  that is the taxonomy actually driving the analysis
- until then **omit `sector`** rather than fabricate it

**`registryVersion`** — proposed `"2026.07"`. Bumped **only** on index
rebalance. Both repos bundle the same string; the snapshot's
`manifest.registryVersion` is how the frontend detects that its static
list has gone stale.

## 4. Market data

Written daily by `scripts/daily_market_data.py` into Supabase
`metric_observations`:

| metric_name | unit | source |
|---|---|---|
| `price` | `inr` | Yahoo chart API, last daily bar's close |
| `market_cap` | `inr_crore` | screener top card |

`period_type='day'`, with `period_start = period_end =` **the close
date taken from Yahoo's last bar** — never the date the job ran. That
is what makes weekends and holidays self-detecting.

⚠️ **Read by explicit `period_end`, never "the latest day row".** The
research pipeline *also* writes day-typed `price`/`market_cap` rows,
stamped with its own scrape date (`screener_parser`, tracked as
`HANDOFF4 §6.7`), so the two writers can disagree by a day or two for
the same close. `manifest.marketDataDate` is the date the market-data
job wrote, and every cap in a snapshot must come from that same date.

**Units are never converted anywhere but the display layer.** Market
cap crosses the boundary in ₹ crore; the frontend formats
`38400 → "₹ 3.84 L Cr"` and derives nothing.

## 5. The snapshot

**Path:** `index_snapshots/nifty_midcap_150`, single field `payload`
holding `JSON.stringify(<IndexSnapshot>)` — **one JSON string**, not
nested Firestore fields, so the edge function returns it verbatim.
Public read on `index_snapshots/*`; the content is public data.

```json
{ "manifest": { "registryVersion", "snapshotVersion",
                "marketDataDate", "verdictEpoch" },
  "dynamics": [ { "ticker", "marketCapCr", "status", "lastUpdatedISO",
                  "latestVersion", "quality", "hasOpenFlags",
                  "verdict" } ] }
```

Derivation, pipeline side:

| Field | Source |
|---|---|
| `marketCapCr` | `metric_observations.market_cap` at `marketDataDate`. **`null` if unknown — never `0`** (a zero renders as a real ₹0 cap) |
| `marketDataDate` | the `period_end` the market-data job wrote (§4) |
| `status` | no `report_versions` row → `not_initiated`; run in flight → `updating`; `generated_at` within 7 days → `updated`; older → `stale` |
| `lastUpdatedISO` | `report_versions.generated_at`, ISO 8601 **with offset** — the browser computes "3 hr ago" from it locally and never re-asks |
| `latestVersion` | `report_versions.version` |
| `quality` | `sections_json.quality` verbatim |
| `hasOpenFlags` | any block with `type:"flag"`, `status:"FLAG"` in the latest report |
| `verdict` | **hardcoded** `{"status":"coming_soon","version":0}` — see §7 |

**Rules:**
- Emit an entry for **every** registry ticker, including uncovered ones
  (today 149 of 150 are `not_initiated`).
- Write the **whole document** each time; no partial updates.
- **`snapshotVersion` increments only when content actually changed** —
  an unchanged rewrite busts every cached copy for nothing.
- Triggers: daily after the market-data job, and on report publish.

## 6. Naming and casing

**The pipeline is snake_case end to end** — `citation_map`, `quality`,
`sections_json`. Renaming DB-side keys would break stored reports,
which must stay reconstructible.

**The snapshot payload is camelCase** (`marketCapCr`, `lastUpdatedISO`)
because it is a frontend-facing document authored for that purpose.

So: **the boundary is the snapshot.** Anything read straight out of
Supabase (`sections_json` and everything under it) stays snake_case and
the frontend converts at its own edge. Known instance: the frontend doc
says `citationMap`; the stored key is `citation_map`.

## 7. Compliance constraints (not negotiable by either repo)

- **No Buy/Sell/Hold, ever** — and no verdict vocabulary
  (attractive/expensive/cheap). `FOUNDATIONS §1`, generation rule 5.
- **The "AI Verdict" column stays locked.** Owner decision 2026-07-26:
  both the column's *name* and its *content* are settled with the
  SEBI/fintech review, before any unlock. The pipeline emits only
  `{"status":"coming_soon","version":0}`. Do not unlock it with
  descriptive content ahead of that review — the risk is in the
  display string sitting beside a stock name, not in the data model.
- Source material is shown as **slices and links**, never wholesale
  reproductions (copyright, `FOUNDATIONS §6`).

## 8. Open coordination items

> Detail and rationale for everything owed by the **frontend** lives in
> `FRONTEND_TASKS.md`; for everything owed by the **pipeline**, in
> `HANDOFF5.md` §3a/§5b. This table is the index, not the spec — keep it
> to one line per item so the two never disagree.

| # | Item | Owed by |
|---|---|---|
| 1 | **Firestore: enabled (done — Native mode, `asia-south1`).** Remaining: a service account with Firestore write, granted cross-project, **with no JSON key** (Cloud Run supplies credentials via the metadata server); plus a public-read rule on `index_snapshots/*` **scoped by name** — the same database holds personal `portfolios/{uid}` data. Detail: `FRONTEND_TASKS.md` §2, `INFRASTRUCTURE.md` §1 | frontend / infra |
| 2 | ~~Confirm the GAE gateway hop can be dropped~~ — **CLOSED 2026-07-29, no action.** `functions/api/index-snapshot.ts` already reads Firestore directly over REST with the public web key and needs no gateway; its header specifies the exact doc path, field name and `stringValue` encoding the pipeline must write | — |
| 3 | **`registryVersion` is a mismatch, not an open question.** The canonical registry JSON carries no such field, the pipeline hardcodes `"2026.07"` and the frontend bundles `"2026.07-seed"` — which is precisely this field's stale signal, fired on day one. Add `registry_version` to `data/universe/nifty_midcap150.json`, read it in the builder, bundle the same string | both |
| 4 | Regenerate the bundled registry from the canonical 150 (frontend currently holds a 24-name seed) — **and drop `entityId` + the GICS `sector` in the same pass** (§2, §3). **Blocking:** `merge.ts` iterates the registry and ignores unmatched snapshot entries, so until this lands a correct 150-row snapshot renders 24 rows | frontend |
| 5 | Snapshot builder + Firestore transport | pipeline |
| 6 | Phased coverage plan — the swarm cannot yet run outside SONACOMS/M&M (`PIPELINE_ANSWERS.md` Q3); UI needs coverage tiers | both |
| 7 | `calc:` value persistence and pre-computed YoY deltas for the report UI | pipeline |
| 8 | Rating-rationale wrong-entity bug, before any credit surface is built | pipeline |

## Change log

- **2026-07-26** — created. Settled: ticker as sole join key
  (`entityId` dropped); `sector` cannot be GICS; snake_case/camelCase
  boundary; verdict column deferred to compliance review;
  `registryVersion` proposed as `"2026.07"`.
- **2026-07-30** — infrastructure verified against vendor docs and the
  live database; recorded in `INFRASTRUCTURE.md`. Settled: Cloud Run in
  `asia-south1` (matching Firestore, whose location is permanent);
  Firestore and Cloud Run live in **separate GCP projects** and stay
  that way, so the project holding personal portfolio data keeps no
  billing account; **no service-account key exists anywhere** (metadata
  server); the snapshot writer must pass the Firebase project id
  explicitly. Two ceilings now known to bind at coverage, both ours to
  fix: Supabase's 500 MB database (~2 refresh cycles of headroom) and
  its 5 GB egress (the snapshot build would spend 28% of it hydrating
  reports for two fields).
- **2026-07-29** — §8 revised after an audit of both repos against this
  file (record: `HANDOFF5.md §8`). Item 2 **closed with no action** —
  the frontend's edge function already reads Firestore directly, so the
  GAE hop was never needed. Items 3 and 4 restated as concrete work
  after measuring the live drift: the two repos already disagree on
  `registryVersion`, and the frontend registry still carries
  `entityId`, a GICS `sector`, SONACOMS-as-constituent, and only 24 of
  150 names — which caps the list page at 24 rows regardless of the
  snapshot.
