"""Public audit API and multilingual, server-rendered marketing pages."""
from __future__ import annotations

import hashlib
import hmac
import mimetypes
import re
import secrets
import threading
import time
from html import escape
from pathlib import Path
from typing import Literal
from xml.sax.saxutils import escape as xml_escape

import anyio
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, PlainTextResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .config import load_settings
from .fetcher import normalize_url
from .i18n import localize_report, message
from .models import ScanReport
from .scanner import ScanError, scan

WEB_DIR = Path(__file__).resolve().parent.parent / "web"
# Windows registry may associate .js with text/plain; nosniff must stay enabled.
mimetypes.init()
mimetypes.add_type("text/javascript", ".js")
mimetypes.add_type("text/css", ".css")
mimetypes.add_type("image/svg+xml", ".svg")
PAGES = {"": "index.html", "metodologia": "metodologia.html", "privacidade": "privacidade.html", "guia-geo": "guia-geo.html"}
LOCALES = {"": "pt-BR", "en": "en", "zh": "zh-CN"}
app = FastAPI(title="MandAPI GEO", version="0.2.0", docs_url=None, redoc_url=None,
              description="Single-page technical SEO and AI search readiness audit.")
app.mount("/assets", StaticFiles(directory=WEB_DIR / "assets", check_dir=False), name="assets")

class ScanIn(BaseModel):
    url: str = Field(min_length=1, max_length=2048)
    keyword: str | None = Field(default=None, max_length=200)
    ai_summary: bool = False
    language: Literal["pt-BR", "en", "zh-CN"] = "pt-BR"

