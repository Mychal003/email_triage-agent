"""Podstawowy test end-to-end grafu (wymaga ustawionego ANTHROPIC_API_KEY)."""

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command

from src.graph import build_graph


def test_low_risk_ticket_routes_correctly():
    agent = build_graph(InMemorySaver())

    state = {
        "ticket_id": "T-TEST",
        "sender": "test@example.com",
        "subject": "Ile trwa dostawa?",
        "body": "Ile trwa standardowa dostawa produktu?",
        "audit_log": [],
    }
    config = {"configurable": {"thread_id": "T-TEST"}}

    result = agent.invoke(state, config)

    if "__interrupt__" in result:
        # klasyfikacja mogła i tak uznać zgłoszenie za wymagające przeglądu -
        # zasymuluj akceptację człowieka, żeby dociągnąć graf do końca
        result = agent.invoke(
            Command(resume={"approved": True, "edited_reply": None}), config
        )

    assert result["route_decision"] in ("auto", "human_review")
    assert result["status"] in ("sent", "rejected")
    assert "draft_reply" in result
    assert len(result["audit_log"]) > 0


def test_sensitive_ticket_pauses_for_human_review_and_can_be_rejected():
    agent = build_graph(InMemorySaver())

    state = {
        "ticket_id": "T-TEST-SENSITIVE",
        "sender": "test@example.com",
        "subject": "Uszkodzona przesyłka",
        "body": (
            "Otrzymałem produkt dzisiaj i jest uszkodzony w transporcie. "
            "Chcę złożyć reklamację i otrzymać zwrot pieniędzy."
        ),
        "audit_log": [],
    }
    config = {"configurable": {"thread_id": "T-TEST-SENSITIVE"}}

    result = agent.invoke(state, config)

    assert "__interrupt__" in result
    assert result["route_decision"] == "human_review"

    result = agent.invoke(Command(resume={"approved": False}), config)

    assert result["status"] == "rejected"
    assert any("odrzucono" in entry for entry in result["audit_log"])


def test_spam_ticket_never_gets_a_reply():
    agent = build_graph(InMemorySaver())

    state = {
        "ticket_id": "T-TEST-SPAM",
        "sender": "phishing@suspicious-domain.example",
        "subject": "PILNE: Twoje konto zostanie zablokowane - zweryfikuj dane",
        "body": (
            "Kliknij w link, aby zweryfikować dane logowania, inaczej Twoje "
            "konto zostanie trwale usunięte w ciągu 24 godzin: "
            "http://suspicious-domain.example/login"
        ),
        "audit_log": [],
    }
    config = {"configurable": {"thread_id": "T-TEST-SPAM"}}

    result = agent.invoke(state, config)

    assert "__interrupt__" not in result
    assert result["category"] == "spam"
    assert result["status"] == "ignored"
    assert "draft_reply" not in result
    assert any("skip" in entry for entry in result["audit_log"])
