"""Węzeł: pobranie relevantnego kontekstu z bazy wiedzy (RAG)."""

from src.state import TicketState
from src.tools.knowledge_base import retrieve_context


def retrieve_node(state: TicketState) -> TicketState:
    query = f"{state['subject']} {state['body']}"
    context = retrieve_context(query)

    audit_log = state.get("audit_log", [])
    audit_log.append(f"[retrieve] znaleziono {len(context)} fragmentów kontekstu")

    return {
        **state,
        "retrieved_context": context,
        "audit_log": audit_log,
    }
