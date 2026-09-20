"""Camada de rede. Hoje: httpx puro.

Se precisar renderizar JS, o plano é trocar APENAS este módulo por Crawl4AI
(unclecode/crawl4ai, Apache-2.0) ou Firecrawl. O resto do pipeline não muda.
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from urllib.parse import urljoin, urlparse

import httpx

from .config import load_settings
from .models import SiteFacts

# Bots de IA que importam para GEO. Se o site bloqueia, ele não pode ser citado.
AI_CRAWLERS: tuple[str, ...] = (
    "gptbot",
    "oai-searchbot",
    "chatgpt-user",
    "claudebot",
    "claude-web",
    "anthropic-ai",
    "perplexitybot",
    "google-extended",
    "applebot-extended",
    "ccbot",
    "bytespider",
    "meta-externalagent",
    "cohere-ai",
    "amazonbot",
    "yandexbot",
    "youbot",
    "diffbot",
)

_RANK: dict[str, int] = {"allow": 0, "partial": 1, "block": 2}


@dataclass
class FetchResult:
    url: str
    final_url: str
    status_code: int
    html: str = ""
    headers: dict[str, str] = field(default_factory=dict)
    elapsed_ms: int = 0
    content_bytes: int = 0
    redirect_count: int = 0
    error: str | None = None

    @property
    def ok(self) -> bool:
        return self.error is None and 200 <= self.status_code < 300


def normalize_url(raw: str) -> str:
    raw = (raw or "").strip()
    if not raw:
        raise ValueError("Informe uma URL.")
    if not re.match(r"^https?://", raw, re.IGNORECASE):
        raw = "https://" + raw.lstrip("/")
    return raw


def origin_of(url: str) -> str:
    parsed = urlparse(url)
    return f"{parsed.scheme}://{parsed.netloc}"


def _client() -> httpx.Client:
    settings = load_settings()
    return httpx.Client(
        timeout=settings.scan_timeout,
        follow_redirects=True,
        headers={
            "User-Agent": settings.user_agent,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
        },
    )


def fetch_page(url: str) -> FetchResult:
    """Baixa uma página. Nunca levanta exceção - devolve FetchResult com .error."""
    target = normalize_url(url)
    started = time.perf_counter()
    try:
        with _client() as client:
            response = client.get(target)
    except httpx.HTTPError as exc:
        return FetchResult(
            url=target,
            final_url=target,
            status_code=0,
            elapsed_ms=int((time.perf_counter() - started) * 1000),
            error=f"{type(exc).__name__}: {exc}",
        )

    body = response.content
    encoding = response.encoding or "utf-8"
    try:
        html = body.decode(encoding, errors="replace")
    except LookupError:
        html = body.decode("utf-8", errors="replace")

    return FetchResult(
        url=target,
        final_url=str(response.url),
        status_code=response.status_code,
        html=html,
        headers={k.lower(): v for k, v in response.headers.items()},
        elapsed_ms=int((time.perf_counter() - started) * 1000),
        content_bytes=len(body),
        redirect_count=len(response.history),
    )


def fetch_text(url: str) -> tuple[int | None, str | None]:
    """Busca um recurso auxiliar (robots.txt, sitemap.xml, llms.txt). Silencioso."""
    try:
        with _client() as client:
            response = client.get(url)
    except httpx.HTTPError:
        return None, None

    if response.status_code >= 400:
        return response.status_code, None

    try:
        return response.status_code, response.text
    except Exception:
        return response.status_code, None


def _verdict_for(value: str, directive: str) -> str:
    """Traduz uma linha Allow/Disallow em allow | partial | block.

    Só 'Disallow: /' bloqueia o site inteiro. Um caminho específico
    (ex: /admin) é bloqueio parcial, não impede a IA de ler o site.
    """
    value = value.strip()
    if directive == "allow":
        return "allow"
    if value == "":
        # 'Disallow:' vazio significa "permitir tudo"
        return "allow"
    if value == "/":
        return "block"
    return "partial"


def parse_robots_ai_rules(robots_txt: str) -> dict[str, str]:
    """Retorna {bot: 'allow'|'partial'|'block'|'unspecified'}.

    Regras explícitas para um bot vencem as regras de '*'.
    Dentro de um grupo, mantemos o veredito mais restritivo encontrado
    (conservador de propósito: preferimos alertar demais a alertar de menos).
    """
    wildcard: dict[str, str] = {}
    explicit: dict[str, str] = {}

    current: list[str] = []

    for raw_line in robots_txt.splitlines():
        line = raw_line.split("#", 1)[0].strip()
        if not line or ":" not in line:
            continue

        directive, _, value = line.partition(":")
        directive = directive.strip().lower()
        value = value.strip()

        if directive == "user-agent":
            agent = value.lower()
            if agent == "*":
                current = ["*"]
            elif agent in AI_CRAWLERS:
                current = [agent]
            else:
                current = []
            continue

        if directive not in {"allow", "disallow"} or not current:
            continue

        verdict = _verdict_for(value, directive)
        for agent in current:
            target = wildcard if agent == "*" else explicit
            previous = target.get(agent)
            if previous is None or _RANK[verdict] > _RANK[previous]:
                target[agent] = verdict

    rules: dict[str, str] = {}
    for bot in AI_CRAWLERS:
        if bot in explicit:
            rules[bot] = explicit[bot]
        elif "*" in wildcard:
            rules[bot] = wildcard["*"]
        else:
            rules[bot] = "unspecified"
    return rules


def _sitemap_candidates(robots_txt: str | None, base: str) -> list[str]:
    found: list[str] = []
    if robots_txt:
        for line in robots_txt.splitlines():
            if line.lower().startswith("sitemap:"):
                candidate = line.split(":", 1)[1].strip()
                if candidate:
                    found.append(candidate)
    if not found:
        found.append(urljoin(base + "/", "sitemap.xml"))
    return found


def _count_sitemap_urls(xml: str | None) -> int:
    if not xml:
        return 0
    return len(re.findall(r"<loc\b", xml, flags=re.IGNORECASE))


def _collect_sitemap(base: str, robots_txt: str | None) -> tuple[str | None, int | None, int]:
    candidates = _sitemap_candidates(robots_txt, base)
    last_status: int | None = None
    for candidate in candidates:
        status, xml = fetch_text(candidate)
        last_status = status
        count = _count_sitemap_urls(xml)
        if count > 0:
            return candidate, status, count
    return (candidates[0] if candidates else None), last_status, 0


def collect_site_facts(page_url: str, robots_txt: str | None = None) -> SiteFacts:
    """Coleta robots.txt / sitemap.xml / llms.txt. Reaproveita robots já baixado."""
    base = origin_of(page_url)

    if robots_txt is None:
        robots_status, robots_txt = fetch_text(urljoin(base + "/", "robots.txt"))
    else:
        robots_status = 200

    sitemap_url, sitemap_status, sitemap_count = _collect_sitemap(base, robots_txt)

    llms_status, llms_txt = fetch_text(urljoin(base + "/", "llms.txt"))
    llms_full_status, _ = fetch_text(urljoin(base + "/", "llms-full.txt"))

    return SiteFacts(
        robots_txt=robots_txt,
        robots_status=robots_status,
        sitemap_url=sitemap_url,
        sitemap_status=sitemap_status,
        sitemap_url_count=sitemap_count,
        llms_txt=llms_txt[:20000] if llms_txt else None,
        llms_status=llms_status,
        llms_full_status=llms_full_status,
        ai_crawler_rules=parse_robots_ai_rules(robots_txt or ""),
    )