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

# --- Phase 5 cost telemetry: token usage accumulated per process ------------
# {provider: {"in": n, "out": n}} — read by main.py at finish_run.
usage_totals: dict = {"gemini": {"in": 0, "out": 0},
                      "nvidia": {"in": 0, "out": 0},
                      "fireworks": {"in": 0, "out": 0}}
_usage_lock = threading.Lock()

# --- Round 1 per-node telemetry ---------------------------------------------
# Node attribution is THREAD-LOCAL: the synth wave (B/E/D1/D2/D3) runs its
# nodes on parallel threads and every LLM call is synchronous inside its
# node's thread — a plain global would misattribute the wave's calls.
_node_local = threading.local()
node_usage: dict = {}       # {node_id: {calls,in,out,cached_in,latency_s,cost_usd,spirals,truncations}}
telemetry_extra: dict = {}  # free-form per-run stats (verifier trends, ...)


def set_current_node(node_id: str) -> None:
    _node_local.node = node_id


def current_node() -> str:
    return getattr(_node_local, "node", "(unattributed)")


def _node_rec(node: str) -> dict:
    return node_usage.setdefault(node, {
        "calls": 0, "in": 0, "out": 0, "cached_in": 0, "latency_s": 0.0,
        "cost_usd": 0.0, "spirals": 0, "truncations": 0})


def note_wasted_output(kind: str = "spiral") -> None:
    """Count a burned output budget against the current node: 'spiral'
    (reasoning spiral in an envelope/verifier call) or 'truncation' (s2
    extraction overflow). Spiral-rate-per-node is the Round-5
    hypothesis-test statistic."""
    key = "spirals" if kind == "spiral" else "truncations"
    with _usage_lock:
        _node_rec(current_node())[key] += 1


def _add_usage(provider: str, tokens_in: int, tokens_out: int,
               cached_in: int = 0, latency_s: float = 0.0) -> None:
    from src.config import FIREWORKS_COST_IN_PER_M, FIREWORKS_COST_OUT_PER_M
    with _usage_lock:
        usage_totals[provider]["in"] += int(tokens_in or 0)
        usage_totals[provider]["out"] += int(tokens_out or 0)
        rec = _node_rec(current_node())
        rec["calls"] += 1
        rec["in"] += int(tokens_in or 0)
        rec["out"] += int(tokens_out or 0)
        rec["cached_in"] += int(cached_in or 0)
        rec["latency_s"] += latency_s
        if provider == "fireworks":     # only paid tokens are priced
            rec["cost_usd"] += (int(tokens_in or 0) * FIREWORKS_COST_IN_PER_M +
                                int(tokens_out or 0) * FIREWORKS_COST_OUT_PER_M) / 1e6


def dump_telemetry(run_id: str = "") -> None:
    """End-of-run per-node cost table + sidecar file. The runs table
    stays scalar-only (DB_SCHEMA.md); the per-node breakdown lives in
    data/telemetry/{run_id}.json."""
    with _usage_lock:
        snap = {n: dict(r) for n, r in node_usage.items()}
    if not snap:
        return
    print("\n--- per-node telemetry (Round 1) ---")
    print(f"{'node':<26}{'calls':>6}{'in_tok':>12}{'out_tok':>10}"
          f"{'cached':>12}{'sec':>7}{'spir':>5}{'trunc':>6}{'cost$':>8}")
    for n, r in sorted(snap.items(), key=lambda kv: -kv[1]["cost_usd"]):
        print(f"{n:<26}{r['calls']:>6}{r['in']:>12,}{r['out']:>10,}"
              f"{r['cached_in']:>12,}{r['latency_s']:>7.0f}{r['spirals']:>5}"
              f"{r['truncations']:>6}{r['cost_usd']:>8.3f}")
    print(f"{'TOTAL':<26}{sum(r['calls'] for r in snap.values()):>6}"
          f"{sum(r['in'] for r in snap.values()):>12,}"
          f"{sum(r['out'] for r in snap.values()):>10,}"
          f"{sum(r['cached_in'] for r in snap.values()):>12,}"
          f"{sum(r['latency_s'] for r in snap.values()):>7.0f}"
          f"{sum(r['spirals'] for r in snap.values()):>5}"
          f"{sum(r['truncations'] for r in snap.values()):>6}"
          f"{sum(r['cost_usd'] for r in snap.values()):>8.3f}")
    if run_id:
        import os
        os.makedirs("data/telemetry", exist_ok=True)
        path = os.path.join("data/telemetry", f"{run_id}.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"run_id": run_id, "nodes": snap,
                       "extra": telemetry_extra}, f, indent=1, default=str)
        print(f"telemetry sidecar: {path}")


