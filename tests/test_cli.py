import argparse
import io
import json
import tempfile
import unittest
from unittest import mock
from pathlib import Path

from hh_parser import cli
from hh_parser import client as hh
from tests.fake_api import FakeAPI

UA = "t/1 (t@example.org)"


def api_handler(path, headers):
    if path.startswith("/vacancies?"):
        return 200, {
            "found": 3,
            "pages": 1,
            "items": [
                {"id": "1", "name": "Go dev", "alternate_url": "https://hh.ru/vacancy/1",
                 "published_at": "2026-10-03T10:00:00+0300", "employer": {"name": "Acme"}, "area": {"name": "Москва"}},
                {"id": "2", "name": "Broken"},
                {"id": "1", "name": "Go dev (duplicate in the result)"},
            ],
        }
    if path == "/vacancies/2":
        return 404, {"errors": [{"type": "not_found"}]}
    vid = path.rsplit("/", 1)[1]
    return 200, {"id": vid, "name": "Go dev", "description": "<p>Требования:</p><ul><li>Go</li></ul>"}


def run_search(api, **overrides):
    args = argparse.Namespace(text="go", area="", period=0, per_page=10, pages=1,
                              json=False, out="", raw=False, vault="", exclude="")
    for k, v in overrides.items():
        setattr(args, k, v)
    out, err = io.StringIO(), io.StringIO()
    code = cli.cmd_search(args, out, err, client=hh.HHClient(UA, "", api.url))
    return code, out.getvalue(), err.getvalue()


class CliTest(unittest.TestCase):
    def setUp(self):
        # No real pauses between requests in tests.
        patcher = mock.patch.object(cli.time, "sleep")
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_parse_id(self):
        for arg, want in (("123456", "123456"), (" 123456 ", "123456"),
                          ("https://hh.ru/vacancy/987654?query=go", "987654"),
                          ("https://spb.hh.ru/vacancy/42", "42")):
            self.assertEqual(cli.parse_id(arg), want)
        for bad in ("abc", ""):
            with self.assertRaises(ValueError):
                cli.parse_id(bad)

    def test_truncate_is_character_safe(self):
        self.assertEqual(cli.truncate("Ünïcode title", 4), "Ünï…")
        self.assertEqual(cli.truncate("short", 10), "short")

    def test_unique_and_split_known(self):
        items = cli.unique_by_id([{"id": "1"}, {"id": "2"}, {"id": "1"}, {"id": "3"}])
        self.assertEqual(len(items), 3)
        fresh, seen = cli.split_known(items, {"2"})
        self.assertEqual([i["id"] for i in fresh], ["1", "3"])
        self.assertEqual(seen, ["2"])

    def test_table_has_ids_and_urls(self):
        with FakeAPI(api_handler) as api:
            code, out, _ = run_search(api)
        self.assertEqual(code, 0)
        self.assertIn("ID", out.splitlines()[0])
        self.assertIn("https://hh.ru/vacancy/1", out)
        self.assertEqual(len(api.requests), 1)  # the table needs no vacancy details

    def test_json_mode_prints_only_json_on_stdout_and_reports_failures_on_stderr(self):
        with FakeAPI(api_handler) as api:
            code, out, err = run_search(api, json=True)
        views = json.loads(out)
        self.assertEqual([v["id"] for v in views], ["1"])  # "2" failed, the duplicate "1" was dropped
        self.assertEqual(views[0]["requirements"], "- Go")
        self.assertIn("vacancy 2", err)

    def test_out_dir_writes_view_and_raw(self):
        with FakeAPI(api_handler) as api, tempfile.TemporaryDirectory() as d:
            run_search(api, out=d)
            view = json.loads((Path(d) / "1.json").read_text(encoding="utf-8"))
            self.assertEqual(view["title"], "Go dev")
            run_search(api, out=d, raw=True)
            raw = json.loads((Path(d) / "1.json").read_text(encoding="utf-8"))
            self.assertIn("description", raw)  # the API response, not the view

    def test_vault_skips_known_vacancies_without_fetching_them(self):
        with FakeAPI(api_handler) as api, tempfile.TemporaryDirectory() as d:
            run_search(api, vault=d)
            first_requests = len(api.requests)
            self.assertEqual(len(list(Path(d).glob("*(1).md"))), 1)

            _, _, err = run_search(api, vault=d)
            self.assertIn("1 new, 1 already in the vault", err)  # "2" is still new: it failed before
            # second run: one search request, and a detail request only for the vacancy that failed before
            detail_paths = [p for p, _ in api.requests[first_requests:] if p.startswith("/vacancies/")]
            self.assertEqual(detail_paths, ["/vacancies/2"])
            self.assertEqual(len(list(Path(d).glob("*.md"))), 1)

    def test_exclude_skips_vacancies_by_title_before_fetching_them(self):
        def handler(path, headers):
            if path.startswith("/vacancies?"):
                titles = ["Go developer", "Junior Go developer", "Руководитель отдела Go", "Senior Go Backend"]
                return 200, {"found": 4, "pages": 1,
                             "items": [{"id": str(i + 1), "name": t} for i, t in enumerate(titles)]}
            vid = path.rsplit("/", 1)[1]
            return 200, {"id": vid, "name": "x"}

        with FakeAPI(handler) as api:
            _, out, err = run_search(api, json=True, exclude="junior, руководитель")
        self.assertEqual([v["id"] for v in json.loads(out)], ["1", "4"])
        self.assertIn("excluded 2 by title", err)
        fetched = [p for p, _ in api.requests if p.startswith("/vacancies/")]
        self.assertEqual(sorted(fetched), ["/vacancies/1", "/vacancies/4"])  # excluded ones cost no request

    def test_exclude_defaults_to_the_environment_and_can_be_switched_off(self):
        def handler(path, headers):
            return 200, {"found": 2, "pages": 1, "items": [{"id": "1", "name": "Junior dev"}, {"id": "2", "name": "Dev"}]}

        with FakeAPI(handler) as api:
            with mock.patch.dict("os.environ", {"HH_EXCLUDE": "junior"}):
                _, out, _ = run_search(api, exclude=None)
                self.assertNotIn("Junior dev", out)
                self.assertIn("Dev", out)
                _, out, _ = run_search(api, exclude="")  # an explicit empty value turns the filter off
                self.assertIn("Junior dev", out)

    def test_fetch_details_sink_error_stops_the_run(self):
        def boom(*_a):
            raise RuntimeError("disk full")

        with FakeAPI(api_handler) as api:
            with self.assertRaises(RuntimeError):
                cli.fetch_details(hh.HHClient(UA, "", api.url), [{"id": "1"}], boom, io.StringIO(), delay=0)


if __name__ == "__main__":
    unittest.main()
