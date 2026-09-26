"""Fetch public pages and auxiliary resources with bounded, validated requests."""

from __future__ import annotations

import re
import time
import xml.etree.ElementTree as ET
import zlib
from dataclasses import dataclass, field
from urllib.parse import quote, urljoin, urlparse

import httpcore
import httpx

from .config import load_settings
from .models import SiteFacts
from .network import PublicHTTPTransport, UnsafeURL, normalize_public_url

AI_CRAWLERS: tuple[str, ...] = (
    "gptbot", "oai-searchbot", "chatgpt-user", "claudebot", "claude-searchbot",
    "claude-web", "anthropic-ai", "perplexitybot", "googlebot", "google-extended",
    "applebot-extended", "ccbot", "bytespider", "meta-externalagent", "cohere-ai",
    "amazonbot", "yandexbot", "youbot", "diffbot",
)

HTML_LIMIT = 2 * 1024 * 1024
AUX_LIMIT = 512 * 1024
MAX_REDIRECTS = 5
MAX_SITEMAPS = 3


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
    return normalize_public_url(raw)


def origin_of(url: str) -> str:
    parsed = urlparse(url)
    return f"{parsed.scheme}://{parsed.netloc}"


def _client(deadline: float | None = None) -> httpx.Client:
    settings = load_settings()
    deadline = deadline if deadline is not None else time.monotonic() + settings.scan_timeout
    return httpx.Client(
        timeout=settings.scan_timeout,
        follow_redirects=False,
        trust_env=False,
        transport=PublicHTTPTransport(deadline),
        headers={
            "User-Agent": settings.user_agent,
            "Accept": "text/html,application/xhtml+xml,text/plain,text/markdown,application/xml;q=0.9",
            "Accept-Encoding": "gzip, deflate",
            "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
        },
    )


def _check_deadline(deadline: float) -> None:
    if time.monotonic() >= deadline:
        raise httpx.ReadTimeout("Request deadline exceeded")


def _read_body(response: httpx.Response, limit: int, deadline: float) -> bytes:
    """Limit decoded output during decompression, including compressed bombs."""
    encoding = response.headers.get("content-encoding", "identity").strip().lower()
    if encoding not in {"", "identity", "gzip", "deflate"}:
        raise ValueError("O site usa uma compressão não suportada para esta análise.")
    decoder = zlib.decompressobj(31 if encoding == "gzip" else 15) if encoding in {"gzip", "deflate"} else None
    chunks: list[bytes] = []
    size = raw_size = 0
    first_chunk = True
    if decoder is None:
        try:
            length = int(response.headers.get("content-length", "0"))
        except ValueError:
            length = 0
        if length > limit:
            raise ValueError("O recurso excede o limite de tamanho permitido para análise.")
    for raw in response.iter_raw(chunk_size=16384):
        _check_deadline(deadline)
        raw_size += len(raw)
        if raw_size > limit * 2 + 65536:
            raise ValueError("O recurso excede o limite de tamanho permitido para análise.")
        pending = raw
        while pending:
            if decoder is None:
                chunk, pending = pending, b""
            else:
                try:
                    chunk = decoder.decompress(pending, limit - size + 1)
                except zlib.error:
                    if encoding != "deflate" or not first_chunk:
                        raise ValueError("O site enviou conteúdo comprimido inválido.") from None
                    decoder = zlib.decompressobj(-15)
                    chunk = decoder.decompress(pending, limit - size + 1)
                pending = decoder.unconsumed_tail
                if decoder.eof and decoder.unused_data:
                    pending = decoder.unused_data
                    if encoding != "gzip":
                        raise ValueError("O site enviou conteúdo comprimido inválido.")
                    decoder = zlib.decompressobj(31)
            first_chunk = False
            size += len(chunk)
            if size > limit:
                raise ValueError("O recurso excede o limite de tamanho permitido para análise.")
            chunks.append(chunk)
            _check_deadline(deadline)
    if decoder is not None and not decoder.eof:
        raise ValueError("O site enviou conteúdo comprimido incompleto.")
    _check_deadline(deadline)
    return b"".join(chunks)


def _resource_kind(url: str) -> str:
    filename = urlparse(url).path.rstrip("/").rsplit("/", 1)[-1].lower()
    if filename == "robots.txt":
        return "robots"
    if filename in {"llms.txt", "llms-full.txt"}:
        return "llms"
    return "sitemap"


