"""
The reasoning nodes of the Company Research Workflow.

Each analysis node gets a *filtered* slice of state["raw_chunks"] by source
type — a cheap stand-in for real retrieval. Fine at this scale (a few dozen
chunks); replace with an actual similarity search (e.g. pgvector) once a
company accumulates hundreds of chunks. That swap only touches
`format_chunks_for_prompt` below — no node signatures change.
"""

from src.llm import synthesize
from src.workflow import prompts

_DRY_RUN_TEXT = (
    "_(dry run — no LLM call made)_ This section would be grounded in the "
    "gathered source chunks, with claims cited like [concall_synthetic_0]."
)


def format_chunks_for_prompt(raw_chunks, source_types=None, max_chars=12000) -> str:
    chunks = raw_chunks
    if source_types is not None:
        chunks = [c for c in chunks if c["source_type"] in source_types]
        # The order of source_types expresses priority: company-level types
        # listed first get into the prompt budget before macro/industry
        # context. Stable sort keeps ingestion order within a type.
        chunks = sorted(chunks, key=lambda c: source_types.index(c["source_type"]))

    block = ""
    for c in chunks:
        entry = f"\n[{c['chunk_id']}] ({c['source_type']}, {c['source_title']})\n{c['text']}\n"
        if len(block) + len(entry) > max_chars:
            break
        block += entry
    return block or "(no relevant source excerpts were gathered for this section)"


def _run_section(state, template, source_types, state_key):
    if state.get("dry_run"):
        return {state_key: _DRY_RUN_TEXT}

    chunks_block = format_chunks_for_prompt(state["raw_chunks"], source_types=source_types)
    prompt = template.format(
        company_name=state["company_name"],
        ticker=state["ticker"],
        macro_context=state["macro_context"],
        industry_context=state["industry_context"],
        chunks_block=chunks_block,
    )
    content = synthesize([
        {"role": "system", "content": prompts.SYSTEM_PROMPT},
        {"role": "user", "content": prompt},
    ])
    return {state_key: content}


def financial_analysis_node(state):
    result = _run_section(
        state, prompts.FINANCIAL_ANALYSIS_PROMPT,
        source_types=["filing", "concall", "news", "industry", "macro_stub", "industry_stub"],
        state_key="financial_analysis",
    )
    print("[financial_analysis] done")
    return result


def business_model_node(state):
    result = _run_section(
        state, prompts.BUSINESS_MODEL_PROMPT,
        # broad context is useful here, but company-level sources first
        source_types=["filing", "concall", "news", "industry", "macro",
                      "macro_stub", "industry_stub"],
        state_key="business_model_analysis",
    )
    print("[business_model] done")
    return result


def management_node(state):
    result = _run_section(
        state, prompts.MANAGEMENT_PROMPT,
        source_types=["concall", "news"],
        state_key="management_analysis",
    )
    print("[management] done")
    return result


def risk_node(state):
    result = _run_section(
        state, prompts.RISK_PROMPT,
        source_types=["concall", "news", "filing", "macro", "industry", "macro_stub", "industry_stub"],
        state_key="risk_analysis",
    )
    print("[risk] done")
    return result


def peer_node(state):
    result = _run_section(
        state, prompts.PEER_PROMPT,
        source_types=["news", "industry", "industry_stub", "filing"],
        state_key="peer_analysis",
    )
    print("[peer] done")
    return result


def valuation_synthesis_node(state):
    if state.get("dry_run"):
        print("[valuation_synthesis] done (dry run)")
        return {"valuation_synthesis": _DRY_RUN_TEXT}

    prompt = prompts.VALUATION_SYNTHESIS_PROMPT.format(
        company_name=state["company_name"],
        ticker=state["ticker"],
        macro_context=state["macro_context"],
        industry_context=state["industry_context"],
        business_model_analysis=state["business_model_analysis"],
        financial_analysis=state["financial_analysis"],
        management_analysis=state["management_analysis"],
        risk_analysis=state["risk_analysis"],
        peer_analysis=state["peer_analysis"],
    )
    content = synthesize([
        {"role": "system", "content": prompts.SYSTEM_PROMPT},
        {"role": "user", "content": prompt},
    ])
    print("[valuation_synthesis] done")
    return {"valuation_synthesis": content}
