"""Load public startup settings without requiring or initializing credentials."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Literal, Mapping
from urllib.parse import urlsplit

from dotenv import dotenv_values
from pydantic import BaseModel, ConfigDict, ValidationError, model_validator

PROJECT_ROOT = Path(__file__).resolve().parents[2]


class ConfigurationError(RuntimeError):
    """A sanitized startup failure; never includes configuration values."""


def valid_address(value: str, *, origin: bool, production: bool) -> bool:
    if not value or any(character.isspace() for character in value) or "*" in value or "\\" in value:
        return False
    try:
        parts = urlsplit(value)
        port = parts.port
    except ValueError:
        return False
    return bool(
        parts.scheme in {"http", "https"}
        and parts.hostname
        and parts.username is None
        and parts.password is None
        and not parts.query
        and not parts.fragment
        and parts.path in ({""} if origin else {"", "/"})
        and (port is None or 1 <= port <= 65535)
        and (parts.scheme == "https" or (not production and parts.hostname in {"localhost", "127.0.0.1", "::1"}))
    )


class Settings(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    app_env: Literal["development", "production"] = "development"
    allowed_origins: tuple[str, ...] = ("http://localhost:5500", "http://127.0.0.1:5500")
    api_base_url: str = "http://127.0.0.1:8000"

    @model_validator(mode="after")
    def check_addresses(self) -> "Settings":
        production = self.app_env == "production"
        if not self.allowed_origins or not all(
            valid_address(origin, origin=True, production=production) for origin in self.allowed_origins
        ):
            raise ValueError("ALLOWED_ORIGINS 형식을 확인하세요.")
        if not valid_address(self.api_base_url, origin=False, production=production):
            raise ValueError("API_BASE_URL 형식을 확인하세요.")
        return self


def load_settings(env_file: Path | None = None, environ: Mapping[str, str] | None = None) -> Settings:
    path = PROJECT_ROOT / ".env" if env_file is None else env_file
    try:
        values = dict(dotenv_values(path, interpolate=False, encoding="utf-8-sig")) if path.is_file() else {}
        values.update(os.environ if environ is None else environ)
        defaults = Settings()
        origins = values.get("ALLOWED_ORIGINS", ",".join(defaults.allowed_origins)) or ""
        return Settings(
            app_env=values.get("APP_ENV", "development"),
            allowed_origins=tuple(dict.fromkeys(item.strip() for item in origins.split(","))),
            api_base_url=values.get("API_BASE_URL", values.get("RENDER_EXTERNAL_URL", defaults.api_base_url)),
        )
    except (ValidationError, OSError, UnicodeError, TypeError, ValueError):
        raise ConfigurationError(
            "시작 설정을 읽을 수 없습니다. APP_ENV, ALLOWED_ORIGINS, API_BASE_URL과 .env 형식을 확인하세요."
        ) from None
