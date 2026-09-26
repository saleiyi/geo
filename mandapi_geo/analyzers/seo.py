"""SEO técnico. Cada Check tem peso; o score da área vem de scoring.py."""

from __future__ import annotations

import re

from ..models import Check, Issue, PageFacts, SiteFacts

AREA = "seo"
TITLE_MIN, TITLE_MAX = 30, 60
DESC_MIN, DESC_MAX = 120, 160
SLOW_MS = 2000


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
    # Issues só entram quando o status é warn/fail E existe título correspondente.
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
    sample = (page.title or "") + (page.meta_description or "") + page.text[:1000]
    cjk_count = len(re.findall(r"[\u3040-\u30ff\u3400-\u9fff\uac00-\ud7af]", sample))
    cjk = (page.lang or "").lower().startswith(("zh", "ja", "ko")) or cjk_count / max(len(sample), 1) >= 0.2

    # ------------------------- Disponibilidade -------------------------

    if page.status_code == 200:
        _check(
            checks, issues,
            cid="seo.status", label="Status HTTP", status="pass", weight=3.0,
            value=str(page.status_code),
            hint="A página precisa responder 200.",
        )
    elif 300 <= page.status_code < 400:
        _check(
            checks, issues,
            cid="seo.status", label="Status HTTP", status="warn", weight=3.0,
            value=str(page.status_code),
            hint="A página precisa responder 200.",
            severity="high",
            title="A página não responde 200",
            detail=f"O servidor respondeu HTTP {page.status_code} após os redirecionamentos.",
            fix="Aponte a URL final para uma página que responda 200, sem depender de redirecionamento.",
            impact=10,
        )
    else:
        _check(
            checks, issues,
            cid="seo.status", label="Status HTTP", status="fail", weight=3.0,
            value=str(page.status_code),
            hint="A página precisa responder 200.",
            severity="critical",
            title="A página não responde 200",
            detail=f"O servidor respondeu HTTP {page.status_code}.",
            fix="Corrija o status do servidor ou redirecione para a URL correta.",
            impact=15,
        )

    # ------------------------- Title -------------------------

    title_len = page.title_len
    if not page.title:
        _check(
            checks, issues,
            cid="seo.title", label="Tag title", status="fail", weight=3.0,
            value="ausente",
            hint=f"Referência editorial de {TITLE_MIN}-{TITLE_MAX} caracteres, sem limite universal de ranking.",
            severity="critical",
            title="Página sem tag title",
            detail="A página não possui <title>.",
            fix=f"Escreva um title de {TITLE_MIN}-{TITLE_MAX} caracteres com a palavra-chave principal.",
            impact=12,
        )
    elif cjk:
        _check(
            checks, issues, cid="seo.title", label="Tag title", status="info", weight=0.0,
            value=f"{title_len} caracteres",
            hint="Título detectado em contexto CJK. Limites editoriais de caracteres latinos não se aplicam; revise clareza e exibição no idioma.",
        )
    elif TITLE_MIN <= title_len <= TITLE_MAX:
        _check(
            checks, issues,
            cid="seo.title", label="Tag title", status="pass", weight=3.0,
            value=f"{title_len} caracteres",
            hint=f"Referência editorial de {TITLE_MIN}-{TITLE_MAX} caracteres, sem limite universal de ranking.",
        )
    else:
        _check(
            checks, issues,
            cid="seo.title", label="Tag title", status="warn", weight=3.0,
            value=f"{title_len} caracteres",
            hint=f"Referência editorial de {TITLE_MIN}-{TITLE_MAX} caracteres, sem limite universal de ranking.",
            severity="medium",
            title="Title fora do tamanho ideal",
            detail=f'Título atual tem {title_len} caracteres: "{(page.title or "")[:90]}".',
            fix=(
                f"Reescreva o title com {TITLE_MIN}-{TITLE_MAX} caracteres, incluindo a "
                "tema principal. A exibição depende da largura, consulta e dispositivo; o Google pode reescrever o título."
            ),
            impact=8,
        )

    # ------------------------- Meta description -------------------------

    desc_len = page.meta_description_len
    if not page.meta_description:
        _check(
            checks, issues,
            cid="seo.meta_description", label="Meta description", status="fail", weight=2.0,
            value="ausente",
            hint=f"Referência editorial de {DESC_MIN}-{DESC_MAX} caracteres; o buscador pode gerar outro trecho.",
            severity="high",
            title="Meta description ausente",
            detail="A página não possui meta description.",
            fix=(
                f"Escreva uma meta description de {DESC_MIN}-{DESC_MAX} caracteres que resuma "
                "a página e seja útil ao leitor. O Google pode usar outro trecho no resultado."
            ),
            impact=6,
        )
    elif cjk:
        _check(
            checks, issues, cid="seo.meta_description", label="Meta description", status="info", weight=0.0,
            value=f"{desc_len} caracteres",
            hint="Descrição detectada em contexto CJK. Revise a utilidade no idioma; a quantidade de caracteres não determina o trecho exibido.",
        )
    elif DESC_MIN <= desc_len <= DESC_MAX:
        _check(
            checks, issues,
            cid="seo.meta_description", label="Meta description", status="pass", weight=2.0,
            value=f"{desc_len} caracteres",
            hint=f"Referência editorial de {DESC_MIN}-{DESC_MAX} caracteres; o buscador pode gerar outro trecho.",
        )
    else:
        _check(
            checks, issues,
            cid="seo.meta_description", label="Meta description", status="warn", weight=2.0,
            value=f"{desc_len} caracteres",
            hint=f"Referência editorial de {DESC_MIN}-{DESC_MAX} caracteres; o buscador pode gerar outro trecho.",
            severity="low",
            title="Meta description fora do tamanho ideal",
            detail=f"Descrição atual tem {desc_len} caracteres.",
            fix=f"Ajuste para {DESC_MIN}-{DESC_MAX} caracteres.",
            impact=3,
        )

    # ------------------------- H1 -------------------------

    if page.h1_count == 1:
        _check(
            checks, issues,
            cid="seo.h1", label="H1 único", status="pass", weight=2.5,
            value="1",
            hint="Um título principal claro costuma facilitar a leitura e manutenção da página.",
        )
    elif page.h1_count == 0:
        _check(
            checks, issues,
            cid="seo.h1", label="H1 único", status="fail", weight=2.5,
            value="0",
            hint="Um título principal claro costuma facilitar a leitura e manutenção da página.",
            severity="high",
            title="Página sem H1",
            detail="Não foi encontrado nenhum H1, que é o título principal para buscadores.",
            fix="Adicione um H1 com o tema central da página.",
            impact=8,
        )
    else:
        _check(
            checks, issues,
            cid="seo.h1", label="H1 único", status="warn", weight=2.5,
            value=str(page.h1_count),
            hint="Um título principal claro costuma facilitar a leitura e manutenção da página.",
            severity="medium",
            title=f"Página com {page.h1_count} H1",
            detail="Foram encontrados vários H1. Verifique se a estrutura mantém uma hierarquia clara; isso não prova perda de ranking.",
            fix="Mantenha um único H1 e rebaixe os demais para H2.",
            impact=6,
        )

    # ------------------------- Hierarquia -------------------------

    if page.h2_count >= 2:
        _check(
            checks, issues,
            cid="seo.headings", label="Hierarquia de títulos", status="pass", weight=2.0,
            value=f"H2: {page.h2_count} / H3: {page.h3_count}",
            hint="Use H2/H3 para dividir o conteúdo em blocos.",
        )
    else:
        _check(
            checks, issues,
            cid="seo.headings", label="Hierarquia de títulos",
            status="warn" if page.h2_count == 1 else "fail", weight=2.0,
            value=f"H2: {page.h2_count} / H3: {page.h3_count}",
            hint="Use H2/H3 para dividir o conteúdo em blocos.",
            severity="medium",
            title="Conteúdo com pouca subdivisão em subtítulos",
            detail=f"Encontrados {page.h2_count} H2 e {page.h3_count} H3.",
            fix="Quebre o texto em seções com H2 e subseções com H3, cobrindo subtemas da palavra-chave.",
            impact=5,
        )

    # ------------------------- Canonical -------------------------

    _check(
        checks, issues,
        cid="seo.canonical", label="URL canônica",
        status="pass" if page.canonical else "warn", weight=1.5,
        value=page.canonical or "ausente",
        hint="Evita conteúdo duplicado.",
        severity="medium",
        title="Tag canonical ausente",
        detail="Sem canonical, o Google pode escolher outra URL como principal.",
        fix='Adicione <link rel="canonical"> apontando para a URL definitiva da página.',
        impact=4,
    )

    # ------------------------- Idioma -------------------------

    _check(
        checks, issues,
        cid="seo.lang", label="Atributo lang",
        status="pass" if page.lang else "warn", weight=1.5,
        value=page.lang or "ausente",
        hint="Informa o idioma da página (ex: pt-BR).",
        severity="low",
        title="Idioma da página não declarado",
        detail="Sem o atributo lang, buscadores e IAs podem interpretar o idioma errado.",
        fix='Declare <html lang="pt-BR">.',
        impact=3,
    )

    # ------------------------- Mobile -------------------------

    _check(
        checks, issues,
        cid="seo.viewport", label="Meta viewport (mobile)",
        status="pass" if page.has_viewport else "fail", weight=2.0,
        value="presente" if page.has_viewport else "ausente",
        hint="A configuração de viewport ajuda a apresentação em dispositivos móveis.",
        severity="high",
        title="Página sem meta viewport",
        detail="Não foi encontrada uma meta viewport. A usabilidade móvel precisa ser conferida no navegador.",
        fix='Adicione <meta name="viewport" content="width=device-width, initial-scale=1">.',
        impact=7,
    )

    # ------------------------- HTTPS -------------------------

    _check(
        checks, issues,
        cid="seo.https", label="HTTPS",
        status="pass" if page.is_https else "fail", weight=2.0,
        value="sim" if page.is_https else "não",
        hint="HTTPS protege a conexão e contribui para a confiança do usuário.",
        severity="high",
        title="Site sem HTTPS",
        detail="A URL final usa HTTP e não protege a conexão com TLS.",
        fix="Instale um certificado SSL (Let's Encrypt é gratuito) e redirecione HTTP para HTTPS.",
        impact=8,
    )

    # ------------------------- Dados estruturados -------------------------

    _check(
        checks, issues, cid="seo.schema", label="Dados estruturados (JSON-LD)", status="info", weight=0.0,
        value=", ".join(page.jsonld_types[:6]) or "nenhum",
        hint="Tipos observados em JSON-LD. Adicione dados estruturados somente quando apropriados; não são requisito de ranking ou citação. Não validamos todos os campos, Microdata ou RDFa.",
    )

    # ------------------------- Open Graph -------------------------

    og_count = len(page.og_tags)
    if og_count >= 3:
        _check(
            checks, issues,
            cid="seo.open_graph", label="Open Graph", status="pass", weight=1.0,
            value=f"{og_count} tags",
            hint="Controla como o link aparece ao ser compartilhado.",
        )
    else:
        _check(
            checks, issues,
            cid="seo.open_graph", label="Open Graph",
            status="warn" if og_count else "fail", weight=1.0,
            value=f"{og_count} tags",
            hint="Controla como o link aparece ao ser compartilhado.",
            severity="low",
            title="Open Graph incompleto",
            detail=f"Encontradas {og_count} tags og:.",
            fix="Adicione og:title, og:description, og:image e og:url.",
            impact=2,
        )

    # ------------------------- Imagens -------------------------

    coverage = page.alt_coverage
    missing_alt = max(0, page.images_total - page.images_with_alt - page.images_with_empty_alt)
    alt_value = (
        f"{page.images_with_alt} descritivos; {page.images_with_empty_alt} vazios; "
        f"{missing_alt} sem atributo alt"
    )
    if page.images_total == 0:
        _check(
            checks, issues, cid="seo.image_alt", label="Alt text das imagens", status="info", weight=0.0,
            value="nenhuma imagem", hint="Texto alternativo apoia acessibilidade. Imagens decorativas podem usar alt vazio.",
        )
    elif missing_alt == 0:
        _check(
            checks, issues, cid="seo.image_alt", label="Alt text das imagens", status="pass", weight=1.5,
            value=alt_value,
            hint="Todas as imagens declaram alt. Confirme manualmente se textos descrevem imagens informativas e se os atributos vazios correspondem a imagens decorativas.",
        )
    else:
        _check(
            checks, issues, cid="seo.image_alt", label="Alt text das imagens",
            status="warn" if coverage >= 0.6 else "fail", weight=1.5, value=alt_value,
            hint="Atributo alt vazio pode ser intencional para decoração; atributo ausente precisa ser revisado.",
            severity="medium", title="Imagens sem atributo alt",
            detail=f"{missing_alt} de {page.images_total} imagens não declaram o atributo alt.",
            fix="Descreva imagens informativas com alt útil e declare alt vazio nas imagens puramente decorativas.", impact=4,
        )

    # A missing robots.txt does not prohibit crawling. Network failures are unknown.
    robots_value = "válido (HTTP 200)" if site.robots_status == 200 and site.robots_txt is not None else (
        "ausente (HTTP 404/410), sem bloqueio por este arquivo" if site.robots_status in {404, 410} else "não verificado"
    )
    _check(
        checks, issues, cid="seo.robots", label="robots.txt", status="info", weight=0.0,
        value=robots_value, hint="Arquivo opcional para orientar rastreamento. A permissão para esta URL é avaliada na seção GEO.",
    )

    # ------------------------- Sitemap -------------------------

    sitemap_found = site.sitemap_url_count > 0
    sitemap_absent = site.sitemap_status in {404, 410}
    _check(
        checks, issues, cid="seo.sitemap", label="sitemap.xml",
        status="pass" if sitemap_found else ("warn" if sitemap_absent else "info"),
        weight=1.0 if sitemap_found or sitemap_absent else 0.0,
        value=f"{site.sitemap_url_count} entradas loc" if sitemap_found else ("não encontrado (HTTP 404/410)" if sitemap_absent else "não verificado"),
        hint="Sitemaps podem conter páginas ou referências a outros sitemaps. Ajudam na descoberta, mas não garantem indexação; falha de consulta não comprova ausência.",
        severity="low", title="Sitemap não encontrado nos endereços consultados",
        detail="Os endereços consultados responderam HTTP 404/410. Um sitemap pode existir em outro caminho e não é obrigatório para todas as páginas.",
        fix="Se for útil para a descoberta do site, publique um sitemap válido e indique sua localização em robots.txt.", impact=2,
    )

    # ------------------------- Volume de conteúdo -------------------------

    _check(
        checks, issues, cid="seo.word_count", label="Volume de texto observado", status="info", weight=0.0,
        value=f"{page.word_count} unidades de texto",
        hint="Estimativa por palavras separadas e caracteres CJK. Não existe um mínimo universal para ranking ou citação; avalie a intenção da página sem preenchimento artificial.",
    )

    # ------------------------- Links internos -------------------------

    _check(
        checks, issues,
        cid="seo.internal_links", label="Links internos",
        status="pass" if page.internal_links >= 5 else ("warn" if page.internal_links else "fail"),
        weight=1.5,
        value=str(page.internal_links),
        hint="Distribui autoridade e ajuda a IA a mapear o site.",
        severity="medium",
        title="Poucos links internos",
        detail=f"Encontrados {page.internal_links} links internos.",
        fix="Adicione links contextuais para páginas relacionadas do próprio site.",
        impact=4,
    )

    # ------------------------- hreflang (contexto LatAm) -------------------------

    if page.hreflang:
        _check(
            checks, issues,
            cid="seo.hreflang", label="hreflang", status="pass", weight=1.0,
            value=", ".join(page.hreflang[:6]),
            hint="Bom sinal para operação multi-país na América Latina.",
        )
    else:
        _check(
            checks, issues,
            cid="seo.hreflang", label="hreflang", status="info", weight=1.0,
            value="não declarado",
            hint="Relevante apenas se o site atende mais de um país ou idioma.",
        )

    # ------------------------- Tempo de resposta -------------------------

    if page.elapsed_ms <= SLOW_MS:
        _check(
            checks, issues,
            cid="seo.request_time", label="Tempo total da requisição", status="pass", weight=1.5,
            value=f"{page.elapsed_ms} ms",
            hint=f"Download do HTML e redirecionamentos a partir do scanner; referência de {SLOW_MS} ms. Não é TTFB nem Core Web Vitals.",
        )
    else:
        _check(
            checks, issues,
            cid="seo.request_time", label="Tempo total da requisição",
            status="warn" if page.elapsed_ms <= SLOW_MS * 2 else "fail", weight=1.5,
            value=f"{page.elapsed_ms} ms",
            hint=f"Download do HTML e redirecionamentos a partir do scanner; referência de {SLOW_MS} ms. Não é TTFB nem Core Web Vitals.",
            severity="high" if page.elapsed_ms > SLOW_MS * 2 else "medium",
            title="Tempo total da requisição elevado",
            detail=f"A requisição completa levou {page.elapsed_ms} ms, incluindo transferência do HTML e eventuais redirecionamentos.",
            fix="Ative cache, CDN e compressão. Verifique a hospedagem no Brasil/LatAm.",
            impact=5,
        )

    # ------------------------- Peso do HTML -------------------------

    kb = page.page_bytes / 1024
    _check(
        checks, issues,
        cid="seo.page_size", label="Peso do HTML",
        status="pass" if kb <= 500 else ("warn" if kb <= 1500 else "fail"), weight=1.0,
        value=f"{kb:.0f} KB",
        hint="Considera apenas o HTML, não os assets.",
        severity="low",
        title="HTML da página muito pesado",
        detail=f"O HTML tem {kb:.0f} KB antes de carregar imagens, CSS e JS.",
        fix="Reduza markup inline, scripts e CSS embutidos no HTML.",
        impact=2,
    )

    return checks, issues
