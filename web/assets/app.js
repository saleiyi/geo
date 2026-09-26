'use strict';

(() => {
  const $ = (id) => document.getElementById(id);
  const form = $('scan-form');
  if (!form) return;

  const AREA = { seo: 'SEO técnico', geo: 'Preparação para IA', content: 'Conteúdo' };
  const SEVERITY = { critical: 'Crítica', high: 'Alta', medium: 'Média', low: 'Baixa' };
  const STATUS = { pass: 'Passou', warn: 'Atenção', fail: 'Falhou', info: 'Informativo' };
  const SCOPE = 'HTML de uma página e arquivos públicos de apoio. Sem renderização JavaScript, rastreamento completo do site ou verificação de posições e citações. Pontuação heurística, sem garantia de ranking.';
  let currentReport = null;
  let isDemo = false;
  let controller = null;
  let printState = null;

  function node(tag, className, text) {
    const element = document.createElement(tag);
    if (className) element.className = className;
    if (text !== undefined && text !== null) element.textContent = String(text);
    return element;
  }

  function plain(value, fallback = 'Não informado') {
    return value === null || value === undefined || value === '' ? fallback : String(value);
  }

  function score(value) {
    const number = Number(value);
    return Number.isFinite(number) ? Math.max(0, Math.min(100, Math.round(number))) : 0;
  }

  function areaLabel(area) { return AREA[area] || plain(area, 'Outros'); }
  function getIssues() { return currentReport?.issues || []; }
  function getChecks() { return (currentReport?.areas || []).flatMap((area) => (area.checks || []).map((check) => ({ ...check, area: check.area || area.area }))); }

  function dateLabel(value) {
    const date = new Date(value);
    return Number.isNaN(date.getTime()) ? 'Não informado' : date.toLocaleString('pt-BR', { dateStyle: 'medium', timeStyle: 'short' });
  }

  function showStatus(state, message, detail = '') {
    const feedback = $('scan-feedback');
    feedback.hidden = false;
    feedback.dataset.state = state;
    $('status').textContent = message;
    $('status-detail').textContent = detail;
    $('spinner').hidden = state !== 'loading';
    $('cancel-button').hidden = state !== 'loading';
  }

  function setBusy(busy) {
    $('submit').disabled = busy;
    $('demo-button').disabled = busy;
    $('url').readOnly = busy;
    $('results').setAttribute('aria-busy', String(busy));
    $('submit').textContent = busy ? 'Analisando…' : 'Analisar página →';
  }

  function validateUrl(raw) {
    if (!raw.trim()) throw new Error('Informe a URL da página que deseja analisar.');
    let input = raw.trim();
    if (!/^[a-z][a-z\d+.-]*:/i.test(input)) input = `https://${input}`;
    let url;
    try { url = new URL(input); } catch { throw new Error('Confira o endereço. Exemplo: https://seusite.com.br/pagina'); }
    if (!['http:', 'https:'].includes(url.protocol) || !url.hostname || !url.hostname.includes('.')) {
      throw new Error('Use uma URL pública com HTTP ou HTTPS. Exemplo: https://seusite.com.br');
    }
    if (url.username || url.password) throw new Error('Use uma URL pública, sem usuário ou senha no endereço.');
    url.hash = '';
    return url.href;
  }

  function renderScores() {
    const container = $('area-scores');
    container.replaceChildren();
    Object.entries(AREA).forEach(([key, label]) => {
      const area = currentReport.areas.find((item) => item.area === key);
      if (!area) return;
      const value = score(currentReport.score[key] ?? area.score);
      const card = node('article', 'area-card');
      const top = node('div');
      const valueElement = node('strong', '', value);
      valueElement.append(node('span', '', ' / 100'));
      top.append(node('h3', '', label), valueElement);
      const bar = node('span', 'mini-bar');
      bar.setAttribute('aria-hidden', 'true');
      const fill = node('i');
      fill.style.width = `${value}%`;
      bar.append(fill);
      card.append(top, bar, node('p', '', `${area?.checks?.length || 0} verificações · nota heurística`));
      container.append(card);
    });
  }

  function renderIssues() {
    const issues = getIssues();
    const area = $('area-filter').value;
    const severity = $('severity-filter').value;
    const filtered = issues.filter((issue) => (area === 'all' || issue.area === area) && (severity === 'all' || issue.severity === severity));
    const container = $('issues');
    container.replaceChildren();
    $('issue-total').textContent = issues.length;
    $('filter-count').textContent = `${filtered.length} de ${issues.length} prioridades exibidas.`;
    if (!filtered.length) {
      container.append(node('div', 'empty-state', issues.length ? 'Nenhuma prioridade corresponde a estes filtros. Selecione outra área ou severidade.' : 'Nenhum problema foi sinalizado pelas regras desta análise. Confira as verificações e considere os limites do método.'));
      return;
    }
    filtered.forEach((issue) => {
      const card = node('article', 'issue-card');
      card.dataset.severity = Object.hasOwn(SEVERITY, issue.severity) ? issue.severity : 'low';
      const header = node('div', 'issue-heading');
      header.append(node('span', 'severity-tag', `Severidade ${SEVERITY[issue.severity]?.toLowerCase() || 'não informada'}`), node('span', 'area-tag', areaLabel(issue.area)), node('h4', '', plain(issue.title, 'Ponto de atenção')));
      const fix = node('p', 'issue-fix');
      fix.append(node('strong', '', 'Como revisar: '), document.createTextNode(plain(issue.fix, 'Consulte a verificação e avalie o contexto da página.')));
      card.append(header, node('p', '', plain(issue.detail, 'Veja as verificações para mais detalhes.')), fix);
      container.append(card);
    });
  }

  function renderChecks() {
    const area = $('area-filter').value;
    const checks = getChecks().filter((check) => area === 'all' || check.area === area);
    const container = $('checks');
    container.replaceChildren();
    $('check-total').textContent = checks.length;
    if (!checks.length) {
      container.append(node('p', 'empty-state', 'Nenhuma verificação disponível para esta área.'));
      return;
    }
    checks.forEach((check, index) => {
      const item = node('details', 'check-item');
      item.dataset.checkId = `${plain(check.id, 'check')}-${index}`;
      const summary = node('summary');
      const status = node('span', 'check-status', STATUS[check.status] || 'Informativo');
      status.dataset.status = Object.hasOwn(STATUS, check.status) ? check.status : 'info';
      summary.append(status, node('span', '', plain(check.label, check.id)), node('span', 'area-tag', areaLabel(check.area)));
      const evidence = node('div', 'check-evidence');
      const list = node('dl');
      list.append(node('dt', '', 'EVIDÊNCIA ENCONTRADA'), node('dd', '', plain(check.value, 'A verificação não retornou um valor adicional.')), node('dt', '', 'ORIENTAÇÃO'), node('dd', '', plain(check.hint, 'Revise este resultado no contexto da página. Não há orientação adicional para esta verificação.')));
      evidence.append(list);
      item.append(summary, evidence);
      container.append(item);
    });
  }

  function renderReport(report, demo = false) {
    currentReport = report;
    isDemo = demo;
    $('area-filter').value = 'all';
    $('severity-filter').value = 'all';
    $('demo-banner').hidden = !demo;
    $('overall-score').textContent = score(report.score.overall);
    $('report-ring').style.setProperty('--score', score(report.score.overall));
    $('report-domain').textContent = plain(report.domain, 'Página analisada');
    $('report-summary').textContent = plain(report.score.summary, 'Consulte as evidências de cada verificação para interpretar a pontuação.');
    $('report-url').textContent = plain(report.target_url);
    $('report-final-url').textContent = plain(report.facts?.final_url, report.target_url);
    $('report-date').textContent = demo ? 'Data fictícia · exemplo demonstrativo' : `${dateLabel(report.scanned_at)} (horário local)`;
    $('report-time').textContent = demo ? 'Duração fictícia · 3,2 s' : `${(Math.max(0, Number(report.elapsed_ms) || 0) / 1000).toLocaleString('pt-BR', { maximumFractionDigits:1 })} s`;
    $('engine').textContent = plain(report.engine);
    $('rescan').textContent = demo ? 'Analisar minha página ↗' : 'Analisar novamente ↗';
    renderScores();
    renderIssues();
    renderChecks();
    $('results').hidden = false;
    document.body.classList.add('has-report');
    $('report-title').focus({ preventScroll:true });
    $('results').scrollIntoView({ behavior: window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth', block:'start' });
  }

  function errorMessage(data, status) {
    if (typeof data?.detail === 'string') return data.detail;
    if (status === 429) return 'O limite de análises foi atingido. Aguarde um pouco e tente novamente.';
    if (status === 503) return 'O serviço está temporariamente ocupado. Tente novamente em instantes.';
    if (Array.isArray(data?.detail)) return 'O endereço não passou pela validação. Confira a URL e tente novamente.';
    return `Não foi possível concluir a análise (HTTP ${status}). Tente novamente em instantes.`;
  }

  form.addEventListener('submit', async (event) => {
    event.preventDefault();
    if (controller) return;
    $('url-error').hidden = true;
    $('url').removeAttribute('aria-invalid');
    let url;
    try { url = validateUrl($('url').value); } catch (error) {
      $('url-error').textContent = error.message;
      $('url-error').hidden = false;
      $('url').setAttribute('aria-invalid', 'true');
      $('url').focus();
      return;
    }
    $('url').value = url;
    $('results').hidden = true;
    setBusy(true);
    showStatus('loading', 'Lendo a página e verificando os sinais…', 'O tempo varia conforme a resposta do site. Você pode cancelar a espera.');
    controller = new AbortController();
    const requestController = controller;
    let timedOut = false;
    const timeout = window.setTimeout(() => { timedOut = true; requestController.abort(); }, 120000);
    try {
      const response = await fetch('/api/scan', { method:'POST', headers:{ 'Content-Type':'application/json', 'Accept':'application/json' }, body:JSON.stringify({ url, ai_summary:false, language:document.documentElement.lang }), signal:requestController.signal });
      let data;
      try { data = await response.json(); } catch {
        if (requestController.signal.aborted) throw new DOMException('Aborted', 'AbortError');
        throw new Error('O servidor retornou uma resposta inesperada. Tente novamente em instantes.');
      }
      if (!response.ok) throw new Error(errorMessage(data, response.status));
      if (!data || !data.score || !Array.isArray(data.areas) || !Array.isArray(data.issues)) throw new Error('O relatório recebido está incompleto. Tente uma nova análise.');
      showStatus('success', 'Análise concluída. Seu relatório está pronto.', 'Revise as evidências e baixe uma cópia para comparar depois.');
      renderReport(data);
    } catch (error) {
      if (error.name === 'AbortError') {
        showStatus(timedOut ? 'error' : 'cancelled', timedOut ? 'A análise excedeu o tempo de espera.' : 'Espera cancelada.', timedOut ? 'O site pode estar lento ou bloquear a leitura. Tente novamente mais tarde.' : 'O servidor pode terminar uma requisição já iniciada. Você pode analisar outra página.');
      } else {
        showStatus('error', 'Não foi possível analisar esta página.', error instanceof TypeError ? 'Verifique sua conexão e tente novamente. O serviço também pode estar temporariamente indisponível.' : error.message);
      }
      $('submit').focus({ preventScroll:true });
    } finally {
      window.clearTimeout(timeout);
      controller = null;
      setBusy(false);
    }
  });

  $('cancel-button').addEventListener('click', () => controller?.abort());
  $('url').addEventListener('input', () => { $('url-error').hidden = true; $('url').removeAttribute('aria-invalid'); });
  $('area-filter').addEventListener('change', () => { renderIssues(); renderChecks(); });
  $('severity-filter').addEventListener('change', renderIssues);
  $('rescan').addEventListener('click', () => {
    if (!currentReport || controller) return;
    if (isDemo) {
      $('url').focus();
      $('scan-form').scrollIntoView({ behavior:'smooth', block:'center' });
      return;
    }
    $('url').value = currentReport.target_url;
    form.requestSubmit();
  });

  function markdownText(value) {
    return plain(value, '—').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/([\\`*_{}\[\]()#+.!|])/g, '\\$1').replace(/\r?\n/g, '  \n');
  }

  function markdownReport() {
    const r = currentReport;
    const text = ['# Relatório MandAPI GEO', ''];
    if (isDemo) text.push('> DEMONSTRAÇÃO: dados inteiramente fictícios, sem análise de uma página real.', '');
    text.push(`- Página solicitada: ${markdownText(r.target_url)}`, `- URL final: ${markdownText(r.facts?.final_url || r.target_url)}`, `- Data: ${markdownText(r.scanned_at)}`, `- Duração: ${markdownText(r.elapsed_ms)} ms`, `- Motor: ${markdownText(r.engine)}`, '', `**Escopo:** ${SCOPE}`, '', '## Pontuações', '', `- Geral: ${score(r.score.overall)}/100`);
    Object.entries(AREA).forEach(([key, label]) => { if (r.areas.some((area) => area.area === key)) text.push(`- ${label}: ${score(r.score[key])}/100`); });
    text.push('', markdownText(r.score.summary), '', '## Prioridades de correção', '');
    if (!getIssues().length) text.push('Nenhum problema sinalizado pelas regras. Isso não garante ausência de problemas.', '');
    getIssues().forEach((issue) => text.push(`### ${markdownText(issue.title)}`, '', `Área: ${areaLabel(issue.area)} · Severidade: ${SEVERITY[issue.severity] || 'Não informada'}`, '', markdownText(issue.detail), '', `**Como revisar:** ${markdownText(issue.fix)}`, ''));
    text.push('## Todas as verificações', '');
    getChecks().forEach((check) => text.push(`### ${markdownText(check.label)}`, '', `Área: ${areaLabel(check.area)} · Status: ${STATUS[check.status] || 'Informativo'}`, '', `**Evidência:** ${markdownText(check.value)}`, '', `**Orientação:** ${markdownText(check.hint)}`, ''));
    return text.join('\n');
  }

  function download(format) {
    if (!currentReport) return;
    const report = isDemo ? { ...currentReport, demonstration:true, demonstration_notice:'Dados fictícios. Nenhuma análise real foi executada.' } : currentReport;
    const blob = new Blob([format === 'json' ? JSON.stringify(report, null, 2) : markdownReport()], { type:format === 'json' ? 'application/json;charset=utf-8' : 'text/markdown;charset=utf-8' });
    const link = node('a');
    const objectUrl = URL.createObjectURL(blob);
    link.href = objectUrl;
    const domain = plain(currentReport.domain, 'pagina').replace(/[^a-z\d.-]/gi, '-').slice(0, 100);
    link.download = `mandapi-geo-${isDemo ? 'exemplo-' : ''}${domain}.${format}`;
    document.body.append(link);
    link.click();
    link.remove();
    window.setTimeout(() => URL.revokeObjectURL(objectUrl), 1000);
  }

  $('download-json').addEventListener('click', () => download('json'));
  $('download-md').addEventListener('click', () => download('md'));
  $('print-report').addEventListener('click', () => window.print());
  window.addEventListener('beforeprint', () => {
    if (!currentReport || $('results').hidden || printState) return;
    printState = { area:$('area-filter').value, severity:$('severity-filter').value, opened:[...$('checks').querySelectorAll('details[open]')].map((item) => item.dataset.checkId) };
    $('area-filter').value = 'all';
    $('severity-filter').value = 'all';
    renderIssues();
    renderChecks();
    $('checks').querySelectorAll('details').forEach((item) => { item.open = true; });
  });
  window.addEventListener('afterprint', () => {
    if (!printState) return;
    $('area-filter').value = printState.area;
    $('severity-filter').value = printState.severity;
    renderIssues();
    renderChecks();
    $('checks').querySelectorAll('details').forEach((item) => { item.open = printState.opened.includes(item.dataset.checkId); });
    printState = null;
  });

  $('demo-button').addEventListener('click', () => {
    if (controller) return;
    $('scan-feedback').hidden = true;
    renderReport({
      target_url:'https://exemplo.com.br/', domain:'exemplo.com.br', scanned_at:'2026-09-26T09:00:00Z', elapsed_ms:3200, engine:'demonstração — dados fictícios',
      score:{ overall:76, seo:84, geo:68, content:0, grade:'B', summary:'Exemplo ilustrativo: uma base técnica organizada, com oportunidades na descrição e na identificação do conteúdo. As notas são fictícias.' },
      facts:{ final_url:'https://exemplo.com.br/' },
      areas:[
        { area:'seo', label:AREA.seo, score:84, checks:[{ id:'demo-https', area:'seo', label:'Conexão HTTPS', status:'pass', value:'Exemplo: a página usa HTTPS.', hint:'Mantenha um certificado válido e redirecione a versão HTTP.' },{ id:'demo-description', area:'seo', label:'Descrição da página', status:'warn', value:'Exemplo fictício: descrição genérica, sem explicar o serviço.', hint:'Escreva uma descrição específica que resuma a proposta desta página.' },{ id:'demo-canonical', area:'seo', label:'Endereço canonical', status:'pass', value:'https://exemplo.com.br/ (URL fictícia)', hint:'Confirme se o endereço corresponde à versão principal da página.' }] },
        { area:'geo', label:AREA.geo, score:68, checks:[{ id:'demo-author', area:'geo', label:'Identificação do responsável', status:'warn', value:'Exemplo: não foi encontrada identificação explícita do responsável.', hint:'Quando fizer sentido, apresente autoria, experiência ou a organização responsável pelo conteúdo.' },{ id:'demo-bots', area:'geo', label:'Regras para crawlers de IA', status:'info', value:'Exemplo: este relatório não consultou nenhum robots.txt real.', hint:'Revise separadamente as decisões de acesso para busca e para treinamento.' },{ id:'demo-headings', area:'geo', label:'Organização dos títulos', status:'pass', value:'Exemplo: um título principal e seções descritivas.', hint:'Use títulos que ajudem a encontrar respostas, sem repetir termos artificialmente.' },{ id:'demo-answer', area:'geo', label:'Resposta à necessidade do leitor', status:'warn', value:'Exemplo: o texto não explica o que está incluído no serviço.', hint:'Responda à dúvida central primeiro e detalhe condições, exemplos e limites.' }] }
      ],
      issues:[
        { id:'demo-description', area:'seo', severity:'high', title:'Tornar a descrição da página mais específica', detail:'Neste exemplo fictício, a descrição é genérica e não informa o que a página oferece.', fix:'Resuma o serviço e o público atendido em uma frase útil. Evite listas artificiais de palavras-chave.' },
        { id:'demo-author', area:'geo', severity:'medium', title:'Identificar quem responde pelo conteúdo', detail:'Neste exemplo fictício, não há indicação clara da pessoa ou organização responsável.', fix:'Inclua identificação verificável e informações de contexto relevantes para o assunto.' },
        { id:'demo-answer', area:'geo', severity:'low', title:'Explicar o serviço com mais clareza', detail:'Neste exemplo fictício, o leitor precisa procurar informações básicas em outras páginas.', fix:'Explique o que está incluído, para quem é o serviço e quais são as condições, usando informações reais.' }
      ]
    }, true);
  });
})();
