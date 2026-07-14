"""
The S0–S9 report-generation graph (REPORT_GEN_PLAYBOOK.md §1):

  s0_resolve -> s1_discover -> s2_extract -> s3_compute
      -> [B, D, E, F]   (parallel synthesis wave 1)
      -> G  (peers, needs D)
      -> H  (risks, needs G + pools)
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
    b_node, d_node, e_node, f_node, g_node, h_node, c_node, i_node, j_node,
)
from src.pipeline.s9_verifier import verifier_node
from src.pipeline.s8_composer import composer_node


def build_graph():
    g = StateGraph(ReportState)

    g.add_node("s0_resolve", resolve_node)
    g.add_node("s1_discover", discover_node)
    g.add_node("s2_extract", extract_node)
    g.add_node("s3_compute", compute_node)
    for name, fn in (("synth_B", b_node), ("synth_D", d_node),
                     ("synth_E", e_node), ("synth_F", f_node)):
        g.add_node(name, fn)
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
    for name in ("synth_B", "synth_D", "synth_E", "synth_F"):
        g.add_edge("s3_compute", name)
        g.add_edge(name, "synth_G")
    g.add_edge("synth_G", "synth_H")
    g.add_edge("synth_H", "synth_C")
    g.add_edge("synth_C", "synth_I")
    g.add_edge("synth_I", "synth_J")
    g.add_edge("synth_J", "s9_verifier")
    g.add_edge("s9_verifier", "s8_composer")
    g.add_edge("s8_composer", END)

    return g.compile()
