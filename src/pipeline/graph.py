"""
The S0–S9 report-generation graph (Phase 4 order; see HANDOFF3 §2):

  s0_resolve -> s1_discover -> s2_extract -> s3_compute
      -> [B, E, D1(s4a_pl), D2(s4b_bs), D3(s4c_cf)]   (parallel wave)
      -> s4d_followup (claim_checks pooling + bounded follow-ups)
      -> synth_D (s4e integrated financial synthesis + scoreboard)
      -> F  (management — AFTER s4e, consumes the credibility scoreboard)
      -> G  (peers, needs D)
      -> H  (risks, needs G + non-corroborated claims)
      -> C  (industry & macro — LAST narrative: needs E's graph edges)
      -> I  (valuation, needs D/G/C)
      -> s9_verifier -> s8_composer (with J written just before assembly)
"""

from langgraph.graph import StateGraph, START, END

from src.pipeline.state import ReportState
from src.pipeline.s0_resolve import resolve_node
from src.pipeline.s1_discover import discover_node
from src.pipeline.s2_extract import extract_node
from src.pipeline.s3_compute import compute_node
from src.pipeline.s4_synth import (
    b_node, d1_node, d2_node, d3_node, s4d_node, d_node, e_node, f_node,
    g_node, h_node, c_node, i_node, j_node,
)
from src.pipeline.s9_verifier import verifier_node
from src.pipeline.s8_composer import composer_node


def build_graph():
    g = StateGraph(ReportState)

    g.add_node("s0_resolve", resolve_node)
    g.add_node("s1_discover", discover_node)
    g.add_node("s2_extract", extract_node)
    g.add_node("s3_compute", compute_node)
    for name, fn in (("synth_B", b_node), ("synth_E", e_node),
                     ("synth_D1", d1_node), ("synth_D2", d2_node),
                     ("synth_D3", d3_node)):
        g.add_node(name, fn)
    g.add_node("s4d_followup", s4d_node)
    g.add_node("synth_D", d_node)
    g.add_node("synth_F", f_node)
    g.add_node("synth_G", g_node)
    g.add_node("synth_H", h_node)
    g.add_node("synth_C", c_node)
    g.add_node("synth_I", i_node)
    g.add_node("synth_J", j_node)
    g.add_node("s9_verifier", verifier_node)
    g.add_node("s8_composer", composer_node)

    g.add_edge(START, "s0_resolve")
    g.add_edge("s0_resolve", "s1_discover")
    g.add_edge("s1_discover", "s2_extract")
    g.add_edge("s2_extract", "s3_compute")
    for name in ("synth_B", "synth_E", "synth_D1", "synth_D2", "synth_D3"):
        g.add_edge("s3_compute", name)
    # LIST-form edges are joins (wait for ALL). Individual edges are
    # separate triggers — with B/E finishing 3 supersteps before the
    # D-chain, that re-ran F..composer twice (caught in dry-run).
    g.add_edge(["synth_D1", "synth_D2", "synth_D3"], "s4d_followup")
    g.add_edge("s4d_followup", "synth_D")
    # F waits for the whole first wave (B/E) plus the financial synthesis
    g.add_edge(["synth_B", "synth_E", "synth_D"], "synth_F")
    g.add_edge("synth_F", "synth_G")
    g.add_edge("synth_G", "synth_H")
    g.add_edge("synth_H", "synth_C")
    g.add_edge("synth_C", "synth_I")
    g.add_edge("synth_I", "synth_J")
    g.add_edge("synth_J", "s9_verifier")
    g.add_edge("s9_verifier", "s8_composer")
    g.add_edge("s8_composer", END)

    return g.compile()
