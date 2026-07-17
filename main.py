"""
Entrypoint for AlphaNet report generation (S0-S9 pipeline).

Usage:
    python main.py                # lite model (default), asks which company
    python main.py high           # main model (5 RPM / 20 RPD — synthesis-only reruns)
    python main.py --dry-run      # zero network/LLM/DB — graph sanity check
    python main.py --ticker SONACOMS   # skip the menu

Model policy: no fallback, no automatic retries — first error aborts
cleanly; rerunning is cheap (ingested URLs are reused with zero LLM calls).
"""

import argparse

from src.pipeline.graph import build_graph
from src.config import (
    COMPANIES,
    GEMINI_LITE_MODEL, GEMINI_LITE_RPM, GEMINI_MAIN_MODEL, GEMINI_MAIN_RPM,
    gemini_configured, supabase_configured,
)
from src.llm import set_active_model, get_active_model


def pick_company(ticker_arg: str | None) -> dict:
    if ticker_arg:
        for c in COMPANIES:
            if c["ticker"].lower() == ticker_arg.lower():
                return c
        raise SystemExit(f"Unknown ticker '{ticker_arg}' — add it to config.COMPANIES")
    print("Which stock do you want to run the analysis for?")
    for i, c in enumerate(COMPANIES, start=1):
        print(f"  {i}. {c['label']}  — {c['name']} ({c['ticker']})")
    while True:
        choice = input(f"Select [1-{len(COMPANIES)}]: ").strip()
        if choice.isdigit() and 1 <= int(choice) <= len(COMPANIES):
            return COMPANIES[int(choice) - 1]
        print("  Not a valid choice, try again.")


def main():
    parser = argparse.ArgumentParser(description="AlphaNet report generator")
    parser.add_argument("mode", nargs="?", default="lite", choices=["lite", "high"])
    parser.add_argument("--model", default="gemini", choices=["gemini", "M3", "GLM"],
                        help="M3 = MiniMax-M3 via Fireworks (PAID) · GLM = GLM-5.2 "
                             "via NVIDIA trial. Both route synthesis+verification "
                             "only; document reads stay on Gemini")
    parser.add_argument("--ticker", default=None)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--reingest", action="store_true",
                        help="ignore stored extractions and re-read every "
                             "company document (use after extraction-prompt "
                             "or model upgrades; costs a full read budget)")
    args = parser.parse_args()

    if args.mode == "high":
        set_active_model(GEMINI_MAIN_MODEL, GEMINI_MAIN_RPM)
    else:
        set_active_model(GEMINI_LITE_MODEL, GEMINI_LITE_RPM)

    if args.model != "gemini" and not args.dry_run:
        from src.llm import set_synth_provider
        provider = {"M3": "fireworks", "GLM": "nvidia"}[args.model]
        set_synth_provider(provider)
        print(f"Synthesis/verification: {args.model} via {provider} — "
              f"document reads stay on Gemini.")

    if not args.dry_run and not gemini_configured():
        parser.exit(1, "GEMINI_API_KEY is not set (needed for document reads "
                       "even with --model GLM). Fill .env or use --dry-run.\n")

    company = pick_company(args.ticker)
    persist = not args.dry_run and supabase_configured()

    run_id = ""
    if persist:
        from src import db
        entity_id = db.get_or_create_entity(company["name"], "company",
                                            metadata={"ticker": company["ticker"]})
        run_id = db.start_run("company", entity_id)
        print(f"Run {run_id} started for entity {entity_id}")
    elif not args.dry_run:
        print("NOTE: Supabase is not configured — running without persistence.\n")

    mode = " (DRY RUN)" if args.dry_run else f" [model: {get_active_model()}]"
    print(f"\nAlphaNet report generation: {company['name']} ({company['ticker']}){mode}\n")

    state = {
        "dry_run": args.dry_run,
        "persist": persist,
        "reingest": args.reingest,
        "run_id": run_id,
        "profile": dict(company),
        "pack": {},
        "peer_entities": [],
    }
    if args.reingest:
        print("REINGEST: stored extractions ignored; every document re-read.\n")

    def _mark_failed(reason: str):
        # Must NEVER raise: if the network is down, the Supabase write fails
        # too and would mask the real error with its own traceback.
        if persist:
            try:
                from src import db
                db.finish_run(run_id, "failed", model_used=get_active_model(),
                              error_message=reason[:2000])
            except Exception as e:
                print(f"  [warn] could not mark run failed in DB "
                      f"(network down?): {e}")

    from src.llm import ModelOverloadedError, LLMError, calls_made
    app = build_graph()
    try:
        result = app.invoke(state)
    except ModelOverloadedError as e:
        _mark_failed(str(e))
        parser.exit(1, f"\nStopped: {get_active_model()} is overloaded / out of quota.\n({e})\n"
                       f"No automatic retry — run again in a while. Ingested pages are reused.\n")
    except LLMError as e:
        _mark_failed(str(e))
        parser.exit(1, f"\nStopped on the first LLM error (no retry, by design): {e}\n"
                       f"Rerunning is safe — ingested pages are reused.\n")
    except KeyboardInterrupt:
        _mark_failed("interrupted by user (Ctrl+C)")
        parser.exit(130, "\nInterrupted — run marked as failed. Rerunning is safe.\n")
    except Exception as e:
        _mark_failed(str(e))
        text = f"{type(e).__name__}: {e}"
        if any(t in text for t in ("getaddrinfo", "ConnectError", "ConnectTimeout",
                                   "NameResolutionError", "Connection aborted")):
            parser.exit(1, f"\nStopped: network connection lost mid-run.\n({text[:300]})\n"
                           f"Nothing is broken — check your connection and rerun. "
                           f"Everything already ingested is reused for free.\n")
        raise

    if persist:
        from src import db
        import src.llm as llm
        db.finish_run(run_id, "success", model_used=get_active_model())
        print(f"\nLLM calls this run: {llm.calls_made}")

    print(f"\nDone. Report: {result['report_path']}")


if __name__ == "__main__":
    main()
