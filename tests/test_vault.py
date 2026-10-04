import datetime as dt
import tempfile
import unittest
from pathlib import Path

from hh_parser.vault import Vault, file_name, render

NOW = dt.datetime(2026, 10, 4, 12, 0, tzinfo=dt.timezone.utc)


def sample(vid="42"):
    return {
        "id": vid,
        "title": 'Go: "senior" / backend [remote]',
        "url": "https://hh.ru/vacancy/" + vid,
        "published_at": "2026-10-03T10:00:00+0300",
        "employer": "Acme",
        "area": "Москва",
        "salary": {"from": 250000, "to": 350000, "currency": "RUR", "gross": False},
        "key_skills": ["Go", "PostgreSQL"],
        "professional_roles": ["Backend"],
        "requirements": "- 3+ years of Go",
        "description_text": "Full text",
    }


class VaultTest(unittest.TestCase):
    def test_file_name_is_safe_and_keeps_id(self):
        self.assertEqual(file_name(sample()), "Go senior backend remote (42).md")
        self.assertLessEqual(len(file_name({"id": "7", "title": "я" * 200})), 100)
        self.assertEqual(file_name({"id": "8", "title": "///"}), "vacancy (8).md")

    def test_render(self):
        out = render(sample(), NOW)
        for want in (
            '---\nid: "42"\n',
            'url: "https://hh.ru/vacancy/42"',
            "salary_from: 250000",
            "salary_to: 350000",
            'salary_currency: "RUR"',
            "published: 2026-10-03\n",
            'key_skills: ["Go", "PostgreSQL"]',
            "status: new\n",
            "collected: 2026-10-04\n",
            '# Go: "senior" / backend [remote]',
            "Acme · Москва · from 250000 to 350000 RUR",
            "## Requirements\n\n- 3+ years of Go",
            "## Full description\n\nFull text",
            "## My notes",
        ):
            self.assertIn(want, out)
        self.assertNotIn("## Responsibilities", out)  # empty sections are skipped

    def test_render_without_salary(self):
        v = sample()
        v["salary"] = None
        out = render(v, NOW)
        self.assertNotIn("salary_", out)
        self.assertIn("salary not specified", out)

    def test_save_is_idempotent_and_never_overwrites(self):
        with tempfile.TemporaryDirectory() as d:
            vault = Vault(Path(d) / "Vacancies")
            self.assertTrue(vault.save(sample(), NOW))

            path = vault.dir / file_name(sample())
            path.write_text("my edits", encoding="utf-8")  # the user edits the note...
            changed = sample()
            changed["title"] = "Renamed"
            self.assertFalse(vault.save(changed, NOW))  # ...a second run must not touch it
            self.assertEqual(path.read_text(encoding="utf-8"), "my edits")
            self.assertEqual(len(list(vault.dir.iterdir())), 1)

    def test_known_ids(self):
        with tempfile.TemporaryDirectory() as d:
            vault = Vault(d)
            vault.save(sample("1"), NOW)
            vault.save(sample("2"), NOW)
            (Path(d) / "unrelated.md").write_text("x")
            self.assertEqual(vault.known_ids(), {"1", "2"})

    def test_save_rejects_empty_id(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(ValueError):
                Vault(d).save({"id": ""})


if __name__ == "__main__":
    unittest.main()
