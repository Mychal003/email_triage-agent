"""Węzeł: klasyfikacja zgłoszenia (kategoria + pewność)."""

import json

from langchain_anthropic import ChatAnthropic

from src.config import CLASSIFY_MODEL_NAME
from src.state import TicketState

_llm = ChatAnthropic(model=CLASSIFY_MODEL_NAME, temperature=0)

_CLASSIFY_PROMPT = """Sklasyfikuj poniższe zgłoszenie klienta.

Temat: {subject}
Treść: {body}

Odpowiedz WYŁĄCZNIE w formacie JSON (bez żadnego innego tekstu):
{{
  "category": "jedna z: pytanie_produktowe, reklamacja, zwrot_pieniedzy, \
sprawa_prawna, rezygnacja_z_uslugi, spam, inne",
  "confidence": liczba od 0.0 do 1.0
}}
"""


def _parse_json_response(content: str) -> dict:
    """Modele czasem owijają odpowiedź w markdown code fence (```json ... ```)
    mimo instrukcji "tylko JSON" - w szczególności zaobserwowano to na Haiku."""
    content = content.strip()
    if content.startswith("```"):
        content = content.strip("`").removeprefix("json").strip()
    return json.loads(content)


def classify_node(state: TicketState) -> TicketState:
    prompt = _CLASSIFY_PROMPT.format(subject=state["subject"], body=state["body"])
    response = _llm.invoke(prompt)

    result = _parse_json_response(response.content)

    audit_log = state.get("audit_log", [])
    audit_log.append(
        f"[classify] kategoria={result['category']} pewność={result['confidence']}"
    )

    return {
        **state,
        "category": result["category"],
        "confidence": float(result["confidence"]),
        "audit_log": audit_log,
    }


def classify_condition(state: TicketState) -> str:
    """Spam/phishing nigdy nie dostaje odpowiedzi - pomija resztę grafu
    (retrieve/generate/route/send), żeby nie marnować wywołań LLM i, co
    ważniejsze, nigdy nie odpowiadać na wiadomość phishingową (odpowiedź
    tylko potwierdza atakującemu, że skrzynka jest aktywna)."""
    return "spam" if state.get("category") == "spam" else "process"
