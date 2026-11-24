"""Węzeł: klasyfikacja zgłoszenia (kategoria + pewność)."""

import json

from langchain_anthropic import ChatAnthropic

from src.config import CATEGORIES, CLASSIFY_MODEL_NAME
from src.state import TicketState

_llm = ChatAnthropic(model=CLASSIFY_MODEL_NAME, temperature=0)

_CLASSIFY_PROMPT = """Sklasyfikuj poniższe zgłoszenie klienta.

Temat: {subject}
Treść: {body}

Odpowiedz WYŁĄCZNIE w formacie JSON (bez żadnego innego tekstu):
{{
  "category": "jedna z: {categories}",
  "confidence": liczba od 0.0 do 1.0
}}
"""

# Kategoria/pewność ustawiana, gdy odpowiedzi modelu nie da się zinterpretować.
# Pewność 0.0 jest zawsze poniżej CONFIDENCE_THRESHOLD, więc takie zgłoszenie
# na pewno trafi do human_review - w razie wątpliwości decyduje człowiek.
_FALLBACK_CATEGORY = "inne"
_FALLBACK_CONFIDENCE = 0.0


def _parse_json_response(content: str) -> dict:
    """Modele czasem owijają odpowiedź w markdown code fence (```json ... ```)
    albo dopisują tekst przed/po JSON-ie mimo instrukcji "tylko JSON" -
    w szczególności zaobserwowano to na Haiku. Bierzemy fragment od
    pierwszego `{` do ostatniego `}`. Rzuca ValueError, jeśli to nie jest
    obiekt JSON."""
    start = content.find("{")
    end = content.rfind("}")
    if start == -1 or end < start:
        raise ValueError("brak obiektu JSON w odpowiedzi modelu")

    result = json.loads(content[start : end + 1])
    if not isinstance(result, dict):
        raise ValueError("odpowiedź modelu nie jest obiektem JSON")
    return result


def _normalize_category(raw) -> str | None:
    """Sprowadza kategorię do postaci z CATEGORIES ("Zwrot pieniedzy" ->
    "zwrot_pieniedzy"). Zwraca None dla kategorii spoza listy - bez tego
    np. "Reklamacja" z wielkiej litery nie trafiłaby do SENSITIVE_CATEGORIES
    i mogła zostać wysłana automatycznie."""
    if not isinstance(raw, str):
        return None
    category = raw.strip().lower().replace(" ", "_").replace("-", "_")
    return category if category in CATEGORIES else None


def _normalize_confidence(raw) -> float:
    """Pewność nie-liczbowa (np. "wysoka") -> 0.0, poza zakresem -> przycięta do 0-1."""
    if isinstance(raw, bool):
        return _FALLBACK_CONFIDENCE
    try:
        confidence = float(raw)
    except (TypeError, ValueError):
        return _FALLBACK_CONFIDENCE
    if confidence != confidence:  # NaN
        return _FALLBACK_CONFIDENCE
    return min(max(confidence, 0.0), 1.0)


def classify_node(state: TicketState) -> TicketState:
    prompt = _CLASSIFY_PROMPT.format(
        subject=state["subject"],
        body=state["body"],
        categories=", ".join(CATEGORIES),
    )
    response = _llm.invoke(prompt)

    audit_log = state.get("audit_log", [])

    try:
        result = _parse_json_response(response.content)
    except (TypeError, ValueError) as e:
        # json.JSONDecodeError dziedziczy po ValueError
        audit_log.append(
            f"[classify] błąd parsowania odpowiedzi modelu ({e}) "
            f"-> eskalacja do człowieka"
        )
        return {
            **state,
            "category": _FALLBACK_CATEGORY,
            "confidence": _FALLBACK_CONFIDENCE,
            "audit_log": audit_log,
        }

    category = _normalize_category(result.get("category"))
    confidence = _normalize_confidence(result.get("confidence"))

    if category is None:
        audit_log.append(
            f"[classify] nieznana kategoria od modelu: {result.get('category')!r} "
            f"-> eskalacja do człowieka"
        )
        category, confidence = _FALLBACK_CATEGORY, _FALLBACK_CONFIDENCE

    audit_log.append(f"[classify] kategoria={category} pewność={confidence}")

    return {
        **state,
        "category": category,
        "confidence": confidence,
        "audit_log": audit_log,
    }


def classify_condition(state: TicketState) -> str:
    """Spam/phishing nigdy nie dostaje odpowiedzi - pomija resztę grafu
    (retrieve/generate/route/send), żeby nie marnować wywołań LLM i, co
    ważniejsze, nigdy nie odpowiadać na wiadomość phishingową (odpowiedź
    tylko potwierdza atakującemu, że skrzynka jest aktywna)."""
    return "spam" if state.get("category") == "spam" else "process"
