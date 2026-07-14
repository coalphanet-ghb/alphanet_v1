"""
Entrypoint for the AlphaNet POC.

Usage:
    python main.py                # lite model (default), asks which company
    python main.py high           # main model (gemini-3.5-flash, 5 RPM / 20 RPD — tight)
    python main.py --dry-run      # no network, no LLM calls — sanity check only
    python main.py --ticker SONACOMS --company "Sona BLW ..."   # skip the menu

Model policy: no fallback, no automatic retries — the first error aborts
the run cleanly and retrying is manual. Reruns are cheap: already-ingested
URLs are reused without new LLM calls.
"""

import argparse

from src.workflow.graph import build_graph
from src.knowledge.stubs import MACRO_CONTEXT_STUB, INDUSTRY_CONTEXT_STUB
from src.config import (
    COMPANIES,
    GEMINI_LITE_MODEL, GEMINI_LITE_RPM, GEMINI_MAIN_MODEL, GEMINI_MAIN_RPM,
    gemini_configured, supabase_configured,
)
from src.llm import set_active_model, get_active_model


def pick_company() -> tuple[str, str]:
    print("Which stock do you want to run the analysis for?")
    for i, c in enumerate(COMPANIES, start=1):
        print(f"  {i}. {c['label']}  — {c['name']} ({c['ticker']})")
    while True:
        choice = input(f"Select [1-{len(COMPANIES)}]: ").strip()
        if choice.isdigit() and 1 <= int(choice) <= len(COMPANIES):
            c = COMPANIES[int(choice) - 1]
            return c["ticker"], c["name"]
        print("  Not a valid choice, try again.")


def main():
    parser = argparse.ArgumentParser(description="AlphaNet company research POC")
    parser.add_argument("mode", nargs="?", default="lite", choices=["lite", "high"],
                        help="'high' uses the main model (gemini-3.5-flash); "
                             "default is the lite model")
    parser.add_argument("--ticker", default=None)
    parser.add_argument("--company", default=None)
    parser.add_argument("--dry-run", action="store_true",
                         help="Skip search, Gemini, and Supabase entirely; verifies "
                              "the graph wiring and report assembly in seconds.")
    args = parser.parse_args()

    if args.mode == "high":
        set_active_model(GEMINI_MAIN_MODEL, GEMINI_MAIN_RPM)
    else:
        set_active_model(GEMINI_LITE_MODEL, GEMINI_LITE_RPM)

    if not args.dry_run and not gemini_configured():
        parser.exit(1, "GEMINI_API_KEY is not set (or is still the placeholder).\n"
                       "Copy .env.example to .env and fill it in, or run with --dry-run.\n")

    if args.ticker and args.company:
        ticker, company_name = args.ticker, args.company
    else:
        ticker, company_name = pick_company()

    # Run/entity bookkeeping (skipped in dry-run or when Supabase isn't set up).
    run_id, company_entity_id = "", ""
    persist = not args.dry_run and supabase_configured()
    if persist:
        from src import db
        company_entity_id = db.get_or_create_entity(
            company_name, "company", metadata={"ticker": ticker})
        run_id = db.start_run("company", company_entity_id)
        print(f"Run {run_id} started for entity {company_entity_id}")
    elif not args.dry_run:
        print("NOTE: Supabase is not configured — running without persistence.\n")

    app = build_graph()

    initial_state = {
        "ticker": ticker,
        "company_name": company_name,
        "macro_context": MACRO_CONTEXT_STUB,
        "industry_context": INDUSTRY_CONTEXT_STUB,
        "dry_run": args.dry_run,
        "run_id": run_id,
        "company_entity_id": company_entity_id,
        "raw_chunks": [],
        "financial_analysis": "",
        "business_model_analysis": "",
        "management_analysis": "",
        "risk_analysis": "",
        "peer_analysis": "",
        "valuation_synthesis": "",
        "final_report_md": "",
        "report_path": "",
    }

    mode = " (DRY RUN)" if args.dry_run else f" [model: {get_active_model()}]"
    print(f"\nRunning AlphaNet POC workflow for {company_name} ({ticker}){mode}...\n")

    def _mark_failed(reason: str):
        if persist:
            from src import db
            db.finish_run(run_id, "failed", model_used=get_active_model(),
                          error_message=reason[:2000])

    from src.llm import ModelOverloadedError, LLMError
    try:
        result = app.invoke(initial_state)
    except ModelOverloadedError as e:
        _mark_failed(str(e))
        parser.exit(1, f"\nStopped: {get_active_model()} is overloaded / out of quota.\n"
                       f"({e})\n"
                       f"No automatic retry — run main.py again in a little while. "
                       f"Already-ingested pages will be reused without new LLM calls.\n")
    except LLMError as e:
        _mark_failed(str(e))
        parser.exit(1, f"\nStopped on the first LLM error (no retry, by design): {e}\n"
                       f"Run marked as failed. Rerunning is safe — already-ingested "
                       f"pages are reused without new LLM calls.\n")
    except KeyboardInterrupt:
        _mark_failed("interrupted by user (Ctrl+C)")
        parser.exit(130, "\nInterrupted — run marked as failed. Rerunning is safe.\n")
    except Exception as e:
        _mark_failed(str(e))
        raise

    if persist:
        from src import db
        db.finish_run(run_id, "success", model_used=get_active_model())

    print(f"\nDone. Report saved to: {result['report_path']}")


if __name__ == "__main__":
    main()
