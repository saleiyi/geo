"""Single-page GEO readiness heuristics, not observed AI visibility."""

from __future__ import annotations

import re

from ..models import Check, Issue, PageFacts, SiteFacts

AREA = "geo"

# Search crawlers have different purposes from training crawlers.
KEY_BOTS: dict[str, str] = {
    "googlebot": "Googlebot (Google Search)",
    "oai-searchbot": "OAI-SearchBot (ChatGPT Search)",
    "perplexitybot": "PerplexityBot (Perplexity)",
    "claude-searchbot": "Claude-SearchBot (Claude Search)",
}
TRAINING_BOTS = {"gptbot", "claudebot", "google-extended", "applebot-extended", "ccbot"}

RATIO_PASS, RATIO_WARN = 0.06, 0.02


def _check(
    checks: list[Check],
    issues: list[Issue],
    *,
    cid: str,
    label: str,
    status: str,
    weight: float,
    value: str | None = None,
    hint: str | None = None,
    severity: str = "medium",
    title: str | None = None,
    detail: str | None = None,
    fix: str | None = None,
    impact: int = 0,
) -> None:
    checks.append(
        Check(id=cid, area=AREA, label=label, status=status, weight=weight, value=value, hint=hint)
    )
    if status in {"fail", "warn"} and title:
        issues.append(
            Issue(
                id=cid,
                area=AREA,
                severity=severity,
                title=title,
                detail=detail or "",
                fix=fix or hint or "",
                impact=impact,
            )
        )


