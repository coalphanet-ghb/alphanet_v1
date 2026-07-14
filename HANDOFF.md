# AlphaNet — Engineering Handoff

> **Read this first.** This document carries the full context and every
> architectural decision made so far. The decisions in here were reasoned
> through carefully — where something looks odd or over-simple, there is
> almost always a stated reason. **Don't silently "improve" a decision
> marked as deliberate.** If you think one is wrong, say so explicitly and
> explain why, rather than quietly changing it.

---

## 1. What AlphaNet is

An **AI-native equity research platform for Indian equities**. The goal is to
be the AI-powered successor to Screener.in: instead of exposing raw financial
data, every listed company gets one continuously-updated, institutional-quality
research report synthesized from trusted public sources.

Positioning: *"What AI Research Agents say about Indian Equities."*

**It does NOT give Buy/Sell/Hold recommendations.** It presents structured
research, valuation analysis, risks, business quality, and supporting
evidence so users decide for themselves. This is a hard product rule, and
it is also load-bearing for the regulatory posture (see §11).

Target users: serious retail investors, long-term/fundamental investors,
equity researchers, MBA/CFA students — people who currently use Screener,
ValuePickr, Moneycontrol, Tickertape.

### The core intellectual bet

Research is decomposed into **reusable knowledge layers**, not one giant
prompt:

```
Macro  →  Industry / Sector  →  Company  →  Final Report
```

Macro research is computed once and reused across all companies. Industry
research is computed once per sector and reused across every company in it.
Company research contains only company-specific knowledge. The final report
is assembled from all three. This avoids duplicated computation and enables
incremental updates.

### Cost philosophy ("bill-safe")

- Minimize LLM calls; reuse knowledge; never regenerate unchanged reports
- Cache expensive outputs
- **Prefer deterministic code over AI reasoning wherever possible**
- Live within free tiers (Cloudflare + Supabase + Cloud Run + Gemini free tier)

---

## 2. Current state of the code

The existing codebase is a **Phase 1 walking skeleton** that has been run
successfully end-to-end. It proves the core loop works. It is now being
upgraded, not rewritten.

```
alphanet/
  main.py                        # CLI entrypoint
  src/
    config.py                    # env vars, defaults, model name
    llm.py                       # Krutrim wrapper  ← BEING REPLACED
    ingestion/web_research.py    # ddgs + trafilatura  ← BEING DELETED
    knowledge/stubs.py           # hardcoded macro & industry context ← temporary
    workflow/
      state.py                   # LangGraph state schema
      prompts.py                 # prompt templates
      nodes.py                   # 5 parallel analysis nodes + valuation synthesis
      graph.py                   # StateGraph wiring (fan-out / fan-in)
    output/report_writer.py      # deterministic markdown assembly + citation check
  data/reports/                  # generated .md output
```

The graph shape is correct and should be preserved:

```
        gather_sources
       /   |    |    |    \
financial biz  mgmt risk  peer      ← parallel fan-out
       \   |    |    |    /
        valuation_synthesis          ← fan-in
              |
        report_composer              ← deterministic, no LLM
```

**What's being migrated away from (decided, not up for debate):**
- `gpt-oss-120b` via Krutrim → **Gemini**
- `ddgs` + `trafilatura` DIY scraping → **Gemini's native tools**
- Local markdown files as the only persistence → **Supabase**

---

## 3. Model routing — READ CAREFULLY

This is the single most misunderstood part of the stack. Get it wrong and
you either hit a paywall or silently break grounding.

**One Gemini API key. Three call types. Two different model strings.**

| Call type | Model | Tool | Cost |
|---|---|---|---|
| **Open discovery** — macro/sector scanning, "find the latest concall/results/news" | `gemini-2.5-flash` | `google_search` | Free, **no card**, ~500 RPD (shared with 2.5 Flash-Lite) |
| **Reading a known URL** — filings, concall transcripts, annual reports | `gemini-3.5-flash` | `url_context` | Free, **no card** |
| **Synthesis / valuation / narrative writing** | `gemini-3.5-flash` | none | Free tier |

### Why the split (this is the non-obvious part)

`google_search` grounding availability is a **2.5-vs-3.x distinction, not a
free-vs-paid one.** On *every* Gemini 3.x model (3 Flash, 3.5 Flash, 3.1 Pro,
3.1 Flash-Lite), `google_search` is listed as **"Not available" on the free
tier** — it only turns on once billing is enabled on the project, even though
you'd then get 5,000 free grounded prompts/month.

`gemini-2.5-flash` is the **only card-free path to `google_search`.**

Meanwhile `url_context` (fetch and read a specific URL you already have) is
**free of charge across all generations**, with no Gemini-3-only restriction.
So reading a known filing URL works free on 3.5 Flash without billing.

