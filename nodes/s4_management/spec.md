# s4_management — Management, Governance & Guidance writer (LLM) → section F

## Purpose
Write blueprint section F. Reader-question: *"Can I trust the people
running this?"* Three pillars: guidance track record (computed), capital
allocation report card (computed), governance flag battery (evidence).

## Inputs
- `guidance_scorecard` (calc: items × actuals, delivery rates, bias)
- guidance_items pool (current/open commitments)
- computed_financials (sources-and-uses, incremental ROCE, payout funding)
- Evidence: 4-quarter concall passages (incl. dodged questions),
  AR governance notes (RPT, remuneration, auditor), shareholding/pledge,
  rating_rationale, news events
- `[[SECTOR_OVERLAY:governance]]` (sector-typical structures, e.g. MNC
  royalty norms, OEM dealer-financing recourse)

## Instructions
1. **Guidance track record** (table + narrative): render the scorecard —
   each past commitment: guided vs delivered vs verdict (beat/met/missed +
   magnitude). Then the credibility sentence: delivery rate + bias
   direction ("guides conservatively on margins, over-promises on capex
   timelines — 3 of 4 capex completions slipped ≥2 quarters
   [calc:guidance_scorecard]"). Intra-year walk-downs called out.
   **Table-cell discipline:** every cell holds THAT ROW's own value for
   THAT column — the "Actual" cell is the actual of the row's own metric
   and period, with its provenance. If the row's actual is not in
   context, the cell is "—" (and the gap goes to insufficiencies); never
   fill a cell with a number belonging to another row or metric.
2. **Current guidance** (ranked_list): every open commitment: metric,
   period, value, the assumption behind it (from transcript), and what
   would make it credible/incredible given the track record. Separate
   **management claim** vs **independently evidenced** — label each item.
3. **Capital allocation report card** (narrative + metric_card): narrate
   computed sources-and-uses (5y): where each rupee went; incremental
   ROCE vs cost of capital; M&A record (price paid → outcome, goodwill
   impairments = tuition); buyback timing vs valuation history; dividend
   consistency vs FCF (operations-funded or borrowed — calc).
4. **Governance battery** (flag blocks): render only notable items, each
   with severity: pledge level/trend (>20% WATCH, >50% FLAG), promoter
   remuneration vs PAT, royalty trend for MNC subs, RPT patterns (loans to
   group entities, promoter-family leases), board/auditor hygiene (exits,
   tenure, fees mix, qualifications, CARO), disclosure conduct (transcript
   dodges from s2, discontinued disclosures, deadline-edge results).
   Clean governance = one line saying so; don't manufacture concerns.
5. **Promoter skin-in-the-game** (metric_card): holding trend +
   distinguish pledge-invocation falls from institutional-sale falls.

## Prohibited
Character adjectives ("visionary", "seasoned"); psychoanalysis; treating
management claims as facts (label them); importing outside reputation
("known for..."); softening a computed miss.

## Quality checklist
- [ ] Every scorecard row cites transcript evidence + actuals calc
- [ ] Claim-vs-evidenced labels on all current guidance items
- [ ] Incremental-ROCE sentence present (value creation on new capital)
- [ ] Each governance flag has severity + the specific disclosure cited
- [ ] Dodged-question patterns surfaced if s2 captured them

## Golden example (credibility sentence)
"Across 11 tracked commitments from FY24–FY26 calls, management delivered
8 (73%) [calc:guidance_scorecard]; both misses in the set were capex
timelines, both slipping 2+ quarters [ev:…, ev:…] — forward capex dates
below should be read with that bias."
