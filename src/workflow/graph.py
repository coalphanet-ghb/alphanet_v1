"""
Wires up the Company Research Workflow as an actual LangGraph graph:

           gather_sources
          /  |   |   |   \\
   financial biz mgmt risk peer     <- run in parallel (fan-out)
          \\  |   |   |   /
           valuation_synthesis       <- fan-in, waits for all five
                  |
             report_composer

This shape mirrors the "Company Research Workflow" box in the original
architecture diagram: parallel specialist nodes feeding a synthesis step.
"""

from langgraph.graph import StateGraph, START, END

from src.workflow.state import CompanyResearchState
from src.ingestion.research import gather_sources_node
from src.workflow.nodes import (
    financial_analysis_node,
    business_model_node,
    management_node,
    risk_node,
    peer_node,
    valuation_synthesis_node,
)
from src.output.report_writer import report_composer_node

_ANALYSIS_NODES = {
    "financial_analysis": financial_analysis_node,
    "business_model": business_model_node,
    "management": management_node,
    "risk": risk_node,
    "peer": peer_node,
}


def build_graph():
    graph = StateGraph(CompanyResearchState)

    graph.add_node("gather_sources", gather_sources_node)
    for name, fn in _ANALYSIS_NODES.items():
        graph.add_node(name, fn)
    graph.add_node("valuation_synthesis", valuation_synthesis_node)
    graph.add_node("report_composer", report_composer_node)

    graph.add_edge(START, "gather_sources")
    for name in _ANALYSIS_NODES:
        graph.add_edge("gather_sources", name)
        graph.add_edge(name, "valuation_synthesis")
    graph.add_edge("valuation_synthesis", "report_composer")
    graph.add_edge("report_composer", END)

    return graph.compile()
