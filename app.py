"""Uruchomienie agenta na przykładowych zgłoszeniach (CLI demo).

Nad prawdziwą skrzynką Gmail zamiast danych przykładowych -> `gmail_app.py`.
"""

import json

from src.checkpointer import get_checkpointer
from src.cli import run_tickets
from src.graph import build_graph


def main():
    agent = build_graph(get_checkpointer())

    with open("data/sample_tickets.json", "r", encoding="utf-8") as f:
        tickets = json.load(f)

    run_tickets(agent, tickets)


if __name__ == "__main__":
    main()
