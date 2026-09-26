'use strict';

(() => {
  const $ = (id) => document.getElementById(id);
  const form = $('scan-form');
  if (!form) return;

  const AREA = { seo: 'Technical SEO', geo: 'AI readiness', content: 'Content' };
  const SEVERITY = { critical: 'Critical', high: 'High', medium: 'Medium', low: 'Low' };
  const STATUS = { pass: 'Passed', warn: 'Review', fail: 'Failed', info: 'Info', unknown:'Unverified' };
  const SCOPE = 'One page’s HTML and public supporting files. No JavaScript rendering, full-site crawl, or ranking and citation tracking. Heuristic score, with no ranking guarantees.';
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
  const DIFF_LABELS = { resolved:'Resolved in this check', new_issues:'New issues', persistent:'Still present', unverified:'Unverified', worsened:'Worsened', improved:'Improved' };
  const COMPARE_REASONS = {
    missing_version:'This older report lacks required version information. Recheck the page to create a compatible baseline.',
    schema_mismatch:'The report formats differ. Changes cannot be confirmed between these versions.',
    engine_mismatch:'The analysis engines differ. Create a new baseline to compare the same rules.',
    scoring_mismatch:'Scoring rules have changed. These scores and fixes cannot be compared.',
    target_mismatch:'The requested URLs differ. Compare the same page to confirm changes.',
    redirect_mismatch:'The final URLs after redirects differ. Changes cannot be attributed to the same page.',
    not_newer:'The current audit must be newer than the baseline. Run another audit after making changes.',
    coverage_changed:'Check coverage has changed. Comparable evidence is shown, but no reliable score difference is available.',
    weights_changed:'Check weights changed. Comparable evidence is shown, but scores are not compared.'
  };

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
    $('submit').textContent = busy ? 'Auditing…' : 'Check this page free →';
    $('retest-baseline').disabled = busy;
    $('save-baseline').disabled = busy;
    $('import-baseline').disabled = busy;
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
    renderBaseline();
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
    [['Baseline page',baseline.target_url],['Final URL',baseline.facts?.final_url || baseline.target_url],['Baseline date',dateLabel(baseline.scanned_at)],['Versions: format / scoring / engine',reportVersion(baseline)]].forEach(([label,value]) => {
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
      baselineStatus('Baseline saved in this browser. Update the page and recheck when ready.');
    } catch {
      baselineStatus('Browser storage is blocked. The baseline works in this tab only and will be lost on reload or language change. An older saved copy may remain.');
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
        baselineStatus('Baseline restored from this browser. No audit has been started.');
      }
    } catch {
      baselineStatus('The saved baseline could not be read. Import a valid JSON or use a baseline in this tab only.');
    }
    renderBaseline();
  }

  function baselineError(error) {
    baselineStatus(error.message === 'baseline_too_large' ? 'The file or report exceeds 1 MiB. Choose a smaller report.' : 'This file could not be used. Import a valid MandAPI GEO JSON report; demonstrations and incomplete files are not accepted.',true);
  }

  function diffGroups() {
    if (!comparison?.compatible) return [];
    return [['resolved',comparison.resolved],['new_issues',comparison.new_issues],['persistent',comparison.persistent],['unverified',comparison.unverified]].map(([key,items]) => [key,items || []]);
  }

  function diffExplanation(diff) {
    if (['previous_not_scored','previous_unknown','check_missing_before'].includes(diff.reason)) return 'The baseline lacks enough evidence to classify this issue as new or as a regression.';
    if (diff.change === 'worsened') return 'The status worsened between the two audits.';
    if (diff.change === 'improved') return 'The status improved, but an issue remains.';
    if (diff.change === 'resolved') return 'The same check passed in the latest audit. This does not establish what caused the change.';
    if (diff.change === 'new_issue') return 'A new issue was flagged in this check.';
    if (diff.reason === 'check_missing') return 'The check is missing from the new report; the fix is unconfirmed.';
    if (diff.reason === 'not_scored' || diff.reason === 'unknown_status' || diff.change === 'unverified') return 'The new result cannot confirm whether the issue was resolved.';
    return 'The issue is still present. Compare the evidence before taking action.';
  }

  function comparisonReason() {
    if (comparison?.compatible && !comparison.score_comparable && !COMPARE_REASONS[comparison.score_reason]) return 'There is not enough equivalent data to compare scores. Review only the check changes that can be confirmed.';
    return COMPARE_REASONS[comparison?.reason] || COMPARE_REASONS[comparison?.score_reason] || 'Checks have been compared. Scores are compared only when versions, coverage, and weights match.';
  }

  function appendEvidence(container,label,check,issue) {
    const side = node('div','diff-evidence');
    side.append(node('h5','',label),node('p','diff-status',check ? (STATUS[check.status] || 'Unverified') : 'Check missing'),node('p','',plain(check?.value,'No evidence available.')));
    if (issue?.severity) side.append(node('p','',`Severity: ${SEVERITY[issue.severity] || plain(issue.severity)}`));
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
      $('comparison-notice').textContent = 'This report cannot be compared reliably. Recheck the page and save a new baseline.';
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
    [['Baseline page',baseline.target_url],['Baseline final URL',baseline.facts?.final_url || baseline.target_url],['Baseline date',dateLabel(baseline.scanned_at)],['Baseline versions',reportVersion(baseline)],['Current page',currentReport.target_url],['Current final URL',currentReport.facts?.final_url || currentReport.target_url],['Current date',dateLabel(currentReport.scanned_at)],['Current versions',reportVersion(currentReport)]].forEach(([label,value])=>{const row=node('div');row.append(node('dt','',label),node('dd','',value));metadata.append(row);});
    details.append(metadata);
    details.append(node('p','small muted','The baseline comes from this browser or an imported JSON file. The server does not authenticate its source or integrity.'));
    if (!comparison.compatible) return;
    if (comparison.score_comparable) {
      Object.entries(comparison.score_delta || {}).filter(([key]) => key !== 'content').forEach(([key,value]) => {
        const item=node('div','delta-card');
        item.append(node('span','',key==='overall'?'Overall score':areaLabel(key)),node('strong','',`${value > 0 ? '+' : ''}${value}`),node('span','small muted','points since baseline'));
        scores.append(item);
      });
    }
    ['resolved','new_issues','persistent','unverified','worsened'].forEach((key) => {
      const item=node('div','diff-count');
      item.append(node('strong','',comparison.counts?.[key] || 0),node('span','',DIFF_LABELS[key]));
      counts.append(item);
    });
    details.append(node('p','small muted','“Worsened” is a subset of issues still present. Missing evidence is never treated as a fix.'));
    diffGroups().forEach(([key,items]) => {
      const group=node('section','diff-group');
      group.append(node('h4','',`${DIFF_LABELS[key]} (${items.length})`));
      if (!items.length) group.append(node('p','small muted','No findings in this category.'));
      items.forEach((diff,index) => {
        const item=node('details','diff-item'); item.dataset.diffId=`${key}-${index}`;
        const summary=node('summary');
        summary.append(node('span','',plain(diff.label,diff.id)),node('span','area-tag',areaLabel(diff.area)));
        if (diff.change==='worsened' || diff.change==='improved') summary.append(node('span','tag',DIFF_LABELS[diff.change]));
        const body=node('div','diff-body'); body.append(node('p','small muted',diffExplanation(diff)));
        const evidence=node('div','diff-evidence-grid');
        appendEvidence(evidence,'Before · baseline',diff.before,diff.before_issue);
        appendEvidence(evidence,'After · current audit',diff.after,diff.after_issue);
        body.append(evidence); item.append(summary,body); group.append(item);
      });
      details.append(group);
    });
  }

  function comparisonMarkdown() {
    if (!comparison || !baseline) return [];
    const lines=['## Fix and recheck comparison','',`- Baseline page: ${markdownText(baseline.target_url)}`,`- Baseline final URL: ${markdownText(baseline.facts?.final_url || baseline.target_url)}`,`- Baseline date: ${markdownText(baseline.scanned_at)}`,`- Baseline versions: ${markdownText(reportVersion(baseline))}`,`- Current page: ${markdownText(currentReport.target_url)}`,`- Current final URL: ${markdownText(currentReport.facts?.final_url || currentReport.target_url)}`,`- Current date: ${markdownText(currentReport.scanned_at)}`,`- Current versions: ${markdownText(reportVersion(currentReport))}`,'',comparisonReason(),'','Observed changes do not establish causality, rankings, traffic, or AI citations.'];
    lines.push('','The baseline comes from this browser or an imported JSON file. The server does not authenticate its source or integrity.');
    if (!comparison.compatible) { lines.push('','No fixes or score differences were confirmed.'); return lines; }
    if (comparison.score_comparable) Object.entries(comparison.score_delta || {}).filter(([key])=>key!=='content').forEach(([key,value])=>lines.push(`- ${key==='overall'?'Overall score':areaLabel(key)}: ${value>0?'+':''}${value}`));
    diffGroups().forEach(([key,items]) => {
      lines.push('',`### ${DIFF_LABELS[key]} (${items.length})`,'');
      if (!items.length) lines.push('No findings in this category.');
      items.forEach((diff) => {
        lines.push('',`#### ${markdownText(diff.label || diff.id)}`,'',diffExplanation(diff));
        [['Before · baseline',diff.before,diff.before_issue],['After · current audit',diff.after,diff.after_issue]].forEach(([label,check,issue])=>lines.push('',`**${label}**`, `- Status: ${check?(STATUS[check.status] || 'Unverified'):'Check missing'}`,`- Evidence: ${markdownText(check?.value)}`,`- Severity: ${markdownText(issue?.severity ? SEVERITY[issue.severity] || issue.severity : null)}`,`- Guidance: ${markdownText(check?.hint || issue?.fix)}`));
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
    try { window.localStorage.removeItem(BASELINE_KEY); storedBaselinePresent=false; baselineStatus('Baseline removed from this browser.'); }
    catch { baselineStatus('Baseline removed from this tab. Browser storage access is blocked; clear site data in browser settings to remove an earlier saved copy.'); }
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
    const text = ['# MandAPI GEO report', ''];
    if (isDemo) text.push('> DEMONSTRATION: entirely fictional data; no real page was audited.', '');
    text.push(`- Requested page: ${markdownText(r.target_url)}`, `- Final URL: ${markdownText(r.facts?.final_url || r.target_url)}`, `- Date: ${markdownText(r.scanned_at)}`, `- Duration: ${markdownText(r.elapsed_ms)} ms`, `- Engine: ${markdownText(r.engine)}`, '', `**Scope:** ${SCOPE}`, '', '## Scores', '', `- Overall: ${score(r.score.overall)}/100`);
    Object.entries(AREA).forEach(([key, label]) => { if (r.areas.some((area) => area.area === key)) text.push(`- ${label}: ${score(r.score[key])}/100`); });
    text.push('', markdownText(r.score.summary), '', '## Fix priorities', '');
    if (!getIssues().length) text.push('No issues were flagged by the rules. This does not guarantee that no problems exist.', '');
    getIssues().forEach((issue) => text.push(`### ${markdownText(issue.title)}`, '', `Area: ${areaLabel(issue.area)} · Severity: ${SEVERITY[issue.severity] || 'Not provided'}`, '', markdownText(issue.detail), '', `**How to review:** ${markdownText(issue.fix)}`, ''));
    text.push('## All checks', '');
    getChecks().forEach((check) => text.push(`### ${markdownText(check.label)}`, '', `Area: ${areaLabel(check.area)} · Status: ${STATUS[check.status] || 'Info'}`, '', `**Evidence:** ${markdownText(check.value)}`, '', `**Guidance:** ${markdownText(check.hint)}`, ''));
    text.push('', `Report version: ${markdownText(r.schema_version)}`, `Scoring version: ${markdownText(r.scoring_version)}`);
    if (comparison && !isDemo) text.push('', ...comparisonMarkdown());
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
      target_url:'https://example.com/', domain:'example.com', scanned_at:'2026-09-26T09:00:00Z', elapsed_ms:3200, engine:'demonstration — fictional data',
      score:{ overall:76, seo:84, geo:68, content:0, grade:'B', summary:'Illustrative HTML checks: description length, declared authorship, and semantic structure. Scores and values are fictional.' },
      facts:{ final_url:'https://example.com/' },
      areas:[
        { area:'seo', label:AREA.seo, score:84, checks:[{ id:'demo-https', area:'seo', label:'HTTPS connection', status:'pass', value:'Example: the page uses HTTPS.', hint:'Keep a valid certificate and redirect the HTTP version.' },{ id:'demo-description', area:'seo', label:'Meta description length', status:'warn', value:'30 characters; Portuguese page (fictional example).', hint:'Length is an editorial guideline, not an assessment of the description’s meaning or quality.' },{ id:'demo-canonical', area:'seo', label:'Canonical URL', status:'pass', value:'https://example.com/ (fictional URL)', hint:'Confirm that the URL is the main version of the page.' }] },
        { area:'geo', label:AREA.geo, score:68, checks:[{ id:'demo-author', area:'geo', label:'Declared authorship in HTML', status:'warn', value:'No author declaration found (fictional example).', hint:'Check whether suitable author identification is present in the HTML. This check does not verify credentials.' },{ id:'demo-bots', area:'geo', label:'AI crawler rules', status:'info', value:'Example: this report did not fetch a real robots.txt file.', hint:'Review search access and training access decisions separately.' },{ id:'demo-extractable', area:'geo', label:'Text-to-HTML ratio', status:'pass', value:'Text accounts for 8.2% of HTML (fictional example).', hint:'The ratio is a structural heuristic; it does not measure topic understanding or citation probability.' },{ id:'demo-semantic', area:'geo', label:'Semantic HTML', status:'warn', value:'No <main> or <article> tag found (fictional example).', hint:'Use suitable semantic elements to identify the main content, without changing information merely to earn points.' }] }
      ],
      issues:[
        { id:'demo-author', area:'geo', severity:'medium', title:'Review the author declaration', detail:'In this fictional example, no author declaration was found in the HTML.', fix:'Where appropriate for the page, identify the real author in visible content and corresponding markup.' },
        { id:'demo-semantic', area:'geo', severity:'medium', title:'Identify main content with semantic HTML', detail:'In this fictional example, the HTML contains neither <main> nor <article>.', fix:'Review the structure and use <main> for the main content or <article> for independent content where appropriate.' },
        { id:'demo-description', area:'seo', severity:'low', title:'Review meta description length', detail:'In this fictional Portuguese example, the description has 30 characters. The tool did not evaluate its meaning.', fix:'Review the description in its page and language context. Length alone does not determine quality or the search snippet.' }
      ]
    }, true);
  });
})();
