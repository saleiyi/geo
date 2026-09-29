"""Orquestrador: URL -> ScanReport.

Esta é a única função que o resto da aplicação precisa chamar.
"""

from __future__ import annotations

import time
from urllib.parse import urlparse

from .analyzers import geo as geo_analyzer
from .analyzers import seo as seo_analyzer
from .fetcher import collect_site_facts, fetch_page, normalize_url
from .models import ScanReport
from .parser import parse_page
from .scoring import build_area, build_scorecard, sort_issues


class ScanError(RuntimeError):
    """Falha ao obter ou processar a página. A mensagem é exibida ao usuário."""


def scan(url: str, keyword: str | None = None, ai_summary: bool = False, language: str = "pt-BR") -> ScanReport:
    started = time.perf_counter()
    target = normalize_url(url)

    fetch = fetch_page(target)
    if not fetch.ok:
        reason = fetch.error or f"HTTP {fetch.status_code}"
        raise ScanError(f"Não foi possível acessar {target}: {reason}")

    page = parse_page(fetch)
    site = collect_site_facts(fetch.final_url or target)

    seo_checks, seo_issues = seo_analyzer.analyze(page, site)
    geo_checks, geo_issues = geo_analyzer.analyze(page, site)
    # Only truncate the returned evidence after every analyzer has seen the full text.
    page.text = page.text[:5000]

    areas = [
        build_area("seo", seo_checks, seo_issues),
        build_area("geo", geo_checks, geo_issues),
    ]

    report = ScanReport(
        target_url=target,
        requested_keyword=keyword,
        domain=urlparse(fetch.final_url or target).netloc,
        elapsed_ms=int((time.perf_counter() - started) * 1000),
        score=build_scorecard(areas),
        areas=areas,
        issues=sort_issues(seo_issues + geo_issues),
        facts=page,
        site=site,
    )

    if ai_summary:
        from .i18n import localize_report
        from .report import generate_ai_summary

        summary = generate_ai_summary(localize_report(report, language), language=language)
        if summary:
            report.ai_summary = summary
            report.engine = "rules-v2+llm"

    return report
