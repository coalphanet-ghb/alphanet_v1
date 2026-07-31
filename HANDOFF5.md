# HANDOFF 5 — the product era: two sprints (2026-07-27, restructured 2026-07-29)

> For the next assistant session(s). The pipeline is validated and the
> UI era has started. This doc carries **two sprint plans meant to be
> executed in separate chats**, each now in three parts —
> **prerequisites → the work → testing**:
>
> - **SPRINT 1 — ship the list page** (§3a/§3b/§3c): Firestore
>   transport, Cloud Run job, scheduler. Mechanical and mostly infra,
>   but *not* unblocked — §3a is real and some of it is owed by the
>   other repo, so read it first.
> - **SPRINT 2 — the pipeline rethink** (§5a/§5b/§5c): report shape,
>   verifier economics, spec rewrites. Exploratory, evidence-first.
>
> They stay independent: Sprint 2 touches no deployment, and Sprint 1
> touches research code in exactly **one** bounded place, called out as
> such (§3a.3). Either can go first; Sprint 1 is smaller and makes
> something visible.
>
> **Read §2b before planning either.** After the 2026-07-29 audit it
> lists exactly one unassigned thing — **G1**, without which the list
> page stays empty no matter how Sprint 1 goes — plus a ledger of where
> everything that used to sit beside it now lives.
>
> **`HANDOFF4.md` remains the authority on the pipeline itself** — how
> it runs, the retry policy, the cost model, the watch list. Read it
> before changing anything inside `src/pipeline/`. This file does not
> repeat it.

---

## 1. Reading order

1. **This file** — §2b (what is still unowned), then your sprint's
   three parts in order (§3a→3b→3c or §5a→5b→5c), then **§8**, which
   records what the 2026-07-29 audit verified in code, what it deleted,
   and why — read it before re-adding anything that looks missing.
2. **`HANDOFF4.md`** — the pipeline: architecture, gates, retry policy,
   cost model, open watch list.
3. **`FOUNDATIONS.md`** — timeless layer: product identity, the
   no-Buy/Sell/Hold rule, settled decisions with rationale (including
   the blocks-vs-claims duality), compliance risks.
4. **`ui_bridge/SHARED_CONTRACT.md`** — the cross-repo contract. Join
   key, registry, snapshot payload, casing boundary, who owes what.
   **Anything crossing the repo boundary is settled here first.**
5. **`ui_bridge/FRONTEND_TASKS.md`** — everything we need FROM the
   frontend, with the measurements behind each ask. Skim it so you know
   what is blocked on them; **do not duplicate it into this file.**
   (`ui_bridge/PIPELINE_TASKS.md` is the reverse direction — their asks
   of us — and `PIPELINE_ANSWERS.md` is our dated reply to it.)
6. **`DAILY_MARKET_DATA_PLAN.md`** — what Sprint 1 deploys, and why it
   is built the way it is.
6b. **`INFRASTRUCTURE.md`** — **read before Sprint 1 §3b.5 or any cost
   decision.** Deployment topology (two GCP projects, regions,
   credentials), every free-tier ceiling verified from vendor docs
   2026-07-30, and measured headroom. Its §4 names the two constraints
   that bind at coverage and the two cheapest ways out.
7. **`PIPELINE_BACKLOG.md`** — the raw material for Sprint 2.
8. `DB_SCHEMA.md` before touching persistence; `GENERALIZATION_PLAN.md`
   for the coverage problem in §4.

## 2. Where things stand (2026-07-27)

**Pipeline: healthy.** SONA v23 — $0.51, 0 spirals, **507/507 citations
(0.0% unresolved, a project first)**, `diff_golden` clean vs v22.
Goldens: SONA v22 (frozen), M&M v5.

**Built and working this session, all zero-LLM:**

| Piece | State |
|---|---|
| `data/universe/nifty_midcap150.json` | canonical 150 from the official NSE CSV |
| `scripts/seed_universe.py` | 165 company entities, ticker-first, zero duplicates, idempotent |
| `scripts/daily_market_data.py` | **150/150 close + market cap live in Supabase**, idempotent, self-dating |
| `scripts/build_snapshot.py` | correct 28.6 KB payload, version discipline proven |
| `db.get_metric_observations` | paginated (was 12 rows from silent truncation) |
| `db.get_entity_by_ticker` | the only sanctioned company resolver |

