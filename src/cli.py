"""Wspólna pętla CLI: przepuszcza listę zgłoszeń przez graf agenta i
wypisuje wynik. Używane zarówno przez `app.py` (dane przykładowe), jak i
`gmail_app.py` (prawdziwe maile)."""

from typing import List


def run_tickets(agent, tickets: List[dict]) -> None:
    if not tickets:
        print("Brak zgłoszeń do przetworzenia.")
        return

    for ticket in tickets:
        print(f"\n{'=' * 60}")
        print(f"Zgłoszenie {ticket['ticket_id']}: {ticket['subject']}")
        print("=" * 60)

        # thread_id = ticket_id -> to samo zgłoszenie można później wznowić
        # (np. z poziomu Streamlit) po decyzji human_review
        config = {"configurable": {"thread_id": ticket["ticket_id"]}}
        initial_state = {**ticket, "audit_log": []}
        result = agent.invoke(initial_state, config)

        if "__interrupt__" in result:
            print(f"Kategoria: {result.get('category')} (pewność: {result.get('confidence')})")
            print("Decyzja: human_review -> status: pending_review")
            print(f"Szkic odpowiedzi:\n{result.get('draft_reply', '(brak)')}")
            print(
                "\n(zgłoszenie czeka na akceptację człowieka - uruchom "
                "`streamlit run streamlit_app.py`, aby je zaakceptować lub odrzucić)"
            )
            continue

        print(f"Kategoria: {result['category']} (pewność: {result['confidence']})")
        print(f"Decyzja: {result['route_decision']} -> status: {result['status']}")
        print(f"Odpowiedź:\n{result.get('draft_reply', '(brak)')}")
        print("\nLog audytowy:")
        for entry in result["audit_log"]:
            print(f"  - {entry}")
