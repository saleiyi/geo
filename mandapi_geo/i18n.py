"""Deterministic report localization. Page evidence stays in its original language."""
from __future__ import annotations
from .models import ScanReport

MESSAGES = {
    'invalid_url': ('Informe uma URL pública HTTP(S), sem credenciais ou endereço local.', 'Enter a public HTTP(S) URL without credentials or a local address.', '请输入公开的 HTTP(S) 网址，不支持账号密码或内网地址。'),
    'quota': ('O limite diário de análises deste endereço foi atingido. Tente novamente após 00:00 UTC.', 'This address has reached its daily scan limit. Try again after 00:00 UTC.', '当前网络地址已达到每日扫描限额，请于 UTC 零点（北京时间早上 8 点）后重试。'),
    'busy': ('Todas as vagas de análise estão ocupadas. Tente novamente em alguns instantes.', 'All scan slots are busy. Please try again shortly.', '扫描服务繁忙，请稍后重试。'),
    'ai_disabled': ('O resumo por IA não está disponível para esta solicitação. Use o relatório técnico.', 'An AI summary is unavailable for this request. Use the technical report.', '当前请求不支持 AI 摘要，请使用技术诊断报告。'),
    'scan_failed': ('Não foi possível analisar a página. Confira a URL e tente novamente.', 'Could not scan this page. Check the URL and try again.', '未能完成页面扫描，请检查网址并重试。'),
    'timeout': ('O site demorou a responder. Tente novamente mais tarde.', 'The website took too long to respond. Try again later.', '目标网站响应超时，请稍后重试。'),
    'blocked': ('O site recusou o acesso do scanner. Revise o firewall ou tente outra página pública.', 'The website refused the scanner. Check its firewall or try another public page.', '目标网站拒绝了扫描器访问，请检查其防火墙设置或尝试其他公开页面。'),
    'rate': ('O site está limitando solicitações. Aguarde antes de tentar novamente.', 'The website is limiting requests. Wait before trying again.', '目标网站正在限制访问频率，请等待一段时间再试。'),
    'html': ('Esta URL não retornou uma página HTML analisável.', 'This URL did not return an HTML page that can be analyzed.', '此网址未返回可供分析的 HTML 网页。'),
    'large': ('A página excedeu o limite de tamanho da análise.', 'The page exceeded the scan size limit.', '目标页面超过扫描大小限制。'),
}

def message(key: str, language: str, reason: str = '') -> str:
    if key == 'scan_failed' and reason:
        raw = reason.lower()
        if '429' in raw: key = 'rate'
        elif '403' in raw or '401' in raw: key = 'blocked'
        elif 'tempo' in raw or 'timeout' in raw or 'prazo' in raw: key = 'timeout'
        elif 'html' in raw: key = 'html'
        elif 'tamanho' in raw or 'limite de' in raw: key = 'large'
        elif 'privad' in raw or 'públic' in raw or 'local' in raw: key = 'invalid_url'
    return MESSAGES[key][{'pt-BR': 0, 'en': 1, 'zh-CN': 2}.get(language, 0)]

