from __future__ import annotations

from typing import Any


STOPWORDS_AND_PRONOUNS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "but",
    "for",
    "from",
    "he",
    "her",
    "hers",
    "him",
    "his",
    "i",
    "in",
    "it",
    "its",
    "of",
    "on",
    "or",
    "our",
    "she",
    "that",
    "the",
    "their",
    "them",
    "they",
    "this",
    "to",
    "we",
    "who",
    "with",
    "you",
}


def is_named_entity_like(entity: str) -> bool:
    normalized = " ".join(entity.strip().split())
    if not normalized:
        return False
    if normalized.lower() in STOPWORDS_AND_PRONOUNS:
        return False
    if len(normalized) <= 2:
        return False
    tokens = normalized.replace("-", " ").split()
    return any(token[:1].isupper() for token in tokens)


def filter_named_entity_hubs(
    hubs: list[dict[str, Any]], top_k: int
) -> list[dict[str, Any]]:
    filtered = [
        hub for hub in hubs
        if is_named_entity_like(str(hub.get("entity", "")))
    ]
    return filtered[:top_k]
