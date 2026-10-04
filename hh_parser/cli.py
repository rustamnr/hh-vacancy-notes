"""Command line: ``python -m hh_parser search ...`` and ``python -m hh_parser vacancy ...``."""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path
from typing import Any, Callable, Optional, TextIO

from hh_parser import client as hh
from hh_parser.config import ConfigError, HHConfig, load_dotenv
from hh_parser.vault import Vault
from hh_parser.view import salary_text, vacancy_view

Sink = Callable[[str, bytes, dict], None]

_ID_RE = re.compile(r"^\d+$")
_URL_ID_RE = re.compile(r"/vacancy/(\d+)")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="hh_parser", description="Collect vacancies from hh.ru (application token, read-only).")
    sub = p.add_subparsers(dest="command", required=True)

    s = sub.add_parser(
        "search",
        help="search vacancies",
        description=(
            "Prints a table by default. The other modes fetch every found vacancy in full: "
            "--json prints a JSON array with separated fields, --out DIR writes one JSON file "
            "per vacancy, --vault DIR writes one Markdown note per vacancy."
        ),
    )
    s.add_argument("--text", default="golang", help="search text (hh query language is supported)")
    s.add_argument("--area", default="", help="hh area id, e.g. 1 = Moscow; empty = everywhere")
    s.add_argument("--period", type=int, default=0, help="only vacancies published within this many days (0 = no limit)")
    s.add_argument("--per-page", type=int, default=20, help="results per page, 1..100")
    s.add_argument("--pages", type=int, default=1, help="how many pages to fetch")
    s.add_argument("--json", action="store_true", help="fetch every found vacancy and print a JSON array instead of the table")
    s.add_argument("--out", default="", metavar="DIR", help="write one JSON file per vacancy to DIR")
    s.add_argument("--raw", action="store_true", help="with --out: write the raw API response instead of the separated fields")
    s.add_argument(
        "--vault",
        default="",
        metavar="DIR",
        help="write one Markdown note per vacancy to DIR (e.g. an Obsidian folder); known vacancies are skipped",
    )

    v = sub.add_parser("vacancy", help="print one vacancy as JSON")
    v.add_argument("vacancy", help="vacancy id or hh.ru URL")
    v.add_argument("--raw", action="store_true", help="print the API response as is (re-indented)")
    return p


def parse_id(arg: str) -> str:
    """Accept a bare id or any URL containing /vacancy/<id>."""
    arg = arg.strip()
    if _ID_RE.match(arg):
        return arg
    m = _URL_ID_RE.search(arg)
    if m:
        return m.group(1)
    raise ValueError(f"cannot find a vacancy id in {arg!r}")


def dump_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2)


def truncate(s: str, n: int) -> str:
    s = s.strip()
    return s if len(s) <= n else s[: n - 1] + "…"


def print_table(items: list[dict[str, Any]], out: TextIO) -> None:
    def name(obj: Any) -> str:
        return truncate(obj["name"], 30) if isinstance(obj, dict) and obj.get("name") else "-"

    rows = [("ID", "PUBLISHED", "TITLE", "COMPANY", "SALARY", "AREA", "URL")]
    for it in items:
        rows.append((
            str(it.get("id", "")),
            (it.get("published_at") or "")[:10] or "-",
            truncate(it.get("name", ""), 55),
            name(it.get("employer")),
            salary_text(it.get("salary")),
            name(it.get("area")),
            it.get("alternate_url", ""),
        ))
    widths = [max(len(r[i]) for r in rows) for i in range(len(rows[0]) - 1)]
    for r in rows:
        out.write("  ".join(c.ljust(w) for c, w in zip(r, widths)) + "  " + r[-1] + "\n")