### Two hard constraints

1. **Keep billing DISABLED on the prototyping GCP project.** Enabling billing
   kills the free tier on that project entirely.
2. **Do not trust any quota number in this document, including the ones above.**
   Google has revised these repeatedly and without notice. Check the live quota
   panel in AI Studio before relying on a number.

---

## 4. The evidence-extraction pattern (important)

There is a widely-repeated claim that you can "map Gemini's grounding citation
spans directly into evidence rows." **This is misleading and you must not build
on it without verifying.**

What `google_search` grounding actually returns is:
- the **source URL and title**, and
- start/end indices pointing into **Gemini's own output text** — i.e. "these
  characters of *my answer* are supported by that link."

What it does **not** reliably give you is **the source passage itself**. So you
**cannot** populate `evidence.text` (the citable slice of the original document)
from a grounding annotation alone. You'd end up with a URL and a claim, but no
supporting text — which guts the entire verification layer, because you can't
check a claim against source text you never retrieved.

### Therefore: ingestion is a TWO-STEP pattern

```
Step 1 — DISCOVER (gemini-2.5-flash + google_search)
         "Find the latest Sona BLW concall transcript / quarterly results / news"
         → returns URLs. That's all we want from it. Not analysis.

Step 2 — READ (gemini-3.5-flash + url_context)
         Feed those URLs in, extract real passages.
         → THIS populates evidence.text with genuine source material.
```

For documents whose URL you already know (a specific BSE/NSE filing), **skip
Step 1 entirely** and go straight to `url_context`.

This happens to also satisfy the project's own principle that *ingestion is
separate from reasoning*. It falls out naturally rather than being forced.

> **ACTION BEFORE BUILDING:** run one grounded call and dump the raw response
> to inspect exactly what the annotations contain in the current API version.
> This is a ~10 minute check that de-risks the entire evidence layer. Do not
> take this document's word for it.

---

## 5. Database — Supabase (Postgres)

Supabase is **live and the schema is already applied.** Nine tables.

**The schema is FROZEN as-is for now. Do not modify it without asking.**
Two changes were proposed and explicitly declined by the project owner:
- a `claim_evidence` junction table (rejected — keep `claims.evidence_ids uuid[]`)
- changing the `evidence.embedding` dimension (rejected — leave it alone)

### Consequence of keeping `evidence_ids` as an array

Postgres **cannot enforce foreign keys on array elements**. So nothing at the
DB level stops a claim from referencing an evidence UUID that doesn't exist —
which is exactly the hallucinated-citation failure mode this architecture
exists to catch.

**→ The citation-integrity check MUST therefore be implemented in application
code.** Before persisting claims, verify every UUID in `evidence_ids` actually
resolves to a real `evidence` row. Flag or reject any that don't. This is not
optional; it's the DB-level safety net we consciously gave up.

### On embeddings

`evidence.embedding vector(768)` exists but is **nullable and unused. Leave it
that way.** Retrieval today is deterministic and structural: a node asks "give
me evidence linked to entity X from document type Y" — a plain SQL join through
`entity_mentions`. No vectors involved. Embeddings only become necessary when
that filter returns too much to fit in a prompt and you need semantic ranking
within it. With a handful of companies you are nowhere near that.

The column is empty, so changing its dimension later is a one-line `ALTER TABLE`
with zero rows to migrate. There is no painful retrofit waiting. Ignore it.

### The nine tables and what each is for

**Ingestion layer**
- `source_documents` — one row per raw document ingested (annual report, concall
  transcript, news article, brokerage note, macro data). `content_hash` for
  dedup; `raw_storage_path` points at the full original in Supabase Storage.
- `evidence` — **the atomic, citable unit.** A paragraph, a page, a concall
  timestamp. Every claim traces back to an evidence row, never to free text.
  This is what makes citations checkable by code instead of trusted on faith.

**Graph layer (lite)**
- `entities` — nouns: `company` | `sector` | `commodity` | `policy` | `person` |
  `macro_factor` | `geography` | `other`
- `entity_relationships` — edges: e.g. Sona BLW `--supplies_to-->` Bosch;
  Steel `--input_cost_for-->` Auto
- `entity_mentions` — links evidence to the entities it discusses

  Deliberately **plain Postgres tables, not a graph DB.** Recursive CTEs give
  you traversal ("what does Steel connect to?") without standing up Neo4j.
  A real graph engine is a legitimate V2/V3 move once entity volume demands
  graph-native queries. Not now.

**Numeric layer**
- `metric_observations` — structured time-series facts: commodity prices, repo
  rate, GDP growth, quarterly ratios. **Append-only.** Past periods never change;
  only new periods get added. Unique on
  `(entity_id, metric_name, period_start, period_end)`.

