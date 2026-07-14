# Sector Pack Registry — schema

> One JSON file per sub-sector (taxonomy: DATA_SOURCES.md §1). A pack is
> ALL the sector-specific behavior in the system; everything not in a pack
> is universal. Knowledge source: ANALYST_KNOWLEDGE.md Part 2.
> Consumers: s0_resolve, s1_discover, s3_compute, the prompt assembler
> (overlay slots), s8_composer.

## Fields

| Field | Type | Consumed by | Meaning |
|---|---|---|---|
| `pack_id` | str | all | stable id, matches filename |
| `label` | str | composer | display name |
| `sub_sectors` | [str] | s0 | taxonomy entries this pack covers |
| `version` | int | all | bump on any change; runs pin it |
| `snapshot_vitals` | [{metric_id, label, unit, calc}] | s8_composer | ≤8 sector vitals for section A (universal four are hardcoded: mcap, P/E, div yield, ROE) |
| `macro_commodity_subset` | [str] | s0 | entity names joining the macro read plan |
| `sector_queries` | [{q, blocks, results}] | s1 | the sector overlay query bank (slots allowed) |
| `compute` | object | s3 | `skip_modules` [str], `sector_kpis` [{formula_id, label, inputs, norm_healthy, norm_warning}] |
| `peer_table_columns` | [str] | s3/s5_peers | pack columns appended to the universal set |
| `valuation` | object | s3/s7 | `primary_multiple`, `secondary` [str], `cyclical` bool, `conventions` str |
| `overlays` | {slot: str} | prompt assembler | prose injected at `[[SECTOR_OVERLAY:<slot>]]` — slots: business_model, financials, supply_chain, governance, peers, risks, industry, valuation, takeaways |
| `forensic_signatures` | [str] | s3 (checks) + financials overlay | sector-specific fake-it patterns to test/watch |
| `data_cadence` | [{print, when, source}] | s6/risks monitorables | what publishes when |
| `classic_mistakes` | [str] | all synthesis overlays | guardrails appended to every synthesis prompt for this sector |

## Rules
- Overlay prose is INSTRUCTIONAL (how to analyze), never factual claims
  about any specific company — facts must come from evidence at runtime.
- `norm_healthy`/`norm_warning` ranges are context for interpretation and
  must be quoted as "sector norm" in output, never as company data.
- A pack never contradicts a node spec; it specializes it. Conflicts →
  the spec wins, fix the pack.
- New sector onboarding: copy `_TEMPLATE` structure from any pack, fill
  the 7-point template of ANALYST_KNOWLEDGE (S-template), version=1.