def analyze(page: PageFacts, site: SiteFacts) -> tuple[list[Check], list[Issue]]:
    checks: list[Check] = []
    issues: list[Issue] = []

    # ===================== ACESSO =====================

    robots_known = site.robots_status == 200 and site.robots_txt is not None
    robots_absent = site.robots_status in {404, 410}
    blocked = [KEY_BOTS[b] for b in KEY_BOTS if site.ai_crawler_rules.get(b) == "block"] if robots_known else []
    partial = [KEY_BOTS[b] for b in KEY_BOTS if site.ai_crawler_rules.get(b) == "partial"] if robots_known else []
    if not robots_known and not robots_absent:
        _check(
            checks, issues, cid="geo.ai_crawlers", label="Permissão dos robôs de busca",
            status="info", weight=0.0, value="não verificada",
            hint="Não foi possível validar robots.txt. Falha de rede, resposta inválida ou HTTP de erro não comprovam permissão nem bloqueio.",
        )
    elif blocked or partial:
        _check(
            checks, issues, cid="geo.ai_crawlers", label="Permissão dos robôs de busca",
            status="fail" if blocked else "warn", weight=4.0,
            value=("bloqueado: " if blocked else "revisar caminhos: ") + ", ".join(blocked or partial),
            hint="Avalia a permissão declarada para a URL analisada, sem testar o acesso real de cada serviço.",
            severity="high", title="Robôs de busca com restrição declarada",
            detail="Regras de robots.txt restringem: " + ", ".join(blocked or partial) + ".",
            fix="Se esta página deve ser pública para busca, revise as regras aplicáveis ao seu caminho. Preserve restrições intencionais de áreas privadas.", impact=12,
        )
    else:
        _check(
            checks, issues, cid="geo.ai_crawlers", label="Permissão dos robôs de busca",
            status="pass", weight=4.0,
            value="sem regras (HTTP 404/410)" if robots_absent else "sem bloqueio declarado para esta URL",
            hint="Ausência de bloqueio em robots.txt não garante rastreamento, indexação ou citação.",
        )

    training = ", ".join(f"{bot}: {site.ai_crawler_rules.get(bot, 'unspecified')}" for bot in sorted(TRAINING_BOTS)) if robots_known else "não verificado"
    _check(
        checks, issues, cid="geo.training_bots", label="Preferências de uso e treinamento de IA",
        status="info", weight=0.0, value=training,
        hint="Permissões de treinamento são independentes da busca. Google-Extended controla usos do Gemini, não a inclusão no Google Search. Esta observação não altera a nota.",
    )
    _check(
        checks, issues, cid="geo.llms_txt", label="llms.txt (opcional)", status="info", weight=0.0,
        value="presente" if site.llms_status == 200 and site.llms_txt else ("ausente" if site.llms_status in {404, 410} else "não verificado"),
        hint="Proposta opcional para orientar ferramentas compatíveis. Não é requisito de indexação nem garantia de uso ou citação por IA; não altera a nota.",
    )

    directives = {agent: set(values) for agent, values in page.robots_directives.items()}
    # Preserve compatibility with facts supplied directly by callers.
    generic = directives.setdefault("*", set())
    generic.update(token for token in re.split(r"[,\s]+", (page.meta_robots or "").lower()) if token)
    if "none" in generic:
        generic.update(("noindex", "nofollow"))
    relevant = {agent: generic | directives.get(agent, set()) for agent in KEY_BOTS}
    noindex = [KEY_BOTS[agent] for agent, values in relevant.items() if "noindex" in values or "none" in values]
    nosnippet = [KEY_BOTS[agent] for agent, values in relevant.items() if "nosnippet" in values or "max-snippet:0" in values]
    nofollow = [KEY_BOTS[agent] for agent, values in relevant.items() if "nofollow" in values or "none" in values]
    if noindex or nosnippet:
        _check(
            checks, issues, cid="geo.indexable", label="Diretivas de indexação e trechos",
            status="fail" if noindex else "warn", weight=3.0,
            value=("noindex: " + ", ".join(noindex)) if noindex else ("restrição de trechos: " + ", ".join(nosnippet)),
            hint="Diretivas observadas em meta tags e X-Robots-Tag; o suporte e os efeitos variam por serviço.",
            severity="high", title="Página com diretiva restritiva de indexação" if noindex else "Página com restrição de trechos",
            detail="Foram encontradas diretivas aplicáveis a robôs de busca. Este teste não consulta índices de busca.",
            fix="Revise meta robots, meta tags específicas e X-Robots-Tag. Remova a restrição apenas se ela contrariar a intenção desta página pública.", impact=12,
        )
    else:
        _check(
            checks, issues, cid="geo.indexable", label="Diretivas de indexação e trechos",
            status="pass", weight=3.0, value="sem restrição de indexação observada",
            hint="A ausência de noindex não comprova indexação; robots.txt, autenticação e outros controles também podem limitar o acesso.",
        )
    _check(
        checks, issues, cid="geo.link_following", label="Diretiva de seguimento de links",
        status="info", weight=0.0, value="nofollow: " + ", ".join(nofollow) if nofollow else "sem nofollow observado",
        hint="nofollow diz respeito aos links da página; isoladamente, não impede a indexação desta URL.",
    )

    # ===================== COMPREENSÃO =====================

    _check(
        checks, issues, cid="geo.entity", label="Entidade declarada (Schema)", status="info", weight=0.0,
        value="Organization/LocalBusiness presente" if page.has_organization_schema else "ausente",
        hint="Declare uma organização apenas quando apropriado ao conteúdo. A ausência de Organization não impede compreensão ou citação e não altera a nota.",
    )

    q_count = len(page.question_headings)
    faq_sim = "sim" if page.has_faq_schema else "não"
    _check(
        checks, issues, cid="geo.faq", label="Perguntas e respostas observadas", status="info", weight=0.0,
        value=f"{q_count} títulos-pergunta, FAQPage: {faq_sim}",
        hint="Use perguntas e respostas quando ajudarem o leitor. FAQPage não é requisito de busca com IA e seus resultados especiais têm elegibilidade limitada; esta observação não altera a nota.",
    )

    intro_len = page.first_paragraph_length or len(page.first_paragraph)
    _check(
        checks, issues, cid="geo.answer_first", label="Estrutura do primeiro parágrafo", status="info", weight=0.0,
        value=f"{intro_len} caracteres no primeiro parágrafo" if intro_len else "nenhum parágrafo de conteúdo",
        hint="Abertura observada no conteúdo principal quando identificado. Comprimento e presença de parágrafo dependem do idioma e do propósito; não medem qualidade nem alteram a nota.",
    )

    ratio = page.text_html_ratio
    if ratio >= RATIO_PASS:
        _check(
            checks, issues,
            cid="geo.extractable", label="Conteúdo extraível", status="pass", weight=2.0,
            value=f"{ratio:.1%} do HTML é texto",
            hint="A proporção texto/HTML é uma heurística; não reproduz a extração de cada buscador ou modelo.",
        )
    elif ratio >= RATIO_WARN:
        _check(
            checks, issues,
            cid="geo.extractable", label="Conteúdo extraível", status="warn", weight=2.0,
            value=f"{ratio:.1%} do HTML é texto",
            hint="A proporção texto/HTML é uma heurística; não reproduz a extração de cada buscador ou modelo.",
            severity="medium",
            title="Proporção de texto útil baixa",
            detail=f"Apenas {ratio:.1%} do HTML é conteúdo textual legível.",
            fix="Reduza markup inline e scripts, e entregue o conteúdo principal em HTML semântico.",
            impact=5,
        )
    else:
        _check(
            checks, issues,
            cid="geo.extractable", label="Conteúdo extraível", status="fail", weight=2.0,
            value=f"{ratio:.1%} do HTML é texto",
            hint="A proporção texto/HTML é uma heurística; não reproduz a extração de cada buscador ou modelo.",
            severity="high",
            title="Quase não há texto legível no HTML",
            detail=f"Apenas {ratio:.1%} do HTML é conteúdo textual legível.",
            fix=(
                "Confira se o conteúdo principal aparece no HTML inicial. Uma proporção baixa, isoladamente, não prova dependência de JavaScript."
            ),
            impact=9,
        )

    semantic = page.has_main or page.has_article
    _check(
        checks, issues,
        cid="geo.semantic_html", label="HTML semântico",
        status="pass" if semantic else "warn", weight=1.5,
        value="main/article presente" if semantic else "ausente",
        hint="Ajuda parsers de IA a isolar o conteúdo principal.",
        severity="medium",
        title="Falta HTML semântico",
        detail="Nenhuma tag <main> ou <article> encontrada.",
        fix="Envolva o conteúdo principal em <main> e cada conteúdo independente em <article>.",
        impact=4,
    )

    _check(
        checks, issues, cid="geo.structured", label="Blocos estruturados (listas/tabelas)", status="info", weight=0.0,
        value=f"{page.list_count} listas, {page.table_count} tabelas",
        hint="Use listas para passos e tabelas para comparações quando forem úteis. Nem toda página precisa desses formatos; esta observação não altera a nota.",
    )

    # ===================== CITABILIDADE =====================

    _check(
        checks, issues, cid="geo.citation_signals", label="Dados numéricos observados", status="info", weight=0.0,
        value=f"{page.number_signals} ocorrências numéricas",
        hint="Números podem ser preços, datas ou elementos de navegação. Esta contagem não verifica fontes, exatidão ou probabilidade de citação e não altera a nota.",
    )

    _check(
        checks, issues,
        cid="geo.author", label="Autoria declarada",
        status="pass" if page.author_name else "warn", weight=2.0,
        value=page.author_name or "não declarada",
        hint="Autoria e credenciais verificáveis podem ajudar o leitor a avaliar a origem; esta checagem identifica apenas declarações.",
        severity="medium",
        title="Conteúdo sem autoria declarada",
        detail="Não encontramos autor no schema nem na página.",
        fix="Declare o autor no schema (author) e exiba nome, cargo e credenciais na página.",
        impact=5,
    )

    freshness = page.date_modified or page.date_published
    _check(
        checks, issues,
        cid="geo.freshness", label="Data declarada do conteúdo",
        status="pass" if freshness else "warn", weight=1.5,
        value=freshness or "sem data declarada",
        hint="Registra a presença de uma data declarada; não verifica a atualização efetiva nem a exatidão do conteúdo.",
        severity="low",
        title="Conteúdo sem data de atualização",
        detail="Nenhum dateModified ou datePublished encontrado.",
        fix="Declare datePublished e dateModified no schema e mostre a data de atualização na página.",
        impact=3,
    )

    _check(
        checks, issues,
        cid="geo.breadcrumb", label="Breadcrumb estruturado",
        status="pass" if page.has_breadcrumb_schema else "info", weight=1.0,
        value="presente" if page.has_breadcrumb_schema else "ausente",
        hint="Ajuda a IA a entender a posição da página no site.",
    )

    if page.jsonld_types:
        _check(
            checks, issues,
            cid="geo.schema_types", label="Tipos de entidade encontrados",
            status="info", weight=1.0, value=", ".join(page.jsonld_types[:8]),
            hint="Tipos encontrados no JSON-LD. Quantidade não mede qualidade; os dados devem refletir o conteúdo visível.",
        )

    return checks, issues