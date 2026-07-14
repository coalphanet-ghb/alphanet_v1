# AlphaNet — Source Map & Query Banks (v0.1 draft for review)

> Reverse-engineered from REPORT_BLUEPRINT.md v0.3 (frozen). This is the
> master registry of WHERE every report block's information comes from and
> WHAT we search to find it. Once approved, this becomes:
> `src/ingestion/queries.py` v2 (universal + per-sector banks) and the
> sector pack registry.
>
> Access-note legend: [PDF] url_context-friendly PDFs · [HTML] readable
> pages · [JS] JavaScript-heavy, url_context may fail — prefer its press
> releases or news coverage · [BOT] known bot-hostile — reach via news
> coverage or Google cache, never directly · [PAY] paywalled — excluded,
> use news quotes of its data.
> All links are from training knowledge — spot-check before wiring in.

---

## 1. Sector taxonomy (attach packs at sub-sector level)

**1. Automobiles & Mobility**
auto OEM – PV · auto OEM – 2W · auto OEM – CV · tractors/farm equipment ·
auto ancillaries/components · tyres · batteries (lead-acid + Li-ion) ·
EV pure-plays · auto engineering/IT (ER&D: KPIT, Tata Elxsi type) ·
auto dealerships

**2. BFSI**
private banks · PSU banks · small finance banks · NBFC – diversified ·
NBFC – housing finance · NBFC – vehicle finance · NBFC – gold loans ·
NBFC – microfinance · insurance – life · insurance – general ·
AMCs · capital-market infra (exchanges, depositories, RTAs) · broking ·
wealth/fintech/payments · credit rating agencies

**3. IT & Digital**
IT services – large cap · IT services – mid cap · ER&D services ·
SaaS/products · internet platforms (ecommerce, delivery, classifieds,
travel) · data centers/cloud infra · gaming

**4. Consumer**
FMCG – food & beverages · FMCG – home & personal care · tobacco ·
FMEG (fans, wiring, lighting, small appliances) · consumer durables
(AC, refrigeration, washing) · paints & adhesives · QSR & food services ·
retail – grocery/value · retail – apparel/fashion · retail – jewellery ·
footwear · alco-bev (spirits, beer) · e-commerce enablers

**5. Healthcare**
pharma – domestic formulations · pharma – US generics · pharma –
API/CRAMS/CDMO · biotech & vaccines · hospitals · diagnostics ·
medical devices & consumables

**6. Chemicals & Agri-inputs**
specialty chemicals · commodity/bulk chemicals · fluorochemicals ·
agrochemicals · fertilizers · dyes & pigments · industrial gases ·
carbon black/derivatives

**7. Industrials & Capital Goods**
capital goods/heavy engineering · power T&D equipment (transformers,
switchgear) · cables & wires · EPC – power/transmission · EPC – roads/
urban infra · EPC – water · defence · railways (rolling stock, signalling,
wagons) · EMS (electronics manufacturing services) · bearings & industrial
consumables · HVAC/cooling · solar module/cell manufacturing

**8. Energy & Utilities**
power gen – thermal · power gen – renewables (solar/wind IPPs) · hydro ·
power transmission & distribution utilities · power exchanges ·
oil & gas – upstream · refining & OMCs · city gas distribution ·
LNG infra · coal & mining services

**9. Materials**
cement · steel · non-ferrous (aluminium, copper, zinc) · mining ·
pipes (PVC/CPVC/steel) · paper & packaging · glass · ceramics/tiles/
sanitaryware · wood panels/laminates

**10. Infrastructure, Realty & Logistics**
real estate – residential · real estate – commercial/REITs · InvITs ·
construction/diversified EPC · ports · airports · logistics – 3PL/express ·
logistics – rail/container · shipping · warehousing

**11. Agri & Allied**
sugar · tea/coffee/plantations · dairy · poultry/aqua/feed · seeds ·
agri warehousing & services

**12. Telecom & Media**
telecom operators · telecom towers/infra · broadcast & OTT · multiplexes ·
print media

