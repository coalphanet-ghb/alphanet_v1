"""
Central configuration for AlphaNet.

Everything that would change between local dev and a future Cloud Run
deployment lives here, read from environment variables so the same code
runs unmodified in both places.
"""

import os
from dotenv import load_dotenv

load_dotenv()

# --- Gemini -----------------------------------------------------------
# Discovery uses NO LLM (ddgs). Gemini is used for reading known URLs
# (url_context) and synthesis. Two models, no fallback, no automatic
# retries (first error aborts; manual rerun is cheap because ingested
# URLs are reused). Calls self-throttle to the active model's RPM.
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
GEMINI_LITE_MODEL = os.environ.get("GEMINI_LITE_MODEL", "gemini-3.1-flash-lite")
GEMINI_LITE_RPM = int(os.environ.get("GEMINI_LITE_RPM", "15"))
GEMINI_MAIN_MODEL = os.environ.get("GEMINI_MAIN_MODEL", "gemini-3.5-flash")
GEMINI_MAIN_RPM = int(os.environ.get("GEMINI_MAIN_RPM", "5"))

# --- Supabase ---------------------------------------------------------
SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_SERVICE_ROLE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")

_PLACEHOLDER_MARKERS = ("your_", "your-project-ref")


def _is_placeholder(value: str) -> bool:
    return (not value) or any(m in value for m in _PLACEHOLDER_MARKERS)


def gemini_configured() -> bool:
    return not _is_placeholder(GEMINI_API_KEY)


def supabase_configured() -> bool:
    return not (_is_placeholder(SUPABASE_URL) or _is_placeholder(SUPABASE_SERVICE_ROLE_KEY))


# --- Pilot companies (main.py pick menu) --------------------------------
# `name` must match data/seed_entities.json so runs attach to the seeded
# entity. `pack_id` selects the sector pack; `segments` fill {segment}
# query slots; `screener_slug` builds deterministic screener URLs.
COMPANIES = [
    {
        "label": "SONA",
        "ticker": "SONACOMS",
        "name": "Sona BLW Precision Forgings Limited (Sona Comstar)",
        "pack_id": "auto_ancillaries",
        "segments": ["EV driveline", "differential assemblies"],
        "aliases": ["Sona BLW", "Sona Comstar"],
        "screener_slug": "SONACOMS",
        "peer_screener_slugs": ["BHARATFORG", "UNOMINDA", "SCHAEFFLER", "ENDURANCE"],
    },
    {
        "label": "M&M",
        "ticker": "M&M",
        "name": "Mahindra & Mahindra",
        "pack_id": "auto_oem",
        "segments": ["SUV", "tractor", "commercial vehicle"],
        "aliases": ["Mahindra", "M&M"],
        "screener_slug": "M%26M",
        "peer_screener_slugs": ["TATAMOTORS", "MARUTI", "ESCORTS"],
    },
]

# --- Read budget (playbook §0) ------------------------------------------
# Every URL read = 1 url_context call. P1 never cut; P3 cut first.
MAX_READ_CALLS = int(os.environ.get("MAX_READ_CALLS", "26"))
MAX_RESULTS_DOC_HUNT = 5         # ddgs results for document-hunt queries
MAX_RESULTS_DATA = 3             # ddgs results for data/news queries
MAX_URLS_MACRO = 4               # macro theme reads (batched)
MAX_URLS_SECTOR = 4
CONCALL_QUARTERS = 4             # transcripts to ingest
PREFLIGHT_TIMEOUT = 6            # seconds, requests pre-flight

# Freshness (days) before shared layers are re-read
MACRO_FRESH_DAYS = 7
SECTOR_FRESH_DAYS = 30

# Domain tables (playbook §0)
TIER1_DOMAINS = [
    "bseindia.com", "screener.in", "researchbytes.com",
    "icra.in", "crisilratings.com", "careratings.com", "indiaratings.co.in",
    "siam.in", "fada.in", "acma.in", "rbi.org.in", "mospi.gov.in",
    "pib.gov.in", "ppac.gov.in", "imf.org", "worldbank.org",
]
BLOCKED_DOMAINS = [
    "nseindia.com",              # bot-hostile; BSE mirrors filings
    "facebook.com", "x.com", "twitter.com", "linkedin.com", "youtube.com",
]

# --- Output --------------------------------------------------------------
REPORTS_DIR = os.environ.get("REPORTS_DIR", "data/reports")
PACKS_DIR = os.environ.get("PACKS_DIR", "data/sector_packs")
NODES_DIR = os.environ.get("NODES_DIR", "nodes")
