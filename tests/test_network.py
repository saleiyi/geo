"""Offline regressions for SSRF, resource limits and robots precedence."""

from __future__ import annotations

import gzip
import socket
import ssl
import threading
import time

import httpcore
import httpx
import pytest

from mandapi_geo import fetcher, network


def response(body: bytes = b"<html>ok</html>", status: int = 200,
             content_type: str = "text/html", **headers) -> httpx.Response:
    return httpx.Response(status, headers={"content-type": content_type, **headers},
                          stream=httpx.ByteStream(body))


def mock_client(monkeypatch, handler):
    calls = []
    def handle(request):
        calls.append(str(request.url))
        return handler(request)
    monkeypatch.setattr(fetcher, "_client", lambda deadline=None: httpx.Client(
        transport=httpx.MockTransport(handle), trust_env=False, follow_redirects=False))
    return calls


@pytest.mark.parametrize("url", [
    "file:///etc/passwd", "ftp://example.com", "javascript:alert(1)",
    "http://user:password@example.com/", "https://localhost/", "http://127.0.0.1/",
    "http://169.254.169.254/latest/meta-data", "http://10.0.0.1", "http://192.168.0.1",
    "http://100.64.0.1/", "http://224.0.0.1", "http://[::1]/", "http://[fe80::1]/",
    "http://[::ffff:127.0.0.1]/", "http://[2002:7f00:1::]/", "http://foo.local/",
    "http://example.com:0/", "https://example.com\\@127.0.0.1/", "https://ex ample.com/",
    "https://example.com/\r\nHeader: injected", "http://%31%32%37.0.0.1/",
])
def test_reject_unsafe_url_syntax_and_literals(url):
    with pytest.raises(ValueError):
        fetcher.normalize_url(url)


def test_normalize_public_url():
    assert fetcher.normalize_url(" Exemplo.com.br/ação#fragment ") == "https://exemplo.com.br/a%C3%A7%C3%A3o"
    assert fetcher.normalize_url("HTTPS://EXAMPLE.COM") == "https://example.com/"
    assert fetcher.normalize_url("http://8.8.8.8/") == "http://8.8.8.8/"


def test_mixed_dns_answer_is_rejected_before_any_connection(monkeypatch):
    monkeypatch.setattr(network.socket, "getaddrinfo", lambda *args: [
        (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 443)),
        (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", 443)),
    ])
    monkeypatch.setattr(network.socket, "socket", lambda *args: pytest.fail("Unsafe connection attempted"))
    with pytest.raises(network.UnsafeURL):
        network.PublicNetworkBackend(time.monotonic() + 2).connect_tcp("example.com", 443)


def test_dns_rebinding_pins_verified_numeric_socket_address(monkeypatch):
    lookups, connections = [], []
    def dns(*args):
        lookups.append(args)
        address = "93.184.216.34" if len(lookups) == 1 else "127.0.0.1"
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (address, 443))]
    class FakeSocket:
        def settimeout(self, value): pass
        def setsockopt(self, *args): pass
        def connect(self, address): connections.append(address)
        def close(self): pass
    monkeypatch.setattr(network.socket, "getaddrinfo", dns)
    monkeypatch.setattr(network.socket, "socket", lambda *args: FakeSocket())
    stream = network.PublicNetworkBackend(time.monotonic() + 2).connect_tcp("example.com", 443)
    stream.close()
    assert len(lookups) == 1
    assert connections == [("93.184.216.34", 443)]


def test_tls_preserves_original_hostname():
    names = []
    class Stream:
        def start_tls(self, context, server_hostname, timeout):
            names.append(server_hostname)
            return self
    network.DeadlineStream(Stream(), time.monotonic() + 2).start_tls(ssl.create_default_context(), "example.com")
    assert names == ["example.com"]


def test_dns_wait_has_total_deadline(monkeypatch):
    release = threading.Event()
    monkeypatch.setattr(network.socket, "getaddrinfo", lambda *args: release.wait(1))
    started = time.monotonic()
    try:
        with pytest.raises(httpcore.ConnectTimeout):
            network.resolve_public("example.com", 443, started + 0.03)
        assert time.monotonic() - started < 0.5
    finally:
        release.set()


def test_deadline_applies_across_individually_fast_reads(monkeypatch):
    now, timeouts = [0.0], []
    monkeypatch.setattr(network.time, "monotonic", lambda: now[0])
    class Stream:
        def read(self, max_bytes, timeout):
            timeouts.append(timeout)
            now[0] += 0.4
            return b"x"
    stream = network.DeadlineStream(Stream(), 1.0)
    assert stream.read(1, 15) == b"x"
    assert stream.read(1, 15) == b"x"
    with pytest.raises(httpcore.ReadTimeout):
        stream.read(1, 15)
    assert timeouts == pytest.approx([1.0, 0.6, 0.2])