**Not done:** nothing is transported to Firestore, so the frontend
still sees nothing. That is Sprint 1.

## 2b. CARRIED FORWARD — what genuinely belongs to neither sprint

This section used to hold four items. The 2026-07-29 audit (§8) found
homes for three of them, because "carried forward, unassigned" is
exactly how AR optimisation got skipped the first time. **One thing
remains unowned:**

### GENERALIZATION_PLAN G1 — the thing that makes the product non-empty

§4 below explains the coverage problem, but nobody owns fixing it. G1
(universe-driven onboarding + a `generic_default` pack) is what lets
the swarm run a company that is not SONACOMS or M&M. **Until it lands
the list page renders 150 empty rows forever**, however well Sprint 1
goes. Arguably deserves to be its own sprint. Detail:
`GENERALIZATION_PLAN.md`.

Note that G1 is also what makes §3a.3 (ticker-first entity resolution)
*urgent* rather than theoretical — the duplicate-entity failure it
prevents cannot occur until the swarm runs a real constituent, and
becomes near-certain the moment it does. Sprint 1 closes it first
precisely so G1 does not have to discover it as data corruption.

### Where the other three went

| Was here | Now | Why it moved |
|---|---|---|
| AR optimisation | **§5b.7** | orthogonal to the shape work, but Sprint 2 is the only sprint touching research code, and leaving it unassigned is what caused it to be skipped once already |
| Two frontend asks (`calc:` values, YoY deltas) | **§5b.1** | both are "what does provenance look like to a reader", i.e. the same question §5a.1 answers — decide once, implement once |
| Rating-rationale wrong-entity bug | **§5b.2** | research-code fix; contract §8 item 8; must land before any credit surface |

---

## 3. SPRINT 1 — ship the list page

**Goal:** the `/reports` list renders live, daily-refreshed data with
nobody running commands.

Everything upstream is built and verified; what remains is transport,
automation, and the prerequisites below — three of which are owed by
the other repo and therefore have lead time.

---

### 3a. PREREQUISITES

Split by who does the work. **Everything owed by the frontend has been
moved out of this file** — it lives in `ui_bridge/FRONTEND_TASKS.md`,
which is the only document that repo needs to read. Do not re-describe
their work here; it drifts.

#### Owed by the frontend / infra → `ui_bridge/FRONTEND_TASKS.md`

| # | Item | Effect on us |
|---|---|---|
| F1 | ~~Firestore enabled~~ — **DONE**: `(default)`, Native mode, `asia-south1` | — |
| F2 | Service account with Firestore write, granted **on the Firebase project** — **no JSON key** | cannot authenticate |
| F3 | Public-read rule on `index_snapshots/*` | their edge function's read 503s |
| F4 | Registry regenerated from the canonical 150 (+ drop `entityId` and the GICS `sector`) | **blocks §3c test X1** — `merge.ts` iterates the registry, so a correct 150-row snapshot renders 24 until this lands |
| F5 | Bundle `registryVersion = "2026.07"` | otherwise the staleness signal fires on day one |

F1 is done. **F2 and F3 are the only real blockers**, both console work.
F4 has no effect on the bytes we publish — only on what renders — so
§3b is not blocked on it, but §3c test X1 is.

**On F2 — no key material anywhere, and the grant is cross-project.**
Firestore lives in the **Firebase project**, which has no billing
account; Cloud Run lives in a **different, billed project**. So the
service account is created in the Cloud Run project and granted
Firestore write **on the Firebase project**. It needs **no JSON key** —
the job runs *as* that account and takes credentials from the metadata
server, so Secret Manager holds only the two Supabase values. Topology,
rationale, and the three one-time costs of the split:
`INFRASTRUCTURE.md §1`.

⚠️ **`push_snapshot.py` must pass the Firebase project id explicitly.**
Google client libraries infer the project from the runtime, which on
Cloud Run is the *wrong* one. A default `firestore.Client()` targets the
Cloud Run project — and if that project ever gains its own Firestore,
the write succeeds **silently against the wrong database**.

