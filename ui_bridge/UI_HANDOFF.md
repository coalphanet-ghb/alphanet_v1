# UI HANDOFF — AlphaNet → frontend

> Transfer context for the frontend repo. Pair it with `ui_bridge/alphanet.ts`
> (copy that file over; it is the only thing that should know how a report
> is stored). Written 2026-07-22 against **M&M report v5** and **SONA v22**,
> envelope contract **1.0.0**.
>
> Backend context lives in the pipeline repo: `HANDOFF4.md` (current state,
> §2b citation labels), `FOUNDATIONS.md` (product identity + the hard
> rules), `DB_SCHEMA.md` (persistence contract).

---

## 1. What the backend actually gives you

One company → one versioned research report, stored as
`report_versions.sections_json`. That JSON holds **12 section envelopes**
(B, C, D, D1, D2, D3, E, F, G, H, I, J), each `{blocks[], claims[],
insufficiencies[]}`, with five block types: `narrative`, `metric_card`,
`table`, `ranked_list`, `flag`.

Blocks are **pre-rendered analysis**. The model already wrote the prose,
built the table, and cited its sources. Your job is layout and
interaction — not computation.

Real shape, M&M v5 (blocks / claims per section):

| B | C | D | D1 | D2 | D3 | E | F | G | H | I | J |
|---|---|---|----|----|----|---|---|---|---|---|---|
| 8/20 | 6/29 | 12/13 | 7/22 | 14/13 | 9/8 | 10/29 | 12/25 | 8/11 | 4/20 | 10/20 | 4/12 |

Payload: ~430 KB per report, 416 citation labels across 59 documents.

### Three rules that are not negotiable

1. **Never parse `final_report_md`.** It ships in the payload for
   debug/export. The typed envelopes are the API — re-parsing markdown is
   exactly the failure mode this contract exists to prevent.
2. **Never recompute.** Every number carries lineage and a unit. Don't
   derive percentages, convert crore↔billion, annualise, or round in the
   view layer. `formatValue()` in the connector mirrors the Python
   formatter exactly so the UI and the markdown export can never disagree.
3. **Always render period + basis.** `FY26` vs `Q3FY26`, `consolidated` vs
   `standalone`. Two numbers with different bases are not comparable and
   the report is careful about this; the UI must not flatten it away.

## 2. The second data surface: `metric_observations`

Separate from the report, and useful for charting: **975 rows / 333
distinct metric names for M&M**, each with entity, period, value, unit and
source document. Revenue, EPS, OPM, ROCE, CFO, borrowings, debtor days,
CCC, dividend payout — typically 12–25 periods each. Also
`promoter_holding_pct` (16), `fii_holding_pct` (15), `dii_holding_pct`
(14), and `price` (23 points: 13 recent + 10 FY-end closes).

These are **observed facts, append-only** — the right source for time-series
charts. But note the boundary: **derived values are deliberately not stored**
(no CAGR, TTM, PE series, ratios). Plotting an observed series is fine;
computing a growth rate from it in the frontend violates rule 2 above. If
you need a derived number, it belongs in the pipeline's compute step.

## 3. Architecture decision you need to make first

**The service-role key bypasses RLS and must never reach a browser.** RLS
is currently fully closed, so a client-side Supabase call returns nothing.
Two options:

- **(Recommended) Server-side fetching.** Next.js server components /
  route handlers hold the key; the browser gets JSON. Preserves the
  invariant exactly, no backend change, and 430 KB payloads want server
  rendering anyway.
- **Anon-key + RLS read policies** on `report_versions`, `entities`,
  `evidence`, `source_documents`. Cleaner client story, but it is a
  deliberate security-posture change and needs sign-off — it makes every
  stored report world-readable to anyone with the anon key.

The connector is written for option 1.

## 4. Your mock-up, reconciled against real data

Honest mapping. Three buckets.

### Backed by real data today

| Mock surface | Source |
|---|---|
| Business Overview, segment/geography mix | **B** blocks + `metric_observations` |
| Economic & Industry Overview | **C** blocks |
| Financial Analysis (BS / P&L / CF tables) | **D1/D2/D3** `table` blocks — already built, e.g. `d2_bs_evolution` |
| Key Ratios (ROE, ROCE, margins, coverage) | **D** blocks + `metric_observations` |
| Peers Overview table | **G** — includes the peer table *and* non-comparability flags |
| Supply Chain (suppliers, inputs, customers, competition) | **E** — maps almost 1:1 to your four cards |
| Risk tab | **H** ranked lists with `monitorable` per item |
| News & Updates | `source_documents` where `doc_class='news_batch'` |
| Institutional Investors (promoter/FII/DII) | `metric_observations` — *available, contrary to my earlier read* |

### Not available — no pipeline produces this

- **Price Performance chart (1M/6M/1Y/3Y/5Y).** Only 23 price points exist
  (13 recent + 10 FY-end closes). A real chart needs a market-data feed;
  that is not AlphaNet's job and shouldn't become one.
- **Technical Analysis (RSI, MACD, EMA, trend/strength).** Nothing in
  S0–S9 computes these. Would be a new, separate data source.
- **"Semantic" tab.** No backing concept exists.
- **Tata Motors as the subject.** Covered companies are **SONACOMS** and
  **M&M** only. Tata's PV/CV entities demerged in Oct 2025 and appear as
  *peers* — the M&M report explicitly declares TMPV non-comparable on
  ROE/ROCE/PE. Build the mock against M&M or SONA.

