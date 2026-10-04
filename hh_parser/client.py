"""A small client for the hh.ru HTTP API (application token, read-only)."""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Callable, Optional

DEFAULT_BASE_URL = "https://api.hh.ru"

# hh serves at most 2000 results per search.
MAX_DEPTH = 2000

# Pauses between requests: the access is a privilege hh can withdraw.
PAGE_DELAY = 0.5
DETAIL_DELAY = 0.3

_MAX_BODY = 4 << 20


class HHError(Exception):
    """A failed request. ``status`` is 0 when the request never got an answer."""

    def __init__(
        self,
        status: int,
        errors: Optional[list[dict[str, Any]]] = None,
        request_id: str = "",
        description: str = "",
    ) -> None:
        self.status = status
        self.errors = errors or []
        self.request_id = request_id
        self.description = description
        super().__init__(self._message())

    def kinds(self) -> str:
        """A short "type/value" summary of the errors in the response."""
        return ", ".join(
            "/".join(p for p in (str(e.get("type", "")), str(e.get("value", ""))) if p)
            for e in self.errors
        )

    def has(self, key: str) -> bool:
        return any(e.get("type") == key or e.get("value") == key for e in self.errors)

    @property
    def bad_user_agent(self) -> bool:
        return self.has("bad_user_agent")

    @property
    def token_expired(self) -> bool:
        return self.has("token_expired")

    @property
    def token_revoked(self) -> bool:
        return self.has("token_revoked")

    @property
    def captcha_required(self) -> bool:
        return self.has("captcha_required")

    @property
    def limit_exceeded(self) -> bool:
        return self.has("limit_exceeded") or self.has("overall_limit") or self.has("in_a_row_limit")

    def _message(self) -> str:
        msg = f"hh api: status {self.status}"
        if self.kinds():
            msg += ": " + self.kinds()
        elif self.description:
            msg += ": " + self.description
        if self.request_id:
            msg += f" (request_id {self.request_id})"
        return msg


def _parse_error(status: int, body: bytes) -> HHError:
    """Never fails: a body that is not the documented error shape still gives an HHError."""
    try:
        payload = json.loads(body)
    except ValueError:
        payload = None
    if not isinstance(payload, dict):
        return HHError(status)
    errors = payload.get("errors")
    return HHError(
        status,
        errors=[e for e in errors if isinstance(e, dict)] if isinstance(errors, list) else [],
        request_id=str(payload.get("request_id") or ""),
        description=str(payload.get("description") or ""),
    )


class HHClient:
    def __init__(
        self,
        user_agent: str,
        token: str = "",
        base_url: str = DEFAULT_BASE_URL,
        timeout: float = 15.0,
    ) -> None:
        if not user_agent:
            raise ValueError("user_agent is required (the API rejects requests without it)")
        self._user_agent = user_agent
        self._token = token
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout

    def __repr__(self) -> str:  # never show the token
        return f"HHClient(base_url={self._base_url!r})"

    def get_bytes(self, path: str, query: Optional[dict[str, Any]] = None) -> bytes:
        url = self._base_url + path
        if query:
            url += "?" + urllib.parse.urlencode(query)
        headers = {"User-Agent": self._user_agent, "Accept": "application/json"}
        if self._token:
            headers["Authorization"] = "Bearer " + self._token
        request = urllib.request.Request(url, headers=headers, method="GET")
        try:
            with urllib.request.urlopen(request, timeout=self._timeout) as resp:  # noqa: S310 (https base url)
                return resp.read(_MAX_BODY)
        except urllib.error.HTTPError as exc:
            raise _parse_error(exc.code, exc.read(_MAX_BODY)) from None
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise HHError(0, description=f"{request.get_method()} {path}: {exc}") from exc

    def get_json(self, path: str, query: Optional[dict[str, Any]] = None) -> Any:
        body = self.get_bytes(path, query)
        try:
            return json.loads(body)
        except ValueError as exc:
            raise HHError(200, description=f"decode response: {exc}") from exc

    def search_vacancies(
        self,
        text: str = "",
        area: str = "",
        per_page: int = 20,
        page: int = 0,
        period: int = 0,
    ) -> dict[str, Any]:
        """GET /vacancies."""
        query: dict[str, Any] = {}
        if text:
            query["text"] = text
        if area:
            query["area"] = area
        if per_page > 0:
            query["per_page"] = per_page
        if page > 0:
            query["page"] = page
        if period > 0:
            query["period"] = period
        return self.get_json("/vacancies", query)

    def vacancy_raw(self, vacancy_id: str) -> bytes:
        """GET /vacancies/{id} exactly as hh sent it."""
        return self.get_bytes("/vacancies/" + urllib.parse.quote(vacancy_id, safe=""))

    def vacancy(self, vacancy_id: str) -> dict[str, Any]:
        return json.loads(self.vacancy_raw(vacancy_id))


def validate_paging(per_page: int, pages: int) -> None:
    """Reject values hh would refuse and stay inside its 2000-result depth limit."""
    if not 1 <= per_page <= 100:
        raise ValueError(f"per-page must be between 1 and 100, got {per_page}")
    if pages < 1:
        raise ValueError(f"pages must be at least 1, got {pages}")
    if per_page * pages > MAX_DEPTH:
        raise ValueError(
            f"hh serves at most {MAX_DEPTH} results per search: per-page * pages = {per_page * pages}"
        )


def search_all(
    client: HHClient,
    text: str = "",
    area: str = "",
    period: int = 0,
    per_page: int = 20,
    pages: int = 1,
    delay: float = PAGE_DELAY,
    sleep: Callable[[float], None] = time.sleep,
) -> tuple[int, list[dict[str, Any]]]:
    """Fetch up to ``pages`` pages of one search. Returns (total found, items)."""
    found = 0
    items: list[dict[str, Any]] = []
    for page in range(pages):
        if page > 0:
            sleep(delay)
        res = client.search_vacancies(text=text, area=area, per_page=per_page, page=page, period=period)
        found = int(res.get("found", 0))
        items.extend(res.get("items", []))
        if page + 1 >= int(res.get("pages", 0)):
            break
    return found, items