def _check_content_type(response: httpx.Response, kind: str) -> None:
    content_type = response.headers.get("content-type", "").split(";", 1)[0].strip().lower()
    allowed = {
        "html": {"text/html", "application/xhtml+xml"},
        "robots": {"text/plain", "text/x-robots-txt"},
        "llms": {"text/plain", "text/markdown", "text/x-markdown"},
        "sitemap": {"application/xml", "text/xml"},
    }
    if content_type not in allowed[kind]:
        if kind == "html":
            raise ValueError("A URL não retornou uma página HTML. Informe a URL de uma página do site.")
        raise ValueError("O recurso auxiliar não retornou o formato esperado.")


def _valid_auxiliary(text: str, kind: str) -> bool:
    if re.search(r"<(?:!doctype\s+html|html|head|body)(?:\s|>)", text[:8192], re.I):
        return False
    if kind == "sitemap":
        if re.search(r"<!\s*(?:DOCTYPE|ENTITY)\b", text, re.I):
            return False
        try:
            root = ET.fromstring(text)
        except ET.ParseError:
            return False
        return root.tag.rsplit("}", 1)[-1] in {"urlset", "sitemapindex"}
    if kind == "llms":
        return bool(re.search(r"^#\s+\S", text, re.M))
    lines = [line.split("#", 1)[0].strip() for line in text.splitlines()]
    return not any(lines) or any(re.match(r"(?:user-agent|sitemap)\s*:", line, re.I) for line in lines)


def _download(url: str, kind: str, limit: int) -> FetchResult:
    started = time.monotonic()
    deadline = started + load_settings().scan_timeout
    result = FetchResult(url=str(url), final_url=str(url), status_code=0)
    try:
        target = normalize_url(url)
        result.url = result.final_url = target
        with _client(deadline) as client:
            for redirects in range(MAX_REDIRECTS + 1):
                _check_deadline(deadline)
                with client.stream("GET", target, follow_redirects=False,
                                   timeout=max(0.001, deadline - time.monotonic())) as response:
                    result.status_code = response.status_code
                    result.final_url = str(response.url)
                    result.headers = {key.lower(): value for key, value in response.headers.items()}
                    if "x-robots-tag" in response.headers:
                        result.headers["x-robots-tag"] = "\n".join(response.headers.get_list("x-robots-tag"))
                    result.redirect_count = redirects
                    if response.status_code in {301, 302, 303, 307, 308}:
                        if redirects == MAX_REDIRECTS:
                            raise ValueError("O site excedeu o limite de 5 redirecionamentos.")
                        location = response.headers.get("location", "")
                        if not location:
                            raise ValueError("O site informou um redirecionamento inválido.")
                        target = normalize_url(urljoin(target, location))
                        continue
                    if response.status_code == 403:
                        raise ValueError("O site bloqueou o acesso do analisador (HTTP 403). Verifique as regras do servidor ou CDN.")
                    if response.status_code == 429:
                        raise ValueError("O site limitou temporariamente as requisições (HTTP 429). Tente novamente mais tarde.")
                    if not 200 <= response.status_code < 300:
                        raise ValueError(f"O site retornou HTTP {response.status_code}. Verifique se a página está disponível.")
                    _check_content_type(response, kind)
                    body = _read_body(response, limit, deadline)
                    try:
                        text = body.decode(response.encoding or "utf-8", errors="replace")
                    except LookupError:
                        text = body.decode("utf-8", errors="replace")
                    if kind != "html" and not _valid_auxiliary(text.lstrip("\ufeff"), kind):
                        raise ValueError("O recurso auxiliar não contém um arquivo válido no formato esperado.")
                    result.html = text
                    result.content_bytes = len(body)
                    break
    except (httpx.TimeoutException, httpcore.TimeoutException):
        result.error = "O site demorou demais para responder. Tente novamente em alguns instantes."
    except (httpx.HTTPError, httpcore.NetworkError, OSError):
        result.error = "Não foi possível acessar o site. Confira o endereço e a disponibilidade do servidor."
    except (UnsafeURL, ValueError) as exc:
        result.error = str(exc)
    except Exception:
        result.error = "Não foi possível analisar este recurso. Verifique a URL e tente novamente."
    result.elapsed_ms = int((time.monotonic() - started) * 1000)
    return result


def fetch_page(url: str) -> FetchResult:
    """Fetch HTML/XHTML. Return a localized error instead of raising exceptions."""
    return _download(url, "html", HTML_LIMIT)


def fetch_text(url: str) -> tuple[int | None, str | None]:
    """Fetch a validated robots, sitemap or llms resource with the same guardrails."""
    try:
        kind = _resource_kind(url)
    except (ValueError, TypeError):
        return None, None
    result = _download(url, kind, AUX_LIMIT)
    return result.status_code or None, result.html if result.ok else None