**On F3 — this is no longer an empty database.** The Firebase project
also holds `portfolios/{uid}`: real personal portfolio data, unrelated
to this product. The rule must be scoped to `index_snapshots` by name
and added *alongside* what exists — never `match /{document=**}`, never
"test mode". `allow write: if false` is correct, because the F2 service
account bypasses security rules entirely.

#### Owed by us

| # | Item |
|---|---|
| 1 | **`registryVersion` becomes data, not a literal** |
| 2 | **Commit the pipeline work** |
| 3 | **Ticker-first entity resolution in the research path** |

**1 — this is a fix, not a confirmation.** Contract §3 names
`data/universe/nifty_midcap150.json` as canonical, but that file
carries no `registryVersion` field at all (only `as_of`), and the
string is hardcoded at `build_snapshot.py:47`. Add
`"registry_version": "2026.07"` to the registry JSON and have the
builder read it from there, so the field has exactly one home. The
frontend's half of this is F5; the drift it prevents is written up in
`FRONTEND_TASKS.md` §5.

**2 — a Cloud Run image built from this repo today ships nothing.**
`scripts/build_snapshot.py`, `scripts/daily_market_data.py`,
`scripts/seed_universe.py`, `src/ingestion/market_data.py`,
`ui_bridge/SHARED_CONTRACT.md`, `ui_bridge/PIPELINE_ANSWERS.md`,
`HANDOFF5.md`, `PIPELINE_BACKLOG.md` and now
`ui_bridge/FRONTEND_TASKS.md` are all untracked; `src/db.py` (the
pagination fix) is modified-unstaged. Containerisation is step §3b.4 —
this has to be true before it.

**3 — close the duplicate-ticker hole at its source.** `main.py:91` and
`s0_resolve.py:52` still resolve the run company with
`get_or_create_entity(name, "company")`, which dedups on `(name, type)`
— the exact thing SHARED_CONTRACT §2 forbids and `seed_universe.py`
was written to avoid. It cannot bite today (neither pilot is a
constituent). It bites the first time G1 runs one whose config name is
not byte-identical to the seeded NSE name — the "Bharat Forge" vs
"Bharat Forge Ltd." class, 6 known cases — creating a second entity
carrying the **same ticker**, after which `get_entity_by_ticker`'s
`.limit(1)` returns an arbitrary one of the two and that company shows
`not_initiated` with a null cap forever.
Fix: resolve by ticker → fall back to exact name → then create, and
enrich metadata explicitly (`get_or_create_entity` writes metadata
**only on insert**, which is why `seed_universe.py` does its own
update).
**This is the one place Sprint 1 crosses into research code,
deliberately — and it needs no live run to prove.** Both pilots are
seeded with their tickers in `metadata` and with names identical to
`config.COMPANIES`, so the entire gate is a five-line script asserting
that ticker-resolution and name-resolution return the *same* entity id
for SONACOMS and M&M. Same id ⇒ behaviour provably unchanged ⇒ no
`diff_golden` cycle owed.

**❌ DELETED from this list — do not re-add.** The old §1.1 item 4,
"confirm the GAE hop is dropped" (contract §8 item 2), is answered by
code that already exists on the frontend side. There is nothing to
confirm and nobody to ask. Struck from the contract, and written up for
the frontend as "do not build it" in `FRONTEND_TASKS.md` §3.

---

### 3b. SPRINT 1 — the work

**1. Firestore transport.** New `scripts/push_snapshot.py` (or a
`--push` flag on the builder). Writes the payload as **one JSON
string** into the single field `payload` of
`index_snapshots/nifty_midcap_150` — not nested Firestore fields,
because the edge function returns `doc.fields.payload.stringValue`
verbatim (contract §5).

**2. Fail loudly on a duplicate ticker.** `build_snapshot.py:179`
builds `by_ticker` as a dict comprehension over every company entity —
**last write wins, silently** — so a duplicated ticker would join one
entity's report to another entity's market cap and publish it.
`seed_universe.py` gates this, but only when seeding; the snapshot
builds daily. ~4 lines, in a file this sprint already edits. (§3a.3
stops duplicates being *created*; this stops one being *shipped* if it
ever is.)

**3. Age-bound the `updating` status.** `_running()` trusts
`runs.status='running'` with no time filter, so a hard-killed run
(Cloud Run preemption, power loss — `main.py`'s `_mark_failed` covers
only the graceful aborts) pins that company at "updating" in the UI
indefinitely. Treat a run older than ~6 h as not running. Two lines,
and included **only** because we are already inside this function.

