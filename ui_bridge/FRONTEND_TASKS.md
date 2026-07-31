# FRONTEND TASKS — AlphaNet pipeline → frontend repo

> Written 2026-07-29 from the **pipeline** repo. This is the mirror of
> your `PIPELINE_TASKS.md`: what we need from your side, why, and what
> we measured to conclude it.
>
> **`SHARED_CONTRACT.md` remains authoritative** for anything crossing
> the boundary. This file is a work list; durable agreements belong
> there. `PIPELINE_ANSWERS.md` (2026-07-26) answered your §8 and is
> still valid — nothing here contradicts it.
>
> Everything below came out of an audit of both repos against the code
> on 2026-07-29. Where a claim is measured rather than assumed, the
> file and line are named so you can check it yourself.

---

## 1. The short version

We are deploying the daily market-data + snapshot job to GCP and
wiring the Firestore transport (the "main deliverable" of your §5).
**Four things on your side gate it**, and one thing you planned is
**cancelled**:

| # | Item | Blocks |
|---|---|---|
| 1 | ~~Firestore enabled~~ | **DONE** — `(default)`, Native mode, `asia-south1` |
| 2 | Service account with Firestore write, **no JSON key** | the writer cannot authenticate |
| 3 | Public-read rule on `index_snapshots/*` | your own edge function's read |
| 4 | Regenerate the bundled registry from the canonical 150 | the list page renders **24 rows**, not 150 |
| 5 | ~~The GAE gateway hop (your §5.5)~~ | **cancelled — do not build it** |

2–3 are one sitting of console work. 4 is a code change. 5 is deleting a
plan.

**Two things changed since this file was first written (2026-07-30):**
F1 turned out to be already done, and **F2 no longer needs a key file** —
see §2. Both make this list shorter, not longer.

---

## 2. Firestore — already on. What's left is one account and one rule

**F1 is done** — the database exists, `(default)`, **Native mode**,
`asia-south1`. Native mode is what your edge function needs; the REST
document path it uses doesn't exist in Datastore mode. Nothing to do.

Two things remain, and neither involves handling a secret.

**F2 — a service account, with no key file.** The job runs on Cloud Run
*as* a service account and takes credentials from the metadata server,
so **there is nothing to download, store, or rotate.** Earlier versions
of this file and of `SHARED_CONTRACT.md` said "service account key via
Secret Manager" — that was written before the runtime was settled, and
it's now strictly worse than the alternative. Ignore it.

What's needed, given Cloud Run and Firestore are in **different
projects**:

- create the service account in the **Cloud Run project** (ours, the
  billed one);
- grant it Firestore write **on your Firebase project** — add its email
  as a principal with Cloud Datastore User, or narrower;
- **do not generate a JSON key.**

**F3 — the public-read rule**, and this one needs care now that the
database isn't empty. Your read path uses `FIREBASE_API_KEY`, the public
web key, so without a read rule your own edge function 503s and the page
falls back to its local sample. But the same database holds
`portfolios/{uid}` — real personal portfolio data. So the rule must be
**scoped by name and added alongside what exists**:

```
match /index_snapshots/{doc} {
  allow read: if true;
  allow write: if false;
}
```

`allow write: if false` is correct even though we write daily: the F2
service account authenticates server-side and **bypasses security rules
entirely**. Never widen this with `match /{document=**}`, and never use
"test mode" — either would expose `portfolios`.

We will write precisely what your edge function already expects, so
nothing changes on your side once the document exists:

```
collection/doc : index_snapshots/nifty_midcap_150
field          : payload   (stringValue) = JSON.stringify(IndexSnapshot)
```

One JSON **string**, not nested Firestore fields — your reader does
`doc.fields.payload.stringValue`, and nested fields would return an
object it cannot parse.

## 3. The GAE gateway is cancelled — please don't build it

Your `PIPELINE_TASKS §5.5` routes GCE → a Google App Engine gateway →
Firestore, to respect a VM's 1 GB egress ceiling and its lack of a
public IP.

