"""
Daily market data (zero-LLM): closing price and market cap per ticker.

Deliberately independent of the research swarm. Price is a fact about a
ticker, not about whether an LLM has written a report — coupling the two
meant 149 of 150 index constituents had no price at all, at monthly
granularity, and only when a run happened to touch their sector.

Division of labour between the two sources (both probed 2026-07-26):
- **Yahoo chart API** is authoritative for the close AND the close DATE.
  Taking the date from the last daily bar — never `date.today()` — makes
  weekends and holidays self-detecting, so no NSE calendar is needed.
  1.5 KB/company. It exposes no market cap (the v7/quote and
  v10/quoteSummary endpoints that would are 401 Unauthorized).
- **Screener top card** is the only working market-cap source, and
  throws in a price we use as a staleness cross-check. 192 KB/company;
  on GCP ingress is free, so this is the honest choice over deriving
  mcap from cached shares-outstanding (which goes silently wrong after
  a QIP, buyback or split).

Both raise FetchError and never abort a caller: one unreachable company
must not cost the other 149.
"""

import datetime

import requests

from src.ingestion.fetcher import FetchError, _HEADERS

# Corporate-form suffixes carry no identity — they match every company.
# Kept separate from merely WEAK words: 'India' is generic, but it is a
# real part of a name and is better than validating nothing at all.
_SUFFIXES = frozenset({
    "ltd", "limited", "the", "and", "&", "inc", "plc", "corp",
    "corporation", "co", "company",
})


def company_tokens(name: str) -> list:
    """Every meaningful lowercase word of a company name, for identity
    validation (the caller matches with `any`).

    Corporate suffixes are dropped; nothing else is. Filtering to the
    "distinctive" long words was tried and is wrong in both directions:
    a >=4-char rule leaves '3M India Ltd.' with NO tokens at all — and
    an empty list silently disables the guard — while 'AIA Engineering
    Ltd.' reduces to ['engineering'], which its own screener page never
    says ("About AIA manufactures high-chrome grinding media…"), so a
    correct page gets rejected. False negatives cost real data every
    day; the guard's job is to catch a page for a DIFFERENT company,
    and any surviving name word does that."""
    words = [w.strip(".,()").lower() for w in str(name or "").split()]
    return [w for w in words if len(w) >= 2 and w not in _SUFFIXES]


def fetch_daily_close(ticker: str, tokens: list) -> tuple[float, str, str]:
    """(close, close_date_iso, long_name) from Yahoo's chart API.

    The date is the last daily bar's timestamp read in UTC — Indian
    market hours (03:45–10:00 UTC) never straddle a UTC date boundary,
    so this is the true trading date regardless of the host's timezone
    (the job runs on GCP in UTC, developers run it in IST).

    Identity is validated on two signals, because names alone are not
    dependable here: `meta.symbol` must be the symbol we asked for (an
    exact check, and the real defence against the wisesheets
    'M&M.NS -> Macy's Inc' class), and the name — longName, or
    shortName when longName is null — must contain a name token.
    Recently-listed constituents (SWIGGY, LENSKART, GROWW, NTPCGREEN…)
    return `longName: null` with a perfectly good shortName and valid
    closes; requiring longName alone rejected 13 of 150 real
    companies."""
    from urllib.parse import quote
    # The PATH needs percent-encoding ('M&MFIN' -> 'M%26MFIN'), but Yahoo
    # echoes meta.symbol DECODED — comparing the two encodings rejected
    # every ampersand ticker (GVT&D, M&MFIN).
    symbol = f"{ticker}.NS"
    url = (f"https://query1.finance.yahoo.com/v8/finance/chart/"
           f"{quote(ticker, safe='')}.NS")
    try:
        r = requests.get(url, params={"range": "5d", "interval": "1d"},
                         headers=_HEADERS, timeout=30)
    except requests.RequestException as e:
        raise FetchError(f"yahoo request failed: {e}") from e
    if r.status_code != 200:
        raise FetchError(f"yahoo chart HTTP {r.status_code}")
    try:
        res = r.json()["chart"]["result"][0]
        closes = res["indicators"]["quote"][0]["close"]
        stamps = res["timestamp"]
    except (KeyError, IndexError, TypeError, ValueError) as e:
        raise FetchError(f"yahoo chart shape: {e}") from e

    meta = res.get("meta") or {}
    got_symbol = str(meta.get("symbol") or "")
    if got_symbol and got_symbol.upper() != symbol.upper():
        raise FetchError(f"identity mismatch: asked '{symbol}', "
                         f"yahoo answered '{got_symbol}'")
    long_name = str(meta.get("longName") or meta.get("shortName") or "")
    if long_name and tokens and not any(t in long_name.lower() for t in tokens):
        raise FetchError(f"identity mismatch: yahoo resolved '{symbol}' "
                         f"to '{long_name}'")

    last = [(t, c) for t, c in zip(stamps, closes) if c is not None]
    if not last:
        raise FetchError("yahoo returned no non-null closes in 5d")
    stamp, close = last[-1]
    close_date = datetime.datetime.fromtimestamp(
        stamp, tz=datetime.timezone.utc).date().isoformat()
    return round(float(close), 2), close_date, long_name


def _top_card(url: str, tokens: list) -> dict:
    """Parse one screener page and return its top-card values."""
    from src.ingestion.screener_parser import parse_company_page
    from src.pipeline.s3_compute import parse_value

    try:
        parsed = parse_company_page(url)
    except Exception as e:
        raise FetchError(f"screener parse failed: {e}") from e

    about = (parsed.get("about") or "").lower()
    if about and tokens and not any(t in about for t in tokens):
        raise FetchError(f"identity mismatch: {url} does not mention "
                         f"this company")

    # top-card values are the ones the parser stamps with a period itself
    # (the periodic tables all carry a printed period instead)
    found = {}
    for c in parsed.get("candidates") or []:
        name = c.get("name")
        if name in ("market_cap", "price") and c.get("period_parsed") \
                and name not in found:
            v = parse_value(c.get("value_printed"), name)
            if v:
                found[name] = v[0]
    return found


def fetch_market_cap(screener_slug: str, tokens: list) -> tuple[float, float]:
    """(market_cap_cr, price) from the screener top card.

    Reuses the proven zero-LLM page parser rather than a second scraper,
    and `parse_value` rather than hand-rolled number cleaning ('₹ 44,707
    Cr.' -> 44707.0), so there is one code path for both. The company
    name must appear in the page's 'about' text before the numbers are
    trusted — the slug is deterministic, but a dead slug that redirects
    would otherwise ship another company's cap.

    Consolidated first, then STANDALONE: companies that report no
    consolidated accounts (PAGEIND, SBICARD, BDL, HONAUT…) still serve a
    /consolidated/ page, but an empty shell of one — market cap renders
    as a bare '₹ Cr.' with no number. Six of 150 constituents need the
    fallback."""
    base = f"https://www.screener.in/company/{screener_slug}"
    try:
        found = _top_card(f"{base}/consolidated/", tokens)
    except FetchError:
        found = {}      # a consolidated page that RAISES must still fall
                        # through — a thin shell page trips the parser's
                        # own sanity check before we ever see the card
    if "market_cap" not in found or "price" not in found:
        found = _top_card(f"{base}/", tokens)
    if "market_cap" not in found:
        raise FetchError("no market_cap on the screener top card "
                         "(consolidated or standalone)")
    if "price" not in found:
        raise FetchError("no price on the screener top card "
                         "(consolidated or standalone)")
    return found["market_cap"], found["price"]
