"""Markdown notes for Obsidian.

Each vacancy is one note with YAML properties (shown by Obsidian as Properties,
queryable with Dataview) and the description as text. A note is named
"<title> (<id>).md" and the id in the name is what makes writing idempotent: a
vacancy whose id is already in the folder is never written again, so notes you
edited (status, comments) are never overwritten.
"""

from __future__ import annotations

import datetime as dt
import json
import re
from pathlib import Path
from typing import Any, Optional

from hh_parser.view import salary_text

_ID_IN_NAME = re.compile(r"\((\d+)\)\.md$")
_MAX_TITLE = 80
# Characters that file systems or Obsidian do not accept in note names
# (# ^ [ ] break wiki links).
_UNSAFE_IN_NAME = re.compile(r'[/\\:*?"<>|#^\[\]]')


class Vault:
    def __init__(self, directory: str | Path) -> None:
        self.dir = Path(directory).expanduser()
        self.dir.mkdir(parents=True, exist_ok=True)

    def known_ids(self) -> set[str]:
        """Ids of the vacancies already present in the folder."""
        ids = set()
        for entry in self.dir.iterdir():
            m = _ID_IN_NAME.search(entry.name)
            if entry.is_file() and m:
                ids.add(m.group(1))
        return ids

    def save(self, view: dict[str, Any], now: Optional[dt.datetime] = None) -> bool:
        """Write the note unless one with the same id exists. Returns whether a note was created."""
        if not view.get("id"):
            raise ValueError("vacancy without id")
        if view["id"] in self.known_ids():
            return False
        path = self.dir / file_name(view)
        try:
            # "x" = never overwrite, even if the note appeared since the check.
            with open(path, "x", encoding="utf-8") as f:
                f.write(render(view, now))
        except FileExistsError:
            return False
        return True


def file_name(view: dict[str, Any]) -> str:
    """"<title> (<id>).md" with the title made safe for a file name."""
    title = " ".join(_UNSAFE_IN_NAME.sub(" ", view.get("title", "")).split())
    title = title[:_MAX_TITLE].strip() or "vacancy"
    return f"{title} ({view['id']}).md"


def _j(value: Any) -> str:
    """JSON is also a valid YAML scalar or flow sequence."""
    return json.dumps(value, ensure_ascii=False)


def render(view: dict[str, Any], now: Optional[dt.datetime] = None) -> str:
    now = now or dt.datetime.now(dt.timezone.utc)
    salary = view.get("salary") or {}
    props: list[tuple[str, str]] = [
        ("id", _j(view["id"])),
        ("source", _j("hh")),
        ("url", _j(view.get("url", ""))),
        ("employer", _j(view.get("employer", ""))),
        ("area", _j(view.get("area", ""))),
    ]
    if salary.get("from") is not None:
        props.append(("salary_from", str(salary["from"])))
    if salary.get("to") is not None:
        props.append(("salary_to", str(salary["to"])))
    if salary.get("currency"):
        props.append(("salary_currency", _j(salary["currency"])))
    props += [
        ("experience", _j(view.get("experience", ""))),
        ("employment", _j(view.get("employment", ""))),
        ("schedule", _j(view.get("schedule", ""))),
    ]
    published = (view.get("published_at") or "")[:10]
    if len(published) == 10:
        props.append(("published", published))
    props += [
        ("key_skills", _j(view.get("key_skills", []))),
        ("roles", _j(view.get("professional_roles", []))),
        ("letter_required", _bool(view.get("response_letter_required"))),
        ("has_test", _bool(view.get("has_test"))),
        ("archived", _bool(view.get("archived"))),
        # The fields below are for you: change them in Obsidian, they are never rewritten.
        ("status", "new"),
        ("tags", '["vacancy", "hh"]'),
        ("collected", now.astimezone(dt.timezone.utc).strftime("%Y-%m-%d")),
    ]

    out = ["---", *(f"{k}: {v}" for k, v in props), "---", ""]
    out.append(f"# {view.get('title', '')}")
    out.append("")
    sal = salary_text(view.get("salary")) if view.get("salary") else "salary not specified"
    out.append(f"{view.get('employer') or '-'} · {view.get('area') or '-'} · {sal}")
    out.append("")
    out.append(f"[Open on hh.ru]({view.get('url', '')})")

    skills = "\n".join(f"- {s}" for s in view.get("key_skills", []))
    for title, body in (
        ("Key skills", skills),
        ("Requirements", view.get("requirements", "")),
        ("Responsibilities", view.get("responsibilities", "")),
        ("Nice to have", view.get("nice_to_have", "")),
        ("Conditions", view.get("conditions", "")),
        ("Full description", view.get("description_text", "")),
    ):
        body = body.strip()
        if body:
            out += ["", f"## {title}", "", body]
    # An empty place for the reader to write in.
    out += ["", "## My notes", ""]
    return "\n".join(out)


def _bool(value: Any) -> str:
    return "true" if value else "false"