**13. Textiles**
spinning/yarn · garments/apparel export · home textiles ·
technical textiles

**14. Services (other)**
hotels & tourism · aviation · education & training · staffing/HR ·
facility management/security · travel platforms

**15. Diversified / holding companies**

> Pilot packs to author first: **auto OEM – PV** (M&M is PV+tractors+EV)
> and **auto ancillaries** (Sona). Every other sub-sector gets a pack by
> the same template as coverage expands.

---

## 2. Universal sources, mapped to report sections

These apply to EVERY company regardless of sector.

### Tier-1 (primary, must-ingest)

| Source | Feeds sections | Link | Access |
|---|---|---|---|
| BSE corporate announcements + results | A,B,D,F,H | bseindia.com/corporates/ann.html | [HTML/PDF] |
| NSE corporate filings | A,B,D,F,H | nseindia.com/companies-listing/corporate-filings-announcements | [BOT] — use BSE mirror of same filings |
| Company annual report (MD&A, segments, RPT, risk factors, raw-material notes) | B,D,E,F,H | company IR page / BSE attachment | [PDF] |
| Company investor presentation | B,D,E,F | company IR page / BSE attachment | [PDF] |
| Earnings concall transcript (every quarter, accumulating history) | D,E,F,H | BSE attachments; screener.in concall tab; researchbytes.com | [PDF/HTML] |
| Quarterly results press release + statements | A,D | BSE attachment | [PDF] |
| **Credit rating rationales — ICRA / CRISIL / CARE / India Ratings** (dense, free, underused: leverage, liquidity, customer concentration, risks, guidance checks) | D,E,F,H | icra.in · crisilratings.com · careratings.com · indiaratings.co.in | [PDF/HTML] |
| Screener.in company page (10y financials, ratios, peers, shareholding, price) | A,D,G,I | screener.in/company/{TICKER}/ | [HTML] — needs viability test |
| Shareholding pattern + promoter pledge disclosures | A,F | BSE shareholding tab | [HTML] |

### Tier-2 (supplementary/cross-check)

| Source | Feeds | Link | Access |
|---|---|---|---|
| Trendlyne (historical valuation percentile, sharing data) | I | trendlyne.com | [JS] partial |
| Tijori Finance (segment data, operational KPIs) | B,D | tijorifinance.com | [JS] partial |
| Moneycontrol / ET / Livemint / Business Standard company news | B,F,H | news sites | [HTML], some [PAY] |
| ValuePickr forum threads (bull/bear arguments to *check*, never cite as fact) | H,I | forum.valuepickr.com | [HTML] |
| NSE indices factsheets (sector P/E context) | I | niftyindices.com | [PDF] |
| DRHP/RHP for recent IPOs (richest single doc that exists for them) | B,E,F,H | SEBI / company | [PDF] |

### Macro layer (feeds section C for every company)

| Source | What | Link | Access |
|---|---|---|---|
| RBI — MPC statements, bulletins, DBIE database | rates, credit, INR, system liquidity | rbi.org.in · dbie.rbi.org.in | [HTML/PDF] |
| MOSPI | GDP, CPI, IIP | mospi.gov.in | [HTML/PDF] |
| PIB releases | GDP/GST/policy announcements | pib.gov.in | [HTML] |
| Ministry of Finance — Monthly Economic Review | broad macro view | dea.gov.in | [PDF] |
| IMF WEO / World Bank GEP | global growth, recent + medium-term view | imf.org · worldbank.org | [HTML/PDF] |
| PPAC | crude, fuel prices/consumption | ppac.gov.in | [HTML/PDF] |
| FBIL / RBI reference rate | INR/USD | fbil.org.in | [HTML] |
| Commerce ministry / DGCI&S Tradestat | exports/imports, trade deals | tradestat.commerce.gov.in | [JS] — use PIB/news |
| IMD | monsoon forecast (rural demand) | imd.gov.in | [HTML] |
| US Fed FOMC statements | global rates | federalreserve.gov | [HTML] |
| worldsteel / LME via news | steel, base metals | worldsteel.org | [HTML] |
| Tradingeconomics (aggregator fallback) | most indicators on one page | tradingeconomics.com | [HTML] |

