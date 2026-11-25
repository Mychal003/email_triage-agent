from langchain_anthropic import ChatAnthropic

from src.config import GENERATE_MODEL_NAME
from src.state import TicketState

# Sonnet 5 (jak cała bieżąca generacja modeli) nie przyjmuje już parametrów
# samplingu (temperature/top_p/top_k) - zwraca 400 "deprecated for this model".
_llm = ChatAnthropic(model=GENERATE_MODEL_NAME)

_GENERATE_PROMPT = """Jesteś asystentem obsługi klienta. Napisz uprzejmą,
konkretną odpowiedź na poniższe zgłoszenie, wykorzystując WYŁĄCZNIE fakty
podane w kontekście z bazy wiedzy poniżej.

Zasady:
- Nie dodawaj żadnych warunków, zasad, terminów ani szczegółów, których nie
  ma dosłownie w kontekście - nawet jeśli wydają się typowe, prawdopodobne
  albo "zwykle tak jest" w tego typu sklepach. Kontekst to jedyne źródło
  prawdy o zasadach firmy, nie Twoja ogólna wiedza.
- Jeśli kontekst nie zawiera odpowiedzi na część pytania klienta, napisz to
  wprost (np. że tę kwestię trzeba zweryfikować z obsługą klienta) - nie
  zgaduj i nie wymyślaj brakujących szczegółów.

Kategoria zgłoszenia: {category}
Temat: {subject}
Treść zgłoszenia: {body}

Kontekst z bazy wiedzy:
{context}

Napisz tylko treść odpowiedzi e-mail, bez dodatkowych komentarzy.
"""


def _extract_text(content) -> str:
    """`response.content` bywa listą bloków (np. `thinking` + `text`), gdy
    model myśli - Sonnet 5 domyślnie włącza adaptive thinking, jeśli nie
    podamy `thinking` explicite. Interesuje nas tylko treść odpowiedzi."""
    if isinstance(content, str):
        return content
    return "".join(
        block.get("text", "")
        for block in content
        if isinstance(block, dict) and block.get("type") == "text"
    )

#Przyjmuje aktualny stan grafu i zwraca jego zaktualizowaną wersję.
def generate_node(state: TicketState) -> TicketState:
    context = "\n---\n".join(state.get("retrieved_context", [])) or "(brak)"

    prompt = _GENERATE_PROMPT.format(
        category=state.get("category", "inne"),
        subject=state["subject"],
        body=state["body"],
        context=context,
    )
    response = _llm.invoke(prompt)

    audit_log = state.get("audit_log", [])
    audit_log.append("[generate] wygenerowano szkic odpowiedzi")

    return {
        **state,
        "draft_reply": _extract_text(response.content),
        "audit_log": audit_log,
    }
