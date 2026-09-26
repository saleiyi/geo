"""Configuracao central. Tudo vem de variavel de ambiente, com defaults seguros."""

from __future__ import annotations

import os
import math
import re
from dataclasses import dataclass
from functools import lru_cache
from urllib.parse import urlsplit


def _env(key: str, default: str = "") -> str:
    value = os.environ.get(key, "")
    value = value.strip()
    return value or default


def _public_text(key: str, limit: int = 200, multiline: bool = False) -> str:
    value = _env(key)
    allowed_controls = '\n\r\t' if multiline else ''
    if len(value) > limit or any(ord(c) < 32 and c not in allowed_controls or ord(c) == 127 for c in value):
        raise ValueError(f'{key} contains unsupported characters or exceeds {limit} characters.')
    return value


def _contact_email() -> str:
    value = _public_text('CONTACT_EMAIL', 254)
    if not value:
        return ''
    # A plain public mailbox, not an address list, display name or mailto query.
    local, separator, domain = value.rpartition('@')
    if (not separator or not re.fullmatch(r"[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]{1,64}", local)
            or local.startswith('.') or local.endswith('.') or '..' in local):
        raise ValueError('CONTACT_EMAIL must contain one plain email address.')
    try:
        domain = domain.encode('idna').decode('ascii').lower()
    except UnicodeError:
        raise ValueError('CONTACT_EMAIL must contain one plain email address.') from None
    labels = domain.split('.')
    if len(labels) < 2 or any(not re.fullmatch(r'[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?', label) for label in labels):
        raise ValueError('CONTACT_EMAIL must contain one plain email address.')
    return f'{local}@{domain}'


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
    operator_name: str = ''
    contact_email: str = ''
    hosting_provider: str = ''
    privacy_log_notice_pt: str = ''
    privacy_log_notice_en: str = ''
    privacy_log_notice_zh: str = ''

    @property
    def llm_enabled(self) -> bool:
        return bool(self.llm_api_key)

    @property
    def publication_missing(self) -> tuple[str, ...]:
        """Configuration prerequisites only; these do not verify a live deployment."""
        fields = ['operator_name', 'contact_email', 'hosting_provider',
                  'privacy_log_notice_pt', 'privacy_log_notice_en', 'privacy_log_notice_zh']
        missing = ['SITE_URL_HTTPS'] if not self.site_url.startswith('https://') else []
        missing.extend(field.upper() for field in fields if not getattr(self, field))
        return tuple(missing)


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
    # Trusted process environment only; never derive the origin from request headers.
    site_url = _env("SITE_URL", _env('RENDER_EXTERNAL_URL')).rstrip("/")
    if site_url:
        from .network import normalize_public_url
        parsed = urlsplit(site_url)
        # Also validate empty userinfo, ports, IDNA names and literal public IPs.
        try:
            normalized = normalize_public_url(site_url)
        except ValueError:
            raise ValueError('SITE_URL must be a public HTTP(S) origin without a path or credentials.') from None
        if (parsed.scheme not in {"http", "https"} or not parsed.hostname
                or "@" in parsed.netloc or parsed.username or parsed.password or parsed.query or parsed.fragment
                or parsed.path or any(c in site_url for c in '<>"\\\r\n\t')):
            raise ValueError("SITE_URL must be an HTTP(S) origin without a path or credentials.")
        site_url = normalized.rstrip("/")

    requested_indexing = _env('SITE_INDEXABLE', 'false').lower() == 'true'
    settings = Settings(
        llm_base_url=_env("LLM_BASE_URL", "https://api.mandapi.com/v1"),
        llm_api_key=_env("LLM_API_KEY"),
        llm_model=_env("LLM_MODEL", "gpt-4o-mini"),
        scan_timeout=timeout,
        user_agent=_env("USER_AGENT", "MandAPIGeoBot/0.2"),
        free_scan_daily_limit=limit,
        site_url=site_url,
        site_indexable=bool(site_url.startswith("https://") and requested_indexing),
        google_site_verification=_env("GOOGLE_SITE_VERIFICATION"),
        max_concurrent_scans=concurrent,
        public_ai_summary=_env("PUBLIC_AI_SUMMARY", "false").lower() == "true",
        operator_name=_public_text('OPERATOR_NAME'),
        contact_email=_contact_email(),
        hosting_provider=_public_text('HOSTING_PROVIDER'),
        privacy_log_notice_pt=_public_text('PRIVACY_LOG_NOTICE_PT', 4000, multiline=True),
        privacy_log_notice_en=_public_text('PRIVACY_LOG_NOTICE_EN', 4000, multiline=True),
        privacy_log_notice_zh=_public_text('PRIVACY_LOG_NOTICE_ZH', 4000, multiline=True),
    )
    if requested_indexing and settings.publication_missing:
        raise ValueError('SITE_INDEXABLE=true requires: ' + ', '.join(settings.publication_missing))
    return settings
