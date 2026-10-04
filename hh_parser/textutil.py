"""Turning a vacancy description into plain text and its parts."""

from __future__ import annotations

import html
import re
from dataclasses import dataclass

_BREAK_TAGS = re.compile(r"<\s*(br\s*/?|/p|/div|/ul|/ol|/h[1-6]|/tr)\s*>", re.IGNORECASE)
_LIST_ITEM = re.compile(r"<\s*li[^>]*>", re.IGNORECASE)
_ANY_TAG = re.compile(r"<[^>]*>")
_SPACES = re.compile(r"[ \t ]+")
_MANY_NEWLINES = re.compile(r"\n{3,}")


def html_to_text(src: str) -> str:
    """Convert the HTML fragments hh uses for descriptions into plain text:
    block ends become line breaks, list items become "- " bullets, other tags
    are dropped and entities are decoded. For display and keyword analysis,
    not for rendering untrusted HTML."""
    s = _BREAK_TAGS.sub("\n", src)
    s = _LIST_ITEM.sub("\n- ", s)
    s = _ANY_TAG.sub("", s)
    s = html.unescape(s)
    s = "\n".join(_SPACES.sub(" ", line).strip() for line in s.split("\n"))
    s = _MANY_NEWLINES.sub("\n\n", s)
    return s.strip()


RESPONSIBILITIES = "responsibilities"
REQUIREMENTS = "requirements"
NICE_TO_HAVE = "nice_to_have"
CONDITIONS = "conditions"

# Employers write headings freely, so this is a heuristic: a short line is a
# heading when it starts with one of these phrases.
_HEADINGS = [
    ("обязанности", RESPONSIBILITIES),
    ("задачи", RESPONSIBILITIES),
    ("чем предстоит заниматься", RESPONSIBILITIES),
    ("чем вам предстоит заниматься", RESPONSIBILITIES),
    ("что нужно делать", RESPONSIBILITIES),
    ("что предстоит делать", RESPONSIBILITIES),
    ("responsibilities", RESPONSIBILITIES),
    ("what you will do", RESPONSIBILITIES),
    ("требования", REQUIREMENTS),
    ("мы ожидаем", REQUIREMENTS),
    ("что мы ожидаем", REQUIREMENTS),
    ("ожидания от кандидата", REQUIREMENTS),
    ("от вас", REQUIREMENTS),
    ("что нужно знать", REQUIREMENTS),
    ("requirements", REQUIREMENTS),
    ("what we expect", REQUIREMENTS),
    ("must have", REQUIREMENTS),
    ("будет плюсом", NICE_TO_HAVE),
    ("будет преимуществом", NICE_TO_HAVE),
    ("приветствуется", NICE_TO_HAVE),
    ("nice to have", NICE_TO_HAVE),
    ("условия", CONDITIONS),
    ("мы предлагаем", CONDITIONS),
    ("что мы предлагаем", CONDITIONS),
    ("что предлагаем", CONDITIONS),
    ("we offer", CONDITIONS),
    ("conditions", CONDITIONS),
]

# Keeps ordinary sentences from being mistaken for headings.
_MAX_HEADING_LEN = 60


@dataclass
class Section:
    kind: str
    title: str
    body: str


def _heading_kind(line: str) -> str:
    low = line.strip().lower().lstrip("-*• ").rstrip(": ")
    if not low or len(low) > _MAX_HEADING_LEN:
        return ""
    for prefix, kind in _HEADINGS:
        if low.startswith(prefix):
            return kind
    return ""


def sections(text: str) -> list[Section]:
    """Split plain text (see html_to_text) into the known parts of a vacancy
    description. Text before the first heading and under unknown headings is
    not returned; callers should keep the full text as well."""
    out: list[Section] = []
    cur: Section | None = None

    def flush() -> None:
        nonlocal cur
        if cur is not None:
            cur.body = cur.body.strip()
            if cur.body:
                out.append(cur)
            cur = None

    for line in text.split("\n"):
        kind = _heading_kind(line)
        if kind:
            flush()
            cur = Section(kind, line.strip().rstrip(": "), "")
            continue
        if cur is None:
            continue
        t = line.strip()
        # A short line ending with ":" that is not a known heading starts an
        # unknown section, which ends the current one.
        if t.endswith(":") and len(t) <= _MAX_HEADING_LEN and not t.startswith("-"):
            flush()
            continue
        cur.body += line + "\n"
    flush()
    return out
