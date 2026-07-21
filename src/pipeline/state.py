"""
Shared state flowing through the S0–S9 report-generation graph.

Nodes write their own keys; envelopes are also persisted to
knowledge_entries as they land (state is the working copy, DB is the
record). Everything is plain dicts so LangGraph's default merge works.
"""

from typing import TypedDict, List, Optional, NotRequired


class ReportState(TypedDict):
    # run identity
    dry_run: bool
    run_id: str
    persist: bool                       # Supabase configured & not dry-run
    reingest: NotRequired[bool]         # --reingest: ignore stored extractions

    # s0_resolve
    profile: dict                       # company profile (config entry + entity ids)
    pack: dict                          # loaded sector pack
    peer_entities: List[dict]           # [{id, name, metadata}]
    read_plan: NotRequired[dict]

    # s1_discover
    url_plan: NotRequired[List[dict]]   # [{target, doc_class, urls, batch, priority}]
    backbone: NotRequired[dict]         # Round 3.2: {"members": {slug: content}} — sector-stored screener+price data; s2 rehydrates instead of fetching
    refresh_sector: NotRequired[bool]   # --refresh-sector: force backbone refresh

    # s2_extract (in-memory working pools; persisted as they land)
    evidence_pool: NotRequired[List[dict]]      # [{id, text, doc_class, url, title, tags, page}]
    metric_candidates: NotRequired[List[dict]]
    guidance_items: NotRequired[List[dict]]
    risk_signals: NotRequired[List[dict]]       # evidence refs tagged risk
    supply_edges: NotRequired[List[dict]]
    peer_mentions: NotRequired[List[str]]
    events: NotRequired[List[dict]]
    guidance_evolution: NotRequired[List[dict]]  # cross-quarter concall trails (Phase 3.3)
    recurring_themes: NotRequired[List[dict]]    # cross-quarter concall themes/dodges
    read_log: NotRequired[List[dict]]           # per-URL outcome (reused/read/failed)
    screener_doc_links: NotRequired[dict]       # url -> {concall_transcripts, annual_reports}

    # s3_compute
    computed: NotRequired[dict]         # {computed_financials, forensic_flags, guidance_scorecard, peer_table, valuation_context, insufficiencies}

    # s4 statement-forensic wave (Phase 4)
    envelope_D1: NotRequired[dict]      # P&L forensic node (s4a_pl)
    envelope_D2: NotRequired[dict]      # BS forensic node (s4b_bs)
    envelope_D3: NotRequired[dict]      # CF forensic node (s4c_cf)
    claim_checks: NotRequired[List[dict]]   # pooled mgmt-claim-vs-numbers verdicts
    followups: NotRequired[List[dict]]      # answered followup_requests (s4d)

    # s4–s8 section envelopes, keyed by blueprint letter
    envelope_B: NotRequired[dict]
    envelope_C: NotRequired[dict]
    envelope_D: NotRequired[dict]
    envelope_E: NotRequired[dict]
    envelope_F: NotRequired[dict]
    envelope_G: NotRequired[dict]
    envelope_H: NotRequired[dict]
    envelope_I: NotRequired[dict]
    envelope_J: NotRequired[dict]

    # s9 + s8_composer
    verification: NotRequired[dict]     # {claim_id: verdict}
    report_path: NotRequired[str]
    final_report_md: NotRequired[str]
