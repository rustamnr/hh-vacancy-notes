import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from hh_parser.config import ConfigError, HHConfig, load_dotenv, parse_dotenv


class ConfigTest(unittest.TestCase):
    def test_parse_dotenv(self):
        text = "# comment\n\nA=1\nexport B = two \nC=\"quoted value\"\nD='single'\nbroken line\nE=a=b\n"
        self.assertEqual(
            parse_dotenv(text),
            {"A": "1", "B": "two", "C": "quoted value", "D": "single", "E": "a=b"},
        )

    def test_load_dotenv_does_not_override_and_tolerates_missing_file(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / ".env"
            path.write_text("HH_TEST_A=from-file\nHH_TEST_B=from-file\n")
            with mock.patch.dict(os.environ, {"HH_TEST_A": "from-env"}, clear=False):
                os.environ.pop("HH_TEST_B", None)
                load_dotenv(str(path))
                self.assertEqual(os.environ["HH_TEST_A"], "from-env")
                self.assertEqual(os.environ["HH_TEST_B"], "from-file")
                os.environ.pop("HH_TEST_B", None)
            load_dotenv(str(Path(d) / "missing.env"))  # must not raise

    def test_from_env_requires_both_values(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(ConfigError) as cm:
                HHConfig.from_env()
        self.assertIn("HH_USER_AGENT", str(cm.exception))
        self.assertIn("HH_APP_TOKEN", str(cm.exception))

    def test_token_is_never_printed(self):
        with mock.patch.dict(os.environ, {"HH_USER_AGENT": "a/1 (a@b.c)", "HH_APP_TOKEN": "super-secret"}, clear=True):
            cfg = HHConfig.from_env()
        self.assertNotIn("super-secret", repr(cfg))
        self.assertEqual(cfg.app_token, "super-secret")


if __name__ == "__main__":
    unittest.main()