### Blocked by a hard product rule — please read before designing these

**AlphaNet does not give Buy/Sell/Hold, and this is load-bearing, not a
style preference.** It is the stated product identity (FOUNDATIONS §1),
it is enforced in the generation contract (rule 5 bans recommendations,
target prices and verdict vocabulary), and it is the core of the
regulatory posture: publicly offering research on individual listed
Indian securities may engage the **SEBI Research Analyst framework**, and
the no-recommendation stance is the main thing keeping us on the right
side of that line (FOUNDATIONS §6). That review is explicitly required
*before the UI ships to anyone but you*.

Two mock surfaces cross it:

- **Brokerage Targets** (Buy / Buy / Buy / Add, target price, upside %).
  Republishing broker recommendations is both a recommendation surface and
  a separate copyright question (§6.1).
- **Valuation Summary** ("Intrinsic Value ₹1,210", "Upside Potential
  +14.5%", "12M Target", DCF base case). A price target with an upside
  number is a recommendation in all but name.

**What section I actually gives you instead**, and it is genuinely good
UI material: the multiple with its own 10-year percentile ("22.8× TTM,
70th percentile of its own range, median 21.5×"), peer rank, P/B against
book value, and the risk events that explain multiple moves. That is
valuation *context* — the reader draws the conclusion. I'd design the
Valuation surface around "where does this multiple sit, and why", with no
fair-value number anywhere on it.

If you want the target-price surface anyway, that is your call as owner —
but take it to the SEBI/fintech compliance review first, not after the UI
is built around it.

## 5. What the mock has no home for — and this is the pruning audit

HANDOFF4 §7.3 says the mapping exercise *is* the next optimization audit.
Running it against your mock, the report produces four things with nowhere
to go:

1. **Section F — Management, Governance & Guidance** (12 blocks, 25
   claims). Guidance scorecard, credibility assessment, dodged-question
   tracking. This is arguably the most differentiated output in the whole
   product and your mock has no surface for it.
2. **The claims-vs-numbers scoreboard** (`claimChecks`, 13 rows on M&M).
   Management said X; the computed number says Y; verdict corroborated /
   contradicted / unverifiable. Nothing else in Indian retail research
   does this.
3. **Insufficiencies** — every section carries them ("not disclosed / not
   computable"). Gaps are a first-class output, never papered over
   (FOUNDATIONS §3.10). They need a real, non-apologetic surface.
4. **Verification status** — `claims.verification_status` per claim, plus
   the report-level badge (M&M v5: 160/187 supported, 493/499 citations
   resolved). The trust layer is the product; right now the mock shows no
   evidence that any of it exists.

Also unmapped: **section J (Key Takeaways)**, 4 blocks.

So the audit's first output is: the mock over-builds surfaces we can't
feed (technical, brokerage, semantic) and under-builds the ones that are
genuinely differentiated (F, the scoreboard, verification, gaps). Worth
resolving before either side gets built out.

## 6. Citations — the thing to get right

Every block and claim carries citations, and they now read as labels, not
UUIDs:

```
AR.17        annual report, passage 17     CC-May26.4   May 2026 earnings call
IP.9         investor presentation         CR.2         credit-rating rationale
S-MARUTI     peer screener page            47           news / sector / macro link
calc:roce_pct_series   a computed value    sec:D.d1_x   an upstream finding
```

`resolveCitation()` handles all forms with the same precedence as the
backend. `getEvidence()` fetches the **verbatim source passage** behind a
citation — wire that to hover/click on a citation chip. It is the single
highest-trust affordance available: the reader can check any sentence
against the actual text and the source URL.

`citationMap.documents` is section K, the legend — 59 documents with
label ranges, titles and URLs.

One caveat: `calc:` citations resolve to a formula id, **not a value** —
computed values are derived at run time and deliberately never persisted.
Render them as a "computed" provenance chip, not a link. If the UI needs
the underlying series, pull it from `metric_observations` (§2) or ask me
to persist a computed snapshot into `sections_json` (one line in the
composer, no schema change).

## 7. Known gaps on the backend side

Fix on the pipeline, not in the UI:

- **`calc:` values aren't persisted** (§6). Cheap to fix if the UI needs
  them.
- **Rating-rationale documents are currently the wrong entity** — M&M v5
  ingested a *Mahindra & Mahindra Financial Services* bond page and a 2019
  CRISIL rationale as M&M evidence. Don't build a "credit view" surface on
  `CR.*` until that's fixed (HANDOFF4 §6.1).
- **~21% of claims cite `calc:`/`sec:` instead of evidence** and are
  dropped before persist — so `claims` rows undercount what the report
  displays. Use envelope `claims[]` for display, the `claims` table for
  verification status.
- SONA v22 predates citation labels: its citations are raw UUIDs and
  `citationMap` is empty. The connector falls back correctly, but SONA
  will look uglier than M&M until it is re-run.

## 8. Suggested first tasks

1. Wire `getReport(db, "M&M")` server-side and render **section E** —
   10 blocks, maps almost 1:1 to your Supply Chain cards, no compliance
   questions, exercises four of the five block types.
2. Build the five block renderers as one component set. Every section is
   just an ordered list of these; get them right once.
3. Build the citation chip + evidence popover (`resolveCitation` →
   `getEvidence`). Do this early — it shapes the type layer.
4. Then settle §5 (what F / the scoreboard / insufficiencies / verification
   look like) and §4's compliance question before building Valuation.
