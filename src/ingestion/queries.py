"""
Hand-curated search queries for URL discovery (ddgs), one bank per research
layer. This is deliberately dumb, deterministic Python — the finance
knowledge lives in the keywords, not in a model.

Tuning guidance:
- Anchor queries to institutions and primary publishers (RBI, MOSPI, SIAM,
  FADA, ACMA, IEA/OPEC, exchanges) — it pulls authoritative pages above
  SEO spam.
- Append "latest" / a current context word where freshness matters; ddgs
  has no date filter worth trusting.
- Site hints ("screener.in", "valuepickr", "economictimes", "livemint",
  "moneycontrol") steer stock queries to the pages Indian investors
  actually read.

Each entry: (query, doc_type) where doc_type must be a valid
source_documents.type: 'annual_report' | 'concall_transcript' | 'news' |
'brokerage_report' | 'regulatory_filing' | 'macro_data' |
'industry_report' | 'other'.

Company queries are templates — format with company=..., ticker=... —
and carry their own source_type for the chunk filtering in nodes.py.
"""

# --- MACRO (source_type: "macro") --------------------------------------
MACRO_QUERIES = [
    ("india gdp growth latest quarter data mospi rbi",              "macro_data"),
    ("global gdp growth outlook imf world bank latest",             "macro_data"),
    ("india cpi inflation latest data",                             "macro_data"),
    ("rbi monetary policy committee repo rate latest decision",     "macro_data"),
    ("us fed fomc interest rate decision latest",                   "macro_data"),
    ("crude oil price today brent outlook iea opec",                "macro_data"),
    ("crude oil price forecast year end",                           "news"),
    ("gold price today outlook world gold council",                 "macro_data"),
    ("steel price india hrc trend latest",                          "macro_data"),
    ("global steel price outlook worldsteel",                       "industry_report"),
    ("inr usd exchange rate outlook rbi intervention",              "news"),
    ("india trade deal agreement latest news",                      "news"),
    ("india union budget capex manufacturing pli latest",           "news"),
]

# --- SECTOR: auto / auto components (source_type: "industry") -----------
# The POC pilot is an auto-components company, so only the auto bank exists.
# Adding a sector later = adding another list here and routing on the
# company's sector entity.
SECTOR_AUTO_QUERIES = [
    ("india auto sales latest month siam data",                     "industry_report"),
    ("fada vehicle retail sales latest month india",                "industry_report"),
    ("india passenger vehicle sales market share latest",          "industry_report"),
    ("india two wheeler sales market leaders latest",               "industry_report"),
    ("india ev sales penetration latest month",                     "industry_report"),
    ("india tractor commercial vehicle sales latest",               "industry_report"),
    ("india auto components industry acma outlook exports",         "industry_report"),
    ("auto component industry india margin outlook steel cost",     "news"),
    ("pli scheme auto components incentive update india",           "news"),
    ("rare earth magnet supply china export curbs auto industry",   "news"),
    ("global oem ev platform sourcing india suppliers",             "news"),
]

# --- COMPANY (templates; source_type per query) --------------------------
COMPANY_QUERY_TEMPLATES = [
    ("{company} latest quarterly results",                    "filing",   "regulatory_filing"),
    ("{company} results press release bse nse announcement",  "filing",   "regulatory_filing"),
    ("{company} earnings concall transcript latest",          "concall",  "concall_transcript"),
    ("{company} annual report highlights",                    "filing",   "annual_report"),
    ("{company} screener.in",                                 "filing",   "other"),
    ("{company} valuepickr discussion",                       "news",     "other"),
    ("{company} news economictimes livemint moneycontrol",    "news",     "news"),
    ("{ticker} brokerage report target price rationale",      "news",     "brokerage_report"),
]
