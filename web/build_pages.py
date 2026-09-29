"""Generate static, crawlable editorial pages; no runtime translation service."""
from pathlib import Path
import json

ROOT = Path(__file__).resolve().parent

PAGES = {
    "metodologia": {
        "pt": ("Metodologia e limites da auditoria", "Entenda o que verificamos, como as notas são calculadas e por que evidências valem mais que uma pontuação isolada.", """
<h2>O que esta análise cobre?</h2><p>O MandAPI GEO lê o HTML público de <strong>uma URL</strong> e consulta arquivos de apoio do site, como robots.txt, sitemap e, quando disponível, llms.txt. O relatório agrupa verificações de SEO técnico e preparação para buscas com IA.</p><p>Não executamos JavaScript, não navegamos por todas as páginas e não acessamos áreas autenticadas. Informações exibidas apenas depois da execução de scripts podem não aparecer no relatório.</p>
<h2>Como calculamos as notas?</h2><p>Cada verificação elegível tem um peso. Uma verificação aprovada recebe 100% desse peso; um alerta, 50%; uma falha, 0%. Verificações informativas não entram na pontuação.</p><p>Perguntas frequentes, números, comprimento do primeiro parágrafo, listas, tabelas e presença de marcação de organização são observações informativas, sem penalização por ausência. As preferências de treinamento e o arquivo llms.txt também não alteram a nota. Não adicione esses elementos apenas para elevar a pontuação.</p><p><strong>Nota de cada área = pontos obtidos ÷ pesos elegíveis × 100</strong>, arredondada. A nota geral é a média das áreas SEO e preparação para IA, com o mesmo peso. Não é uma probabilidade de indexação ou citação.</p><div class="notice">Uma nota alta significa que a página atende a mais critérios desta ferramenta. Ela não mede posição no Google, presença real no ChatGPT, tráfego, conversões ou qualidade editorial completa.</div>
<h2>Como ler as prioridades?</h2><p>As ocorrências são ordenadas primeiro por severidade e depois por impacto estimado nas regras. Comece pelas barreiras técnicas, confira o valor encontrado e avalie se a recomendação faz sentido para a página. A severidade é uma orientação de revisão, não uma estimativa de perda financeira.</p><p>Abra cada verificação para consultar a evidência e a orientação. Dados ausentes no HTML não provam que algo esteja ausente em todas as versões da página.</p>
<h2>O que significa preparação para IA?</h2><p>Avaliamos sinais observáveis, como estrutura do conteúdo, identificação e regras de acesso para crawlers. Esses sinais não reproduzem os sistemas internos dos buscadores. Não existe aqui um teste direto de respostas geradas por assistentes.</p><p>Arquivos como <code>llms.txt</code> e dados estruturados especiais não são um requisito universal de GEO. A presença de um arquivo não comprova que ele seja usado por um mecanismo de busca. <a href="/guia-geo">Leia as orientações e fontes no guia.</a></p>
<h2>Limites que afetam o resultado</h2><ul><li>O resultado retrata uma resposta HTTP em um momento específico. Sites podem mudar por região, dispositivo, cookies ou proteção contra robôs.</li><li>Um sitemap disponível não confirma que todas as URLs estão indexadas.</li><li>robots.txt expressa regras de acesso; não comprova rastreamento, treinamento ou citações reais.</li><li>Não são medidos Core Web Vitals, backlinks, autoridade, volume de busca ou acessibilidade completa.</li><li>Os critérios são heurísticos e podem produzir falsos positivos ou deixar problemas passar.</li></ul>
<h2>Como acompanhar melhorias?</h2><p>Baixe o relatório completo, registre as alterações e analise novamente a mesma URL. Combine o diagnóstico com revisão humana e dados reais de ferramentas de busca. Compare resultados somente quando URL, conteúdo e condições forem semelhantes.</p>"""),
        "en": ("Audit methodology and limitations", "Understand what we check, how scores work, and why evidence matters more than an isolated number.", """
<h2>What does the audit cover?</h2><p>MandAPI GEO reads the public HTML of <strong>one URL</strong> and checks supporting site files such as robots.txt, a sitemap, and llms.txt when available. The report groups technical SEO and AI search readiness checks.</p><p>We do not execute JavaScript, crawl every page, or access authenticated areas. Content displayed only after scripts run may not appear in the report.</p>
<h2>How are scores calculated?</h2><p>Each eligible check has a weight. A passing check earns 100% of its weight; a warning earns 50%; a failure earns 0%. Informational checks do not affect the score.</p><p>FAQ patterns, numbers, first-paragraph length, lists, tables, and organization markup are informational observations, with no penalty for absence. Training preferences and llms.txt do not change the score either. Do not add these elements simply to raise a score.</p><p><strong>Area score = earned points ÷ eligible weights × 100</strong>, rounded. The overall score is an equally weighted average of SEO and AI readiness. It is not the probability of indexing or citation.</p><div class="notice">A high score means that the page meets more of this tool’s criteria. It does not measure Google rankings, actual ChatGPT mentions, traffic, conversions, or complete editorial quality.</div>
<h2>How should I read priorities?</h2><p>Findings are ordered by severity and then by estimated rule impact. Start with technical barriers, inspect the observed value, and decide whether each recommendation applies to your page. Severity guides review; it does not estimate financial loss.</p><p>Expand each check to inspect evidence and guidance. A detail missing from the fetched HTML may exist in other versions of the page.</p>
<h2>What does AI readiness mean?</h2><p>We evaluate observable signals such as content structure, identification, and crawler access rules. These checks do not reproduce search engines’ internal systems. The audit does not directly test answers generated by assistants.</p><p>Files such as <code>llms.txt</code> and special structured data are not universal GEO requirements. A file’s presence does not prove that a search engine uses it. <a href="/guia-geo">Read the guide and its sources.</a></p>
<h2>What can affect the results?</h2><ul><li>A report captures an HTTP response at one moment. Sites may vary by region, device, cookies, or bot protection.</li><li>An available sitemap does not confirm that its URLs are indexed.</li><li>robots.txt describes access rules; it does not prove actual crawling, training, or citations.</li><li>We do not measure Core Web Vitals, backlinks, authority, search volumes, or full accessibility.</li><li>Heuristic checks may produce false positives or miss issues.</li></ul>
<h2>How can I track improvements?</h2><p>Download the full report, record your changes, and audit the same URL again. Combine findings with human review and real search data. Compare results only when the URL, content, and conditions are comparable.</p>"""),
        "zh": ("审计方法与适用边界", "了解我们检查什么、分数如何计算，以及为什么具体证据比单一分数更重要。", """
<h2>这次分析覆盖什么？</h2><p>MandAPI GEO 读取<strong>一个 URL</strong> 的公开 HTML，并检查 robots.txt、网站地图及可用的 llms.txt 等辅助文件。报告按技术 SEO 和 AI 搜索就绪度组织检查项。</p><p>我们不执行 JavaScript，不抓取网站所有页面，也不访问需要登录的内容。仅在脚本运行后出现的信息，可能不会被报告识别。</p>
<h2>分数如何计算？</h2><p>每个参与计分的检查项都有权重。通过获得全部权重，需关注获得 50%，未通过获得 0%。仅供参考的检查项不参与计分。</p><p>FAQ、数字、首段长度、列表、表格和组织信息标记仅作为参考观察，缺失不扣分。训练访问偏好和 llms.txt 也不影响分数。不要为了提高分数而刻意添加这些元素。</p><p><strong>单项领域得分 = 已获得分值 ÷ 有效权重总和 × 100</strong>，结果取整。总分是 SEO 与 AI 就绪度得分的等权平均值，不代表被收录或引用的概率。</p><div class="notice">高分说明页面满足了本工具更多检查规则，不代表 Google 排名、ChatGPT 实际提及、流量、转化或完整的内容质量。</div>
<h2>如何理解问题优先级？</h2><p>问题先按严重程度排序，再按规则估计的影响排序。先处理技术障碍，查看实际检测值，再判断建议是否适用。严重程度用于辅助复查，不是经济损失估算。</p><p>展开检查项即可查看证据与建议。在抓取到的 HTML 中没有找到某项信息，不等于页面的所有版本都不存在该信息。</p>
<h2>AI 搜索就绪度意味着什么？</h2><p>我们评估内容结构、身份信息、爬虫访问规则等可观察信号。这些检查不能还原搜索引擎内部机制，也不直接测试 AI 助手生成的回答。</p><p><code>llms.txt</code> 或特殊结构化数据并不是通用的 GEO 必备条件。文件存在也不能证明某个搜索引擎正在使用它。<a href="/guia-geo">查看指南与官方来源。</a></p>
<h2>哪些限制会影响结果？</h2><ul><li>报告记录某一时刻的 HTTP 响应。地域、设备、Cookie 与反爬设置可能改变页面内容。</li><li>网站地图可访问，不代表其中的 URL 都已被收录。</li><li>robots.txt 表达访问规则，不证明实际抓取、训练或引用行为。</li><li>我们不测量 Core Web Vitals、外链、权威度、搜索量或完整无障碍表现。</li><li>启发式检查可能误报，也可能遗漏问题。</li></ul>
<h2>如何跟踪改进？</h2><p>下载完整报告，记录修改，再分析同一个 URL。把自动检查与人工复核、真实搜索数据结合起来。只有 URL、内容与条件相近时，前后分数才有可比性。</p>"""),
    },
    "privacidade": {
        "pt": ("Privacidade, com clareza", "O que acontece com a URL enviada e com os dados usados para produzir seu relatório.", """
<h2>O que recebemos?</h2><p>Ao iniciar uma análise, o navegador envia a URL informada ao servidor. O servidor acessa essa página pública e arquivos de apoio para extrair sinais técnicos e de conteúdo. O site de destino recebe essas requisições e pode registrá-las.</p><p>Envie apenas URLs públicas. Não inclua senhas, tokens de acesso, dados pessoais ou informações confidenciais no endereço ou nos parâmetros da URL.</p>
<h2>Os relatórios são armazenados?</h2><p>A aplicação não usa um banco de dados para manter histórico de análises. As informações são processadas durante a requisição e o relatório permanece na memória da página aberta. Recarregar ou fechar a página remove o relatório da interface.</p><p>Arquivos JSON, Markdown ou PDF que você exporta ficam no dispositivo conforme as configurações do navegador. Esses arquivos podem conter URLs e trechos públicos da página analisada; compartilhe-os com cuidado.</p>
<h2>Cookies, métricas e serviços de IA</h2><p>Esta interface não inclui ferramentas de analytics de terceiros, pixels publicitários ou cookies próprios de acompanhamento. A análise iniciada por este formulário solicita apenas o motor de regras, sem resumo por modelo de IA.</p><p>A API pode ter uma função opcional de resumo por IA, usada somente quando solicitada e configurada pelo operador. Nesse caso, informações do relatório podem ser enviadas ao provedor configurado. Essa opção não é ativada pelo formulário deste site.</p>
<h2>Logs e infraestrutura</h2><p>O servidor, o provedor de hospedagem, proxies e serviços de proteção podem manter registros operacionais, como IP, horário, rota, erros e informações de requisição. A retenção desses registros depende da configuração da implantação. A ausência de um banco de relatórios não significa ausência de todos os logs.</p><p>Para aplicar os limites de uso, a aplicação mantém em memória um identificador derivado do IP com hash e um valor aleatório temporário. O contador é reiniciado à meia-noite UTC e não é persistido em banco de dados. Tentativas que iniciam uma análise também contam quando a leitura falha. Os limites efetivos dependem da configuração do serviço.</p>
<h2>Informações desta operação</h2><p>Consulte o quadro de <a href="#operator-information">informações do operador</a> para identificar o responsável, o contato de privacidade, a hospedagem e as práticas de registro e retenção aplicáveis a este serviço.</p><p>Consulte esta página novamente se novas integrações, contas ou armazenamento forem adicionados. As práticas descritas devem acompanhar a configuração efetiva do serviço.</p>"""),
        "en": ("Privacy, clearly explained", "What happens to the URL you submit and the data used to produce your report.", """
<h2>What do we receive?</h2><p>When you start an audit, your browser sends the submitted URL to the server. The server accesses that public page and supporting files to extract technical and content signals. The destination site receives these requests and may log them.</p><p>Submit public URLs only. Do not include passwords, access tokens, personal data, or confidential information in the address or its query parameters.</p>
<h2>Are reports stored?</h2><p>The application does not use a database to maintain an audit history. Information is processed during the request, and the report stays in the memory of the open page. Reloading or closing the page removes it from the interface.</p><p>JSON, Markdown, or PDF files you export are saved to your device according to browser settings. They may contain URLs and public excerpts from the audited page; consider their contents before sharing.</p>
<h2>Cookies, analytics, and AI services</h2><p>This interface includes no third-party analytics, advertising pixels, or first-party tracking cookies. Audits started through this form use the rules engine without an AI-generated summary.</p><p>The API may offer an optional AI summary, used only when requested and configured by the operator. In that case, report information may be sent to the configured provider. This website’s form does not enable that option.</p>
<h2>Logs and infrastructure</h2><p>The server, hosting provider, proxies, and protection services may keep operational records such as IP addresses, timestamps, routes, errors, and request information. Retention depends on deployment configuration. No report database does not mean no logs exist.</p><p>To apply usage limits, the application keeps an IP-derived identifier in memory using a hash and a temporary random salt. The counter resets at midnight UTC and is not persisted in a database. Attempts that begin an audit also count when reading fails. Effective limits depend on the service configuration.</p>
<h2>About this deployment</h2><p>See the <a href="#operator-information">operator information</a> for the responsible operator, privacy contact, hosting provider, and logging and retention practices applicable to this service.</p><p>Review this page again if integrations, accounts, or storage are introduced. The description must stay aligned with the service’s actual configuration.</p>"""),
        "zh": ("清楚说明隐私处理方式", "你提交的 URL 如何处理，以及生成报告时会使用哪些数据。", """
<h2>我们会接收哪些信息？</h2><p>开始分析后，浏览器将你填写的 URL 发送给服务器。服务器访问该公开页面和辅助文件，提取技术与内容信号。目标网站会收到这些请求，也可能记录这些访问。</p><p>请只提交公开 URL，不要在地址或查询参数中包含密码、访问令牌、个人数据或保密信息。</p>
<h2>报告会被保存吗？</h2><p>应用不使用数据库保存分析历史。信息在请求期间处理，报告保留在当前打开页面的内存中。刷新或关闭页面后，界面中的报告会消失。</p><p>导出的 JSON、Markdown 或 PDF 根据浏览器设置保存在你的设备中。这些文件可能包含 URL 和被分析页面的公开内容片段，分享前请检查其中的信息。</p>
<h2>Cookie、统计与 AI 服务</h2><p>当前界面未集成第三方流量统计、广告像素或自有追踪 Cookie。通过这个表单发起的分析只使用规则引擎，不请求 AI 生成摘要。</p><p>API 可以提供可选的 AI 摘要功能，只有运营者完成配置且请求明确启用时才使用。此时，报告信息可能被发送给配置的模型服务提供方。本网站表单不会启用该选项。</p>
<h2>日志与基础设施</h2><p>服务器、托管服务、代理和防护服务可能记录 IP、时间、路由、错误和请求信息等运行日志。日志保留期限取决于部署配置。不建立报告数据库，并不代表完全没有日志。</p><p>为了限制使用次数，应用使用 IP 和临时随机盐值计算哈希标识，仅在内存中保存计数器。计数器在 UTC 零点重置，不持久写入数据库。开始分析后即使读取失败，也会计入次数。实际限额取决于服务配置。</p>
<h2>本次运营的信息</h2><p>请查看上方的<a href="#operator-information">运营信息</a>，了解本服务的运营主体、隐私联系邮箱、托管服务商，以及适用的日志记录与保留规则。</p><p>如果将来增加第三方集成、账户或存储，请重新查看本页。隐私说明应始终与服务的真实配置一致。</p>"""),
    },
    "guia-geo": {
        "pt": ("GEO na prática: comece pelos fundamentos", "Um roteiro para melhorar SEO e preparar conteúdo para buscas com IA, sem atalhos ou promessas de citação.", """
<h2>O que é GEO?</h2><p>GEO é a sigla de Generative Engine Optimization: práticas voltadas a tornar conteúdo mais encontrável e compreensível em experiências de busca com IA. Uma forma útil de começar é revisar acesso técnico, clareza das respostas e confiança nas informações.</p><p>Esta é uma orientação prática da equipe MandAPI GEO. Não há fórmula que garanta presença em respostas de assistentes.</p>
<h2>1. Garanta que a página possa ser lida</h2><p>Confira se a URL pública retorna conteúdo útil em HTML, tem um título específico e não contém bloqueios de indexação acidentais. Verifique também se os links internos levam à versão correta da página e se o sitemap aponta para URLs canônicas.</p><p><strong>Exercício:</strong> abra o código-fonte e procure a resposta principal da página. Se ela só aparece depois de executar JavaScript, esta ferramenta pode não detectá-la. Avalie a renderização com ferramentas apropriadas.</p>
<h2>2. Responda primeiro; detalhe depois</h2><p>Escolha uma necessidade real do leitor. Responda de forma direta, depois acrescente exemplos, condições e limites. Use títulos descritivos e listas ou tabelas quando tornarem a comparação mais simples.</p><p><strong>Exercício:</strong> peça a alguém que não conhece seu negócio para explicar o serviço após ler o primeiro parágrafo. Reescreva onde houver ambiguidade.</p>
<h2>3. Dê contexto verificável</h2><p>Identifique o responsável pelo conteúdo quando pertinente. Explique experiências e métodos reais, cite fontes primárias e atualize informações que mudam. Datas, números e credenciais devem ter fundamento; não os adicione apenas para satisfazer uma regra automática.</p>
<h2>4. Evite os atalhos de GEO</h2><p>O Google orienta manter os fundamentos de SEO para seus recursos de IA; não exige um schema especial para esse fim. Sua documentação informa que <code>llms.txt</code> não ajuda nem prejudica a visibilidade no Google. Isso não substitui páginas acessíveis e conteúdo útil. <a href="https://developers.google.com/search/docs/fundamentals/ai-optimization-guide" rel="noopener">Fonte: Google Search Central.</a></p><p>Use dados estruturados apropriados ao conteúdo visível. Não invente avaliações, perguntas, preços ou autoria para preencher uma marcação.</p>
<h2>5. Separe busca de treinamento</h2><p>A OpenAI documenta finalidades distintas: <code>OAI-SearchBot</code> está relacionado à busca, enquanto <code>GPTBot</code> está relacionado ao treinamento. Revise as regras de cada agente conforme sua decisão editorial; liberar treinamento não é requisito para aparecer na busca. Permitir acesso também não garante citação. <a href="https://developers.openai.com/api/docs/bots" rel="noopener">Fonte: documentação de bots da OpenAI.</a></p>
<h2>6. Meça o que de fato aconteceu</h2><p>Use este relatório para identificar ações. Para avaliar resultados, combine dados de indexação, consultas, tráfego e conversões das suas ferramentas reais. Uma variação de nota não comprova aumento de visibilidade, nem permite atribuir um resultado a uma única mudança.</p><div class="notice"><strong>Checklist de revisão:</strong> página acessível, título claro, resposta útil, responsável identificável quando pertinente, fontes verificáveis e decisões conscientes sobre crawlers. Primeiro qualidade; depois comparação de resultados.</div>"""),
        "en": ("A practical GEO guide: start with the basics", "A path to better SEO and content readiness for AI search, without shortcuts or promises of citations.", """
<h2>What is GEO?</h2><p>GEO stands for Generative Engine Optimization: practices intended to make content easier to find and understand in AI search experiences. A useful starting point is technical access, clear answers, and trustworthy information.</p><p>This is practical guidance from MandAPI GEO. There is no formula that guarantees inclusion in assistant responses.</p>
<h2>1. Make sure the page can be read</h2><p>Check that the public URL returns useful HTML, has a specific title, and contains no accidental indexing blocks. Check that internal links point to the correct page version and that sitemap entries use canonical URLs.</p><p><strong>Exercise:</strong> open the page source and look for its main answer. If it only appears after JavaScript runs, this tool may miss it. Review rendering with suitable tools.</p>
<h2>2. Answer first; add detail afterward</h2><p>Choose a real reader need. Answer directly, then add examples, conditions, and limitations. Use descriptive headings and lists or tables where they simplify comparison.</p><p><strong>Exercise:</strong> ask someone unfamiliar with your business to explain your service after reading the first paragraph. Rewrite anything ambiguous.</p>
<h2>3. Provide verifiable context</h2><p>Identify the person or organization responsible where relevant. Describe real experience and methods, cite primary sources, and update information that changes. Dates, numbers, and credentials need a basis; do not add them just to satisfy an automated rule.</p>
<h2>4. Avoid GEO shortcuts</h2><p>Google recommends SEO fundamentals for its AI features and does not require special schema for them. Its documentation says <code>llms.txt</code> neither helps nor harms Google visibility. It cannot replace accessible pages and useful content. <a href="https://developers.google.com/search/docs/fundamentals/ai-optimization-guide" rel="noopener">Source: Google Search Central.</a></p><p>Use structured data appropriate to visible content. Do not invent reviews, questions, prices, or authorship to fill a markup template.</p>
<h2>5. Separate search from training</h2><p>OpenAI documents different purposes: <code>OAI-SearchBot</code> relates to search, while <code>GPTBot</code> relates to training. Review each agent’s rules according to your publishing policy; allowing training is not a requirement for search inclusion. Access also does not guarantee citation. <a href="https://developers.openai.com/api/docs/bots" rel="noopener">Source: OpenAI bot documentation.</a></p>
<h2>6. Measure what actually happened</h2><p>Use this report to identify actions. Evaluate outcomes with indexing, query, traffic, and conversion data from your actual tools. A score change does not prove increased visibility or establish that a single change caused an outcome.</p><div class="notice"><strong>Review checklist:</strong> accessible page, clear title, useful answer, identifiable responsibility when relevant, verifiable sources, and deliberate crawler policies. Improve quality, then compare real outcomes.</div>"""),
        "zh": ("GEO 实践指南：从基础做起", "改善 SEO 与 AI 搜索内容准备度的行动路线，不依赖捷径，也不承诺引用结果。", """
<h2>什么是 GEO？</h2><p>GEO 是 Generative Engine Optimization 的缩写，通常指让内容更容易在 AI 搜索体验中被发现和理解的一类实践。可以先从技术可访问性、回答清晰度和信息可信度入手。</p><p>本文由 MandAPI GEO 提供实用建议。没有任何公式能够保证内容出现在 AI 助手的回答中。</p>
<h2>1. 确认页面可以被读取</h2><p>检查公开 URL 是否返回有用的 HTML、是否有具体标题，以及是否存在意外的禁止收录设置。确认站内链接指向正确页面版本，网站地图使用规范 URL。</p><p><strong>练习：</strong>打开网页源代码，查找页面的核心答案。如果答案必须等 JavaScript 运行才出现，本工具可能无法检测，请使用适合的工具检查渲染情况。</p>
<h2>2. 先回答问题，再补充细节</h2><p>选择读者的真实需求，直接回答，再提供实例、条件和限制。使用描述性的标题，只有在能帮助阅读和对比时才使用列表或表格。</p><p><strong>练习：</strong>请一个不了解你业务的人阅读首段，然后复述你的服务。哪里表达含糊，就优先改写哪里。</p>
<h2>3. 提供可核实的背景</h2><p>在适当场景标注内容负责人，介绍真实经验和方法，引用一手来源，并更新会变化的信息。日期、数字和资质必须有依据，不要为了通过自动检查而添加它们。</p>
<h2>4. 避免所谓 GEO 捷径</h2><p>Google 建议其 AI 功能继续遵循 SEO 基础，并不要求特殊 schema。其文档说明 <code>llms.txt</code> 对 Google 可见度没有帮助或损害，不能代替可访问的网页与有用内容。<a href="https://developers.google.com/search/docs/fundamentals/ai-optimization-guide" rel="noopener">来源：Google 搜索中心。</a></p><p>使用与页面可见内容相符的结构化数据，不要为了填写标记而虚构评价、问题、价格或作者。</p>
<h2>5. 区分搜索抓取与模型训练</h2><p>OpenAI 文档区分了不同用途：<code>OAI-SearchBot</code> 与搜索相关，<code>GPTBot</code> 与训练相关。按自己的内容政策分别检查规则；允许训练不是出现在搜索中的必要条件。允许访问也不保证被引用。<a href="https://developers.openai.com/api/docs/bots" rel="noopener">来源：OpenAI 爬虫文档。</a></p>
<h2>6. 衡量真实发生的变化</h2><p>用本报告寻找改进项，再用真实工具中的收录、查询、流量与转化数据评估效果。分数变化不能证明可见度提升，也不能证明某项改动导致了业务结果。</p><div class="notice"><strong>复查清单：</strong>页面可访问，标题清晰，回答有用，必要时标注负责人，来源可核实，并明确选择爬虫访问政策。先改善质量，再比较真实结果。</div>"""),
    },
}

