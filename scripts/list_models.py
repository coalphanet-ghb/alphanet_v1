"""
Lists every model available to YOUR API key (names change under Google's
feet — never trust a hardcoded name), and optionally smoke-tests candidates
with a tiny generateContent call so you know what actually works before a
real run.

Usage:
    python scripts/list_models.py            # list only (free, no generation)
    python scripts/list_models.py --test     # also test-call flash models (a few tiny calls)
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.config import GEMINI_API_KEY, gemini_configured  # noqa: E402


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--test", action="store_true",
                        help="also make one tiny test call per flash-family model")
    args = parser.parse_args()

    if not gemini_configured():
        sys.exit("GEMINI_API_KEY is not set — fill in .env first.")

    from google import genai
    client = genai.Client(api_key=GEMINI_API_KEY)

    print("Models supporting generateContent, visible to this key:\n")
    candidates = []
    for m in client.models.list():
        actions = getattr(m, "supported_actions", None) or []
        if "generateContent" not in actions:
            continue
        name = m.name.removeprefix("models/")
        print(f"  {name:45s} {getattr(m, 'display_name', '')}")
        skip = ("tts", "image", "banana", "robotics", "computer-use", "omni",
                "lyria", "antigravity", "deep-research", "gemma")
        if ("flash" in name or "lite" in name) and not any(s in name for s in skip):
            candidates.append(name)

    if not args.test:
        print("\nRun with --test to smoke-test the flash-family models above.")
        return

    print("\nSmoke tests (one tiny call each):")
    for name in candidates:
        try:
            r = client.models.generate_content(model=name, contents="Say OK.")
            text = (r.text or "").strip().replace("\n", " ")[:40]
            print(f"  WORKS   {name:45s} -> {text}")
        except Exception as e:
            msg = str(e).split("\n")[0][:100]
            print(f"  FAILS   {name:45s} -> {msg}")


if __name__ == "__main__":
    main()
