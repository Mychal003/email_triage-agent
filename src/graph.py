"""Definicja grafu LangGraph dla agenta triage'ującego zgłoszenia."""

from langgraph.graph import StateGraph, END

from src.state import TicketState
from src.nodes.classify import classify_node, classify_condition
from src.nodes.retrieve import retrieve_node
from src.nodes.generate import generate_node
from src.nodes.route import route_node, route_condition
from src.nodes.send import send_node, human_review_node, skip_node


def build_graph(checkpointer):
    """Buduje graf agenta.

    Węzeł `human_review` wywołuje `interrupt()`, więc graf wymaga
    checkpointera - bez niego LangGraph nie ma jak zapisać stanu w miejscu
    przerwania ani wznowić go później decyzją człowieka. Zobacz
    `src/checkpointer.py` po gotowe implementacje (pamięć procesu / sqlite).
    """
    graph = StateGraph(TicketState)

    graph.add_node("classify", classify_node)
    graph.add_node("retrieve", retrieve_node)
    graph.add_node("generate", generate_node)
    graph.add_node("route", route_node)
    graph.add_node("human_review", human_review_node)
    graph.add_node("send", send_node)
    graph.add_node("skip", skip_node)

    graph.set_entry_point("classify")

    graph.add_conditional_edges(
        "classify",
        classify_condition,
        {
            "spam": "skip",
            "process": "retrieve",
        },
    )
    graph.add_edge("retrieve", "generate")
    graph.add_edge("generate", "route")

    graph.add_conditional_edges(
        "route",
        route_condition,
        {
            "auto": "send",
            "human_review": "human_review",
        },
    )

    graph.add_edge("send", END)
    graph.add_edge("human_review", END)
    graph.add_edge("skip", END)

    return graph.compile(checkpointer=checkpointer)