UI = {
    "pt": {"lang":"pt-BR", "prefix":"", "home":"Início", "method":"Metodologia", "privacy":"Privacidade", "guide":"Guia de GEO", "analyze":"Analisar uma página", "skip":"Ir para o conteúdo", "library":"BIBLIOTECA MANDAPI GEO", "nav":"Navegação principal", "side":"Nesta biblioteca", "back":"← Voltar para a análise", "review":"Atualizado em 26 de setembro de 2026 · Equipe MandAPI GEO", "next":"Um próximo passo concreto", "cta":"Analise uma página e confira as evidências por trás de cada recomendação.", "tagline":"Fundamentos sólidos para um novo jeito de buscar.", "disclaimer":"Auditoria de uma página. Sem garantia de ranking.", "locale":"Português (Brasil)", "language":"Escolher idioma"},
    "en": {"lang":"en", "prefix":"/en", "home":"Home", "method":"Methodology", "privacy":"Privacy", "guide":"GEO guide", "analyze":"Audit a page", "skip":"Skip to content", "library":"MANDAPI GEO LIBRARY", "nav":"Main navigation", "side":"In this library", "back":"← Back to the audit", "review":"Updated September 26, 2026 · MandAPI GEO team", "next":"A practical next step", "cta":"Audit a page and inspect the evidence behind each recommendation.", "tagline":"Solid foundations for a new way to search.", "disclaimer":"Single-page audit. No ranking guarantees.", "locale":"English", "language":"Choose language"},
    "zh": {"lang":"zh-CN", "prefix":"/zh", "home":"首页", "method":"分析方法", "privacy":"隐私说明", "guide":"GEO 指南", "analyze":"分析一个页面", "skip":"跳至正文", "library":"MANDAPI GEO 知识库", "nav":"主导航", "side":"知识库导航", "back":"← 返回页面分析", "review":"更新于 2026 年 9 月 26 日 · MandAPI GEO 团队", "next":"从一个具体行动开始", "cta":"分析一个页面，查看每条建议背后的实际证据。", "tagline":"扎实的基础，面向新的搜索方式。", "disclaimer":"单页审计，不保证排名。", "locale":"简体中文", "language":"选择语言"},
}

