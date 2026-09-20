"""Modelos de dados do relatorio. Tudo serializavel para JSON (vai direto pro front)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, Field

Area = Literal["seo", "geo", "content"]
Status = Literal["pass", "warn", "fail", "info"]
Severity = Literal["critical", "high", "medium", "low"]


class Check(BaseModel):
    """Um teste individual. label/hint sao pt-BR porque aparecem no relatorio."""

    id: str
    area: Area
    label: str
    status: Status
    weight: float = 1.0
    value: str | None = None
    hint: str | None = None


class Issue(BaseModel):
    """Problema priorizado + como corrigir."""

    id: str
    area: Area
    severity: Severity
    title: str
    detail: str
    fix: str
    impact: int = 0


class AreaReport(BaseModel):
    area: Area
    label: str
    score: int = 0
    checks: list[Check] = Field(default_factory=list)
    issues: list[Issue] = Field(default_factory=list)


class ScoreCard(BaseModel):
    overall: int = 0
    seo: int = 0
    geo: int = 0
    content: int = 0
    grade: str = "F"
    summary: str = ""


class PageFacts(BaseModel):
    """Fatos extraidos do HTML. Sem HTML cru - isso e descartado apos o parse."""

    url: str
    final_url: str
    status_code: int
    elapsed_ms: int
    page_bytes: int
    is_https: bool

    title: str | None = None
    meta_description: str | None = None
    canonical: str | None = None
    lang: str | None = None
    has_viewport: bool = False
    meta_robots: str | None = None
    hreflang: list[str] = Field(default_factory=list)

    og_tags: list[str] = Field(default_factory=list)
    twitter_card: str | None = None

    headings: list[tuple[int, str]] = Field(default_factory=list)
    h1_count: int = 0
    h2_count: int = 0
    h3_count: int = 0
    question_headings: list[str] = Field(default_factory=list)

    jsonld_types: list[str] = Field(default_factory=list)
    has_faq_schema: bool = False
    has_organization_schema: bool = False
    has_breadcrumb_schema: bool = False

    images_total: int = 0
    images_with_alt: int = 0
    internal_links: int = 0
    external_links: int = 0

    word_count: int = 0
    text: str = ""
    text_html_ratio: float = 0.0
    first_paragraph: str = ""

    has_main: bool = False
    has_article: bool = False
    has_nav: bool = False
    has_footer: bool = False

    author_name: str | None = None
    date_published: str | None = None
    date_modified: str | None = None

    list_count: int = 0
    table_count: int = 0
    number_signals: int = 0

    @property
    def title_len(self) -> int:
        return len(self.title or "")

    @property
    def meta_description_len(self) -> int:
        return len(self.meta_description or "")

    @property
    def alt_coverage(self) -> float:
        if self.images_total == 0:
            return 1.0
        return self.images_with_alt / self.images_total


class SiteFacts(BaseModel):
    """Recursos do site inteiro (robots.txt / sitemap.xml / llms.txt)."""

    robots_txt: str | None = None
    robots_status: int | None = None
    sitemap_url: str | None = None
    sitemap_status: int | None = None
    sitemap_url_count: int = 0
    llms_txt: str | None = None
    llms_status: int | None = None
    llms_full_status: int | None = None
    ai_crawler_rules: dict[str, str] = Field(default_factory=dict)


class ScanReport(BaseModel):
    target_url: str
    requested_keyword: str | None = None
    domain: str = ""
    scanned_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    elapsed_ms: int = 0

    score: ScoreCard = Field(default_factory=ScoreCard)
    areas: list[AreaReport] = Field(default_factory=list)
    issues: list[Issue] = Field(default_factory=list)
    facts: PageFacts | None = None
    site: SiteFacts | None = None
    ai_summary: str | None = None
    engine: str = "rules-v1"

    def area(self, name: Area) -> AreaReport | None:
        for item in self.areas:
            if item.area == name:
                return item
        return None