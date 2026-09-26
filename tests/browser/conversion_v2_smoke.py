"""Optional Edge/Playwright acceptance; offline report fixtures, local API only.

Run with a local preview on port 8000. No production dependency or external scans.
"""
from datetime import datetime, timezone
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from playwright.sync_api import sync_playwright
from mandapi_geo.analyzers import seo, geo
from mandapi_geo.fetcher import FetchResult
from mandapi_geo.i18n import localize_report
from mandapi_geo.models import ScanReport, SiteFacts
from mandapi_geo.parser import parse_page
from mandapi_geo.scoring import build_area, build_scorecard, sort_issues

OUT = ROOT / 'reports' / 'conversion-v2'
SHOTS = ROOT / 'docs' / 'screenshots'
KEY = 'mandapi-geo-baseline-v1'
OUT.mkdir(parents=True, exist_ok=True)


def report(repaired=False, language='en'):
    additions = '<meta name="description" content="A clear, specific summary of this documentation page and the practical examples it contains for people evaluating their technical website improvements."><meta name="viewport" content="width=device-width,initial-scale=1">' if repaired else ''
    html = f'<html lang="en"><head><title>Practical website documentation and examples</title>{additions}</head><body><main><h1>Website documentation</h1><p>This public documentation example demonstrates the same page before and after two technical metadata repairs.</p></main></body></html>'
    facts = parse_page(FetchResult(url='https://example.com/', final_url='https://example.com/', status_code=200, html=html))
    site = SiteFacts(robots_status=404, sitemap_status=404, llms_status=404)
    areas = [build_area(name, *engine.analyze(facts, site)) for name, engine in [('seo', seo), ('geo', geo)]]
    result = ScanReport(target_url=facts.url, domain='example.com', facts=facts, site=site, areas=areas,
        score=build_scorecard(areas), issues=sort_issues([i for a in areas for i in a.issues]),
        scanned_at=datetime(2026, 9, 26, 10 if repaired else 9, tzinfo=timezone.utc))
    return localize_report(result, language).model_dump(mode='json')


def check_width(page):
    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth'), 'horizontal overflow'


