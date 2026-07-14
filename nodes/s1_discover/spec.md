# s1_discover — URL discovery (deterministic, ddgs)

## Purpose
Execute the read plan's queries against ddgs and produce the final,
prioritized, pre-flighted URL plan. Zero LLM calls.

## Inputs
- s0 read plan (queries per target, priorities, batch groups)
- domain tables: TIER1_DOMAINS, DEPRIORITIZED, BLOCKED (nseindia, known
  paywalls), LEARNED_FAILURES (from past run logs)

## Behavior
1. **Query expansion:** fill slots ({company}, {ticker}, {quarter}×4,
   {fy}, {segment}); doc-hunt queries fetch 5 results, data/news 3.
2. **Concall shortcut:** fetch screener concall-tab URL first; if it
   yields the 4 transcript links, cancel per-quarter searches.
3. **Rerank** per query: Tier-1 domains first; drop BLOCKED and
   LEARNED_FAILURES; dedupe across queries (first-seen wins);
   round-robin so no query hogs a layer budget.
4. **Pre-flight** (requests.head/get, 5s timeout, no JS): drop 404/410,
   login redirects, >35MB content-length. Advisory only — Gemini's
   fetcher differs; borderline cases stay in.
5. Assemble **URL plan**: per read-target {urls[], call grouping (solo vs
   batch of 2–3), extraction doc_class}; enforce playbook budget;
   log the plan (auditable input to S2).

## Output (JSON)
`{reads: [{target, doc_class, urls[], batch, priority, queries_used[]}],
dropped:{blocked[], preflight_failed[], over_budget[]}}`

## Quality checklist
- [ ] Every P1 target has ≥1 surviving URL or an explicit gap entry
- [ ] No BLOCKED domain in plan; no duplicate URLs
- [ ] Concall coverage: 4 quarters resolved or gaps named per quarter
- [ ] ddgs politeness: 1s between queries; failures logged not fatal
