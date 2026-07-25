# DB_SCHEMA.md — Supabase schema + persistence contract

> For any AI agent or developer touching persistence. The schema is
> **FROZEN** — nothing in this codebase alters tables; all integrity
> that the schema cannot express lives in application code
> (`src/db.py`). Where this doc and the live DB disagree, the live DB
> wins; schema snapshot verified 2026-07-19.

## The tables (10)

### `source_documents` — one row per ingested document
| Column | Type | Notes |
|---|---|---|
| id | uuid | PK |
| type | text | from `_DOC_TYPE_MAP` in s2_extract (doc_class → type) |
| title | text | |
| url_or_path | text? | reuse lookup key (`get_source_document_by_url`) |
| published_date | date? | **R3 must populate per doc class** (AR release, concall quarter, PPT date, news pub date) — often null historically |
| ingested_at | timestamptz | |
| content_hash | text? | sha256 of extracted text — dedup key in `save_source_document` |
| raw_storage_path | text? | unused |
| metadata | jsonb | carries `layer` ('macro'/'industry'/company) and `doc_class`; `get_layer_evidence` filters `metadata->>layer` |

### `evidence` — verbatim extracted lines (the citation currency)
| Column | Type | Notes |
|---|---|---|
| id | uuid | PK — this uuid is what every claim/block cites |
| source_document_id | uuid? | → source_documents |
| text | text | VERBATIM quote; `save_evidence` is idempotent on (doc, text) |
| page_or_timestamp | text? | |
| confidence | numeric? | unused |
| embedding | vector? | **stays null by design** — retrieval is structural, not semantic |
| created_at | timestamptz | |

**No tags/section/doc_class columns.** Line-level attributes (tags like
`risk_signal`/`guidance_item`, and — per the 2026-07-19 plan — section
maps) live in the `extract:{doc_id}` knowledge-entry JSON and are
rehydrated into the run-time evidence pool. Do not try to store them
here.

### `entities`
| Column | Type | Notes |
|---|---|---|
| id | uuid | PK |
| name | text | `get_or_create_entity` dedups on (name, type) — names must match data/seed_entities.json |
| type | text | company / sector / macro_indicator / … |
| metadata | jsonb | screener slug, ticker, sector key, etc. |

### `metric_observations` — observed numeric facts (append-only)
| Column | Type | Notes |
|---|---|---|
| id | uuid | PK |
| entity_id | uuid | |
| metric_name | text | canonical names from `src/ingestion/metric_names.py` |
| period_type | text | |
| period_start / period_end | date | |
| value | numeric | |
| unit | text? | unit-class guard in s3 drops impossible units |
| source_document_id | uuid? | provenance |
| ingested_at | timestamptz | |

Unique constraint `(entity_id, metric_name, period_start, period_end)`
— upserts use `ignore_duplicates=True`: **existing rows are never
overwritten** (observed facts are append-only; restatements do not
update rows). **Derived values (TTM, CAGRs, PE series) are NEVER
stored here** — they are computed at run time in s3 with full lineage.

**`period_type='day'` rows** come from two writers and mean different
things — do not conflate them:
- the **screener top card** on any research run (`price`, `market_cap`,
  `pe`, `book_value`, `dividend_yield_pct`, `roce_pct`, `roe_pct`),
  stamped `date.today()` — i.e. the date the SCRAPER RAN, not the
  close it reflects (`screener_parser.py`, see the HANDOFF4 §6 watch
  item);
- the **daily market-data job** (`scripts/daily_market_data.py`), which
  writes only `price` + `market_cap`, stamped with the AUTHORITATIVE
  close date taken from Yahoo's last daily bar. Consumers that need a
  specific trading day (the UI snapshot) must query an explicit
  `period_end`, never "the latest day row".

Row-count expectations: a fully-researched company carries ~1,000 rows
(SONA: 634 year / 241 quarter / 85 month / 28 day, across 321 distinct
metric names — of which 233 appear exactly once: the AR-extraction
disclosure tail). The daily job adds 2 rows per company per trading day
(~75K/yr across 150 companies, ~12 MB — trivial). **Never page an
unbounded `select` against this table** — PostgREST caps at 1,000 rows
silently (see invariant 9).