**That constraint does not apply to what we are building.** We are
deploying a **Cloud Run Job**, which has normal outbound internet and
no such ceiling; the 1 GB limit you were designing around is a GCE
free-tier constraint. There is no gateway anywhere in the pipeline
repo and there will not be one.

We also do not need one: your `functions/api/index-snapshot.ts` reads
Firestore **directly**, and our writer will write it directly. The hop
would sit between two things that already talk to each other.

Recorded as **closed with no action** in `SHARED_CONTRACT.md` §8 item
2. Flag it now if something on your side genuinely depends on that
gateway existing; otherwise it is off both lists.

## 4. The registry rebuild — three changes, one pass

This is the one item here that is real engineering, and it is the one
that decides whether the list page works.

### Why it is blocking, measured

`src/services/companies/merge.ts` iterates the **registry** and drops
any snapshot entry with no matching identity — your own comment says
so: *"a dynamic entry with no matching identity is ignored (it is not
in the tracked universe)."* That is the right design. The consequence
is that **the registry, not the snapshot, decides how many rows
render.**

`src/services/companies/registry/niftyMidcap150.ts` still holds the
24-name hand-typed seed (its own header says so). So a correct,
complete 150-row snapshot will render **24 rows** until this lands.
Our Sprint 1 acceptance test for "150 rows on `/reports`" is
explicitly conditioned on it.

### The three changes

Do them in one pass — they are the same file and each costs a
round-trip if split.

**4.1 — Import the real 150.** Canonical source is
`data/universe/nifty_midcap150.json` in the pipeline repo, generated
from the official NSE Indices CSV (committed alongside it). Fields per
company: `ticker`, `name`, `screener_slug` (pipeline-internal, ignore
it), `nse_industry`, `isin`. Regenerate from that file with a build
script — a rebalance should be a data refresh, not a code edit, which
is what your own §3 already proposed.