**4. Containerise.** One image, one entrypoint, three steps in order:

```
daily_market_data.py  →  build_snapshot.py  →  push_snapshot.py
```

The ordering is the contract's (§5.4: the snapshot writes *after* the
market-cap job). Non-zero exit anywhere aborts the rest — a snapshot
built on a failed fetch would quietly publish stale caps.

**5. Cloud Run Job + Cloud Scheduler.** Quotas, headroom and the
reasoning behind each choice: `INFRASTRUCTURE.md §3–§4`.
- **Cloud Run Job**, not GCE: batch-shaped, no idle cost, and outbound
  internet works out of the box. Measured at ~4% of the free monthly
  vCPU allowance, and the free tier **does** apply to jobs.
- **Region `asia-south1`** — same as Firestore, which is permanent and
  cannot be moved. Do **not** relocate to a US region chasing a free
  tier that isn't region-restricted for any service we use
  (`INFRASTRUCTURE.md §5`).
- ⚠️ **Set the task timeout explicitly.** The default is **10 minutes**,
  which would kill our ~6-minute job on a slow day; the maximum is 168 h.
  Use ~30 min with retries bounded. **This, not a budget alert, is the
  runaway-spend safeguard** — a GCP budget only notifies, it never caps.
- **Cloud Scheduler** → `0 18 * * 1-5`, TZ `Asia/Kolkata` (post-close).
  Retries are safe: every step is idempotent by construction. 3 jobs are
  free **per billing account**; we need 1.
- **Secret Manager** for `SUPABASE_URL` and `SUPABASE_SERVICE_ROLE_KEY`
  only — the Firebase service account needs **no stored key** (§3a F2).
- **Artifact Registry cleanup policy** at deploy time. 0.5 GB is free
  and our image is Python plus nine dependencies, so accumulated
  versions are the most likely first non-zero charge.
- **Alert on failure.** A scheduled job that fails quietly is worse than
  no scheduled job — and here it compounds: Supabase free projects
  **suspend after 1 week of inactivity**, and this job is what keeps ours
  alive. A silent outage past a week means a suspended database needing
  manual restore (`INFRASTRUCTURE.md §4.4`).

**6. One documentation line.** `daily_market_data.py` carries an
intraday guard (`--allow-intraday`; it refuses a close dated *today*
before 15:40 IST, because append-only means a half-day price could
never be corrected) that `DAILY_MARKET_DATA_PLAN §5`'s flag list does
not mention — nor `--delay`. The 18:00 IST schedule clears it, but a
human running §3c tests in the afternoon will hit exit 2 and read a
working guard as a broken job.

**Deferred inside Sprint 1** (unchanged): the contract names a
**second** snapshot trigger, *on report publish*. While reports are
rare the daily rebuild is sufficient. When the swarm starts producing
them, add a post-run rebuild.

---

### 3c. TESTING SPRINT 1

| # | Test | Pass |
|---|---|---|
| 1 | `gcloud run jobs execute <job> --wait` | exit 0; log ends with the `[daily] …` and `[snapshot] …` summary lines |
| 2 | Execute again immediately | `0 newly inserted (already up to date)` and `(unchanged — version held)` — idempotency proven in the cloud |
| 3 | Execute with `--min-coverage 1.01` | **exit 1** — proves the failure path actually fails (verified: coverage can never reach 1.01, so this always fires) |
| 4 | `gcloud scheduler jobs run <sched>` | forces an immediate run |
| 5 | Byte length of the Firestore `payload` == what the builder wrote, and `GET /api/index-snapshot` returns the same bytes | the transport is verbatim, not re-encoded or nested |
| 6 | Next trading day, query `metric_observations` for the new date | ~300 rows appear unattended — the real end-to-end proof |
| 7 | Duplicate-ticker guard (§3b.2) | a scratch entity sharing an existing ticker makes the builder exit non-zero instead of silently choosing one |
| 8 | Entity-resolution gate (§3a.3) | SONACOMS and M&M resolve to the **same** entity id by ticker and by name |

