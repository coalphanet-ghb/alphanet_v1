# AlphaNet — Final Report Blueprint (v0.2 — owner markup incorporated)

> Status: PROPOSAL, one review round done (owner markup of 2026-07-14
> incorporated). Once frozen, we reverse-map: blocks → data needs →
> sources → queries → nodes → calculations → (any) schema updates.
> Nothing gets built against this until it's approved.

## Design rules (these make it work for ALL sectors)

1. **One fixed skeleton, everywhere.** Every company — auto OEM, bank,
   IT, pharma, cement — gets the same 11 sections (A–K). A reader who
   learns to read one AlphaNet report can read them all.
2. **Sector metric packs.** The *skeleton* never changes; the *metrics
   inside* the number-driven sections (A, D, H, I) come from a per-sector
   pack. A bank's pack has NII, NIM, CASA, GNPA/NNPA, PCR, credit growth,
   capital adequacy — and simply has no EBITDA or working-capital block,
   because those are meaningless for a lender. Packs are config
   (a registry file), not code forks.
3. **Facts are computed, never generated.** Any number that can be derived
   (CAGR, ratio, percentile vs history) is computed in Python from stored
   observations. The LLM's job is extraction (with citations) and
   interpretation (with citations) — never arithmetic.
4. **Every block cites or it doesn't ship.** Narrative blocks carry
   evidence citations; numeric blocks carry provenance to
   metric_observations rows (which trace to a source document). A block
   with neither is a bug.
5. **No recommendations, ever.** "P/E is at the 88th percentile of its own
   5-year range" is a fact. "Expensive, avoid" is advice. We publish facts
   and framing, never the verdict.
6. **Each section answers one reader-question.** Stated below as *"Q:"* —
   if a block doesn't help answer its section's question, it goes.

---

## The skeleton

### A. Snapshot  *(zero LLM — pure data card)*
*Q: "What am I looking at, right now?"*

- Identity: name, ticker, sector/industry, market-cap bucket
- Price context: CMP, 52-week range + position in it, 1y/3y/5y price CAGR
- **Universal vitals (all sectors, exactly these four):** market cap, P/E,
  dividend yield, ROE
- **Sector vitals (from pack — max 8, the most relevant per sector):**
  everything else lives here: D/E, interest coverage, PEG, ROCE, promoter
  holding/pledge, P/B, and the sector-specific ones (auto OEM: volume
  growth, EBITDA margin; bank: NIM, GNPA, CASA, CAR; IT: cc revenue
  growth, attrition)
- Report metadata: **last updated** (single stamp; full reproducibility
  detail lives in section K)

### B. Business Overview
*Q: "How does this company actually make money?"*

- What it does, in plain language (no corporate-speak)
- Revenue mix table: by segment / product / geography / customer-type,
  with % share and trend direction (mix shifting toward what?)
- Key customers & dependence (top-customer concentration if disclosed)
- Business model mechanics: pricing power, recurring vs cyclical revenue,
  capex intensity, where it sits in its value chain
- Moat assessment: claimed advantages, each with evidence — and an honest
  "not evidenced" where we can't support one

### C. Industry & Macro Context  *(the reused-layers payoff)*
*Q: "What tide is this boat floating on?"*

- Sector state: demand snapshot with the 3–4 numbers that matter (from
  industry layer: e.g. SIAM/FADA volumes for auto; credit growth for banks)
- Structure: competitive intensity, consolidation/fragmentation, regulatory
  posture
- Sector growth drivers and outlook (absorbed from the old "Growth
  Drivers" section: industry-level demand drivers, policy tailwinds,
  technology shifts like the EV transition)
- **This company's specific sensitivities** (via the entity graph): which
  macro factors and input entities feed it, in which direction, with the
  transmission spelled out (repo rate → auto loans → entry-segment demand;
  steel → gross margin). For **every** sensitivity entity (commodities,
  rates, currency, international-trade factors): give the **recent view
  AND the expected medium-term view**, both cited.
- What changed recently in the macro/industry picture that a holder of
  this stock should know

