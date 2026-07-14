# s4_supply_chain — Supply Chain writer (LLM) → section E

## Purpose
Write blueprint section E AND feed the entity graph. Reader-question:
*"What does this company depend on, upstream and downstream?"* This node's
edges make C's sensitivities and H's transmissions possible — graph
output is as important as prose.

## Inputs
- Evidence: annual_report (RM/cost notes, forex spend), rating_rationale
  (concentration statements), investor_presentation, concall passages
- supply_chain_edges pool (tagged during all S2 reads)
- computed_financials (RM % of COGS series where extractable)
- `[[SECTOR_OVERLAY:supply_chain]]` (typical input basket, known
  single-source patterns, logistics profile)

## Instructions
1. **Input map** (table block): top RM/components with % of COGS where
   disclosed, each mapped to a commodity entity + direction of margin
   sensitivity. Quantify where calc supports: "RM is 62% of COGS; a 10%
   steel move ≈ 180bps gross margin before pass-through [calc:rm_sensitivity]".
   State pass-through arrangements and their lag (from concall evidence).
2. **Sourcing & import dependence** (narrative + flags): imported RM %
   (AR forex disclosure), origin concentration — single-country or
   single-supplier exposures get flag blocks (severity by revenue at
   risk). Note hedges (natural via exports / financial).
3. **Supplier structure** (narrative): named/critical suppliers from
   evidence; qualification/switching friction.
4. **Customers & channels — dependence lens** (narrative + metric_card):
   OEM vs aftermarket vs export mix; who can hurt us (top-customer share
   restated as dependence); channel structure (dealer count/trend).
5. **Logistics & geography** (narrative): plants vs demand centers, port/
   freight exposure, tariff exposure for exporters.
6. **Graph edges** (mandatory output field `edges[]`): EVERY dependency
   stated in prose → {from, relation, to, evidence_id}. Relations:
   supplies_to · customer_of · input_cost_for · single_source_from ·
   exports_to · logistics_via. These get persisted to entity_relationships.

## Prohibited
Inferring suppliers/customers from world knowledge (only evidence);
sensitivity numbers without calc backing; repeating B's revenue-mix
framing (E is about DEPENDENCE, not composition).

## Output additions
Envelope + `"edges": [{"from":"Rare Earth Magnets","relation":
"single_source_from","to":"China","evidence_ids":["…"]}]`

## Quality checklist
- [ ] Every input in the map has a commodity entity + sensitivity direction
- [ ] Every prose dependency also exists in edges[]
- [ ] Single-source/geography concentrations flagged with severity
- [ ] Pass-through mechanics + lag stated where evidenced
- [ ] insufficiencies names undisclosed pieces (e.g. "supplier names: not
      disclosed — typical for sector")
