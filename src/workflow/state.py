"""
Shared state that flows through every node in the Company Research graph.

Each parallel analysis node writes to its own key only, so LangGraph's
default state-merging (each node returns a partial dict update) is enough —
no custom reducers are needed for this POC.
"""

from typing import TypedDict, List, Optional, NotRequired


class SourceChunk(TypedDict):
    chunk_id: str             # evidence row UUID once persisted; synthetic id otherwise
    source_title: str
    source_url: str
    source_type: str          # "news" | "concall" | "filing" | "macro" | "industry" | "macro_stub" | "industry_stub"
    published_date: Optional[str]
    text: str
    evidence_id: NotRequired[Optional[str]]          # set when persisted to Supabase
    source_document_id: NotRequired[Optional[str]]   # set when persisted to Supabase


class CompanyResearchState(TypedDict):
    # inputs
    ticker: str
    company_name: str
    macro_context: str
    industry_context: str
    dry_run: bool

    # persistence context (empty strings when DB isn't configured / dry run)
    run_id: str
    company_entity_id: str

    # populated by gather_sources
    raw_chunks: List[SourceChunk]

    # populated by the parallel analysis nodes
    financial_analysis: str
    business_model_analysis: str
    management_analysis: str
    risk_analysis: str
    peer_analysis: str

    # populated by later nodes
    valuation_synthesis: str
    final_report_md: str
    report_path: str