> **Pipeline-ordering constraint (deliberate):** the sensitivities block
> requires knowing ALL entities that impact the company — raw materials,
> logistics, customers — much of which is discovered by the Supply Chain
> analysis (E) and other company nodes. So this block is generated LATE in
> the workflow, after the other analyses are done and no new entity
> relations are expected. C is written in two passes or last among the
> narrative sections.

### D. Financial Analysis  *(compute spine + interpretation — grouped BY STATEMENT)*
*Q: "Is this a good business, financially, and is it getting better or worse?"*

**D1. P&L:**
- Growth: revenue & profit, 3y/5y CAGRs + last-4-quarters momentum
- Profitability: margin trajectory and what's driving it
- Returns: ROE/ROCE trend vs cost of capital ("does growth create value?")
- P&L quality checks: other-income dependence, effective tax rate
  anomalies, EPS trend vs dilution, one-offs/exceptional items

**D2. Balance Sheet:**
- Strength: leverage, coverage, liquidity, asset base composition
- **Forensic checks:** receivables growth vs revenue growth, inventory
  build-up, DuPont decomposition (what actually drives ROE), CWIP that
  never commissions, loans/advances to related parties, contingent
  liabilities — an explicit "anything fishy?" pass with flags, not prose
  padding

**D3. Cash Flow Statement:**
- CFO trend, FCF trend, cash conversion cycle
- **Quality of earnings:** CFO vs EBITDA/PAT over multiple years (accruals
  gap), where investing cash actually goes vs stated strategy, financing
  pattern (serial diluter? debt-funded dividends?)

- One-line verdicts per sub-block, LLM-written FROM the computed table
- Sector pack overrides/extends the sub-blocks (examples):
  - **Lenders:** statement grouping adapts — NII/NIM trend, CASA, credit
    growth vs system, asset quality (GNPA/NNPA/slippages), PCR, credit
    cost, CAR, RoA decomposition. (No EBITDA, no working capital.)
  - **Manufacturers/auto:** gross vs EBITDA margin bridge, volume vs
    realization split, working-capital cycle, capex intensity & asset turns
  - **IT/services:** cc revenue growth, deal TCV, utilization, attrition,
    margin walk
- Anything not disclosed → explicitly "not disclosed", never estimated

### E. Supply Chain Analysis
*Q: "What does this company depend on, upstream and downstream?"*

- **Inputs:** key raw materials / components, their price sensitivity,
  sourcing concentration (domestic vs imported, single-source risks)
- **Suppliers:** named where disclosed, dependence and switching ability
- **Customers / channels:** OEM vs aftermarket, dealer network, export
  markets, customer concentration (complements B's revenue-mix view with a
  dependence lens)
- **Logistics & geography:** plant locations, freight exposure, trade
  routes / tariff exposure for exporters
- Every dependency found here becomes an `entity_relationships` edge —
  this section is a primary FEEDER of the entity graph, which is what
  makes C's sensitivities block and G's risk transmission possible

### F. Management, Governance & Guidance
*Q: "Can I trust the people running this?"*

- **Guidance track record table:** what they guided (per past concalls) vs
  what happened — the single most underrated trust signal
- Current stated guidance & assumptions, and company-level growth plans
  absorbed from the old "Growth Drivers" section: announced capex &
  expansion with status, order book, new products/platforms — each:
  driver → mechanism → evidence → timeline, with management claims
  explicitly separated from independently evidenced facts
- Capital allocation record: where profits went (capex/dividends/buyback/
  acquisitions) and returns achieved on them
- Governance hygiene: promoter holding trend & pledging, board
  independence, auditor changes, related-party transactions, remuneration
  vs profit growth — flag-based (only surfaced when notable)

### G. Peer Comparison
*Q: "Why own this one instead of its rivals?"*