COMPARISON_METHOD = {
    'pt':'<h2>O que uma comparação confirma?</h2><p>Uma referência é uma cópia compacta de um relatório anterior. A comparação exige a mesma URL solicitada e final, versões compatíveis de formato, motor e pontuação e uma nova análise com data posterior. Diferenças de nota só são mostradas quando cobertura e pesos também correspondem.</p><p>Um problema só é marcado como resolvido quando a mesma verificação passa depois. Um resultado ausente, desconhecido ou apenas informativo não confirma reparo. Problemas mais graves também continuam na categoria de problemas presentes, portanto os totais dessas categorias não devem ser somados. Alterações observadas não provam causalidade ou melhoria em rankings e citações.</p><p>Relatórios antigos sem versões podem ser importados como referência, mas não produzem uma comparação confirmada. O arquivo importado é validado localmente; isso não autentica a origem dos seus dados. Mantenha cópias dos relatórios reais para revisão.</p>',
    'en':'<h2>What does a comparison confirm?</h2><p>A baseline is a compact copy of an earlier report. Comparison requires the same requested and final URLs, compatible report, engine, and scoring versions, and a newer audit date. Score differences appear only when coverage and weights also match.</p><p>An issue is marked resolved only when the same check later passes. A missing, unknown, or informational result does not confirm a fix. Worsened issues are also included among persistent issues, so those category totals should not be added together. Observed changes do not prove causality or better rankings and citations.</p><p>Older reports without version information can be imported as baselines but do not produce confirmed comparisons. Imported files are validated locally; this does not authenticate their data source. Keep copies of real reports for review.</p>',
    'zh':'<h2>比较能够确认什么？</h2><p>基线是先前报告的紧凑副本。比较要求请求 URL 和最终 URL 相同，报告格式、引擎及评分版本兼容，而且当前分析时间晚于基线。只有检查覆盖范围和权重也一致时，才显示分数变化。</p><p>只有同一检查项在后续分析中通过，才标为已解决。缺失、未知或仅供参考的结果都不能确认修复。更严重的问题也属于仍然存在的问题，因此这两个类别的数量不能相加。观察到变化不证明因果关系，也不证明排名或引用改善。</p><p>没有版本信息的旧报告可以导入为基线，但不能产生已确认的比较。导入文件在本地验证，这不代表其数据来源经过认证。请保留真实报告副本以便复查。</p>'
}
BASELINE_PRIVACY = {
    'pt':'<h2>Referência salva neste navegador</h2><p>Apenas quando você clica em salvar ou importa um arquivo, uma cópia compacta de até 1 MiB é gravada no localStorage deste navegador. Há uma única referência; a próxima substitui a anterior. Ela contém URLs, data, versões, notas, verificações, evidências e problemas e permanece após recarregar a página ou trocar de idioma.</p><p>Use “Limpar referência” para removê-la. Se o navegador bloquear o armazenamento, a referência funciona apenas na aba atual e pode ser perdida ao sair. Não há sincronização entre dispositivos ou histórico no servidor. Arquivos JSON importados são lidos e validados no navegador, sem upload. Restaurar ou importar não inicia análise; reanalisar a URL exige uma ação sua.</p>',
    'en':'<h2>A baseline saved in this browser</h2><p>Only when you click save or import a file is a compact copy of up to 1 MiB written to this browser’s localStorage. There is one baseline; the next replaces it. It contains URLs, dates, versions, scores, checks, evidence, and issues, and persists across reloads and language changes.</p><p>Use “Clear baseline” to remove it. If browser storage is blocked, the baseline works only in the current tab and can be lost when you leave. There is no device synchronization or server-side history. Imported JSON is read and validated in the browser without upload. Restoring or importing never starts an audit; rechecking requires your action.</p>',
    'zh':'<h2>保存在当前浏览器的基线</h2><p>只有主动点击保存或导入文件时，才会把最多 1 MiB 的紧凑报告写入当前浏览器的 localStorage。仅保存一份基线，下一份会替换上一份。其中包含 URL、日期、版本、分数、检查项、证据和问题，刷新页面或切换语言后仍保留。</p><p>使用“清除基线”即可删除。如果浏览器禁止存储，基线仅在当前标签页有效，离开后可能丢失。不跨设备同步，服务器不保存历史。导入的 JSON 在浏览器本地读取并验证，不会上传。恢复或导入基线不会启动分析，复测需要你的主动操作。</p>'
}
OPERATOR_PRIVACY = {
    'pt': ('Informações do operador', 'Operador', 'Contato de privacidade', 'Provedor de hospedagem', 'Logs e retenção'),
    'en': ('Operator information', 'Operator', 'Privacy contact', 'Hosting provider', 'Logs and retention'),
    'zh': ('运营信息', '运营主体', '隐私联系邮箱', '托管服务商', '日志与保留规则'),
}

