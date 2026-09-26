"""Public API, localization and multilingual SEO contracts; no external traffic."""
from dataclasses import replace
from pathlib import Path
import ast
import json
import xml.etree.ElementTree as ET

from bs4 import BeautifulSoup
from fastapi.testclient import TestClient
import pytest

import mandapi_geo.api as api
from mandapi_geo.config import load_settings
from mandapi_geo.fetcher import FetchResult
from mandapi_geo.i18n import CHECK_TEXT, localize_report
from mandapi_geo.models import ScanReport, SiteFacts
from mandapi_geo.parser import parse_page
from mandapi_geo.analyzers import seo, geo
from mandapi_geo.scoring import build_area, build_scorecard, sort_issues
from mandapi_geo.scanner import ScanError


def fixture_report():
    p = parse_page(FetchResult(url='https://example.com/', final_url='https://example.com/', status_code=200,
        html='<html lang="en"><head><title>Example domain</title></head><body><main><h1>Example</h1><p>A public page used for documentation and illustrative examples.</p></main></body></html>'))
    site = SiteFacts(robots_status=404, llms_status=404, sitemap_status=404)
    areas = [build_area(name, *engine.analyze(p, site)) for name, engine in [('seo', seo), ('geo', geo)]]
    return ScanReport(target_url=p.url, domain='example.com', facts=p, site=site, areas=areas,
        score=build_scorecard(areas), issues=sort_issues([i for a in areas for i in a.issues]))


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv('SITE_URL', '')
    monkeypatch.setenv('SITE_INDEXABLE', 'false')
    monkeypatch.setenv('FREE_SCAN_DAILY_LIMIT', '3')
    monkeypatch.setenv('PUBLIC_AI_SUMMARY', 'false')
    load_settings.cache_clear()
    monkeypatch.setattr(api, 'gate', api.ScanGate())
    with TestClient(api.app) as c:
        yield c
    load_settings.cache_clear()


@pytest.mark.parametrize('locale,lang', [('', 'pt-BR'), ('en', 'en'), ('zh', 'zh-CN')])
@pytest.mark.parametrize('slug', ['', 'metodologia', 'privacidade', 'guia-geo'])
def test_localized_pages_have_valid_metadata(client, locale, lang, slug):
    path = '/' + '/'.join(part for part in [locale, slug] if part)
    response = client.get(path)
    assert response.status_code == 200
    assert response.headers['content-language'] == lang
    assert response.headers['x-robots-tag'] == 'noindex, nofollow'
    soup = BeautifulSoup(response.text, 'html.parser')
    assert soup.html['lang'] == lang
    assert len(soup.find_all('h1')) == 1
    assert soup.find('link', rel='canonical')['href'] == 'http://127.0.0.1:8000' + path
    assert {x['hreflang'] for x in soup.find_all('link', rel='alternate')} == {'pt-BR','en','zh-CN','x-default'}
    assert '__SITE_URL__' not in response.text
    for script in soup.find_all('script', type='application/ld+json'):
        assert json.loads(script.string)['@context'] == 'https://schema.org'


def test_assets_are_executable_with_nosniff(client):
    for path in ['app.js','app.en.js','app.zh.js']:
        r = client.get('/assets/' + path)
        assert r.status_code == 200
        assert r.headers['content-type'].startswith('text/javascript')
        assert r.headers['x-content-type-options'] == 'nosniff'
    assert client.get('/assets/styles.css').headers['content-type'].startswith('text/css')


def test_preview_does_not_advertise_indexable_pages(client):
    assert 'Disallow: /' in client.get('/robots.txt').text
    assert not ET.fromstring(client.get('/sitemap.xml').text).findall('{*}url')


def test_public_sitemap_and_host_header_are_safe(client, monkeypatch):
    monkeypatch.setenv('SITE_URL','https://geo.example.com')
    monkeypatch.setenv('SITE_INDEXABLE','true')
    load_settings.cache_clear()
    r = client.get('/en',headers={'host':'evil.example'})
    assert r.status_code == 200
    assert 'evil.example' not in r.text
    assert 'https://geo.example.com/en' in r.text
    assert 'x-robots-tag' not in r.headers
    urls = ET.fromstring(client.get('/sitemap.xml').text).findall('{*}url')
    assert len(urls) == 12
    assert all(len(u.findall('{http://www.w3.org/1999/xhtml}link')) == 4 for u in urls)
    assert 'Sitemap: https://geo.example.com/sitemap.xml' in client.get('/robots.txt').text


