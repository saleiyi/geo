"""Evidence boundaries and meaningful crawler/indexing regressions; no network."""

import pytest

from mandapi_geo.analyzers import geo, seo
from mandapi_geo.fetcher import FetchResult
from mandapi_geo.models import ScanReport, SiteFacts
from mandapi_geo.parser import parse_page
from mandapi_geo.report import _build_prompt, to_markdown
from mandapi_geo.scoring import area_score, build_area, build_scorecard


def page(html="<html><body><h1>Example</h1><p>A useful public page.</p></body></html>", headers=None):
    return parse_page(FetchResult(url="https://example.com/", final_url="https://example.com/", status_code=200, html=html, headers=headers or {}))


def check(facts, check_id, site=None):
    checks, _ = geo.analyze(facts, site or SiteFacts())
    return next(item for item in checks if item.id == check_id)


@pytest.mark.parametrize("directives", ["noindex", "none", "NOINDEX, NOFOLLOW"])
def test_generic_header_prevents_false_indexability_pass(directives):
    facts = page(headers={"x-robots-tag": directives})
    assert check(facts, "geo.indexable").status == "fail"


def test_nofollow_is_not_noindex():
    facts = page(headers={"x-robots-tag": "nofollow"})
    assert check(facts, "geo.indexable").status == "pass"
    assert "nofollow" in check(facts, "geo.link_following").value


def test_agent_specific_rules_do_not_leak_into_search():
    facts = page(headers={"x-robots-tag": "gptbot: noindex, nofollow"})
    assert check(facts, "geo.indexable").status == "pass"
    facts = page(headers={"x-robots-tag": "googlebot: noindex, nofollow"})
    result = check(facts, "geo.indexable")
    assert result.status == "fail"
    assert "Googlebot" in result.value
    assert "OAI-SearchBot" not in result.value


def test_repeated_headers_preserve_agent_scope():
    facts = page(headers={"x-robots-tag": "gptbot: noindex\nnofollow"})
    assert check(facts, "geo.indexable").status == "pass"
    assert "OAI-SearchBot" in check(facts, "geo.link_following").value


def test_duplicate_meta_rules_combine_restrictively():
    facts = page('<html><head><meta name="robots" content="index"><meta name="robots" content="none"></head><body></body></html>')
    assert check(facts, "geo.indexable").status == "fail"
    assert "noindex" in facts.robots_directives["*"]


def test_googlebot_meta_and_zero_snippet_are_observed():
    facts = page('<html><head><meta name="googlebot" content="noindex"></head></html>')
    assert check(facts, "geo.indexable").status == "fail"
    facts = page(headers={"x-robots-tag": "max-snippet: 0"})
    assert check(facts, "geo.indexable").status == "warn"


def test_training_opt_out_and_optional_llms_do_not_change_score():
    facts = page()
    baseline = SiteFacts(robots_status=200, robots_txt="User-agent: *\nAllow: /", ai_crawler_rules={"oai-searchbot": "allow"}, llms_status=404)
    variant = baseline.model_copy(update={"ai_crawler_rules": {"oai-searchbot": "allow", "gptbot": "block", "claudebot": "block", "google-extended": "block"}, "llms_status": 200, "llms_txt": "# Optional context"})
    base_checks, _ = geo.analyze(facts, baseline)
    new_checks, issues = geo.analyze(facts, variant)
    assert area_score(base_checks) == area_score(new_checks)
    assert not any(issue.id in {"geo.llms_txt", "geo.training_bots", "geo.ai_crawlers"} for issue in issues)
    assert all(item.status == "info" and item.weight == 0 for item in new_checks if item.id in {"geo.llms_txt", "geo.training_bots"})


def test_adding_faq_or_unverified_numbers_cannot_inflate_score():
    baseline = page()
    variant = baseline.model_copy(update={"has_faq_schema": True, "question_headings": ["What?", "How?"], "number_signals": 100})
    before, _ = geo.analyze(baseline, SiteFacts())
    after, issues = geo.analyze(variant, SiteFacts())
    assert area_score(before) == area_score(after)
    assert not any(item.id in {"geo.faq", "geo.citation_signals"} for item in issues)


@pytest.mark.parametrize("status,robots,expected", [(404, None, "pass"), (410, None, "pass"), (503, None, "info"), (None, None, "info"), (200, None, "info"), (200, "", "pass")])
def test_missing_unavailable_and_empty_robots_are_distinguished(status, robots, expected):
    site = SiteFacts(robots_status=status, robots_txt=robots)
    assert check(page(), "geo.ai_crawlers", site).status == expected
    _, issues = seo.analyze(page(), site)
    assert not any(issue.id == "seo.robots" for issue in issues)


def test_word_count_is_an_observation_not_a_minimum_ranking_requirement():
    checks, issues = seo.analyze(page(), SiteFacts())
    volume = next(item for item in checks if item.id == "seo.word_count")
    assert volume.status == "info" and volume.weight == 0
    assert not any(issue.id == "seo.word_count" for issue in issues)