def operator_privacy_block(language):
    heading, *labels = OPERATOR_PRIVACY[language]
    fields = ['__OPERATOR_NAME__', '__CONTACT_EMAIL__', '__HOSTING_PROVIDER__', '__PRIVACY_LOG_NOTICE__']
    rows = ''.join(f'<div><dt>{label}</dt><dd>{field}</dd></div>' for label, field in zip(labels, fields))
    return f'<section class="privacy-operator" id="operator-information" aria-labelledby="operator-title"><h2 id="operator-title">{heading}</h2><dl>{rows}</dl></section>'

HOME_META = {
    'pt':('Auditoria SEO e GEO grátis por página | MandAPI GEO','Analise uma URL: SEO técnico, preparação para buscas com IA e estrutura do conteúdo. Veja prioridades, evidências e compare após corrigir. Sem cadastro.'),
    'en':('Free SEO & GEO Page Checker, AI Readiness Audit | MandAPI GEO','Check one page for technical SEO and AI search readiness. Get evidence, prioritized fixes, and compare a new audit against your saved baseline. No login.'),
    'zh':('免费 SEO 与 GEO 页面检测工具 · AI 搜索准备度分析 | MandAPI GEO','输入一个公开页面 URL，检查技术 SEO、AI 搜索准备度和内容结构。查看优先修正项、检查证据，保存基线并对比复测结果，无需登录。')
}