Tests 1–8 are ours and need nothing from the frontend beyond F1–F3.
**Two further tests are cross-repo** and cannot pass until
`FRONTEND_TASKS.md` F4/F5 land — track them, but do not treat them as
Sprint 1 being incomplete on our side:

| # | Test | Pass |
|---|---|---|
| X1 | Frontend loads `/reports` | 150 rows, live caps, "coming soon" verdict badges. Against today's 24-name seed this legitimately renders **24** — that is F4 outstanding, not a snapshot defect |
| X2 | `registryVersion` in the served payload == the string the frontend bundles | the staleness signal is not self-firing on day one (F5) |

⚠️ **Tests 1/2/4 run before 15:40 IST will exit 2** on the intraday
guard. That is the guard working, not a failure. `--allow-intraday`
overrides it and writes a permanent row — use it only deliberately.

---

## 4. The coverage problem — read before planning either sprint

🚨 **Zero of the 150 tracked companies have a report.** SONACOMS and
M&M — the only two companies the swarm can run — are **not NIFTY
Midcap 150 constituents** (the frontend's `PIPELINE_TASKS §2` believed
SONACOMS was; it is not). So after Sprint 1 the list page will render
150 rows of live market caps and 150 "coming soon" badges, which is
honest but empty.

Filling it is blocked on **`GENERALIZATION_PLAN.md` G1**, not on
budget: `config.COMPANIES` holds only the two pilots, and `load_pack()`
*raises* for any sector without a pack (3 exist, covering ~10 of 150).
Once G1 lands, coverage costs ~$1.5/company ≈ **$225** and ~50 hours
sequential.

**This is a product decision, not an engineering one**, and it belongs
to the owner: ship the empty-but-honest list first, or hold the UI
until some coverage exists. Whichever, note that `M&MFIN` **is** a
constituent and is a poor first subject until the rating-rationale
wrong-entity bug (HANDOFF4 §6.1) is fixed — that bug involves this
exact company.

---

## 5. SPRINT 2 — the pipeline rethink

**Source material: `PIPELINE_BACKLOG.md`** (written 2026-07-27, with
what is already built vs the real gaps marked **[verified]** or
**[owner suggestion]**). Read it before planning; it is deliberately
not summarised away here.

---

### 5a. PREREQUISITES

**1. The UI mapping exercise — evidence, not code.** Map every block
type and section to what the UI actually renders. Output: which blocks
are load-bearing, which are dead weight, and what a citation should
look like to a human. **Everything in §5b that is not marked
"independent" should be decided from this evidence**; deciding the
report's shape before it exists is guessing. This is also the audit
that was always going to drive the next pruning round (HANDOFF4 §7.2)
— the report is still too big.

It must settle **two questions in one pass**, because they are the same
question — *what does provenance look like to a reader?* — and
answering them separately means implementing twice:

- **Does the `.47` in `AR.47` matter to anyone?** The index is
  load-bearing machinery (it resolves a citation to one of 136 AR
  passages via `citation_map`) and must stay, but it is almost
  certainly meaningless to a reader, who wants "Annual Report FY26" and
  the passage text. The titles already ship — they are in
  `citation_map.documents` — so the open question is only what the UI
  renders *in the marker's place*.
- **What does a computed number's provenance look like?** This is the
  frontend's `calc:` ask (§5b.1). Today the composer *resolves*
  `calc:<formula_id>` but never ships the number behind it, so the UI
  can only render a "computed" chip where the figure belongs.

⚠️ The exercise needs a stable target: the frontend is rebuilding the
report page **right now**. Agree what it renders before auditing
against it, or the audit measures a moving object. That ask, and the
"agree the provenance display before we implement it" ask behind
§5b.1, are written up for them in `ui_bridge/FRONTEND_TASKS.md` §7 —
neither blocks their work, so raise them early rather than at the
point of need.

**2. A one-minute doc fix, in passing.** `HANDOFF4 §6`'s watch list has
**two items numbered 7 and two numbered 8** (the 2026-07-26 additions
restarted the count). `SHARED_CONTRACT §4` and
`DAILY_MARKET_DATA_PLAN` L3/L5 both cross-reference "§6.7"/"§6.8" and
each currently resolves to two different items. Not a work item — just
do not leave it, since this sprint reads §6 anyway.

---

