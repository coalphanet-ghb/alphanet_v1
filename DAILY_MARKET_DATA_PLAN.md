# DAILY MARKET DATA — plan (owner-approved 2026-07-26, ready to implement)

> **Goal.** Closing price + market cap for all 150 NIFTY Midcap 150
> companies, refreshed once daily, **independent of the research
> swarm**. Feeds the frontend list page (`ui_bridge/PIPELINE_TASKS.md`
> §4, and §5's snapshot writer downstream).
>
> **Non-goal.** The PE path, P/B and own-history percentile keep using
> the existing monthly / FY-end series in `s3_compute`. This job is
> **purely additive** — it does not change how any report is produced.
>
> Owner decisions on record: fetch market cap properly every day (no
> derived-from-cached-shares shortcut); deploy as a job on GCP.

---

## 1. Why decouple (the current state, measured)

| | Price | Market cap |
|---|---|---|
| Source | Yahoo chart API, `interval=1mo` | Screener top card |
| Granularity | **monthly** (13× 1y + 10y FY-end) | single latest value |
| Trigger | `sector_backbone.refresh_backbone` (TTL 1 day) → else `s2_extract._price_history_via_yahoo` | the same screener parse |
| Runs when | **only when a research run touches that sector** | same |
| Coverage | 15 companies max (auto packs) | same 15 |

Nothing in the system runs on a clock: the backbone's 1-day TTL only
fires when somebody researches a company in that sector. So today
`no research → no price`, and 149 of the 150 list rows would render
empty forever. The data is also the wrong shape (monthly, not a dated
daily close).

Decoupling is right on three counts: the dependency direction is wrong
(price is a fact about a ticker, not about whether an LLM wrote a
report); the granularity and freshness are wrong; and it is zero-LLM
deterministic work that should never sit behind a ~$0.53 LLM run
(FOUNDATIONS §1).

## 2. Sources — probed live 2026-07-26

| Source | Result |
|---|---|
| Yahoo chart `interval=1d&range=5d` | ✅ works — `2026-07-24 → 717.95`, identity-validated via `meta.longName`, **1.5 KB**/company. Carries the close DATE. No mcap field. |
| Yahoo `v7/finance/quote` (batch) | ❌ HTTP 401 Unauthorized |
| Yahoo `v10/quoteSummary` | ❌ HTTP 401 Invalid Crumb |
| Screener top card | ✅ both — `price ₹718`, `market_cap ₹44,707 Cr.`, 1.1 s, **192 KB**/company, existing proven parser |

Market cap has exactly one working source. 150 × 192 KB ≈ **28 MB/day
inbound**; on GCP **ingress is free** (billing is on egress, and ours is
~150 KB/day of requests), so there is no reason to compromise.

**Roles by strength:** Yahoo is authoritative for the close *and the
close date*; screener supplies market cap plus a price cross-check.
Letting Yahoo's last bar define the date makes weekends and holidays
self-detecting — **no NSE holiday calendar is needed**.

## 3. Landmine ledger

Found while tracing this. Three are fixed here, three are decided or
deferred with a written home.

| # | Landmine | Disposition |
|---|---|---|
| L1 | `s3_compute.py:605` calls `db.get_metric_observations(eid)` unbounded; **PostgREST caps at 1,000 rows silently**. SONA is at **988** — twelve rows from degrading every calc citation to a `mem_` id. Pre-existing, unrelated to this feature. | **FIXED — D0.1** (paginate) |
| L2 | `get_or_create_entity` dedups on `(name, type)`; the universe CSV uses NSE names, the DB uses seeded names — **6 confirmed mismatches** (`'Bharat Forge Ltd.'` vs `'Bharat Forge'`, `'UNO Minda Ltd.'` vs `'Uno Minda'`, …). Naive seeding creates 6 duplicate entities and splits their observations. | **FIXED — D0.2/D0.3** (resolve by ticker first) |
| L3 | `screener_parser.py:110` stamps `date.today()` — the scrape date, not the close date. A Saturday run would invent a Saturday close. | **AVOIDED here** (this job dates from Yahoo); residue in the research path **deferred → HANDOFF4 §6.7** |
| L4 | Reusing the screener path wholesale would write **7** day-rows/company/day = 262 K rows/yr. | **FIXED by design** — this job writes exactly 2 metrics (75 K rows/yr ≈ 12 MB) |
| L5 | `pe`/`roce_pct`/`roe_pct`/`dividend_yield_pct` are screener-*computed* yet stored as observations (vs invariant 3). | **Deferred → HANDOFF4 §6.8** |
| L6 | SONA's 233 single-occurrence metric names (24% of rows) look like bloat. | **Decided: do NOT clean** — `inputs[]` lineage ids are cited by stored reports, so deleting orphans them. Written as **DB_SCHEMA invariant 10**; the 1,000-row cap is **invariant 9**. |

## 4. Storage decision

**`metric_observations`, `period_type='day'`, one row per (company,
metric, close date).** Rationale:

- Semantically exact: an observed numeric fact with a period. Both
  values are *observed from a source*, so invariant 3 holds.
- **Idempotent for free** — the unique constraint
  `(entity_id, metric_name, period_start, period_end)` plus
  `ignore_duplicates=True` means a re-run writes nothing. Retries and
  double-schedules are safe by construction.
- Respects the frozen schema (no DDL, invariant 8).
- Not a new pattern: the screener parse already writes day-typed
  `price`/`market_cap`.
- Future-proof: a real daily close series is what a better PE path
  would need later.

Rejected: one `knowledge_entries` blob per day. Smaller (250 rows/yr)
and it would serve the UI in a single read, but it is unqueryable
per-company and forecloses the daily-PE path.

Consumers must query an **explicit `period_end`**, never "the latest
day row" (see L3 residue).

## 5. Implementation

### D0 — Prerequisites *(land BEFORE any daily write)*

**D0.1 — paginate `get_metric_observations`** (`src/db.py`)

```python
def get_metric_observations(entity_id, metric_names=None, _page=1000):
    """Complete set for an entity. Paginated: PostgREST silently caps
    unbounded selects at 1,000 rows (DB_SCHEMA invariant 9) and
    s3_compute's lineage id_map was twelve rows from truncating."""
    client, out, off = get_client(), [], 0
    while True:
        q = (client.table("metric_observations").select("*")
             .eq("entity_id", entity_id).order("period_start")
             .range(off, off + _page - 1))
        if metric_names:
            q = q.in_("metric_name", metric_names)
        batch = q.execute().data or []
        out += batch
        if len(batch) < _page:
            return out
        off += _page
```

*Touches the research pipeline → lands ALONE.*
**Gates:** SONA returns 988 with `_page=1000` **and** with `_page=100`
(proves the loop, since 988 does not yet truncate) → `--dry-run` →
live SONA run → `diff_golden` clean.

**D0.2 — `db.get_entity_by_ticker(ticker, entity_type="company")`**
Looks up `metadata->>ticker`; returns the row or `None`. No backfill
task: the 5 ticker-less entities are Bosch / Tesla / Ford / General
Motors / Stellantis — foreign supply-chain counterparties, correctly
tickerless.

**D0.3 — `scripts/seed_universe.py`** — seeds entities from
`data/universe/nifty_midcap150.json`, **ticker-first**: resolve by
ticker → else by exact name → else create with
`metadata={ticker, screener_slug, isin, nse_industry}`. Never renames
an existing entity. `--dry-run` prints the plan.
**Gates:** exactly **6** resolve to existing rows (ASHOKLEY,
BHARATFORG, ENDURANCE, ESCORTS, SCHAEFFLER, UNOMINDA), 144 created,
company entities 21 → **165**, and
`select metadata->>ticker, count(*) group by 1 having count(*) > 1`
returns **zero rows**.

**D0 STATUS — implemented 2026-07-26, one gate outstanding.**
- `get_metric_observations` paginated. **A real bug surfaced in the
  gate:** the first implementation ordered by `period_start` only and
  returned 988 rows at every page size — the correct *count*, but a
  different *id set* each time (duplicates plus misses), because
  `period_start` is not unique and OFFSET has no stable tie-break.
  Fixed with `.order("period_start").order("id")`; now 988 identical
  unique ids at `_page` 1000 / 100 / 7, and the `metric_names` filter
  paginates correctly too. Written up as DB_SCHEMA invariant 9 —
  **verify a paginator on its id set, never its row count.**
- `db.get_entity_by_ticker` added; resolves SONACOMS, returns None for
  an unknown ticker. No backfill needed — the 5 ticker-less entities
  are Bosch / Tesla / Ford / GM / Stellantis, correctly tickerless.
- `scripts/seed_universe.py` run: 6 resolved by ticker (exactly the 6
  name-mismatch cases, none renamed), 144 created, **21 → 165 company
  entities**, GATE PASS (160 distinct tickers, zero duplicates, all
  150 universe tickers resolve). Re-run creates 0 — idempotent.
- `py_compile` clean; `main.py --dry-run` clean.
- **GATE CLOSED 2026-07-27.** SONA v23: **$0.51, 0 spirals,
  507/507 citations (0.0% unresolved — a project first), `diff_golden`
  vs v22 clean, NO regression flags.** The pagination fix is
  behaviourally invisible, as intended. The first attempt at this gate
  aborted when `synth_F` spiralled twice; the identical rerun was
  clean, confirming sampling rather than regression (analysis now in
  HANDOFF4 §5). Bonus: v23 is also the citation-labelled SONACOMS
  re-run the frontend asked for in `PIPELINE_TASKS §7.3` — the only
  covered company in the universe, so it is the demo report.

### D1 — `src/ingestion/market_data.py` (new, zero-LLM)

Mirrors `fetcher.py` conventions — raises `FetchError`, never aborts a
caller.

```python
def fetch_daily_close(ticker, company_tokens) -> tuple[float, str, str]:
    """(close, close_date_iso, long_name) from Yahoo's chart API
    (range=5d, interval=1d). The DATE is the last bar's timestamp —
    never date.today() — so non-trading days are self-detecting.
    Identity-validated via meta.longName (the wisesheets/Macy's rule)."""

def fetch_market_cap(screener_slug, company_tokens) -> tuple[float, float]:
    """(market_cap_cr, price) from the screener top card. Reuses the
    proven parse_company_page; validates the company name appears in
    the page's 'about' text before trusting the numbers."""
```

### D2 — `scripts/daily_market_data.py` (new)

Flags: `--dry-run`, `--limit N`, `--universe <path>`,
`--min-coverage 0.90`.

Per company: resolve entity by ticker (missing → warn "run
seed_universe first", skip) → Yahoo close + date → screener mcap +
price → **cross-check**: if `|screener_price − close| / close > 2%`
the screener page is stale, so write price and **skip mcap** rather
than store a stale one → accumulate rows.

Rows written (nothing else):

| metric_name | unit | value |
|---|---|---|
| `price` | `inr` | Yahoo close |
| `market_cap` | `inr_crore` | screener top card |

with `period_type='day'` and `period_start = period_end =` **that
company's own close date** (a suspended stock legitimately reports an
older date; writing it under its own date stays truthful, and no
phantom day is ever invented). One `bulk_save_metric_observations` at
the end.

Operational shape: sequential with a ~0.5 s politeness delay
(~4–5 min for 150); one retry per company on transient failure;
per-company failure is never fatal; missing value → **omit the row**
(the UI contract says `null`, never `0`, and a missing row *is* null).

Output ends with the gate line, e.g.
`[daily] 2026-07-24: 149/150 close, 147/150 mcap, 3 stale-price skips, 296 rows written`
and exits non-zero below `--min-coverage`, so a silent partial failure
pages you instead of quietly under-filling the list page.

**D1/D2 STATUS — DONE and verified in production 2026-07-26.** Owner's
full run: **150/150 close, 150/150 mcap, 0 stale skips, 367 s**, 300
rows submitted / 290 newly inserted (10 pre-existed from smoke tests —
the idempotency proving itself). DB confirms 150 `price` + 150
`market_cap` rows at 2026-07-24 across 150 distinct companies; table
8,452 -> 8,752, exactly +300. The run happened on a **Sunday** and
correctly recorded **Friday's** close: weekend detection via Yahoo's
last bar, no NSE calendar, no phantom row.

Four defects surfaced in the dry-run gate before that, all fixed; each
was a *false negative* costing real companies:

1. **Identity tokens were too clever.** Keeping only "distinctive"
   (>=4-char) words left `3M India Ltd.` with NO tokens — an empty list
   silently disables the guard — and reduced `AIA Engineering Ltd.` to
   `['engineering']`, a word its own screener page never uses ("About
   AIA manufactures high-chrome grinding media…"), so a *correct* page
   was rejected. Now: every non-suffix word, `any` match.
2. **`longName` is null for recent listings** (SWIGGY, LENSKART, GROWW,
   NTPCGREEN, ITCHOTELS, HDBFS, …) — 13 of 150 rejected despite valid
   closes. Now validates on `meta.symbol` (exact, and the real defence
   against the Macy's class) plus `longName or shortName`.
3. **Companies with no consolidated accounts** (PAGEIND, SBICARD, BDL,
   HONAUT, ICICIGI, POWERINDIA) still serve a `/consolidated/` page —
   an empty shell where market cap renders as a bare `₹ Cr.`. Falls
   back to standalone; and a consolidated page that *raises* (LGEINDIA,
   too thin for the parser) must fall through too, not abort.
4. **Ampersand tickers** (`GVT&D`, `M&MFIN`): the URL path needs
   `%26`, but Yahoo echoes `meta.symbol` decoded — comparing the two
   encodings rejected both.

Also fixed: the summary line reported rows *submitted* as rows
"written", so a re-run claimed "6 rows written" having inserted none.
It now reports `N rows submitted, M newly inserted (already up to
date)` — verified 0-new on re-run and 4-new when two companies were
added. Live-write smoke test done at `--limit 5`; 10 rows in the DB,
no duplicates.

### D3 — GCP deployment

> Superseded in detail by **`HANDOFF5.md §3b.5`** (the work) and
> **`INFRASTRUCTURE.md`** (topology, verified quotas, measured
> headroom). Kept here because the *reasoning* below is what chose the
> shape. Corrections since it was written are flagged inline.

- **Cloud Run Job** (not GCE): batch-shaped, no idle cost, and outbound
  internet works out of the box — a no-public-IP GCE would need Cloud
  NAT. ⚠️ **The "60-min timeout" was wrong**: the Cloud Run job task
  timeout defaults to **10 minutes** (max 168 h), which would kill our
  ~6-minute job on a slow day. Set it explicitly to ~30 min.
- **Region `asia-south1`**, matching Firestore — whose location is
  permanent. The free tier is not region-restricted for any service
  this job uses (`INFRASTRUCTURE.md §5`).
- **Cloud Scheduler** → `0 18 * * 1-5`, TZ `Asia/Kolkata` (post-close).
  Retries are safe because the job is idempotent. Comfortably past the
  intraday guard at 15:40 IST.
- **Secret Manager** for `SUPABASE_URL` + `SUPABASE_SERVICE_ROLE_KEY` —
  never baked into the image, never in a `VITE_` var (FOUNDATIONS §2:
  the service-role key is server-side only). **Firestore needs no
  stored credential**: the job runs as a service account and takes
  credentials from the metadata server, so there is no JSON key.
- Egress stays trivial (~150 KB/day of requests), so
  `PIPELINE_TASKS §5.5`'s 1 GB/month ceiling — which is about writing
  to Firestore — is untouched by this job. ⚠️ **But the snapshot
  BUILDER's Supabase egress is not trivial at coverage**: hydrating 150
  reports for two fields is ~64 MB/run ≈ 1.4 GB/month, 28% of
  Supabase's free 5 GB. Fixed by persisting `has_open_flags`
  (`HANDOFF5 §5b.1b`, `INFRASTRUCTURE.md §4.2`).
- **This job is what keeps Supabase alive.** Free projects suspend after
  1 week of inactivity, and a suspended project needs manual restore —
  so a silent failure compounds rather than self-heals. That is the real
  reason the failure alert is mandatory, not optional.

## 6. The snapshot builder — DONE 2026-07-27 (`scripts/build_snapshot.py`)

Reads Supabase, emits the exact `IndexSnapshot` payload (contract in
`ui_bridge/SHARED_CONTRACT.md` §5). **Firestore transport deliberately
excluded** — it needs a service account and the answers in
`PIPELINE_ANSWERS.md`; the builder is fully testable without it and
emits the exact bytes that will later be uploaded.

Verified: **150 companies, 150 with market cap, 28.6 KB** (contract
predicted 25–30 KB). Re-run holds the version (`v1 (unchanged —
version held)`), so an unchanged rewrite cannot bust the edge cache.
Report-joining was proven on a temporary universe containing SONA and
M&M — `status: updated`, `latestVersion` 23/5, full `quality` object,
`lastUpdatedISO` with offset — since no real constituent has a report
to exercise it.

Design notes worth keeping:
- **`marketDataDate` is not "the newest day row."** The research
  pipeline also writes day-typed `market_cap` stamped with its own
  scrape date, so one stray row could masquerade as a trading day. The
  builder takes the newest date whose coverage clears 50% of the index
  — which skips holidays for free. Proof it matters: SONA and M&M come
  back `marketCapCr: null` because their only caps are research-scrape
  dated, not close dated. Null, never 0.
- **`sections_json` is never bulk-fetched** — ~430 KB per report, so
  the index is read without it and only the winning rows are hydrated.
  At 150 covered companies a naive select would drag ~64 MB per run.
  (Cleaner future fix: have the composer persist `has_open_flags`
  alongside `quality`, so the snapshot never needs the blocks at all.)
- **`snapshotVersion` is the `knowledge_entries` version counter** for
  section `index_snapshot`, so version discipline survives an ephemeral
  Cloud Run filesystem.
- **`entities.type` is NOT freely extensible** — `type='index'` is
  rejected by a CHECK constraint (SQLSTATE 23514). The index entity is
  `type='other'` with `metadata.kind='index'`; DB_SCHEMA invariant 8
  corrected accordingly.

🚨 **Finding that changes the product plan: ZERO of the 150 tracked
companies have a report.** SONACOMS and M&M are both outside the NIFTY
Midcap 150 (the frontend's §2 believed SONACOMS was a constituent).
Every row renders `not_initiated` until the swarm can run real
constituents — which is blocked on GENERALIZATION_PLAN G1.

Also out of scope, noted for later: once a daily close series exists
for 150 companies, `sector_backbone`'s 1y-monthly Yahoo fetch becomes
derivable from it (month-end closes), and the PE path could move from
monthly to daily resolution. Real optimization, own change, own
`diff_golden`.
