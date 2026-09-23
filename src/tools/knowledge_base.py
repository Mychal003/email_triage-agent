"""Retriever nad bazą wiedzy oparty o wektorową bazę Chroma (embeddingi
semantyczne) zamiast prostego nakładania się słów kluczowych - patrz
README "Kolejne kroki rozwoju".
"""

import json
from pathlib import Path
from typing import List

import chromadb
from chromadb.utils import embedding_functions

from src.config import CHROMA_PERSIST_DIR, KNOWLEDGE_BASE_PATH

_COLLECTION_NAME = "knowledge_base"

# Domyślny embedding Chroma (all-MiniLM-L6-v2) jest trenowany na angielskim i
# w testach dawał słabe dopasowania dla polskich zapytań (np. "Kiedy dotrze
# moje zamówienie?" nie trafiał na wpis o czasie dostawy). Ten model wspiera
# polski i działa lokalnie, bez klucza API - tylko jednorazowe pobranie wag.
_EMBEDDING_MODEL = "paraphrase-multilingual-MiniLM-L12-v2"

_client = chromadb.PersistentClient(path=CHROMA_PERSIST_DIR)
_collection = _client.get_or_create_collection(
    _COLLECTION_NAME,
    embedding_function=embedding_functions.SentenceTransformerEmbeddingFunction(
        model_name=_EMBEDDING_MODEL
    ),
)


def _load_knowledge_base() -> List[dict]:
    path = Path(KNOWLEDGE_BASE_PATH)
    if not path.exists():
        return []
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _sync_collection() -> None:
    """Ładuje `data/knowledge_base.json` do kolekcji Chroma.

    `upsert` po `id` wpisu jest idempotentny - ponowny import z tą samą
    treścią nie przelicza embeddingów, a zmiana treści wpisu nadpisuje jego
    wektor. Wykonywane raz przy starcie procesu (import modułu), tak jak
    inicjalizacja klientów LLM w innych węzłach.
    """
    kb = _load_knowledge_base()
    if not kb:
        return
    _collection.upsert(
        ids=[entry["id"] for entry in kb],
        documents=[entry["text"] for entry in kb],
    )


_sync_collection()


def retrieve_context(query: str, top_k: int = 3) -> List[str]:
    """Zwraca najbardziej semantycznie pasujące fragmenty bazy wiedzy dla zapytania."""
    if _collection.count() == 0:
        return []

    result = _collection.query(
        query_texts=[query], n_results=min(top_k, _collection.count())
    )
    return result["documents"][0]
