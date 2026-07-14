"""
Central configuration for the AlphaNet POC.

Everything that would change between local dev, Antigravity, and a future
Cloud Run deployment lives here, read from environment variables so the
same code runs unmodified in all three places.
"""

import os
from dotenv import load_dotenv

# Loads variables from a local .env file if present. On Cloud Run later,
# these will just come from real environment variables / Secret Manager,
# and load_dotenv() is a harmless no-op there.
load_dotenv()

# --- Gemini -----------------------------------------------------------
# Discovery uses NO LLM (ddgs — see src/ingestion/queries.py). Gemini is
# used only for reading known URLs (url_context) and for synthesis.
#
# Two models, no fallback (a failed run is retried manually; reruns are
# cheap because ingested URLs are reused):
#   lite (default)      — gemini-3.1-flash-lite: 15 RPM / 500 RPD free tier
#   main (`main.py high`) — gemini-3.5-flash:      5 RPM /  20 RPD free tier (!)
# The RPM numbers drive self-throttling in src/llm.py so the script doesn't
# trip its own rate limit. Free-tier limits move around — check the AI
# Studio quota panel, and re-verify model names with scripts/list_models.py.
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
GEMINI_LITE_MODEL = os.environ.get("GEMINI_LITE_MODEL", "gemini-3.1-flash-lite")
GEMINI_LITE_RPM = int(os.environ.get("GEMINI_LITE_RPM", "15"))
GEMINI_MAIN_MODEL = os.environ.get("GEMINI_MAIN_MODEL", "gemini-3.5-flash")
GEMINI_MAIN_RPM = int(os.environ.get("GEMINI_MAIN_RPM", "5"))

# --- Supabase ---------------------------------------------------------
# service_role key: backend-only, bypasses RLS (RLS is enabled and fully
# closed on every table).
SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_SERVICE_ROLE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")

_PLACEHOLDER_MARKERS = ("your_", "your-project-ref")


def _is_placeholder(value: str) -> bool:
    return (not value) or any(m in value for m in _PLACEHOLDER_MARKERS)


def gemini_configured() -> bool:
    return not _is_placeholder(GEMINI_API_KEY)


def supabase_configured() -> bool:
    return not (_is_placeholder(SUPABASE_URL) or _is_placeholder(SUPABASE_SERVICE_ROLE_KEY))


# --- Pilot companies (main.py shows these as a pick menu) ---------------
# `name` must match the entity name in data/seed_entities.json so the run
# attaches to the seeded entity instead of creating a duplicate.
COMPANIES = [
    {"label": "SONA", "ticker": "SONACOMS",
     "name": "Sona BLW Precision Forgings Limited (Sona Comstar)"},
    {"label": "M&M", "ticker": "M&M",
     "name": "Mahindra & Mahindra"},
]

# Ingestion knobs.
# Every URL read is one Gemini url_context call, so the per-layer URL caps
# are the main quota lever: a full fresh run = MACRO + SECTOR + COMPANY
# reads + 6 synthesis calls (2+2+4+6 = 14 calls with the defaults below —
# within even the main model's 20 RPD, barely; lite's 500 RPD has plenty
# of headroom if you want to raise these).
MAX_RESULTS_PER_QUERY = 3        # ddgs results fetched per search query
MAX_URLS_MACRO = 2               # URLs actually read per layer
MAX_URLS_SECTOR = 2
MAX_URLS_COMPANY = 4
MAX_CHUNKS_PER_RUN = 60          # hard cap so we don't blow up prompt sizes
CHUNK_SIZE_CHARS = 1200          # naive fixed-size chunking for this POC

# Output
REPORTS_DIR = os.environ.get("REPORTS_DIR", "data/reports")
