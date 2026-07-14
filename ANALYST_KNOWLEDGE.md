# AlphaNet — Analyst Knowledge Base (v0.1 draft)

> The master reference of HOW to analyze, at institutional depth. Node
> specs (skills.md per node) get distilled FROM this document — the node
> prompt tells the model exactly what to check and how to reason, so
> nothing analytical is left to a cheap model's improvisation.
> Companion docs: REPORT_BLUEPRINT.md (what we output, frozen v0.3),
> REPORT_GEN_PLAYBOOK.md (how we gather), DATA_SOURCES.md (where from).
>
> Two-part structure: PART 1 universal knowledge (block-wise, B→J) +
> numeric hygiene; PART 2 sector packs + the Python compute library.
> Rule zero everywhere: **models interpret, Python computes, every claim
> cites.**

---

# PART 1 — UNIVERSAL ANALYTICAL KNOWLEDGE

## 0. Numeric & reporting hygiene (applies to every node)

- **Units:** Indian filings mix ₹ crore (10⁷), ₹ lakh (10⁵), and millions.
  Normalize EVERYTHING to ₹ crore at extraction; store the original unit.
  1 crore = 10 million; 100 lakh = 1 crore. USD figures: state FX rate used.
- **Fiscal year:** April–March. FY26 = Apr 2025–Mar 2026. Q1=Apr-Jun,
  Q2=Jul-Sep (festive build), Q3=Oct-Dec (festive+wedding), Q4=Jan-Mar.
  Never compare an Indian company's "FY25" to a CY24 global peer without
  saying so.
- **Consolidated vs standalone:** prefer CONSOLIDATED for analysis;
  standalone matters for (a) dividend capacity, (b) spotting losses parked
  in subsidiaries (large gap between cons and standalone PAT = investigate
  subsidiaries), (c) banks where subsidiaries distort. Never mix bases in
  one time series — tag every metric_observation cons/standalone.
- **TTM:** trailing 4 quarters, built only from same-basis quarters.
  Growth on TTM beats single-quarter YoY for judging trend.
- **Ind-AS quirks:** Ind-AS 116 (FY20+) capitalizes leases → inflates
  EBITDA and debt vs pre-FY20 history (retail, aviation, QSR worst
  affected) — flag when comparing across the boundary. Ind-AS 115 revenue
  recognition for EPC/real estate (percentage-of-completion vs handover)
  changes revenue meaning. Other comprehensive income ≠ PAT.
- **Base-year discipline:** any CAGR quoted must name both endpoints; a
  CAGR off a covid/cyclical-trough base is flagged as flattered. Compute
  3y AND 5y AND TTM momentum; disagreement between them IS the finding.
- **Restatements/exceptionals:** track "exceptional items" separately;
  compute margins ex-exceptionals; repeated "exceptional" losses (3+ years)
  are operating losses wearing a costume — say so.
- **Missing ≠ zero.** Undisclosed segments/metrics render as "not
  disclosed"; a company that STOPS disclosing a metric it used to publish
  (order book, volume split) is itself a yellow flag worth stating.

## B. Business Overview — how to analyze a business model

**Revenue quality ladder** (rank the mix): contracted/annuity (utilities,
towers) > recurring repeat-purchase (FMCG, pharma chronic) > order-book
backed (capital goods; check book-to-bill) > transactional cyclical
(commodities, OEM sales). State where each segment sits.

**Moat tests — evidence over adjectives.** A claimed moat must show up in
numbers, else it's marketing:
- Pricing power → gross margin stability through input-cost cycles
  (compute gross margin σ across 5y vs peers)
- Switching costs → client retention / repeat revenue %, long contract
  tenures
- Scale/cost moat → margin AND asset-turn superiority vs peers at similar
  mix
- Brand → premium realization vs category (ASP vs peers), A&P spend
  leverage
- Regulatory/license → count of licenses/approvals (banking licence, USFDA
  approvals, defence clearances)
- Network effects → take-rate stability with rising volumes (exchanges,
  platforms)
Verdict format: moat claim → the numeric fingerprint we checked → held/not.

**Value-chain position:** who captures the margin in this chain (brand vs
manufacturer vs distributor)? Company's share of end-product value
(content per vehicle for ancillaries, realization per tonne for
converters). Backward/forward integration moves and their margin logic.

**Customer/geography concentration:** top-1/top-5/top-10 customer share of
revenue (AR discloses >10% customers under Ind-AS 108); export share by
region; the concentration number pairs with section E's dependence lens.

**Unit economics where applicable:** per-unit realization, per-unit EBITDA
(auto), per-sq-ft (retail), per-bed (hospitals), ARPU (telecom), AUM
take-rate (AMC). Trend of the unit metric > trend of the aggregate.

## C. Industry & Macro — transmission mechanisms, not weather reports

**The test for every macro statement: name the transmission.** Bad: "high
rates are a headwind." Good: "each 50bp repo cut historically lifts
entry-PV demand with a 2–3 quarter lag via EMI affordability; ~70% of PVs
are financed."

**Standard transmission map (India):**
- Repo rate → lending rates (banks reprice with 1–2Q lag) → EMI-financed
  demand (autos, housing, durables) + corporate capex IRRs + NBFC cost of
  funds (immediately, via CPs/NCDs)
- INR depreciation → (+) exporters IT/pharma/chem/ancillaries with export
  mix, (–) importers (oil, electronics, capital goods with import content),
  (–) FX-debt carriers; hedging policy determines the lag
