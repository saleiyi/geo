"""Testes do pipeline. São poucos de propósito - cobrem os erros que já cometemos.

Regra: todo bug encontrado em produção vira um teste aqui.
"""

from __future__ import annotations

import pytest

from mandapi_geo.analyzers import geo as geo_analyzer
from mandapi_geo.analyzers import seo as seo_analyzer
from mandapi_geo.fetcher import FetchResult, parse_robots_ai_rules
from mandapi_geo.models import SiteFacts
from mandapi_geo.parser import parse_page
from mandapi_geo.scoring import area_score, build_area, build_scorecard, grade_for

GOOD_HTML = """<!doctype html>
<html lang="pt-BR">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Assessoria contábil em São Paulo | Contabilidade Silva</title>
  <meta name="description" content="Assessoria contábil para pequenas empresas em São Paulo. Abertura de empresa em até 5 dias, contabilidade mensal e impostos sem dor de cabeça.">
  <link rel="canonical" href="https://exemplo.com.br/">
  <script type="application/ld+json">
  {
    "@context": "https://schema.org",
    "@type": "Organization",
    "name": "Contabilidade Silva",
    "url": "https://exemplo.com.br/",
    "sameAs": ["https://www.instagram.com/exemplo"],
    "author": {"@type": "Person", "name": "Ana Silva"},
    "datePublished": "2025-01-10",
    "dateModified": "2026-08-01"
  }
  </script>
</head>
<body>
<main>
  <h1>Assessoria contábil em São Paulo</h1>
  <p>Somos um escritório de contabilidade com 12 anos de experiência e mais de 400 clientes atendidos em São Paulo. Abrimos sua empresa em até 5 dias úteis.</p>
  <h2>Como funciona?</h2>
  <p>O processo leva 3 etapas e 5 dias úteis no total.</p>
  <ul><li>Etapa 1</li><li>Etapa 2</li><li>Etapa 3</li></ul>
  <h2>Quanto custa?</h2>
  <p>O plano mensal começa em R$ 290.</p>
  <table><tr><td>Plano</td><td>Preço</td></tr></table>
</main>
</body>
</html>
"""


def make_page(html: str = GOOD_HTML) -> object:
    fetch = FetchResult(
        url="https://exemplo.com.br/",
        final_url="https://exemplo.com.br/",
        status_code=200,
        html=html,
        content_bytes=len(html.encode("utf-8")),
        elapsed_ms=180,
    )
    return parse_page(fetch)


# ---------------------------------------------------------------- robots.txt

def test_robots_disallow_root_blocks_everything() -> None:
    rules = parse_robots_ai_rules("User-agent: GPTBot\nDisallow: /\n")
    assert rules["gptbot"] == "block"
    # Quem não foi citado fica indefinido, não bloqueado.
    assert rules["claudebot"] == "unspecified"


def test_robots_wildcard_applies_to_all_bots() -> None:
    rules = parse_robots_ai_rules("User-agent: *\nDisallow: /\n")
    assert rules["gptbot"] == "block"
    assert rules["perplexitybot"] == "block"


def test_robots_explicit_rule_beats_wildcard() -> None:
    rules = parse_robots_ai_rules(
        "User-agent: *\nDisallow: /\n\nUser-agent: ClaudeBot\nDisallow:\n"
    )
    assert rules["claudebot"] == "allow"
    assert rules["gptbot"] == "block"


def test_robots_specific_path_is_partial_not_block() -> None:
    rules = parse_robots_ai_rules("User-agent: GPTBot\nDisallow: /admin\n")
    assert rules["gptbot"] == "partial"


# ------------------------------------------- regressão: falso positivo (bug real)

def test_missing_robots_does_not_claim_bots_are_blocked() -> None:
    """Bug encontrado rodando contra example.com.

    Sem robots.txt, o relatório afirmava 'Bots de IA estão bloqueados'.
    HTTP 404 significa ausência de regras, não uma falha de acesso declarada.
    """
    page = make_page()
    site = SiteFacts(robots_txt=None, robots_status=404)

    checks, issues = geo_analyzer.analyze(page, site)

    crawler_check = next(c for c in checks if c.id == "geo.ai_crawlers")
    assert crawler_check.status == "pass"
    assert "bloqueado" not in (crawler_check.value or "").lower()

    crawler_issues = [i for i in issues if i.id == "geo.ai_crawlers"]
    assert crawler_issues == []


