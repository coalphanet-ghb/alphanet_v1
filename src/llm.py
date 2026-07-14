"""
Gemini wrapper. One active model per run — lite by default, the main model
when `main.py high` is used — and NO fallback and NO automatic retries:
the first error of any kind aborts the run cleanly, and retrying is a
manual decision (cheap, because already-ingested URLs are reused).

Two call types:
    read_urls()  active model + url_context  -> real passages from known URLs
    synthesize() active model, no tools      -> reasoning / section writing

Calls are self-throttled to the active model's free-tier RPM so the script
doesn't trip its own rate limit (3.5-flash free tier is only 5 RPM / 20 RPD;
3.1-flash-lite is 15 RPM / 500 RPD). Keep billing DISABLED on the GCP project.
"""

import time
from typing import List

from src.config import (
    GEMINI_API_KEY, GEMINI_LITE_MODEL, GEMINI_LITE_RPM,
    gemini_configured,
)


class LLMError(RuntimeError):
    pass


class ModelOverloadedError(LLMError):
    """503 capacity / 429 rate-quota — nothing is broken; retry later."""


class CallDeadlineError(LLMError):
    """Google's server gave up on ONE request ("Deadline expired") —
    usually url_context chewing on a slow or huge page. Also arrives with a
    503 status, but it is a property of that URL, not of the model or your
    quota, so ingestion skips the URL instead of aborting the run."""


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


def set_active_model(model: str, rpm: int) -> None:
    """Called once by main.py before the run starts."""
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
                "Create a key in Google AI Studio on a project with billing "
                "DISABLED, copy .env.example to .env, and fill it in."
            )
        from google import genai
        _client = genai.Client(api_key=GEMINI_API_KEY)
    return _client


def _generate(contents, config):
    """One call on the active model. Self-throttles to the model's RPM.
    Any failure raises immediately — no retry, no fallback; the run should
    end and be retried manually."""
    global _last_call_at
    client = _get_client()

    gap = _min_call_interval - (time.monotonic() - _last_call_at)
    if gap > 0:
        time.sleep(gap)
    _last_call_at = time.monotonic()

    try:
        return client.models.generate_content(
            model=_active_model, contents=contents, config=config
        )
    except Exception as e:
        if _is_deadline(e):     # check before overload — it also carries a 503
            raise CallDeadlineError(
                f"{_active_model} request deadline expired (slow/huge page?): {e}"
            ) from e
        if _is_overload(e):
            raise ModelOverloadedError(
                f"{_active_model} is overloaded or out of quota: {e}"
            ) from e
        raise LLMError(f"Gemini call to {_active_model} failed: {e}") from e


def read_urls(urls: List[str], instruction: str) -> str:
    """
    Read specific, already-known URLs via the url_context tool and return the
    extraction as text. This is the step that produces genuine source
    passages — the only legitimate feedstock for evidence rows.
    """
    from google.genai import types

    if not urls:
        return ""
    config = types.GenerateContentConfig(
        tools=[types.Tool(url_context=types.UrlContext())],
        temperature=0.1,
    )
    prompt = instruction + "\n\nURLs to read:\n" + "\n".join(urls)
    response = _generate(prompt, config)
    return response.text or ""


def synthesize(messages, temperature: float = 0.3, max_tokens: int = 1800) -> str:
    """
    Plain reasoning/writing call, no tools. Accepts
    [{"role": ..., "content": ...}] message lists, so analysis nodes need
    no signature changes.
    """
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
