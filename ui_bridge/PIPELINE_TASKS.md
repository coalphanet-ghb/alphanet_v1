# PIPELINE TASKS — frontend → AlphaNet pipeline repo

> Written 2026-07-23 from the **frontend repo** (`alphanet`, the React/Vite SPA
> on Cloudflare Pages). This is the reply to your `UI_HANDOFF.md`.
>
> **How to use this doc:** you are reading it inside the *pipeline* repo. It
> tells you what the frontend now needs from the backend, in what order, and
> the exact data contract to write against. It assumes you know this repo
> (`HANDOFF4.md`, `FOUNDATIONS.md`, `DB_SCHEMA.md`) and knows nothing about the
> frontend beyond what is written here.
>
> **First action:** don't start coding. Read §1–§3, then answer the questions in
> §8. Two of them can change the work in §5.

---

## 1. What the frontend now is

Two surfaces, two completely different data paths. This split is deliberate and
is the thing to understand before anything else.

| Surface | Route | Payload | Path | Traffic |
|---|---|---|---|---|
| **Company list** | `/reports` | ~25 KB, all 150 companies | Supabase → **Firestore mirror** → Cloudflare edge cache → browser | high |
| **Report detail** | `/reports/:ticker` | ~430 KB, one company | Supabase → **Cloudflare Pages Function** (service-role key) → browser | low |

The list is small, read by everyone, and changes on a schedule — so it is
mirrored once into Firestore and served from an edge cache. **The pipeline's job
for the list is to keep that one Firestore document fresh.** That is task §5.

The report detail path reads Supabase directly through a server-side function.
**The pipeline does not serve it and does not need to build an API for it** —
see §7.

---

## 2. The tracked universe changed — read this carefully

The frontend now lists the **NIFTY Midcap 150** as its tracked universe.

Two consequences:

1. **M&M is a largecap. It is not in the NIFTY Midcap 150.** Your most complete
   report (M&M v5) is therefore not a member of the universe the product tracks.
   It remains useful as a development/demo fixture, but it is not coverage.
2. Of the 150 companies, **exactly one — SONACOMS — has a report today.** The
   other 149 will render as `not_initiated` / "coming soon", which the UI
   handles honestly. Nothing is broken by this, but it means the swarm has ~149
   companies of runway. **Plan the compute and API cost for that before running
   it** — you are on an e2-micro with sequential processing.

Whether the universe should be Midcap 150 at all is a product decision that is
already made on the frontend side. If it is wrong, say so now (§8), because
everything below assumes it.

---

## 3. The registry — the shared root dependency

Both repos need the same answer to *"which 150 companies?"*. The frontend needs
it to render the list; you need it to know what to research; the market-cap job
needs it to know what to price. **If the two repos maintain separate lists they
will drift, and drift here is silent.**

### What exists on the frontend today

`src/services/companies/registry/niftyMidcap150.ts` — a typed, bundled list.
It currently holds a **labelled 24-name seed, not the real 150**, because index
membership can't be recalled reliably and hand-typing 150 tickers would be
fabricated data.

Each entry:

```ts
{
  entityId: "sona-blw",              // stable slug; should match Supabase entities
  ticker:   "SONACOMS",              // NSE symbol — the JOIN KEY for everything
  name:     "Sona BLW Precision Forgings Ltd.",
  sector:   "Consumer Discretionary",
  industry: "Auto Components",
  exchange: "NSE"
}
```

### Task 3.1 — establish the canonical list

1. Pull the official **NIFTY Midcap 150** constituents from NSE Indices
   (niftyindices.com → Broad Market → NIFTY Midcap 150). CSV or factsheet.
2. Commit that CSV to **this (pipeline) repo** as the canonical artifact —
   it is a data repo, this is data.
3. Make this repo's universe (`src/config.py COMPANIES`, or wherever it now
   lives) **generated from that CSV**, not hand-maintained.
4. Send the frontend either the CSV or a JSON array of the objects above. The
   frontend regenerates its bundled registry from it with a script.

`ticker` is the join key across both repos and the Firestore snapshot. It must
match exactly — NSE symbol, uppercase, no suffix.

**Done when:** one CSV in this repo drives both repos' universe, and a rebalance
is a file refresh + version bump rather than an edit in two places.

---

## 4. Market cap for 150 companies — this is new work

`metric_observations` only holds price/mcap for companies the swarm has actually
researched. That is 2. The list page needs a market cap for **all 150**, daily.

**This is not a job for the research swarm.** It is a separate, cheap ingestion:

- Source: any market data feed covering NSE (your call — NSE bhavcopy, a broker
  API, a data vendor).
- Cadence: **once daily, post market close.** Market caps do not need to be live;
  the UI states the date they are as of.
- Store: Supabase, as the source of truth. Whether that is `metric_observations`
  with `metric='market_cap'` or a dedicated table is your schema decision.
