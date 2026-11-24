"""Testy jednostkowe parsowania/normalizacji klasyfikacji i routingu - bez
wywołań LLM (import classify.py nadal wymaga ustawionego ANTHROPIC_API_KEY,
bo klient ChatAnthropic tworzony jest przy imporcie)."""

from types import SimpleNamespace

import pytest

from src.nodes import classify
from src.nodes.classify import (
    _normalize_category,
    _normalize_confidence,
    _parse_json_response,
)
from src.nodes.route import route_node


@pytest.mark.parametrize(
    "content",
    [
        '{"category": "reklamacja", "confidence": 0.9}',
        '```json\n{"category": "reklamacja", "confidence": 0.9}\n```',
        'Oto wynik:\n{"category": "reklamacja", "confidence": 0.9}\nPozdrawiam',
    ],
)
def test_parse_json_response_accepts_wrapped_json(content):
    assert _parse_json_response(content) == {"category": "reklamacja", "confidence": 0.9}


@pytest.mark.parametrize("content", ["", "nie wiem", "{zepsuty json", "[1, 2]"])
def test_parse_json_response_rejects_garbage(content):
    with pytest.raises(ValueError):
        _parse_json_response(content)


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("reklamacja", "reklamacja"),
        ("Reklamacja", "reklamacja"),
        ("  Zwrot pieniedzy ", "zwrot_pieniedzy"),
        ("sprawa-prawna", "sprawa_prawna"),
        ("SPAM", "spam"),
        ("zażalenie", None),
        (None, None),
        (3, None),
    ],
)
def test_normalize_category(raw, expected):
    assert _normalize_category(raw) == expected


@pytest.mark.parametrize(
    "raw, expected",
    [
        (0.9, 0.9),
        ("0.7", 0.7),
        (1.7, 1.0),
        (-0.2, 0.0),
        ("wysoka", 0.0),
        (None, 0.0),
        (True, 0.0),
        (float("nan"), 0.0),
    ],
)
def test_normalize_confidence(raw, expected):
    assert _normalize_confidence(raw) == expected


def _ticket():
    return {
        "ticket_id": "T-UNIT",
        "sender": "test@example.com",
        "subject": "Temat",
        "body": "Treść",
        "audit_log": [],
    }


def _fake_llm(monkeypatch, content):
    monkeypatch.setattr(
        classify, "_llm", SimpleNamespace(invoke=lambda prompt: SimpleNamespace(content=content))
    )


def test_classify_node_falls_back_on_unparseable_response(monkeypatch):
    _fake_llm(monkeypatch, "Przepraszam, nie potrafię tego sklasyfikować.")

    result = classify.classify_node(_ticket())

    assert result["category"] == "inne"
    assert result["confidence"] == 0.0
    assert any("błąd parsowania" in entry for entry in result["audit_log"])
    assert route_node(result)["route_decision"] == "human_review"


def test_classify_node_escalates_unknown_category(monkeypatch):
    _fake_llm(monkeypatch, '{"category": "zażalenie", "confidence": 0.99}')

    result = classify.classify_node(_ticket())

    assert result["category"] == "inne"
    assert result["confidence"] == 0.0
    assert any("nieznana kategoria" in entry for entry in result["audit_log"])
    assert route_node(result)["route_decision"] == "human_review"


def test_classify_node_normalizes_sensitive_category(monkeypatch):
    _fake_llm(monkeypatch, '{"category": "Reklamacja", "confidence": 0.99}')

    result = classify.classify_node(_ticket())

    assert result["category"] == "reklamacja"
    assert route_node(result)["route_decision"] == "human_review"


def test_route_node_sends_unknown_category_to_human_review():
    state = {**_ticket(), "category": "cos_dziwnego", "confidence": 0.99}

    result = route_node(state)

    assert result["route_decision"] == "human_review"
    assert "nieznana kategoria" in result["audit_log"][-1]


def test_route_node_auto_for_safe_confident_ticket():
    state = {**_ticket(), "category": "pytanie_produktowe", "confidence": 0.95}

    assert route_node(state)["route_decision"] == "auto"
