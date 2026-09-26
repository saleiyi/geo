"""Agregação de score. Uma fórmula só, fácil de explicar ao cliente."""

from __future__ import annotations

from .models import AreaReport, Check, Issue, ScoreCard

AREA_LABELS: dict[str, str] = {
    "seo": "SEO Técnico",
    "geo": "Preparação para busca com IA (GEO)",
    "content": "Inteligência de Conteúdo",
}

AREA_WEIGHTS: dict[str, float] = {
    "seo": 0.5,
    "geo": 0.5,
    "content": 0.3,
}

_STATUS_VALUE: dict[str, float] = {"pass": 1.0, "warn": 0.5, "fail": 0.0}

_SEVERITY_ORDER: dict[str, int] = {"critical": 0, "high": 1, "medium": 2, "low": 3}


def area_score(checks: list[Check]) -> int:
    scored = [c for c in checks if c.status in _STATUS_VALUE]
    total = sum(c.weight for c in scored)
    if total <= 0:
        return 0
    earned = sum(c.weight * _STATUS_VALUE[c.status] for c in scored)
    return int(round(earned / total * 100))


def grade_for(score: int) -> str:
    if score >= 85:
        return "A"
    if score >= 70:
        return "B"
    if score >= 55:
        return "C"
    if score >= 40:
        return "D"
    return "F"


def sort_issues(issues: list[Issue]) -> list[Issue]:
    return sorted(issues, key=lambda i: (_SEVERITY_ORDER.get(i.severity, 9), -i.impact))


def build_area(area: str, checks: list[Check], issues: list[Issue]) -> AreaReport:
    return AreaReport(
        area=area,  # type: ignore[arg-type]
        label=AREA_LABELS.get(area, area),
        score=area_score(checks),
        checks=checks,
        issues=sort_issues(issues),
    )


def _summary(overall: int, seo: int, geo: int) -> str:
    if overall >= 80:
        base = "A página atende à maioria das verificações técnicas desta auditoria."
    elif overall >= 60:
        base = "A página tem uma base técnica aproveitável e pontos que merecem revisão."
    elif overall >= 40:
        base = "A página apresenta várias oportunidades de melhoria técnica e de estrutura do conteúdo."
    else:
        base = "A página apresenta lacunas nas verificações técnicas e de conteúdo aplicadas."
    if geo - seo <= -15:
        base += " Priorize as verificações de preparação para busca com IA."
    elif geo - seo >= 15:
        base += " Priorize as verificações de SEO técnico."
    return base + " A nota é heurística e não comprova ranking, tráfego ou citações por IA."


def build_scorecard(areas: list[AreaReport]) -> ScoreCard:
    by_area = {a.area: a for a in areas}

    seo = by_area["seo"].score if "seo" in by_area else 0
    geo = by_area["geo"].score if "geo" in by_area else 0
    content = by_area["content"].score if "content" in by_area else 0

    present = [a for a in areas if a.area in AREA_WEIGHTS and a.area != "content"]
    if present:
        total_weight = sum(AREA_WEIGHTS[a.area] for a in present)
        overall = int(round(sum(AREA_WEIGHTS[a.area] * a.score for a in present) / total_weight))
    else:
        overall = 0

    return ScoreCard(
        overall=overall,
        seo=seo,
        geo=geo,
        content=content,
        grade=grade_for(overall),
        summary=_summary(overall, seo, geo),
    )