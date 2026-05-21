from __future__ import annotations

from collections.abc import Callable
from typing import Any


STOPWORDS_AND_PRONOUNS = {
    "a",
    "add",
    "additional tips",
    "all",
    "an",
    "and",
    "are",
    "as",
    "at",
    "avoid",
    "but",
    "can",
    "chat time",
    "check",
    "choose",
    "congratulations",
    "create",
    "enjoy",
    "focus",
    "for",
    "from",
    "good",
    "he",
    "her",
    "hers",
    "here",
    "him",
    "his",
    "how",
    "however",
    "i",
    "in",
    "it",
    "its",
    "make",
    "many",
    "miss",
    "mix",
    "monsieur",
    "mr",
    "mrs",
    "ms",
    "of",
    "on",
    "one",
    "or",
    "our",
    "remember",
    "she",
    "some",
    "start",
    "that",
    "the",
    "their",
    "them",
    "there",
    "these",
    "they",
    "then",
    "this",
    "tips",
    "to",
    "try",
    "use",
    "we",
    "what",
    "when",
    "where",
    "which",
    "who",
    "why",
    "with",
    "you",
    "your",
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
