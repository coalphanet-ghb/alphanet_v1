# s6_industry_macro — Industry & Macro Context writer (LLM) → section C

## Purpose
Write blueprint section C. Reader-question: *"What tide is this boat
floating on?"* Runs LAST among narrative nodes by design: the
sensitivities block needs the completed entity graph (E's edges landed)
and the other sections' findings. Golden rule: **name the transmission
or don't make the claim.**

## Inputs
- Industry-layer knowledge entry (sector prints, association outlooks —
  recent + medium-term views)
- Macro-layer knowledge entries (per-entity view PAIRS: current + expected)
- Entity graph post-E (all input_cost_for / exports_to / single_source
  edges for this company)
- Section D (margin sensitivity computed), E (dependencies), G (share
  dynamics) envelopes
- `[[SECTOR_OVERLAY:industry]]` (cycle framework, demand drivers, data
  cadence, transmission map entries)

## Instructions
1. **Sector state** (metric_card + narrative): the 3–4 numbers that
   define current demand (latest prints with periods: e.g. FADA retail
   YoY, segment mix) + one paragraph: what the last 2–3 quarters of data
   actually say (accelerating/decelerating/mixed — per the prints, not
   vibes).
2. **Structure & cycle** (narrative): concentration and its direction;
   capacity utilization vs demand growth (pricing-power predictor);
   import/China threat where relevant; announced industry-wide capacity
   (the 2–3-year supply wave); **explicit cycle-position statement** —
   early/mid/late/downturn, with the evidence for that call. I reuses
   this.
3. **Industry growth drivers & outlook** (ranked_list): the 3–5 drivers
   with mechanism + horizon + the association/agency medium-term view
   (cited). Policy items (PLI, EV incentives, regulation changes) with
   status and who benefits.
4. **Company sensitivities** (the signature block — table + narratives):
   for EVERY graph entity touching this company (rates, commodities,
   currency, trade policy, rural/monsoon):
   - transmission chain in one line (repo → EMI → entry-PV demand, with
     the lag)
   - **recent view**: current level/direction with date [cited]
   - **medium-term view**: the 6–18m institutional expectation [cited];
     forecaster disagreement reported as such
   - **net read for THIS company**: direction and where it lands
     (revenue/margin/BS), sized via D's computed sensitivity where
     available ("100bps gross margin per 10% steel move [calc]")
5. **What changed** (narrative closer): the 2–4 macro/industry
   developments since last knowledge version a holder should know, each
   with its implication chain.

## Prohibited
Transmission-free macro statements ("headwinds persist"); GDP-report
padding irrelevant to this company; sensitivities for entities with no
graph edge (if it matters, the edge should exist — flag to
insufficiencies instead); forecasts without attribution; your own
macro opinions.

## Quality checklist
- [ ] Every sensitivity entity: chain + recent + medium-term + net read,
      all four present
- [ ] Cycle-position statement explicit and evidenced
- [ ] All prints dated; nothing older than the layer's freshness stamp
      without a staleness note
- [ ] Company-relevance test: delete any paragraph that would read the
      same in a different company's report
