# PIPELINE → FRONTEND — answers to PIPELINE_TASKS §8

> Written 2026-07-26 from the **pipeline** repo, replying to
> `PIPELINE_TASKS.md` (2026-07-23). Answers first, because two of your
> questions were gating work already in flight. Anything durable that
> crosses the repo boundary now lives in **`SHARED_CONTRACT.md`** —
> treat that as the living contract and this file as a dated reply.

---

## §8 answers

### Q1 — Is the envelope contract still `1.0.0`? **YES.** ✅

Verified against the latest stored report (M&M v5, 2026-07-22):
`sections_json.envelope_contract_version == "1.0.0"`. Same 12 sections,
same 5 block types, `quality` shape unchanged
(`{total, unresolved, verified_total, verified_supported}`).

**One additive change since your doc** — `sections_json` gained
`citation_map`, which you already anticipated. Shape:

```json
"citation_map": { "labels": { "1": "<evidence-uuid>", "2": "…" }, … }
```

⚠️ **Casing:** we store `citation_map` (snake_case, like every other key
in `sections_json`); your doc calls it `citationMap`. Nothing else in
the payload is camelCase. Convention proposal in `SHARED_CONTRACT.md`
§6 — the pipeline stays snake_case end to end and the frontend converts
at its boundary, because renaming DB-side keys would break stored
reports.

### Q2 — Is NIFTY Midcap 150 the right universe? **Accepted.** ✅

