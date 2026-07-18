# s7_valuation — Valuation Context writer (LLM) → section I

## Purpose
Write blueprint section I: what the market is already assuming — facts
and framing, never verdicts. Reader-question: *"What is the market
already assuming?"*

## Inputs
- `valuation_context` (calc: TTM multiples, own-history percentiles,
  peer ranks, 3y return decomposition, normalized-earnings context)
- Section D (returns/growth), G (peer table), C (cycle position) envelopes
- Evidence: any multiples/valuation commentary passages (context only)
- `[[SECTOR_OVERLAY:valuation]]` (primary multiple, conventions,
  cyclical-normalization requirement, known non-comparabilities)

## Instructions
1. **Where it trades** (metric_card + narrative): primary multiple (pack)
   + 1–2 secondary, INCLUDING P/B (calc:pb) with the book value behind
   it. The canonical sentence pattern: "trades at 32× TTM earnings —
   88th percentile of its own 5-year range [calc], and #2 of 5 in its
   peer set [calc:peer_table]". Same-period, same-basis, from calc only.
1b. **The year in the multiple** (narrative + table from calc:pe_1y_path
   when present): the 12-month PE trajectory — start/end/high/low, PE
   change vs price change (did earnings keep up with the price?). Then
   ATTRIBUTE the major moves to the year's evidenced events: guidance
   revisions (GUIDANCE EVOLUTION), risk events (SECTION H), sensitivity
   shocks (SECTION C) — each attribution cited to its sec:/evidence
   source and anchored to the month it happened. A move you cannot
   attribute is stated as unattributed — never invent a story for a
   price move. This block is the bridge between "what happened this
   year" (B–H) and "what the market repriced" — write it that way.
2. **Cyclical adjustment** (narrative, when pack flags cyclical): the
   peak/trough trap stated plainly — current multiple against NORMALIZED
   earnings context (calc: mid-cycle margin × current revenue), plus C's
   cycle-position. "8× on peak-cycle earnings" framing where applicable.
3. **Multiple ↔ fundamentals cross-check** (narrative): does the
   premium/discount vs peers line up with the growth + returns gaps from
   D and G? Where it does, say what carries it. Where it doesn't:
   "the 40% premium to peer median is not explained by growth (in line)
   or returns (2nd quartile) in available data" — legitimate finding,
   no further speculation.
4. **Implied expectations** (narrative): the qualitative reverse-DCF
   framing: what the current multiple roughly assumes (growth for how
   long, at what returns), anchored to calc where available; then ONE
   sentence each: what in B–F is consistent with that assumption, what
   strains it. Both sides, cited.
5. **Re-rating decomposition** (metric_card): calc's 3y return split
   (EPS growth × multiple change + dividends) + one sentence: did the
   stock earn its move or re-rate its way there?
6. **The bull/bear framing** (narrative closer): two short paragraphs —
   the valuation-relevant bull case and bear case, each strictly from
   cited findings in B–H. Symmetric length. No adjudication.

## Prohibited
Target prices, fair values, "attractive/expensive/cheap/rich/stretched/
undemanding", buy/sell/hold language, "we believe", DCF outputs,
un-calc'd multiples, peer multiples from memory.

## Quality checklist
- [ ] Percentile sentence present with both own-history and peer-rank
- [ ] Cyclical normalization applied when pack requires
- [ ] Premium/discount either attributed or declared unexplained
- [ ] Implied-expectations paragraph has both the consistent and the
      straining evidence
- [ ] Zero verdict vocabulary (scan against prohibited list)
