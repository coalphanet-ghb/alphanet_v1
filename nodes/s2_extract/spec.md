# s2_extract — document extraction (LLM + url_context)

## Purpose
Turn fetched documents into (a) verbatim evidence passages, (b) structured
metric candidates, (c) cross-block tags. One call per solo doc / per batch
group. THE only node that creates evidence — everything downstream cites
what this node captures. Extraction is NOT analysis: no opinions, no
synthesis, no arithmetic.

## Inputs
- URL(s) via url_context (per s1 plan) + `doc_class` + company profile
  (name/aliases/ticker, fiscal quarter map) + seeded entity name list

## Instructions (prompt body)

You are an ingestion instrument. From the document(s), extract — VERBATIM,
never paraphrased — every passage relevant to the focus list of your
doc_class (below). For batched URLs, open each source's output with
`=== SOURCE: <url> ===`. For every passage record page/section/timestamp
markers as printed. Do not summarize. Do not add commentary. Do not
compute. If a document is unreadable or irrelevant, say exactly that.

**Numbers:** wherever a passage contains a reportable number (financial
statement line, ratio, volume, price, guidance figure), ALSO emit a
`metric_candidate` with the value EXACTLY as printed plus its printed
unit ("₹ 1,234 cr", "12.4%", "45,210 units"), period as printed
("Q3FY26", "FY25", "Oct-25"), and basis if stated (consolidated/
standalone). Flag ambiguous units/periods `"ambiguous": true` rather than
guessing.

**Tags (emit whenever seen, any doc_class):**
- `risk_signal` — any passage describing a threat, dependence, dispute,
  decline, covenant, warning, auditor remark
- `guidance_item` — any forward-looking management commitment: {metric,
  period, value_or_direction, verbatim_quote, speaker if named}
- `supply_chain_edge` — any stated relationship: {from_entity, relation
  (supplies_to | customer_of | input_cost_for | single_source_from |
  exports_to), to_entity, verbatim_quote}
- `peer_mention` — competitor named in a competitive context
- `event` — dated corporate event (order win, capex approval, resignation,
  rating action, penalty)

## Doc-class focus lists

| doc_class | Extract with priority |
|---|---|
| `concall` | ALL guidance statements (with speaker); volume/demand commentary; margin walk explanations; capex/order-book updates; every analyst question that management dodged or answered defensively (verbatim Q + A); one-off explanations |
| `annual_report` | Accounting-policy notes (revenue recognition, depreciation, capitalization); RM/cost-of-materials breakdown; segment revenue/results/capital-employed; top-customer disclosures; RPT note (amounts + counterparties); contingent liabilities; CWIP; borrowings schedule; auditor report language incl. CARO; MD&A demand/strategy passages; risk factors (specific ones, skip boilerplate); remuneration; pledge |
| `investor_presentation` | Segment/revenue mix charts (as numbers); order book/new wins; capacity + utilization; capex plans with amounts/timelines; market-share claims; strategy targets |
| `results_pdf` | Every statement line item as printed (P&L, BS if included, CF if included), quarter + YoY comparatives; exceptional items + notes; segment tables; auditor limited-review remarks |
| `rating_rationale` | Rating + outlook + change; EVERY strength/weakness listed; leverage/coverage numbers cited; liquidity assessment; customer/supplier concentration statements; guidance/expectation statements by the agency |
| `screener_page` | The full ratio/statement tables (each cell → metric_candidate); shareholding summary; price/market cap/multiples as displayed |
| `shareholding` | Category-wise holding %, quarter trend, pledge % |
| `news_batch` | Dated events and direct quotes only; skip opinion/anonymous-sourced speculation; note publication + date per item |
| `sector_page` | Industry data points (volumes, prices, growth) with periods; association/agency outlook statements (recent AND medium-term views) |
| `macro_page` | Indicator values with dates; official/institutional forecasts with horizon; policy decisions with effective dates |
| `valuepickr` | Distinct bull arguments and bear arguments (verbatim, attributed "forum user"); factual claims worth verifying — tag each `risk_signal` or `event`; NEVER extract as fact, always as "claimed" |

## Output (JSON)
```json
{"sources": [{"url": "...", "readable": true, "doc_class": "concall",
  "passages": [{"text": "<verbatim>", "page_or_timestamp": "p.4",
                "entities_mentioned": ["Steel", "Bosch"],
                "tags": ["risk_signal"]}],
  "metric_candidates": [{"name": "revenue", "value_printed": "₹ 8,412 cr",
                "period_printed": "Q3FY26", "basis": "consolidated",
                "statement": "P&L", "ambiguous": false,
                "quote_location": "p.2 table"}],
  "guidance_items": [...], "supply_chain_edges": [...],
  "peer_mentions": [...], "events": [...] }]}
```

## Quality checklist
- [ ] Zero paraphrase: spot-check any passage against source verbatim
- [ ] Every number in passages also appears as a metric_candidate
- [ ] No arithmetic anywhere (no computed totals, no unit conversions)
- [ ] Batched output has SOURCE delimiters exactly; parseable
- [ ] Dodged analyst questions captured (concall) — highest-value signal
- [ ] Ambiguity flagged, not resolved by guessing

## Golden example (fragment)
Input (concall p.7): *"We are guiding for 25-27% EBITDA margin for FY27
as the Halol plant ramps."* →
passage{text: as printed, page:"p.7", tags:["guidance_item"]};
guidance_item{metric:"EBITDA margin", period:"FY27",
value_or_direction:"25-27%", quote:"...", speaker:"CFO"};
metric_candidate{name:"ebitda_margin_guidance", value_printed:"25-27%",
period_printed:"FY27", ambiguous:false}
