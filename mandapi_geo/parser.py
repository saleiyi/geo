"""HTML -> PageFacts. Sem chamada de rede, sem LLM. So extracao deterministica.

Este modulo e a base de tudo: se os fatos extraidos estiverem errados,
todo o relatorio fica errado. Por isso nao ha heuristica "criativa" aqui.
"""

from __future__ import annotations

import json
import re
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from .fetcher import FetchResult
from .models import PageFacts

_WS = re.compile(r"\s+")
_NUMBER = re.compile(r"\b\d[\d.,]*\s*(?:%|mil|milhao|milhao|reais|r\$)?", re.IGNORECASE)
_QUESTION_STARTS = (
    "como ",
    "o que ",
    "qual ",
    "quais ",
    "quando ",
    "onde ",
    "por que ",
    "porque ",
    "quem ",
    "quanto ",
    "what ",
    "how ",
    "why ",
    "when ",
    "where ",
    "who ",
    "which ",
)

_DROP_TAGS = ("script", "style", "noscript", "template", "svg", "iframe")


def _clean(value: str | None) -> str:
    if not value:
        return ""
    return _WS.sub(" ", value).strip()


def _meta(soup: BeautifulSoup, *, name: str | None = None, prop: str | None = None) -> str | None:
    if name:
        tag = soup.find("meta", attrs={"name": re.compile(f"^{re.escape(name)}$", re.I)})
        if tag and tag.get("content"):
            return _clean(tag["content"])
    if prop:
        tag = soup.find("meta", attrs={"property": re.compile(f"^{re.escape(prop)}$", re.I)})
        if tag and tag.get("content"):
            return _clean(tag["content"])
    return None


def _collect_jsonld_types(soup: BeautifulSoup) -> tuple[list[str], bool, bool, bool, str | None, str | None, str | None]:
    """Percorre JSON-LD recursivamente. Retorna tipos + flags de schema relevantes."""
    types: list[str] = []
    has_faq = has_org = has_breadcrumb = False
    author: str | None = None
    published: str | None = None
    modified: str | None = None

    def walk(node: object) -> None:
        nonlocal has_faq, has_org, has_breadcrumb, author, published, modified
        if isinstance(node, list):
            for item in node:
                walk(item)
            return
        if not isinstance(node, dict):
            return

        raw_type = node.get("@type")
        node_types: list[str] = []
        if isinstance(raw_type, str):
            node_types = [raw_type]
        elif isinstance(raw_type, list):
            node_types = [str(item) for item in raw_type]

        for item in node_types:
            types.append(item)
            lowered = item.lower()
            if lowered == "faqpage":
                has_faq = True
            elif lowered in {"organization", "localbusiness", "corporation"}:
                has_org = True
            elif lowered == "breadcrumblist":
                has_breadcrumb = True

        if not author and "author" in node:
            raw_author = node["author"]
            if isinstance(raw_author, dict):
                author = _clean(str(raw_author.get("name") or "")) or None
            elif isinstance(raw_author, str):
                author = _clean(raw_author) or None
            elif isinstance(raw_author, list) and raw_author:
                first = raw_author[0]
                if isinstance(first, dict):
                    author = _clean(str(first.get("name") or "")) or None

        if not published and node.get("datePublished"):
            published = _clean(str(node["datePublished"])) or None
        if not modified and node.get("dateModified"):
            modified = _clean(str(node["dateModified"])) or None

        for value in node.values():
            if isinstance(value, (dict, list)):
                walk(value)

    for tag in soup.find_all("script", attrs={"type": re.compile("ld\\+json", re.I)}):
        payload = tag.string or tag.get_text() or ""
        payload = payload.strip()
        if not payload:
            continue
        try:
            walk(json.loads(payload))
        except (json.JSONDecodeError, TypeError, ValueError):
            # JSON-LD quebrado e um problema real, mas nao derruba o scan.
            continue

    return types, has_faq, has_org, has_breadcrumb, author, published, modified


