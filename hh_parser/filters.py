"""Excluding vacancies by words in the title."""

from __future__ import annotations

import re
from typing import Callable


def _normalize(text: str) -> str:
    return text.lower().replace("ё", "е")


def parse_words(value: str) -> list[str]:
    """Split a comma-separated list ("junior, джун, team lead") into normalized words."""
    return [w for w in (_normalize(part).strip() for part in value.split(",")) if w]


def title_excluder(words: list[str]) -> Callable[[str], bool]:
    """Return a function telling whether a title contains any of the words.

    A word matches at the start of a word of the title, so "джун" matches
    "Джуниор" and "джуна" but "head" does not match "ahead". Case and the
    letters ё/е do not matter. A phrase such as "team lead" matches as a whole."""
    if not words:
        return lambda _title: False
    pattern = re.compile(r"(?<!\w)(?:" + "|".join(re.escape(w) for w in words) + ")")
    return lambda title: pattern.search(_normalize(title)) is not None