def language_links(language, slug=""):
    paths = {"pt": "/" + slug, "en": "/en" + ("/" + slug if slug else ""), "zh": "/zh" + ("/" + slug if slug else "")}
    return '<nav class="language-switch" aria-label="'+UI[language]["language"]+'">' + ''.join(f'<a href="{paths[key]}" lang="{UI[key]["lang"]}" hreflang="{UI[key]["lang"]}"'+(' aria-current="page"' if key == language else '')+f'>{label}</a>' for key,label in [("pt","PT"),("en","EN"),("zh","中文")]) + '</nav>'

def alternates(slug=""):
    return '\n'.join(f'<link rel="alternate" hreflang="{lang}" href="__SITE_URL__{path}">' for lang,path in [("pt-BR","/"+slug),("en","/en"+("/"+slug if slug else "")),("zh-CN","/zh"+("/"+slug if slug else "")),("x-default","/"+slug)])

def create_editorial_pages(slugs=None):
    for slug, versions in PAGES.items():
        if slugs is not None and slug not in slugs:
            continue
        for language, (title, description, body) in versions.items():
            if slug=='metodologia': body+=COMPARISON_METHOD[language]
            if slug=='privacidade':
                body=operator_privacy_block(language)+body
                body+=BASELINE_PRIVACY[language]
                body=body.replace('Recarregar ou fechar a página remove o relatório da interface.','Recarregar ou fechar a página remove o relatório atual da interface, exceto a referência que você escolheu salvar no navegador.')
                body=body.replace('Reloading or closing the page removes it from the interface.','Reloading or closing the page removes the current report from the interface, except for a baseline you explicitly chose to save in your browser.')
                body=body.replace('刷新或关闭页面后，界面中的报告会消失。','刷新或关闭页面后，当前报告会从界面消失；你主动保存在浏览器中的基线除外。')
            u=UI[language]
            prefix=u['prefix']
            home=prefix or '/'
            route=f'{prefix}/{slug}'
            og_image='og-image'+('' if language=='pt' else '.'+language)+'.png'
            if prefix:
                for link in PAGES:
                    body=body.replace(f'href="/{link}"', f'href="{prefix}/{link}"')
            links=''.join(f'<a href="{prefix}/{key}"'+(' aria-current="page"' if slug==key else '')+f'>{u[label]}</a>' for key,label in [('guia-geo','guide'),('metodologia','method'),('privacidade','privacy')])
            schema=json.dumps({"@context":"https://schema.org","@type":"WebPage","name":title,"description":description,"url":"__SITE_URL__"+route,"inLanguage":u['lang']},ensure_ascii=False)
            html=f'''<!doctype html>
<html lang="{u['lang']}"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>{title} — MandAPI GEO</title><meta name="description" content="{description}"><meta name="robots" content="__INDEX_ROBOTS__">__GOOGLE_VERIFICATION__<link rel="canonical" href="__SITE_URL__{route}">{alternates(slug)}<meta property="og:type" content="article"><meta property="og:site_name" content="MandAPI GEO"><meta property="og:title" content="{title}"><meta property="og:description" content="{description}"><meta property="og:url" content="__SITE_URL__{route}"><meta property="og:image" content="__SITE_URL__/assets/{og_image}"><meta property="og:image:width" content="1200"><meta property="og:image:height" content="630"><meta name="twitter:card" content="summary_large_image"><meta name="twitter:title" content="{title}"><meta name="twitter:description" content="{description}"><meta name="twitter:image" content="__SITE_URL__/assets/{og_image}"><link rel="icon" href="/assets/favicon.svg" type="image/svg+xml"><link rel="stylesheet" href="/assets/styles.css"><link rel="stylesheet" href="/assets/design.css"><script type="application/ld+json">{schema}</script></head>
<body><a class="skip-link" href="#main">{u['skip']}</a><header class="site-header"><div class="container header-inner"><a class="brand" href="{home}" aria-label="MandAPI GEO, {u['home']}"><span class="brand-mark" aria-hidden="true">m<span>↗</span></span><span>MandAPI <span class="brand-geo">GEO</span></span></a><nav class="main-nav" aria-label="{u['nav']}"><a href="{prefix}/guia-geo">{u['guide']}</a><a href="{prefix}/metodologia">{u['method']}</a></nav>{language_links(language,slug)}<a class="button button-small button-outline header-cta" href="{home}#url">{u['analyze']} ↗</a></div></header>
<main id="main" class="container article-shell"><aside class="article-sidebar"><p>{u['side']}</p><nav aria-label="{u['side']}">{links}<a class="back-link" href="{home}">{u['back']}</a></nav></aside><article><header class="article-header"><p class="eyebrow">{u['library']}</p><h1>{title}</h1><p class="article-lead">{description}</p><p class="article-meta">{u['review']}</p></header><div class="article-body">{body}<div class="article-cta"><h2>{u['next']}</h2><p>{u['cta']}</p><a class="button button-dark" href="{home}#url">{u['analyze']} →</a></div></div></article></main>
<footer class="site-footer"><div class="container"><div class="footer-top"><div><a class="brand" href="{home}">MandAPI <span class="brand-geo">GEO</span></a><p>{u['tagline']}</p></div><nav aria-label="{u['side']}">{links}</nav></div><div class="footer-bottom"><span>MandAPI GEO · {u['locale']}</span><span>{u['disclaimer']}</span></div></div></footer></body></html>'''
            target=ROOT/(language if language!='pt' else '')/(slug+'.html')
            target.parent.mkdir(parents=True,exist_ok=True)
            target.write_text(html,encoding='utf-8')

