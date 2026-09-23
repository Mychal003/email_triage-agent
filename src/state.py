"""Schemat stanu przekazywanego między węzłami grafu."""

from typing import TypedDict, Optional, List


class TicketState(TypedDict, total=False):
    # dane wejściowe
    ticket_id: str
    sender: str
    subject: str
    body: str

    # wynik klasyfikacji
    category: str
    confidence: float

    # wynik RAG
    retrieved_context: List[str]

    # wygenerowana odpowiedź
    draft_reply: str

    # decyzja routingu: "auto" | "human_review"
    route_decision: str

    # status końcowy: "sent" | "rejected" | "ignored" (spam/phishing - patrz
    # skip_node w src/nodes/send.py)
    # (dopóki nie ustawiony, a graf jest zatrzymany na human_review -> zgłoszenie
    # oczekuje na akceptację człowieka; patrz interrupt() w src/nodes/send.py)
    status: str

    # log decyzji agenta (do audytu)
    audit_log: List[str]
