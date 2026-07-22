# FOUNDATIONS — product identity, settled decisions, principles

> Consolidated 2026-07-22 from HANDOFF.md (2026-07-13, the original
> engineering handoff) and HANDOFF2.md (2026-07-17), which were then
> deleted. Their plans are long executed; **everything durable in them
> lives here.** This file is deliberately timeless: it carries WHAT the
> product is and WHY the architecture is shaped this way. Current state
> and work order live in HANDOFF4.md + NEXT_STEPS.md.
>
> **Decisions marked deliberate were reasoned through. Don't silently
> "improve" one — if you think it's wrong, say so and explain why.**

---

## 1. What AlphaNet is

An **AI-native equity research platform for Indian equities** — the
AI-powered successor to Screener.in: instead of exposing raw financial
data, every listed company gets one continuously-updated,
institutional-quality research report synthesized from trusted public
sources.

Positioning: *"What AI Research Agents say about Indian Equities."*

**It does NOT give Buy/Sell/Hold recommendations.** It presents
structured research, valuation context, risks, business quality and
supporting evidence so users decide for themselves. This is a hard
product rule and it is load-bearing for the regulatory posture (§6).

Target users: serious retail investors, long-term/fundamental
investors, equity researchers, MBA/CFA students — people who today use
Screener, ValuePickr, Moneycontrol, Tickertape.

### The core intellectual bet

Research decomposes into **reusable knowledge layers**, not one giant
prompt:

```
Macro  →  Industry / Sector  →  Company  →  Final Report
```

Macro is computed once and reused across all companies; industry once
per sector and reused across every company in it; company research
holds only company-specific knowledge. This avoids duplicated
computation and enables incremental updates. (The 2026-07 sector
pipeline made the industry layer first-class: it now owns the numeric
backbone for every member stock — see HANDOFF4 §2 R3.)

### Cost philosophy ("bill-safe")

Minimize LLM calls; reuse knowledge; never regenerate unchanged
reports; cache expensive outputs; **prefer deterministic code over AI
reasoning wherever possible.**

## 2. Settled architecture decisions (and why)

**Evidence is the atomic citable unit — never cite a document.**
`source_documents` holds the raw doc; `evidence` holds the citable
slices; every claim traces to an evidence row. This is what makes
citations checkable by code instead of trusted on faith.

**Why the citation-integrity check lives in application code.**
`claims.evidence_ids` is `uuid[]`, and Postgres cannot enforce foreign
keys on array elements — so nothing at the DB level stops a claim
citing a nonexistent evidence UUID, which is exactly the
hallucinated-citation failure mode this architecture exists to catch.
`db.save_claims` verifies every UUID; `run_section` additionally
requires membership in THIS RUN's evidence pool. **Deliberately
declined:** a `claim_evidence` junction table (owner decision — keep
the array + app-code check).

**Why `evidence.embedding` stays null.** Retrieval is deterministic and
structural: "give me evidence linked to entity X from document type Y"
— a plain SQL join through `entity_mentions`. Embeddings only matter
when that filter returns more than fits a prompt and you need semantic
ranking within it. The column is empty, so changing its dimension later
is a one-line ALTER with zero rows to migrate. **Deliberately
declined:** changing the embedding dimension now.

**Why plain Postgres tables, not a graph DB.** `entities` +
`entity_relationships` + `entity_mentions` with recursive CTEs give
traversal ("what does Steel connect to?") without standing up Neo4j. A
real graph engine is a legitimate later move once entity volume demands
graph-native queries.

**Why no MCP for DB access.** MCP is for letting an LLM *decide* to
query your DB. That is not this architecture — nodes deterministically
load their context. `supabase-py`, server-side, with the `service_role`
key (bypasses RLS; RLS stays fully closed; never expose it to a
frontend).

**Sources are found by `entity_id` + `section`, not by document type.**
"Crude oil" is an entity of type commodity; the macro node's crude
sub-topic queries evidence via `entity_mentions` for that entity. Same
mechanism at every layer — this is what the graph-lite tables buy.

**One `source_documents` row per concall EVENT** (Q1FY26, Q2FY26 …),
each with its own evidence rows, so history accumulates naturally. The
*synthesis across* concalls lives in `knowledge_entries` as a versioned
row, citing evidence from six different concalls without duplication.