def create_home_pages():
    import re
    from bs4 import BeautifulSoup
    from translations import HOME, ATTRIBUTES, JS
    source=(ROOT/'index.html').read_text(encoding='utf-8')
    for language, index in [('pt',0),('en',1),('zh',2)]:
        soup=BeautifulSoup(source,'html.parser')
        for existing in soup.find_all(class_='language-switch') + soup.find_all('link',rel='alternate') + soup.find_all('meta',property=['og:image:width','og:image:height']):
            existing.decompose()
        ui=UI[language]
        soup.html['lang']=ui['lang']
        for option in soup.find(id='area-filter').find_all('option',value='content'): option.decompose()
        translation={row[0]:row[index] for row in HOME+ATTRIBUTES}
        missing=[]
        for text in list(soup.find_all(string=True)):
            if text.parent.name in ['script','style','title']: continue
            content=str(text).strip()
            if content in translation:
                text.replace_with(str(text).replace(content,translation[content]))
            elif content and any(c in content for c in 'ãõçáéíóúêô'):
                missing.append(content)
        for element in soup.find_all(True):
            for attribute in ['content','aria-label','placeholder','title']:
                if element.has_attr(attribute) and element[attribute] in translation:
                    element[attribute]=translation[element[attribute]]
            if language!='pt' and element.has_attr('href'):
                href=element['href']
                if href=='/': element['href']=ui['prefix']
                elif href in ['/metodologia','/privacidade','/guia-geo']: element['href']=ui['prefix']+href
        canonical=ui['prefix'] or '/'
        page_title,page_description=HOME_META[language]
        soup.title.string=page_title
        soup.find('meta',attrs={'name':'description'})['content']=page_description
        soup.find('meta',property='og:title')['content']=page_title
        soup.find('meta',property='og:description')['content']=page_description
        soup.find('link',rel='canonical')['href']='__SITE_URL__'+canonical
        soup.find('meta',property='og:url')['content']='__SITE_URL__'+canonical
        soup.find('meta',property='og:image')['content']='__SITE_URL__/assets/og-image'+('' if language=='pt' else '.'+language)+'.png'
        for prop,value in [('og:image:width','1200'),('og:image:height','630')]:
            tag=soup.new_tag('meta'); tag['property']=prop; tag['content']=value; soup.head.append(tag)
        for name,value in [('twitter:title',page_title),('twitter:description',page_description),('twitter:image',soup.find('meta',property='og:image')['content'])]:
            tag=soup.find('meta',attrs={'name':name}) or soup.new_tag('meta'); tag['name']=name; tag['content']=value; soup.head.append(tag)
        soup.find('meta',property='og:locale')['content']={'pt':'pt_BR','en':'en_US','zh':'zh_CN'}[language]
        for item in BeautifulSoup(alternates(),'html.parser').contents:
            soup.head.append(item)
        language_nav=BeautifulSoup(language_links(language),'html.parser').nav
        soup.find(class_='header-cta').insert_before(language_nav)
        script=soup.find('script',src='/assets/app.js')
        if language!='pt': script['src']=f'/assets/app.{language}.js'
        schema=soup.find('script',type='application/ld+json')
        data=json.loads(schema.string)
        if '@graph' in data: data=data['@graph'][1]
        data['url']='__SITE_URL__'+canonical
        data['inLanguage']=ui['lang']
        data['description']=soup.find('meta',attrs={'name':'description'})['content']
        data['featureList']={'pt':['Auditoria de uma página HTML','Verificações com evidências','Relatórios em JSON e Markdown'],'en':['Single-page HTML audit','Checks with evidence','JSON and Markdown reports'],'zh':['单页 HTML 分析','检查证据可查','JSON 与 Markdown 报告']}[language]
        schema.string=json.dumps({'@context':'https://schema.org','@graph':[{'@type':'WebSite','name':'MandAPI GEO','url':'__SITE_URL__'+canonical,'inLanguage':ui['lang']},data]},ensure_ascii=False)
        target=ROOT/(language if language!='pt' else '')/'index.html'
        target.parent.mkdir(parents=True,exist_ok=True)
        target.write_text(str(soup),encoding='utf-8')
        if language!='pt' and missing: print(language,'untranslated:',missing)
    javascript=(ROOT/'assets/app.js').read_text(encoding='utf-8')
    for language,index in [('en',1),('zh',2)]:
        mapping={row[0]:row[index] for row in HOME+JS}
        pattern=re.compile('|'.join(re.escape(key) for key in sorted(mapping,key=len,reverse=True)))
        translated=pattern.sub(lambda m:mapping[m.group(0)],javascript)
        translated=translated.replace("'pt-BR'",repr(UI[language]['lang']))
        translated=translated.replace('https://exemplo.com.br/','https://example.com/').replace("'exemplo.com.br'","'example.com'")
        translated=translated.replace("'Não informada'", "'Not provided'" if language=='en' else "'未提供'")
        translated=translated.replace("'não informada'", "'not provided'" if language=='en' else "'未提供'")
        translated=translated.replace("'pagina'", "'page'").replace("'exemplo-'", "'example-'")
        translated=translated.replace('${filtered.length} de ${issues.length}', '${filtered.length} of ${issues.length}' if language=='en' else '${filtered.length} / ${issues.length}')
        (ROOT/f'assets/app.{language}.js').write_text(translated,encoding='utf-8')

if __name__=='__main__':
    create_editorial_pages()
    create_home_pages()