def run_cost_usd() -> tuple[int, int, float]:
    """(total_in, total_out, est_cost). Only paid Fireworks tokens are
    priced; Gemini/NVIDIA run on free tiers (cost 0 until that changes)."""
    from src.config import FIREWORKS_COST_IN_PER_M, FIREWORKS_COST_OUT_PER_M
    ti = sum(v["in"] for v in usage_totals.values())
    to = sum(v["out"] for v in usage_totals.values())
    fw = usage_totals["fireworks"]
    cost = (fw["in"] * FIREWORKS_COST_IN_PER_M +
            fw["out"] * FIREWORKS_COST_OUT_PER_M) / 1_000_000
    return ti, to, round(cost, 4)


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


def _post_with_retry(provider: str, payload: dict) -> tuple[int, str, float]:
    """Throttled, serialized POST with the documented 429 retry loop and
    the requests→curl transport fallback. Returns (status, body,
    latency_s of the final attempt)."""
    global calls_made
    cfg = _OPENAI_PROVIDERS[provider]

    with cfg["lock"]:       # serialize: one in-flight request per provider
        for attempt in range(4):
            gap = (60.0 / max(cfg["rpm"], 1) + 0.5) - (time.monotonic() - cfg["last_call"])
            if gap > 0:
                time.sleep(gap)
            cfg["last_call"] = time.monotonic()
            calls_made += 1
            t0 = time.monotonic()

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
            latency = time.monotonic() - t0

            if status == 429 and attempt < 3:
                print(f"  [llm] 429 rate-limited — waiting {retry_after:.0f}s "
                      f"(attempt {attempt + 1}/4)")
                time.sleep(retry_after)
                continue
            break
    return status, text, latency


def _openai_generate(provider: str, system: str, user: str, temperature: float,
                     max_tokens: int, reasoning_effort: str = "") -> str:
    """One OpenAI-style chat call. Same policy as Gemini: throttled,
    serialized, no model fallback — first error aborts. HTTP 429 is the
    ONE retryable case (deterministic rate limiting, not an outage).
    reasoning_effort (Round 2.3, probe-verified): "" = provider default;
    "none" disables M3 reasoning; "low"/"medium"/"high" accepted."""
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
    if reasoning_effort:
        payload["reasoning_effort"] = reasoning_effort
    status, text, latency = _post_with_retry(provider, payload)

    if status in (429, 503):
        raise ModelOverloadedError(
            f"{cfg['model']} is rate-limited/overloaded (HTTP {status}): {text[:300]}")
    if status != 200:
        raise LLMError(f"{provider} API error HTTP {status}: {text[:300]}")
    try:
        data = json.loads(text)
        choice = data["choices"][0]
        # Reasoning models can exhaust max_tokens INSIDE reasoning_content
        # and omit "content" entirely — that is a truncation, and must not
        # crash here as a KeyError ("unexpected shape").
        content = (choice.get("message") or {}).get("content") or ""
    except (KeyError, IndexError, ValueError) as e:
        raise LLMError(f"Unexpected {provider} response shape: {text[:300]}") from e
    u = data.get("usage") or {}
    _add_usage(provider, u.get("prompt_tokens", 0), u.get("completion_tokens", 0),
               cached_in=(u.get("prompt_tokens_details") or {}).get("cached_tokens", 0),
               latency_s=latency)
    # Reasoning models spend hidden thinking tokens INSIDE max_tokens —
    # a truncated envelope must fail loudly as truncation, not as a
    # mysterious JSON parse error downstream.
    if choice.get("finish_reason") == "length" or not content:
        usage = data.get("usage", {})
        reasoning_len = len((choice.get("message") or {})
                            .get("reasoning_content") or "")
        raise LLMError(
            f"{cfg['model']} output TRUNCATED at max_tokens="
            f"{payload['max_tokens']} (finish_reason="
            f"{choice.get('finish_reason')}, completion used "
            f"{usage.get('completion_tokens')} tokens incl. hidden "
            f"reasoning; reasoning_content {reasoning_len} chars, visible "
            f"content truncated or absent) — raise the call's max_tokens.")
    return content