### 5b. SPRINT 2 — the work

#### Independent of the mapping evidence — can land any time

**1. Persist `calc:` values and ship YoY deltas pre-computed.**
Contract §8 item 7; both improve the report page the frontend is
rebuilding now. Assessed as a small composer change, no schema change.
The Key Ratios tiles want "ROE 18.6% · YoY +180 bps", and the frontend
is contractually forbidden from deriving numbers (rule 2) — so either
we emit the delta or the tiles show a bare value. **Implement the
display shape §5a.1 settled, not a guess.**

**2. Rating-rationale wrong-entity gate.** `HANDOFF4 §6.1` (top watch
item), contract §8 item 8. Confirmed at source: the `rating_rationale`
branch in `s1_discover.py:293` filters only for **distinct domains** —
there is no identity check and no recency check anywhere on this path —
so `"{company} credit rating rationale icra OR crisil OR care"` with
`{company} = "Mahindra & Mahindra"` happily returns a **Mahindra &
Mahindra *Financial Services*** bond page and a **30-09-2019** CRISIL
rationale, and both were ingested as M&M evidence on v5. Wrong-entity
evidence is worse than missing evidence, and this is exactly the class
the deterministic spine guards elsewhere (the wisesheets "M&M.NS →
Macy's" precedent). Needs an identity + recency gate in s1.
Orthogonal to everything else here — land it alone. Note `M&MFIN` is
itself a Midcap 150 constituent, so this also unblocks it as a demo
subject (§4).

**1b. Persist `has_open_flags` alongside `quality` in `sections_json`.**
Composer change, ~3 lines, and **it is a requirement before G1, not a
nicety.** `build_snapshot.py` deliberately avoids bulk-fetching
`sections_json`, but it must hydrate the winning row per company to
derive `hasOpenFlags` — and at full coverage the winning set *is* 150
rows, so the daily build would pull ~64 MB, **~1.4 GB/month ≈ 28% of
Supabase's free 5 GB egress, for two fields**. The builder's own
docstring already names this fix as "cleaner future"; the measurement in
`INFRASTRUCTURE.md §4.2` makes it load-bearing. Once it lands, the
snapshot never reads report blocks at all.

**3. Make unresolvable claim citations visible.** `HANDOFF4 §6.4`:
21–28% of emitted claims cite `calc:`/`sec:`, get silently dropped at
persist (`s4_synth.py:338`) and are never verified. `validate_envelope`
does not catch it — it checks `evidence_ids` is a *list*, not that its
entries resolve. Cheapest real fix on the board: a resolution check in
the validator so the count lands in `schema_issues`, plus a contract
line for I/J (whose support genuinely *is* mostly calc/sec — the fix is
"don't emit claims you can't back", not "find more claims"). **Do this
before 5, not after:** it is the measurement the verifier work needs.

#### Decided from the mapping evidence

**4. Prove the style change on ONE section.** Owner's refined
direction: synthesis stays the primary producer; only its *output
style* changes — **terse, properly-ordered bullet points per section**
instead of explanatory paragraphs, because bullets are what the UI
renders. No schema revolution (blocks stay blocks), the claims layer is
untouched, and the saving lands on the *expensive* side — prose is
output tokens at ~4× input pricing. Do **one** section (F or D1) and
read it side by side against the current output.
**Carry the scar tissue:** rule 9 ("reason briefly") once produced a
section with zero claims and zero insufficiencies because the model
economised on the envelope itself. Rule 9 now says so explicitly
(`specs.py:98-101`: *"Brevity applies to your REASONING ONLY… A thin
envelope is a defect, not efficiency"*) — any new style instruction
must repeat that guard verbatim in spirit.

**5. Verifier design review.** It is the **most expensive node in a
run** and a product feature by standing decision, so the question is
efficiency and design, never whether to keep coverage. Sharpest idea on
the table: **calc-backed claims get a deterministic check** — compare
the asserted number against the computed table — both cheaper and
stronger than an LLM pass, and it rescues the class item 3 makes
visible. Re-assert the **8–20 claims-per-section ceiling** here too
(`HANDOFF4 §6.3`: v5 hit C 29, E 29, F 25) — it is the contract line,
not one spec, and every claim is a verifier task, so a section drifting
to 30 is a cost event.

**6. Spec rewrites — the implementation surface.** If 4 changes the
output shape, every `nodes/*/spec.md`, the `ENVELOPE_CONTRACT` and the
sector-pack overlays are written for the wrong deliverable. **The specs
ARE the prompts** (`src/specs.py` parses them at runtime), so this is a
behaviour change per node, each needing its own `diff_golden` cycle.
Easy to underestimate.

#### Orthogonal — but this is the only sprint that touches research code

**7. AR optimisation.** `HANDOFF4 §7.2`, and the declared next item
before the UI era forked away from it. Numbers to beat, from M&M v4's
fresh run: **9 calls for 5 bundles** (3 truncations + 2 unparseable),
**$1.95 = 72% of run cost**, 1054 s = 39% of wall, **`growth_outlook`
lost entirely**. Confirmed at source (`s2_extract.py:367`): each bundle
gets ONE shared reprompt budget spanning both failure modes, and the
"be MUCH terser" retry only fires *after* a wasted 64K generation — so
a bundle that truncates twice is skipped. Not a size problem: SONA's AR
prefix is *larger* (286K vs 268K cached tokens) and runs 5/5 clean in 5
calls at $0.88. It is conglomerate breadth. Likely direction: start the
wide bundles terse rather than paying a truncation first, or split
`growth_outlook`.
**Why it is in a sprint rather than carried forward:** it was carried
forward once and got skipped. It is ~70% of a *fresh* run, G1 means
~149 fresh runs, and this is precisely where the ~$225 index-coverage
estimate lives. **Owner call to move it back out** if Sprint 2 is
already too big — but then give it an owner, not a backlog.

---

### 5c. TESTING SPRINT 2

**The discipline first: one behaviour change, one `diff_golden`.** A
reuse run is ~$0.53; only item 7 needs a fresh run (~$1.4–2.0).
Batching two changes into one run makes a regression unattributable —
this is why D0.1 was made to land alone.

| Thread | Gate |
|---|---|
| 5b.1 `calc:` + YoY | deterministic: the rendered figure must equal the computed table's value for that `formula_id`. No live run needed beyond one composer pass |
| 5b.2 rating gate | **verify with the exact failing case** (FOUNDATIONS §5.3): re-run M&M discovery and assert the GoldenPi M&M-*Financial-Services* page and the 30-09-2019 CRISIL rationale are both rejected — **and** that SONA's one legitimate rating doc still passes. A gate that rejects everything is not a fix |
| 5b.3 validator | `schema_issues` now reports unresolvable claim citations, at a count near the measured 21–28%. **Zero means the check is not firing**, not that the problem is gone |
| 5b.4 style | the real gate is an owner **read**, side by side — not a metric. The automatable half is the scar tissue as a test: section claim counts and insufficiency counts must not drop, and `schema_issues` must stay `{}` |
| 5b.5 verifier | not-fully-supported stays inside the historical 6–16% band; every deterministic calc check agrees with the computed table; verifier cost per run falls rather than rises |
| 5b.6 specs | `diff_golden` per node, plus the run-level gates from `HANDOFF4 §3`: `[synth_X] N claim citation(s) did not resolve` **expects 0**, `[s8] envelope contract violation(s)` expects none, composer citations ≥98% |
| 5b.7 AR | a **fresh** run (`--reingest`) measured against M&M v4: 9 calls / 5 bundles, $1.95, 1054 s, 54 AR passages. Pass = **5/5 bundles landed AND cost down**. A cost win that halves passage yield is not a win — the terser reprompt already does that (54 vs SONA's 136) |

---

## 6. How to run what exists

```powershell
# daily market data (zero LLM, ~6 min, idempotent)
.venv\Scripts\python.exe scripts\daily_market_data.py --dry-run --limit 5
.venv\Scripts\python.exe scripts\daily_market_data.py

# the snapshot (zero LLM, seconds)
.venv\Scripts\python.exe scripts\build_snapshot.py --dry-run
.venv\Scripts\python.exe scripts\build_snapshot.py

# entities for a universe (idempotent, ticker-first)
.venv\Scripts\python.exe scripts\seed_universe.py --dry-run

# the research pipeline (paid) — see HANDOFF4 §3
.venv\Scripts\python.exe -u main.py --ticker SONACOMS --model M3
.venv\Scripts\python.exe scripts\diff_golden.py SONACOMS
```

Always `.venv\Scripts\python.exe` — bare `python` lacks langgraph.

## 7. Bootstrap for the new session

**For Sprint 1:**
> Read HANDOFF5.md §3a/§3b/§3c and §8, then
> ui_bridge/SHARED_CONTRACT.md and DAILY_MARKET_DATA_PLAN.md. We are
> deploying the daily market-data + snapshot job to GCP and wiring the
> Firestore transport. Start with §3a: F1–F5 are the frontend's and
> already written up in ui_bridge/FRONTEND_TASKS.md — tell me which of
> them you need from me and when, do not re-plan their work. Items 1–3
> are yours and can start immediately. Do not re-open anything §8
> records as deleted.

**For Sprint 2:**
> Read HANDOFF5.md §5a/§5b/§5c, then PIPELINE_BACKLOG.md in full, then
> HANDOFF4.md §6 (watch list) and §7. We are rethinking the report's
> shape. Start with the UI mapping exercise (§5a.1) — do not propose
> changes to synthesis before that evidence exists. §5b.1–3 are
> independent of it and can land in parallel; one behaviour change per
> `diff_golden` (§5c).

## 8. Audit record — 2026-07-29

The restructuring above came from a full read of the docs against the
code. What follows is the part that is not visible in the plans: what
was **verified**, what was **deleted**, and what was **judged not worth
doing**. A future session should read this before "fixing" something
that was already looked at.

### Verified in code (claims in the docs that hold)

- `--min-coverage 1.01` really does force exit 1 (§3c test 3) —
  coverage is a ratio ≤ 1.0, so the failure path always fires.
- The daily job's date discipline, identity guards, standalone
  fallback, ampersand handling and `rows submitted / newly inserted`
  reporting are all as `DAILY_MARKET_DATA_PLAN` describes.
- `build_snapshot.py`'s `marketDataDate` coverage rule, null-never-zero
  handling, two-step report hydration and version-hold are as
  documented.
- The citation-integrity spine is real and layered exactly as
  FOUNDATIONS §2 claims: label→uuid resolution in `s4_synth.run_section`
  *before* persist, pool-membership check there, uuid existence check in
  `db.save_claims`, and a separate resolution pass in the composer.

### Deleted (do not re-add)

| Item | Why |
|---|---|
| "Confirm the GAE hop is dropped" (old §1.1.4, contract §8 item 2) | answered by existing code on the frontend side. Nothing to confirm, nobody to ask. Struck from the contract; `FRONTEND_TASKS.md` §3 tells them not to build it |
| "Confirm `registryVersion = 2026.07`" as a *confirmation* | it is a live mismatch, not an open question — split into a concrete fix on each side (§3a.1 here, F5 there) |
| `entityId` / GICS `sector` as separate frontend asks | folded into F4; they are edits to the same file in the same pass |
| **All frontend work, from this file entirely** | it now lives in `ui_bridge/FRONTEND_TASKS.md`. §3a keeps a five-row F1–F5 summary of what we are *blocked on* and nothing more. Describing their work in two places is how the repos drift — which is the failure mode `SHARED_CONTRACT.md` exists to prevent |

### Considered and deliberately NOT made work items

- **`HANDOFF4 §6`'s duplicated watch-list numbering** (two 7s, two 8s,
  cross-referenced by two other docs). Real but one minute — §5a.2 says
  fix it in passing, not schedule it.
- **`_count_at()` in the daily job counts rows table-wide** for the
  date, so a concurrent research run would skew the "newly inserted"
  number. The count is a log line, not a gate; the write itself is
  idempotent. Not worth a change.
- **Retro-cleaning the 233 single-occurrence metric names.** Already
  settled as DB_SCHEMA invariant 10 — stored reports cite those row ids
  through `inputs[]` lineage. Left alone on purpose.

### One flag that belongs to neither sprint

`FOUNDATIONS §6.3` wants the SEBI / copyright review done **before the
UI ships to anyone but the owner**. Sprint 1 does not onboard users,
but it does make `/reports` render live data publicly. That is a
threshold worth crossing deliberately rather than by default — and it
is the same review that gates unlocking the verdict column (contract
§7).
