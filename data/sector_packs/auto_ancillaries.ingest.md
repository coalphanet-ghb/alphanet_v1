# auto_ancillaries — sector ingestion skill doc (Round 3.3)

> Git-versioned sector INGESTION knowledge: trusted sources, what to
> extract, how to analyse this sector's data. Consumed by the Round-4
> sector trusted-source reads (loaded via `packs.ingest_doc`); the
> synthesis overlays stay in `auto_ancillaries.json`. The members
> registry (peer set + backbone scope) also lives in that JSON.

## Trusted sources (sector layer)

| Source | What it carries | Cadence |
|---|---|---|
| acma.in (ACMA) | industry turnover, exports/imports, EV-component trends, policy asks | half-yearly + events |
| siam.in (SIAM) | OEM production/sales volumes (the demand signal for ancillaries) | monthly |
| fada.in (FADA) | retail registrations — leading demand indicator vs SIAM wholesale | monthly |
| ibef.org auto-components page | market size, FDI, capex aggregates | quarterly-ish |
| rating agency sector outlooks (ICRA/CRISIL/CARE auto-ancillary sector notes) | margin/leverage outlooks, sector credit view | occasional |
| pib.gov.in (PLI-Auto, FAME/EMPS notifications) | incentive schemes shaping EV component capex | event-driven |

## What to extract (sector reads)

- Industry growth prints WITH period labels (production volumes by
  segment: PV/CV/2W/tractor; component industry turnover; export mix).
- EV transition data: EV penetration by segment, localisation targets,
  PLI beneficiary lists — these drive every member's EV-optionality
  narrative.
- Input-cost series mentions: steel (alloy/special), aluminium, copper,
  rare-earth magnets — capture direction + period, values verbatim.
- Policy events with dates (PLI disbursements, import duty changes,
  CBAM/tariff measures touching exports).
- NEVER extract per-company financials from sector pages — the numeric
  backbone (screener) is authoritative for member financials.

## How to analyse (sector-level judgement notes)

- Ancillary revenue follows OEM production with a lag; check SIAM
  volumes BEFORE judging a member's growth print as company-specific.
- Export-heavy members (Sona, Motherson, Bharat Forge) decouple from
  Indian OEM volumes — weigh US/EU class-8 truck and PV cycles.
- Content-per-vehicle expansion (EV, premiumisation) can offset flat
  volumes — a flat-volume + growing-revenue quarter is mix, not share gain.
- Rare-earth magnet supply (China export licensing) is a sector-wide
  chokepoint for EV motor makers — treat as systematic, not company risk.