def test_environment_proxy_is_ignored(monkeypatch):
    monkeypatch.setenv("HTTP_PROXY", "http://127.0.0.1:8080")
    monkeypatch.setenv("HTTPS_PROXY", "http://127.0.0.1:8080")
    with fetcher._client(time.monotonic() + 2) as client:
        assert client.trust_env is False
        assert isinstance(client._transport, network.PublicHTTPTransport)
        assert isinstance(client._transport._pool._network_backend, network.PublicNetworkBackend)


def test_each_redirect_rejects_private_target(monkeypatch):
    calls = mock_client(monkeypatch, lambda request: response(status=302, location="http://127.0.0.1/secret"))
    result = fetcher.fetch_page("https://example.com/")
    assert not result.ok and "privados" in result.error
    assert calls == ["https://example.com/"]


def test_redirect_host_dns_is_checked_at_connection_time(monkeypatch):
    # Exercise the real httpx/httpcore transport, including redirect dispatch.
    lookups = []
    def dns(host, port, *args):
        lookups.append(host)
        ip = "93.184.216.34" if host == "example.com" else "127.0.0.1"
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (ip, port))]
    class FakeSocket:
        def settimeout(self, value): pass
        def setsockopt(self, *args): pass
        def connect(self, address): assert address[0] == "93.184.216.34"
        def send(self, data): return len(data)
        def recv(self, size):
            return b"HTTP/1.1 302 Found\r\nLocation: http://unsafe.example/\r\nContent-Length: 0\r\n\r\n"
        def close(self): pass
    monkeypatch.setattr(network.socket, "getaddrinfo", dns)
    monkeypatch.setattr(network.socket, "socket", lambda *args: FakeSocket())
    result = fetcher.fetch_page("http://example.com/")
    assert not result.ok and "reservado" in result.error
    assert lookups == ["example.com", "unsafe.example"]


def test_redirect_loop_stops_at_five(monkeypatch):
    calls = mock_client(monkeypatch, lambda request: response(status=302, location="/again"))
    result = fetcher.fetch_page("https://example.com/")
    assert result.redirect_count == 5
    assert len(calls) == 6
    assert "redirecionamentos" in result.error


@pytest.mark.parametrize("status,message", [(403, "bloqueou"), (429, "limitou"), (404, "HTTP 404")])
def test_localized_http_errors(monkeypatch, status, message):
    mock_client(monkeypatch, lambda request: response(status=status))
    result = fetcher.fetch_page("example.com")
    assert not result.ok and message in result.error
    assert result.status_code == status


def test_timeout_error_hides_transport_internals(monkeypatch):
    def timeout(request):
        raise httpx.ReadTimeout("sensitive internal transport detail")
    mock_client(monkeypatch, timeout)
    result = fetcher.fetch_page("example.com")
    assert "demorou" in result.error
    assert "sensitive" not in result.error


def test_html_only_and_xhtml_allowed(monkeypatch):
    mock_client(monkeypatch, lambda request: response(b"%PDF-1.7", content_type="application/pdf"))
    result = fetcher.fetch_page("example.com/file.pdf")
    assert not result.ok and "HTML" in result.error
    mock_client(monkeypatch, lambda request: response(content_type="application/xhtml+xml"))
    assert fetcher.fetch_page("example.com").ok


def test_html_limit_applies_after_decompression(monkeypatch):
    body = gzip.compress(b"x" * (fetcher.HTML_LIMIT + 1))
    mock_client(monkeypatch, lambda request: response(body, **{"content-encoding": "gzip"}))
    result = fetcher.fetch_page("example.com")
    assert not result.ok and "limite de tamanho" in result.error
    assert result.html == ""


def test_valid_gzip_html_is_decoded(monkeypatch):
    body = b"<html>compressed</html>"
    mock_client(monkeypatch, lambda request: response(gzip.compress(body), **{"content-encoding": "gzip"}))
    result = fetcher.fetch_page("example.com")
    assert result.ok and result.html == body.decode()
    assert result.content_bytes == len(body)


def test_streaming_html_without_content_length_is_bounded(monkeypatch):
    class LargeStream(httpx.SyncByteStream):
        def __iter__(self):
            for _ in range(200):
                yield b"x" * 16384
    mock_client(monkeypatch, lambda request: httpx.Response(200, headers={"content-type": "text/html"}, stream=LargeStream()))
    result = fetcher.fetch_page("example.com")
    assert not result.ok and "limite de tamanho" in result.error


def test_fetch_page_keeps_separate_x_robots_headers(monkeypatch):
    mock_client(monkeypatch, lambda request: httpx.Response(200, headers=[
        ("content-type", "text/html"), ("x-robots-tag", "googlebot: noindex"),
        ("x-robots-tag", "nofollow"),
    ], stream=httpx.ByteStream(b"<html>ok</html>")))
    result = fetcher.fetch_page("example.com")
    assert result.ok
    assert result.headers["x-robots-tag"] == "googlebot: noindex\nnofollow"