### `entity_relationships` — the entity graph
| Column | Type | Notes |
|---|---|---|
| id | uuid | PK |
| from_entity_id / to_entity_id | uuid | |
| relationship_type | text | `peer_of` (peer → company), supply-chain relations (`supplies_to`, `customer_of`, `input_cost_for`, `single_source_from`, `exports_to`); **R2 adds `member_of` (stock → sector)** |
| evidence_id | uuid? | provenance |
| created_at | timestamptz | |

Dedup in `save_entity_relationship` on (from, to, type).

### `entity_mentions` — evidence ↔ entity links
| Column | Type | Notes |
|---|---|---|
| id | uuid | PK |
| evidence_id / entity_id | uuid | unique on the pair; upsert ignores duplicates |

### `knowledge_entries` — versioned JSON store (the workhorse)
| Column | Type | Notes |
|---|---|---|
| id | uuid | PK |
| layer | text | 'macro' / 'industry' / 'company' |
| entity_id | uuid | |
| section | text | free-form key — see conventions below |
| version | int4 | auto-incremented per (layer, entity, section) by `save_knowledge_entry` |
| content_json | jsonb | the payload |
| based_on_versions_json | jsonb | pins upstream context versions |
| generated_by_run_id | uuid? | |
| created_at | timestamptz | |

**Section-key conventions in use:**
- `section_B` … `section_J` — synthesis envelopes (company layer)
- `extract:{source_document_id}` — a document's extraction output
  (passages with tags + evidence-row ids, metric candidates, guidance
  items…). Reuse loads the **latest version only**. Line-level tags
  live here: the `passage_tags` map (evidence_id → tags, persisted
  since Round 1.3, 2026-07-21) is rehydrated on reuse; pre-fix entries
  fall back to `risk_evidence_ids` → risk_signal. Per-passage section
  maps and the extraction focus-hash join them in Round 4.
- `concall_cross_quarter` — batched/trails-pass output
  (guidance_evolution[], recurring_themes[])

### `claims` — per-claim citation records
| Column | Type | Notes |
|---|---|---|
| id | uuid | PK |
| knowledge_entry_id | uuid | → the section envelope entry |
| text | text | |
| evidence_ids | uuid[] | **NO FK possible on array elements** — see invariant #1 |
| confidence | numeric? | |
| verification_status | text | pending → verified/failed (s9 verifier via `update_claim_status`) |
| created_at | timestamptz | |

### `report_versions`
| Column | Type | Notes |
|---|---|---|
| id | uuid | PK |
| company_id | uuid | |
| version | int4 | auto-incremented per company |
| generated_at | timestamptz | |
| sections_json | jsonb | **typed blocks — the future UI renders this**; also carries `quality`, `envelope_contract_version`, the run manifest and `citation_map` (below) |
| based_on_macro_version / based_on_industry_version / based_on_company_version | int4? | layer-version pins (industry = sector layer) |

### `runs` — run observability (aggregates only)
| Column | Type | Notes |
|---|---|---|
| id | uuid | PK |
| workflow_name | text | e.g. report generation; R2 sector runs get their own name |
| entity_id | uuid? | |
| started_at / finished_at | timestamptz | |
| status | text | running / succeeded / failed |
| model_used | text? | |
| tokens_input / tokens_output | int4? | run totals |
| cost_usd | numeric? | |
| error_message | text? | |

**Scalar-only — no jsonb.** Per-node telemetry breakdowns (R0) go to
local sidecar files `data/telemetry/{run_id}.json`, NOT this table.

## Invariants (application-code contracts — do not weaken)

1. **Citation integrity is app code.** `claims.evidence_ids` is a
   uuid[] with no FK enforcement possible. `db.save_claims` verifies
   every cited uuid exists (strict=True raises; strict=False persists
   the offender as verification_status='failed'). Additionally,
   `run_section` (s4_synth) only accepts uuids present in **this
   run's** evidence pool — merely existing in the DB is not enough.
   **Nodes cite run-scoped LABELS, not uuids** (`src/pipeline/
   citations.py`): `run_section` resolves label → uuid *before*
   `save_claims`, so what reaches the DB is uuids and only uuids. An
   unresolvable label is stripped exactly like a bad uuid was.
