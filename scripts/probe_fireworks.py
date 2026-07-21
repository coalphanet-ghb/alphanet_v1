"""Round 1 probes (one-off; ~$0.05 total on Fireworks M3).

P1  Prefix caching: two calls sharing a large identical prefix — does
    usage report cached prompt tokens (prompt_tokens_details), i.e. is
    a repeated prefix recognized at all? Verdict sets Round 4's AR
    conversation bundle count (3 vs 5): fully re-billed prefixes argue
    for fewer, fatter bundles.
P2  Reasoning effort: does the serverless M3 endpoint accept a
    reasoning-effort / thinking-budget parameter? A working cap is a
    direct lever on spiral waste (Round 2.3).

Usage: python scripts/probe_fireworks.py
Verdicts go into NEXT_STEPS.md "Round 1 log".
"""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(errors="replace")   # cp1252 guard (HANDOFF3 §4)
    except Exception:
        pass

from src.llm import raw_chat, set_current_node, LLMError  # noqa: E402


def _usage(data: dict) -> dict:
    u = data.get("usage") or {}
    return {"prompt": u.get("prompt_tokens"),
            "completion": u.get("completion_tokens"),
            "prompt_tokens_details": u.get("prompt_tokens_details"),
            "usage_keys": sorted(u.keys())}


def probe_prefix_caching():
    print("=== P1: prefix caching ===")
    para = ("The company reported consolidated revenue growth with stable "
            "operating margins across its business segments, citing volume "
            "recovery, richer product mix and disciplined cost control "
            "through the financial year under review. ")
    prefix = "FILING EXCERPT (probe corpus):\n" + para * 500   # ~20K+ tokens
    questions = (
        "In one short sentence: what does the excerpt say about margins?",
        "In one short sentence: what does the excerpt say about volumes?",
    )
    for i, q in enumerate(questions):
        data = raw_chat(
            [{"role": "user", "content": prefix + "\n\nQUESTION: " + q}],
            max_tokens=2000, temperature=0.0)
        print(f"call {i + 1}: usage = {json.dumps(_usage(data))}")
    print("\nVerdict guide: call 2 reporting cached tokens > 0 in "
          "prompt_tokens_details => prefix caching ACTIVE (billing discount "
          "per Fireworks pricing page); absent/zero => assume full "
          "re-billing per query — Round 4 then favors 3 fat bundles over 5.")


def probe_reasoning_effort():
    print("\n=== P2: reasoning-effort param ===")
    q = [{"role": "user", "content":
          "What is 17 * 23? Reply with just the number."}]
    ctrl = raw_chat(q, max_tokens=4000, temperature=0.0)
    print(f"control              : usage = {json.dumps(_usage(ctrl))}")
    for name, extra in (
            ("reasoning_effort=low", {"reasoning_effort": "low"}),
            ("reasoning_effort=none", {"reasoning_effort": "none"}),
            ("max_reasoning_tokens", {"max_reasoning_tokens": 512})):
        try:
            data = raw_chat(q, max_tokens=4000, temperature=0.0,
                            extra_payload=extra)
            print(f"{name:<21}: ACCEPTED — usage = {json.dumps(_usage(data))}")
        except LLMError as e:
            print(f"{name:<21}: REJECTED — {str(e)[:200]}")
    print("\nVerdict guide: ACCEPTED with a visibly lower completion_tokens "
          "than control => a real reasoning cap exists (apply in Round 2.3). "
          "ACCEPTED with identical usage => param silently ignored — treat "
          "as unsupported.")


if __name__ == "__main__":
    set_current_node("probe")
    probe_prefix_caching()
    probe_reasoning_effort()
