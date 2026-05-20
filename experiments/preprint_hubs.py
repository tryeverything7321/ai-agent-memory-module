from __future__ import annotations

from collections.abc import Callable
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
    "there",
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


def select_actionable_hubs(
    hubs: list[dict[str, Any]],
    top_k: int,
    has_trigger_fact: Callable[[str], bool],
) -> list[dict[str, Any]]:
    selected = []
    for hub in hubs:
        entity = str(hub.get("entity", ""))
        if not is_named_entity_like(entity):
            continue
        if not has_trigger_fact(entity):
            continue
        selected.append(hub)
        if len(selected) >= top_k:
            break
    return selected
