"""
Assembles the final markdown report and writes it to disk.

Deliberately NOT an LLM call — formatting is a deterministic job, and
doing it in code is both cheaper and matches the project's own cost
philosophy ("prefer deterministic preprocessing over AI reasoning where
possible").

This also does one small but important trust check: it scans every
generated section for citation tags like [chunk_id], resolves them
against the chunks that were actually gathered, and flags any citation
the model wrote that doesn't correspond to a real source. That's a first,
lightweight version of the "groundedness verification" step from the
architecture discussion — not a replacement for a real verification LLM
pass later, but it catches outright invented citations for free.
"""

import os
import re
from datetime import datetime, timezone

from src.config import REPORTS_DIR, supabase_configured
from src import db


def _extract_cited_chunk_ids(*texts) -> set:
    ids = set()
    for t in texts:
        ids.update(re.findall(r"\[([a-zA-Z0-9_\.\-]+)\]", t or ""))
    return ids


def build_markdown(state) -> str:
    sections = [
        ("Business Overview", state.get("business_model_analysis", "")),
        ("Financial Analysis", state.get("financial_analysis", "")),
        ("Management & Guidance", state.get("management_analysis", "")),
        ("Risks", state.get("risk_analysis", "")),
        ("Peer & Market Positioning", state.get("peer_analysis", "")),
        ("Valuation & Key Takeaways", state.get("valuation_synthesis", "")),
    ]

    cited_ids = _extract_cited_chunk_ids(*(content for _, content in sections))
    chunk_by_id = {c["chunk_id"]: c for c in state.get("raw_chunks", [])}

    lines = []
    lines.append(f"# {state['company_name']} ({state['ticker']}) — AI Research Report")
    lines.append("")
    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    lines.append(f"_Generated {generated_at} — AlphaNet POC, Phase 1 walking skeleton_")
    lines.append("")
    lines.append("> Automated research synthesis, not investment advice. This is a "
                  "proof-of-concept pipeline — verify all figures against primary "
                  "sources before relying on anything here. No Buy/Sell/Hold view is "
                  "expressed or implied.")

    for title, content in sections:
        lines.append("")
        lines.append(f"## {title}")
        lines.append("")
        lines.append(content.strip() if content else "_Not generated._")

    lines.append("")
    lines.append("## Sources")
    lines.append("")
    if cited_ids:
        for cid in sorted(cited_ids):
            c = chunk_by_id.get(cid)
            if c:
                date_str = f", {c['published_date']}" if c.get("published_date") else ""
                lines.append(f"- **[{cid}]** {c['source_title']} "
                              f"({c['source_type']}{date_str}) — {c['source_url']}")
            else:
                lines.append(f"- **[{cid}]** ⚠️ cited by the model but not found among "
                              f"gathered sources — treat this claim with caution")
    else:
        lines.append("_No citation tags were found in the generated sections._")

    unresolved = [cid for cid in cited_ids if cid not in chunk_by_id]
    if unresolved:
        lines.append("")
        lines.append(f"**Note:** {len(unresolved)} citation(s) above could not be matched "
                      f"to a gathered source. This usually means the model referenced a "
                      f"chunk_id that wasn't actually provided to it — a sign the "
                      f"corresponding claim may not be reliably grounded.")

    return "\n".join(lines)


def write_report(ticker: str, markdown_text: str, output_dir: str = REPORTS_DIR) -> str:
    os.makedirs(output_dir, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    safe_ticker = re.sub(r"[^A-Za-z0-9_-]+", "_", ticker).strip("_") or "TICKER"
    filename = f"{safe_ticker}_{timestamp}.md"
    path = os.path.join(output_dir, filename)
    with open(path, "w", encoding="utf-8") as f:
        f.write(markdown_text)
    return path


def _persist_report_version(state, markdown_text: str) -> None:
    """Writes a report_versions row pinned to this run's sections. Macro/
    industry versions stay null until those loops exist (Sprint 3)."""
    company_entity_id = state.get("company_entity_id")
    if not company_entity_id:
        return
    sections_json = {
        "business_overview": state.get("business_model_analysis", ""),
        "financial_analysis": state.get("financial_analysis", ""),
        "management_guidance": state.get("management_analysis", ""),
        "risks": state.get("risk_analysis", ""),
        "peer_positioning": state.get("peer_analysis", ""),
        "valuation_key_takeaways": state.get("valuation_synthesis", ""),
        "final_report_md": markdown_text,
        "run_id": state.get("run_id") or None,
    }
    _, version = db.save_report_version(company_entity_id, sections_json)
    print(f"[report_composer] saved report_versions v{version} for company "
          f"entity {company_entity_id}")


def report_composer_node(state) -> dict:
    markdown_text = build_markdown(state)
    path = write_report(state["ticker"], markdown_text)
    print(f"[report_composer] report written to {path}")

    if not state.get("dry_run") and supabase_configured():
        try:
            _persist_report_version(state, markdown_text)
        except Exception as e:
            print(f"  [warn] failed to persist report version to Supabase: {e}")

    return {"final_report_md": markdown_text, "report_path": path}