Canonical list built from the official NSE Indices CSV and committed
here: `data/universe/nifty_midcap150.json` (150 rows: name, ticker,
screener_slug, nse_industry, isin). Your registry still holds the
24-name seed — **we can ship you the real 150 today** (see §"What we
are shipping you" below).

🚨 **Correction to your §2 — SONACOMS is NOT a constituent either.**
Your doc says *"exactly one — SONACOMS — has a report today"*. Checked
against the official NSE list: **neither SONACOMS nor M&M is in the
NIFTY Midcap 150.** So **zero of the 150 tracked companies have a
report**, and every row currently renders `not_initiated`.

Consequences for your plan:
- The demo-report idea needs a new subject. SONA/M&M remain useful dev
  fixtures but they are outside the tracked universe, so a user
  browsing the list can never reach them.
- Re-running SONACOMS was still worth doing (it was owed as a
  verification gate on our side, and v23 now has citation labels and a
  populated `citation_map`) — but not for the reason your §7.3 gave.
- If you want a covered demo before the swarm scales, pick a real
  constituent and we will run it once G1 lands. Note `M&MFIN`
  (Mahindra & Mahindra Financial Services) **is** a constituent — the
  same entity implicated in our rating-rationale wrong-entity bug, so
  it is a poor first choice until that is fixed.

### Q3 — Cost/time to run the swarm across ~149 companies?

**This is not a cost question yet — the swarm currently cannot run any
company outside SONACOMS and M&M.** Two independent blockers, both in
this repo:

1. `config.COMPANIES` holds exactly those two entries;
   `main.py --ticker APLAPOLLO` exits with "Unknown ticker".
2. Past that, `load_pack()` **raises** for any sector without a pack.
   Three packs exist (`auto_ancillaries`, `auto_oem`, `banks`),
   covering ~10 of the 150. There is no generic fallback yet.

So coverage is gated on engineering, not budget. That work is planned
as G0–G4 in `GENERALIZATION_PLAN.md` (universe-driven onboarding + a
`generic_default` pack, then ~15 sector packs, then the financials
wave — which is 36 of your 150, the hardest cohort).

**Once G1 lands**, measured per-run economics give: **~$1.5/company
first run ≈ $225 for the index**, ~20 min each ≈ **~50 hours
sequential**. Reruns are ~$0.53.

**So yes — plan a phased coverage model, and yes, the UI should show
coverage tiers.** The honest sequencing is auto (~10 companies, packs
exist) → non-financial packs (~114) → financials (36).

### Q4 — Market data source? **Chosen, built and live.** ✅

- **Close price:** Yahoo chart API (`interval=1d`). Authoritative for
  the close *and its date* — we take the date from the last daily bar,
  never "today", so weekends and holidays are self-detecting and no NSE
  calendar is needed.
- **Market cap:** screener top card (the only working source — Yahoo's
  batch quote endpoints are 401). Falls back to the standalone page for
  companies with no consolidated accounts.
- **Cross-check:** if screener's price disagrees with the Yahoo close
  by >2%, the page is stale, so we write the price and **omit** the
  market cap rather than store a wrong one.

**Live as of 2026-07-24: 150/150 close, 150/150 market cap.** Stored in
Supabase `metric_observations` as `price` (unit `inr`) and
`market_cap` (unit **`inr_crore`**, as you asked), `period_type='day'`,
dated with the close date. Idempotent — re-runs insert nothing.

⚠️ **Read it by explicit date, never "the latest day row".** The
research pipeline also writes day-typed rows stamped with its own
scrape date; the two writers can disagree by a day. `marketDataDate`
should be the `period_end` this job wrote. Detail in
`SHARED_CONTRACT.md` §4.

### Q5 — What should the "AI Verdict" column be?

**Owner decision: stays locked, and both the name and the content get
settled with the SEBI/fintech review before any unlock.** We will keep
emitting only the neutral shape `{"status":"coming_soon","version":0}`.

Your compliance flag was right to raise, and we agree with it:
"Verdict" is recommendation-adjacent vocabulary sitting beside a stock
name, which `FOUNDATIONS §1` and generation rule 5 forbid. Please do
not unlock the column — even with descriptive content — ahead of that
review.

### Q6 — Schema changes since `DB_SCHEMA.md`?

Schema itself is **still frozen** (10 tables, no DDL). Three things to
know:

1. `sections_json.citation_map` (Q1).
2. `metric_observations` now receives ~300 rows/day from the market-data
   job (`period_type='day'`). See the read caveat in Q4.
3. `DB_SCHEMA.md` gained two invariants worth knowing if you ever query
   Supabase directly: **PostgREST silently caps unbounded selects at
   1,000 rows** (pagination needs a unique tiebreaker column, or you
   get duplicates-plus-misses with a plausible-looking count), and
   **observation rows are never deleted** — computed lineage ids inside
   stored reports point at them.

---

## What we are shipping you

- **The real 150-company registry** — `data/universe/nifty_midcap150.json`,
  generated from the official NSE CSV. Regenerate your bundled registry
  from this. Includes **ISIN**, which you did not ask for but will want
  for any future data-vendor join.
- **Market caps for all 150**, refreshed daily (Q4).

## What we need from you

1. **Firestore enabled in the Firebase project** (you have the project —
   Auth ≠ Firestore), plus a **service account** with write access to
   `index_snapshots/*`, and the public-read rule on that collection.
2. **Confirm the §5.5 transport can be simplified.** Your doc routes
   GCE → GAE gateway → Firestore to respect the VM's 1 GB egress and
   lack of public IP. **There is no such gateway in this repo** — zero
   references to Firestore, Firebase or App Engine anywhere. We plan to
   run the snapshot writer as a **Cloud Run job**, which has normal
   egress and can write Firestore directly, so the GAE hop is
   unnecessary. Flag it if that conflicts with something on your side.
3. **`registryVersion` string** — we propose `"2026.07"`, bumped only on
   index rebalance. Confirm and bundle the same string.

## Two changes we need in your registry

Both are in `SHARED_CONTRACT.md` §2–§3; summarised here because they
change your typed registry entry:

1. **Drop `entityId`; `ticker` is the sole join key.** Your own doc says
   ticker is *the* join key, and a second identifier is drift waiting to
   happen — worse, `entityId` means different things on each side (your
   slug `"sona-blw"` vs our Supabase UUID). If you need a pretty URL,
   derive the slug from the ticker at render time.
2. **`sector` cannot be GICS.** NSE gives one classification field
   (`Industry`: "Financial Services", "Capital Goods", …) — we have no
   source for "Consumer Discretionary" and will not invent a mapping
   nobody maintains. Proposal: `industry` = NSE Industry (available
   now); `sector` = our `pack_id` once sector packs exist, since that is
   the taxonomy actually driving the analysis. Until then, omit
   `sector` rather than fabricate it.

## Status of your §7 asks

| Ask | Status |
|---|---|
| Re-run SONACOMS (v22 predates citation labels) | **In progress** — the run is already owed as a verification gate on our side, so it satisfies both |
| Fix the rating-rationale entity bug | Open, tracked in `HANDOFF4 §6.1` — agreed it must land before any credit surface |
| Persist `calc:` values | Not started; still assessed as a small composer change |
| Ship YoY deltas pre-computed | Not started; agreed the frontend must not derive numbers |