---

## 3. Universal company query bank v2 (templates)

Grouped by the block they feed. `{company}`, `{ticker}`, `{quarter}`,
`{fy}` are slots. (doc_type mapping done at implementation.)

**A/D — statements & ratios**
- `{company} screener.in`
- `{company} quarterly results {quarter} press release pdf`
- `{company} audited financial results {fy} bse`

**B — business**
- `{company} annual report {fy} pdf`
- `{company} investor presentation {quarter} pdf`
- `{company} segment revenue mix products`

**E — supply chain**
- `{company} raw materials suppliers annual report`
- `{company} imports sourcing china dependence`
- `{company} plants capacity locations`
- `{company} customers order book concentration`

**F — management, governance, guidance**
- `{company} earnings concall transcript {quarter}`
- `{company} concall transcript researchbytes OR screener`
- `{company} management guidance {fy}`
- `{company} capex expansion announcement`
- `{company} shareholding pattern promoter pledge`
- `{company} credit rating rationale icra OR crisil OR care`

**H — risks**
- `{company} credit rating rationale` (reused — best structured risk source)
- `{company} annual report risk factors`
- `{company} litigation penalty regulatory action news`

**I — valuation**
- `{company} historical PE valuation trendlyne`
- `{company} valuation expensive OR cheap analysis`

**G — peers:** no extra queries — the peer set comes from
entity_relationships and each peer's own A/D data (already ingested or
ingested on demand via the same templates).

## 4. Macro query bank v2

Per frozen blueprint C: every macro entity needs a **recent view** and a
**medium-term/expected view** — so entities get query PAIRS.

- Repo rate: `rbi mpc repo rate decision latest` + `rbi repo rate outlook economists forecast`
- India GDP: `india gdp growth latest quarter mospi` + `india gdp forecast rbi imf {fy}`
- CPI: `india cpi inflation latest month` + `india inflation outlook rbi projection`
- Crude: `brent crude price today` + `crude oil price forecast iea opec eia`
- INR/USD: `rupee dollar exchange rate today` + `inr usd outlook forecast`
- Steel: `india hrc steel price latest` + `steel price outlook india {fy}`
- Copper/base metals: `lme copper price today` + `copper price outlook`
- Gold: `gold price india today` + `gold price outlook world gold council`
- US Fed: `us fed fomc decision latest` + `fed rate cut path expectations`
- Trade policy: `india us trade deal tariff latest news` + `india fta eu uk update`
- Monsoon/rural: `imd monsoon forecast latest` + `rural demand recovery india indicators`
- Fiscal/capex: `india union budget capex infrastructure allocation` + `gst collections latest month`
- Global growth: `imf world economic outlook latest gdp` (single, doc has both views)

## 5. Sector source index (associations, regulators, data portals — ALL groups)