**Knowledge layer**
- `knowledge_entries` — the versioned, **STRUCTURED (JSON, never prose)** output
  of each research layer. One row per `(layer, entity, section, version)`.
  `based_on_versions_json` pins which upstream versions it was built from,
  e.g. `{"macro": 21, "industry": 18}`.
- `claims` — individual factual statements, each tied to `evidence_ids`.
  Verification operates at this level. Never let a node emit free-text citations.

**Output layer**
- `report_versions` — the assembled human-readable report, pinned to the exact
  macro/industry/company knowledge versions used, so you can always answer
  "why did this report say X last month" even after the knowledge bases moved on.

**Ops layer**
- `runs` — one row per workflow execution: tokens, cost, model, status, errors.
  **Log this from day one.** Retrofitting means your earliest runs are unauditable.

### Access

Backend connects with the **`service_role` key**, which bypasses RLS entirely.
RLS is enabled and fully closed on every table. There's a commented-out policy
in the schema to open read access on `report_versions` only, if the frontend
ever queries Supabase directly.

**MCP is NOT needed here.** MCP is for letting an LLM *decide* to query your DB.
That is not this architecture — nodes deterministically load their context.
Use `supabase-py` server-side. Skip MCP.

---

## 6. Answers to design questions already settled

**Do we store full source documents, or just relevant slices?**
Both. `source_documents.raw_storage_path` → full original in Supabase Storage
(cheap, and you'll want it when chunking improves). `evidence` → the citable
slices. **Never cite a document; always cite an evidence row.**

**How does an agent find the right sources across macro/sector/company sub-topics?**
Not by document type — by **`entity_id` + `section`**. "Crude oil" is an
`entity` of type `commodity`; the macro node's crude sub-topic queries evidence
via `entity_mentions` for that entity. Same mechanism at every layer. This is
what the graph-lite tables buy you.

**Concalls — one row per company, or one per quarter?**
**One `source_documents` row per concall event** (Q1FY26, Q2FY26, ...), each with
its own evidence rows. History accumulates naturally. The *synthesis across*
concalls lives in `knowledge_entries` as a versioned row — so a "management
guidance track record" entry can cite evidence from six different concalls
without duplicating anything.

**Versioning — two different regimes, both already in the schema:**
- `evidence` and `metric_observations` are **append-only** (facts don't change;
  new ones arrive)
- `knowledge_entries` and `report_versions` are **versioned** (synthesis genuinely
  gets superseded, and reports must be reconstructible after the fact)

**How does context-chaining between the three loops work?**
Trivially. Every workflow's first node is `get_latest(layer, entity_id, section)`
— pull the most recent `knowledge_entries` row for the layer(s) it depends on,
deserialize `content_json`, feed it in as context. **That is the entire
mechanism.** No orchestration magic needed yet.

---

## 7. Node specs (`spec.md` per node)

Formalize each node's contract as a versioned markdown file in git. This is the
"skills.md per node" idea, and it's the right instinct — it makes prompts
reviewable like code and gives the golden-test-set something to diff against.

```
/nodes/
  macro/spec.md
  industry/spec.md                    # templated; sector name is a parameter
  company/
    business_overview/spec.md
    financial_analysis/spec.md
    valuation/spec.md
    risk_esg/spec.md
    supply_chain/spec.md
    peer_positioning/spec.md
  composer/
    section_writer/spec.md
    citation_resolution/spec.md
    verification/spec.md
```

Each `spec.md` contains:
1. **Purpose** (1–2 lines)
2. **Input context / versions required**
3. **Retrieval instructions** — `google_search` (2.5) vs `url_context` (3.5) vs
   internal evidence lookup
4. **Output JSON schema**
5. **Quality checklist**
6. **One golden example**

---

## 8. Anti-hallucination principles (non-negotiable)

1. **Grounding over recall.** Every synthesis prompt says explicitly: use only
   the provided sources; if the answer isn't there, say so. Never fill gaps from
   parametric knowledge.
2. **Structured output, never prose citations.** Nodes emit
   `{claim, evidence_ids, confidence}` JSON. Prose citations ("according to the
   annual report...") are unverifiable and are exactly where hallucination hides.
3. **Verify citations in application code** (see §5 — we gave up the DB-level FK).
4. **A cheap verification pass.** One narrow LLM call per claim: "is this claim
   supported by this text?" Far cheaper than the generation call that produced it,
   and the highest-leverage single thing for trustworthiness.
5. **Deterministic math.** Ratios, CAGR, growth rates, multiples — compute in
   Python (pandas/numpy) and give the LLM the *result to interpret*. Never ask a
   model to do arithmetic. Financial research is exactly where subtle numeric
   errors are unacceptable.
6. **Model tiering.** Cheap models for mechanical tasks (chunk classification,
   impact detection, citation resolution). Best model only for valuation synthesis
   and section-writing.
7. **Golden set.** Once 5–10 companies have manually-reviewed reports you trust,
   freeze them as a regression set. Rerun and diff after every prompt/model change.
   Without this, quality drift is invisible until a user catches it.

---

## 9. Sprint plan (what to build next)

**Sprint 1 — persistence + Gemini swap ← START HERE**
- `src/db.py`: thin data-access module. Functions:
  `get_or_create_entity`, `save_source_document`, `save_evidence`,
  `save_knowledge_entry`, `get_latest(layer, entity_id, section)`,
  `save_claims` (with the app-level evidence-ID integrity check),
  `start_run` / `finish_run`
- `src/llm.py`: replace Krutrim with Gemini (`google-genai` SDK). Expose the
  three call types from §3 as distinct functions so the model split is explicit
  and hard to get wrong.
- Rewrite `src/ingestion/` to the two-step discover→read pattern (§4).
  **Delete `ddgs` and `trafilatura`.**
- Retrofit the existing company workflow to write into Supabase instead of only
  a local markdown file.
- Seed ~30–50 entities by hand for the pilot: Sona BLW, auto-components sector,
  steel, rare earths, INR, repo rate, its named customers and peers.
  **Don't build NER.** Just match known entity names against evidence text.

**Sprint 2 — structured output + node specs**
Nodes emit structured JSON + claims (not prose) into
`knowledge_entries` / `claims`. Write the `spec.md` files.

**Sprint 3 — macro + industry loops**
One macro node → versioned macro entry. One industry node per pilot sector →
versioned industry entry. The company workflow now loads these via `get_latest`
instead of `src/knowledge/stubs.py`. **Delete the stubs.**

**Sprint 4 — composer + verification**
Section-writer nodes turn JSON → prose, strictly grounded. Cheap verification
model checks each claim against its cited evidence. Assemble `report_versions`,
render markdown.

**Sprint 5 — golden set + observability**
Freeze 5 pilot companies as a regression set. Every run logged to `runs`.
Build a "diff this run vs last golden" script.

**Sprint 6+ — update workflow, scale**
Rule-based triggers **first** (new filing → deterministic regen of the affected
sections). LLM judgment **only** for genuinely ambiguous inputs like a news
article, where you actually need to decide if it's material. Keeping the
orchestrator mostly deterministic is what keeps it cheap and predictable.

---

## 10. Deliberate non-goals (do NOT build these yet)

- ❌ Vector search / embeddings — structural retrieval is sufficient at this scale
- ❌ A graph database (Neo4j etc.) — three Postgres tables + recursive CTEs
- ❌ MCP servers for DB access — nodes load context deterministically
- ❌ NER for entity extraction — hand-seed the pilot entity set
- ❌ Scheduler / orchestrator / multi-company automation — validate quality first
- ❌ The full 12-section report — start with Business Overview, Financial
  Analysis, Management & Guidance, Risks, Peer Positioning, Valuation.
  Supply Chain, ESG, Brokerage Research, Technical Analysis come later; they add
  surface area without teaching you anything new about whether the core works.
- ❌ Any UI work — markdown output is fine for now

The single biggest risk to this project is **automating a research loop whose
output isn't actually trustworthy.** Every sprint above is ordered to attack
that risk first. Resist building infrastructure around an unvalidated core.

---

## 11. Things to verify / open risks

1. **Gemini grounding response shape** (§4) — inspect a raw response before
   building the evidence layer on assumptions.
2. **Live quota numbers** — check AI Studio's quota panel, not this doc.
3. **Compliance, worth a real conversation before going live with users:**
   - Redistributing full brokerage reports or large chunks of news content raises
     **copyright** questions. Store and display source *slices* and links, not
     wholesale reproductions.
   - Publicly offering structured research on individual listed securities in
     India may engage **SEBI's Research Analyst framework**, depending on
     positioning and monetization — *even without Buy/Sell calls*. The no-recommendations
     rule helps but is not automatically sufficient.
   - Neither of these blocks development. Both should be reviewed with someone
     who specializes in SEBI/fintech compliance before real users are onboarded.
     This is not legal advice.

---

## 12. Quality bar for the first real output

When the pipeline produces its first Sona BLW report, **read it like a skeptical
analyst, not a proud engineer:**

- Does every specific number trace back to something actually in the sources?
- Is there any claim that sounds plausible but isn't attributable to a specific
  evidence row? That's a hallucination risk even if it happens to be true.
- Do the citations actually point to the right page/section when you go check?
- Is it genuinely synthesizing across sources, or just restating one document?

If most of it survives that scrutiny, the hard part is validated. If it doesn't,
that's *valuable* — far cheaper to learn now than after building schedulers and
macro automation on top of a shaky core.
