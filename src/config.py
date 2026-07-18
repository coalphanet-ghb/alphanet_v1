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

# --- NVIDIA trial endpoint (GLM-5.2) --------------------------------------
# OpenAI-style chat endpoint, no server-side URL fetching — with
# `--model GLM` the synthesis/verification calls route here while S2
# document reads stay on Gemini url_context.
# (MiniMax-M3 was tried first and replaced: its long reasoning generations
# kept hitting the trial gateway's 504 timeout; GLM-5.2 is faster.)
NVIDIA_API_KEY = os.environ.get("NVIDIA_API_KEY", "")
NVIDIA_API_URL = os.environ.get(
    "NVIDIA_API_URL", "https://integrate.api.nvidia.com/v1/chat/completions")
NVIDIA_MODEL = os.environ.get("NVIDIA_MODEL", "z-ai/glm-5.2")
NVIDIA_RPM = int(os.environ.get("NVIDIA_RPM", "6"))    # trial-tier pacing (bursty limiter)


def nvidia_configured() -> bool:
    return not _is_placeholder(NVIDIA_API_KEY)


# --- Fireworks AI (PAID — MiniMax-M3 serverless) ---------------------------
# `--model M3` routes synthesis/verification here. Paid tier: no trial
# queue, no gateway 504s, up to 64K output tokens.
FIREWORKS_API_KEY = os.environ.get("FIREWORKS_API_KEY", "")
FIREWORKS_API_URL = os.environ.get(
    "FIREWORKS_API_URL", "https://api.fireworks.ai/inference/v1/chat/completions")
FIREWORKS_MODEL = os.environ.get("FIREWORKS_MODEL", "accounts/fireworks/models/minimax-m3")
FIREWORKS_RPM = int(os.environ.get("FIREWORKS_RPM", "30"))
# USD per 1M tokens (Phase 5 cost telemetry; override in .env when
# Fireworks reprices — these are the serverless MiniMax-M3 list prices)
FIREWORKS_COST_IN_PER_M = float(os.environ.get("FIREWORKS_COST_IN_PER_M", "0.55"))
FIREWORKS_COST_OUT_PER_M = float(os.environ.get("FIREWORKS_COST_OUT_PER_M", "2.19"))


def fireworks_configured() -> bool:
    return not (_is_placeholder(FIREWORKS_API_KEY) or
                FIREWORKS_API_KEY == "fireworks_paid_key")


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
        "peer_screener_slugs": ["BHARATFORG", "UNOMINDA", "SCHAEFFLER", "ENDURANCE",
                                "MOTHERSON", "SANSERA", "HAPPYFORGE", "RKFORGE"],
        # PE-history comes from ticker-derived URL templates in s1 (with
        # identity validation); add "valuation_history_url" here ONLY as a
        # rare per-company escape hatch when the templates miss.
    },
    {
        "label": "M&M",
        "ticker": "M&M",
        "name": "Mahindra & Mahindra",
        "pack_id": "auto_oem",
        "segments": ["SUV", "tractor", "commercial vehicle"],
        "aliases": ["Mahindra", "M&M"],
        "screener_slug": "M%26M",
        # Tata Motors demerged (2025): TMPV = passenger vehicles (the SUV
        # comparator), TMCV = the CV entity; old TATAMOTORS slug 404s
        "peer_screener_slugs": ["TMPV", "TMCV", "MARUTI", "ESCORTS", "HYUNDAI"],
    },
]

# --- Read budget (playbook §0; Phase 3.4 raised on paid tier) -----------
# Every read = 1 extraction call (local-fetch inline or url_context).
# P1 never cut; P3 cut first.
MAX_READ_CALLS = int(os.environ.get("MAX_READ_CALLS", "40"))
MAX_NEWS_URLS = int(os.environ.get("MAX_NEWS_URLS", "10"))   # was 6
MAX_RESULTS_DOC_HUNT = 5         # ddgs results for document-hunt queries
MAX_RESULTS_DATA = 3             # ddgs results for data/news queries
MAX_URLS_MACRO = 4               # macro theme reads (batched)
MAX_URLS_SECTOR = 4
CONCALL_QUARTERS = 4             # transcripts to ingest
PREFLIGHT_TIMEOUT = 6            # seconds, requests pre-flight

# Freshness (days) before shared layers are re-read
MACRO_FRESH_DAYS = 7
SECTOR_FRESH_DAYS = 30

# Domain tables (playbook §0; extended per run post-mortems)
TIER1_DOMAINS = [
    "bseindia.com", "screener.in", "researchbytes.com",
    "icra.in", "crisilratings.com", "careratings.com", "indiaratings.co.in",
    "siam.in", "fada.in", "acma.in", "rbi.org.in", "mospi.gov.in",
    "pib.gov.in", "ppac.gov.in", "imf.org", "worldbank.org",
    "alphaspread.com", "trendlyne.com", "tijorifinance.com", "concall.in",
]
BLOCKED_DOMAINS = [
    "nseindia.com",              # bot-hostile; BSE mirrors filings
    "facebook.com", "x.com", "twitter.com", "linkedin.com", "youtube.com",
    "instagram.com",             # a reel once landed in an M&M news batch
    "morningstar.com", "marketscreener.com", "gurufocus.com",  # transcript paywalls
    "careratingtracker.com",     # agency index page, not rationales
]
BLOCKED_URL_PATTERNS = [
    "moneycontrol.com/financials",   # JS tables, unreadable
]
# legal databases: allowed ONLY for the litigation query (old cases pollute
# news evidence otherwise)
LEGAL_DOMAINS = ["indiankanoon.org", "casemine.com"]

# learned domain scores (read_log outcomes accumulate here; >=2 failures
# demotes the domain in s1 reranking)
DOMAIN_SCORES_PATH = os.environ.get("DOMAIN_SCORES_PATH", "data/domain_scores.json")

# reuse quality gates: a P1 document reused with fewer stored passages than
# this gets re-read instead (thin early extractions self-heal)
REUSE_MIN_PASSAGES = {"concall": 5, "annual_report": 10, "investor_presentation": 4}

# --- Output --------------------------------------------------------------
REPORTS_DIR = os.environ.get("REPORTS_DIR", "data/reports")
PACKS_DIR = os.environ.get("PACKS_DIR", "data/sector_packs")
NODES_DIR = os.environ.get("NODES_DIR", "nodes")
