"""Checkpointer grafu - trwały zapis stanu, wymagany przez `interrupt()`
w węźle `human_review` (żeby CLI i Streamlit mogły dzielić te same,
oczekujące na akceptację, wątki rozmów)."""

import sqlite3

from langgraph.checkpoint.sqlite import SqliteSaver

CHECKPOINT_DB_PATH = "data/checkpoints.sqlite"


def get_checkpointer() -> SqliteSaver:
    """Zwraca checkpointer zapisujący do lokalnego pliku sqlite.

    Dzięki trwałości na dysku zgłoszenie wysłane do `human_review` przez
    `python app.py` może zostać zaakceptowane później, w osobnym procesie,
    przez `streamlit run streamlit_app.py`.
    """
    conn = sqlite3.connect(CHECKPOINT_DB_PATH, check_same_thread=False)
    return SqliteSaver(conn)
