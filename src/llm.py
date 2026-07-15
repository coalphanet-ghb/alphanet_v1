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
import threading
import time
from typing import List, Optional

import requests as _requests

from src.config import (
    GEMINI_API_KEY, GEMINI_LITE_MODEL, GEMINI_LITE_RPM, gemini_configured,
    NVIDIA_API_KEY, NVIDIA_API_URL, NVIDIA_MODEL, NVIDIA_RPM,
    nvidia_configured,
    FIREWORKS_API_KEY, FIREWORKS_API_URL, FIREWORKS_MODEL, FIREWORKS_RPM,
    fireworks_configured,
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


# Synthesis provider: "gemini" (default), "nvidia" (GLM-5.2 trial,
# --model GLM) or "fireworks" (MiniMax-M3 PAID, --model M3). Document
# reads (url_context) ALWAYS stay on Gemini — the OpenAI-style endpoints
# have no server-side URL fetching.
# Each OpenAI-style provider: url, key, model, rpm pacing, output cap,
# its own serialization lock + throttle clock + sticky curl-fallback flag.
_OPENAI_PROVIDERS = {
    "nvidia": {"url": NVIDIA_API_URL, "key": NVIDIA_API_KEY,
               "model": NVIDIA_MODEL, "rpm": NVIDIA_RPM, "max_out": 8192,
               "configured": nvidia_configured,
               "lock": threading.Lock(), "last_call": 0.0, "use_curl": False},
    "fireworks": {"url": FIREWORKS_API_URL, "key": FIREWORKS_API_KEY,
                  "model": FIREWORKS_MODEL, "rpm": FIREWORKS_RPM, "max_out": 64000,
                  "configured": fireworks_configured,
                  "lock": threading.Lock(), "last_call": 0.0, "use_curl": False},
}
_synth_provider = "gemini"


def set_synth_provider(provider: str) -> None:
    global _synth_provider
    if provider in _OPENAI_PROVIDERS and not _OPENAI_PROVIDERS[provider]["configured"]():
        raise LLMError(f"{provider.upper()}_API_KEY is not set in .env.")
    _synth_provider = provider


def get_active_model() -> str:
    if _synth_provider in _OPENAI_PROVIDERS:
        return f"{_OPENAI_PROVIDERS[_synth_provider]['model']} (reads: {_active_model})"
    return _active_model


# The graph runs synthesis nodes in parallel; provider calls must be
# serialized or racing threads bypass the RPM throttle and pile
# concurrent heavy requests onto the endpoint.
_gemini_lock = threading.Lock()


def _find_curl() -> str:
    """Prefer Git-for-Windows curl: on this network, both Python's TLS
    stack and System32's Schannel curl get connection-reset by the NVIDIA
    edge, while Git's curl handshakes fine. Override with NVIDIA_CURL."""
    import os as _os
    import shutil
    for cand in (_os.environ.get("NVIDIA_CURL"),
                 r"C:\Program Files\Git\mingw64\bin\curl.exe",
                 shutil.which("curl")):
        if cand and _os.path.exists(cand):
            return cand
    return "curl"


def _post_via_curl(cfg: dict, payload: dict) -> tuple[int, str]:
    """Transport fallback for TLS-fingerprint-hostile network paths.
    Payload goes via temp file to dodge command-length/quoting limits."""
    import subprocess, tempfile, os as _os
    body = json.dumps(payload)
    fd, path = tempfile.mkstemp(suffix=".json")
    try:
        with _os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(body)
        proc = subprocess.run(
            [_find_curl(), "-sS", "-m", "600",
             "-w", "\n%{http_code}",
             cfg["url"],
             "-H", f"Authorization: Bearer {cfg['key']}",
             "-H", "Content-Type: application/json",
             "-d", f"@{path}"],
            capture_output=True, text=True, encoding="utf-8", timeout=620)
    finally:
        _os.unlink(path)
    if proc.returncode != 0:
        raise LLMError(f"{cfg['model']} via curl failed: {proc.stderr[:300]}")
    out = proc.stdout.rstrip()
    body_text, _, code = out.rpartition("\n")
    return int(code or 0), body_text


def _openai_generate(provider: str, system: str, user: str, temperature: float,
                     max_tokens: int) -> str:
    """One OpenAI-style chat call. Same policy as Gemini: throttled,
    serialized, no model fallback — first error aborts. HTTP 429 is the
    ONE retryable case (deterministic rate limiting, not an outage).
    Transport falls back requests->curl for TLS-hostile network paths."""
    global calls_made
    cfg = _OPENAI_PROVIDERS[provider]

    payload = {
        "model": cfg["model"],
        "messages": ([{"role": "system", "content": system}] if system else []) +
                    [{"role": "user", "content": user}],
        "max_tokens": min(max_tokens, cfg["max_out"]),
        "temperature": temperature,
        "top_p": 0.95,
        "stream": False,
    }

    with cfg["lock"]:       # serialize: one in-flight request per provider
        for attempt in range(4):
            gap = (60.0 / max(cfg["rpm"], 1) + 0.5) - (time.monotonic() - cfg["last_call"])
            if gap > 0:
                time.sleep(gap)
            cfg["last_call"] = time.monotonic()
            calls_made += 1

            status, text, retry_after = 0, "", 25.0
            if not cfg["use_curl"]:
                try:
                    r = _requests.post(
                        cfg["url"], json=payload, timeout=(30, 600),
                        headers={"Authorization": f"Bearer {cfg['key']}",
                                 "Accept": "application/json"})
                    status, text = r.status_code, r.text
                    retry_after = float(r.headers.get("Retry-After") or 25)
                except _requests.exceptions.ConnectionError:
                    print(f"  [llm] {provider} endpoint reset Python TLS — "
                          f"switching to curl transport")
                    cfg["use_curl"] = True
                except _requests.RequestException as e:
                    raise LLMError(f"{provider} API request failed: {e}") from e
            if cfg["use_curl"]:
                status, text = _post_via_curl(cfg, payload)

            if status == 429 and attempt < 3:
                print(f"  [llm] 429 rate-limited — waiting {retry_after:.0f}s "
                      f"(attempt {attempt + 1}/4)")
                time.sleep(retry_after)
                continue
            break

    if status in (429, 503):
        raise ModelOverloadedError(
            f"{cfg['model']} is rate-limited/overloaded (HTTP {status}): {text[:300]}")
    if status != 200:
        raise LLMError(f"{provider} API error HTTP {status}: {text[:300]}")
    try:
        data = json.loads(text)
        choice = data["choices"][0]
        content = choice["message"]["content"] or ""
    except (KeyError, IndexError, ValueError) as e:
        raise LLMError(f"Unexpected {provider} response shape: {text[:300]}") from e
    # Reasoning models spend hidden thinking tokens INSIDE max_tokens —
    # a truncated envelope must fail loudly as truncation, not as a
    # mysterious JSON parse error downstream.
    if choice.get("finish_reason") == "length":
        usage = data.get("usage", {})
        raise LLMError(
            f"{cfg['model']} output TRUNCATED at max_tokens="
            f"{payload['max_tokens']} (completion used "
            f"{usage.get('completion_tokens')} incl. hidden reasoning) — "
            f"raise the call's max_tokens.")
    return content


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

    with _gemini_lock:      # parallel synth nodes must not race the throttle
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
    system_parts = [m["content"] for m in messages if m["role"] == "system"]
    user_parts = [m["content"] for m in messages if m["role"] != "system"]

    if _synth_provider in _OPENAI_PROVIDERS:
        text = _openai_generate(_synth_provider, "\n\n".join(system_parts),
                                "\n\n".join(user_parts), temperature, max_tokens)
        if not text:
            raise LLMError(f"{_synth_provider} returned an empty response")
        return text

    from google.genai import types
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
    if _synth_provider in _OPENAI_PROVIDERS:
        # No response_mime_type on these endpoints — instruct + lenient parse.
        text = _openai_generate(
            _synth_provider,
            system + "\n\nCRITICAL: output ONLY the JSON object. No prose, "
                     "no markdown fences, no reasoning preamble.",
            user, temperature, max_tokens)
        parsed = parse_json_lenient(text)
        if parsed is None:
            raise LLMError(f"{get_active_model()} returned an unparseable envelope. "
                           f"First 300 chars: {text[:300]}")
        return parsed

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
    candidate = t[start:end + 1]
    try:
        return json.loads(candidate)
    except json.JSONDecodeError:
        try:
            # strict=False tolerates literal newlines/tabs inside strings —
            # a common model slip that shouldn't fail a whole node.
            return json.loads(candidate, strict=False)
        except json.JSONDecodeError:
            return None