| Sector group | Primary data sources (link · access) |
|---|---|
| Auto OEM (PV/2W/CV/tractor) | SIAM siam.in [HTML] · FADA retail data fada.in [PDF] · VAHAN dashboard [JS→news] · Tractor & Mechanization Assoc. via news · PIB auto PLI |
| Auto ancillaries | ACMA acma.in [HTML/PDF] · SIAM/FADA (derived demand) · steel/alu prices · EXIM via news |
| Auto ER&D / IT | NASSCOM ER&D reports [PDF] · client OEM capex news · company decks |
| EV ecosystem | VAHAN EV dashboard [JS→news] · PM E-DRIVE / Ministry of Heavy Industries heavyindustries.gov.in [HTML] · battery cell price news · CEA charging infra |
| Banks / NBFC | RBI DBIE (sectoral credit, deposits) [HTML] · RBI Financial Stability Report [PDF] · company Basel III / Pillar 3 disclosures [PDF] · TransUnion CIBIL via news |
| Insurance / AMC / capital-market infra | IRDAI monthly figures irdai.gov.in [HTML] · Life Insurance Council · **AMFI monthly AUM amfiindia.com** [HTML] · SEBI bulletins · NSE/BSE volume stats |
| IT services / SaaS | NASSCOM [PDF] · ISG/deal-flow via news · Naukri JobSpeak (hiring proxy) via news · USD/INR |
| FMCG | NielsenIQ prints via news · company volume prints · IMD monsoon · MNREGA/rural wage data via news |
| FMEG / consumer durables | CEAMA via news · RAC/appliance volume news · copper/commodity prices · real-estate completions |
| EMS / electronics | MeitY PLI updates meity.gov.in [HTML] · ICEA icea.org.in · global client news |
| Pharma | USFDA inspection/ANDA data accessdata.fda.gov [HTML] · CDSCO · AIOCD-AWACS monthly via news · Pharmexcil exports · WHO GMP news |
| Chemicals (specialty/agro/bulk) | Chemexcil · crude derivative prices (PPAC) · China price indices via news · DGCI&S trade data · company-specific molecule news |
| Capital goods / T&D equipment / cables | **IEEMA production data ieema.org** [HTML] · CEA transmission plans cea.nic.in [PDF] · PFC/REC/SECI/PGCIL tender awards via news · LME copper/aluminium |
| EPC (power/roads/water) | NHAI awards via news · Ministry of Jal Shakti · CEA capacity addition [PDF] · order-book disclosures (exchange filings) |
| Defence / railways | MoD contract announcements pib · defence budget docs · Indian Railways capex/wagon tenders via news |
| Power gen & utilities | **CEA monthly generation/capacity cea.nic.in** [PDF] · Grid-India/POSOCO · SECI auction results · Ministry of Power pib · IEX market data iexindia.com [HTML] |
| Oil & gas / CGD | **PPAC ppac.gov.in** [HTML/PDF] · MoPNG pib · PNGRB (CGD authorizations) · OPEC/IEA monthly [PDF] |
| Cement | DPIIT/IIP cement production · housing/infra capex news · petcoke/coal prices · dealer channel checks via brokerages (news quotes) |
| Steel / metals / mining | **JPC jpcindiansteel.nic.in** [HTML] · worldsteel · LME · Coal India e-auction premiums via news · ministry of mines |
| Real estate / REITs | RERA state portals [JS] · Anarock/Knight Frank/JLL public reports [PDF] · CREDAI · RBI housing price index |
| Ports / logistics / aviation | Indian Ports Association cargo data ipa.nic.in [HTML] · railway freight data via news · E-way bill volumes (GSTN via PIB) · **DGCA monthly traffic dgca.gov.in** [PDF] |
| Telecom | **TRAI monthly subscriber reports trai.gov.in** [PDF — excellent] · DoT · company ARPU prints |
| Media / gaming | TRAI broadcast data · BARC ratings via news · box office trackers via news |
| Textiles | CITI · Texprocil export data · Cotton Association of India prices · China+1 trade news |
| Sugar / agri | ISMA isma.co.in · Food Ministry (FRP/MSP) pib · IMD · global raw sugar prices via news |
| Hotels / tourism | FHRAI · Ministry of Tourism arrivals data · STR/HVS occupancy-ADR via news |
| Diversified/holding | constituent-company sources + holdco discount news |

## 6. Sector query banks — the 12 named sub-sectors (authored now)

Pattern per sector: ~8–12 queries covering (i) volume/demand prints,
(ii) pricing/input costs, (iii) policy, (iv) structure/competition,
(v) medium-term outlook. Remaining sectors get banks by this template
when their first company is onboarded.

