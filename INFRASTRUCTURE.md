# INFRASTRUCTURE — topology, free-tier ceilings, measured headroom

> Written 2026-07-30. **Every quota in §3 was read from the vendor's own
> current documentation on that date**, not from memory — links are on
> each row. Quotas move; re-verify before making a decision that depends
> on a number being exact.
>
> §4 is the part that matters for architecture: measured usage against
> those ceilings, and the three places where a ceiling is close enough to
> change a plan.
>
> Companion docs: `DB_SCHEMA.md` (what the tables are),
> `DAILY_MARKET_DATA_PLAN.md` (what the daily job does),
> `HANDOFF5.md §3` (how it gets deployed),
> `ui_bridge/SHARED_CONTRACT.md` (the two data paths).

---

## 1. Topology

Four systems, three vendors, **two separate GCP projects**. The
project split is deliberate and is the thing most likely to be
mis-assumed by someone reading only the code.

```
                        ┌──────────────────────────────────────┐
   RESEARCH (manual)    │  developer machine                   │
                        │  main.py — S0..S9 swarm, paid LLM    │
                        │  ~10-20 min/company, ~$0.51-2.00     │
                        └──────────────┬───────────────────────┘
                                       │ writes
                                       ▼
                        ┌──────────────────────────────────────┐
                        │  SUPABASE (Postgres)  — free plan    │
                        │  source of truth for everything      │
                        └───────┬──────────────────────┬───────┘
                                │ reads                │ reads (~430 KB)
   ┌────────────────────────────┴──────┐               │
   │  GCP PROJECT A  (billed)          │               │
   │  region: asia-south1              │               │
   │                                   │               │
   │  Cloud Run Job (daily, ~6 min)    │               │
   │    daily_market_data.py           │               │
   │    build_snapshot.py              │               │
   │    push_snapshot.py ──────────┐   │               │
   │  Cloud Scheduler  0 18 * * 1-5│   │               │
   │  Secret Manager (supabase x2) │   │               │
   │  Artifact Registry (image)    │   │               │
   └───────────────────────────────┼───┘               │
                    cross-project  │ writes 28.6 KB    │
                                   ▼                   │
   ┌───────────────────────────────────┐               │
   │  GCP PROJECT B  (Firebase, Spark) │               │
   │  region: asia-south1              │               │
   │  Firestore (default), Native mode │               │
   │    index_snapshots/nifty_midcap_150   ← public read
   │    portfolios/{uid}  ← PERSONAL DATA, unrelated   │
   │  Firebase Auth                    │               │
   └───────────────┬───────────────────┘               │
                   │ REST read, public web API key     │
                   ▼                                   ▼
   ┌───────────────────────────────────────────────────────────┐
   │  CLOUDFLARE PAGES  (frontend repo)                        │
   │   /api/index-snapshot   → Firestore, edge-cached 30 min   │
   │   /reports/:ticker      → Supabase direct, service-role   │
   └───────────────────────────────────────────────────────────┘
```

### Why two projects, and what that costs

Project A holds billing and runs compute. Project B is the pre-existing
Firebase project: Auth, and a `portfolios/{uid}` collection holding
**personal portfolio data unrelated to this product**.

Keeping them split is the right call, for one reason that outweighs the
inconvenience: **Project B has no billing account attached**, so the
project holding personal financial data cannot run up a bill under any
circumstance, and its blast radius stays small. Consolidating would
mean attaching a payment method to that project — a downgrade.

What the split costs, all one-time:

| # | Consequence | Where |
|---|---|---|
| 1 | The Firestore client **must be passed Project B's id explicitly**. Google client libraries infer the project from the runtime environment, which on Cloud Run is *Project A*. A default `firestore.Client()` targets the wrong project — and if Project A ever gains its own Firestore, that write succeeds silently against the wrong database | `push_snapshot.py` |
| 2 | The IAM grant is **cross-project**: the service account lives in Project A, the Firestore write role is granted on Project B | Project B → IAM |
| 3 | Logs and quota live in different consoles | operational |

Same region both sides, so **no egress charge between them**.

### Credentials — no key material anywhere

The Cloud Run job runs **as** its service account and takes credentials
from the metadata server. There is **no JSON key file**, nothing in
Secret Manager for Firestore, nothing to rotate or leak.

A key would only be needed to run the job outside GCP. Locally, use
`gcloud auth application-default login` instead of downloading one.