def run():
    summary = {'fixture_only': True, 'languages': [], 'errors': []}
    with sync_playwright() as p:
        browser = p.chromium.launch(channel='msedge', headless=True)
        context = browser.new_context(viewport={'width': 375, 'height': 812}, accept_downloads=True)
        context.set_default_timeout(10000)
        page = context.new_page()
        page.on('pageerror', lambda error: summary['errors'].append(str(error)))
        calls = []
        def scan(route):
            data = route.request.post_data_json
            locale = data['language']
            calls.append(locale)
            route.fulfill(json=report(len(calls) > 1, locale))
        page.route('**/api/scan', scan)
        for path, locale in [('/', 'pt-BR'), ('/en', 'en'), ('/zh', 'zh-CN')]:
            page.goto('http://127.0.0.1:8000' + path)
            page.wait_for_function('!!window.GeoComparison')
            assert page.locator('h1').count() == 1
            assert page.locator('.faq-list details').count() >= 8
            check_width(page)
            bounds = {name: page.locator(selector).bounding_box() for name, selector in [('h1', 'h1'), ('input', '#url'), ('cta', '#submit')]}
            assert all(b and b['y'] >= 0 and b['y'] + b['height'] <= 812 for b in bounds.values()), bounds
            assert page.evaluate('localStorage.length') == 0
            summary['languages'].append({'language': locale, 'first_fold': bounds, 'faq': 9})
            if locale == 'zh-CN':
                page.screenshot(path=str(SHOTS/'conversion-v2-after-hero.png'))
                page.screenshot(path=str(SHOTS/'conversion-v2-after-mobile.png'), full_page=True)
        page.set_viewport_size({'width': 1440, 'height': 1000})
        page.screenshot(path=str(SHOTS/'conversion-v2-after-desktop.png'), full_page=True)
        page.set_viewport_size({'width': 375, 'height': 812})
        page.locator('#url').fill('https://example.com/')
        page.locator('#submit').click()
        page.locator('#results').wait_for(state='visible')
        assert page.locator('#top-priorities > *').count() == 3
        assert page.evaluate('localStorage.length') == 0
        with page.expect_download() as export:
            page.locator('#download-json').click()
        export.value.save_as(str(OUT/'fixture-before.json'))
        page.locator('#save-baseline').click()
        assert page.evaluate('(key)=>!!localStorage.getItem(key)', KEY)
        page.reload()
        page.locator('#retest-baseline').wait_for(state='visible')
        assert len(calls) == 1, 'restore must not trigger a scan'
        page.goto('http://127.0.0.1:8000/en')
        assert len(calls) == 1
        page.locator('#retest-baseline').click()
        page.locator('#comparison-section').wait_for(state='visible')
        page.wait_for_function("document.querySelectorAll('#comparison-counts > *').length === 5")
        counts = page.locator('#comparison-counts').inner_text()
        assert int(page.locator('#comparison-counts strong').first.inner_text()) >= 2, counts
        assert page.locator('#comparison-scores > *').count() == 3
        assert 'does not authenticate' in page.locator('#comparison-details').inner_text()
        check_width(page)
        summary['comparison_counts'] = counts
        with page.expect_download() as export:
            page.locator('#download-comparison').click()
        export.value.save_as(str(OUT/'fixture-comparison.md'))
        md = (OUT/'fixture-comparison.md').read_text(encoding='utf-8')
        assert 'readiness-2026-09-26' in md and 'does not authenticate' in md
        page.locator('#comparison-section').screenshot(path=str(SHOTS/'conversion-v2-fixture-comparison.png'))
        page.evaluate("dispatchEvent(new Event('beforeprint'))")
        assert page.locator('.diff-item:not([open])').count() == 0
        page.emulate_media(media='print')
        page.pdf(path=str(OUT/'fixture-comparison.pdf'), format='A4', print_background=True)
        page.emulate_media(media='screen')
        page.evaluate("dispatchEvent(new Event('afterprint'))")
        print('Layout, comparison, exports and print verified', flush=True)
        # User clearance wins over an earlier, still-pending file read.
        page.evaluate("() => {window.originalText=File.prototype.text; File.prototype.text=function(){return new Promise(r=>window.finishImport=r)}}")
        print('Import race: controlled read installed', flush=True)
        page.locator('#import-baseline').set_input_files(str(OUT/'fixture-before.json'))
        print('Import race: file selected', flush=True)
        page.wait_for_function('!!window.finishImport')
        page.locator('#clear-baseline').click()
        print('Import race: cleared', flush=True)
        page.evaluate('(body)=>window.finishImport(body)', (OUT/'fixture-before.json').read_text(encoding='utf-8'))
        page.wait_for_timeout(100)
        assert not page.evaluate('(key)=>!!localStorage.getItem(key)', KEY), 'late import resurrected cleared baseline'
        # Explicit save likewise wins over an older import.
        page.locator('#import-baseline').set_input_files(str(OUT/'fixture-before.json'))
        page.locator('#save-baseline').click()
        page.evaluate('(body)=>window.finishImport(body)', (OUT/'fixture-before.json').read_text(encoding='utf-8'))
        page.wait_for_timeout(100)
        assert json.loads(page.evaluate('(key)=>localStorage.getItem(key)', KEY))['scanned_at'] == '2026-09-26T10:00:00.000Z'
        # Out-of-order reads cannot replace the most recently selected file.
        page.evaluate('() => {window.pendingReads=[]; File.prototype.text=function(){return new Promise(r=>pendingReads.push(r))}}')
        for _ in range(2):
            page.locator('#import-baseline').set_input_files(str(OUT/'fixture-before.json'))
        page.evaluate('(body)=>pendingReads[1](body)', json.dumps(report(True, 'en')))
        page.evaluate('(body)=>pendingReads[0](body)', json.dumps(report(False, 'en')))
        page.wait_for_timeout(100)
        assert json.loads(page.evaluate('(key)=>localStorage.getItem(key)', KEY))['scanned_at'] == '2026-09-26T10:00:00.000Z'
        page.evaluate('() => {File.prototype.text=window.originalText}')
        print('Import race passed', flush=True)
        page.locator('#import-baseline').set_input_files({'name':'bad.json','mimeType':'application/json','buffer':b'{broken'})
        page.wait_for_function("document.querySelector('#baseline-status').classList.contains('field-error')")
        page.locator('#import-baseline').set_input_files({'name':'large.json','mimeType':'application/json','buffer':b' '* (1024*1024+1)})
        page.wait_for_function("document.querySelector('#baseline-status').textContent.includes('1 MiB')")
        old = report(False, 'en')
        old.pop('scoring_version')
        page.locator('#import-baseline').set_input_files({'name':'legacy.json','mimeType':'application/json','buffer':json.dumps(old).encode()})
        page.wait_for_function("document.querySelector('#comparison-notice').textContent.includes('older report')")
        assert page.locator('#comparison-counts > *').count() == 0
        assert page.locator('#comparison-scores > *').count() == 0
        page.locator('#clear-baseline').click()
        page.locator('#demo-button').click()
        assert page.locator('#save-baseline').is_hidden()
        assert page.locator('#comparison-section').is_hidden()
        assert not summary['errors'], summary['errors']
        summary['scan_requests'] = len(calls)
        summary['checks'] = ['375px first fold x3', 'no horizontal overflow', 'explicit storage only', 'restore across languages without scan', 'actual analyzer repair comparison', 'JSON/Markdown/PDF export', 'clear/save/new import supersede pending reads', 'invalid and oversized import rejected', 'legacy version blocked', 'demo baseline blocked']
        (OUT/'browser-checks.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
        browser.close()
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == '__main__':
    run()
