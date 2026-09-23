"""Węzeł: decyzja routingu - auto-wysyłka czy przegląd człowieka.

To jest serce logiki human-in-the-loop: agent NIE wysyła odpowiedzi
automatycznie, jeśli pewność klasyfikacji jest zbyt niska albo kategoria
jest oznaczona jako wrażliwa.
"""

from src.config import CONFIDENCE_THRESHOLD, SENSITIVE_CATEGORIES
from src.state import TicketState


def route_node(state: TicketState) -> TicketState:
    category = state.get("category", "inne")
    confidence = state.get("confidence", 0.0)

    is_sensitive = category in SENSITIVE_CATEGORIES
    is_low_confidence = confidence < CONFIDENCE_THRESHOLD

    decision = "human_review" if (is_sensitive or is_low_confidence) else "auto"

    audit_log = state.get("audit_log", [])
    reason = "kategoria wrażliwa" if is_sensitive else (
        "niska pewność" if is_low_confidence else "wysoka pewność, kategoria bezpieczna"
    )
    audit_log.append(f"[route] decyzja={decision} ({reason})")

    return {
        **state,
        "route_decision": decision,
        "audit_log": audit_log,
    }


def route_condition(state: TicketState) -> str:
    """Funkcja warunkowa używana przez LangGraph do wyboru kolejnej krawędzi."""
    return state["route_decision"]