def parse_page(fetch: FetchResult) -> PageFacts:
    soup = BeautifulSoup(fetch.html or "", "lxml")

    title_tag = soup.find("title")
    title = _clean(title_tag.get_text()) if title_tag else None
    description = _meta(soup, name="description")

    canonical_tag = soup.find("link", attrs={"rel": lambda v: v and "canonical" in v})
    canonical = _clean(canonical_tag.get("href")) if canonical_tag and canonical_tag.get("href") else None

    html_tag = soup.find("html")
    lang = _clean(html_tag.get("lang")) if html_tag and html_tag.get("lang") else None

    viewport_tag = soup.find(
        "meta", attrs={"name": re.compile("^viewport$", re.I)}
    )
    has_viewport = bool(viewport_tag)

    hreflang: list[str] = []
    for tag in soup.find_all("link", attrs={"rel": lambda v: v and "alternate" in v}):
        code = tag.get("hreflang")
        if code:
            hreflang.append(_clean(code).lower())

    og_tags = [
        _clean(tag.get("property"))
        for tag in soup.find_all("meta", attrs={"property": re.compile("^og:", re.I)})
        if tag.get("property")
    ]
    twitter_card = _meta(soup, name="twitter:card")

    headings: list[tuple[int, str]] = []
    for level in range(1, 7):
        for tag in soup.find_all(f"h{level}"):
            text = _clean(tag.get_text())
            if text:
                headings.append((level, text))

    question_headings = [
        text
        for level, text in headings
        if text.endswith("?") or text.lower().startswith(_QUESTION_STARTS)
    ]

    schema_types, has_faq, has_org, has_breadcrumb, author, published, modified = _collect_jsonld_types(soup)

    images = soup.find_all("img")
    images_with_alt = [img for img in images if _clean(img.get("alt"))]

    base_host = urlparse(fetch.final_url or fetch.url).netloc.lower()
    internal = external = 0
    for anchor in soup.find_all("a", href=True):
        href = anchor["href"].strip()
        if not href or href.startswith(("#", "mailto:", "tel:", "javascript:")):
            continue
        resolved = urljoin(fetch.final_url or fetch.url, href)
        host = urlparse(resolved).netloc.lower()
        if host == base_host:
            internal += 1
        elif host:
            external += 1

    has_main = bool(soup.find("main"))
    has_article = bool(soup.find("article"))
    has_nav = bool(soup.find("nav"))
    has_footer = bool(soup.find("footer"))

    first_paragraph = ""
    for paragraph in soup.find_all("p"):
        text = _clean(paragraph.get_text())
        if len(text) >= 40:
            first_paragraph = text
            break

    list_count = len(soup.find_all(["ul", "ol"]))
    table_count = len(soup.find_all("table"))

    # A partir daqui o soup e mutado: extracao de texto limpo.
    body = soup.body or soup
    for tag in body.find_all(_DROP_TAGS):
        tag.decompose()
    text = _clean(body.get_text(" "))
    word_count = len([w for w in text.split(" ") if w])

    page_bytes = fetch.content_bytes or len(fetch.html or "")
    ratio = (len(text) / page_bytes) if page_bytes else 0.0

    return PageFacts(
        url=fetch.url,
        final_url=fetch.final_url,
        status_code=fetch.status_code,
        elapsed_ms=fetch.elapsed_ms,
        page_bytes=page_bytes,
        is_https=(urlparse(fetch.final_url or fetch.url).scheme == "https"),
        title=title,
        meta_description=description,
        canonical=canonical,
        lang=lang,
        has_viewport=has_viewport,
        meta_robots=_meta(soup, name="robots"),
        hreflang=sorted(set(hreflang)),
        og_tags=sorted(set(og_tags)),
        twitter_card=twitter_card,
        headings=headings,
        h1_count=sum(1 for level, _ in headings if level == 1),
        h2_count=sum(1 for level, _ in headings if level == 2),
        h3_count=sum(1 for level, _ in headings if level == 3),
        question_headings=question_headings[:20],
        jsonld_types=sorted(set(schema_types)),
        has_faq_schema=has_faq,
        has_organization_schema=has_org,
        has_breadcrumb_schema=has_breadcrumb,
        images_total=len(images),
        images_with_alt=len(images_with_alt),
        internal_links=internal,
        external_links=external,
        word_count=word_count,
        text=text[:20000],
        text_html_ratio=round(ratio, 4),
        first_paragraph=first_paragraph[:600],
        has_main=has_main,
        has_article=has_article,
        has_nav=has_nav,
        has_footer=has_footer,
        author_name=author,
        date_published=published,
        date_modified=modified,
        list_count=list_count,
        table_count=table_count,
        number_signals=len(_NUMBER.findall(text)),
    )