- Crude ↑ → (–) paints, tyres, FMCG (packaging), aviation, OMC marketing
  margins; (+) upstream, (mixed) city gas; fuel price → freight cost →
  everything logistics-heavy
- Steel/base metals ↑ → (–) auto, capital goods, construction margins with
  a ~1–2 quarter lag (inventory + contract resets); ancillaries with
  pass-through clauses lag but recover; check who has pass-through
- Monsoon/rural income → tractors, 2W, entry PV, agrochem, rural-heavy FMCG
  (with a season's lag); MSP hikes same channel
- Govt capex cycle → EPC order books → capital goods → cement/steel demand
  (order → revenue conversion 12–24 months)
- Global: Fed path → FII flows → valuation multiples (not earnings); US/EU
  demand → IT deal flow, pharma generics, textile/chem exports; China
  stimulus/dumping → metals & chemicals pricing

**Industry structure checklist:** concentration (top-3 share, rising or
falling), capacity utilization vs demand growth (pricing power predictor),
import threat (China landed cost vs domestic price), regulatory posture
(PLI support vs price control), technology disruption exposure (EV vs ICE,
GenAI vs IT services billing), entry barriers actually observed (failed
entrants count).

**Cycle position:** where are we — capacity utilization %, price premiums/
discounts prevailing, inventory levels in channel, new capacity announced
industry-wide (supply wave 2–3 years out). State the cycle stage explicitly;
valuation section reuses it.

**Recent vs medium-term view (per frozen blueprint):** for every
sensitivity entity output BOTH: current level/direction (with date) AND
the 6–18 month expected path per cited institutional forecasts (RBI SPF,
IMF, IEA, association projections). Disagreement among forecasters is
itself reportable.

## D. Financial Analysis — the deep block

### D1. P&L analysis

**Growth decomposition (compute, then interpret):**
- Revenue growth = volume growth + realization/price growth + mix effect
  (+ consolidation effect if M&A — strip it: organic vs reported)
- Flag: growth driven >60% by price in a falling-volume business = share
  loss masked by inflation; the reverse (volume-led) is higher quality
- Compare company growth vs industry print (SIAM/sector data) → share
  gain/loss per year, stated in points

**Margin architecture:**
- Gross margin = pricing power vs input costs (RM basket analysis per
  sector pack); EBITDA margin adds operating leverage (employee + other
  opex absorption); EBIT adds D&A (capex intensity showing up); PAT adds
  finance cost + tax + other income
- Margin bridge YoY (compute each component's contribution): RM delta,
  employee delta, other-opex delta, mix. Attribute, don't hand-wave
- Operating leverage: ΔEBITDA% / ΔRevenue% over multi-year; high fixed-cost
  businesses swing both ways — state the elasticity
- Peer-relative: margin gap vs best peer, and whether it's mix, scale, or
  efficiency (ties to G)

**P&L quality checks (all computed as flags):**
- Other income / PBT > 15–20% sustained → earnings are treasury, not
  operations (check what the cash is FOR)
- Effective tax rate << 25.17% (new regime) or << peers without stated
  exemption (SEZ, 115BAB new-mfg 15%) → question sustainability;
  one-off tax reversals inflating PAT → normalize
- EPS growth vs PAT growth divergence → dilution (count share issuances,
  ESOP overhang, warrants); buyback-flattered EPS → state it
- Exceptional items frequency (see hygiene) — compute margins both ways
- Depreciation rate (dep/avg gross block) drifting DOWN while asset base
  ages → PAT inflation lever; compare policy vs peers
- Interest capitalization during construction — check CWIP notes; expensed
  vs capitalized interest shifts PAT
- Revenue recognition notes: bill-and-hold, long credit periods offered,
  channel incentives netting — read AR accounting-policy note when DSO
  moves

### D2. Balance Sheet analysis + forensic battery

**Strength metrics (compute):** net debt/EBITDA (<1 comfortable, >3
stressed for most industrials), D/E, interest coverage (EBIT/interest; <2
is distress territory, tag vs rating rationale view), current ratio,
quick ratio, cash + liquid investments vs ST debt (liquidity wall),
debt maturity profile if disclosed.

**DuPont — always compute, 5-stage:**
ROE = (PAT/PBT) × (PBT/EBIT) × (EBIT/Sales) × (Sales/Avg Assets) ×
(Avg Assets/Avg Equity) = tax burden × interest burden × operating margin
× asset turnover × leverage.
The NARRATIVE requirement: say WHICH lever drives ROE and its trend. An
ROE held up by rising leverage while operating margin decays is the
opposite of quality even at the same headline number. ROCE = EBIT(1-t)/
(avg debt+equity); compare ROCE vs estimated cost of capital (~11–13% for
India mid-caps) — value creation verdict.

**Working capital forensics (compute all):**
- DSO = receivables/revenue × 365; DIO = inventory/COGS × 365; DPO =
  payables/COGS × 365; CCC = DSO + DIO − DPO. 5-year trend each.
- **The classic flag:** receivables growing materially faster than revenue
  for 2+ years (DSO drift >15–20 days) = channel stuffing / fictitious
  sales / weakening customers. Pair with: any receivables factoring
  disclosed? Unbilled revenue rising (EPC/IT)?
- Inventory building ahead of demand → obsolescence risk (check
  write-off history); payables stretching → cash flow flattered
  temporarily; negative-WC models (OEMs, FMCG, retail) losing their
  float = deterioration signal even while "WC is still negative"
- Loans & advances to related/group parties, inter-corporate deposits →
  cash leakage channel; capital advances aging without assets arriving

**Asset-side checks:**
- CWIP aging: CWIP > 20–25% of gross block for 2+ years without
  commissioning = capex black hole (or capitalized-expense hideout)
- Goodwill/intangibles from acquisitions vs subsequent impairments =
  capital-allocation report card (feeds F)
- Investment book: what is non-core (real estate, group companies?) —
  holding-company behavior inside an operating company
- **Cash yield test:** interest income / average (cash + liquid
  investments) should ≈ 4–7%. Materially lower → the cash may not exist
  as stated (the Satyam test), or is trapped/pledged
- **Borrowing cost test:** interest expense / average gross debt should ≈
  7–11% for most corporates. Far below → understated debt (guarantees,
  off-BS); far above → expensive hidden borrowings or intra-year peak debt

**Liability-side checks:** contingent liabilities / net worth (>25–30% =
material; read what they are — tax disputes usually survivable, guarantees
to group companies are not), guarantees given to subsidiaries/promoter
entities, pledged promoter shares (any pledge >20% of promoter holding =
governance flag; rising pledge = distress), preference capital/quasi-debt.

**Off-BS & structure:** operating leases pre-Ind-AS-116 history,
factoring/securitization of receivables, LC/BG utilization (working
capital stress proxy), subsidiary debt not consolidated (JVs at equity
method carrying leverage).

### D3. Cash Flow analysis

**Quality of earnings (compute):**
- CFO/EBITDA sustained ≥ 70–80% for industrials (banks N/A); < 50% for
  2–3 years = earnings not converting to cash → find WHERE it leaks
  (usually WC, sometimes fictional revenue)
- CFO pre-tax / EBITDA and CFO/PAT both, 5-year medians, not single years
  (WC timing noise)
- Accrual ratio (Sloan): (PAT − CFO − CFI)/avg total assets; persistently
  high accruals predict earnings reversals
- Cumulative 5y test: ΣPAT vs ΣCFO — the long-window truth teller

**FCF construction:** FCF = CFO − capex (use "purchase of PP&E+CWIP" from
CFI, not the BS delta). Report FCF margin and FCF conversion (FCF/PAT).
Distinguish growth capex vs maintenance capex (estimate maintenance ≈
depreciation as crude floor; management commentary refines).

**Where the cash goes (CFI/CFF pattern read):**
- CFI: capex into what (segment disclosures/MD&A) — does deployment match
  stated strategy? Acquisitions at what multiples? "Investments" that are
  really parked treasury vs strategic
- CFF: the financing personality — serial equity diluter / debt-funded
  dividend payer / genuine deleverager / buyback-while-borrowing. Compute:
  dividends + buybacks vs FCF (payout funded by operations or by
  borrowings?)
- Interest paid (CFF/CFO per Ind-AS) vs P&L interest — large gaps =
  capitalization
- Tax paid (CFO) vs tax provision (P&L) — persistent underpayment =
  deferred-tax games or disputes accumulating

### D-cross. Cross-statement triangulation (the fraud lens)

Run as a battery; each outputs OK/FLAG(severity)+evidence:
1. Revenue↑ + DSO↑↑ + CFO flat → aggressive recognition
2. PAT↑ + cash tax paid flat/down → paper profits
3. EBITDA↑ + CFO/EBITDA falling → WC absorption or fake EBITDA
4. Cash balance high + borrowings rising + interest income low → cash
   is fictitious/encumbered (why borrow at 9% while "holding" cash at 2%?)
5. Capex high for years + asset turnover falling + no commissioning →
   CWIP hideout
6. Dep rate falling + gross block aging → PAT propping
7. Interest expense implies rate ≠ disclosed borrowing mix → hidden debt
8. Promoter pledge rising + dividend hikes + buybacks → cash extraction
   pattern
9. RPT sales/purchases growing faster than third-party revenue → transfer
   games
10. Auditor: resignation/qualification/CARO adverse remarks/fee anomalies →
    weight heavily; a Big-4 exit mid-tenure is a red alert
11. Subsidiary/JV losses growing while standalone shines → loss parking
12. Frequent auditor/CFO/CS/independent-director exits → cluster = alarm

**Composite screens (compute, report as context not verdicts):**
- Piotroski F-score (9 tests) — trajectory of fundamentals
- Altman Z″ (emerging-market variant) — distress zone check, industrials
  only
- Beneish M-score (8-variable) — earnings-manipulation probability, data
  permitting; components matter more than the composite

## E. Supply Chain analysis

- **Input mapping:** top 3–5 RM/components by % of COGS (AR "cost of
  materials" + notes); each mapped to a commodity entity with its price
  series → quantify margin sensitivity ("100bps gross margin per 10% steel
  move" style, computed from disclosed RM share)
- **Import dependence:** imported RM % (AR forex-spend disclosure), origin
  concentration (China single-source = tariff/geopolitical exposure),
  hedging policy (natural hedge via exports?)
- **Supplier structure:** named/critical suppliers, single-source
  components (auto semiconductors 2021 as archetype), supplier
  financial health if disclosed
- **Customer/channel:** OEM vs aftermarket vs export mix; dealer network
  size/trend; customer concentration re-stated as DEPENDENCE (who can hurt
  us) vs B's revenue-mix (where money comes from)
- **Logistics/geography:** plant locations vs demand centers, port
  dependence for exporters, freight cost % of sales sensitivity
- **Output = graph edges:** every finding lands as entity_relationships
  (supplies_to, input_cost_for, exports_to, single_source_from) — this
  section FEEDS C's sensitivity block and H's transmission chains

## F. Management, Governance & Guidance

**Guidance track record (the signature block):**
- Extract every forward commitment from each of the last 4+ concalls:
  metric, period, stated value/range/direction. Store as guidance_items
- Join vs actuals when the period closes → hit/miss/beat, and the
  DIRECTION of misses (serial over-promisers vs sandbaggers)
- Score honestly: >75% delivery = credible; systematic overshoot on capex
  timelines and demand forecasts = discount all forward claims and SAY SO
- Also track guidance REVISIONS intra-year (walking down quietly)

**Capital allocation report card (compute + narrate):**
- 5y sources & uses: where did every rupee of CFO + fundraise GO
  (capex/M&A/dividends/buybacks/debt paydown/cash pile)?
- Incremental ROCE: ΔEBIT(1−t) / Δcapital-employed over rolling 3y —
  is new capital earning above cost of capital?
- M&A record: price paid vs subsequent segment performance; goodwill
  impairments = tuition paid
- Buyback timing vs valuation history (bought high?); dividend policy
  consistency vs FCF

**Governance flags (India-specific battery):**
- Promoter holding trend (rising = skin in the game; falling via pledge
  invocation ≠ falling via stake sale to institutions — distinguish)
- Pledge % of promoter holding (>20% flag, >50% red), pledge purpose
- Promoter remuneration vs PAT (>5% of PAT for non-founder-scale = flag),
  remuneration growth vs profit growth
- Royalty/brand-fee payouts to parent (MNC subsidiaries: trend as % of
  sales; hikes without shareholder vote history)
- RPT battery: loans to promoter entities, purchases/sales with group
  firms, real-estate leases from promoter family — trend & arm's-length
- Board: independent-director tenure/exits, audit-committee composition,
  frequency of "leave of absence" patterns
- Auditor: tenure, network firm size vs company scale, fees mix
  (audit vs non-audit), resignations with vague reasons
- Disclosure conduct: results delayed to the 45-day deadline habitually,
  concall discontinued after bad quarters, analyst-question dodging
  patterns (qualitative but citable from transcripts)
- Track promised-vs-delivered on non-financial commitments too (demerger
  timelines, stake sales, deleveraging promises)

## G. Peer Comparison

- **Peer-set discipline:** 3–6 names; same dominant business (not just
  same GICS bucket); note size mismatch explicitly; include one global
  reference peer where relevant (e.g., Bosch for ancillaries) as context
  only, not in Indian valuation stats
- **Normalization before comparing:** same fiscal basis, consolidated,
  ex-exceptionals margins, same-period multiples (all TTM); adjust for
  Ind-AS 116 asymmetries where mix of old/new data
- **The comparison set (compute the table):** growth (3y revenue CAGR),
  margin (EBITDA or sector equivalent), returns (ROE/ROCE), leverage
  (ND/EBITDA), WC intensity (CCC), capex intensity, valuation (sector
  primary multiple, TTM) + sector-pack columns
- **The narrative rule: explain gaps or don't state them.** A P/E premium
  must be attributed: superior growth? returns? governance? mix? If the
  premium can't be explained by fundamentals, SAY it can't — that IS the
  finding (either mispricing or an intangible we can't verify)
- **Rank honestly:** where the company is best-in-class, mid-pack, worst.
  Every "worst" cell is a candidate risk → feeds H (frozen blueprint
  ordering: G before H, deliberately)

## H. Risks

- **Structure per risk (all five fields mandatory):** name → transmission
  chain (via graph entities) → current evidence (cited) → severity
  (impact on earnings/BS if it hits: quantify order-of-magnitude where
  possible) → **monitorable** (the specific print/date that updates it)
- **Coverage checklist (avoid recency-bias risk lists):** demand cycle,
  input costs, customer concentration, supplier/single-source, competition
  /disruption (incl. tech transitions), regulatory/policy, leverage/
  liquidity/refinancing, governance/promoter, execution (capex/M&A
  integration), FX, litigation/contingent liabilities, key person,
  climate/physical where material
- **Source hierarchy:** rating rationale risk sections (professionally
  triaged) > AR risk factors (boilerplate-heavy; extract the specific) >
  concall Q&A pushback (what analysts probe = live worries) > news >
  G's worst-cells > forensic flags from D
- **Ranking:** severity × nearness; cap at 6–8 ranked entries + a
  "structural watch" tail; never pad
- **Symmetry duty:** if a risk is priced/known (per I), say so — a risk
  section is not a short thesis

## I. Valuation Context (facts & framing, never verdicts)

- **Multiple selection by business model:** stable earners → P/E;
  leverage-divergent or D&A-heavy comparisons → EV/EBITDA; financials →
  P/B (with RoE cross-ref) or P/ABV where NPAs distort; loss-making
  growth → EV/Sales (state why); cyclicals → NORMALIZED earnings or
  P/B at cycle position; asset businesses → EV/tonne (cement), EV/MW
  (power), per-key (hotels), per-bed (hospitals). The sector pack sets the
  primary; report 2–3, not seven
- **Percentile framing (compute):** current multiple vs OWN 5y/10y
  distribution (median, band, current percentile) and vs peer set (rank).
  Language: "trades at 32× TTM earnings — 88th percentile of its own 5y
  range, and #2 of 5 in its peer set"
- **The cyclical trap (state when relevant):** low P/E on peak-cycle
  earnings is expensive; high P/E at trough is cheap. Anchor with
  mid-cycle margin × current revenue as normalized-earnings context
- **Multiple ↔ fundamentals cross-check:** premium vs peers justified by
  growth+returns gap? Rough tools: PEG as sanity (not gospel), the
  "what growth for how long" implied-expectations framing (qualitative
  reverse-DCF: at 40×, market roughly assumes mid-teens earnings growth
  for a decade — is anything in D/F consistent with that?)
- **What changed:** re-rating vs earnings — decompose 3y stock return into
  EPS growth + multiple change + dividends (compute). A stock that
  "worked" purely on re-rating has a different risk than one that earned it
- **Hard lines:** no target price, no fair value, no buy/sell language,
  no "attractive/expensive" verdicts — percentiles and implied
  expectations are facts; conclusions belong to the reader

## J. Key Takeaways — synthesis discipline

- Exactly 3 positives + 3 negatives, each ≤ 2 lines, each citing its
  section's strongest evidence; no positive without a number, no negative
  without a transmission
- 3 monitorables with dates/events (next quarterly print, specific data
  release, capacity commissioning, regulatory decision)
- Tone check before emit: would both a bull and a bear call this fair?
  If either would call it cheerleading/hit-piece, rebalance
- Nothing new appears here — J only compresses what B–I established

---

# PART 2 — SECTOR KNOWLEDGE PACKS

> Depth tiers: pilots (auto OEM, auto ancillaries) = full depth. Banks =
> full depth (structurally different; proves the pack concept). Major
> groups = solid working packs. Everything else gets authored at
> onboarding using the SAME template: business-model essence → the
> defining KPIs (with norms) → D-adaptations → sector forensics → peer/
> valuation conventions → data cadence → classic analytical mistakes.

## S1. Auto OEM (PV / 2W / CV / tractors) — PILOT

**Model essence:** cyclical assembler capturing brand + distribution
margin; profitability = volume × (realization − RM basket) − fixed-cost
absorption. Negative working capital when healthy (dealers pay upfront,
suppliers financed 60–90 days) — WC turning positive is an early stress
signal.

**Defining KPIs:** monthly wholesale (SIAM) AND retail (FADA) volumes +
the gap between them (= channel inventory build/drain; >45–50 days PV
inventory is discount-war territory); market share by segment; ASP/blended
realization; EBITDA margin (PV healthy 8–12%, 2W 13–18% for leaders, CV
cyclical 5–11%, tractors 15–20%); discount levels; capacity utilization
(pricing power above ~80%); order backlog for launch-driven models; EV %
of volumes + per-unit EV economics vs ICE.

**D-adaptations:** D1 growth MUST decompose volume × realization × mix
(all published); RM basket = steel, aluminium, copper, plastics/crude
derivatives, precious metals in catalysts — margin bridge vs commodity
index with ~1–2Q lag; other-income watch (customer-advance float for
tractor/2W cos). D2: dealer/channel financing recourse, capex cycle
(new platform ₹1,500–4,000cr; peak-capex years depress ROCE — normalize),
capitalized R&D (% of revenue capitalized vs expensed — aggressive
capitalizers flatter PAT; compare policy across OEMs). D3: customer
advances swelling CFO (tractors, EV bookings) — strip to judge underlying.

**Sector forensics:** discount escalation hidden as "marketing expense"
vs netted from revenue (policy differs — check note); dealer stuffing
(wholesale >> retail for 2+ quarters before a fiscal-year end); warranty
provision adequacy vs recall history; royalty to foreign parent
(Maruti-type) trend.

**Peers/valuation:** compare within segment (PV vs PV); primary multiple
P/E (EV/EBITDA when leverage diverges); EV businesses inside OEMs get SOTP
treatment in market narratives — note when the market is doing this;
tractor/rural franchises command premium multiples for lower cyclicality.

**Cadence:** monthly volumes (1st of month, SIAM ~10th, FADA ~5th–8th),
festive season (Oct–Nov) = ~35–40% of annual PV/2W retail, monsoon
(Jun–Sep) drives tractor H2, price hikes announced Jan/Apr, commodity
contracts reset quarterly.

**Classic mistakes to avoid:** judging demand off wholesale alone;
annualizing festive quarters; ignoring the EV drag on near-term margins
while crediting the optionality; treating tractor cyclicality (monsoon)
like CV cyclicality (freight economics + IIP).

## S2. Auto Ancillaries / Components — PILOT

**Model essence:** volume taker on OEM platforms + content-per-vehicle
(CPV) growth story + aftermarket annuity. Winning = getting spec'd on
platforms (5–7 year revenue visibility once on), raising CPV via
premiumization (EV, electronics, safety), and export share.

**Defining KPIs:** CPV trend; order book / net new business wins
(lifetime value basis — check the counting convention!); OEM concentration
(top customer %); platform/program mix (growing vs sunset platforms);
export % + destination mix; aftermarket % (higher margin, counter-
cyclical); EBITDA margin (commodity processors 8–12%, technology/
precision parts 18–28%); RM pass-through arrangement (with lag — usually
quarterly reset, so margins compress when commodities spike and recover
after); utilization; EV-readiness of the portfolio.

**D-adaptations:** D1: split growth into underlying OEM production growth
vs CPV/share gains vs new wins ramping — a component maker growing at
OEM-market rate has NO story, growing 1.5–2× market = content story
(verify vs SIAM production data); tooling income (one-off, lumpy —
separate from product revenue). D2: capex-ahead-of-ramp is normal (new
win → 12–18m capex → revenue), so CWIP with a NAMED program is fine;
CWIP without disclosed programs is not; receivables: OEM receivables are
safe but 60–90 days; aftermarket/export receivables riskier. D3: FCF
negative during win-driven capex cycles is acceptable IF incremental ROCE
on completed programs clears hurdle — compute program-cycle ROCE, not
just point-in-time.

**EV exposure taxonomy (apply to every product line):** obsolete in BEV
(engine internals, fuel systems, exhaust) / agnostic (bearings, seating,
lighting, forgings that shift shape) / enhanced (e-motors, e-axles,
controllers, sensors, HV harnesses — CPV multiplies). State the revenue %
in each bucket — THE strategic number for this sector.

**Sector forensics:** related-party sales to promoter-owned distributors
(aftermarket channel games); "order book" inflation via lifetime-value
counting changes; rare-earth/import dependence (magnets — China export
controls = live single-source risk); customer advances vs tooling
receivables netting.

**Peers/valuation:** peer by PRODUCT overlap, not "auto anc" label
(a forging co vs a wiring-harness co is not a comparison); P/E primary;
technology/EV-content names carry structural premium — quantify the
premium vs CPV growth differential; global peers (Bosch, Aptiv, Schaeffler
AG) as context on where multiples CAN go, never as Indian comps.

**Cadence:** OEM monthly volumes (derived demand), quarterly OEM
production schedules commentary in concalls, commodity resets, EU/US SAAR
for exporters, China rare-earth policy news.

**Classic mistakes:** valuing on order-book multiples without conversion
history; missing the pass-through lag (calling a commodity-spike quarter a
structural margin break); crediting EV optionality while ignoring the ICE
cash-cow melt rate; comparing CPV across companies with different
content-counting definitions.

## S3. Banks & NBFCs — FULL PACK (structurally different)

**Model essence:** spread business on a levered balance sheet. The P&L IS
the balance sheet. EBITDA, working capital, FCF, EV multiples — ALL
meaningless. Growth without asset quality is just future credit cost.

**Defining KPIs:** NIM (net interest income/avg interest-earning assets;
Indian banks 3–4.5%, NBFC spread varies by segment); CASA ratio (current+
savings/total deposits — funding-cost moat, 35–45% strong for banks; N/A
for NBFCs → track cost of borrowings + mix of bank lines/NCD/CP);
credit growth vs system (RBI fortnightly data); deposit growth vs credit
growth (LDR/CD ratio 75–90% comfort); asset quality: GNPA%, NNPA%,
slippage ratio (fresh NPAs/opening advances — the LEADING indicator),
credit cost (provisions/avg advances), PCR (>70% comfort), restructured +
write-off adjusted view (add back write-offs to see true stress); capital:
CET1/CAR vs regulatory minimums + growth headroom; RoA (1%+ good for
banks, 2%+ excellent) and its decomposition; RoE with leverage stated.

**RoA tree (compute — replaces DuPont):** NII/assets + fee income/assets
− opex/assets (cost-income ratio) − credit cost/assets − tax → RoA;
× leverage → RoE. Narrate which lever moves.

**Analysis adaptations:** growth quality = WHERE the book grows
(unsecured personal/MFI = high yield high risk; secured mortgage = slow
safe) — segment-mix shift IS the risk story; NIM trend decomposition
(yield on advances vs cost of funds — repricing cycles: floating-rate
books reprice with repo, deposits lag → NIM expands in hiking cycles,
compresses in cuts, ~2–3Q); counter-cyclical provisioning buffers
(management prudence signal); ALM mismatch for NBFCs (borrow-short-
lend-long = IL&FS/DHFL archetype) — check ALM disclosures.

**Sector forensics:** evergreening signatures (restructured loans
regrowing, "standard" accounts with repeated moratoria, lending to
stressed groups' fresh SPVs); divergence reports (RBI-assessed vs
disclosed NPAs — automatic red flag); fee income quality (assignment/
securitization gains booked upfront by NBFCs); write-off recycling
(GNPA "improves" via write-offs while credit cost stays high); deposit
concentration (bulk vs retail); promoter/group exposure of the book.

**Peers/valuation:** P/B (or P/ABV = book minus NNPA) with RoE — the
P/B↔RoE regression line IS the sector's valuation map; sustainable RoE >
cost of equity justifies >1× book, mechanically; peer within model class
(large private ≠ SFB ≠ gold NBFC); credit cost normalized-cycle view for
cyclicals like MFI/vehicle finance.

**Cadence:** RBI fortnightly credit/deposit data, quarterly results with
slippage detail, RBI policy (repo + stance + liquidity), FSR twice yearly,
monthly business updates (many banks pre-release).

## S4. IT Services (solid pack)

KPIs: revenue growth in CONSTANT CURRENCY (reported INR growth includes
FX — always split), deal TCV + book-to-bill, attrition (LTM), utilization
(ex-trainees), pyramid/fresher intake, onsite-offshore mix, client
concentration (top-5/10), vertical mix (BFSI/retail/healthcare exposure to
client-side cycles), EBIT margin walk (wage hikes − pyramid − utilization
− pricing − FX). D-adaptations: DSO incl. unbilled (unbilled creep = flag);
buyback/dividend payout ratios (mature = 80%+ payout); acquisitions'
revenue vs organic split. Forensics: unbilled revenue & contract assets
growth vs revenue; visa/immigration cost jumps; hedging book MTM.
Valuation: P/E primary; growth-adjusted vs peers; margin-band stability
matters more than level. Cadence: quarterly guidance rituals (some guide
revenue bands), major-deal announcements, US macro/BFSI capex commentary.
Mistakes: treating INR growth as demand; annualizing furlough quarters
(Q3 seasonal); reading headcount adds as demand in the GenAI era
(decoupling underway).

## S5. FMCG (solid pack)

KPIs: volume growth vs value growth (price/mix) — volume is truth; rural
vs urban split; distribution (direct reach, stockist count); market share
by category (Nielsen via commentary); gross margin vs A&P spend (cutting
A&P to protect EBITDA = borrowing from the future — flag it); working
capital (negative for strong franchises); new-launch contribution %.
D-adaptations: RM basket = palm oil, crude derivatives (packaging), agri
inputs (milk, wheat, barley) — gross-margin bridge vs basket; ad-spend %
as investment line, not just cost. Forensics: channel loading before
quarter-ends (distributor inventory days if disclosed), one-off "other
operating income" (scheme incentives), related-party brand royalties.
Valuation: P/E premium franchise; compare vs own history percentile — the
sector's re-rating/de-rating dominates returns. Cadence: monsoon, WPI food,
quarterly volume prints, GST changes. Mistakes: crediting price-led growth
as franchise strength during inflation; missing down-trading signals.

## S6. Pharma (solid pack)

KPIs: split the business FIRST — domestic formulations (IPM growth,
chronic vs acute mix, MR productivity) / US generics (base erosion
5–8% normal, launches, ANDA pipeline, para-IV/FTF events) / API-CDMO
(client qualification cycles, capacity). Plant-level USFDA status
(OAI/VAI/WL history per plant — a warning letter can freeze approvals);
R&D % of sales and where it goes (ANDA vs complex vs NCE); gross margin by
mix. Forensics: capitalized R&D policies, inventory write-offs
(failed launches), receivables in US channel (buying-group consolidation
pressure), contingent liabilities (patent litigation, DoJ/FTC). Valuation:
P/E on BASE business ex-one-off launches (a para-IV windfall quarter is
not run-rate); CDMO gets contract-visibility premium. Cadence: USFDA
inspection news, monthly IPM (AIOCD) prints, ANDA approvals (weekly FDA),
NLEM/price-control updates. Mistakes: run-rating exclusivity quarters;
ignoring plant concentration (one plant = 40% of US sales is a real risk
line); treating "US price erosion" commentary as company-specific when
it's industry-wide (or vice versa).

## S7. Specialty Chemicals (solid pack)

KPIs: product vs commodity mix (spread stability test), capacity
utilization + announced capex pipeline (the sector over-builds in
upcycles), China price spreads for key molecules, client-qualification
status (multi-year approvals = switching-cost moat), export %,
value-added depth (fluorination/complex chemistry premium). D-adaptations:
margin normalization across the agrochem destocking-type cycles — state
cycle position; capex/sales heavy (15–25%) in build years — program-level
ROCE like ancillaries. Forensics: inventory valuation in falling-price
cycles (NRV write-downs lagging), capitalization during long project
gestation. Valuation: mid-cycle EV/EBITDA framing; the 2021-22 "spec-chem
premium" collapse is the cautionary percentile tale. Cadence: China
operating-rate/pricing news, agrochem channel inventory commentary,
crude/feedstock. Mistakes: extrapolating spread spikes (supply-disruption
windfalls); calling commodity converters "specialty."

## S8. Capital Goods / T&D equipment / Cables & wires / EMS (working pack)

KPIs: ORDER BOOK (size, book-to-bill, composition, aging) + order INFLOW
run-rate — the P&L is the past, the order book is the story; execution
cycle length; margin in backlog vs P&L margin (mix shift signal);
working capital (EPC-type = high WC, product-type = lower; advances
from customers = quality signal); for cables/EMS: copper/commodity
pass-through lag, client concentration (EMS: anchor-client risk is THE
risk), PLI benefits quantified. Forensics: unbilled/contract assets vs
milestones (aggressive PoC recognition), LDs (liquidated damages)
provisioning, receivables from government counterparties aging, order-book
double-counting (framework vs firm orders). Valuation: P/E on
execution-visible earnings; order-book multiples only as cross-check.
Cadence: tender awards (PGCIL/SECI/railways/defence), CEA capex plans,
quarterly inflow disclosures. Mistakes: valuing announced (not firm)
orders; ignoring margin dilution in mega-orders won on price.

## S9. Cement / Metals / Commodities (working pack)

KPIs: volume growth vs industry, realization per tonne (regional prices
matter — cement is a regional business), EBITDA/tonne (the sector
scoreboard: cement ₹800–1,300 healthy; steel varies with cycle), cost
curve position (fuel/power mix for cement, coking-coal integration for
steel, captive mines), utilization, net debt/EBITDA through-cycle,
expansion pipeline (organic ₹/tonne capex vs acquisition EV/tonne paid).
D-adaptations: through-cycle normalization is EVERYTHING — compute
mid-cycle EBITDA/tonne over 7–10y; leverage judged at trough EBITDA, not
peak. Forensics: freight/other-expense games in realization comparisons;
inter-unit transfers in integrated players. Valuation: EV/tonne vs
replacement cost (cement ~$80–120/t replacement context), EV/EBITDA
mid-cycle, P/B at trough. Cadence: monthly/weekly regional price checks
(dealer surveys via news), fuel (petcoke/coal) prices, China steel
output/exports. Mistakes: peak-multiple-on-peak-earnings; ignoring
regional supply waves (new south-India capacity ≠ north prices).

## S10. Power / Utilities / EPC-infra (working pack)

KPIs: regulated-equity businesses (transmission, discoms-adjacent) =
regulated RoE (15.5% CERC framework) × equity base growth — earnings are
formulaic, track capitalization of projects; IPPs = PLF, merchant vs PPA
mix, tariff realization, fuel supply security, receivables from discoms
(THE sector risk — days receivable from state discoms); renewables =
auctioned tariff economics, PPA counterparty, CUF (capacity utilization
factor), module-cost cycles for developers. EPC overlay per S8. Forensics:
receivable aging from discoms, regulatory assets accumulation (deferred
recoveries), aggressive capitalization of employee/interest cost during
construction. Valuation: regulated = P/B vs regulated-RoE clarity; IPP/
renewables = EV/MW vs auction economics; InvIT yield framing. Cadence:
CEA monthly, SECI/state auction tariffs, coal availability, discom-dues
(PRAAPTI portal data via news). Mistakes: valuing regulated and merchant
megawatts alike; ignoring PPA counterparty quality.

## S11. Consumer Durables / FMEG (working pack)

KPIs: category growth (AC penetration ~8–10% households = runway story),
season dependence (AC = summer make-or-break, Q4/Q1), market share,
channel inventory pre-season, gross margin vs copper/commodities, PLI/
import-substitution progress (compressors, PCBs), distribution expansion,
brand vs contract-manufacturing mix. Forensics: extended-credit-driven
channel loading pre-season, warranty provisioning, related-party
distribution. Valuation: P/E with season-normalized TTM. Cadence: summer
onset news, festive, RBI consumer-credit conditions, BEE rating changes.
Mistakes: annualizing a hot summer; missing energy-norm transitions that
obsolete channel inventory.

## S-template (for onboarding any other sector)

1. Model essence in 2 lines (where profit actually comes from)
2. The 6–10 defining KPIs with healthy/warning ranges
3. D1/D2/D3 adaptations (what replaces/augments standard analysis)
4. Sector forensic signatures (how THIS sector fakes it)
5. Peer & valuation conventions (the multiple that clears, norms)
6. Data cadence (what prints when; what to monitor)
7. Classic analytical mistakes in this sector

---

# PART 3 — PYTHON COMPUTE LIBRARY SPEC (deterministic layer)

> Everything below is code, not LLM. Inputs: metric_observations
> (+ statements extracted at S2). Outputs: computed metrics + flags with
> full provenance (input row ids), stored as knowledge_entries
> (`computed_financials`, `forensic_flags`, `peer_table`,
> `valuation_context`, `guidance_scorecard`). The LLM receives these
> tables and MAY NOT recompute or extrapolate beyond them.

**growth.py** — YoY/QoQ, CAGR(3/5/10) with endpoint disclosure,
TTM builder (same-basis guard), momentum (TTM vs 3y trend), organic vs
reported where M&A flagged.

**margins.py** — gross/EBITDA/EBIT/PBT/PAT margins (ex-exceptional
variants), YoY margin bridge decomposition (RM/employee/other-opex/mix
contributions), operating-leverage elasticity.

**returns.py** — ROE, ROCE, ROIC; DuPont 3-stage & 5-stage; incremental
ROCE (rolling 3y Δ); banks: RoA tree instead (NII, fees, opex, credit
cost as % of assets; leverage to RoE).

**leverage.py** — net debt/EBITDA, D/E, interest coverage, implied
borrowing rate (interest/avg gross debt) + gap vs disclosed mix, cash
yield (interest income/avg cash & investments) + gap flag, contingent
liabilities/net worth.

**working_capital.py** — DSO/DIO/DPO/CCC (5y series), WC/sales,
receivables-vs-revenue divergence score, inventory-vs-COGS divergence,
unbilled revenue tracking where disclosed.

**cashflow.py** — CFO/EBITDA & CFO/PAT (yearly + 5y median), Sloan
accrual ratio, ΣPAT vs ΣCFO cumulative gap, FCF (CFO − PP&E capex),
FCF conversion, maintenance-capex floor (≈ depreciation), payout vs FCF
funding check, P&L-vs-CFS interest & tax reconciliation gaps.

**forensic.py** — the D-cross battery (12 checks) each emitting
{check, status OK/WATCH/FLAG, inputs, one-line rationale}; composite
screens: Piotroski F (9 components itemized), Altman Z″ (EM variant,
industrials only), Beneish M (8 ratios, data permitting) — components
always shown, composites labeled "screen, not verdict."

**guidance.py** — guidance_items × actuals join; per-item outcome
(beat/met/missed + magnitude); management credibility scorecard
(delivery rate by metric type, bias direction).

**peers.py** — normalized peer table builder (basis/period/exceptional
alignment), ranks, gaps vs best-in-class, z-scores within peer set;
worst-cell extraction → risk candidates for H.

**valuation.py** — TTM multiples (P/E, EV/EBITDA, P/B, sector-primary
from pack), own-history percentile (5y/10y), peer-set rank, PEG sanity,
3y return decomposition (EPS growth × multiple change + dividend),
normalized-earnings context for cyclicals (mid-cycle margin × current
revenue).

**sector_kpis.py** — pack-registered computations (EBITDA/tonne,
CPV proxy, NIM/RoA tree, CASA, GNPA ratios, cc-growth splits, book-to-bill,
EV/MW...) — each pack contributes formulas here; one registry, no forks.

**Provenance rule:** every computed value carries {formula_id, input
metric_observation ids, periods, basis}. A computed number without full
lineage does not ship.

---

## Changelog
- v0.1 (2026-07-14): initial draft — universal knowledge (B–J + hygiene),
  full packs for auto OEM / ancillaries / banks-NBFC, solid packs IT/FMCG/
  pharma/spec-chem, working packs capital goods/commodities/power/durables,
  sector template, Python compute library spec.
