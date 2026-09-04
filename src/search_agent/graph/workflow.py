from typing import Any

from langgraph.graph import END, START, StateGraph

from search_agent.graph.nodes import Nodes
from search_agent.graph.state import AgentState


def build_graph(nodes: Nodes) -> Any:
    graph = StateGraph(AgentState)
    for name, node in (
        ("classify", nodes.classify),
        ("resolve_scope", nodes.resolve),
        ("retrieve", nodes.retrieve),
        ("evaluate", nodes.evaluate),
        ("search_web", nodes.web),
        ("ingest_report", nodes.ingest_report),
        ("synthesize", nodes.synthesize),
        ("validate_citations", nodes.validate),
    ):
        graph.add_node(name, node)
    graph.add_edge(START, "classify")
    graph.add_conditional_edges("classify", lambda s: "synthesize" if s["route"] == "conversation" else "resolve_scope")
    graph.add_edge("resolve_scope", "retrieve")
    graph.add_edge("retrieve", "evaluate")
    graph.add_conditional_edges(
        "evaluate", lambda s: "search_web" if s["use_web"] and s.get("attempts", 0) < 2 else "synthesize"
    )
    graph.add_edge("search_web", "ingest_report")
    graph.add_edge("ingest_report", "retrieve")
    graph.add_edge("synthesize", "validate_citations")
    graph.add_edge("validate_citations", END)
    return graph.compile()