- Peer set from entity_relationships (3–6 names, disclosed as "AlphaNet
  peer set")
- Computed table: universal columns (growth, ROE, valuation multiple) +
  sector-pack columns (bank: NIM/GNPA/CASA; auto: margin/volume growth)
- Narrative: *why* the gaps exist (mix, scale, execution) — not just that
  they exist; where this company ranks and on what dimension it leads/lags

### H. Risks
*Q: "What kills this thesis?"*

- Ranked risk register, each entry: risk → transmission → evidence →
  **monitorable** (the specific number/event that tells you it's happening)
- Three buckets: company-specific / industry / macro, linked to graph
  entities so risk entries update when upstream layers change
- Runs AFTER peer comparison (G) deliberately — relative weakness surfaced
  there (losing share, inferior margins/returns vs peers) feeds the risk
  register
- Include the boring structural ones (customer concentration, key-person,
  regulatory) — not just headlines

### I. Valuation Context  *(facts and framing — never a verdict)*
*Q: "What is the market already assuming?"*

- Primary multiple per sector pack (P/E; P/B for lenders; EV/EBITDA for
  capital-intensive) — current vs own 5y history (percentile) vs peer set
- Multiple-vs-fundamentals cross-check (premium to peers vs superior ROE?)
- "Priced in": what the current multiple implies, in words
- Bull/bear framing of the valuation debate, both sides cited
- Hard line: no target price, no fair value, no rating

### J. Key Takeaways
*Q: "The 60-second version?"*

- 3 strongest evidenced positives, 3 most material negatives/risks
  (deliberately symmetric — forces balance)
- "What to watch next": 3 monitorables with expected timing (next concall,
  festive-season sales, RBI policy, capacity commissioning)
- Every bullet carries citations; this section is what the UI leads with

### K. Sources & Provenance
- Grouped by layer (macro/industry/company), each: title, type, date, link
- Report reproducibility: knowledge versions + run id + model used +
  per-source data-as-of dates (the detail behind A's "last updated" stamp)
- The existing invented-citation check stays, surfaced as a quality badge
  (e.g. "47/47 citations resolved")

---

## Cross-cutting requirements

- **Freshness stamps.** Every section shows data-as-of; anything stale
  gets flagged rather than silently served.
- **"Insufficient evidence" is a first-class output.** A thin section says
  so explicitly. Credibility comes from admitting gaps.
- **Sector pack registry** (to be built): per sector → the ≤8 A-vitals,
  D sub-blocks to include/exclude, H columns, I primary multiple. Adding a
  new sector = writing a pack, not touching the skeleton.
- **Section generation order matters:** B, D, E, F are independent; then
  G (peers), then H (risks — consumes G's relative-weakness findings),
  then I; C's sensitivities block runs late (after E has fed the entity
  graph); J and A assemble last. The workflow graph must encode this, not
  run everything in one parallel fan-out as today.
- **Blocks, not prose** (agreed, to be reverse-mapped after this freezes):
  every section compiles to typed blocks {narrative | metric_card | table |
  ranked_list | flag} each with citations[] — markdown becomes just one
  renderer.

## Explicitly OUT of v1 (unchanged from HANDOFF)

Technical analysis, shareholder-return simulations, DCF/target prices,
brokerage-view aggregation, ESG scoring, news-feed timeline. Each can slot
in as a section later without touching the skeleton.

## Changelog

- **v0.3 (2026-07-14):** owner markup — Peer Comparison and Risks swapped
  (now G and H respectively): risks are sometimes surfaced BY the peer
  comparison, so peers must be analyzed first and the risk node consumes
  its findings. Generation-order note updated to match.
- **v0.2 (2026-07-14):** owner markup — A: universal vitals trimmed to
  exactly {mcap, P/E, div yield, ROE}, everything else into sector packs
  (max 8), metadata simplified to "last updated". C: sensitivities block
  requires the full entity graph → generated late in the workflow; every
  sensitivity entity gets recent + medium-term view. D: regrouped by
  statement (P&L / BS / CFS) with forensic checks (receivables, DuPont,
  fishy-flags) and quality-of-earnings analysis. E: new Supply Chain
  Analysis section (was a v1 non-goal in HANDOFF; owner overrode — it
  feeds the entity graph). Old "Growth Drivers & Outlook" dissolved into
  C (industry-level) and F (company-level). Lettering shifted: old E→F.
- **v0.1 (2026-07-14):** initial draft.
