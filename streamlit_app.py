import json
import sqlite3

import streamlit as st
from langgraph.types import Command

from src.checkpointer import CHECKPOINT_DB_PATH, get_checkpointer
from src.graph import build_graph

st.set_page_config(page_title="Email Triage Agent - przegląd", page_icon="📬")


@st.cache_resource
def get_agent():
    return build_graph(get_checkpointer())


def load_sample_tickets():
    with open("data/sample_tickets.json", "r", encoding="utf-8") as f:
        return json.load(f)


def persisted_thread_ids():
    """Wszystkie wątki już zapisane w checkpointerze - m.in. te wczytane
    przez `gmail_app.py`, których nie ma w `data/sample_tickets.json`.
    Bez tego prawdziwe maile z Gmaila nigdy nie pojawiłyby się w tym UI."""
    conn = sqlite3.connect(CHECKPOINT_DB_PATH)
    try:
        cursor = conn.execute("SELECT DISTINCT thread_id FROM checkpoints")
        return [row[0] for row in cursor.fetchall()]
    finally:
        conn.close()


def run_or_resume(agent, ticket):
    """Uruchamia wątek zgłoszenia jeśli jeszcze nie istnieje, po czym zwraca
    jego bieżący snapshot stanu (ewentualnie zatrzymany na `interrupt()`)."""
    config = {"configurable": {"thread_id": ticket["ticket_id"]}}
    snapshot = agent.get_state(config)

    if not snapshot.values:
        agent.invoke({**ticket, "audit_log": []}, config)
        snapshot = agent.get_state(config)

    return snapshot


def is_pending_review(agent, thread_id):
    snapshot = agent.get_state({"configurable": {"thread_id": thread_id}})
    return bool(snapshot.tasks and snapshot.tasks[0].interrupts)


st.title("📬 Email Triage Agent — przegląd zgłoszeń")
st.caption(
    "Zgłoszenia niejednoznaczne lub wrażliwe zatrzymują się w `human_review` "
    "(LangGraph `interrupt()`) i czekają tutaj na akceptację człowieka."
)

agent = get_agent()

# Lista do wyboru: przykładowe zgłoszenia (jeszcze nieuruchomione da się
# odpalić wprost z tego UI) + wszystkie wątki już istniejące w checkpointerze,
# łącznie ze zgłoszeniami wczytanymi z prawdziwej skrzynki Gmail.
tickets_by_id = {t["ticket_id"]: t for t in load_sample_tickets()}
for thread_id in persisted_thread_ids():
    if thread_id not in tickets_by_id:
        snapshot = agent.get_state({"configurable": {"thread_id": thread_id}})
        if snapshot.values:
            tickets_by_id[thread_id] = {
                "ticket_id": thread_id,
                "sender": snapshot.values.get("sender", "?"),
                "subject": snapshot.values.get("subject", "(bez tematu)"),
                "body": snapshot.values.get("body", ""),
            }

pending_ids = {
    ticket_id for ticket_id in tickets_by_id if is_pending_review(agent, ticket_id)
}
tickets = sorted(tickets_by_id.values(), key=lambda t: t["ticket_id"] not in pending_ids)

ticket = st.selectbox(
    "Zgłoszenie",
    tickets,
    format_func=lambda t: (
        ("[czeka] " if t["ticket_id"] in pending_ids else "")
        + f"{t['ticket_id']} — {t['subject']}"
    ),
)

snapshot = run_or_resume(agent, ticket)
state = snapshot.values

st.subheader(f"{ticket['ticket_id']}: {ticket['subject']}")
st.write(f"**Od:** {ticket['sender']}")
st.write(f"**Treść:** {ticket['body']}")

if state.get("category"):
    st.write(
        f"**Kategoria:** `{state['category']}` "
        f"(pewność: {state.get('confidence')})"
    )

pending_interrupts = snapshot.tasks[0].interrupts if snapshot.tasks else ()

if pending_interrupts:
    payload = pending_interrupts[0].value
    st.warning("⏳ Zgłoszenie czeka na akceptację człowieka.")

    edited_reply = st.text_area(
        "Szkic odpowiedzi (można edytować przed wysyłką)",
        value=payload.get("draft_reply") or "",
        height=220,
    )

    config = {"configurable": {"thread_id": ticket["ticket_id"]}}
    col_approve, col_reject = st.columns(2)

    if col_approve.button("✅ Zaakceptuj i wyślij", type="primary"):
        agent.invoke(
            Command(resume={"approved": True, "edited_reply": edited_reply}),
            config,
        )
        st.rerun()

    if col_reject.button("❌ Odrzuć"):
        agent.invoke(Command(resume={"approved": False}), config)
        st.rerun()

elif state.get("status"):
    status_labels = {
        "sent": "✅ wysłano",
        "rejected": "🚫 odrzucono",
    }
    st.success(f"Status: {status_labels.get(state['status'], state['status'])}")
    st.write("**Odpowiedź:**")
    st.write(state.get("draft_reply", "(brak)"))

if state.get("audit_log"):
    with st.expander("Log audytowy"):
        for entry in state["audit_log"]:
            st.text(entry)
