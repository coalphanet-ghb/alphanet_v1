# auto_oem — sector ingestion skill doc (Round 3.3)

> Git-versioned sector INGESTION knowledge: trusted sources, what to
> extract, how to analyse this sector's data. Consumed by the Round-4
> sector trusted-source reads (loaded via `packs.ingest_doc`); the
> synthesis overlays stay in `auto_oem.json`. The members registry
> (peer set + backbone scope) also lives in that JSON.

## Trusted sources (sector layer)

| Source | What it carries | Cadence |
|---|---|---|
| siam.in (SIAM) | wholesale production/sales by segment (PV/CV/2W/3W/tractor) | monthly |
| fada.in (FADA) | retail registrations + dealer inventory commentary | monthly |
| vahan dashboard (parivahan) | registration-level splits incl. fuel type / EV share | monthly |
| tractor association prints (TMA) | tractor volumes — the rural-demand proxy | monthly |
| rating agency sector outlooks (ICRA/CRISIL auto OEM notes) | demand outlooks, discounting trends, credit view | occasional |
| pib.gov.in (FAME/EMPS/PM-eDrive, scrappage, GST notifications) | demand-side policy with effective dates | event-driven |

## What to extract (sector reads)

- Volume prints per segment WITH period labels and wholesale-vs-retail
  basis (SIAM vs FADA vs VAHAN numbers differ — record the source class).
- EV penetration by segment and month; charging-infra milestones.
- Discounting/inventory commentary (FADA dealer surveys) — the
  margin-pressure leading indicator.
- Monsoon/rural indicators when tied to tractor/2W demand statements.
- Policy events with dates (GST changes, FAME allocations, emission
  norm deadlines — BS7/CAFE-3 with effective dates).
- NEVER extract per-company financials from sector pages — the numeric
  backbone (screener) is authoritative for member financials.

## How to analyse (sector-level judgement notes)

- Wholesale (SIAM) vs retail (FADA) divergence = channel filling or
  destocking; flag it before crediting an OEM's "growth" print.
- Segment mix matters more than totals: SUV share gains at a PV OEM are
  margin-accretive; entry-2W weakness is an affordability signal.
- Tractors follow monsoon + rural cash flows with a season lag — check
  IMD/monsoon prints before reading tractor volumes as share shifts.
- EV share moves are policy-sensitive (incentive cliffs distort
  month-on-month EV prints — prefer 3-month views).
- Post-demerger Tata Motors: TMPV (PV) and TMCV (CV) are separate
  listings — never mix their volumes or multiples in comparisons.
