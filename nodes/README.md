# Node Specs — shared contract

> One spec.md per workflow node (graph stages S0–S9 from
> REPORT_GEN_PLAYBOOK.md). A node's runtime prompt is assembled as:
> **spec body (§Instructions) + sector-pack overlay + context data**.
> Specs are versioned in git; changing a spec = changing the product.
> Knowledge source: ANALYST_KNOWLEDGE.md. Output target:
> REPORT_BLUEPRINT.md (frozen v0.3).

## Node index

| Node | Stage | Kind | Writes blueprint section |
|---|---|---|---|
| s0_resolve | S0 | deterministic | — (run plan) |
| s1_discover | S1 | deterministic | — (URL plan) |
| s2_extract | S2 | LLM (url_context) | — (evidence, metrics, tags) |
| s3_compute | S3 | deterministic | — (computed tables) |
| s4_business | S4 | LLM | B |
| s4_financials | S4 | LLM | D |
| s4_supply_chain | S4 | LLM | E |
| s4_management | S4 | LLM | F |
| s5_peers | S5 | LLM | G |
| s5_risks | S5 | LLM | H |
| s6_industry_macro | S6 | LLM | C |
| s7_valuation | S7 | LLM | I |
| s8_takeaways | S8 | LLM | J |
| s8_composer | S8 | deterministic | A, K + assembly |
| s9_verifier | S9 | LLM (cheap) | — (claim verification) |

## Common output envelope (every LLM synthesis node)

```json
{
  "section": "D",
  "blocks": [ <Block>, ... ],
  "claims": [ {"text": "...", "evidence_ids": ["uuid"], "confidence": 0.9} ],
  "insufficiencies": ["management guidance for FY27 margins: not found in sources"],
  "self_check": {"all_numbers_provenanced": true, "citations_resolve": true}
}
```

### Block types

```json
{"type":"narrative",   "id":"d1_growth", "title":"...", "md":"...", "citations":["evidence-uuid", "calc:roce_5y"]}
{"type":"metric_card", "id":"...", "metrics":[{"name":"ROCE","value":18.2,"unit":"percent","period":"FY26","basis":"consolidated","provenance":"calc:roce"}]}
{"type":"table",       "id":"...", "title":"...", "columns":[...], "rows":[[...]], "provenance":["calc:peer_table"]}
{"type":"ranked_list", "id":"...", "items":[{"rank":1,"title":"...","md":"...","citations":[...], "monitorable":"...", "severity":"high"}]}
{"type":"flag",        "id":"...", "check":"receivables_vs_revenue", "status":"FLAG", "severity":"medium", "md":"...", "citations":[...]}
```

## Non-negotiable rules (all LLM nodes)

1. **Grounding:** use ONLY the supplied context. A fact not in context does
   not exist. Gaps go in `insufficiencies`, never filled from memory.
2. **No arithmetic.** Numbers come from supplied evidence (cite the
   evidence UUID) or computed tables (cite `calc:<formula_id>`). Never
   derive, sum, average, annualize, or convert units yourself.
3. **Citation discipline:** every block carries `citations`; every claim
   in `claims[]` carries resolvable `evidence_ids`. A block with neither
   is invalid output.
4. **Period/basis discipline:** every number is stated with its period
   (FY26 / Q3FY26 / TTM) and basis (consolidated/standalone) exactly as
   given in context.
5. **No recommendations:** never buy/sell/hold, never target prices, never
   "attractive/expensive/cheap/rich". Percentiles, gaps, and implied
   expectations are facts — verdicts belong to the reader.
6. **Institutional prose:** dense, active voice, specific. Ban filler
   ("it is worth noting", "delved", "in conclusion"). Numbers > adjectives.
   British/Indian financial conventions (₹ crore, FY-quarters).
7. **Honest uncertainty:** conflicting sources → present both with dates
   and say which is more recent/authoritative; don't silently pick one.
8. **Envelope only:** output is the JSON envelope, nothing else. Invalid
   JSON = failed node run (no retry with "fix it" chatter; the run fails).

## Insufficiency protocol

When a spec's checklist item cannot be produced from context: emit an
`insufficiencies` entry naming (a) what's missing, (b) which source class
would supply it (so the orchestrator can schedule a follow-up read). The
composer renders material gaps as explicit "not disclosed / not found"
lines — absence of evidence is reported, never papered over.

## Sector-pack overlay

The prompt assembler injects, per company sector:
- pack KPI definitions + healthy/warning ranges (from ANALYST_KNOWLEDGE
  Part 2 / pack registry)
- pack D-adaptations, forensic signatures, valuation conventions
- pack-specific prohibited comparisons (e.g., "no EV/EBITDA for banks")
Specs mark overlay slots as `[[SECTOR_OVERLAY:<topic>]]`.

## Verification & versioning

- Numeric claims and all FLAG blocks are verified by s9_verifier (batch);
  narrative claims sampled. Failed verification → claim status `failed` →
  composer drops or flags the dependent sentence.
- Every node writes its envelope as a `knowledge_entries` row
  (layer='company', section=its blueprint letter, versioned), with
  `based_on_versions_json` pinning upstream context versions.
