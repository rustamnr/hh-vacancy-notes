"""A vacancy flattened into separate, ready-to-use fields."""

from __future__ import annotations

from typing import Any, Optional

from hh_parser import textutil


def _name(obj: Any) -> str:
    return obj.get("name", "") if isinstance(obj, dict) else ""


def _names(items: Any) -> list[str]:
    return [_name(i) for i in items] if isinstance(items, list) else []


def salary_text(salary: Optional[dict[str, Any]]) -> str:
    """Format a salary for humans: "from 200000 to 300000 RUR", or "-" when absent."""
    if not salary or (salary.get("from") is None and salary.get("to") is None):
        return "-"
    parts = []
    if salary.get("from") is not None:
        parts.append(f"from {salary['from']}")
    if salary.get("to") is not None:
        parts.append(f"to {salary['to']}")
    if salary.get("currency"):
        parts.append(salary["currency"])
    return " ".join(parts)


def vacancy_view(detail: dict[str, Any]) -> dict[str, Any]:
    """Flatten a GET /vacancies/{id} response. The description is split into the
    parts we analyse (see textutil.sections); ``description_text`` always holds
    the whole text, so nothing is lost when the split misses a heading."""
    text = textutil.html_to_text(detail.get("description") or "")

    parts: dict[str, list[str]] = {}
    for sec in textutil.sections(text):
        parts.setdefault(sec.kind, []).append(sec.body)

    salary = detail.get("salary")
    if salary:
        salary = {
            "from": salary.get("from"),
            "to": salary.get("to"),
            "currency": salary.get("currency") or "",
            "gross": bool(salary.get("gross")),
        }
    else:
        salary = None

    def joined(kind: str) -> str:
        return "\n\n".join(parts.get(kind, []))

    return {
        "id": str(detail.get("id") or ""),
        "title": detail.get("name") or "",
        "url": detail.get("alternate_url") or "",
        "published_at": detail.get("published_at") or "",
        "archived": bool(detail.get("archived")),
        "employer": _name(detail.get("employer")),
        "area": _name(detail.get("area")),
        "salary": salary,
        "experience": _name(detail.get("experience")),
        "employment": _name(detail.get("employment")),
        "schedule": _name(detail.get("schedule")),
        "professional_roles": _names(detail.get("professional_roles")),
        "key_skills": _names(detail.get("key_skills")),
        "response_letter_required": bool(detail.get("response_letter_required")),
        "has_test": bool(detail.get("has_test")),
        "responsibilities": joined(textutil.RESPONSIBILITIES),
        "requirements": joined(textutil.REQUIREMENTS),
        "nice_to_have": joined(textutil.NICE_TO_HAVE),
        "conditions": joined(textutil.CONDITIONS),
        "description_text": text,
    }
