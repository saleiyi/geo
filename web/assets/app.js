'use strict';

(() => {
  const $ = (id) => document.getElementById(id);
  const form = $('scan-form');
  if (!form) return;

  const AREA = { seo: 'SEO técnico', geo: 'Preparação para IA', content: 'Conteúdo' };
  const SEVERITY = { critical: 'Crítica', high: 'Alta', medium: 'Média', low: 'Baixa' };
  const STATUS = { pass: 'Passou', warn: 'Atenção', fail: 'Falhou', info: 'Informativo', unknown:'Não confirmado' };
  const SCOPE = 'HTML de uma página e arquivos públicos de apoio. Sem renderização JavaScript, rastreamento completo do site ou verificação de posições e citações. Pontuação heurística, sem garantia de ranking.';
  let currentReport = null;
  let isDemo = false;
  let controller = null;
  let printState = null;
  const BASELINE_KEY = 'mandapi-geo-baseline-v1';
  const MAX_BASELINE_BYTES = 1024 * 1024;
  let baseline = null;
  let comparison = null;
  let storedBaselinePresent = false;
  let baselineMutation = 0;
  let aiSummaryAvailable = false;
  fetch('/api/capabilities', { headers:{ 'Accept':'application/json' } })
    .then((response) => response.ok ? response.json() : null)
    .then((data) => {
      aiSummaryAvailable = data?.ai_summary === true;
      $('ai-option').hidden = !aiSummaryAvailable;
    })
    .catch(() => {});
  const DIFF_LABELS = { resolved:'Resolvidos nesta verificação', new_issues:'Novos problemas', persistent:'Ainda presentes', unverified:'Não confirmados', worsened:'Mais graves', improved:'Menos graves' };
  const COMPARE_REASONS = {
    missing_version:'Este relatório antigo não informa as versões necessárias. Reanalise a página para criar uma referência compatível.',
    schema_mismatch:'Os formatos de relatório são diferentes. Não é possível confirmar mudanças entre estas versões.',
    engine_mismatch:'Os motores de análise são diferentes. Crie uma nova referência para comparar com as mesmas regras.',
    scoring_mismatch:'As regras de pontuação mudaram. Estas notas e correções não são comparáveis.',
    target_mismatch:'As URLs solicitadas são diferentes. Compare a mesma página para confirmar mudanças.',
    redirect_mismatch:'As URLs finais após redirecionamentos são diferentes. Não é possível atribuir as mudanças à mesma página.',
    not_newer:'A análise atual precisa ser posterior à referência. Faça uma nova análise após as alterações.',
    coverage_changed:'A cobertura das verificações mudou. As evidências comparáveis são exibidas, mas não há diferença de pontuação confiável.',
    weights_changed:'Os pesos das verificações mudaram. As evidências comparáveis são exibidas, mas as notas não são comparadas.'
  };

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
    $('submit').textContent = busy ? 'Analisando…' : 'Analisar esta página grátis →';
    $('retest-baseline').disabled = busy;
    $('save-baseline').disabled = busy;
    $('import-baseline').disabled = busy;
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
    const summary = !demo && typeof report.ai_summary === 'string' ? report.ai_summary.trim() : '';
    $('ai-summary-panel').hidden = !summary;
    $('ai-summary-content').replaceChildren(...(summary ? summary.split(/\n\s*\n/).filter(Boolean).map((paragraph) => node('p', '', paragraph.trim())) : []));
    $('report-url').textContent = plain(report.target_url);
    $('report-final-url').textContent = plain(report.facts?.final_url, report.target_url);
    $('report-date').textContent = demo ? 'Data fictícia · exemplo demonstrativo' : `${dateLabel(report.scanned_at)} (horário local)`;
    $('report-time').textContent = demo ? 'Duração fictícia · 3,2 s' : `${(Math.max(0, Number(report.elapsed_ms) || 0) / 1000).toLocaleString('pt-BR', { maximumFractionDigits:1 })} s`;
    $('engine').textContent = plain(report.engine);
    $('rescan').textContent = demo ? 'Analisar minha página ↗' : 'Analisar novamente ↗';
    renderScores();
    renderIssues();
    renderChecks();
    renderTopPriorities();
    $('results').hidden = false;
    renderBaseline();
    renderComparison();
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
    renderBaseline();
    setBusy(true);
    showStatus('loading', 'Lendo a página e verificando os sinais…', 'O tempo varia conforme a resposta do site. Você pode cancelar a espera.');
    controller = new AbortController();
    const requestController = controller;
    let timedOut = false;
    const timeout = window.setTimeout(() => { timedOut = true; requestController.abort(); }, 120000);
    try {
      const requestedAiSummary = aiSummaryAvailable && $('ai-summary-opt-in').checked;
      const response = await fetch('/api/scan', { method:'POST', headers:{ 'Content-Type':'application/json', 'Accept':'application/json' }, body:JSON.stringify({ url, ai_summary:requestedAiSummary, language:document.documentElement.lang }), signal:requestController.signal });
      let data;
      try { data = await response.json(); } catch {
        if (requestController.signal.aborted) throw new DOMException('Aborted', 'AbortError');
        throw new Error('O servidor retornou uma resposta inesperada. Tente novamente em instantes.');
      }
      if (!response.ok) throw new Error(errorMessage(data, response.status));
      if (!data || !data.score || !Array.isArray(data.areas) || !Array.isArray(data.issues)) throw new Error('O relatório recebido está incompleto. Tente uma nova análise.');
      showStatus('success', 'Análise concluída. Seu relatório está pronto.', requestedAiSummary && !data.ai_summary ? 'A IA não respondeu nesta análise. O diagnóstico técnico e as evidências estão disponíveis.' : 'Revise as evidências e baixe uma cópia para comparar depois.');
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

  function baselineStatus(message, error = false) {
    $('baseline-status').textContent = message;
    $('baseline-status').classList.toggle('field-error', error);
  }

  function reportVersion(report) {
    return `${plain(report.schema_version)} / ${plain(report.scoring_version)} / ${plain(report.engine)}`;
  }

  function renderBaseline() {
    const meta = $('baseline-meta');
    meta.replaceChildren();
    meta.hidden = !baseline;
    $('clear-baseline').hidden = !baseline && !storedBaselinePresent;
    $('retest-baseline').hidden = !baseline;
    $('save-baseline').hidden = !currentReport || isDemo || $('results').hidden;
    if (!baseline) return;
    [['Página de referência',baseline.target_url],['URL final',baseline.facts?.final_url || baseline.target_url],['Data da referência',dateLabel(baseline.scanned_at)],['Versões: formato / pontuação / motor',reportVersion(baseline)]].forEach(([label,value]) => {
      const item = node('div');
      item.append(node('dt','',label),node('dd','',value));
      meta.append(item);
    });
  }

  function storeBaseline(report) {
    const candidate = window.GeoComparison.validateReport(report);
    const serialized = JSON.stringify(candidate);
    if (new Blob([serialized]).size > MAX_BASELINE_BYTES) throw new Error('baseline_too_large');
    baseline = candidate;
    try {
      window.localStorage.setItem(BASELINE_KEY,serialized);
      storedBaselinePresent = true;
      baselineStatus('Referência salva neste navegador. Corrija a página e reanalise quando estiver pronto.');
    } catch {
      baselineStatus('O navegador bloqueou o armazenamento. A referência funciona apenas nesta aba e será perdida ao recarregar ou trocar de idioma. Uma cópia anterior pode continuar salva.');
    }
    renderBaseline();
    renderComparison();
  }

  function readSavedBaseline() {
    try {
      const raw = window.localStorage.getItem(BASELINE_KEY);
      if (raw) {
        storedBaselinePresent = true;
        if (new Blob([raw]).size > MAX_BASELINE_BYTES) throw new Error('baseline_too_large');
        baseline = window.GeoComparison.validateReport(JSON.parse(raw));
        baselineStatus('Referência restaurada deste navegador. Nenhuma análise foi iniciada.');
      }
    } catch {
      baselineStatus('Não foi possível ler a referência salva. Você pode importar um JSON válido ou usar uma referência apenas nesta aba.');
    }
    renderBaseline();
  }

  function baselineError(error) {
    baselineStatus(error.message === 'baseline_too_large' ? 'O arquivo ou relatório excede o limite de 1 MiB. Escolha um relatório menor.' : 'Não foi possível usar este arquivo. Importe um relatório JSON válido do MandAPI GEO; demonstrações e arquivos incompletos não são aceitos.',true);
  }

  function diffGroups() {
    if (!comparison?.compatible) return [];
    return [['resolved',comparison.resolved],['new_issues',comparison.new_issues],['persistent',comparison.persistent],['unverified',comparison.unverified]].map(([key,items]) => [key,items || []]);
  }

  function diffExplanation(diff) {
    if (['previous_not_scored','previous_unknown','check_missing_before'].includes(diff.reason)) return 'A referência não contém evidência suficiente para classificar este problema como novo ou como uma piora.';
    if (diff.change === 'worsened') return 'O status ficou mais grave entre as duas análises.';
    if (diff.change === 'improved') return 'O status melhorou, mas ainda existe um ponto de atenção.';
    if (diff.change === 'resolved') return 'A mesma verificação passou na análise mais recente. Isso não comprova a causa da mudança.';
    if (diff.change === 'new_issue') return 'Um novo problema foi sinalizado nesta verificação.';
    if (diff.reason === 'check_missing') return 'A verificação não existe no novo relatório; a correção não foi confirmada.';
    if (diff.reason === 'not_scored' || diff.reason === 'unknown_status' || diff.change === 'unverified') return 'O novo resultado não permite confirmar se o problema foi resolvido.';
    return 'O ponto de atenção continua presente. Compare as evidências antes de agir.';
  }

  function comparisonReason() {
    if (comparison?.compatible && !comparison.score_comparable && !COMPARE_REASONS[comparison.score_reason]) return 'Não há dados equivalentes suficientes para comparar as notas. Veja apenas as mudanças confirmáveis nas verificações.';
    return COMPARE_REASONS[comparison?.reason] || COMPARE_REASONS[comparison?.score_reason] || 'As verificações foram comparadas. As notas só são comparadas quando versões, cobertura e pesos são equivalentes.';
  }

  function appendEvidence(container,label,check,issue) {
    const side = node('div','diff-evidence');
    side.append(node('h5','',label),node('p','diff-status',check ? (STATUS[check.status] || 'Não confirmado') : 'Verificação ausente'),node('p','',plain(check?.value,'Nenhuma evidência disponível.')));
    if (issue?.severity) side.append(node('p','',`Severidade: ${SEVERITY[issue.severity] || plain(issue.severity)}`));
    if (check?.hint || issue?.fix) side.append(node('p','muted',plain(check?.hint || issue?.fix)));
    container.append(side);
  }

  function renderComparison() {
    const section = $('comparison-section');
    comparison = null;
    section.hidden = !baseline || !currentReport || isDemo || $('results').hidden;
    if (section.hidden) return;
    try { comparison = window.GeoComparison.compareReports(baseline,currentReport); } catch {
      section.hidden = false;
      $('comparison-notice').textContent = 'Este relatório não pode ser comparado com segurança. Reanalise a página e salve uma nova referência.';
      $('comparison-scores').replaceChildren(); $('comparison-counts').replaceChildren(); $('comparison-details').replaceChildren();
      $('download-comparison').disabled = true;
      return;
    }
    $('download-comparison').disabled = false;
    $('comparison-notice').textContent = comparisonReason();
    const scores = $('comparison-scores'); scores.replaceChildren();
    const counts = $('comparison-counts'); counts.replaceChildren();
    const details = $('comparison-details'); details.replaceChildren();
    const metadata=node('dl','comparison-meta');
    [['Página de referência',baseline.target_url],['URL final da referência',baseline.facts?.final_url || baseline.target_url],['Data da referência',dateLabel(baseline.scanned_at)],['Versões da referência',reportVersion(baseline)],['Página atual',currentReport.target_url],['URL final atual',currentReport.facts?.final_url || currentReport.target_url],['Data atual',dateLabel(currentReport.scanned_at)],['Versões atuais',reportVersion(currentReport)]].forEach(([label,value])=>{const row=node('div');row.append(node('dt','',label),node('dd','',value));metadata.append(row);});
    details.append(metadata);
    details.append(node('p','small muted','A referência vem deste navegador ou de um JSON importado. Sua origem e integridade não são autenticadas pelo servidor.'));
    if (!comparison.compatible) return;
    if (comparison.score_comparable) {
      Object.entries(comparison.score_delta || {}).filter(([key]) => key !== 'content').forEach(([key,value]) => {
        const item=node('div','delta-card');
        item.append(node('span','',key==='overall'?'Nota geral':areaLabel(key)),node('strong','',`${value > 0 ? '+' : ''}${value}`),node('span','small muted','pontos desde a referência'));
        scores.append(item);
      });
    }
    ['resolved','new_issues','persistent','unverified','worsened'].forEach((key) => {
      const item=node('div','diff-count');
      item.append(node('strong','',comparison.counts?.[key] || 0),node('span','',DIFF_LABELS[key]));
      counts.append(item);
    });
    details.append(node('p','small muted','“Mais graves” é um subconjunto dos problemas ainda presentes. Ausência de evidência nunca é tratada como correção.'));
    diffGroups().forEach(([key,items]) => {
      const group=node('section','diff-group');
      group.append(node('h4','',`${DIFF_LABELS[key]} (${items.length})`));
      if (!items.length) group.append(node('p','small muted','Nenhuma ocorrência nesta categoria.'));
      items.forEach((diff,index) => {
        const item=node('details','diff-item'); item.dataset.diffId=`${key}-${index}`;
        const summary=node('summary');
        summary.append(node('span','',plain(diff.label,diff.id)),node('span','area-tag',areaLabel(diff.area)));
        if (diff.change==='worsened' || diff.change==='improved') summary.append(node('span','tag',DIFF_LABELS[diff.change]));
        const body=node('div','diff-body'); body.append(node('p','small muted',diffExplanation(diff)));
        const evidence=node('div','diff-evidence-grid');
        appendEvidence(evidence,'Antes · referência',diff.before,diff.before_issue);
        appendEvidence(evidence,'Depois · análise atual',diff.after,diff.after_issue);
        body.append(evidence); item.append(summary,body); group.append(item);
      });
      details.append(group);
    });
  }

  function comparisonMarkdown() {
    if (!comparison || !baseline) return [];
    const lines=['## Comparação de reparos e nova análise','',`- Página de referência: ${markdownText(baseline.target_url)}`,`- URL final da referência: ${markdownText(baseline.facts?.final_url || baseline.target_url)}`,`- Data da referência: ${markdownText(baseline.scanned_at)}`,`- Versões da referência: ${markdownText(reportVersion(baseline))}`,`- Página atual: ${markdownText(currentReport.target_url)}`,`- URL final atual: ${markdownText(currentReport.facts?.final_url || currentReport.target_url)}`,`- Data atual: ${markdownText(currentReport.scanned_at)}`,`- Versões atuais: ${markdownText(reportVersion(currentReport))}`,'',comparisonReason(),'','Mudanças observadas não comprovam causalidade, ranking, tráfego ou citações por IA.'];
    lines.push('','A referência vem deste navegador ou de um JSON importado. Sua origem e integridade não são autenticadas pelo servidor.');
    if (!comparison.compatible) { lines.push('','Nenhuma correção ou diferença de nota foi confirmada.'); return lines; }
    if (comparison.score_comparable) Object.entries(comparison.score_delta || {}).filter(([key])=>key!=='content').forEach(([key,value])=>lines.push(`- ${key==='overall'?'Nota geral':areaLabel(key)}: ${value>0?'+':''}${value}`));
    diffGroups().forEach(([key,items]) => {
      lines.push('',`### ${DIFF_LABELS[key]} (${items.length})`,'');
      if (!items.length) lines.push('Nenhuma ocorrência nesta categoria.');
      items.forEach((diff) => {
        lines.push('',`#### ${markdownText(diff.label || diff.id)}`,'',diffExplanation(diff));
        [['Antes · referência',diff.before,diff.before_issue],['Depois · análise atual',diff.after,diff.after_issue]].forEach(([label,check,issue])=>lines.push('',`**${label}**`, `- Status: ${check?(STATUS[check.status] || 'Não confirmado'):'Verificação ausente'}`,`- Evidência: ${markdownText(check?.value)}`,`- Severidade: ${markdownText(issue?.severity ? SEVERITY[issue.severity] || issue.severity : null)}`,`- Orientação: ${markdownText(check?.hint || issue?.fix)}`));
      });
    });
    return lines;
  }

  $('save-baseline').addEventListener('click', () => {
    baselineMutation += 1;
    if (currentReport && !isDemo) { try { storeBaseline(currentReport); } catch(error) { baselineError(error); } }
  });
  $('import-baseline').addEventListener('change', async (event) => {
    const file=event.target.files?.[0];
    event.target.value='';
    if (!file) return;
    const mutation = ++baselineMutation;
    try {
      if (file.size>MAX_BASELINE_BYTES) throw new Error('baseline_too_large');
      const raw = await file.text();
      if (mutation !== baselineMutation) return;
      storeBaseline(JSON.parse(raw));
    } catch(error) { if (mutation === baselineMutation) baselineError(error); }
  });
  $('clear-baseline').addEventListener('click', () => {
    baselineMutation += 1;
    baseline=null;
    try { window.localStorage.removeItem(BASELINE_KEY); storedBaselinePresent=false; baselineStatus('Referência removida deste navegador.'); }
    catch { baselineStatus('Referência removida desta aba. O navegador bloqueou o acesso ao armazenamento; apague os dados do site nas configurações para remover uma cópia anterior.'); }
    renderBaseline(); renderComparison();
  });
  $('retest-baseline').addEventListener('click', () => { if (baseline && !controller) { $('url').value=baseline.target_url; form.requestSubmit(); } });
  $('download-comparison').addEventListener('click', () => {
    if (!comparison) return;
    const url=URL.createObjectURL(new Blob([comparisonMarkdown().join('\n')],{type:'text/markdown;charset=utf-8'}));
    const link=node('a');link.href=url;link.download='mandapi-geo-comparison.md';document.body.append(link);link.click();link.remove();setTimeout(()=>URL.revokeObjectURL(url),1000);
  });

  function renderTopPriorities() {
    const list=$('top-priorities');
    if (!list) return;
    list.replaceChildren();
    const issues=getIssues().slice(0,3);
    $('top-priorities-section').hidden=!issues.length;
    issues.forEach((issue,index)=>{
      const card=node('article','priority-card');
      card.append(node('span','step-number',String(index+1).padStart(2,'0')),node('h4','',plain(issue.title)),node('span','severity-tag',SEVERITY[issue.severity] || plain(issue.severity)),node('p','',plain(issue.fix)),node('p','small muted',plain(issue.detail)));
      list.append(card);
    });
  }

  readSavedBaseline();

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
    text.push('', `Versão do relatório: ${markdownText(r.schema_version)}`, `Versão da pontuação: ${markdownText(r.scoring_version)}`);
    if (comparison && !isDemo) text.push('', ...comparisonMarkdown());
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
    printState = { area:$('area-filter').value, severity:$('severity-filter').value, opened:[...$('checks').querySelectorAll('details[open]')].map((item) => item.dataset.checkId), comparisonOpened:[...$('comparison-details').querySelectorAll('details[open]')].map((item) => item.dataset.diffId) };
    $('area-filter').value = 'all';
    $('severity-filter').value = 'all';
    renderIssues();
    renderChecks();
    $('checks').querySelectorAll('details').forEach((item) => { item.open = true; });
    $('comparison-details').querySelectorAll('details').forEach((item) => { item.open = true; });
  });
  window.addEventListener('afterprint', () => {
    if (!printState) return;
    $('area-filter').value = printState.area;
    $('severity-filter').value = printState.severity;
    renderIssues();
    renderChecks();
    $('checks').querySelectorAll('details').forEach((item) => { item.open = printState.opened.includes(item.dataset.checkId); });
    $('comparison-details').querySelectorAll('details').forEach((item) => { item.open = printState.comparisonOpened.includes(item.dataset.diffId); });
    printState = null;
  });

  $('demo-button').addEventListener('click', () => {
    if (controller) return;
    $('scan-feedback').hidden = true;
    renderReport({
      target_url:'https://exemplo.com.br/', domain:'exemplo.com.br', scanned_at:'2026-09-26T09:00:00Z', elapsed_ms:3200, engine:'demonstração — dados fictícios',
      score:{ overall:76, seo:84, geo:68, content:0, grade:'B', summary:'Exemplo ilustrativo de verificações do HTML: tamanho da descrição, autoria declarada e estrutura semântica. As notas e os valores são fictícios.' },
      facts:{ final_url:'https://exemplo.com.br/' },
      areas:[
        { area:'seo', label:AREA.seo, score:84, checks:[{ id:'demo-https', area:'seo', label:'Conexão HTTPS', status:'pass', value:'Exemplo: a página usa HTTPS.', hint:'Mantenha um certificado válido e redirecione a versão HTTP.' },{ id:'demo-description', area:'seo', label:'Comprimento da meta description', status:'warn', value:'30 caracteres; página em português (exemplo fictício).', hint:'O comprimento é uma referência editorial, não uma avaliação do significado ou da qualidade da descrição.' },{ id:'demo-canonical', area:'seo', label:'Endereço canonical', status:'pass', value:'https://exemplo.com.br/ (URL fictícia)', hint:'Confirme se o endereço corresponde à versão principal da página.' }] },
        { area:'geo', label:AREA.geo, score:68, checks:[{ id:'demo-author', area:'geo', label:'Autoria declarada no HTML', status:'warn', value:'Nenhuma declaração de autor encontrada (exemplo fictício).', hint:'Confira se uma identificação de autoria apropriada está presente no HTML. Esta verificação não valida credenciais.' },{ id:'demo-bots', area:'geo', label:'Regras para crawlers de IA', status:'info', value:'Exemplo: este relatório não consultou nenhum robots.txt real.', hint:'Revise separadamente as decisões de acesso para busca e para treinamento.' },{ id:'demo-extractable', area:'geo', label:'Proporção de texto no HTML', status:'pass', value:'8,2% do HTML é texto (exemplo fictício).', hint:'A proporção é uma heurística estrutural; não mede compreensão do tema ou probabilidade de citação.' },{ id:'demo-semantic', area:'geo', label:'HTML semântico', status:'warn', value:'Nenhuma tag <main> ou <article> encontrada (exemplo fictício).', hint:'Use elementos semânticos apropriados para identificar o conteúdo principal, sem alterar sua informação apenas para obter pontos.' }] }
      ],
      issues:[
        { id:'demo-author', area:'geo', severity:'medium', title:'Revisar a declaração de autoria', detail:'Neste exemplo fictício, não foi encontrada uma declaração de autor no HTML.', fix:'Quando fizer sentido para a página, apresente autoria verdadeira em conteúdo visível e marcação correspondente.' },
        { id:'demo-semantic', area:'geo', severity:'medium', title:'Identificar o conteúdo principal com HTML semântico', detail:'Neste exemplo fictício, o HTML não contém <main> nem <article>.', fix:'Revise a estrutura e use <main> para o conteúdo principal ou <article> para conteúdo independente, quando apropriado.' },
        { id:'demo-description', area:'seo', severity:'low', title:'Revisar o comprimento da meta description', detail:'Neste exemplo fictício em português, a descrição tem 30 caracteres. A ferramenta não avaliou seu significado.', fix:'Revise a descrição no contexto da página e do idioma. Comprimento isolado não determina a qualidade ou o trecho exibido na busca.' }
      ]
    }, true);
  });
})();