Secret Manager holds exactly two things, both in Project A:
`SUPABASE_URL` and `SUPABASE_SERVICE_ROLE_KEY`. The service-role key is
server-side only, forever (`FOUNDATIONS §2`, `DB_SCHEMA` invariant 7).

### Firestore security rules

`index_snapshots/*` is public-read because the Cloudflare function
fetches it with the **public web API key**. `portfolios/*` is not, and
must not become so.

```
match /index_snapshots/{doc} {
  allow read: if true;
  allow write: if false;
}
```

`allow write: if false` is correct despite writing daily: the service
account authenticates server-side and **bypasses security rules
entirely**. Never widen this with `match /{document=**}`, and never use
"test mode" — both would expose `portfolios`.

Long-term, a **second Firestore database** for public content would
isolate the two by infrastructure rather than by rule discipline. It
needs a one-line change in the frontend's edge function, which
currently hardcodes `(default)`.

---

## 2. What runs where, and what triggers it

| Workload | Where | Trigger | Cadence | Cost driver |
|---|---|---|---|---|
| Research swarm (`main.py`) | developer machine | manual | per company | **paid LLM** (~$0.51 rerun / ~$1.4–2.0 fresh) |
| Daily market data + snapshot + push | Cloud Run Job, Project A | Cloud Scheduler | weekdays 18:00 IST | ~6 min compute |
| Snapshot read | Cloudflare edge → Firestore | user page load | cached 30 min | Firestore reads |
| Report detail read | Cloudflare Pages Fn → Supabase | user page load | per view | **Supabase egress** |

The swarm is **deliberately not deployed**. `FOUNDATIONS §7` lists
scheduler / multi-company automation as a standing non-goal until the
generalization plan's gates are met. It moves to Cloud Run at G1, if
ever — see §4.3.

---

## 3. Free-tier ceilings (verified 2026-07-30)

### Google Cloud — [Always Free](https://cloud.google.com/free/docs/free-cloud-features)

