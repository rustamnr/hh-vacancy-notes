import unittest

from hh_parser import textutil


class HtmlToTextTest(unittest.TestCase):
    def test_cases(self):
        cases = {
            "paragraphs": ("<p>One</p><p>Two</p>", "One\nTwo"),
            "br": ("a<br>b<br/>c", "a\nb\nc"),
            "list": ("<p>Need:</p><ul><li>Go</li><li>SQL</li></ul>", "Need:\n\n- Go\n- SQL"),
            "entities": ("R&amp;D &quot;team&quot; &nbsp;ok", 'R&D "team" ok'),
            "inline tags dropped": ("<strong>Bold</strong> and <em>it</em>", "Bold and it"),
            "collapses blank lines": ("<p>a</p><p></p><p></p><p></p><p>b</p>", "a\n\nb"),
            "empty": ("", ""),
        }
        for name, (src, want) in cases.items():
            with self.subTest(name):
                self.assertEqual(textutil.html_to_text(src), want)


class SectionsTest(unittest.TestCase):
    def test_sections(self):
        text = (
            "About us\n\nОбязанности:\n- write Go\n- review code\n\nТребования:\n- 3+ years of Go\n- PostgreSQL\n\n"
            "Будет плюсом:\n- Kafka\n\nУсловия:\n- remote\n\nКонтакты:\n- hr@example.org"
        )
        got = [(s.kind, s.body) for s in textutil.sections(text)]
        self.assertEqual(
            got,
            [
                (textutil.RESPONSIBILITIES, "- write Go\n- review code"),
                (textutil.REQUIREMENTS, "- 3+ years of Go\n- PostgreSQL"),
                (textutil.NICE_TO_HAVE, "- Kafka"),
                (textutil.CONDITIONS, "- remote"),
            ],
        )

    def test_no_headings(self):
        self.assertEqual(textutil.sections("Just a paragraph without structure."), [])


if __name__ == "__main__":
    unittest.main()
