import unittest

from hh_parser.filters import parse_words, title_excluder


class FiltersTest(unittest.TestCase):
    def test_parse_words(self):
        self.assertEqual(parse_words(" Junior, ДЖУН ,, Стажёр,team lead "), ["junior", "джун", "стажер", "team lead"])
        self.assertEqual(parse_words(""), [])

    def test_matches_start_of_a_word_ignoring_case_and_yo(self):
        excluded = title_excluder(parse_words("junior,джун,стажер,руководитель,team lead,head of"))
        for title in (
            "Junior Go developer",
            "Golang-разработчик (junior+)",
            "Джуниор разработчик",
            "Стажёр-разработчик Go",
            "Руководитель отдела разработки",
            "Senior Backend Developer / Team Lead (Go)",
            "Head of Engineering",
        ):
            with self.subTest(title):
                self.assertTrue(excluded(title))

    def test_does_not_match_inside_a_word(self):
        excluded = title_excluder(parse_words("head,lead"))
        for title in ("Go developer, ahead of the curve", "Misleading title", "Senior Go developer"):
            with self.subTest(title):
                self.assertFalse(excluded(title))

    def test_empty_word_list_excludes_nothing(self):
        self.assertFalse(title_excluder([])("Junior"))

    def test_regex_characters_in_words_are_literal(self):
        excluded = title_excluder(parse_words("c++,.net"))
        self.assertTrue(excluded("C++ developer"))
        self.assertFalse(excluded("Go developer"))


if __name__ == "__main__":
    unittest.main()
