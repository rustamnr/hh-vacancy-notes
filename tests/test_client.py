import unittest
import urllib.parse

from hh_parser import client as hh
from tests.fake_api import FakeAPI

UA = "hh-parser-test/1.0 (test@mail.test)"


class ClientTest(unittest.TestCase):
    def test_requires_user_agent(self):
        with self.assertRaises(ValueError):
            hh.HHClient("")

    def test_request_headers(self):
        with FakeAPI(lambda p, h: (200, {"id": "1"})) as api:
            hh.HHClient(UA, "tok-123", api.url).vacancy("1")
        headers = api.requests[0][1]
        self.assertEqual(headers["User-Agent"], UA)
        self.assertEqual(headers["Authorization"], "Bearer tok-123")
        self.assertEqual(headers["Accept"], "application/json")

    def test_no_authorization_header_without_token(self):
        with FakeAPI(lambda p, h: (200, {})) as api:
            hh.HHClient(UA, "", api.url).get_json("/x")
        self.assertNotIn("Authorization", api.requests[0][1])

    def test_token_is_not_in_repr(self):
        self.assertNotIn("tok-123", repr(hh.HHClient(UA, "tok-123")))

    def test_search_builds_query(self):
        with FakeAPI(lambda p, h: (200, {"found": 2, "items": []})) as api:
            hh.HHClient(UA, "", api.url).search_vacancies(text="go dev", area="1", per_page=20, page=3, period=7)
        path = api.requests[0][0]
        for want in ("text=go+dev", "area=1", "per_page=20", "page=3", "period=7"):
            self.assertIn(want, path)

    def test_search_omits_empty_params(self):
        with FakeAPI(lambda p, h: (200, {})) as api:
            hh.HHClient(UA, "", api.url).search_vacancies(per_page=10)
        self.assertEqual(api.requests[0][0], "/vacancies?per_page=10")

    def test_vacancy_id_is_escaped(self):
        with FakeAPI(lambda p, h: (200, {})) as api:
            hh.HHClient(UA, "", api.url).vacancy("a/b")
        self.assertEqual(api.requests[0][0], "/vacancies/a%2Fb")

    def test_vacancy_raw_is_returned_as_sent(self):
        with FakeAPI(lambda p, h: (200, '{"id":"1",  "name":"x"}')) as api:
            raw = hh.HHClient(UA, "", api.url).vacancy_raw("1")
        self.assertEqual(raw, b'{"id":"1",  "name":"x"}')

    def test_error_mapping(self):
        cases = [
            (400, {"errors": [{"type": "bad_user_agent", "value": "unset"}]}, "bad_user_agent"),
            (403, {"errors": [{"type": "oauth", "value": "token_expired"}]}, "token_expired"),
            (403, {"errors": [{"type": "oauth", "value": "token_revoked"}]}, "token_revoked"),
            (403, {"errors": [{"type": "captcha_required", "captcha_url": "https://x"}]}, "captcha_required"),
            (403, {"errors": [{"type": "negotiations", "value": "limit_exceeded"}]}, "limit_exceeded"),
        ]
        for status, body, prop in cases:
            with self.subTest(prop):
                with FakeAPI(lambda p, h, s=status, b=body: (s, b)) as api:
                    with self.assertRaises(hh.HHError) as cm:
                        hh.HHClient(UA, "", api.url).get_json("/x")
                self.assertEqual(cm.exception.status, status)
                self.assertTrue(getattr(cm.exception, prop))

    def test_error_does_not_match_unrelated_kind(self):
        with FakeAPI(lambda p, h: (403, {"errors": [{"type": "oauth", "value": "token_expired"}]})) as api:
            with self.assertRaises(hh.HHError) as cm:
                hh.HHClient(UA, "", api.url).get_json("/x")
        self.assertFalse(cm.exception.captcha_required)

    def test_non_json_error_body_still_gives_an_error_without_leaking_it(self):
        with FakeAPI(lambda p, h: (502, "<html>bad gateway</html>")) as api:
            with self.assertRaises(hh.HHError) as cm:
                hh.HHClient(UA, "", api.url).get_json("/x")
        self.assertEqual(cm.exception.status, 502)
        self.assertNotIn("html", str(cm.exception))

    def test_unreachable_server_gives_status_zero(self):
        with self.assertRaises(hh.HHError) as cm:
            hh.HHClient(UA, "", "http://127.0.0.1:1", timeout=2).get_json("/x")
        self.assertEqual(cm.exception.status, 0)


class PagingTest(unittest.TestCase):
    def test_validate_paging(self):
        hh.validate_paging(20, 2)
        hh.validate_paging(100, 20)
        for per_page, pages in ((100, 21), (101, 1), (0, 1), (10, 0)):
            with self.subTest((per_page, pages)):
                with self.assertRaises(ValueError):
                    hh.validate_paging(per_page, pages)

    def test_search_all_pages_until_the_last_and_sleeps_between(self):
        def handler(path, headers):
            query = urllib.parse.parse_qs(urllib.parse.urlparse(path).query)
            page = int(query.get("page", ["0"])[0])
            return 200, {"found": 3, "pages": 2, "items": [{"id": str(page * 2 + i)} for i in range(2 if page == 0 else 1)]}

        sleeps = []
        with FakeAPI(handler) as api:
            found, items = hh.search_all(
                hh.HHClient(UA, "", api.url), text="go", per_page=2, pages=5, sleep=sleeps.append
            )
        self.assertEqual(found, 3)
        self.assertEqual([i["id"] for i in items], ["0", "1", "2"])
        self.assertEqual(len(api.requests), 2)  # stopped at the last page, not at pages=5
        self.assertEqual(sleeps, [hh.PAGE_DELAY])


if __name__ == "__main__":
    unittest.main()