def raw_chat(messages: list, max_tokens: int = 2048, temperature: float = 0.2,
             extra_payload: dict | None = None,
             provider: str = "fireworks") -> dict:
    """Round-1 probes + Round-4 conversation extraction: one chat call
    with a caller-built messages list (multi-turn allowed); returns the
    FULL response JSON (usage details incl. prompt_tokens_details
    preserved — the caching probe reads them). Same transport hardening,
    throttle and serialization as every other call; usage is recorded
    normally against the current node."""
    cfg = _OPENAI_PROVIDERS[provider]
    if not cfg["configured"]():
        raise LLMError(f"{provider.upper()}_API_KEY is not set in .env.")
    payload = {"model": cfg["model"], "messages": messages,
               "max_tokens": min(max_tokens, cfg["max_out"]),
               "temperature": temperature, "top_p": 0.95, "stream": False}
    if extra_payload:
        payload.update(extra_payload)
    status, text, latency = _post_with_retry(provider, payload)
    if status in (429, 503):
        raise ModelOverloadedError(
            f"{cfg['model']} is rate-limited/overloaded (HTTP {status}): {text[:300]}")
    if status != 200:
        raise LLMError(f"{provider} API error HTTP {status}: {text[:300]}")
    data = json.loads(text)
    u = data.get("usage") or {}
    _add_usage(provider, u.get("prompt_tokens", 0), u.get("completion_tokens", 0),
               cached_in=(u.get("prompt_tokens_details") or {}).get("cached_tokens", 0),
               latency_s=latency)
    return data


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
        t0 = time.monotonic()
        response = client.models.generate_content(
            model=_active_model, contents=contents, config=config
        )
        um = getattr(response, "usage_metadata", None)
        if um is not None:
            _add_usage("gemini",
                       getattr(um, "prompt_token_count", 0) or 0,
                       (getattr(um, "candidates_token_count", 0) or 0) +
                       (getattr(um, "thoughts_token_count", 0) or 0),
                       latency_s=time.monotonic() - t0)
        return response
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


def synthesize(messages, temperature: float = 0.3, max_tokens: int = 4096,
               reasoning_effort: str = "") -> str:
    """Plain text call, no tools."""
    system_parts = [m["content"] for m in messages if m["role"] == "system"]
    user_parts = [m["content"] for m in messages if m["role"] != "system"]

    if _synth_provider in _OPENAI_PROVIDERS:
        text = _openai_generate(_synth_provider, "\n\n".join(system_parts),
                                "\n\n".join(user_parts), temperature, max_tokens,
                                reasoning_effort=reasoning_effort)
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
                  max_tokens: int = 16384, reasoning_effort: str = "") -> dict:
    """Structured call with JSON response mime type. Parse failure raises
    LLMError (per node contract: invalid JSON = failed node run)."""
    if _synth_provider in _OPENAI_PROVIDERS:
        # No response_mime_type on these endpoints — instruct + lenient parse.
        text = _openai_generate(
            _synth_provider,
            system + "\n\nCRITICAL: output ONLY the JSON object. No prose, "
                     "no markdown fences, no reasoning preamble.",
            user, temperature, max_tokens, reasoning_effort=reasoning_effort)
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