def unique_by_id(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Drop repeated ids (a result page can shift while we page)."""
    seen: set[str] = set()
    out = []
    for it in items:
        if it["id"] not in seen:
            seen.add(it["id"])
            out.append(it)
    return out


def split_known(
    items: list[dict[str, Any]], known: set[str]
) -> tuple[list[dict[str, Any]], list[str]]:
    """Separate vacancies that are not stored yet from the ids already known."""
    fresh = [it for it in items if it["id"] not in known]
    seen = [it["id"] for it in items if it["id"] in known]
    return fresh, seen


def file_sink(directory: Path, raw: bool) -> Sink:
    def sink(vacancy_id: str, body: bytes, view: dict) -> None:
        path = directory / f"{vacancy_id}.json"
        if raw:
            path.write_bytes(body)
        else:
            path.write_text(dump_json(view) + "\n", encoding="utf-8")

    return sink


def vault_sink(vault: Vault, err: TextIO) -> Sink:
    added = 0

    def sink(vacancy_id: str, body: bytes, view: dict) -> None:
        nonlocal added
        if vault.save(view):
            added += 1
            print(f"saved {added}: {view['title']}", file=err)

    return sink


def fetch_details(
    client: hh.HHClient,
    items: list[dict[str, Any]],
    sink: Sink,
    err: TextIO,
    delay: float = hh.DETAIL_DELAY,
    sleep: Optional[Callable[[float], None]] = None,
) -> None:
    """Load every vacancy by id and hand it to ``sink`` right away, so an
    interrupted run keeps what it already got. A failure on one vacancy is
    reported and skipped; an error from the sink stops the run."""
    sleep = sleep or time.sleep
    failed = 0
    for it in items:
        sleep(delay)
        try:
            body = client.vacancy_raw(it["id"])
            view = vacancy_view(json.loads(body))
        except (hh.HHError, ValueError) as exc:
            failed += 1
            print(f"vacancy {it['id']}: {exc}", file=err)
            continue
        sink(it["id"], body, view)
    if failed:
        print(f"{failed} of {len(items)} vacancies could not be loaded", file=err)


def make_client() -> hh.HHClient:
    load_dotenv(".env")
    cfg = HHConfig.from_env()
    return hh.HHClient(cfg.user_agent, cfg.app_token)


def cmd_search(args: argparse.Namespace, out: TextIO, err: TextIO, client: Optional[hh.HHClient] = None) -> int:
    hh.validate_paging(args.per_page, args.pages)
    client = client or make_client()

    found, items = hh.search_all(
        client, text=args.text, area=args.area, period=args.period, per_page=args.per_page, pages=args.pages
    )
    print(f"found {found} vacancies in total for {args.text!r}, got {len(items)}", file=err)

    if not (args.json or args.out or args.vault):
        print_table(items, out)
        return 0

    items = unique_by_id(items)
    sinks: list[Sink] = []

    if args.vault:
        vault = Vault(args.vault)
        fresh, seen = split_known(items, vault.known_ids())
        print(f"{len(fresh)} new, {len(seen)} already in the vault", file=err)
        # --json and --out still cover everything that was found; the vault
        # alone fetches only what it does not have yet.
        if not args.json and not args.out:
            items = fresh
        sinks.append(vault_sink(vault, err))

    views: list[dict] = []
    if args.json:
        sinks.append(lambda _id, _body, view: views.append(view))
    if args.out:
        directory = Path(args.out).expanduser()
        directory.mkdir(parents=True, exist_ok=True)
        sinks.append(file_sink(directory, args.raw))

    def sink(vacancy_id: str, body: bytes, view: dict) -> None:
        for s in sinks:
            s(vacancy_id, body, view)

    fetch_details(client, items, sink, err)
    if args.json:
        out.write(dump_json(views) + "\n")
    return 0


def cmd_vacancy(args: argparse.Namespace, out: TextIO, err: TextIO, client: Optional[hh.HHClient] = None) -> int:
    vacancy_id = parse_id(args.vacancy)
    client = client or make_client()
    body = client.vacancy_raw(vacancy_id)
    value = json.loads(body) if args.raw else vacancy_view(json.loads(body))
    out.write(dump_json(value) + "\n")
    return 0


def main(argv: Optional[list[str]] = None, out: TextIO = sys.stdout, err: TextIO = sys.stderr) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "search":
            return cmd_search(args, out, err)
        return cmd_vacancy(args, out, err)
    except KeyboardInterrupt:
        print("interrupted", file=err)
        return 130
    except (ConfigError, ValueError, hh.HHError) as exc:
        print(f"error: {exc}", file=err)
        return 1