- Unit: **₹ crore**. The frontend formats crore → "₹ 3.91 L Cr" for display and
  never converts anything itself.

**Done when:** a scheduled job writes a fresh market cap for every ticker in the
registry each trading day, tagged with the close date it reflects.

---

## 5. The snapshot writer — the main deliverable

One Firestore document holds the entire dynamic state of the list. The frontend
reads it through an edge cache; you keep it fresh.

### 5.1 Firestore contract

```
collection/document : index_snapshots/nifty_midcap_150
field               : payload   (string)
value               : JSON.stringify(<IndexSnapshot>)   ← the whole thing, one string
```

The payload is stored as **one JSON string**, not as nested Firestore fields.
That is intentional: the edge function returns it verbatim without decoding
Firestore's typed-value format. ~150 companies ≈ 25–30 KB, far inside
Firestore's 1 MiB document limit.

Security rule: **public read** on `index_snapshots/*`. The snapshot is public
data — company names, market caps, and locked "coming soon" verdicts. No
secrets, no user data. Public read lets the edge fetch it with the public web
API key instead of a service account.

### 5.2 The exact payload shape

```json
{
  "manifest": {
    "registryVersion": "2026.07",
    "snapshotVersion": 47,
    "marketDataDate": "2026-07-22",
    "verdictEpoch": 0
  },
  "dynamics": [
    {
      "ticker": "SONACOMS",
      "marketCapCr": 38400,
      "status": "updated",
      "lastUpdatedISO": "2026-07-22T17:42:00+05:30",
      "latestVersion": 22,
      "quality": {
        "total": 311,
        "unresolved": 24,
        "verified_supported": 121,
        "verified_total": 154
      },
      "hasOpenFlags": true,
      "verdict": { "status": "coming_soon", "version": 0 }
    },
    {
      "ticker": "PERSISTENT",
      "marketCapCr": 41200,
      "status": "not_initiated",
      "lastUpdatedISO": null,
      "latestVersion": null,
      "quality": null,
      "hasOpenFlags": false,
      "verdict": { "status": "coming_soon", "version": 0 }
    }
  ]
}
```

### 5.3 Field derivation

**`manifest`**

| Field | Rule |
|---|---|
| `registryVersion` | Must equal the registry version string the frontend bundles. Signals "your static list is stale" when they diverge. Bump only on rebalance. |
| `snapshotVersion` | Monotonic integer. **Increment on every write where content actually changed.** Unchanged content ⇒ do not bump (it would bust caches for nothing). |
| `marketDataDate` | `YYYY-MM-DD` of the market close the caps reflect. The client swaps in new caps only when this advances. |
| `verdictEpoch` | Bump when **any** company's verdict changes. `0` while verdicts are locked. |

**`dynamics[]`** — one entry per registry ticker. Emit an entry for **every**
company in the registry, including uncovered ones (as in the `PERSISTENT`
example above).

| Field | Rule |
|---|---|
| `ticker` | NSE symbol. Join key. Must match the registry exactly. |
| `marketCapCr` | ₹ crore from §4. **`null` if unknown — never `0`.** |
| `status` | One of `"updated" \| "updating" \| "stale" \| "not_initiated"`. Suggested: no `report_versions` row → `not_initiated`; run in flight → `updating`; `generated_at` within 7 days → `updated`; older → `stale`. You own the thresholds; the UI just displays. |
| `lastUpdatedISO` | ISO 8601 **with offset**, from `report_versions.generated_at`. `null` if never generated. The browser computes "3 hr ago" from this locally and never re-asks — so accuracy here matters. |
| `latestVersion` | Latest `report_versions.version`. `null` if none. |
| `quality` | The `quality` object from `sections_json`. `null` if none. |
| `hasOpenFlags` | `true` if the latest report has any `flag` block with `status: "FLAG"`. |
| `verdict` | **Hardcode `{ "status": "coming_soon", "version": 0 }` for now.** See §6. |

### 5.4 When to write

- **Daily**, after the market-cap job (§4) — updates caps, advances `marketDataDate`.
- **On report publish** — updates `status`, `lastUpdatedISO`, `latestVersion`,
  `quality`, `hasOpenFlags` for that company.

Write the whole document each time. Do not attempt partial updates — the frontend
reads it as one string, and a full rewrite of 30 KB is cheap and atomic.

### 5.5 Respect your own egress shield

Your architecture doc is explicit: the GCE VM has **no public IP and 1 GB/month
egress**, and all outbound traffic is offloaded to GAE. A snapshot writer that
posts to Firestore directly from GCE violates that.

**Follow the path you already use for report publishing:** GCE computes the
snapshot → POSTs it to the GAE gateway over internal VPC → **GAE writes
Firestore**. The Firebase service account lives on GAE, not GCE, and never
leaves this repo.

**Done when:** `index_snapshots/nifty_midcap_150` exists and refreshes on both
triggers, and `snapshotVersion` moves only on real change.

