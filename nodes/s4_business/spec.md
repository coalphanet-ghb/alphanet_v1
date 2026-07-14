# s4_business — Business Overview writer (LLM) → section B

## Purpose
Write blueprint section B: how the company makes money, with every moat
claim tied to a numeric fingerprint. Reader-question: *"How does this
company actually make money?"*

## Inputs
- Evidence: annual_report, investor_presentation, screener, concall,
  news passages (B-relevant)
- computed_financials (revenue mix if extracted, margin stability series,
  unit-economics inputs)
- `[[SECTOR_OVERLAY:business_model]]` (model essence, unit-economics
  definitions, value-chain map)

## Instructions
1. **Plain-language opener** (narrative block): what it sells, to whom,
   how it earns — 4–6 sentences a non-specialist can follow. No jargon,
   no mission-statement language.
2. **Revenue mix table** (table block): segment/product/geography/customer
   -type splits with % and trend arrow — only splits present in evidence;
   name the period. Mix SHIFT commentary: what the mix is moving toward
   and why it matters for margins (cite).
3. **Revenue quality ladder** (narrative): classify each major revenue
   stream — contracted/annuity → recurring → order-book-backed →
   transactional-cyclical. State the blend's implication for earnings
   visibility.
4. **Customer & concentration** (narrative + metric_card): top-customer/
   top-5 share where disclosed; flag >20% single-customer dependence
   (cross-reference: E owns the dependence analysis — here state the
   revenue-side fact only).
5. **Moat assessment** (ranked_list): for EACH claimed advantage, apply
   the fingerprint test from ANALYST_KNOWLEDGE §B: pricing power → gross
   margin stability through input cycles (calc); switching costs →
   retention/tenure evidence; scale → margin+asset-turn superiority vs
   peers (calc:peer_table); brand → realization premium; licenses →
   count/status. Verdict per claim: **held / partially / not evidenced**.
   An unevidenced moat is stated as such — that IS the finding.
6. **Value-chain position** (narrative): who captures margin in this
   chain; company's capture share and direction (integration moves).
7. **Unit economics** (metric_card, if pack defines one): the per-unit
   metric trend from calc, interpreted in one line.

## Prohibited
Adjectival moats without fingerprints; strategy-deck vocabulary
("marquee", "robust", "well-poised"); any number not in context.

## Quality checklist
- [ ] A stranger could explain the business after the opener
- [ ] Every moat claim has a fingerprint test and verdict
- [ ] Mix table periods stated; shifts interpreted, not just listed
- [ ] Concentration numbers cited to disclosure source
- [ ] claims[] populated for every factual assertion

## Golden example (moat verdict)
"Management describes switching costs from multi-year platform
qualifications [ev:…]. Fingerprint: gross margin held 41–43% through the
FY23 steel spike while peer average fell 480bps [calc:gm_stability,
calc:peer_table] — consistent with pass-through contracts plus qualified-
supplier stickiness. Verdict: **held**."
