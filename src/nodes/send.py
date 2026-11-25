from langgraph.types import interrupt

from src.state import TicketState


def send_node(state: TicketState) -> TicketState:
    # TODO: podłączyć prawdziwe wysyłanie, np. Gmail API `messages.send`
    audit_log = state.get("audit_log", [])
    audit_log.append(f"[send] wysłano odpowiedź do {state['sender']}")

    return {
        **state,
        "status": "sent",
        "audit_log": audit_log,
    }


def skip_node(state: TicketState) -> TicketState:
    """Zgłoszenia sklasyfikowane jako spam/phishing kończą tu, bez
    generowania i bez wysyłania jakiejkolwiek odpowiedzi."""
    audit_log = state.get("audit_log", [])
    audit_log.append("[skip] spam/phishing - pominięto bez odpowiedzi")

    return {
        **state,
        "status": "ignored",
        "audit_log": audit_log,
    }


def human_review_node(state: TicketState) -> TicketState:
    decision = interrupt(
        {
            "ticket_id": state["ticket_id"],
            "sender": state["sender"],
            "subject": state["subject"],
            "category": state.get("category"),
            "confidence": state.get("confidence"),
            "draft_reply": state.get("draft_reply"),
        }
    )

    audit_log = state.get("audit_log", [])
    approved = bool(decision.get("approved"))
    reply = decision.get("edited_reply") or state.get("draft_reply")

    if approved:
        audit_log.append(
            f"[human_review] zaakceptowano przez człowieka - wysłano do {state['sender']}"
        )
        status = "sent"
    else:
        audit_log.append("[human_review] odrzucono przez człowieka")
        status = "rejected"

    return {
        **state,
        "status": status,
        "draft_reply": reply,
        "audit_log": audit_log,
    }