---

## 6. AI Verdict — build the plumbing, not the feature

The list has a column the frontend currently renders as a locked
"🔒 Coming soon" badge for every row. The data model is already in place:

```json
"verdict": { "status": "coming_soon" | "available", "version": 0, "label": "…" }
```

**Emit `{"status":"coming_soon","version":0}` for everything.** Do not populate
labels yet.

⚠️ **Compliance flag, raised from the frontend side.** "Verdict" is
recommendation-adjacent vocabulary — exactly what `FOUNDATIONS §1` and the
generation contract's rule 5 ban, and it sits next to a stock name in a table.
While locked there is no exposure. **Before this feature is unlocked, the public
label needs a decision (most likely a rename) with the SEBI/fintech review.**
The data model is neutral on purpose; only the display string carries risk.

If you have a view on what this column should actually contain — something
descriptive and evidence-based rather than a verdict — raise it in §8. That
design is not settled and your read on what the pipeline can honestly support
should shape it.

---

## 7. Report detail — what the pipeline does *not* need to do

The frontend reads report envelopes **directly from Supabase** via a Cloudflare
Pages Function holding the service-role key. Nothing new is needed from you to
serve it. Specifically:

- ❌ Do not build a reports API. ❌ Do not mirror reports into Firestore
  (430 KB × 150 would blow past the Firestore doc limit and the free tier).
- ✅ **Keep RLS fully closed.** The service-role key stays server-side, in a
  Cloudflare secret, never in the browser bundle.
- ✅ Keep `report_versions.sections_json` as the API. The frontend never parses
  `final_report_md`.

### Four asks that *do* affect the report UI

1. **Persist `calc:` values.** Computed citations currently resolve to a formula
   id with no number behind them, so the UI can only render a "computed"
   provenance chip. Your handoff calls this "one line in the composer, no schema
   change." Worth doing — it unlocks showing the actual figure.
2. **Ship YoY deltas pre-computed.** The Key Ratios tiles want "ROE 18.6% · YoY
   +180 bps". A delta is a *derived* value, and the frontend is contractually
   forbidden from deriving numbers (rule 2). So either the pipeline emits the
   delta alongside the value, or the tiles show the value alone. Prefer the
   former.
3. **Re-run SONACOMS.** SONA v22 predates citation labels — raw UUIDs, empty
   `citationMap`. It is the **only covered company actually in the universe**, so
   it will be the demo report, and it currently renders worse than M&M.
4. **Fix the rating-rationale entity bug** before any credit surface is built —
   M&M v5 ingested a *Mahindra & Mahindra Financial Services* bond page as M&M
   evidence (your `HANDOFF4 §6.1`).

---

## 8. Answer these back

Blocking or shaping the work above:

1. **Is the envelope contract still `1.0.0`?** Same 12 sections, same 5 block
   types, same `quality` shape? The frontend is being rebuilt against the
   `UI_HANDOFF.md` spec dated 2026-07-22 and will be wrong if the shape moved.
   ← *most urgent; a 30-minute check saves a rebuild*
2. **Is NIFTY Midcap 150 the right universe?** (§2) Everything assumes it.
3. **What is the realistic cost/time to run the swarm across ~149 new
   companies** on the current e2-micro? If it is prohibitive, the product needs
   a phased coverage plan and the UI should show coverage tiers.
4. **Do you have a market data source** for §4, or does one need choosing?
5. **What should the "AI Verdict" column actually be?** (§6)
6. Any schema changes since `DB_SCHEMA.md` that the frontend should know about?

---

## 9. Suggested order

| # | Task | Why this position |
|---|---|---|
| 0 | Answer §8 Q1 (contract check) | 30 min; unblocks frontend work already in flight |
| 1 | §3 registry — canonical CSV, both repos generate from it | root dependency for everything |
| 2 | §4 market cap ingestion | feeds the snapshot |
| 3 | §5 snapshot writer + Firebase collection/rule/service account | makes the list page live |
| 4 | Hand the frontend `FIREBASE_PROJECT_ID` + web API key | list goes live in minutes |
| 5 | §7 asks (calc: persistence, YoY deltas, SONA re-run) | improves the report page |
| 6 | §2 breadth — run the swarm across the universe | the long pole; plan cost first |

Steps 1–4 here run **in parallel** with the frontend rebuilding the report
detail page. The two tracks only converge at step 4.

---

## 10. Credential handling

| Credential | Lives | Never |
|---|---|---|
| Firebase **service account** (snapshot writer) | this repo / GAE | the frontend repo, GCE |
| Firebase **web API key** + project id | frontend's Cloudflare Pages env | — (public key, snapshot is public data) |
| **Supabase service-role key** | Cloudflare Pages secret (frontend, server-side only) | any `VITE_`-prefixed var, any browser bundle, any chat message |

Do not paste any secret into a chat with an assistant. Put them directly into
the deployment environment.
