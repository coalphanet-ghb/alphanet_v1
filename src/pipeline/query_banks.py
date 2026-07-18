"""
Universal query banks (playbook §4). Sector queries come from the pack.
Each entry: (query_template, doc_class, priority, n_results).
doc_class drives the s2 extraction focus; priority drives budget cuts.
"""

from src.config import MAX_RESULTS_DOC_HUNT, MAX_RESULTS_DATA

# --- company docs (S1-U) ---------------------------------------------------
# {company} {ticker} {fy} {q} slots; expanded in s1.
COMPANY_DOC_QUERIES = [
    # (template, doc_class, priority 1-3, results)
    ("{company} annual report {fy} pdf",                        "annual_report",         1, MAX_RESULTS_DOC_HUNT),
    ("{company} investor presentation pdf",                     "investor_presentation", 1, MAX_RESULTS_DOC_HUNT),
    ("{company} quarterly results press release pdf",           "results_pdf",           1, MAX_RESULTS_DOC_HUNT),
    ("{company} credit rating rationale icra OR crisil OR care", "rating_rationale",     1, MAX_RESULTS_DOC_HUNT),
    ("{company} shareholding pattern promoter pledge",          "shareholding",          2, MAX_RESULTS_DATA),
    # Phase 5.4: own-history multiple series for I's percentile framing
    # (short alias: the full legal name buries these hunts in quote pages)
    ("{company_short} historical pe ratio",                     "valuation_history",     2, MAX_RESULTS_DOC_HUNT),
]

CONCALL_QUERY_TEMPLATES = [
    "{company} {q} {fy} earnings call transcript",
    "{company} concall transcript {q} {fy}",
]

COMPANY_NEWS_QUERIES = [
    ("{company} latest news",                                   "news_batch", 2, MAX_RESULTS_DATA),
    ("{company} order win capex expansion announcement",        "news_batch", 2, MAX_RESULTS_DATA),
    ("{company} litigation OR penalty OR regulatory action",    "news_batch", 2, MAX_RESULTS_DATA),
    ("{company} valuepickr",                                    "valuepickr", 3, MAX_RESULTS_DATA),
]

# --- macro (S1-M): pairs = recent view + medium-term view -------------------
# theme -> [(query, doc_class)]  (batched reads per theme)
MACRO_THEMES = {
    "rates_growth": [
        ("rbi mpc repo rate decision latest", "macro_page"),
        ("rbi repo rate outlook economists forecast", "macro_page"),
        ("india gdp growth latest quarter mospi", "macro_page"),
        ("india cpi inflation latest month", "macro_page"),
        ("us fed fomc decision latest", "macro_page"),
    ],
    "external": [
        ("rupee dollar exchange rate today outlook", "macro_page"),
        ("india us trade deal tariff latest news", "macro_page"),
    ],
    "fiscal_rural": [
        ("india union budget capex infrastructure latest", "macro_page"),
        ("imd monsoon forecast latest", "macro_page"),
        ("gst collections latest month", "macro_page"),
    ],
}

# Commodity queries are generated from the pack's macro_commodity_subset:
COMMODITY_QUERY_TEMPLATES = [
    "{commodity} price today india trend",
    "{commodity} price outlook forecast",
]

# Macro metric-candidate name → seeded entity name (extraction may only
# save observations for indicators it can map to an entity)
MACRO_METRIC_ENTITY_MAP = {
    "repo": "RBI Repo Rate",
    "gdp": "India",
    "cpi": "India",
    "inflation": "India",
    "crude": "Crude Oil",
    "brent": "Crude Oil",
    "steel": "Steel",
    "hrc": "Steel",
    "copper": "Copper",
    "aluminium": "Aluminium",
    "gold": "Gold",
    "rare earth": "Rare Earth Magnets",
    "usd": "INR/USD Exchange Rate",
    "inr": "INR/USD Exchange Rate",
    "rupee": "INR/USD Exchange Rate",
}
