"""Configuracao central. Tudo vem de variavel de ambiente, com defaults seguros."""

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache


def _env(key: str, default: str = "") -> str:
    value = os.environ.get(key, "")
    value = value.strip()
    return value or default


@dataclass(frozen=True)
class Settings:
    llm_base_url: str
    llm_api_key: str
    llm_model: str
    scan_timeout: float
    user_agent: str
    free_scan_daily_limit: int

    @property
    def llm_enabled(self) -> bool:
        return bool(self.llm_api_key)


@lru_cache(maxsize=1)
def load_settings() -> Settings:
    # .env e opcional: em producao usamos env vars reais.
    try:
        from dotenv import load_dotenv

        load_dotenv(override=False)
    except ImportError:
        pass

    try:
        timeout = float(_env("SCAN_TIMEOUT", "15"))
    except ValueError:
        timeout = 15.0

    try:
        limit = int(_env("FREE_SCAN_DAILY_LIMIT", "3"))
    except ValueError:
        limit = 3

    return Settings(
        llm_base_url=_env("LLM_BASE_URL", "https://api.mandapi.com/v1"),
        llm_api_key=_env("LLM_API_KEY"),
        llm_model=_env("LLM_MODEL", "gpt-4o-mini"),
        scan_timeout=timeout,
        user_agent=_env("USER_AGENT", "MandAPIGeoBot/0.1 (+https://mandapi.com/geo)"),
        free_scan_daily_limit=limit,
    )