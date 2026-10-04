"""Configuration from the environment and a .env file."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path


class ConfigError(Exception):
    """A required setting is missing."""


def parse_dotenv(text: str) -> dict[str, str]:
    """Parse KEY=VALUE lines. Blank lines and # comments are skipped, an
    optional ``export`` prefix and matching quotes around the value are removed."""
    values: dict[str, str] = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export "):].lstrip()
        key, sep, value = line.partition("=")
        if not sep:
            continue
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        values[key.strip()] = value
    return values


def load_dotenv(path: str = ".env") -> None:
    """Put the values of a .env file into os.environ without overriding
    variables that are already set. A missing file is fine."""
    try:
        text = Path(path).read_text(encoding="utf-8")
    except FileNotFoundError:
        return
    for key, value in parse_dotenv(text).items():
        os.environ.setdefault(key, value)


@dataclass(frozen=True)
class HHConfig:
    """Settings for the hh.ru API."""

    # Required by hh: "AppName/1.0 (contact@example.org)".
    user_agent: str
    # Application token from dev.hh.ru; never shown by repr().
    app_token: str = field(repr=False)

    @classmethod
    def from_env(cls) -> HHConfig:
        cfg = cls(
            user_agent=os.environ.get("HH_USER_AGENT", ""),
            app_token=os.environ.get("HH_APP_TOKEN", ""),
        )
        missing = [
            name
            for name, value in (("HH_USER_AGENT", cfg.user_agent), ("HH_APP_TOKEN", cfg.app_token))
            if not value
        ]
        if missing:
            raise ConfigError("missing environment variables: " + ", ".join(missing))
        return cfg
