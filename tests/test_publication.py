"""Public operator configuration and truthful deployment preflight; no network."""
import json

from bs4 import BeautifulSoup
from fastapi.testclient import TestClient
import pytest

from mandapi_geo.api import app
from mandapi_geo.config import load_settings
from mandapi_geo.preflight import assess, main

PUBLIC_FIELDS = ['OPERATOR_NAME', 'CONTACT_EMAIL', 'HOSTING_PROVIDER',
                 'PRIVACY_LOG_NOTICE_PT', 'PRIVACY_LOG_NOTICE_EN', 'PRIVACY_LOG_NOTICE_ZH']


@pytest.fixture(autouse=True)
def isolated_config(monkeypatch):
    for key in PUBLIC_FIELDS + ['SITE_URL', 'RENDER_EXTERNAL_URL', 'GOOGLE_SITE_VERIFICATION']:
        monkeypatch.setenv(key, '')
    monkeypatch.setenv('SITE_INDEXABLE', 'false')
    monkeypatch.setenv('PUBLIC_AI_SUMMARY', 'false')
    load_settings.cache_clear()
    yield
    load_settings.cache_clear()


def configured(monkeypatch):
    monkeypatch.setenv('SITE_URL', 'https://geo.example.com')
    for key in PUBLIC_FIELDS:
        monkeypatch.setenv(key, 'Test fixture only')
    monkeypatch.setenv('CONTACT_EMAIL', 'test+privacy@example.com')
    load_settings.cache_clear()


def test_local_runs_without_inventing_operator_information():
    settings = load_settings()
    assert not settings.site_indexable
    assert len(settings.publication_missing) == 7
    assert assess(settings, 'local')['configuration_ready']
    assert not assess(settings, 'preview')['configuration_ready']


@pytest.mark.parametrize('missing', PUBLIC_FIELDS + ['SITE_URL'])
def test_indexing_fails_closed_when_required_public_details_missing(monkeypatch, missing):
    configured(monkeypatch)
    monkeypatch.setenv(missing, '')
    monkeypatch.setenv('SITE_INDEXABLE', 'true')
    with pytest.raises(ValueError, match='SITE_INDEXABLE=true requires'):
        load_settings()


def test_preview_and_production_are_distinct_and_gsc_is_optional(monkeypatch):
    configured(monkeypatch)
    settings = load_settings()
    assert assess(settings, 'preview')['configuration_ready']
    assert not assess(settings, 'production')['configuration_ready']
    monkeypatch.setenv('SITE_INDEXABLE', 'true')
    load_settings.cache_clear()
    settings = load_settings()
    assert assess(settings, 'production')['configuration_ready']
    assert not assess(settings, 'preview')['configuration_ready']
    assert not settings.google_site_verification
    assert 'Customer use' in assess(settings, 'production')['not_verified'][-1]


@pytest.mark.parametrize('email', ['bad', 'Name <test@example.com>', 'a@example.com\r\nBCC:x@y.com',
    'a@localhost', '.a@example.com', 'a..b@example.com', 'a@example.com?subject=bad',
    'a@-example.com', 'a@example..com'])
def test_contact_rejects_non_mailboxes(monkeypatch, email):
    monkeypatch.setenv('CONTACT_EMAIL', email)
    with pytest.raises(ValueError, match='CONTACT_EMAIL'):
        load_settings()


def test_contact_accepts_international_domain_and_normalizes_idna(monkeypatch):
    monkeypatch.setenv('CONTACT_EMAIL', 'team@例子.com')
    assert load_settings().contact_email == 'team@xn--fsqu00a.com'


@pytest.mark.parametrize('key,value', [('OPERATOR_NAME', 'x'*201), ('HOSTING_PROVIDER', 'a\x00b'), ('PRIVACY_LOG_NOTICE_ZH', 'x'*4001)])
def test_public_fields_bounded(monkeypatch, key, value):
    # NUL cannot be passed to a real OS env; exercise a control supported by env.
    monkeypatch.setenv(key, value.replace('\x00', '\x01'))
    with pytest.raises(ValueError, match=key):
        load_settings()


@pytest.mark.parametrize('locale,field,missing', [('', 'PT', 'versão de prévia'), ('en', 'EN', 'preview version'), ('zh', 'ZH', '预览版本')])
def test_privacy_renders_localized_missing_or_escaped_operator_text(monkeypatch, locale, field, missing):
    path = '/' + '/'.join(x for x in [locale, 'privacidade'] if x)
    with TestClient(app) as client:
        html = client.get(path).text
        assert missing in html
        assert '__OPERATOR_NAME__' not in html
        configured(monkeypatch)
        operator = 'Fixture <script>alert(1)</script> & __CONTACT_EMAIL__'
        notice = 'Fixture log policy\n<img src=x onerror=alert(1)>'
        monkeypatch.setenv('OPERATOR_NAME', operator)
        monkeypatch.setenv('PRIVACY_LOG_NOTICE_' + field, notice)
        load_settings.cache_clear()
        response = client.get(path)
        assert response.status_code == 200
        info = BeautifulSoup(response.text, 'html.parser').select_one('#operator-information')
        assert not info.find_all(['script', 'img'])
        assert operator in info.get_text()
        assert notice in info.get_text()
        assert 'test+privacy@example.com' in info.get_text()
        assert missing not in info.get_text()


def test_platform_origin_is_validated_but_explicit_origin_takes_precedence(monkeypatch):
    monkeypatch.setenv('RENDER_EXTERNAL_URL', 'https://geo-fixture.onrender.com')
    assert load_settings().site_url == 'https://geo-fixture.onrender.com'
    assert not load_settings().site_indexable
    monkeypatch.setenv('SITE_URL', 'https://geo.example.com')
    load_settings.cache_clear()
    assert load_settings().site_url == 'https://geo.example.com'
    monkeypatch.setenv('SITE_URL', '')
    monkeypatch.setenv('RENDER_EXTERNAL_URL', 'http://127.0.0.1')
    load_settings.cache_clear()
    with pytest.raises(ValueError, match='SITE_URL'):
        load_settings()


def test_preflight_exit_status_and_output_do_not_expose_env_values(monkeypatch, capsys):
    monkeypatch.setenv('LLM_API_KEY', 'private-key-must-not-be-printed')
    assert main(['--stage', 'preview']) == 1
    payload = json.loads(capsys.readouterr().out)
    assert 'CONTACT_EMAIL' in payload['blocking']
    configured(monkeypatch)
    assert main(['--stage', 'preview']) == 0
    output = capsys.readouterr().out
    assert 'configuration_ready' in output
    assert 'private-key' not in output and 'test+privacy' not in output
    monkeypatch.setenv('SITE_URL', 'https://user:secret@example.com')
    load_settings.cache_clear()
    assert main(['--stage', 'preview']) == 1
    output = capsys.readouterr().out
    assert 'INVALID_CONFIGURATION' in output and 'secret' not in output
