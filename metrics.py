"""Metryki z historii przetworzonych zgłoszeń (README "Kolejne kroki rozwoju").

Nie wprowadza nowej trwałości - czyta stany zgłoszeń już zapisane przez
checkpointer grafu (data/checkpoints.sqlite, patrz src/checkpointer.py),
czyli historię ze wszystkich dotychczasowych uruchomień app.py / gmail_app.py.

Uruchomienie:
    python metrics.py
"""

import sqlite3
from collections import Counter
from typing import List

from src.checkpointer import CHECKPOINT_DB_PATH, get_checkpointer
from src.graph import build_graph


def _thread_ids() -> List[str]:
    conn = sqlite3.connect(CHECKPOINT_DB_PATH)
    try:
        cursor = conn.execute("SELECT DISTINCT thread_id FROM checkpoints")
        return [row[0] for row in cursor.fetchall()]
    finally:
        conn.close()


def collect_states() -> List[dict]:
    """Zwraca stan każdego przetworzonego zgłoszenia (wątku) - łącznie z tymi
    wciąż czekającymi w human_review, dla których część pól jeszcze nie
    istnieje w stanie (patrz src/state.py)."""
    checkpointer = get_checkpointer()
    agent = build_graph(checkpointer)

    states = []
    for thread_id in _thread_ids():
        config = {"configurable": {"thread_id": thread_id}}
        snapshot = agent.get_state(config)
        if snapshot.values:
            states.append(snapshot.values)
    return states


def print_report(states: List[dict]) -> None:
    total = len(states)
    if total == 0:
        print(f"Brak przetworzonych zgłoszeń w {CHECKPOINT_DB_PATH}.")
        print("Uruchom najpierw `python app.py` albo `python gmail_app.py`.")
        return

    # status brakuje w stanie, dopóki human_review nie zostanie rozstrzygnięty
    # (interrupt() w src/nodes/send.py) - traktujemy to jako pending_review
    status_counts = Counter(s.get("status", "pending_review") for s in states)
    decision_counts = Counter(s.get("route_decision", "brak") for s in states)
    category_counts = Counter(s.get("category", "brak") for s in states)
    confidences = [s["confidence"] for s in states if "confidence" in s]

    auto = decision_counts.get("auto", 0)
    ignored = status_counts.get("ignored", 0)

    print(f"Przetworzonych zgłoszeń: {total}")
    print(f"W pełni zautomatyzowanych (auto): {auto} ({100 * auto / total:.0f}%)")
    print(f"Skierowanych do human_review: {decision_counts.get('human_review', 0)}")
    print(f"Pominiętych jako spam/phishing (bez odpowiedzi): {ignored}")

    print("\nStatusy:")
    for status, count in status_counts.most_common():
        print(f"  {status}: {count} ({100 * count / total:.0f}%)")

    print("\nKategorie:")
    for category, count in category_counts.most_common():
        print(f"  {category}: {count} ({100 * count / total:.0f}%)")

    if confidences:
        print(f"\nŚrednia pewność klasyfikacji: {sum(confidences) / len(confidences):.2f}")
        print(f"Zakres pewności: {min(confidences):.2f} - {max(confidences):.2f}")


if __name__ == "__main__":
    print_report(collect_states())