def _robots_octets(value: str) -> str:
    encoded = quote(value, safe="/%?=&:+,;@!~*'$-._")
    def replace(match: re.Match[str]) -> str:
        char = chr(int(match.group(1), 16))
        return char if char.isascii() and (char.isalnum() or char in "-._~") else match.group(0).upper()
    return re.sub(r"%([0-9a-fA-F]{2})", replace, encoded)


def _matches_robots_pattern(pattern: str, path: str, anchored: bool) -> bool:
    # Splitting wildcard segments avoids exponential regex backtracking on
    # hostile robots files containing many overlapping '*' expressions.
    parts = pattern.split("*")
    if not path.startswith(parts[0]):
        return False
    if len(parts) == 1:
        return not anchored or path == pattern
    position = len(parts[0])
    for part in parts[1:-1]:
        found = path.find(part, position)
        if found < 0:
            return False
        position = found + len(part)
    if anchored:
        return path.endswith(parts[-1]) and len(path) - len(parts[-1]) >= position
    return path.find(parts[-1], position) >= 0


def _path_verdict(rules: list[tuple[str, str]], path: str) -> str:
    if path.split("?", 1)[0] == "/robots.txt":
        return "allow"
    matches: list[tuple[int, bool]] = []
    for directive, value in rules:
        if not value:
            continue
        pattern = _robots_octets(value)
        specificity = len(pattern)
        anchored = pattern.endswith("$")
        if anchored:
            pattern = pattern[:-1]
        if _matches_robots_pattern(pattern, path, anchored):
            matches.append((specificity, directive == "allow"))
    return "allow" if not matches or max(matches)[1] else "block"


def _summary_verdict(rules: list[tuple[str, str]]) -> str:
    allows = {value for directive, value in rules if directive == "allow" and value}
    disallows = {value for directive, value in rules if directive == "disallow" and value and value not in allows}
    if not disallows:
        return "allow"
    if any(value in {"/", "/*", "*"} for value in disallows):
        return "partial" if allows else "block"
    return "partial"


def parse_robots_ai_rules(robots_txt: str, target_url: str | None = None) -> dict[str, str]:
    """Merge groups, prefer explicit agents, and apply longest matching path.

    target_url enables per-page verdicts; omit it for whole-site summaries.
    """
    groups: list[tuple[list[str], list[tuple[str, str]]]] = []
    agents: list[str] = []
    directives: list[tuple[str, str]] = []
    seen_rule = False
    for raw_line in robots_txt.lstrip("\ufeff").splitlines():
        line = raw_line.split("#", 1)[0].strip()
        if ":" not in line:
            continue
        directive, value = (part.strip() for part in line.split(":", 1))
        directive = directive.lower()
        if directive == "user-agent":
            if seen_rule:
                groups.append((agents, directives))
                agents, directives, seen_rule = [], [], False
            if value:
                agents.append(value.lower())
        elif directive in {"allow", "disallow"} and agents:
            seen_rule = True
            directives.append((directive, value))
    if agents:
        groups.append((agents, directives))
    path = None
    if target_url is not None:
        parsed = urlparse(target_url)
        path = _robots_octets((parsed.path or "/") + (f"?{parsed.query}" if parsed.query else ""))
    result: dict[str, str] = {}
    for bot in AI_CRAWLERS:
        selected = [rules for names, rules in groups if bot in names]
        if not selected:
            selected = [rules for names, rules in groups if "*" in names]
        if not selected:
            result[bot] = "unspecified"
            continue
        merged = [rule for rules in selected for rule in rules]
        result[bot] = _path_verdict(merged, path) if path is not None else _summary_verdict(merged)
    return result


def _sitemap_candidates(robots_txt: str | None, base: str) -> list[str]:
    found: list[str] = []
    if robots_txt:
        for line in robots_txt.splitlines():
            directive, separator, value = line.partition(":")
            if separator and directive.strip().lower() == "sitemap":
                value = value.split("#", 1)[0].strip()
                if not value:
                    continue
                try:
                    candidate = normalize_url(urljoin(base + "/", value))
                except ValueError:
                    continue
                if candidate not in found:
                    found.append(candidate)
                if len(found) == MAX_SITEMAPS:
                    break
    return found or [urljoin(base + "/", "sitemap.xml")]


def _count_sitemap_urls(xml: str | None) -> int:
    if not xml or not _valid_auxiliary(xml, "sitemap"):
        return 0
    root = ET.fromstring(xml)
    return sum(1 for child in root.iter() if child.tag.rsplit("}", 1)[-1] == "loc" and (child.text or "").strip())


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
        ai_crawler_rules=parse_robots_ai_rules(robots_txt or "", page_url),
    )