def test_chinese_content_does_not_receive_latin_length_penalties():
    facts = page('<html lang="zh-CN"><head><title>专业网站优化服务</title><meta name="description" content="帮助企业改善网站技术基础，清晰展示专业知识。"></head><body><h1>网站优化</h1><h2>什么是生成式搜索优化？</h2><p>专业网站优化服务帮助企业改善网站技术基础。</p></body></html>')
    checks, issues = seo.analyze(facts, SiteFacts())
    assert all(item.status == "info" for item in checks if item.id in {"seo.title", "seo.meta_description", "seo.word_count"})
    assert not any(item.id in {"seo.title", "seo.meta_description", "seo.word_count"} for item in issues)
    assert facts.word_count > 10
    assert facts.question_headings == ["什么是生成式搜索优化？"]


def test_short_chinese_opening_is_preserved_and_not_penalized():
    facts = page('<html lang="zh-CN"><body><p>导航</p><main><p>我们帮助企业优化网站。</p></main></body></html>')
    assert facts.first_paragraph == "我们帮助企业优化网站。"
    assert facts.first_paragraph_length == len(facts.first_paragraph)
    result = check(facts, "geo.answer_first")
    assert result.status == "info" and result.weight == 0


def test_long_first_paragraph_length_is_not_silently_truncated():
    facts = page("<html><main><p>" + "abcd " * 200 + "</p></main></html>")
    assert facts.first_paragraph_length == 999
    assert len(facts.first_paragraph) == 600
    assert "999" in check(facts, "geo.answer_first").value


def test_optional_schema_and_content_formats_do_not_change_score():
    baseline = page()
    variant = baseline.model_copy(update={"jsonld_types": ["Organization"], "has_organization_schema": True, "list_count": 10, "table_count": 5})
    for analyzer in (seo, geo):
        before, _ = analyzer.analyze(baseline, SiteFacts())
        after, issues = analyzer.analyze(variant, SiteFacts())
        assert area_score(before) == area_score(after)
        assert not any(item.id in {"seo.schema", "geo.entity", "geo.structured"} for item in issues)


@pytest.mark.parametrize("status", [None, 200, 403, 429, 500, 503])
def test_unconfirmed_sitemap_is_not_reported_absent(status):
    checks, issues = seo.analyze(page(), SiteFacts(sitemap_status=status))
    result = next(item for item in checks if item.id == "seo.sitemap")
    assert result.status == "info" and result.weight == 0
    assert not any(item.id == "seo.sitemap" for item in issues)


def test_missing_sitemap_is_low_priority_contextual_advice():
    checks, issues = seo.analyze(page(), SiteFacts(sitemap_status=404))
    result = next(item for item in checks if item.id == "seo.sitemap")
    assert result.status == "warn"
    assert next(item for item in issues if item.id == "seo.sitemap").severity == "low"


def test_decorative_alt_is_distinct_from_missing_attribute():
    facts = page('<html><body><img src="photo" alt="Portrait"><img src="decoration" alt=""><img src="unknown"></body></html>')
    assert facts.images_with_alt == 1
    assert facts.images_with_empty_alt == 1
    checks, issues = seo.analyze(facts, SiteFacts())
    result = next(item for item in checks if item.id == "seo.image_alt")
    assert "1 sem atributo alt" in result.value
    assert "1 de 3" in next(item for item in issues if item.id == "seo.image_alt").detail
    decoration = page('<html><body><img src="decoration" alt=""></body></html>')
    checks, issues = seo.analyze(decoration, SiteFacts())
    assert next(item for item in checks if item.id == "seo.image_alt").status == "pass"
    assert not any(item.id == "seo.image_alt" for item in issues)


def test_heading_order_and_full_text_survive_parsing():
    text = "long useful content " * 1500
    facts = page(f"<html><body><h1>A</h1><h3>B</h3><h2>C</h2><p>{text} FINAL_EVIDENCE 98765</p></body></html>")
    assert [level for level, _ in facts.headings] == [1, 3, 2]
    assert facts.text.endswith("FINAL_EVIDENCE 98765")
    assert len(facts.text) > 20000


def test_scan_truncates_only_after_analysis(monkeypatch):
    from mandapi_geo import scanner

    fetch = FetchResult(url="https://example.com/", final_url="https://example.com/", status_code=200, html="<html><body><p>" + "a " * 15000 + "END</p></body></html>")
    observed = []
    original = scanner.geo_analyzer.analyze

    def analyze(facts, site):
        observed.append(facts.text.endswith("END"))
        return original(facts, site)

    monkeypatch.setattr(scanner, "fetch_page", lambda url: fetch)
    monkeypatch.setattr(scanner, "collect_site_facts", lambda url: SiteFacts())
    monkeypatch.setattr(scanner.geo_analyzer, "analyze", analyze)
    report = scanner.scan("https://example.com/")
    assert observed == [True]
    assert len(report.facts.text) == 5000
    assert report.scope == "single_page" and report.engine == "rules-v2"


def test_report_and_llm_prompt_describe_evidence_limits():
    facts = page()
    checks, issues = geo.analyze(facts, SiteFacts())
    report = ScanReport(target_url=facts.url, score=build_scorecard([build_area("geo", checks, issues)]))
    markdown = to_markdown(report)
    prompt = _build_prompt(report)
    assert "Escopo e limites" in markdown
    assert "não medem ranking" in markdown
    assert "rules-v2" in markdown
    assert "Não invente números, perdas de clientes" in prompt
    assert "Write in English." in _build_prompt(report, "en")
    assert "Write in Simplified Chinese." in _build_prompt(report, "zh-CN")
    assert "praticamente invisível" not in report.score.summary
    assert "pontos recuperáveis" not in markdown or "não representa pontos recuperáveis" in markdown