| Service | Free allowance | Scope |
|---|---|---|
| **Cloud Run** | 2,000,000 requests/mo · **180,000 vCPU-seconds** · **360,000 GiB-seconds** · 1 GB outbound from North America | per billing account |
| **Cloud Scheduler** | **3 jobs/month**, then $0.10/job/mo ([pricing](https://cloud.google.com/scheduler/pricing)) | **per billing account**, not per project |
| **Secret Manager** | 6 active secret versions/mo · 10,000 access operations/mo | per account |
| **Artifact Registry** | **0.5 GB storage/mo** | per account |
| **Cloud Logging** | first 50 GiB/mo | **per project** |
| **Firestore** | **1 GiB storage** · 50,000 reads/day · **20,000 writes/day** · 20,000 deletes/day · 10 GiB/mo outbound | **per project** |

**Cloud Run's free tier applies to jobs, not only services** — Google's
own [pricing examples](https://cloud.google.com/run/pricing) show a job
costing $0.00 with free tier against $0.45 without. Jobs bill
instance-based for the whole instance lifetime, minimum 1 minute.

**Cloud Run job task timeout: default 10 minutes, maximum 168 hours**
([docs](https://cloud.google.com/run/docs/configuring/task-timeout)).
The default would kill our ~6-minute job on a slow day — set it
explicitly.

⚠️ **Region restrictions are per-service, not a blanket rule.** The
Always Free page states them for exactly two services: **Cloud Storage**
(us-east1/us-west1/us-central1 only) and **Compute Engine**'s e2-micro
(Oregon / Iowa / South Carolina). Cloud Run, Cloud Scheduler, Secret
Manager and Firestore carry **no such restriction**, and we use neither
restricted service. `asia-south1` is the correct region for us — it is
where Firestore already lives (permanently: a Firestore location cannot
be changed after creation) and closest to the Indian sources the job
fetches.

### Supabase — [Free plan](https://supabase.com/pricing)

| Resource | Free allowance |
|---|---|
| **Database size** | **500 MB** (shared CPU, 500 MB RAM) |
| File storage | 1 GB |
| **Egress** | **5 GB/mo** (+ 5 GB cached) |
| Monthly active users | 50,000 |
| API requests | unlimited |
| Active projects | 2 |
| **Inactivity** | **projects suspend after 1 week of inactivity** |

Pro is $25/mo and raises the database to 8 GB.

---

## 4. Measured usage vs those ceilings

Row counts and payload sizes measured against the live database
2026-07-30. **Only two companies are researched** (SONACOMS, M&M), so
per-company figures divide by two and the 150-company projections
multiply from there.

### Current state

| Table | Rows | Measured payload |
|---|---|---|
| `report_versions` | 28 | **9.28 MB** — avg 324 KB, max 462 KB per row |
| `knowledge_entries` | 833 | ~4.7 MB (section envelopes ~9–24 KB; `extract:` ~2 KB) |
| `metric_observations` | 8,960 | small rows, index-dominated |
| `claims` | 4,393 | small |
| `evidence` | 2,284 | ~0.7 MB (avg 314 chars) |
| `entity_mentions` | 747 | |
| `source_documents` | 356 | |
| `entities` | 187 | 165 companies after `seed_universe` |
| `entity_relationships` | 50 | |
| `runs` | 47 | |

≈ **18 MB of payload**, plus Postgres tuple and index overhead.

### Headroom today

| Ceiling | Using | Headroom |
|---|---|---|
| Cloud Run 180,000 vCPU-s/mo | ~7,900 (6 min × 22 weekdays, 1 vCPU) | **96%** |
| Cloud Run 360,000 GiB-s/mo | ~4,000 (512 MiB) | **99%** |
| Cloud Scheduler 3 jobs | 1 | 2 spare |
| Secret Manager 6 versions | 2 | fine |
| Firestore 20,000 writes/day | **1** | irrelevant |
| Firestore 1 GiB storage | 28.6 KB | irrelevant |
| Supabase 500 MB DB | ~18 MB payload | large *today* — see §4.1 |
| Supabase 5 GB egress/mo | negligible | large *today* — see §4.2 |

Everything is comfortable at two companies. Two of these stop being
comfortable at 150.

### 4.1 — 🚨 The binding constraint is Supabase's 500 MB database

Projecting the measured per-company payloads to full coverage:

| | First pass (1 version each) | Each later full refresh |
|---|---|---|
| `report_versions` | 150 × ~350 KB ≈ **53 MB** | **+53 MB** (new version per company) |
| `knowledge_entries` | 150 × ~275 KB ≈ **41 MB** | **+41 MB** (new envelopes per run) |
| `evidence` | 150 × ~345 KB ≈ **52 MB** | small (deduped on doc+text) |
| `metric_observations` | ~150,000 rows ≈ **20–25 MB** | small |
| `claims` | ~30,000 rows ≈ **5 MB** | +5 MB |
| **payload** | **≈ 175 MB** → **~250 MB** with overhead | **≈ +100 MB** |

So: **initial coverage fits. Continuous updating does not.** The free
plan carries first coverage plus roughly **two full refresh cycles**
before 500 MB.

That collides with the product definition — `FOUNDATIONS §1` promises
*"one continuously-updated research report"* per company. Growth here is
by design, not waste: `report_versions` is versioned deliberately so
reports stay reconstructible, and `DB_SCHEMA` invariant 10 forbids
deleting observations.

**So Supabase Pro ($25/mo, 8 GB — ~30× headroom) is a foreseeable
planned cost at coverage, not a surprise.** Budget it alongside G1's
~$225 of LLM spend rather than discovering it when writes start failing.

**One free lever first, and it is already an open question.**
`final_report_md` is **35.4% of every stored report** — 154.8 KB of the
438 KB latest row — and it is fully derivable from the section blocks by
the composer. `PIPELINE_BACKLOG §1` already asks whether it "becomes a
by-product"; the answer is worth ~18 MB per coverage pass and ~35% of
every future refresh. Second-largest is `citation_map` at 33.4 KB
(7.6%), which is load-bearing and stays.

### 4.2 — ⚠️ Supabase egress becomes the snapshot builder's problem at coverage

`build_snapshot.py` avoids bulk-fetching `sections_json` and hydrates
only the winning row per company. **At full coverage the winning set
*is* 150 rows** — so the daily build pulls 150 × ~430 KB ≈ **64 MB per
run, ~1.4 GB/month: about 28% of the free 5 GB egress**, for two
fields.

The builder's own docstring names the fix as a "cleaner future fix":
have the composer persist **`has_open_flags` alongside `quality`**, so
the snapshot never needs the blocks at all. These numbers upgrade that
from cosmetic to **a requirement before G1**, and it is a small composer
change.

Also on this ceiling: the report-detail page reads ~430 KB from Supabase
per view. 5 GB/mo ÷ 430 KB ≈ **~11,600 report views/month** before
egress runs out — a real product ceiling worth knowing before any
launch, and another argument for trimming `final_report_md`.

### 4.3 — If the swarm is ever deployed, it eats a month of Cloud Run in one pass

G1 bulk coverage is ~149 runs × ~20 min ≈ **50 hours ≈ 180,000
vCPU-seconds at 1 vCPU — essentially 100% of the monthly free
allowance** in a single pass. Overflow is only a few dollars, so this is
a note, not an obstacle.

The real point stands: **hosting the agent is noise; the LLM bill is the
cost** (~$225 for G1 vs single-digit dollars of compute). The pipeline
spends nearly all its wall time waiting on API responses, so it is
cheap to host and expensive to run.

### 4.4 — Two smaller ones worth knowing

**Artifact Registry, 0.5 GB, is the most likely first non-zero line.**
Our image is Python plus `langgraph`, `supabase`, `google-genai`,
`ddgs`, `trafilatura`, `pypdf`, `beautifulsoup4`. A few accumulated
versions will cross 0.5 GB. Cents, but it is what will trip a budget
alert first — set an image cleanup policy at deploy time and measure
the real size after the first build.

**The daily job and Supabase keep each other alive, circularly.**
Supabase free projects suspend after **1 week of inactivity**; our
weekday job is what prevents that. If the job dies quietly for over a
week, Supabase suspends, and a suspended project needs manual restore —
so the outage compounds instead of self-healing. This is the concrete
reason `HANDOFF5 §3b.5` requires a **failure alert**, and why "a
scheduled job that fails quietly is worse than no scheduled job" is
literal here.

---

## 5. Corrections to folklore

Both of these were believed on this project and are wrong.

**A GCP budget does not cap or freeze anything.** It is a notification.
Services keep running and spend keeps accruing past the threshold; the
reporting also lags. There is no spend-cap feature. Halting spend
requires building budget → Pub/Sub → a function that detaches the
billing account, which is blunt and takes everything down.

For this workload the effective safeguard is the **Cloud Run task
timeout** (default 10 min, set it explicitly) with retries bounded — a
hung job then dies on its own instead of billing for hours. That is one
field, and it beats any alert.

**"Free tiers don't apply to Indian regions" is false as a general
rule.** It is true for Cloud Storage and Compute Engine's e2-micro, both
of which we do not use. It is not true for Cloud Run, Cloud Scheduler,
Secret Manager or Firestore. Moving compute to a US region to chase a
non-existent benefit would put Cloud Run a continent away from
Firestore and from the Indian data sources — adding latency and
cross-region traffic to avoid a restriction that does not apply.

**On credits vs free tier:** free-tier usage records no cost at all,
whereas the ₹1,000 activation credit *offsets recorded charges*. If a
budget is configured to track **net** cost, spend drawn from that credit
shows as ₹0 and never trips the alert — draining the credit silently.
Track **gross** cost so the alert fires on real usage.

---

## 6. Decisions this document is meant to inform

| Question | What the numbers say |
|---|---|
| Can we deploy the daily job free? | **Yes** — ~4% of Cloud Run's free CPU. Free tier applies to jobs, and to `asia-south1` |
| Do we need Supabase Pro? | **Not yet; yes at coverage.** Free plan carries first coverage + ~2 refreshes. Plan $25/mo alongside G1 |
| Cheapest storage win available? | **Drop `final_report_md`** from `sections_json` — 35.4% of every report, fully derivable (`PIPELINE_BACKLOG §1`) |
| Anything that must land before G1? | **`has_open_flags` in `sections_json`** — otherwise the daily snapshot build spends ~1.4 GB/mo of Supabase egress (§4.2) |
| Where should the swarm run? | Developer machine, until G1. It is a non-goal by standing decision, and hosting was never the cost |
| Should the two GCP projects merge? | **No.** The split keeps billing off the project holding personal data. Costs three one-time items (§1) |
| How do we bound runaway spend? | Cloud Run task timeout, not a budget alert (§5) |

Sources: [GCP Always Free](https://cloud.google.com/free/docs/free-cloud-features) · [Cloud Run pricing](https://cloud.google.com/run/pricing) · [Cloud Scheduler pricing](https://cloud.google.com/scheduler/pricing) · [Cloud Run task timeout](https://cloud.google.com/run/docs/configuring/task-timeout) · [Supabase pricing](https://supabase.com/pricing)