def test_auxiliary_limit_and_private_redirect(monkeypatch):
    mock_client(monkeypatch, lambda request: response(b"User-agent: *\n#" + b"x" * fetcher.AUX_LIMIT,
                                                    content_type="text/plain"))
    assert fetcher.fetch_text("https://example.com/robots.txt") == (200, None)
    calls = mock_client(monkeypatch, lambda request: response(status=302, location="http://10.0.0.1/"))
    assert fetcher.fetch_text("https://example.com/robots.txt")[1] is None
    assert len(calls) == 1


@pytest.mark.parametrize("path,content_type,body", [
    ("robots.txt", "text/html", b"<html>SPA soft 404</html>"),
    ("robots.txt", "text/plain", b"<html>User-agent: *\nDisallow: /</html>"),
    ("llms.txt", "text/html", b"<html>Home page</html>"),
    ("llms.txt", "text/plain", b"Not Found"),
    ("sitemap.xml", "application/xml", b"<html><loc>fake</loc></html>"),
    ("sitemap.xml", "application/xml", b'<!DOCTYPE x [<!ENTITY e "abc">]><urlset>&e;</urlset>'),
])
def test_auxiliary_soft_404_or_invalid_format_not_reported_present(monkeypatch, path, content_type, body):
    mock_client(monkeypatch, lambda request: response(body, content_type=content_type))
    assert fetcher.fetch_text("https://example.com/" + path) == (200, None)


@pytest.mark.parametrize("path,content_type,body", [
    ("robots.txt", "text/plain", b"User-agent: *\nDisallow: /admin"),
    ("llms.txt", "text/markdown", b"# Example\n\n> Business description"),
    ("sitemap.xml", "application/xml", b'<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"><url><loc>https://example.com/</loc></url></urlset>'),
])
def test_valid_auxiliary_resources(monkeypatch, path, content_type, body):
    mock_client(monkeypatch, lambda request: response(body, content_type=content_type))
    assert fetcher.fetch_text("https://example.com/" + path) == (200, body.decode())


def test_at_most_three_distinct_safe_sitemap_candidates():
    robots = "\n".join(["Sitemap: http://127.0.0.1/secret"] + [f"Sitemap: https://example.com/{i}.xml" for i in range(12)])
    candidates = fetcher._sitemap_candidates(robots, "https://example.com")
    assert candidates == [f"https://example.com/{i}.xml" for i in range(3)]


def test_robots_consecutive_agents_duplicate_groups_and_specific_precedence():
    robots = """User-agent: *
Disallow: /
User-agent: GPTBot
User-agent: ClaudeBot
Disallow: /admin
User-agent: GPTBot
Allow: /admin/public
"""
    public = fetcher.parse_robots_ai_rules(robots, "https://example.com/admin/public")
    assert public["gptbot"] == "allow"
    assert public["claudebot"] == "block"
    assert public["perplexitybot"] == "block"
    normal = fetcher.parse_robots_ai_rules(robots, "https://example.com/about")
    assert normal["gptbot"] == normal["claudebot"] == "allow"
    assert fetcher.parse_robots_ai_rules(robots)["gptbot"] == "partial"


@pytest.mark.parametrize("path,expected", [
    ("/private/article", "block"), ("/private/public/article", "allow"),
    ("/same", "allow"), ("/download/file.pdf", "block"),
    ("/download/file.pdf?html=1", "allow"), ("/normal", "allow"),
])
def test_robots_longest_match_allow_tie_and_wildcard_anchor(path, expected):
    robots = """User-agent: *
Disallow: /private
Allow: /private/public
Disallow: /same
Allow: /same
Disallow: /*.pdf$
"""
    assert fetcher.parse_robots_ai_rules(robots, "https://example.com" + path)["googlebot"] == expected


def test_collect_facts_evaluates_requested_path(monkeypatch):
    monkeypatch.setattr(fetcher, "fetch_text", lambda url: (404, None))
    facts = fetcher.collect_site_facts("https://example.com/about", "User-agent: *\nDisallow: /admin")
    assert facts.ai_crawler_rules["gptbot"] == "allow"


def test_robots_google_documented_wildcard_precedence():
    robots = "User-agent: *\nAllow: /page\nDisallow: /*.htm"
    assert fetcher.parse_robots_ai_rules(robots, "https://example.com/page.htm")["googlebot"] == "block"
    robots = "User-agent: *\nAllow: /page\nDisallow: /*.ph"
    assert fetcher.parse_robots_ai_rules(robots, "https://example.com/page.php5")["googlebot"] == "allow"


def test_robots_resource_itself_is_implicitly_allowed():
    rules = fetcher.parse_robots_ai_rules("User-agent: *\nDisallow: /", "https://example.com/robots.txt")
    assert rules["googlebot"] == "allow"


def test_invalid_inputs_return_results_instead_of_raising():
    assert not fetcher.fetch_page("http://[broken").ok
    assert fetcher.fetch_text("http://[broken") == (None, None)