class ScanGate:
    """Single-process UTC daily quota and concurrency guard; restart resets quota.

    The ASGI server must only accept forwarded headers from trusted proxies.
    Multiple replicas require a shared limiter at the edge.
    """
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._salt = secrets.token_bytes(32)
        self._day = int(time.time() // 86400)
        self._counts: dict[str, int] = {}
        self._active = 0

    def enter(self, identity: str, language: str) -> None:
        settings = load_settings()
        now = time.time()
        retry = max(1, int((int(now // 86400) + 1) * 86400 - now))
        with self._lock:
            if self._day != int(now // 86400):
                self._counts.clear()
                self._salt = secrets.token_bytes(32)
                self._day = int(now // 86400)
            key = hmac.new(self._salt, identity.encode(), hashlib.sha256).hexdigest()
            if self._counts.get(key, 0) >= settings.free_scan_daily_limit:
                raise HTTPException(429, message("quota", language), headers={"Retry-After": str(retry)})
            if self._active >= settings.max_concurrent_scans or (key not in self._counts and len(self._counts) >= 10000):
                raise HTTPException(503, message("busy", language), headers={"Retry-After": "15"})
            self._counts[key] = self._counts.get(key, 0) + 1
            self._active += 1

    def leave(self) -> None:
        with self._lock:
            self._active -= 1

gate = ScanGate()

@app.middleware("http")
async def response_headers(request: Request, call_next):
    response = None
    if request.url.path == "/api/scan" and request.method == "POST":
        size = 0
        chunks = []
        try:
            with anyio.fail_after(10):
                async for chunk in request.stream():
                    size += len(chunk)
                    if size > 8192:
                        response = Response('{"detail":"Request body too large."}', status_code=413, media_type="application/json")
                        break
                    chunks.append(chunk)
        except TimeoutError:
            response = Response('{"detail":"Request body timed out."}', status_code=408, media_type="application/json")
        if response is None:
            request._body = b"".join(chunks)
    if response is None:
        response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data:; font-src 'self'; connect-src 'self'; "
        "object-src 'none'; base-uri 'self'; frame-ancestors 'none'; form-action 'self'"
    )
    if request.url.path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Robots-Tag"] = "noindex, nofollow"
    elif not load_settings().site_indexable:
        response.headers["X-Robots-Tag"] = "noindex, nofollow"
    return response

@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "engine": "rules-v2"}

@app.post("/api/scan", response_model=ScanReport)
def api_scan(payload: ScanIn, request: Request) -> ScanReport:
    try:
        target = normalize_url(payload.url)
    except ValueError as exc:
        raise HTTPException(400, message("invalid_url", payload.language)) from exc
    if payload.ai_summary and (not load_settings().public_ai_summary or payload.language != "pt-BR"):
        raise HTTPException(400, message("ai_disabled", payload.language))
    gate.enter(request.client.host if request.client else "unknown", payload.language)
    try:
        report = scan(target, keyword=payload.keyword, ai_summary=payload.ai_summary)
        return localize_report(report, payload.language)
    except ValueError as exc:
        raise HTTPException(400, message("invalid_url", payload.language)) from exc
    except ScanError as exc:
        raise HTTPException(422, message("scan_failed", payload.language, str(exc))) from exc
    finally:
        gate.leave()

def _origin() -> str:
    # Never trust Host/X-Forwarded-Host when creating public canonical URLs.
    return load_settings().site_url or "http://127.0.0.1:8000"

def page_response(slug: str = "", locale: str = "") -> HTMLResponse:
    if slug not in PAGES or locale not in LOCALES:
        raise HTTPException(404, "Page not found")
    path = WEB_DIR / locale / PAGES[slug]
    if not path.is_file():
        raise HTTPException(404, "Page not found")
    settings = load_settings()
    verification = ('<meta name="google-site-verification" content="' + escape(settings.google_site_verification, quote=True) + '">') if settings.google_site_verification else ""
    missing = {'': 'Não informado — versão de prévia.', 'en': 'Not provided — preview version.', 'zh': '尚未提供——预览版本。'}[locale]
    log_notice = getattr(settings, 'privacy_log_notice_' + {'': 'pt', 'en': 'en', 'zh': 'zh'}[locale])
    replacements = {
        '__SITE_URL__': escape(_origin(), quote=True),
        '__INDEX_ROBOTS__': 'index, follow' if settings.site_indexable else 'noindex, nofollow',
        '__GOOGLE_VERIFICATION__': verification,
        '__OPERATOR_NAME__': escape(settings.operator_name or missing),
        '__CONTACT_EMAIL__': escape(settings.contact_email or missing),
        '__HOSTING_PROVIDER__': escape(settings.hosting_provider or missing),
        '__PRIVACY_LOG_NOTICE__': escape(log_notice or missing),
    }
    # Substitute once: operator-provided text must not become a template directive.
    html = re.sub('|'.join(map(re.escape, replacements)), lambda match: replacements[match[0]], path.read_text(encoding='utf-8'))
    return HTMLResponse(html, headers={"Content-Language": LOCALES[locale], "Cache-Control": "no-cache"})

@app.get("/", response_class=HTMLResponse)
def index():
    return page_response()

@app.get("/favicon.ico", include_in_schema=False)
def favicon():
    return FileResponse(WEB_DIR / "assets" / "favicon.svg", media_type="image/svg+xml")

@app.get("/robots.txt", response_class=PlainTextResponse)
def robots():
    if not load_settings().site_indexable:
        return "User-agent: *\nDisallow: /\n"
    return f"User-agent: *\nAllow: /\nDisallow: /api/\nSitemap: {_origin()}/sitemap.xml\n"

@app.get("/sitemap.xml")
def sitemap():
    entries = []
    if load_settings().site_indexable:
        for slug in PAGES:
            alternatives = {lang: _origin() + ("/" + locale if locale else "") + ("/" + slug if slug else ("" if locale else "/")) for locale, lang in LOCALES.items()}
            for url in alternatives.values():
                links = "".join(f'<xhtml:link rel="alternate" hreflang="{lang}" href="{escape(other, quote=True)}"/>' for lang, other in alternatives.items())
                links += f'<xhtml:link rel="alternate" hreflang="x-default" href="{escape(alternatives["pt-BR"], quote=True)}"/>'
                entries.append(f"<url><loc>{xml_escape(url)}</loc>{links}</url>")
    return Response('<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" xmlns:xhtml="http://www.w3.org/1999/xhtml">' + "".join(entries) + "</urlset>", media_type="application/xml")

@app.get("/{first}", response_class=HTMLResponse)
def top_page(first: str):
    return page_response(locale=first) if first in LOCALES else page_response(slug=first)

@app.get("/{locale}/{slug}", response_class=HTMLResponse)
def translated_page(locale: str, slug: str):
    return page_response(slug, locale)
