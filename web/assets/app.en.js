'use strict';

(() => {
  const $ = (id) => document.getElementById(id);
  const form = $('scan-form');
  if (!form) return;

  const AREA = { seo: 'Technical SEO', geo: 'AI readiness', content: 'Content' };
  const SEVERITY = { critical: 'Critical', high: 'High', medium: 'Medium', low: 'Low' };
  const STATUS = { pass: 'Passed', warn: 'Review', fail: 'Failed', info: 'Info' };
  const SCOPE = 'One page’s HTML and public supporting files. No JavaScript rendering, full-site crawl, or ranking and citation tracking. Heuristic score, with no ranking guarantees.';
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

  function plain(value, fallback = 'Not provided') {
    return value === null || value === undefined || value === '' ? fallback : String(value);
  }

  function score(value) {
    const number = Number(value);
    return Number.isFinite(number) ? Math.max(0, Math.min(100, Math.round(number))) : 0;
  }

  function areaLabel(area) { return AREA[area] || plain(area, 'Other'); }
  function getIssues() { return currentReport?.issues || []; }
  function getChecks() { return (currentReport?.areas || []).flatMap((area) => (area.checks || []).map((check) => ({ ...check, area: check.area || area.area }))); }

  function dateLabel(value) {
    const date = new Date(value);
    return Number.isNaN(date.getTime()) ? 'Not provided' : date.toLocaleString('en', { dateStyle: 'medium', timeStyle: 'short' });
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
    $('submit').textContent = busy ? 'Auditing…' : 'Audit page →';
  }

  function validateUrl(raw) {
    if (!raw.trim()) throw new Error('Enter the URL of the page you want to audit.');
    let input = raw.trim();
    if (!/^[a-z][a-z\d+.-]*:/i.test(input)) input = `https://${input}`;
    let url;
    try { url = new URL(input); } catch { throw new Error('Check the address. Example: https://yoursite.com/page'); }
    if (!['http:', 'https:'].includes(url.protocol) || !url.hostname || !url.hostname.includes('.')) {
      throw new Error('Use a public HTTP or HTTPS URL. Example: https://yoursite.com');
    }
    if (url.username || url.password) throw new Error('Use a public URL without a username or password in the address.');
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
      card.append(top, bar, node('p', '', `${area?.checks?.length || 0} checks · heuristic score`));
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
    $('filter-count').textContent = `${filtered.length} of ${issues.length} priorities shown.`;
    if (!filtered.length) {
      container.append(node('div', 'empty-state', issues.length ? 'No priorities match these filters. Choose a different area or severity.' : 'These rules flagged no issues. Review the checks and consider the method’s limits.'));
      return;
    }
    filtered.forEach((issue) => {
      const card = node('article', 'issue-card');
      card.dataset.severity = Object.hasOwn(SEVERITY, issue.severity) ? issue.severity : 'low';
      const header = node('div', 'issue-heading');
      header.append(node('span', 'severity-tag', `Severity ${SEVERITY[issue.severity]?.toLowerCase() || 'not provided'}`), node('span', 'area-tag', areaLabel(issue.area)), node('h4', '', plain(issue.title, 'Finding')));
      const fix = node('p', 'issue-fix');
      fix.append(node('strong', '', 'How to review: '), document.createTextNode(plain(issue.fix, 'Inspect the check and consider the page context.')));
      card.append(header, node('p', '', plain(issue.detail, 'See the checks for more detail.')), fix);
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
      container.append(node('p', 'empty-state', 'No checks are available for this area.'));
      return;
    }
    checks.forEach((check, index) => {
      const item = node('details', 'check-item');
      item.dataset.checkId = `${plain(check.id, 'check')}-${index}`;
      const summary = node('summary');
      const status = node('span', 'check-status', STATUS[check.status] || 'Info');
      status.dataset.status = Object.hasOwn(STATUS, check.status) ? check.status : 'info';
      summary.append(status, node('span', '', plain(check.label, check.id)), node('span', 'area-tag', areaLabel(check.area)));
      const evidence = node('div', 'check-evidence');
      const list = node('dl');
      list.append(node('dt', '', 'OBSERVED EVIDENCE'), node('dd', '', plain(check.value, 'This check returned no additional value.')), node('dt', '', 'GUIDANCE'), node('dd', '', plain(check.hint, 'Review this result in context. There is no additional guidance for this check.')));
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
    $('report-domain').textContent = plain(report.domain, 'Audited page');
    $('report-summary').textContent = plain(report.score.summary, 'Inspect each check’s evidence to interpret the score.');
    $('report-url').textContent = plain(report.target_url);
    $('report-final-url').textContent = plain(report.facts?.final_url, report.target_url);
    $('report-date').textContent = demo ? 'Fictional date · demonstration' : `${dateLabel(report.scanned_at)} (local time)`;
    $('report-time').textContent = demo ? 'Fictional duration · 3.2 s' : `${(Math.max(0, Number(report.elapsed_ms) || 0) / 1000).toLocaleString('en', { maximumFractionDigits:1 })} s`;
    $('engine').textContent = plain(report.engine);
    $('rescan').textContent = demo ? 'Audit my page ↗' : 'Audit again ↗';
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
    if (status === 429) return 'The audit limit has been reached. Wait a while and try again.';
    if (status === 503) return 'The service is temporarily busy. Please try again shortly.';
    if (Array.isArray(data?.detail)) return 'The address did not pass validation. Check the URL and try again.';
    return `The audit could not be completed (HTTP ${status}). Please try again shortly.`;
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
    showStatus('loading', 'Reading the page and checking signals…', 'Timing depends on the site’s response. You can stop waiting at any time.');
    controller = new AbortController();
    const requestController = controller;
    let timedOut = false;
    const timeout = window.setTimeout(() => { timedOut = true; requestController.abort(); }, 120000);
    try {
      const response = await fetch('/api/scan', { method:'POST', headers:{ 'Content-Type':'application/json', 'Accept':'application/json' }, body:JSON.stringify({ url, ai_summary:false, language:document.documentElement.lang }), signal:requestController.signal });
      let data;
      try { data = await response.json(); } catch {
        if (requestController.signal.aborted) throw new DOMException('Aborted', 'AbortError');
        throw new Error('The server returned an unexpected response. Please try again shortly.');
      }
      if (!response.ok) throw new Error(errorMessage(data, response.status));
      if (!data || !data.score || !Array.isArray(data.areas) || !Array.isArray(data.issues)) throw new Error('The received report is incomplete. Please run a new audit.');
      showStatus('success', 'Audit complete. Your report is ready.', 'Review the evidence and download a copy for later comparison.');
      renderReport(data);
    } catch (error) {
      if (error.name === 'AbortError') {
        showStatus(timedOut ? 'error' : 'cancelled', timedOut ? 'The audit exceeded the waiting time.' : 'Stopped waiting.', timedOut ? 'The site may be slow or blocking access. Please try again later.' : 'The server may finish a request already in progress. You can audit another page.');
      } else {
        showStatus('error', 'This page could not be audited.', error instanceof TypeError ? 'Check your connection and try again. The service may also be temporarily unavailable.' : error.message);
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
    const text = ['# MandAPI GEO report', ''];
    if (isDemo) text.push('> DEMONSTRATION: entirely fictional data; no real page was audited.', '');
    text.push(`- Requested page: ${markdownText(r.target_url)}`, `- Final URL: ${markdownText(r.facts?.final_url || r.target_url)}`, `- Date: ${markdownText(r.scanned_at)}`, `- Duration: ${markdownText(r.elapsed_ms)} ms`, `- Engine: ${markdownText(r.engine)}`, '', `**Scope:** ${SCOPE}`, '', '## Scores', '', `- Overall: ${score(r.score.overall)}/100`);
    Object.entries(AREA).forEach(([key, label]) => { if (r.areas.some((area) => area.area === key)) text.push(`- ${label}: ${score(r.score[key])}/100`); });
    text.push('', markdownText(r.score.summary), '', '## Fix priorities', '');
    if (!getIssues().length) text.push('No issues were flagged by the rules. This does not guarantee that no problems exist.', '');
    getIssues().forEach((issue) => text.push(`### ${markdownText(issue.title)}`, '', `Area: ${areaLabel(issue.area)} · Severity: ${SEVERITY[issue.severity] || 'Not provided'}`, '', markdownText(issue.detail), '', `**How to review:** ${markdownText(issue.fix)}`, ''));
    text.push('## All checks', '');
    getChecks().forEach((check) => text.push(`### ${markdownText(check.label)}`, '', `Area: ${areaLabel(check.area)} · Status: ${STATUS[check.status] || 'Info'}`, '', `**Evidence:** ${markdownText(check.value)}`, '', `**Guidance:** ${markdownText(check.hint)}`, ''));
    return text.join('\n');
  }

  function download(format) {
    if (!currentReport) return;
    const report = isDemo ? { ...currentReport, demonstration:true, demonstration_notice:'Fictional data. No real audit was performed.' } : currentReport;
    const blob = new Blob([format === 'json' ? JSON.stringify(report, null, 2) : markdownReport()], { type:format === 'json' ? 'application/json;charset=utf-8' : 'text/markdown;charset=utf-8' });
    const link = node('a');
    const objectUrl = URL.createObjectURL(blob);
    link.href = objectUrl;
    const domain = plain(currentReport.domain, 'page').replace(/[^a-z\d.-]/gi, '-').slice(0, 100);
    link.download = `mandapi-geo-${isDemo ? 'example-' : ''}${domain}.${format}`;
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
      target_url:'https://example.com/', domain:'example.com', scanned_at:'2026-09-26T09:00:00Z', elapsed_ms:3200, engine:'demonstration — fictional data',
      score:{ overall:76, seo:84, geo:68, content:0, grade:'B', summary:'Illustrative example: an organized technical foundation with opportunities in description and content identification. Scores are fictional.' },
      facts:{ final_url:'https://example.com/' },
      areas:[
        { area:'seo', label:AREA.seo, score:84, checks:[{ id:'demo-https', area:'seo', label:'HTTPS connection', status:'pass', value:'Example: the page uses HTTPS.', hint:'Keep a valid certificate and redirect the HTTP version.' },{ id:'demo-description', area:'seo', label:'Page description', status:'warn', value:'Fictional example: a generic description that does not explain the service.', hint:'Write a specific description that summarizes this page’s purpose.' },{ id:'demo-canonical', area:'seo', label:'Canonical URL', status:'pass', value:'https://example.com/ (fictional URL)', hint:'Confirm that the URL is the main version of the page.' }] },
        { area:'geo', label:AREA.geo, score:68, checks:[{ id:'demo-author', area:'geo', label:'Responsible publisher', status:'warn', value:'Example: no explicit publisher identification was found.', hint:'Where relevant, show the author, their experience, or the organization responsible.' },{ id:'demo-bots', area:'geo', label:'AI crawler rules', status:'info', value:'Example: this report did not fetch a real robots.txt file.', hint:'Review search access and training access decisions separately.' },{ id:'demo-headings', area:'geo', label:'Heading structure', status:'pass', value:'Example: one main heading and descriptive sections.', hint:'Use headings that help readers find answers, without unnatural repetition.' },{ id:'demo-answer', area:'geo', label:'Answering the reader’s need', status:'warn', value:'Example: the text does not explain what the service includes.', hint:'Answer the main question first, then explain conditions, examples, and limits.' }] }
      ],
      issues:[
        { id:'demo-description', area:'seo', severity:'high', title:'Make the page description more specific', detail:'In this fictional example, the description is generic and does not explain the page’s offering.', fix:'Summarize the service and its audience in a useful sentence. Avoid artificial keyword lists.' },
        { id:'demo-author', area:'geo', severity:'medium', title:'Identify who is responsible for the content', detail:'In this fictional example, the responsible person or organization is not clearly identified.', fix:'Include verifiable identification and context relevant to the topic.' },
        { id:'demo-answer', area:'geo', severity:'low', title:'Explain the service more clearly', detail:'In this fictional example, readers must look elsewhere for basic information.', fix:'Use real information to explain what is included, who the service is for, and its conditions.' }
      ]
    }, true);
  });
})();
