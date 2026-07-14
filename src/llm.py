"""
Gemini wrapper. One active model per run (lite default, `main.py high`
for the main model). NO fallback, NO automatic retries: the first error
aborts the run; retry is manual (cheap — ingested URLs are reused).

Call types:
    read_urls()      url_context      -> extraction (JSON mode optional)
    synthesize()     no tools         -> plain text
    generate_json()  no tools, JSON   -> structured envelopes

Self-throttled to the active model's RPM (3.5-flash free tier is only
5 RPM / 20 RPD; 3.1-flash-lite is 15 RPM / 500 RPD). Keep billing
DISABLED on the GCP project.
"""

import json
import time
from typing import List, Optional

from src.config import (
    GEMINI_API_KEY, GEMINI_LITE_MODEL, GEMINI_LITE_RPM, gemini_configured,
)


class LLMError(RuntimeError):
    pass


class ModelOverloadedError(LLMError):
    """503 capacity / 429 rate-quota — nothing is broken; retry later."""


class CallDeadlineError(LLMError):
    """Google gave up on ONE request ("Deadline expired") — a property of
    that URL/payload, not the model. Ingestion skips and moves on."""


def _is_deadline(err: Exception) -> bool:
    text = str(err)
    return "Deadline expired" in text or "DEADLINE_EXCEEDED" in text


def _is_overload(err: Exception) -> bool:
    code = getattr(err, "code", None) or getattr(err, "status_code", None)
    if code in (429, 503):
        return True
    text = str(err)
    return "UNAVAILABLE" in text or "RESOURCE_EXHAUSTED" in text or "503" in text


_client = None
_active_model = GEMINI_LITE_MODEL
_min_call_interval = 60.0 / GEMINI_LITE_RPM + 0.5
_last_call_at = 0.0
calls_made = 0     # per-process call counter (observability)


def set_active_model(model: str, rpm: int) -> None:
    global _active_model, _min_call_interval
    _active_model = model
    _min_call_interval = 60.0 / max(rpm, 1) + 0.5


def get_active_model() -> str:
    return _active_model


def _get_client():
    global _client
    if _client is None:
        if not gemini_configured():
            raise LLMError(
                "GEMINI_API_KEY is not set (or is still the placeholder). "
                "Copy .env.example to .env and fill it in."
            )
        from google import genai
        _client = genai.Client(api_key=GEMINI_API_KEY)
    return _client


def _generate(contents, config):
    """One call, throttled. Any failure raises immediately (no retry, no
    fallback — run ends, rerun is manual)."""
    global _last_call_at, calls_made
    client = _get_client()

    gap = _min_call_interval - (time.monotonic() - _last_call_at)
    if gap > 0:
        time.sleep(gap)
    _last_call_at = time.monotonic()
    calls_made += 1

    try:
        return client.models.generate_content(
            model=_active_model, contents=contents, config=config
        )
    except Exception as e:
        if _is_deadline(e):
            raise CallDeadlineError(
                f"{_active_model} request deadline expired (slow/huge page?): {e}"
            ) from e
        if _is_overload(e):
            raise ModelOverloadedError(
                f"{_active_model} is overloaded or out of quota: {e}"
            ) from e
        raise LLMError(f"Gemini call to {_active_model} failed: {e}") from e


def read_urls(urls: List[str], instruction: str, json_mode: bool = False,
              max_tokens: int = 16384) -> str:
    """Read known URLs via url_context; returns the model's text."""
    from google.genai import types

    if not urls:
        return ""
    config = types.GenerateContentConfig(
        tools=[types.Tool(url_context=types.UrlContext())],
        temperature=0.1,
        max_output_tokens=max_tokens,
        # NOTE: response_mime_type is not combinable with tools on all
        # versions; extraction prompts demand JSON in-text instead.
    )
    prompt = instruction + "\n\nURLs to read:\n" + "\n".join(urls)
    response = _generate(prompt, config)
    return response.text or ""


def synthesize(messages, temperature: float = 0.3, max_tokens: int = 4096) -> str:
    """Plain text call, no tools."""
    from google.genai import types

    system_parts = [m["content"] for m in messages if m["role"] == "system"]
    user_parts = [m["content"] for m in messages if m["role"] != "system"]
    config = types.GenerateContentConfig(
        system_instruction="\n\n".join(system_parts) or None,
        temperature=temperature,
        max_output_tokens=max_tokens,
    )
    response = _generate("\n\n".join(user_parts), config)
    if not response.text:
        raise LLMError(f"Gemini returned an empty response: {response}")
    return response.text


def generate_json(system: str, user: str, temperature: float = 0.2,
                  max_tokens: int = 16384) -> dict:
    """Structured call with JSON response mime type. Parse failure raises
    LLMError (per node contract: invalid JSON = failed node run)."""
    from google.genai import types

    config = types.GenerateContentConfig(
        system_instruction=system or None,
        temperature=temperature,
        max_output_tokens=max_tokens,
        response_mime_type="application/json",
    )
    response = _generate(user, config)
    text = response.text or ""
    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        raise LLMError(f"Node returned invalid JSON envelope: {e}. "
                       f"First 300 chars: {text[:300]}") from e


def parse_json_lenient(text: str) -> Optional[dict]:
    """For extraction responses (tools + JSON-in-text): strip fences,
    find the outermost object. Returns None if unparseable."""
    t = text.strip()
    if t.startswith("```"):
        t = t.split("```", 2)[1] if t.count("```") >= 2 else t.strip("`")
        if t.startswith("json"):
            t = t[4:]
    start, end = t.find("{"), t.rfind("}")
    if start == -1 or end <= start:
        return None
    try:
        return json.loads(t[start:end + 1])
    except json.JSONDecodeError:
        return None
