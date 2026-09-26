"""Configuracao central. Tudo vem de variavel de ambiente, com defaults seguros."""

from __future__ import annotations

import os
import math
from dataclasses import dataclass
from functools import lru_cache
from urllib.parse import urlsplit


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
    site_url: str = ""
    site_indexable: bool = False
    google_site_verification: str = ""
    max_concurrent_scans: int = 2
    public_ai_summary: bool = False

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
    timeout = max(1.0, min(timeout, 30.0)) if math.isfinite(timeout) else 15.0

    try:
        limit = int(_env("FREE_SCAN_DAILY_LIMIT", "3"))
    except ValueError:
        limit = 3
    limit = max(1, min(limit, 1000))
    try:
        concurrent = max(1, min(int(_env("MAX_CONCURRENT_SCANS", "2")), 8))
    except ValueError:
        concurrent = 2
    site_url = _env("SITE_URL").rstrip("/")
    if site_url:
        from .network import normalize_public_url
        parsed = urlsplit(site_url)
        # Also validate empty userinfo, ports, IDNA names and literal public IPs.
        normalized = normalize_public_url(site_url)
        if (parsed.scheme not in {"http", "https"} or not parsed.hostname
                or "@" in parsed.netloc or parsed.username or parsed.password or parsed.query or parsed.fragment
                or parsed.path or any(c in site_url for c in '<>"\\\r\n\t')):
            raise ValueError("SITE_URL must be an HTTP(S) origin without a path or credentials.")
        site_url = normalized.rstrip("/")

    return Settings(
        llm_base_url=_env("LLM_BASE_URL", "https://api.mandapi.com/v1"),
        llm_api_key=_env("LLM_API_KEY"),
        llm_model=_env("LLM_MODEL", "gpt-4o-mini"),
        scan_timeout=timeout,
        user_agent=_env("USER_AGENT", "MandAPIGeoBot/0.2"),
        free_scan_daily_limit=limit,
        site_url=site_url,
        site_indexable=bool(site_url.startswith("https://") and _env("SITE_INDEXABLE", "false").lower() == "true"),
        google_site_verification=_env("GOOGLE_SITE_VERIFICATION"),
        max_concurrent_scans=concurrent,
        public_ai_summary=_env("PUBLIC_AI_SUMMARY", "false").lower() == "true",
    )