1b. **Citation labels are run-scoped and are NEVER stored per-document.**
   A label depends on the whole run pool (including rehydrated
   macro/industry rows), so a label written into an `extract:{doc_id}`
   entry would be wrong on the next run. The run's map is persisted
   once, with the report, as `report_versions.sections_json.citation_map`
   = `{"labels": {label: evidence_uuid}, "documents": [...]}`. That is
   what keeps a stored report re-resolvable after the fact, and what
   the UI reads for footnote markers. jsonb — no DDL.
2. **Append-only observed facts.** Re-reads must not duplicate or
   overwrite: `save_source_document` dedups by content_hash;
   `save_evidence` by (doc, text); metric upserts ignore conflicts.
3. **Derived ≠ observed.** No computed value (TTM, CAGR, PE series,
   ratios) is ever written to `metric_observations`. Computation
   happens in s3 at run time with lineage (`inputs` id lists) kept in
   state — lineage is a persistence/state concern and is NOT rendered
   into prompts.
4. **Latest-version-only reuse.** When rehydrating `extract:{doc_id}`
   entries, load only the highest version (multi-version pools once
   caused duplicate observations — Phase 0.4).
5. **Freshness means "don't re-fetch", never "run without the data".**
   A layer marked fresh must be rehydrated from storage
   (`get_layer_evidence`) into the run's pool (Phase 0.3).
6. **`evidence.embedding` stays null.** No semantic retrieval at this
   scale; joins go through `entity_mentions`.
7. **Service-role key is server-side only** (bypasses RLS — never
   expose to a frontend).
8. **Schema is frozen.** New needs are met with: new `section` key
   strings in knowledge_entries, new `relationship_type` /
   `entities.type` values, jsonb `metadata` fields, or local files —
   never DDL.
9. **PostgREST silently caps unbounded selects at 1,000 rows.** Any
   query that must return a complete set has to paginate with
   `.range()` until a short page comes back. Measured 2026-07-26: the
   table held 8,452 rows and an unbounded `select` returned exactly
   1,000; SONA alone was at 988 — twelve rows from silently truncating
   `s3_compute`'s lineage `id_map` and degrading every calc citation to
   a `mem_` id. Assume any per-entity or table-wide read will cross
   this line eventually.
10. **NEVER delete `metric_observations` rows to "clean up".** Computed
    values carry `inputs[]` arrays of observation row ids, and those
    ids are persisted in `knowledge_entries` and cited by stored
    reports. Deleting observations silently orphans the lineage of
    every historical report that cited them. The long tail of
    single-occurrence metric names is extraction output, not garbage —
    it is cheap to keep and unsafe to remove. If volume ever genuinely
    matters, paginate reads (invariant 9) or narrow what new writers
    emit; never retro-delete.

## Where the 2026-07-19 architecture plan touches the DB

| Plan element | Storage |
|---|---|
| Section-mapped extraction (R3) | per-passage section list inside `extract:{doc_id}` content_json |
| Date tags (R3) | `source_documents.published_date` populated per doc class; joined into the pool |
| Extraction focus-hash versioning (R3) | focus_hash field inside `extract:{doc_id}` content_json; mismatch → re-read |
| Sector membership (R2) | `entity_relationships` type `member_of` (stock → sector entity) |
| Sector numeric backbone (R2) | `metric_observations` per member stock (raw only); sector reads → source_documents with metadata.layer='industry' |
| Sector trusted sources + skill docs | repo files (git-versioned), not DB |
| Computed PE history (R1) | derived — computed in s3 from stored closes + EPS, never persisted as observations |
| Per-node telemetry (R0) | `data/telemetry/{run_id}.json` sidecars; `runs` keeps aggregates |
| Report manifest (R5) | inside `report_versions.sections_json` or sidecar — decide at R5 |