# Each entry: English label, Chinese label, English guidance, Chinese guidance.
CHECK_TEXT = {
 'seo.status': ('HTTP response', 'HTTP 响应状态', 'Use a public page that returns HTTP 200 after redirects.', '确保公开页面经过重定向后返回 HTTP 200。'),
 'seo.title': ('Page title', '页面标题', 'Write a unique, descriptive title. Length thresholds are editorial heuristics, not ranking requirements.', '为页面撰写独特、准确的标题。字符长度仅为编辑参考，不是排名要求。'),
 'seo.meta_description': ('Meta description', '页面描述', 'Summarize the page accurately in a unique meta description. Search engines may choose different snippet text.', '用独特的 meta description 准确概括页面；搜索引擎可能采用其他摘要文字。'),
 'seo.h1': ('Main heading', '主标题 H1', 'Use a clear main heading and a meaningful heading hierarchy; multiple H1s are not an automatic ranking penalty.', '使用清晰的主标题及合理层级；多个 H1 并不意味着必然受到排名惩罚。'),
 'seo.headings': ('Heading structure', '标题层级', 'Use descriptive H2 and H3 headings when they help readers navigate the content.', '在有助于阅读时使用描述性的 H2、H3 标题划分内容。'),
 'seo.canonical': ('Canonical URL', '规范网址', 'Declare the preferred absolute page URL with rel="canonical" and keep it consistent with redirects.', '通过 rel="canonical" 声明首选绝对网址，并与重定向保持一致。'),
 'seo.lang': ('Page language', '页面语言', 'Declare the actual content language on the html element, for example en or zh-CN.', '在 html 元素中声明实际内容语言，例如 en 或 zh-CN。'),
 'seo.viewport': ('Mobile viewport', '移动端视口', 'Add width=device-width, initial-scale=1 to the viewport meta tag and check the layout on a phone.', '为 viewport 添加 width=device-width, initial-scale=1，并在手机上检查布局。'),
 'seo.https': ('HTTPS connection', 'HTTPS 连接', 'Serve the page over HTTPS with a valid certificate and redirect HTTP requests to it.', '使用有效证书通过 HTTPS 提供页面，并重定向 HTTP 请求。'),
 'seo.schema': ('Structured data', '结构化数据', 'Add relevant, valid JSON-LD that matches visible content. Structured data is not required for AI citations.', '可添加与可见内容一致且适用的 JSON-LD；结构化数据不是获得 AI 引用的必要条件。'),
 'seo.open_graph': ('Social link preview', '社交分享预览', 'Provide og:title, og:description, og:image and og:url for useful link previews.', '补充 og:title、og:description、og:image 和 og:url，改善链接分享预览。'),
 'seo.image_alt': ('Image alternative text', '图片替代文本', 'Describe informative images with useful alt text; decorative images can use an empty alt attribute.', '为信息性图片编写有意义的 alt 文本；装饰图片可使用空 alt 属性。'),
 'seo.robots': ('robots.txt', 'robots.txt', 'This optional file declares crawler rules. Missing files do not themselves block crawling; permission checks appear under AI readiness.', '该可选文件声明爬虫规则。文件缺失不代表禁止抓取；具体权限见 AI 搜索准备度检查。'),
 'seo.sitemap': ('XML sitemap', 'XML 站点地图', 'Publish a valid XML sitemap and reference it in robots.txt. A sitemap supports discovery but does not guarantee indexing.', '发布有效的 XML 站点地图并在 robots.txt 中声明；它有助于发现页面，但不保证收录。'),
 'seo.word_count': ('Observed text volume', '已提取文本量', 'There is no universal minimum word count. Cover the user’s question without adding filler.', '不存在通用的最低字数要求。充分回答用户问题，避免为凑字数添加无用内容。'),
 'seo.internal_links': ('Internal links', '内部链接', 'Add useful contextual links to relevant pages on the same website.', '在合适的上下文中链接到站内相关页面，帮助用户继续探索。'),
 'seo.hreflang': ('Language alternatives', '多语言替代页面', 'For multilingual sites, provide reciprocal hreflang links for equivalent pages.', '多语言网站应为内容对应的页面设置互相指向的 hreflang 链接。'),
 'seo.request_time': ('Total request time', '完整请求耗时', 'Measured from this scanner, including redirects and HTML transfer. This is not TTFB or Core Web Vitals; verify performance from your audience’s location.', '由扫描服务器测量，包含重定向与 HTML 下载；不等于首字节时间或核心网页指标，请在受众地区进一步验证性能。'),
 'seo.page_size': ('HTML size', 'HTML 大小', 'Reduce unnecessary inline markup and scripts. This measurement excludes CSS, images and other assets.', '减少冗余的内联标记和脚本；此处仅测量 HTML，不含图片、CSS 等资源。'),
 'geo.ai_crawlers': ('Search crawler permissions', '搜索爬虫权限', 'Review rules for this page’s path. Search crawler access and model-training permissions are different; declared permission does not prove actual access or citation.', '检查适用于当前页面路径的规则。搜索爬虫与模型训练权限不同；允许抓取并不证明实际访问或引用。'),
 'geo.training_bots': ('AI training preferences', 'AI 训练使用偏好', 'Training permissions are informational and do not change the score. GPTBot is distinct from OAI-SearchBot.', '训练权限仅供参考，不影响评分。GPTBot 与 OAI-SearchBot 的用途不同。'),
 'geo.llms_txt': ('Optional llms.txt', '可选的 llms.txt', 'An optional proposal for compatible tools, not a Google Search requirement. Presence or absence does not change this score.', '面向兼容工具的可选提案，并非 Google 搜索要求；有无该文件不影响评分。'),
 'geo.indexable': ('Indexing and snippet directives', '收录与摘要指令', 'Review meta robots and X-Robots-Tag. Remove restrictions only when the page is intended to be indexed; this check does not query search indexes.', '检查 meta robots 与 X-Robots-Tag，仅在确实希望页面被收录时移除限制；此项不查询搜索引擎索引。'),
 'geo.link_following': ('Link-following directives', '链接跟随指令', 'nofollow concerns following links; on its own it does not prevent this page from being indexed.', 'nofollow 涉及页面链接的跟随行为，单独存在不表示当前页面禁止收录。'),
 'geo.entity': ('Declared organization', '已声明的组织实体', 'If relevant, describe the organization in JSON-LD using accurate name, URL and official profiles that match the visible page.', '如适用，可在 JSON-LD 中声明组织的真实名称、网址及官方资料，并与可见内容一致。'),
 'geo.faq': ('Questions and answers', '问答内容', 'Answer real audience questions where useful. FAQ markup is optional and must match visible content.', '在有助于读者时回答真实问题；FAQ 标记是可选项，必须与可见内容一致。'),
 'geo.answer_first': ('Opening paragraph', '开篇段落', 'Introduce the page’s purpose clearly. Paragraph length is only a structural signal, not evidence of answer quality.', '在开篇清晰说明页面主题。段落长度只是结构信号，不代表回答质量。'),
 'geo.extractable': ('Extractable text', '可提取文本', 'Make essential content available in HTML. Text-to-HTML ratio is only a heuristic and does not reproduce a search engine’s rendering.', '在 HTML 中提供核心内容。文本与 HTML 比例只是启发式指标，不等同于搜索引擎渲染结果。'),
 'geo.semantic_html': ('Semantic HTML', '语义化 HTML', 'Use main for the primary content and article where it describes a self-contained piece.', '使用 main 标识主要内容，并在适用时用 article 表示独立文章。'),
 'geo.structured': ('Lists and tables', '列表与表格', 'Use lists for steps and tables for comparisons when helpful. Their presence does not guarantee an AI citation.', '在有助于理解时使用列表呈现步骤、表格呈现比较；这些元素不保证 AI 引用。'),
 'geo.citation_signals': ('Observed numeric occurrences', '已观察的数字数量', 'Use relevant, verifiable facts and sources. Counting numbers does not verify their accuracy and does not affect the score.', '引用相关、可验证的事实和来源。数字计数不能验证准确性，不影响评分。'),
 'geo.author': ('Declared authorship', '已声明的作者', 'Where appropriate, show the author’s real identity and relevant credentials. This check only detects declarations.', '在适用时展示作者真实身份与相关资历；此项仅检测声明，不能验证可信度。'),
 'geo.freshness': ('Declared content date', '已声明的内容日期', 'Show genuine publication and update dates when relevant. A date does not prove the content is current.', '如适用，展示真实发布日期与更新日期；存在日期不能证明内容确实已更新。'),
 'geo.breadcrumb': ('Breadcrumb markup', '面包屑标记', 'Use breadcrumbs where a meaningful page hierarchy exists; they are optional.', '在有明确层级的页面使用面包屑导航；此项为可选。'),
 'geo.schema_types': ('Observed schema types', '已发现的结构化数据类型', 'The presence of a schema type does not validate every field or establish content quality.', '检测到结构化数据类型，不代表所有字段有效或内容质量已验证。'),
}