**Two versioning regimes, both deliberate:** `evidence` and
`metric_observations` are **append-only** (facts don't change; new ones
arrive). `knowledge_entries` and `report_versions` are **versioned**
(synthesis genuinely gets superseded, and reports must be
reconstructible after the fact — "why did this report say X last
month" must stay answerable).

**Context-chaining between layers is trivial by design:** every
workflow's first step is `get_latest(layer, entity_id, section)` —
pull the most recent knowledge entry for the layer(s) it depends on,
deserialize `content_json`, feed it in. That is the entire mechanism;
no orchestration magic.

**Store full documents AND slices.** The full original is cheap to keep
and you will want it when chunking improves.

**A historical note that shaped the evidence layer:** search-grounding
annotations return the source URL plus indices into *the model's own
output* — not the source passage. You therefore cannot populate
`evidence.text` from a grounding annotation, which would gut
verification (you can't check a claim against text you never
retrieved). Hence ingestion was always split: discover URLs, then
genuinely READ them. Today that read is a local fetch + inline
extraction, but the reason the split exists is this.

## 3. Anti-hallucination principles (non-negotiable)

1. **Grounding over recall.** Every synthesis prompt says: use only the
   provided sources; if the answer isn't there, say so. Never fill gaps
   from parametric knowledge. (Now ENVELOPE_CONTRACT rule 1.)
2. **Structured output, never prose citations.** Nodes emit
   `{claim, evidence_ids, confidence}`. Prose citations ("according to
   the annual report…") are unverifiable and are exactly where
   hallucination hides.
3. **Verify citations in application code** (§2 — we gave up the DB FK).
4. **A cheap verification pass.** One narrow call per claim: "is this
   supported by this text?" — far cheaper than the generation call, and
   the highest-leverage single thing for trustworthiness. (This became
   s9_verifier, now a PRODUCT FEATURE: full coverage stays.)
5. **Deterministic math.** Ratios, CAGR, growth, multiples — computed
   in Python; the model interprets the *result*. Never ask a model to
   do arithmetic. (ENVELOPE_CONTRACT rules 2/2b.)
6. **Model tiering.** Cheap models for mechanical tasks; the best model
   only where judgement matters.
7. **Golden set.** Once reports you trust exist, freeze them as a
   regression set; rerun and diff after every prompt/model change.
   Without this, quality drift is invisible until a user catches it.
   (`scripts/diff_golden.py`, `data/golden/`.)

## 4. Quality bar for any report (the skeptical read)

Read output **like a skeptical analyst, not a proud engineer**:

- Does every specific number trace back to something actually in the
  sources?
- Is there any claim that sounds plausible but isn't attributable to a
  specific evidence row? That's a hallucination risk even if it happens
  to be true.
- Do citations point to the right page/section when you go check?
- Is it genuinely synthesizing across sources, or restating one
  document?

## 5. Best practices learned (violate at your peril)

> Preserved from HANDOFF2 §6 with its numbering intact — code comments
> cite these by number (e.g. `s2_extract.py` cites §5.12). HANDOFF3 §7
> extends this list with ten further lessons; both lists are live.

1. **Wrong numbers are worse than missing ones — and they look
   plausible.** Three substring collisions in canon matching shipped
   corrupted values (debtor days as borrowings; a CFO/OP *ratio*
   overwrote CFO and produced a FALSE earnings-manipulation flag).
   Guards exist (`scripts/test_screener_parser.py`: idempotency + trap
   labels + "CFO never contains %"). When touching `metric_names.py`:
   keys are substring-matched longest-first; short keys are landmines
   ("debt", "cash", "pe", "cfo"); add a trap test per new key.
2. **Fixtures lie; live data tells the truth.** Two of three collisions
   were invisible to the hand-built fixture and appeared only on the
   real page. Test parsers against the live page (`--live`), then
   backport the surprising rows INTO the fixture.
3. **Verify with the exact failing case.** Reproduce the precise
   artifact first, then assert the fix on it.
4. **Models interpret, Python computes.** Also: models must NOT convert
   units (contract rule 2b exists because hand-converted crore/billion
   contradicted across sections).
5. **Freshness ≠ absence.** "Layer fresh, skip reads" once meant "run
   without the data" (empty section C). Any skip-optimization must
   rehydrate from storage.
6. **Reuse needs quality gates** or it freezes your worst extraction
   forever (`REUSE_MIN_PASSAGES`, `--reingest`, and since 2026-07 the
   extraction focus-hash).
7. **Failure handlers must never throw** — a DB write inside the
   failure path once crashed during a DNS outage and masked the real
   error.
8. **Free tiers lie about limits; measure them.** 3.5-flash's 5 RPM/20
   RPD and the NVIDIA trial's bursty 429s/504 queues were discovered
   empirically. Paid Fireworks removed a whole class of engineering.
   Probe endpoints with tiny calls before wiring providers.
9. **Every design decision lives in a versioned doc** (blueprint →
   sources → playbook → knowledge → specs → packs). Specs ARE the
   prompts; editing a spec or pack changes the product with zero code
   changes. Keep it so.
10. **Insufficiencies are a feature.** Never paper over gaps; the "Not
    found in sources" sections drive the next phase's priorities.
11. **Read the run log as a dashboard.** Observation counts, dedup
    gaps, reuse/parse lines, quality badge — anomalies there caught
    every real bug before the report was even opened.
12. **Reasoning models spend hidden thinking tokens INSIDE
    max_tokens** — truncation must be detected via
    `finish_reason == "length"`, not parse failure. (Model routing
    facts: MiniMax-M3 chosen for best non-hallucination + instruction
    following; DeepSeek V4 Pro disqualified at 6% non-hallucination.)

## 6. Compliance — review before real users (not legal advice)

1. **Copyright.** Redistributing full brokerage reports or large chunks
   of news content raises copyright questions. Store and display source
   *slices* and links, never wholesale reproductions.
2. **SEBI Research Analyst framework.** Publicly offering structured
   research on individual listed securities in India may engage it,
   depending on positioning and monetization — **even without
   Buy/Sell/Hold calls.** The no-recommendations rule helps but is not
   automatically sufficient.
3. Neither blocks development. Both should be reviewed with someone who
   specializes in SEBI/fintech compliance **before real users are
   onboarded** — i.e. before the UI era ships to anyone but the owner.

## 7. Deliberate non-goals (status as of 2026-07-22)

Still valid: vector search / embeddings (structural retrieval
suffices); a graph database; MCP servers for DB access; NER for entity
extraction (entities are seeded, and the universe registry now feeds
them); scheduler / multi-company automation **until** the
generalization plan's gates are met.

Retired (they were staged non-goals and their time has come): the full
11-section report (built and frozen), and UI work (the next era —
rendering `report_versions.sections_json` against envelope contract
v1.0.0).

**The single biggest risk to this project remains automating a research
loop whose output isn't actually trustworthy.** Resist building
infrastructure around an unvalidated core.
