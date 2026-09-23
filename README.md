# Email Triage Agent

Agent AI oparty o LangGraph do automatycznej klasyfikacji i odpowiadania na
zgłoszenia e-mail / tickety wsparcia klienta. Zgłoszenia o wysokiej pewności
klasyfikacji i niskim ryzyku są obsługiwane w pełni automatycznie. Zgłoszenia
niejednoznaczne lub wrażliwe (np. reklamacje, zwroty pieniędzy) trafiają do
człowieka do akceptacji (human-in-the-loop), a zgłoszenia rozpoznane jako
spam lub phishing są odrzucane bez generowania jakiejkolwiek odpowiedzi.

## Wymagania

- Python 3.10 lub nowszy.
- Klucz API Anthropic (Claude) - https://console.anthropic.com/.
- Opcjonalnie: plik OAuth client ID z Google Cloud Console, jeśli agent ma
  czytać wiadomości z prawdziwej skrzynki Gmail (patrz sekcja "Integracja
  z Gmail").

## Instalacja

```bash
git clone <adres repozytorium>
cd email-triage-agent

python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate

pip install -r requirements.txt

cp .env.example .env
```

Następnie otwórz plik `.env` i uzupełnij co najmniej `ANTHROPIC_API_KEY`.

Przy pierwszym uruchomieniu `python app.py` biblioteka `sentence-transformers`
pobierze lokalnie wagi modelu embeddingowego (`paraphrase-multilingual-MiniLM-L12-v2`,
ok. 470 MB) - jest to jednorazowe pobranie, dalsze uruchomienia korzystają
z lokalnej pamięci podręcznej i nie wymagają dostępu do sieci dla tego kroku.

## Konfiguracja (.env)

| Zmienna | Wymagana | Domyślna wartość | Opis |
|---|---|---|---|
| `ANTHROPIC_API_KEY` | tak | - | Klucz API Anthropic. |
| `CLASSIFY_MODEL_NAME` | nie | `claude-haiku-4-5` | Model używany do klasyfikacji zgłoszeń. |
| `GENERATE_MODEL_NAME` | nie | `claude-sonnet-5` | Model używany do generowania odpowiedzi. |
| `CONFIDENCE_THRESHOLD` | nie | `0.85` | Próg pewności klasyfikacji, poniżej którego zgłoszenie trafia do `human_review`. |
| `GMAIL_CREDENTIALS_PATH` | nie (tylko dla `gmail_app.py`) | `client_secret.json` | Ścieżka do pliku OAuth client ID z Google Cloud Console. |
| `GMAIL_TOKEN_PATH` | nie | `gmail_token.json` | Ścieżka do zapisanego tokenu dostępu (tworzony automatycznie po pierwszej autoryzacji). |
| `GMAIL_QUERY` | nie | `is:unread in:inbox` | Zapytanie Gmail określające, które wiadomości są pobierane. |
| `GMAIL_MAX_RESULTS` | nie | `10` | Maksymalna liczba wiadomości pobierana w jednym uruchomieniu. |
| `LANGSMITH_TRACING` | nie | (nieustawione) | `true`, aby włączyć śledzenie w LangSmith. |
| `LANGSMITH_API_KEY` | nie | (nieustawione) | Klucz API LangSmith (wymagany tylko przy włączonym śledzeniu). |
| `LANGSMITH_PROJECT` | nie | `email-triage-agent` | Nazwa projektu w LangSmith. |

Kategorie uznawane za wrażliwe (zawsze trafiają do `human_review`, niezależnie
od pewności klasyfikacji) są zdefiniowane w `src/config.py`
(`SENSITIVE_CATEGORIES`): `reklamacja`, `zwrot_pieniedzy`, `sprawa_prawna`,
`rezygnacja_z_uslugi`.

## Architektura

```
        classify         kategoria + poziom pewności (LLM)
           |
     spam  |  pozostałe kategorie
     -------------
     |            |
    skip       retrieve      RAG: szukanie kontekstu w bazie wiedzy
   (koniec)        |
                generate     szkic odpowiedzi (LLM + kontekst)
                    |
                  route      decyzja: auto-wysyłka czy eskalacja?
                    |
        niska pewność / kategoria wrażliwa   wysoka pewność, kategoria bezpieczna
                    |                                    |
              human_review                              send
        (interrupt, czeka na człowieka)          (wysyłka + log audytu)
                    |
          zaakceptowano -> send
          odrzucono -> koniec
```

Zgłoszenia klasyfikowane jako spam lub phishing kończą przetwarzanie od razu
po `classify` i nigdy nie docierają do węzłów `retrieve`/`generate`/`route`/`send` -
agent nie generuje dla nich żadnej odpowiedzi.

## Struktura projektu

```
email-triage-agent/
├── README.md
├── requirements.txt
├── .env.example
├── app.py                     # CLI - uruchomienie agenta na danych przykładowych
├── gmail_app.py                # uruchomienie agenta nad prawdziwą skrzynką Gmail
├── streamlit_app.py           # UI do przeglądu i akceptacji zgłoszeń w human_review
├── metrics.py                  # statystyki z historii przetworzonych zgłoszeń
├── data/
│   ├── knowledge_base.json    # baza wiedzy do RAG (źródło danych dla Chroma)
│   ├── sample_tickets.json    # przykładowe zgłoszenia testowe
│   ├── checkpoints.sqlite     # stan grafu (interrupt/resume), tworzony w runtime
│   └── chroma/                 # indeks wektorowy Chroma, tworzony w runtime
├── src/
│   ├── config.py              # konfiguracja (modele, progi, kategorie wrażliwe)
│   ├── state.py               # schemat stanu grafu (TypedDict)
│   ├── graph.py                # definicja grafu LangGraph
│   ├── checkpointer.py        # trwały checkpointer (sqlite) dla interrupt/resume
│   ├── cli.py                  # wspólna pętla CLI dla app.py i gmail_app.py
│   ├── nodes/
│   │   ├── classify.py        # węzeł: klasyfikacja zgłoszenia
│   │   ├── retrieve.py        # węzeł: RAG - pobranie kontekstu
│   │   ├── generate.py        # węzeł: generowanie odpowiedzi
│   │   ├── route.py           # węzeł: logika routingu (auto / eskalacja)
│   │   └── send.py            # węzły: wysyłka, human_review, pominięcie spamu
│   └── tools/
│       ├── knowledge_base.py  # retriever RAG oparty o bazę wektorową Chroma
│       └── gmail_client.py    # odczyt nieprzeczytanych wiadomości przez Gmail API (tylko odczyt)
└── tests/
    └── test_graph.py          # testy end-to-end na realnym API Anthropic
```

## Sposób użycia

### Uruchomienie na przykładowych danych

```bash
python app.py
```

Wczytuje zgłoszenia z `data/sample_tickets.json` i przepuszcza każde przez
graf agenta. Przykładowy przebieg dla zgłoszenia o niskim ryzyku:

```
============================================================
Zgłoszenie T-1001: Ile trwa dostawa?
============================================================
Kategoria: pytanie_produktowe (pewność: 0.97)
Decyzja: auto -> status: sent
Odpowiedź:
Dzień dobry, dostawa standardowa trwa 3-5 dni roboczych. W razie dalszych
pytań jesteśmy do dyspozycji.

Log audytowy:
  - [classify] kategoria=pytanie_produktowe pewność=0.97
  - [retrieve] znaleziono 3 fragmentów kontekstu
  - [generate] wygenerowano szkic odpowiedzi
  - [route] decyzja=auto (wysoka pewność, kategoria bezpieczna)
  - [send] wysłano odpowiedź do klient1@example.com
```

Przykładowy przebieg dla zgłoszenia wrażliwego (kategoria `reklamacja`),
które zatrzymuje się w `human_review`:

```
============================================================
Zgłoszenie T-1002: Uszkodzona przesyłka
============================================================
Kategoria: reklamacja (pewność: 0.95)
Decyzja: human_review -> status: pending_review
Szkic odpowiedzi:
Dzień dobry, przepraszamy za uszkodzenie przesyłki. Prosimy o zgłoszenie
reklamacji w ciągu 14 dni od otrzymania przesyłki wraz ze zdjęciem
uszkodzenia.

(zgłoszenie czeka na akceptację człowieka - uruchom
`streamlit run streamlit_app.py`, aby je zaakceptować lub odrzucić)
```

### Przegląd i akceptacja zgłoszeń (Streamlit)

```bash
streamlit run streamlit_app.py
```

Otwiera interfejs w przeglądarce (domyślnie `http://localhost:8501`). UI
współdzieli z `app.py` i `gmail_app.py` stan grafu zapisany w
`data/checkpoints.sqlite` (po `ticket_id` jako `thread_id`), więc każde
zgłoszenie zatrzymane w `human_review` - niezależnie od źródła - jest tam
widoczne.

Sposób działania:

1. Lista rozwijana "Zgłoszenie" zawiera przykładowe zgłoszenia oraz wszystkie
   zgłoszenia już zapisane w checkpointerze. Pozycje oczekujące na akceptację
   są oznaczone prefiksem `[czeka]` na początku etykiety.
2. Po wybraniu zgłoszenia oczekującego widoczna jest kategoria, pewność
   klasyfikacji oraz edytowalny szkic odpowiedzi.
3. Przycisk "Zaakceptuj i wyślij" wznawia graf z `Command(resume={"approved": True, ...})`
   i ustawia status `sent`; przycisk "Odrzuć" wznawia z `approved: False`
   i ustawia status `rejected`.

Uwaga: w obecnej wersji `send_node` jest zaślepką - ustawia status i zapisuje
wpis w logu audytowym, ale nie wysyła wiadomości przez żadne rzeczywiste API
pocztowe. Rzeczywista wysyłka przez Gmail API jest otwartym punktem
z sekcji "Kolejne kroki rozwoju".

### Integracja z Gmail

Zamiast danych z `data/sample_tickets.json` agent może czytać nieprzeczytane
wiadomości bezpośrednio ze skrzynki Gmail.

Konfiguracja (jednorazowa):

1. W [Google Cloud Console](https://console.cloud.google.com/) utwórz projekt
   (lub użyj istniejącego), włącz Gmail API i utwórz poświadczenia OAuth
   client ID typu "Desktop app".
2. Pobierz plik JSON z poświadczeniami i zapisz go w katalogu projektu.
3. W `.env` ustaw `GMAIL_CREDENTIALS_PATH` na ścieżkę do tego pliku.

Uruchomienie:

```bash
python gmail_app.py
```

Przy pierwszym uruchomieniu otwiera się przeglądarka z ekranem zgody Google.
Jeśli aplikacja OAuth jest w trybie testowym, może pojawić się ostrzeżenie
"Google nie zweryfikował tej aplikacji" - należy wybrać "Zaawansowane", a
następnie "Przejdź do (nazwa aplikacji)", żeby przejść dalej. Po zaakceptowaniu
uprawnień token zostaje zapisany w `GMAIL_TOKEN_PATH` (domyślnie
`gmail_token.json`) i jest automatycznie odświeżany przy kolejnych
uruchomieniach - ekran zgody nie pojawia się ponownie.

Zakres dostępu jest ograniczony do odczytu (`gmail.readonly`). Agent nie
wysyła wiadomości, nie oznacza ich jako przeczytane i nie modyfikuje w żaden
sposób konta. W praktyce oznacza to, że kolejne uruchomienie `gmail_app.py`
pobierze ponownie te same wiadomości, dopóki nie zostaną przeczytane ręcznie
w kliencie Gmail - każde takie uruchomienie ponownie klasyfikuje i generuje
odpowiedź dla tych samych wiadomości (koszt API naliczany od nowa).

### Metryki

```bash
python metrics.py
```

Czyta historię wszystkich dotychczasowych uruchomień `app.py` i
`gmail_app.py` z `data/checkpoints.sqlite` i wypisuje raport:

```
Przetworzonych zgłoszeń: 4
W pełni zautomatyzowanych (auto): 2 (50%)
Skierowanych do human_review: 1
Pominiętych jako spam/phishing (bez odpowiedzi): 1

Statusy:
  sent: 2 (50%)
  pending_review: 1 (25%)
  ignored: 1 (25%)

Kategorie:
  pytanie_produktowe: 2 (50%)
  reklamacja: 1 (25%)
  spam: 1 (25%)

Średnia pewność klasyfikacji: 0.93
Zakres pewności: 0.87 - 0.99
```

### Obserwowalność (LangSmith) - opcjonalnie

Bez dodatkowej konfiguracji agent działa normalnie i loguje tylko
`audit_log` (jedna linia na węzeł, widoczna w konsoli i w UI Streamlit).
Aby zobaczyć pełny trace każdego uruchomienia - każdy węzeł grafu i każde
wywołanie modelu Claude z treścią promptu, odpowiedzią, liczbą tokenów,
kosztem i czasem wykonania - należy założyć darmowe konto na
[smith.langchain.com](https://smith.langchain.com/) i dopisać do `.env`:

```
LANGSMITH_TRACING=true
LANGSMITH_API_KEY=<klucz z smith.langchain.com>
```

Śledzenie jest realizowane automatycznie przez biblioteki `langchain` i
`langgraph` na podstawie tych zmiennych środowiskowych - w kodzie tego
projektu nie ma żadnego wywołania API LangSmith. Bez ustawienia powyższych
zmiennych zachowanie agenta jest identyczne.

### Testy

```bash
pytest
```

Testy w `tests/test_graph.py` wykonują rzeczywiste wywołania API Anthropic
(bez mockowania) i wymagają ustawionego `ANTHROPIC_API_KEY`. Sprawdzają trzy
scenariusze: zgłoszenie o niskim ryzyku (auto), zgłoszenie wrażliwe
zatrzymujące się w `human_review` i możliwe do odrzucenia, oraz zgłoszenie
sklasyfikowane jako spam, które nigdy nie otrzymuje wygenerowanej odpowiedzi.

Uruchomienie jednego testu:

```bash
pytest tests/test_graph.py::test_low_risk_ticket_routes_correctly
```

## Bezpieczeństwo i human-in-the-loop

Agent nie wysyła odpowiedzi automatycznie, gdy:

- pewność klasyfikacji jest poniżej progu `CONFIDENCE_THRESHOLD`, lub
- kategoria zgłoszenia jest oznaczona jako wrażliwa (`SENSITIVE_CATEGORIES`
  w `src/config.py`: reklamacja, zwrot pieniędzy, sprawa prawna, rezygnacja
  z usługi).

W takich przypadkach graf zatrzymuje się w węźle `human_review`
(`interrupt()` z LangGraph) i czeka na decyzję człowieka podjętą w
`streamlit_app.py`.

Zgłoszenia sklasyfikowane jako spam lub phishing są traktowane odrębnie od
powyższego mechanizmu: agent w ogóle nie generuje ani nie wysyła żadnej
odpowiedzi (węzeł `skip`, pomijający `retrieve`, `generate`, `route` i
`send`). Odpowiedź na wiadomość phishingową potwierdzałaby atakującemu, że
skrzynka jest aktywna, więc taka wiadomość nie jest nawet kierowana do
przeglądu człowieka - zostaje jedynie wpis w `audit_log` ze statusem
`ignored`.

Odpowiedzi generowane w węźle `generate` są ograniczone promptem do faktów
zawartych dosłownie w kontekście pobranym z bazy wiedzy - model ma
instrukcję, aby nie dopowiadać warunków czy zasad, których nie ma w
kontekście, i wprost zaznaczać, gdy kontekst nie zawiera odpowiedzi na
pytanie klienta.

## Znane ograniczenia

- `send_node` nie wysyła rzeczywistych wiadomości e-mail - jest to zaślepka
  ustawiająca status i wpis w logu audytowym. Rzeczywista integracja z Gmail
  API (wysyłka) nie jest jeszcze zrealizowana.
- `gmail_app.py` nie oznacza przetworzonych wiadomości jako przeczytane, więc
  powtórne uruchomienie ponownie przetwarza (i ponownie kosztuje wywołaniami
  API) te same nieprzeczytane wiadomości, dopóki nie zostaną przeczytane
  ręcznie.
- `metrics.py` nie mierzy jeszcze czasu obsługi zgłoszeń - checkpointer nie
  zapisuje znaczników czasu per węzeł.

## Kolejne kroki rozwoju

1. Rzeczywista wysyłka odpowiedzi przez Gmail API (`send_node`) - obecnie
   zaślepka; integracja z odczytem (`gmail_app.py`) jest już zrealizowana
   i ograniczona do zakresu `gmail.readonly`.
2. Lokalne oznaczanie już przetworzonych wiadomości Gmail, aby uniknąć
   ponownego przetwarzania tych samych nieprzeczytanych wiadomości przy
   każdym uruchomieniu `gmail_app.py`.
3. Pomiar czasu obsługi zgłoszenia (znaczniki czasu per węzeł w stanie grafu)
   jako uzupełnienie raportu w `metrics.py`.

Zrealizowane dotychczas: RAG na bazie wektorowej Chroma z lokalnymi
embeddingami wielojęzycznymi (`src/tools/knowledge_base.py`), UI w Streamlit
do przeglądu i akceptacji zgłoszeń w `human_review` (`streamlit_app.py`),
opcjonalna integracja z LangSmith do obserwowalności, oraz raport metryk
(`metrics.py`).
# email_triage-agent
