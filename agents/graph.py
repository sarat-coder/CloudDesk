"""LangGraph workflow for CloudDesk support resolution.

Graph shape (§7.3 of CLAUDE.md):
  understand_ticket → classify_severity → customer_context → knowledge_retrieval
  → troubleshooting → resolution_planning → escalation_check → risk_check
      ├─ escalation_required          → escalation
      ├─ approval pending             → human_approval (interrupt)
      │       ├─ approved             → execute_resolution
      │       └─ rejected             → escalation
      └─ low risk                     → execute_resolution
  → ticket_summary → memory_update → END

GRAPH_NODES and GRAPH_EDGES are consumed by GET /api/v1/agents.
"""
from __future__ import annotations

from typing import Any

from langgraph.graph import END, START, StateGraph

from agents.state import SupportState

# Node IDs — these are the values completed_nodes contains and the frontend renders.
GRAPH_NODES = [
    "understand_ticket",
    "classify_severity",
    "customer_context",
    "knowledge_retrieval",
    "troubleshooting",
    "resolution_planning",
    "escalation_check",
    "risk_check",
    "escalation",
    "human_approval",
    "execute_resolution",
    "ticket_summary",
    "memory_update",
]

GRAPH_EDGES: list[tuple[str, str]] = [
    ("understand_ticket", "classify_severity"),
    ("classify_severity", "customer_context"),
    ("customer_context", "knowledge_retrieval"),
    ("knowledge_retrieval", "troubleshooting"),
    ("troubleshooting", "resolution_planning"),
    ("resolution_planning", "escalation_check"),
    ("escalation_check", "risk_check"),
    ("risk_check", "escalation"),        # conditional
    ("risk_check", "human_approval"),    # conditional
    ("risk_check", "execute_resolution"),# conditional
    ("human_approval", "execute_resolution"),  # on approve
    ("human_approval", "escalation"),          # on reject
    ("execute_resolution", "ticket_summary"),
    ("escalation", "ticket_summary"),
    ("ticket_summary", "memory_update"),
    ("memory_update", "END"),
]


# ---------------------------------------------------------------------------
# Routing functions
# ---------------------------------------------------------------------------


def _route_after_risk(state: SupportState) -> str:
    """Decide where to go after risk_check."""
    escalation_decision = state.get("escalation_decision")
    if escalation_decision and escalation_decision.escalation_required:
        return "escalation"

    planned_actions = state.get("planned_actions", [])
    if any(a.requires_approval for a in planned_actions):
        return "human_approval"

    return "execute_resolution"


def _route_after_human_approval(state: SupportState) -> str:
    """After human_approval, route based on the decision stored in state."""
    approved = state.get("_approval_decision", False)
    if approved:
        return "execute_resolution"
    return "escalation"


# ---------------------------------------------------------------------------
# Graph builder
# ---------------------------------------------------------------------------


def build_graph(checkpointer: Any = None) -> Any:
    """Build and compile the support workflow graph.

    Args:
        checkpointer: LangGraph checkpointer (InMemorySaver in tests,
                      AsyncSqliteSaver in production). None → no checkpointing.
    """
    from agents.nodes.understand_ticket import understand_ticket
    from agents.nodes.classify_severity import classify_severity
    from agents.nodes.customer_context import customer_context
    from agents.nodes.knowledge_retrieval import knowledge_retrieval
    from agents.nodes.troubleshooting import troubleshooting as troubleshooting_node
    from agents.nodes.resolution_planning import resolution_planning
    from agents.nodes.escalation_check import escalation_check
    from agents.nodes.risk_check import risk_check
    from agents.nodes.escalation import escalation
    from agents.nodes.human_approval import human_approval
    from agents.nodes.execute_resolution import execute_resolution
    from agents.nodes.ticket_summary import ticket_summary
    from agents.nodes.memory_update import memory_update

    builder = StateGraph(SupportState)

    # Add all nodes
    builder.add_node("understand_ticket", understand_ticket)
    builder.add_node("classify_severity", classify_severity)
    builder.add_node("customer_context", customer_context)
    builder.add_node("knowledge_retrieval", knowledge_retrieval)
    builder.add_node("troubleshooting", troubleshooting_node)
    builder.add_node("resolution_planning", resolution_planning)
    builder.add_node("escalation_check", escalation_check)
    builder.add_node("risk_check", risk_check)
    builder.add_node("escalation", escalation)
    builder.add_node("human_approval", human_approval)
    builder.add_node("execute_resolution", execute_resolution)
    builder.add_node("ticket_summary", ticket_summary)
    builder.add_node("memory_update", memory_update)

    # Linear edges
    builder.add_edge(START, "understand_ticket")
    builder.add_edge("understand_ticket", "classify_severity")
    builder.add_edge("classify_severity", "customer_context")
    builder.add_edge("customer_context", "knowledge_retrieval")
    builder.add_edge("knowledge_retrieval", "troubleshooting")
    builder.add_edge("troubleshooting", "resolution_planning")
    builder.add_edge("resolution_planning", "escalation_check")
    builder.add_edge("escalation_check", "risk_check")

    # Conditional routing after risk_check
    builder.add_conditional_edges(
        "risk_check",
        _route_after_risk,
        {
            "escalation": "escalation",
            "human_approval": "human_approval",
            "execute_resolution": "execute_resolution",
        },
    )

    # Conditional routing after human_approval (interrupt)
    builder.add_conditional_edges(
        "human_approval",
        _route_after_human_approval,
        {
            "execute_resolution": "execute_resolution",
            "escalation": "escalation",
        },
    )

    # Both paths converge at ticket_summary
    builder.add_edge("execute_resolution", "ticket_summary")
    builder.add_edge("escalation", "ticket_summary")
    builder.add_edge("ticket_summary", "memory_update")
    builder.add_edge("memory_update", END)

    if checkpointer is not None:
        return builder.compile(checkpointer=checkpointer, interrupt_before=["human_approval"])
    return builder.compile(interrupt_before=["human_approval"])


# ---------------------------------------------------------------------------
# Module-level compiled graph (lazy-initialised)
# ---------------------------------------------------------------------------

_compiled_graph: Any = None


def get_graph() -> Any:
    """Return the compiled support graph, lazily initialised with the checkpointer."""
    global _compiled_graph
    if _compiled_graph is None:
        from agents.checkpointer import get_checkpointer
        checkpointer = get_checkpointer()
        _compiled_graph = build_graph(checkpointer=checkpointer)
    return _compiled_graph


def reset_graph() -> None:
    """Reset the cached graph — used in tests."""
    global _compiled_graph
    _compiled_graph = None
