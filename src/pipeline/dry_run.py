"""
Synthetic fixtures so `--dry-run` exercises the full graph — extraction
pools, compute on canned metrics, envelope flow, composer render — with
zero network, zero LLM, zero DB.
"""


def synthetic_extraction(state) -> dict:
    company = state["profile"]["name"]
    ev = [
        {"id": "syn_ev_concall", "text": f"[synthetic] Management of {company} guided for "
         "25-27% EBITDA margin for FY27 as the new plant ramps.",
         "url": "internal://dry_run", "doc_class": "concall",
         "title": "(synthetic) concall", "tags": ["guidance_item"], "page": "p.7"},
        {"id": "syn_ev_ar", "text": f"[synthetic] {company} sources 40% of raw material "
         "as imported specialty alloys; steel is the largest cost head.",
         "url": "internal://dry_run", "doc_class": "annual_report",
         "title": "(synthetic) annual report", "tags": ["supply_chain_edge"], "page": "p.112"},
        {"id": "syn_ev_rating", "text": "[synthetic] The rating agency notes customer "
         "concentration with the top OEM at 28% of revenue as a key weakness.",
         "url": "internal://dry_run", "doc_class": "rating_rationale",
         "title": "(synthetic) rating rationale", "tags": ["risk_signal"], "page": None},
    ]
    candidates = []
    for fy, rev, npf, opm, cfo in (("FY23", 2100, 220, 24.1, 190),
                                   ("FY24", 2600, 290, 25.0, 240),
                                   ("FY25", 3150, 355, 25.6, 300),
                                   ("FY26", 3900, 450, 26.2, 380)):
        candidates += [
            {"name": "revenue", "value_printed": f"{rev}", "period_printed": fy,
             "basis": "consolidated", "statement": "P&L", "ambiguous": False,
             "doc_class": "screener_page",
             "url": f"https://www.screener.in/company/{state['profile']['screener_slug']}/consolidated/"},
            {"name": "net profit", "value_printed": f"{npf}", "period_printed": fy,
             "basis": "consolidated", "statement": "P&L", "ambiguous": False,
             "doc_class": "screener_page",
             "url": f"https://www.screener.in/company/{state['profile']['screener_slug']}/consolidated/"},
            {"name": "OPM", "value_printed": f"{opm}%", "period_printed": fy,
             "basis": "consolidated", "statement": "ratio", "ambiguous": False,
             "doc_class": "screener_page",
             "url": f"https://www.screener.in/company/{state['profile']['screener_slug']}/consolidated/"},
            {"name": "cash from operating activity", "value_printed": f"{cfo}",
             "period_printed": fy, "basis": "consolidated", "statement": "CF",
             "ambiguous": False, "doc_class": "screener_page",
             "url": f"https://www.screener.in/company/{state['profile']['screener_slug']}/consolidated/"},
        ]
    candidates += [
        {"name": "Stock P/E", "value_printed": "42.5", "period_printed": "FY26",
         "basis": None, "statement": "price", "ambiguous": False,
         "doc_class": "screener_page",
         "url": f"https://www.screener.in/company/{state['profile']['screener_slug']}/consolidated/"},
        {"name": "ROE", "value_printed": "19.4%", "period_printed": "FY26",
         "basis": None, "statement": "ratio", "ambiguous": False,
         "doc_class": "screener_page",
         "url": f"https://www.screener.in/company/{state['profile']['screener_slug']}/consolidated/"},
    ]
    return {
        "evidence_pool": ev,
        "metric_candidates": candidates,
        "guidance_items": [{"metric": "EBITDA margin", "period": "FY27",
                            "value_or_direction": "25-27%",
                            "quote": ev[0]["text"], "speaker": "CFO"}],
        "risk_signals": [{"evidence_id": "syn_ev_rating", "text": ev[2]["text"],
                          "url": "internal://dry_run"}],
        "supply_edges": [{"from_entity": "Steel", "relation": "input_cost_for",
                          "to_entity": company, "quote": ev[1]["text"]}],
        "peer_mentions": ["Synthetic Peer Ltd"],
        "events": [],
        "read_log": [{"url": "internal://dry_run", "outcome": "synthetic"}],
    }


def synthetic_envelope(letter: str) -> dict:
    env = {
        "section": letter,
        "blocks": [
            {"type": "narrative", "id": f"{letter.lower()}_dry",
             "title": f"(dry run) section {letter}",
             "md": "_Dry run — no LLM call. This block would contain the "
                   f"section-{letter} analysis grounded in evidence and "
                   "calc:* citations._",
             "citations": ["syn_ev_concall"]},
        ],
        "claims": [{"text": f"(dry) synthetic claim for section {letter}",
                    "evidence_ids": ["syn_ev_concall"], "confidence": 1.0}],
        "insufficiencies": ["dry run — everything"],
    }
    # Phase 4: statement-forensic envelopes carry claim_checks +
    # followup_requests so the s4d/s4e/F/H paths run in dry-run too.
    if letter in ("D1", "D2", "D3"):
        env["claim_checks"] = [
            {"mgmt_claim": f"(dry) guided 25-27% EBITDA margin ({letter})",
             "evidence_id": "syn_ev_concall",
             "computed_ref": "calc:opm_pct_series",
             "verdict": "contradicted" if letter == "D1" else "corroborated",
             "note": "(dry) computed series vs guided range"}]
        env["followup_requests"] = [
            {"target": "computed" if letter != "D3" else "evidence",
             "request": f"(dry) follow-up from {letter} on revenue trend",
             "keywords": ["revenue"]}]
    return env
