import base64
import os.path
from typing import List

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

from src.config import (
    GMAIL_CREDENTIALS_PATH,
    GMAIL_MAX_RESULTS,
    GMAIL_QUERY,
    GMAIL_TOKEN_PATH,
)

_SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]


def _get_credentials() -> Credentials:
    """Zwraca poświadczenia OAuth, autoryzując w przeglądarce przy pierwszym
    uruchomieniu i cache'ując token w GMAIL_TOKEN_PATH na kolejne razy."""
    creds = None
    if os.path.exists(GMAIL_TOKEN_PATH):
        creds = Credentials.from_authorized_user_file(GMAIL_TOKEN_PATH, _SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                GMAIL_CREDENTIALS_PATH, _SCOPES
            )
            creds = flow.run_local_server(port=0)
        with open(GMAIL_TOKEN_PATH, "w", encoding="utf-8") as f:
            f.write(creds.to_json())

    return creds


def _decode_body(payload: dict) -> str:
    """Wyciąga tekstową treść (text/plain) z zagnieżdżonego payloadu Gmail API."""
    if payload.get("mimeType") == "text/plain" and payload.get("body", {}).get("data"):
        return base64.urlsafe_b64decode(payload["body"]["data"]).decode(
            "utf-8", errors="replace"
        )

    for part in payload.get("parts", []):
        text = _decode_body(part)
        if text:
            return text

    return ""


def fetch_unread_tickets(max_results: int = None) -> List[dict]:
    """Pobiera nieprzeczytane wiadomości pasujące do GMAIL_QUERY jako listę
    zgłoszeń w formacie zgodnym z `TicketState` (ticket_id/sender/subject/body).

    Nie modyfikuje wiadomości (nie oznacza jako przeczytane) - to celowe,
    zgodne z ograniczeniem do samego odczytu.
    """
    service = build("gmail", "v1", credentials=_get_credentials())

    response = (
        service.users()
        .messages()
        .list(userId="me", q=GMAIL_QUERY, maxResults=max_results or GMAIL_MAX_RESULTS)
        .execute()
    )

    tickets = []
    for ref in response.get("messages", []):
        message = (
            service.users()
            .messages()
            .get(userId="me", id=ref["id"], format="full")
            .execute()
        )
        headers = {h["name"]: h["value"] for h in message["payload"].get("headers", [])}
        body = _decode_body(message["payload"]) or message.get("snippet", "")

        tickets.append(
            {
                "ticket_id": message["id"],
                "sender": headers.get("From", "nieznany"),
                "subject": headers.get("Subject", "(brak tematu)"),
                "body": body.strip(),
            }
        )

    return tickets
