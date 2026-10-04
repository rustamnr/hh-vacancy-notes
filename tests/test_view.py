import json
import unittest

from hh_parser.view import salary_text, vacancy_view


class ViewTest(unittest.TestCase):
    def test_splits_fields(self):
        detail = {
            "id": 1,
            "name": "Go developer",
            "alternate_url": "https://hh.ru/vacancy/1",
            "employer": {"name": "Acme"},
            "salary": {"from": 100, "to": None, "currency": "RUR", "gross": False},
            "key_skills": [{"name": "Go"}, {"name": "PostgreSQL"}],
            "description": "<p>Intro</p><p><strong>Требования:</strong></p><ul><li>3+ years of Go</li></ul>"
            "<p><strong>Условия:</strong></p><ul><li>remote</li></ul>",
        }
        view = vacancy_view(detail)
        self.assertEqual(view["id"], "1")
        self.assertEqual(view["title"], "Go developer")
        self.assertEqual(view["employer"], "Acme")
        self.assertEqual(view["area"], "")
        self.assertEqual(view["key_skills"], ["Go", "PostgreSQL"])
        self.assertEqual(view["salary"], {"from": 100, "to": None, "currency": "RUR", "gross": False})
        self.assertIn("3+ years of Go", view["requirements"])
        self.assertNotIn("remote", view["requirements"])
        self.assertIn("remote", view["conditions"])
        self.assertIn("Intro", view["description_text"])

    def test_empty_vacancy_uses_empty_lists_and_null_salary(self):
        out = json.dumps(vacancy_view({"id": "1"}))
        for want in ('"key_skills": []', '"professional_roles": []', '"salary": null'):
            self.assertIn(want, out)

    def test_salary_text(self):
        self.assertEqual(salary_text(None), "-")
        self.assertEqual(salary_text({"from": None, "to": None}), "-")
        self.assertEqual(salary_text({"from": 100, "to": 200, "currency": "RUR"}), "from 100 to 200 RUR")
        self.assertEqual(salary_text({"from": None, "to": 200, "currency": "USD"}), "to 200 USD")


if __name__ == "__main__":
    unittest.main()
