"""Uruchomienie agenta nad prawdziwymi, nieprzeczytanymi mailami z Gmaila
(zamiast danych przykładowych z app.py).

Wymaga GMAIL_CREDENTIALS_PATH w .env (plik OAuth client ID z Google Cloud
Console, typ "Desktop app") - przy pierwszym uruchomieniu otworzy przeglądarkę
do autoryzacji, potem token jest cache'owany w GMAIL_TOKEN_PATH. Zakres jest
tylko do odczytu (gmail.readonly) - agent niczego nie wysyła ani nie
modyfikuje na koncie (patrz src/tools/gmail_client.py).
"""

from src.checkpointer import get_checkpointer
from src.cli import run_tickets
from src.graph import build_graph
from src.tools.gmail_client import fetch_unread_tickets


def main():
    agent = build_graph(get_checkpointer())
    tickets = fetch_unread_tickets()
    run_tickets(agent, tickets)


if __name__ == "__main__":
    main()
