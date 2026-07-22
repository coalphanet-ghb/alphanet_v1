# GENERALIZATION PLAN — Nifty Midcap 150 (step 1 toward Nifty 500)

> Owner-requested 2026-07-22, after the five-round plan went
> code-complete. Question: is the flow general enough to write reports
> for all Midcap 150 companies, and what must change? This doc is the
> audit verdict + the universe registry + the phased preparation plan.
> Scope: FIRST-report generation for Midcap 150. Nifty 500, the update
> pipeline and the UI stay parked.

## 0. The universe (built 2026-07-22, official NSE CSV)

`data/universe/nifty_midcap150.json` — 150 companies with name /
ticker / screener_slug / NSE industry / ISIN / pack_id (null until a
pack claims them). Raw CSV kept at `data/universe_midcap150_raw.csv`.

Industry distribution (NSE macro classification):

| # | Industry | Note |
|---|---|---|
| 36 | Financial Services | banks/NBFC/AMC/insurance/exchanges — the compute layer's weakest fit; OWN PHASE |
| 19 | Capital Goods | industrial statements — current pipeline fits |
| 14 | Healthcare | pharma + hospitals + diagnostics — 2–3 sub-packs |
| 10 | Automobile & Auto Components | ~half already covered (BHARATFORG, ENDURANCE, SCHAEFFLER, UNOMINDA, ESCORTS in index; packs exist) |
| 8×3 | FMCG / IT / Consumer Services | standard industrials/services |
| 7 | Consumer Durables | standard |
| 6×2 | Chemicals / Power | standard + utility twist |
| 5 | Metals & Mining | commodity twist (cyclical valuation) |
| 4×3 | Oil&Gas / Telecom / Realty | realty needs pre-sales/NAV vocabulary |
| 3×2+2×2+1 | Construction Materials / Services / Diversified / Textiles / Construction | tail |

NOTE: SONA and M&M are NOT constituents — our pilots were built off-index.
The auto packs still cover the 10 auto constituents.

## 1. Audit verdict — what is already general vs not

**GENERAL (no change needed):**
- Report skeleton (REPORT_BLUEPRINT frozen; packs carry variation — by design)
- ENVELOPE_CONTRACT + all citation forms + validator (contract v1.0.0)
- Node specs: sector-agnostic with [[SECTOR_OVERLAY]] slots; remaining
  auto mentions are illustrative examples only (light edit pass listed in G1)
- Extraction: _SCHEMA, AR bundles, trails-pass, focus-hash — all generic
  (one cosmetic "EV/BEV share" in the PPT focus)
- Query banks: company docs/news generic; macro India-generic; sector
  queries come from packs ✓
- Sector backbone + registry (Round 3) — universe-ready by construction
- Deterministic spine: unit guard, pool-gate, identity validation, dedup
- diff_golden, telemetry, manifest — per-ticker, generic

**NOT GENERAL (the gap list):**
| Gap | Where | Fix phase |
|---|---|---|
| Company onboarding hardcoded (2-entry menu; hand-written aliases/segments/slugs) | config.COMPANIES, main.py | G1 |
| Packs: 3 exist (~auto×2 + untested banks); need ~18–22 sub-sector packs | data/sector_packs/ | G2/G3 |
| load_pack raises when pack missing — no generic fallback | src/packs.py | G1 |
| Seeds hand-authored for auto only (entities, belongs_to_sector, peer_of) | data/seed_entities.json, scripts/seed_entities.py | G1 auto-seeder |
| Financials: compute modules (OPM/WC/piotroski/forensic battery) and D1–D3 specs assume industrial statements; screener bank pages have different rows (NII/NIM/financing profit); banks.json skip_modules never live-tested | s3_compute, metric_names, statement specs | G3 |
| Sector-trusted domains hardcoded globally (SIAM/FADA/ACMA in TIER1) instead of per-pack | src/config.py TIER1_DOMAINS; .ingest.md hook exists but s1 doesn't consume yet | G2 |
| {segment} query slots come from hand-written profile segments | config → universe/pack default | G1 |
| No at-scale preflight (slug 404s, Yahoo identity, doc links) — the Tata-demerger lesson ×150 | new script | G0 |
| Goldens can't be hand-frozen ×150 — need a gate-based acceptance policy | process | G2 |

