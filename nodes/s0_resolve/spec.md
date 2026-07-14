# s0_resolve — run planning (deterministic)

## Purpose
Turn (ticker) into a complete run plan: company profile, sector pack,
peer set, staleness map, and the read budget. Zero LLM calls.

## Inputs
- `entities` row for the company (+ metadata: ticker, segments, aliases)
- sector pack registry (pack id from company's `belongs_to_sector` edge)
- `entity_relationships` (peer_of, supplies_to, input_cost_for edges)
- `knowledge_entries` freshness: latest macro/industry/company versions
- `source_documents` by URL (for reuse shortcuts)
- config: MAX_URLS_*, model policy

## Behavior
1. Build **company profile**: name variants for queries (from
   metadata.aliases), segment slots (e.g. M&M → PV, tractor, CV, EV),
   listed-peer set (3–6 from graph; flag if <3 → peer discovery needed).
2. Select **sector pack**; resolve the pack's macro-commodity subset
   (which commodities join the macro read plan).
3. **Staleness map**: macro entities < 7 days old → skip; sector layer
   < 30 days (or no new monthly print due) → skip; company docs by URL
   reuse (existing evidence rows).
4. Emit **read plan**: the §3 playbook table instantiated — every planned
   read with {target, queries, priority P1–P3, batch group, est. calls} —
   trimmed to budget (drop P3 first).
5. Start `runs` row; carry run_id through all nodes.

## Output (JSON)
`{company_profile, pack_id, peer_set[], macro_plan[], sector_plan[],
company_plan[], skipped_as_fresh[], budget:{planned_calls, rpd_check}}`

## Quality checklist
- [ ] Peer set nonempty (else peer-discovery task added to plan)
- [ ] Every plan entry has priority + fallback queries
- [ ] Planned calls ≤ daily budget with ≥20% headroom
- [ ] Fresh layers actually skipped (no redundant macro re-reads)