LIMITATIONS = {
 'en': [
  'One page and public origin files only; this is not a full-site crawl.',
  'Received HTML is analyzed without executing JavaScript; browser-rendered content may be missing.',
  'Scores are technical readiness heuristics, not measurements of ranking, traffic, indexing or actual AI citations.',
  'robots.txt records declared permissions; it does not prove actual crawler, CDN or firewall behavior.',
  'An optional keyword is context only; no search volume, competition or ranking lookup is performed.',
 ],
 'zh-CN': [
  '仅分析一个页面及其站点公开文件，不是全站爬取。',
  '仅分析收到的 HTML，不执行 JavaScript，可能遗漏浏览器渲染的内容。',
  '评分是技术准备度的启发式评估，不测量排名、流量、实际收录或真实 AI 引用。',
  'robots.txt 仅说明声明的权限，不能证明实际爬虫访问、CDN 或防火墙行为。',
  '可选关键词仅作为报告背景，不查询搜索量、竞争程度或搜索排名。',
 ]
}

def _value(check, report, zh):
    p, site = report.facts, report.site
    present, absent = ('已发现', '未发现') if zh else ('Present', 'Not found')
    unknown = '未能验证' if zh else 'Not verified'
    if not p: return check.value
    char = '字符' if zh else 'characters'
    vals = {
      'seo.status': str(p.status_code), 'seo.title': f'{p.title_len} {char}' if p.title else absent,
      'seo.meta_description': f'{p.meta_description_len} {char}' if p.meta_description else absent,
      'seo.h1': str(p.h1_count), 'seo.headings': f'H2: {p.h2_count} / H3: {p.h3_count}',
      'seo.canonical': p.canonical or absent, 'seo.lang': p.lang or absent,
      'seo.viewport': present if p.has_viewport else absent,
      'seo.https': 'HTTPS' if p.is_https else 'HTTP', 'seo.schema': ', '.join(p.jsonld_types) or absent,
      'seo.open_graph': ', '.join(p.og_tags) or absent,
      'seo.image_alt': ((f'已描述 {p.images_with_alt}；空 alt {p.images_with_empty_alt}；缺少 alt {max(0, p.images_total - p.images_with_alt - p.images_with_empty_alt)}' if zh else f'Described: {p.images_with_alt}; empty alt: {p.images_with_empty_alt}; missing alt: {max(0, p.images_total - p.images_with_alt - p.images_with_empty_alt)}') if p.images_total else ('无图片' if zh else 'No images')),
      'seo.word_count': f'{p.word_count} ' + ('文本单位' if zh else 'text units'), 'seo.internal_links': str(p.internal_links),
      'seo.hreflang': ', '.join(p.hreflang) or absent, 'seo.request_time': f'{p.elapsed_ms} ms',
      'seo.page_size': f'{p.page_bytes / 1024:.0f} KB',
      'geo.entity': present if p.has_organization_schema else absent,
      'geo.faq': (f'问句标题：{len(p.question_headings)}；FAQPage：' if zh else f'Question headings: {len(p.question_headings)}; FAQPage: ') + (present if p.has_faq_schema else absent),
      'geo.answer_first': f'{p.first_paragraph_length or len(p.first_paragraph)} {char}',
      'geo.extractable': f'{p.text_html_ratio:.1%}',
      'geo.semantic_html': present if p.has_main or p.has_article else absent,
      'geo.structured': f'列表：{p.list_count}；表格：{p.table_count}' if zh else f'Lists: {p.list_count}; tables: {p.table_count}',
      'geo.citation_signals': str(p.number_signals), 'geo.author': p.author_name or absent,
      'geo.freshness': p.date_modified or p.date_published or absent,
      'geo.breadcrumb': present if p.has_breadcrumb_schema else absent,
      'geo.schema_types': ', '.join(p.jsonld_types) or absent,
    }
    if site:
        vals['geo.training_bots'] = unknown
        vals['seo.robots'] = f'HTTP {site.robots_status}' if site.robots_status and not (site.robots_status == 200 and site.robots_txt is None) else unknown
        vals['seo.sitemap'] = (f'{site.sitemap_url_count} ' + ('loc 条目' if zh else 'loc entries')) if site.sitemap_url_count else (absent if site.sitemap_status in {404, 410} else unknown)
        vals['geo.llms_txt'] = present if site.llms_status == 200 and site.llms_txt else (absent if site.llms_status in {404, 410} else unknown)
        if site.robots_status in {404, 410}:
            vals['geo.ai_crawlers'] = 'HTTP 404/410：未声明爬取规则' if zh else 'HTTP 404/410: no declared crawler rules'
        elif site.robots_status == 200 and site.robots_txt is not None:
            bots = ('googlebot', 'oai-searchbot', 'perplexitybot', 'claude-searchbot')
            states = {'allow': '允许', 'block': '禁止', 'partial': '部分限制', 'unspecified': '未单独声明'} if zh else {'allow': 'allowed', 'block': 'blocked', 'partial': 'partial', 'unspecified': 'unspecified'}
            vals['geo.ai_crawlers'] = '; '.join(f'{b}: {states.get(site.ai_crawler_rules.get(b), unknown)}' for b in bots)
            vals['geo.training_bots'] = '; '.join(f'{b}: {states.get(site.ai_crawler_rules.get(b), unknown)}' for b in ('gptbot', 'claudebot', 'google-extended', 'applebot-extended', 'ccbot'))
        else:
            vals['geo.ai_crawlers'] = unknown
            vals['geo.training_bots'] = unknown
    if check.id in ('geo.indexable', 'geo.link_following'):
        raw = check.value or ''
        replacements = {'sem restrição de indexação observada': '未发现收录限制' if zh else 'No indexing restriction observed', 'sem nofollow observado': '未发现 nofollow' if zh else 'No nofollow observed', 'restrição de trechos': '摘要限制' if zh else 'Snippet restriction'}
        for old, new in replacements.items(): raw = raw.replace(old, new)
        return raw
    return vals.get(check.id, check.value)