## 2. The phases

**G0 — Preflight the universe (zero LLM, ~free) [universe JSON: DONE]**
`scripts/preflight_universe.py`: for each of the 150 — screener
consolidated page resolves + parses (candidate count), doc links
present (AR/concalls/PPT), Yahoo `{ticker}.NS` identity-validates.
Output: readiness CSV (ok / slug-exception / yahoo-miss / thin-docs).
Fix slug exceptions (M&M-style URL encodings, renamed listings).
Gate: ≥95% of universe preflights clean; exceptions documented.

**G1 — Universe-driven onboarding (code, ~2 days of work)**
- Profile from universe: `--ticker <any symbol>` looks up
  data/universe/*.json (COMPANIES becomes overrides-only); aliases
  default to name tokens; segments default from pack.
- Auto-seeder: get_or_create entity, belongs_to_sector edge from the
  pack's sector_entity, member_of + peer_of edges between co-members
  (peer_of currently hand-seeded — generalize to sector co-membership).
- `generic_default` pack + load_pack fallback (loud log line, reduced
  sector sharpness, NEVER a crash) so any company can run day 1.
- Light spec-generalization pass (the audit's example-wording list).
Gate: a never-seeded, pack-less constituent (e.g. APLAPOLLO) produces
a full report end-to-end on generic_default with citations ≥98%.

**G2 — Pack wave 1: non-financials (~114 companies, ~15 packs)**
Priority order (companies covered per pack): capital_goods(19),
pharma + hospitals_diagnostics(14), fmcg(8), it_services(8),
consumer_services(8), consumer_durables(7), chemicals(6),
power_utilities(6), metals_mining(5), oil_gas(4), telecom(4),
realty(4), cement(3), services_logistics(3), tail(diversified/
textiles/construction → generic_default + overlays as needed).
Per pack: members from universe + sector_entity + overlays +
sector_queries + KPIs + valuation conventions + .ingest.md (trusted
sources — also wire s1 to consume them, replacing the global TIER1
additions). Knowledge source: extend ANALYST_KNOWLEDGE.md per sector.
**Acceptance policy at scale (replaces hand-frozen goldens):** freeze
ONE pilot golden per pack; every other company passes GATES ONLY —
citations ≥98%, schema_issues {}, verifier full coverage, unit-guard
log reviewed, zero not-generated sections.
Gate: 1 pilot report per pack owner-reviewed; batch of ~10 diverse
companies run clean.

**G3 — Financials wave (36 companies, the hard one)**
Sub-packs: banks(small-finance + private), nbfc_lending, amc_wealth,
insurance, exchanges_platforms. Work items: screener parser + canon
names for lender rows (NII, NIM, GNPA/NNPA, financing profit, CAR);
skip_modules live-validated (banks.json is untested theory);
D1/D2/D3 overlays rewritten for lender statements (the forensic
battery's accrual checks are wrong-shaped for banks); rating
rationales become the load-bearing doc class (they carry
asset-quality forward views). Pilot: one bank + one NBFC golden.
Gate: pilot goldens owner-reviewed; no industrial-metric leakage
(e.g. OPM/inventory days) in any financials report.

**G4 — Batch operations (the 150-run campaign)**
`scripts/run_universe.py`: sequential batch runner (RPM-serialized
anyway) with per-run gates, halt-on-systemic-failure (3 consecutive
gate failures), resume, and a telemetry ROLLUP report (cost/citations/
verifier/spirals per company — the sidecars already carry everything).
Sector backbones amortize: one refresh serves all members in a
sector's batch window.
Estimates at current measured costs: first runs ~$1.2–1.8/company
(fresh docs) → **~$200–270 for the index**; ~15–20 min/company
sequential → run in sector-batches over nights. Steady-state reruns
~$0.5–0.7.
Gate: full-universe campaign completes; rollup reviewed; failure list
< 10 companies with named causes.

## 3. Explicitly parked (Nifty 500 era)
Smallcap-grade data quality (thinner docs/concalls), the update
pipeline, UI, scheduling, restatement policy, multi-index universe
files (the registry format already supports them: one JSON per index).
