"""
Prompt templates. Deliberately simple for this POC — the point right now
is validating that the grounded, cited pipeline works end to end, not
prompt-perfecting each section. Tighten these once Phase 1 output has been
manually reviewed against real sources.
"""

SYSTEM_PROMPT = """\
You are an equity research analyst assistant for AlphaNet, an AI-native \
research platform for Indian equities. You write institutional-quality, \
neutral research commentary. You never give Buy/Sell/Hold recommendations.

Rules you must follow without exception:
1. Only use the information in the provided source excerpts and the macro/ \
industry context below. Do not use any outside knowledge you may have \
about this company's current financials, share price, or recent events.
2. Every specific factual claim (a number, a date, a management statement, \
a named event, a competitor name) must end with a citation tag in square \
brackets referencing the chunk_id it came from, e.g. [concall_0] or \
[news_Reuters_1].
3. If the provided sources do not contain enough information to cover part \
of the brief, explicitly write "insufficient information in provided \
sources" for that part instead of guessing or inventing details.
4. Never fabricate a chunk_id. Only cite chunk_ids that literally appear in \
the source excerpts you were given.
5. Write dense, analytical prose for a serious investor — not marketing \
language, and not a recommendation.
"""

_HEADER = """\
Company: {company_name} ({ticker})

Macro context:
{macro_context}

Industry context:
{industry_context}

Source excerpts (cite by chunk_id exactly as shown in brackets):
{chunks_block}
"""

FINANCIAL_ANALYSIS_PROMPT = _HEADER + """
Write the "Financial Analysis" section of the research report. Cover, to \
the extent the sources allow:
- Revenue and profitability trends (growth, margins)
- Balance sheet observations (debt levels, working capital) if mentioned
- Cash flow commentary if mentioned
- Any ratios or per-share metrics mentioned in the sources
- Management commentary on financial performance from the concall, if present

Cite every factual claim with its chunk_id. State plainly where a sub-topic \
isn't covered by the sources rather than filling the gap yourself.
"""

BUSINESS_MODEL_PROMPT = _HEADER + """
Write the "Business Overview" section of the research report. Cover, to the \
extent the sources allow:
- What the company does and how it makes money
- Key products/segments and customer base
- Competitive positioning and moat, if discussed
- Recent strategic developments (new orders, capacity, partnerships)

Cite every factual claim with its chunk_id. State plainly where a sub-topic \
isn't covered by the sources rather than filling the gap yourself.
"""

MANAGEMENT_PROMPT = _HEADER + """
Write the "Management & Guidance" section of the research report. Cover, to \
the extent the sources allow:
- Management's stated outlook and guidance from the concall/filings
- Capex plans, order-book commentary, capacity expansion plans
- Notable management commentary on challenges or opportunities

Cite every factual claim with its chunk_id. State plainly where a sub-topic \
isn't covered by the sources rather than filling the gap yourself.
"""

RISK_PROMPT = _HEADER + """
Write the "Risks" section of the research report. Cover, to the extent the \
sources allow:
- Business/operational risks mentioned (customer concentration, input costs, \
execution risk on new platforms)
- Macro or industry risks relevant to this company specifically
- Any regulatory, governance, or ESG-related concerns mentioned in the sources

Cite every factual claim with its chunk_id. State plainly where a sub-topic \
isn't covered by the sources rather than filling the gap yourself.
"""

PEER_PROMPT = _HEADER + """
Write the "Peer & Market Positioning" section of the research report. Cover, \
to the extent the sources allow:
- Named competitors or peer companies mentioned in the sources
- How this company's positioning compares (scale, product breadth, \
end-market exposure) based only on what the sources say
- Any relative performance or market-share commentary mentioned

Cite every factual claim with its chunk_id. State plainly where a sub-topic \
isn't covered by the sources rather than filling the gap yourself.
"""

VALUATION_SYNTHESIS_PROMPT = """\
Company: {company_name} ({ticker})

Macro context:
{macro_context}

Industry context:
{industry_context}

Business Overview section already written:
{business_model_analysis}

Financial Analysis section already written:
{financial_analysis}

Management & Guidance section already written:
{management_analysis}

Risks section already written:
{risk_analysis}

Peer & Market Positioning section already written:
{peer_analysis}

Write a "Valuation & Key Takeaways" section that:
1. Discusses valuation positioning only in qualitative terms based on any \
multiples, analyst commentary, or relative-value language that appears in \
the sections above — do not compute or invent a price target, fair value, \
or specific multiple that wasn't already stated in those sections.
2. Synthesizes the sections above into 4-6 crisp key-takeaway bullet points.
3. Does not issue any Buy/Sell/Hold recommendation.

Preserve any citation tags [like_this] that already appear in the sections \
above if you reference the same facts; do not invent new ones.
"""