@pytest.mark.parametrize('value', ['https://example.com:bad','https://example.com:99999','https://exa mple.com','https://@example.com','https://example.com/sub','https://127.0.0.1'])
def test_site_url_rejects_invalid_origins(monkeypatch, value):
    monkeypatch.setenv('SITE_URL',value)
    load_settings.cache_clear()
    with pytest.raises(ValueError): load_settings()
    load_settings.cache_clear()


@pytest.mark.parametrize('language', ['pt-BR','en','zh-CN'])
def test_api_returns_full_localized_report(client, monkeypatch, language):
    original = fixture_report()
    monkeypatch.setattr(api, 'scan', lambda *a, **k: original)
    r = client.post('/api/scan',json={'url':'https://example.com','language':language})
    assert r.status_code == 200
    body = r.json()
    assert body['scope'] == 'single_page'
    assert body['engine'] == 'rules-v2'
    assert body['limitations']
    assert body['score']['overall'] == original.score.overall
    assert len(body['areas']) == 2
    assert r.headers['cache-control'] == 'no-store'
    if language != 'pt-BR':
        combined = json.dumps({'areas':body['areas'],'issues':body['issues']}, ensure_ascii=False)
        for leftover in ['não verificado','ausente','presente','palavras','caracteres','não encontrado']:
            assert leftover not in combined
        assert original.areas[0].label != body['areas'][0]['label']


def test_invalid_url_does_not_spend_quota_or_fetch(client, monkeypatch):
    def unexpected(*a, **k): pytest.fail('network must not run')
    monkeypatch.setattr(api, 'scan', unexpected)
    for _ in range(4):
        r=client.post('/api/scan',json={'url':'http://127.0.0.1','language':'en'})
        assert r.status_code == 400
    assert api.gate._counts == {}


def test_quota_rejects_forwarded_ip_spoofing(client, monkeypatch):
    monkeypatch.setattr(api, 'scan', lambda *a, **k: fixture_report())
    for n in range(3):
        assert client.post('/api/scan',json={'url':'https://example.com'},headers={'x-forwarded-for':f'8.8.8.{n}'}).status_code == 200
    r = client.post('/api/scan',json={'url':'https://example.com'})
    assert r.status_code == 429
    assert int(r.headers['retry-after']) > 0
    assert api.gate._active == 0


def test_scanner_failure_releases_slot_and_localizes(client, monkeypatch):
    def failed(*a, **k): raise ScanError('HTTP 429')
    monkeypatch.setattr(api, 'scan', failed)
    r = client.post('/api/scan',json={'url':'https://example.com','language':'zh-CN'})
    assert r.status_code == 422
    assert '频率' in r.json()['detail']
    assert api.gate._active == 0


def test_request_limits_and_paid_summary_guard(client):
    r = client.post('/api/scan',content='x'*8193)
    assert r.status_code == 413
    assert r.headers['cache-control'] == 'no-store'
    assert r.headers['x-content-type-options'] == 'nosniff'
    assert client.post('/api/scan',json={'url':'https://example.com','ai_summary':True}).status_code == 400
    assert client.post('/api/scan',json={'url':'https://example.com','language':'bogus'}).status_code == 422
    assert client.post('/api/scan',json={'url':'x'*2049}).status_code == 422


def test_scan_gate_busy_does_not_spend_quota(client):
    gate = api.ScanGate()
    gate.enter('a','en')
    gate.enter('b','en')
    with pytest.raises(api.HTTPException) as exc: gate.enter('c','en')
    assert exc.value.status_code == 503
    assert len(gate._counts) == 2
    gate.leave()
    gate.enter('c','en')


def test_localization_covers_all_rule_ids():
    ids = set()
    for file in ['seo.py','geo.py']:
        tree = ast.parse((Path('mandapi_geo/analyzers')/file).read_text(encoding='utf-8-sig'))
        ids.update(n.value.value for n in ast.walk(tree) if isinstance(n,ast.keyword) and n.arg=='cid' and isinstance(n.value,ast.Constant))
    assert not ids - CHECK_TEXT.keys()


def test_unknown_robots_stays_unknown_in_translation():
    report = fixture_report()
    report.site = SiteFacts(robots_status=200,robots_txt=None)
    for lang in ['en','zh-CN']:
        translated = localize_report(report,lang)
        checks = {c.id:c for a in translated.areas for c in a.checks}
        assert checks['seo.robots'].value in {'Not verified','未能验证'}
        assert checks['geo.training_bots'].value in {'Not verified','未能验证'}