def localize_report(report: ScanReport, language: str) -> ScanReport:
    if language == 'pt-BR': return report
    result = report.model_copy(deep=True)
    zh = language == 'zh-CN'
    result.limitations = LIMITATIONS[language].copy()
    labels = {'seo': '技术 SEO' if zh else 'Technical SEO', 'geo': 'AI 搜索准备度' if zh else 'AI search readiness', 'content': '内容' if zh else 'Content'}
    checks = {}
    for area in result.areas:
        area.label = labels[area.area]
        for check in area.checks:
            entry = CHECK_TEXT.get(check.id)
            if entry:
                check.label = entry[1 if zh else 0]
                check.hint = entry[3 if zh else 2]
                check.value = _value(check, result, zh)
            checks[check.id] = check
    def translate_issue(issue):
        check = checks.get(issue.id)
        if not check: return
        issue.title = ('需要检查：' if zh else 'Review: ') + check.label
        issue.detail = ('本次检测：' if zh else 'Observed in this scan: ') + (check.value or ('未能验证' if zh else 'Not verified'))
        issue.fix = check.hint or ''
    for area in result.areas:
        for issue in area.issues: translate_issue(issue)
    for issue in result.issues: translate_issue(issue)
    n = len(result.issues)
    result.score.summary = (f'本次单页诊断发现 {n} 项待检查问题。优先处理高优先级项目，并核实每项证据。评分不代表搜索排名或实际 AI 引用。' if zh else f'This single-page audit found {n} items to review. Start with high-priority issues and verify each finding. The score does not measure search rankings or actual AI citations.')
    return result