**Auto OEM (PV/tractor/CV/2W)**
- `siam monthly auto sales data latest press release`
- `fada vehicle retail data latest month press release`
- `india passenger vehicle sales market share latest month`
- `india two wheeler sales latest month`
- `india cv sales cycle latest`
- `tractor sales latest month india`
- `india car discounts inventory dealer latest`
- `auto sector outlook {fy} icra crisil india`
- `pm e-drive ev incentive scheme update`
- `auto loan rates india trend`

**Auto ancillaries**
- `acma auto component industry performance latest`
- `auto component exports india latest data`
- `india auto ancillary outlook {fy} icra`
- `steel price india auto industry impact`
- `rare earth magnet supply china auto india`
- `oem platform sourcing india suppliers ev`
- `auto components pli scheme beneficiaries update`

**Auto ER&D / IT**
- `automotive er&d spending trend global`
- `software defined vehicle india er&d companies`
- `global oem r&d budget cuts latest news`
- `nasscom er&d india report latest`

**EV ecosystem**
- `india ev sales vahan latest month`
- `ev penetration india two wheeler passenger vehicle latest`
- `battery cell prices lithium latest trend`
- `pm e-drive subsidy disbursement update`
- `charging infrastructure india rollout latest`
- `china graphite lithium export controls impact india`

**Power infra EPC / T&D**
- `power grid transmission capex india plan cea`
- `transmission tender awards tbcb latest`
- `india power demand peak latest cea`
- `renewable capacity addition india latest month`
- `power t&d capex outlook {fy} india`

**Transformers / switchgear (power ancillaries)**
- `ieema transformer production data india`
- `transformer demand supply shortage india latest`
- `switchgear market india growth data centers`
- `crgo steel price availability india`
- `transformer export orders india us grid`

**Cables & wires**
- `cables wires industry india growth latest`
- `copper aluminium price trend lme latest`
- `housing wires demand india real estate`
- `cables exports india latest data`

**FMCG**
- `fmcg volume growth nielseniq latest quarter india`
- `rural vs urban fmcg demand latest`
- `fmcg raw material palm oil crude derivatives prices`
- `fmcg price hikes grammage latest news`
- `monsoon rural income fmcg demand outlook`

**FMEG**
- `fmeg fans wires lighting demand latest quarter`
- `electrical consumer goods india market share`
- `copper price impact fmeg margins`
- `real estate completions electrical demand india`

**Consumer durables**
- `air conditioner sales india latest season`
- `consumer durables demand festive latest`
- `ac compressor imports pli india`
- `energy efficiency norms bee ac refrigerator change`

**EMS**
- `ems electronics manufacturing india pli latest`
- `smartphone export india latest data`
- `ems companies order wins india latest`
- `component ecosystem semicon india update`

**Pharma (formulations/generics/CDMO)**
- `indian pharma market growth aiocd latest month`
- `us generics pricing pressure latest commentary`
- `usfda inspection indian pharma plants latest`
- `biosecure act cdmo india opportunity update`
- `api prices china dependence india latest`
- `nlem price control update india`

**Specialty chemicals**
- `specialty chemicals india demand recovery latest`
- `china chemical prices dumping india impact`
- `agrochemical inventory destocking global latest`
- `crude derivatives feedstock prices trend`
- `china plus one specialty chemicals india orders`

---

## 7. Known access risks (to test in the next step's spike)

1. **screener.in via url_context** — single most valuable structured
   source; must test whether tables render. If blocked: fall back to BSE
   results PDFs + computing ratios ourselves (more work, more control).
2. **NSE is bot-hostile** — never rely on it; BSE carries the same filings.
3. **JS dashboards (VAHAN, Tradestat, RERA)** — take their data via PIB
   press releases and news coverage instead.
4. **Paywalled press (ET Prime, BS premium)** — headline/lede often
   readable; never depend on body text.
5. **PDF-heavy sources (ratings, TRAI, CEA, DGCA, annual reports)** —
   url_context handles PDFs, but big ones may hit the deadline limit we
   already saw; may need size-aware handling (skip-and-flag exists).

## Changelog
- v0.1 (2026-07-14): initial draft for review.