def test_blocked_search_bots_produce_actionable_issue() -> None:
    page = make_page()
    site = SiteFacts(
        robots_txt="User-agent: OAI-SearchBot\nDisallow: /\n",
        robots_status=200,
        ai_crawler_rules=parse_robots_ai_rules("User-agent: OAI-SearchBot\nDisallow: /\n"),
    )
    checks, issues = geo_analyzer.analyze(page, site)
    crawler_check = next(c for c in checks if c.id == "geo.ai_crawlers")
    assert crawler_check.status == "fail"
    crawler_issue = next(i for i in issues if i.id == "geo.ai_crawlers")
    assert crawler_issue.severity == "high"


# ------------------------------------------------------------------- parsing

def test_parser_extracts_core_facts() -> None:
    page = make_page()
    assert page.lang == "pt-BR"
    assert page.h1_count == 1
    assert page.h2_count == 2
    assert page.has_viewport is True
    assert page.is_https is True
    assert page.has_organization_schema is True
    assert page.author_name == "Ana Silva"
    assert page.date_modified == "2026-08-01"
    assert page.images_total == 0
    assert "assessoria" in page.text.lower()


def test_parser_counts_question_headings() -> None:
    page = make_page()
    # "Como funciona?" e "Quanto custa?" são perguntas.
    assert len(page.question_headings) >= 2


def test_parser_survives_broken_jsonld() -> None:
    broken = GOOD_HTML.replace('"@type": "Organization",', "")
    page = make_page(broken)
    # Não pode explodir; só perde o schema.
    assert page.h1_count == 1


def test_parser_survives_empty_html() -> None:
    page = make_page("")
    assert page.h1_count == 0
    assert page.title is None


# -------------------------------------------------------------------- score

def test_well_optimized_page_scores_high() -> None:
    page = make_page()
    site = SiteFacts(
        robots_txt="User-agent: *\nAllow: /\nSitemap: https://exemplo.com.br/sitemap.xml\n",
        robots_status=200,
        sitemap_url="https://exemplo.com.br/sitemap.xml",
        sitemap_status=200,
        sitemap_url_count=42,
        llms_txt="# Contabilidade Silva\n",
        llms_status=200,
        ai_crawler_rules=parse_robots_ai_rules("User-agent: *\nAllow: /\n"),
    )
    seo_checks, seo_issues = seo_analyzer.analyze(page, site)
    geo_checks, geo_issues = geo_analyzer.analyze(page, site)

    areas = [
        build_area("seo", seo_checks, seo_issues),
        build_area("geo", geo_checks, geo_issues),
    ]
    card = build_scorecard(areas)

    assert card.seo >= 75, f"SEO inesperadamente baixo: {card.seo}"
    assert card.geo >= 70, f"GEO inesperadamente baixo: {card.geo}"
    assert card.grade in {"A", "B"}


def test_bare_page_reports_missing_technical_basics() -> None:
    page = make_page("<html><body><h1>Oi</h1></body></html>")
    site = SiteFacts(robots_status=404)
    seo_checks, seo_issues = seo_analyzer.analyze(page, site)
    geo_checks, geo_issues = geo_analyzer.analyze(page, site)
    areas = [
        build_area("seo", seo_checks, seo_issues),
        build_area("geo", geo_checks, geo_issues),
    ]
    card = build_scorecard(areas)
    # Crawl permissions can pass even on an empty page. Assert actual defects,
    # rather than forcing an arbitrary combined score with optional-file penalties.
    assert card.seo < 55
    failures = {item.id for item in seo_checks if item.status == "fail"}
    assert {"seo.title", "seo.meta_description", "seo.viewport"} <= failures
    assert "heurística" in card.summary


def test_area_score_is_bounded() -> None:
    page = make_page()
    site = SiteFacts()
    checks, _ = seo_analyzer.analyze(page, site)
    score = area_score(checks)
    assert 0 <= score <= 100


@pytest.mark.parametrize(
    "score,expected",
    [(100, "A"), (85, "A"), (84, "B"), (70, "B"), (55, "C"), (40, "D"), (39, "F")],
)
def test_grade_boundaries(score: int, expected: str) -> None:
    assert grade_for(score) == expected