**4.2 — Drop `entityId`.** Owner decision 2026-07-26
(`SHARED_CONTRACT §2`, and `PIPELINE_ANSWERS` "two changes we need in
your registry"). `CompanyIdentity.entityId` is still present and still
documented as *"Stable slug, also the entity key in Supabase"* — which
is precisely the ambiguity the decision removed: on your side it is a
slug (`"sona-blw"`), on ours it is a Supabase UUID, and those are not
the same thing. **`ticker` is the sole join key.** If you want a
pretty URL, derive the slug from the ticker at render time.

**4.3 — Drop the GICS `sector`.** `SHARED_CONTRACT §3`. NSE publishes
**one** classification field (`Industry`: "Financial Services",
"Capital Goods", …). There is no source for GICS-style sectors
("Consumer Discretionary") and we will not invent a mapping nobody
maintains. So:

- `industry` = NSE Industry — available now, in the canonical file;
- `sector` = our `pack_id` once sector packs exist, since that is the
  taxonomy actually driving the analysis;
- until then **omit `sector`** rather than fabricate it.

### One correction that survives into the new list

Your registry still lists **SONACOMS** as a constituent. It is not one
— neither SONACOMS nor M&M is in the NIFTY Midcap 150. We flagged this
in `PIPELINE_ANSWERS` Q2; it matters here because regenerating from
the canonical file fixes it automatically, and hand-patching would
not.

## 5. `registryVersion` — the two repos already disagree

`SHARED_CONTRACT §3` says both repos bundle the same string and that
the snapshot's `manifest.registryVersion` is how you detect your
static list has gone stale. Right now:

| Where | Value |
|---|---|
| `build_snapshot.py:47` (pipeline) | `"2026.07"` — hardcoded |
| `data/universe/nifty_midcap150.json` (canonical) | **no such field** — only `as_of` |
| `registry/niftyMidcap150.ts:55` (frontend) | `"2026.07-seed"` |

So the first snapshot we publish would ship `2026.07` to a client
bundling `2026.07-seed` — which is exactly this field's
"your-list-is-stale" signal, fired on day one, for no reason.

**Our half:** add `"registry_version": "2026.07"` to the canonical
registry JSON and have the builder read it from there rather than from
a literal, so the field has one home. Done as part of our Sprint 1.

**Your half:** bundle `"2026.07"` — not `"2026.07-seed"` — when you
regenerate (§4.1). Bumped only on an index rebalance.

**Worth knowing:** we could not find any code on your side that
actually *compares* the two. `types.ts` documents the field as the
staleness signal but nothing reads it, so today a mismatch fails
silently instead of loudly. That is worse, not better — if you wire the
comparison, wire it before the first real publish, not after.

## 6. What you should expect when Sprint 1 lands

So the list page is not a surprise:

- **150 rows**, every registry ticker present.
- **Live market caps** for essentially all of them (last measured
  150/150), in ₹ crore, refreshed each weekday evening IST. `null`
  where unknown — **never `0`**; a zero would render as a real ₹0 cap.
- **`status: "not_initiated"` on all 150**, and `verdict:
  {"status":"coming_soon","version":0}` on all 150.

That last point is not a bug and not a transitional state we are about
to fix: **zero of the 150 tracked companies have a research report**,
and the swarm cannot yet run any company outside SONACOMS/M&M
(`PIPELINE_ANSWERS` Q3 — it is blocked on engineering, not budget).
Coverage arrives in phases: auto (~10 companies, packs exist) →
non-financial packs (~114) → financials (36, the hardest cohort).

**This is a product decision on your side too**: a page of 150 honest
"coming soon" rows is a different thing to design than a page with
content. `SHARED_CONTRACT §8` item 6 (coverage tiers in the UI) is
still open and still owed by both of us.

The **AI Verdict column stays locked** meanwhile — name *and* content
settled with the SEBI/fintech review before any unlock, per your own
compliance flag and our Q5. We emit only the neutral shape.

## 7. Sprint 2 coordination — two things, no deadline

Our next pipeline sprint rethinks the report's shape. Two items need
you, but neither blocks you:

**7.1 — We need a stable report page to audit against.** The first
step of that sprint is mapping every block type and section to what
the UI actually renders, to decide what is load-bearing and what is
dead weight. You are rebuilding the report page right now. Tell us when
it is stable enough to audit, or the audit measures a moving target and
we prune the wrong things.

**7.2 — Agree the provenance display before we implement it.** Two of
your §7 asks are ours to build and are queued:

- **Persist `calc:` values.** Today the composer resolves
  `calc:<formula_id>` but never ships the number behind it, so you can
  only render a "computed" chip where the figure belongs. Small change
  on our side.
- **Pre-computed YoY deltas**, since you are contractually forbidden
  from deriving numbers.

Related, and the reason we want to settle these together: citation
labels are `<doc-mnemonic>.<passage-index>` — `AR.47`, `CC-May26.4`.
The index is load-bearing machinery for us (it resolves to one of ~136
AR passages) but is almost certainly meaningless to a reader, who wants
"Annual Report FY26" and ideally the passage text. The document titles
**already ship** in `citation_map.documents`; they are simply not what
you are rendering.

All three are the same question — *what does provenance look like to a
human?* Answer it once and we implement once.

---

## Status

| # | Item | Owed by | State |
|---|---|---|---|
| 1 | Firestore enabled | frontend / infra | **done** — Native mode, `asia-south1` |
| 2 | Service account, Firestore write, **no key** | frontend / infra | open |
| 3 | Public-read rule on `index_snapshots/*` (scoped — `portfolios` holds personal data) | frontend / infra | open |
| 4 | Registry: real 150 + drop `entityId` + drop GICS `sector` | frontend | open — **blocks the list page** |
| 5 | Bundle `registryVersion = "2026.07"` | frontend | open |
| — | GAE gateway hop | — | **cancelled 2026-07-29** |
| 6 | Coverage tiers in the UI | both | open, no deadline |
| 7 | Stable report page for the mapping audit | frontend | open, no deadline |
| 8 | Provenance display shape (`calc:`, YoY, citation labels) | both | open, no deadline |

Pipeline-side counterparts to these live in `HANDOFF5.md` §3a and §5;
this file is the only place the frontend needs to read.
