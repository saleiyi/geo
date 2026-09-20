"""GEO / AEO - o diferencial do produto.

Pergunta central: "uma IA consegue ler, entender e CITAR este site?"

Checagens divididas em 3 grupos:
  1. Acesso       - a IA consegue entrar? (robots, llms.txt, indexabilidade)
  2. Compreensão  - a IA entende a entidade e o conteúdo?
  3. Citabilidade - o conteúdo merece ser citado? (dados, autoria, frescor)
"""

from __future__ import annotations

from ..models import Check, Issue, PageFacts, SiteFacts

AREA = "geo"

# Os bots que realmente decidem se o site aparece em resposta de IA.
KEY_BOTS: dict[str, str] = {
    "gptbot": "GPTBot (ChatGPT)",
    "oai-searchbot": "OAI-SearchBot (ChatGPT Search)",
    "claudebot": "ClaudeBot (Claude)",
    "perplexitybot": "PerplexityBot (Perplexity)",
    "google-extended": "Google-Extended (AI Overviews)",
}

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

    blocked = [KEY_BOTS[b] for b in KEY_BOTS if site.ai_crawler_rules.get(b) == "block"]
    partial = [KEY_BOTS[b] for b in KEY_BOTS if site.ai_crawler_rules.get(b) == "partial"]

    if blocked:
        _check(
            checks, issues,
            cid="geo.ai_crawlers", label="Acesso dos bots de IA", status="fail", weight=4.0,
            value="bloqueado: " + ", ".join(blocked),
            hint="Se o robots.txt bloqueia um bot de IA, ele não pode citar seu site.",
            severity="critical",
            title="Bots de IA estão bloqueados no robots.txt",
            detail="Bloqueados: " + ", ".join(blocked) + ". Estes agentes não conseguem ler o site.",
            fix=(
                "Remova as regras Disallow que atingem GPTBot, ClaudeBot, PerplexityBot, "
                "OAI-SearchBot e Google-Extended. Sem isso, sua marca é invisível em resposta de IA."
            ),
            impact=20,
        )
    elif partial:
        _check(
            checks, issues,
            cid="geo.ai_crawlers", label="Acesso dos bots de IA", status="warn", weight=4.0,
            value="bloqueio parcial: " + ", ".join(partial),
            hint="Bloqueios parciais podem esconder páginas importantes da IA.",
            severity="high",
            title="Rastreamento de IA parcialmente bloqueado",
            detail="Regras Disallow atingem caminhos de " + ", ".join(partial) + ".",
            fix=(
                "Revise as regras Disallow: caminhos como /admin ou /checkout podem ser bloqueados, "
                "mas as páginas de conteúdo, serviços e FAQ precisam ficar abertas para IA."
            ),
            impact=10,
        )
    elif site.robots_txt:
        _check(
            checks, issues,
            cid="geo.ai_crawlers", label="Acesso dos bots de IA", status="pass", weight=4.0,
            value="nenhum bot de IA bloqueado",
            hint="Se o robots.txt bloqueia um bot de IA, ele não pode citar seu site.",
        )
    else:
        _check(
            checks, issues,
            cid="geo.ai_crawlers", label="Acesso dos bots de IA", status="warn", weight=4.0,
            value="robots.txt não encontrado",
            hint="Sem robots.txt não há regra explícita, mas também não há sinal de abertura.",
            severity="high",
            title="robots.txt ausente: regras de IA indefinidas",
            detail=(
                "O site não publica robots.txt. Nada bloqueia a IA, mas também não existe "
                "orientação explícita de acesso, e nenhum sitemap pode ser declarado."
            ),
            fix=(
                "Publique um robots.txt permitindo explicitamente GPTBot, ClaudeBot, "
                "PerplexityBot, OAI-SearchBot e Google-Extended, e declare o sitemap."
            ),
            impact=8,
        )

    has_llms = bool(site.llms_txt)
    _check(
        checks, issues,
        cid="geo.llms_txt", label="llms.txt", status="pass" if has_llms else "fail", weight=3.0,
        value="presente" if has_llms else "ausente",
        hint="Padrão emergente para descrever o site diretamente para LLMs.",
        severity="high",
        title="Arquivo llms.txt ausente",
        detail="Não encontramos /llms.txt na raiz do domínio.",
        fix=(
            "Publique /llms.txt com a descrição da empresa, principais páginas e as perguntas "
            "que o site responde. É o equivalente do robots.txt para IA."
        ),
        impact=12,
    )

    robots_meta = (page.meta_robots or "").lower()
    if "noindex" in robots_meta:
        _check(
            checks, issues,
            cid="geo.indexable", label="Indexabilidade", status="fail", weight=3.0,
            value=page.meta_robots or "—",
            hint="noindex impede qualquer aparição em busca e em IA.",
            severity="critical",
            title="Página marcada como noindex",
            detail=f'meta robots = "{page.meta_robots}".',
            fix="Remova o noindex da página principal do negócio.",
            impact=18,
        )
    elif "nosnippet" in robots_meta:
        _check(
            checks, issues,
            cid="geo.indexable", label="Indexabilidade", status="warn", weight=3.0,
            value=page.meta_robots or "—",
            hint="nosnippet reduz drasticamente o que a IA pode reproduzir de você.",
            severity="high",
            title="Página com nosnippet ativo",
            detail=f'meta robots = "{page.meta_robots}".',
            fix="Remova nosnippet se você quer ser citado em respostas de IA.",
            impact=12,
        )
    else:
        _check(
            checks, issues,
            cid="geo.indexable", label="Indexabilidade", status="pass", weight=3.0,
            value=page.meta_robots or "sem restrição",
            hint="noindex impede qualquer aparição em busca e em IA.",
        )

    # ===================== COMPREENSÃO =====================

    _check(
        checks, issues,
        cid="geo.entity", label="Entidade declarada (Schema)",
        status="pass" if page.has_organization_schema else "fail", weight=3.0,
        value="Organization/LocalBusiness presente" if page.has_organization_schema else "ausente",
        hint="Sem entidade explícita, a IA não sabe quem você é.",
        severity="critical",
        title="Entidade do negócio não está declarada",
        detail="Nenhum schema Organization ou LocalBusiness foi encontrado.",
        fix=(
            "Adicione JSON-LD com @type Organization: name, url, logo, sameAs "
            "(Instagram, LinkedIn, Google Business) e endereço. É isso que faz a IA "
            "reconhecer você como entidade, e não como texto solto."
        ),
        impact=16,
    )

    q_count = len(page.question_headings)
    faq_sim = "sim" if page.has_faq_schema else "não"
    if page.has_faq_schema and q_count >= 2:
        _check(
            checks, issues,
            cid="geo.faq", label="Estrutura de perguntas e respostas", status="pass", weight=3.0,
            value=f"{q_count} títulos-pergunta, FAQPage: {faq_sim}",
            hint="IA responde perguntas; conteúdo em formato de pergunta casa direto com a consulta.",
        )
    elif page.has_faq_schema or q_count >= 3:
        _check(
            checks, issues,
            cid="geo.faq", label="Estrutura de perguntas e respostas", status="warn", weight=3.0,
            value=f"{q_count} títulos-pergunta, FAQPage: {faq_sim}",
            hint="IA responde perguntas; conteúdo em formato de pergunta casa direto com a consulta.",
            severity="medium",
            title="Estrutura de FAQ incompleta",
            detail=f"Encontrados {q_count} títulos em formato de pergunta e FAQPage schema: {faq_sim}.",
            fix=(
                "Complete a seção de FAQ com pelo menos 5 perguntas reais de clientes "
                "e marque com FAQPage schema."
            ),
            impact=6,
        )
    else:
        _check(
            checks, issues,
            cid="geo.faq", label="Estrutura de perguntas e respostas", status="fail", weight=3.0,
            value=f"{q_count} títulos-pergunta, FAQPage: {faq_sim}",
            hint="IA responde perguntas; conteúdo em formato de pergunta casa direto com a consulta.",
            severity="high",
            title="Site não está estruturado em perguntas e respostas",
            detail=f"Encontrados {q_count} títulos em formato de pergunta e FAQPage schema: {faq_sim}.",
            fix=(
                'Crie uma seção de FAQ com perguntas reais dos clientes (ex: "Quanto custa...?", '
                '"Vocês atendem em...?") e marque com FAQPage schema.'
            ),
            impact=11,
        )

    intro_len = len(page.first_paragraph)
    if 40 <= intro_len <= 400:
        _check(
            checks, issues,
            cid="geo.answer_first", label="Resposta direta no início", status="pass", weight=2.5,
            value=f"{intro_len} caracteres no primeiro parágrafo",
            hint="IA extrai trechos; um resumo claro nos primeiros 400 caracteres é o que costuma ser citado.",
        )
    elif intro_len == 0:
        _check(
            checks, issues,
            cid="geo.answer_first", label="Resposta direta no início", status="fail", weight=2.5,
            value="nenhum parágrafo de conteúdo",
            hint="IA extrai trechos; um resumo claro nos primeiros 400 caracteres é o que costuma ser citado.",
            severity="high",
            title="Conteúdo não responde de forma direta no início",
            detail="Não encontramos um parágrafo de conteúdo com tamanho suficiente para ser citado.",
            fix=(
                "Comece a página com um parágrafo de 2 a 3 frases que responda objetivamente "
                "à principal dúvida do cliente."
            ),
            impact=7,
        )
    else:
        _check(
            checks, issues,
            cid="geo.answer_first", label="Resposta direta no início", status="warn", weight=2.5,
            value=f"{intro_len} caracteres no primeiro parágrafo",
            hint="IA extrai trechos; um resumo claro nos primeiros 400 caracteres é o que costuma ser citado.",
            severity="medium",
            title="Primeiro parágrafo longo demais para citação",
            detail=f"O primeiro parágrafo útil tem {intro_len} caracteres.",
            fix="Divida a abertura em um resumo curto (2-3 frases) seguido do detalhamento.",
            impact=4,
        )

    ratio = page.text_html_ratio
    if ratio >= RATIO_PASS:
        _check(
            checks, issues,
            cid="geo.extractable", label="Conteúdo extraível", status="pass", weight=2.0,
            value=f"{ratio:.1%} do HTML é texto",
            hint="Muito markup por pouco texto dificulta a leitura por LLM.",
        )
    elif ratio >= RATIO_WARN:
        _check(
            checks, issues,
            cid="geo.extractable", label="Conteúdo extraível", status="warn", weight=2.0,
            value=f"{ratio:.1%} do HTML é texto",
            hint="Muito markup por pouco texto dificulta a leitura por LLM.",
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
            hint="Muito markup por pouco texto dificulta a leitura por LLM.",
            severity="high",
            title="Quase não há texto legível no HTML",
            detail=f"Apenas {ratio:.1%} do HTML é conteúdo textual legível.",
            fix=(
                "O conteúdo provavelmente depende de JavaScript. Sirva o texto principal "
                "em HTML no servidor para que crawlers de IA consigam lê-lo."
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

    blocks = page.list_count + page.table_count
    if blocks >= 3:
        _check(
            checks, issues,
            cid="geo.structured", label="Blocos estruturados (listas/tabelas)", status="pass",
            weight=2.0,
            value=f"{page.list_count} listas, {page.table_count} tabelas",
            hint="Listas e tabelas são extraídas com muito mais precisão por LLMs.",
        )
    elif blocks >= 1:
        _check(
            checks, issues,
            cid="geo.structured", label="Blocos estruturados (listas/tabelas)", status="warn",
            weight=2.0,
            value=f"{page.list_count} listas, {page.table_count} tabelas",
            hint="Listas e tabelas são extraídas com muito mais precisão por LLMs.",
            severity="low",
            title="Poucos blocos estruturados",
            detail=f"Encontradas {page.list_count} listas e {page.table_count} tabelas.",
            fix="Converta comparações, passos e especificações em listas e tabelas.",
            impact=3,
        )
    else:
        _check(
            checks, issues,
            cid="geo.structured", label="Blocos estruturados (listas/tabelas)", status="fail",
            weight=2.0,
            value=f"{page.list_count} listas, {page.table_count} tabelas",
            hint="Listas e tabelas são extraídas com muito mais precisão por LLMs.",
            severity="medium",
            title="Conteúdo sem estrutura de lista ou tabela",
            detail=f"Encontradas {page.list_count} listas e {page.table_count} tabelas.",
            fix="Converta comparações, passos e especificações em listas e tabelas.",
            impact=5,
        )

    # ===================== CITABILIDADE =====================

    signals = page.number_signals
    if signals >= 5:
        _check(
            checks, issues,
            cid="geo.citation_signals", label="Sinais citáveis (dados concretos)", status="pass",
            weight=2.5,
            value=f"{signals} ocorrências numéricas",
            hint="IA cita com mais frequência conteúdo com números, prazos e especificações.",
        )
    elif signals >= 2:
        _check(
            checks, issues,
            cid="geo.citation_signals", label="Sinais citáveis (dados concretos)", status="warn",
            weight=2.5,
            value=f"{signals} ocorrências numéricas",
            hint="IA cita com mais frequência conteúdo com números, prazos e especificações.",
            severity="medium",
            title="Poucos dados concretos no conteúdo",
            detail=f"Encontradas {signals} ocorrências numéricas no texto.",
            fix="Inclua prazos, preços, anos de experiência e percentuais de resultado.",
            impact=5,
        )
    else:
        _check(
            checks, issues,
            cid="geo.citation_signals", label="Sinais citáveis (dados concretos)", status="fail",
            weight=2.5,
            value=f"{signals} ocorrências numéricas",
            hint="IA cita com mais frequência conteúdo com números, prazos e especificações.",
            severity="high",
            title="Conteúdo sem dados concretos",
            detail=f"Encontrados {signals} números ou percentuais no texto.",
            fix=(
                "Inclua dados verificáveis: prazos, preços, anos de experiência, número de clientes, "
                "percentuais de resultado. Trechos com dado concreto são os mais citados."
            ),
            impact=8,
        )

    _check(
        checks, issues,
        cid="geo.author", label="Autoria (E-E-A-T)",
        status="pass" if page.author_name else "warn", weight=2.0,
        value=page.author_name or "não declarada",
        hint="Conteúdo assinado é mais confiável para IA e Google.",
        severity="medium",
        title="Conteúdo sem autoria declarada",
        detail="Não encontramos autor no schema nem na página.",
        fix="Declare o autor no schema (author) e exiba nome, cargo e credenciais na página.",
        impact=5,
    )

    freshness = page.date_modified or page.date_published
    _check(
        checks, issues,
        cid="geo.freshness", label="Frescor do conteúdo",
        status="pass" if freshness else "warn", weight=1.5,
        value=freshness or "sem data declarada",
        hint="dateModified ajuda a IA a avaliar atualidade.",
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
            hint="Quanto mais tipos declarados, melhor a IA entende o contexto.",
        )

    return checks, issues