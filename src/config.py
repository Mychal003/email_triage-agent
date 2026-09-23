"""Konfiguracja agenta: model, progi decyzyjne, kategorie wrażliwe."""

import os
from dotenv import load_dotenv

load_dotenv()

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")

# Klasyfikacja to proste, zamknięte zadanie (kategoria + pewność w JSON) -
# tani model wystarcza. Generowanie odpowiedzi wymaga lepszej jakości języka,
# więc zostaje na droższym modelu. Osobne zmienne env -> łatwa optymalizacja
# kosztów bez ruszania kodu węzłów.
CLASSIFY_MODEL_NAME = os.getenv("CLASSIFY_MODEL_NAME", "claude-haiku-4-5")
GENERATE_MODEL_NAME = os.getenv("GENERATE_MODEL_NAME", "claude-sonnet-5")

# Poniżej tego progu pewności klasyfikacji -> eskalacja do człowieka
CONFIDENCE_THRESHOLD = float(os.getenv("CONFIDENCE_THRESHOLD", "0.85"))

# Kategorie, które ZAWSZE trafiają do przeglądu człowieka,
# niezależnie od pewności klasyfikacji (bo są wysokiego ryzyka)
SENSITIVE_CATEGORIES = {
    "reklamacja",
    "zwrot_pieniedzy",
    "sprawa_prawna",
    "rezygnacja_z_uslugi",
}

KNOWLEDGE_BASE_PATH = "data/knowledge_base.json"

# Katalog trwałej bazy wektorowej Chroma (indeks budowany z KNOWLEDGE_BASE_PATH)
CHROMA_PERSIST_DIR = "data/chroma"

# Gmail API - źródło zgłoszeń zamiast data/sample_tickets.json. Zakres celowo
# tylko do odczytu (gmail.readonly, src/tools/gmail_client.py) - agent nie
# wysyła ani nie modyfikuje niczego na koncie. GMAIL_CREDENTIALS_PATH to plik
# OAuth client ID pobrany z Google Cloud Console (typ "Desktop app"),
# GMAIL_TOKEN_PATH to token dostępu zapisywany po pierwszej autoryzacji
# w przeglądarce - oba gitignored, bo to poświadczenia.
GMAIL_CREDENTIALS_PATH = os.getenv("GMAIL_CREDENTIALS_PATH", "client_secret.json")
GMAIL_TOKEN_PATH = os.getenv("GMAIL_TOKEN_PATH", "gmail_token.json")
GMAIL_QUERY = os.getenv("GMAIL_QUERY", "is:unread in:inbox")
GMAIL_MAX_RESULTS = int(os.getenv("GMAIL_MAX_RESULTS", "10"))

# LangSmith (opcjonalne, obserwowalność) - jeśli w .env ustawisz LANGSMITH_TRACING=true
# i LANGSMITH_API_KEY (konto na smith.langchain.com), langchain/langgraph same
# zaczną wysyłać tam pełny trace każdego uruchomienia grafu: każdy węzeł +
# każde wywołanie Claude (prompt, odpowiedź, tokeny, koszt, czas). To automatyczne
# przechwytywanie w bibliotece, nie kod tego projektu - stąd brak wywołań LangSmith
# gdziekolwiek indziej. Bez tych zmiennych agent działa dokładnie tak samo, zero
# zmian w zachowaniu - tylko nazwa projektu ma sensowny domyślny fallback.
os.environ.setdefault("LANGSMITH_PROJECT", "email-triage-agent")
