"""Agregação de score. Uma fórmula só, fácil de explicar ao cliente."""

from __future__ import annotations

from .models import AreaReport, Check, Issue, ScoreCard

AREA_LABELS: dict[str, str] = {
    "seo": "SEO Técnico",
    "geo": "Visibilidade em IA (GEO)",
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
    gap = geo - seo
    if overall >= 80:
        base = "Seu site está bem preparado tanto para a busca tradicional quanto para a IA."
    elif overall >= 60:
        base = "A base é sólida, mas há pontos claros que impedem a IA de citar seu site."
    elif overall >= 40:
        base = "Seu site aparece no Google, mas está praticamente invisível para IA."
    else:
        base = "Seu site tem problemas estruturais que bloqueiam tanto o Google quanto a IA."

    if gap <= -15:
        base += " O maior gargalo está em GEO: falta a camada que as IAs leem."
    elif gap >= 15:
        base += " O SEO está pior que o GEO: priorize a base técnica primeiro."
    return base


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