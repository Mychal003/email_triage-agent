from src.config import CATEGORIES, CONFIDENCE_THRESHOLD, SENSITIVE_CATEGORIES
from src.state import TicketState

#Przyjmuje aktualny stan grafu i na jego podstawie podejmuje decyzję dotyczącą dalszego przetwarzania zgłoszenia.
def route_node(state: TicketState) -> TicketState:
    category = state.get("category", "inne")
    confidence = state.get("confidence", 0.0)

    # dodatkowe zabezpieczenie - classify_node już normalizuje kategorię, ale
    # kategoria spoza listy nigdy nie może zostać wysłana automatycznie
    is_unknown = category not in CATEGORIES
    is_sensitive = category in SENSITIVE_CATEGORIES
    is_low_confidence = confidence < CONFIDENCE_THRESHOLD

    decision = (
        "human_review" if (is_unknown or is_sensitive or is_low_confidence) else "auto"
    )

    audit_log = state.get("audit_log", [])
    if is_unknown:
        reason = "nieznana kategoria"
    elif is_sensitive:
        reason = "kategoria wrażliwa"
    elif is_low_confidence:
        reason = "niska pewność"
    else:
        reason = "wysoka pewność, kategoria bezpieczna"
    audit_log.append(f"[route] decyzja={decision} ({reason})")

    return {
        **state,
        "route_decision": decision,
        "audit_log": audit_log,
    }

#Odczytuje decyzję podjętą wcześniej przez route_node() i zwraca ją do LangGraph.
def route_condition(state: TicketState) -> str:
    """Funkcja warunkowa używana przez LangGraph do wyboru kolejnej krawędzi."""
    return state["route_decision"]
