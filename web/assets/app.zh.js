'use strict';

(() => {
  const $ = (id) => document.getElementById(id);
  const form = $('scan-form');
  if (!form) return;

  const AREA = { seo: '技术 SEO', geo: 'AI 搜索就绪度', content: '内容' };
  const SEVERITY = { critical: '严重', high: '高', medium: '中', low: '低' };
  const STATUS = { pass: '已通过', warn: '需关注', fail: '未通过', info: '仅供参考', unknown:'无法确认' };
  const SCOPE = '单页 HTML 与公开辅助文件。不执行 JavaScript、不抓取全站、不追踪排名或引用。启发式评分不保证排名。';
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
  const DIFF_LABELS = { resolved:'本次检查已解决', new_issues:'新增问题', persistent:'仍然存在', unverified:'无法确认', worsened:'变得更严重', improved:'严重程度降低' };
  const COMPARE_REASONS = {
    missing_version:'此旧报告缺少必要版本信息，请重新分析页面以建立兼容基线。',
    schema_mismatch:'报告格式版本不同，无法确认两个版本之间的变化。',
    engine_mismatch:'分析引擎不同，请建立新基线，使用相同规则进行比较。',
    scoring_mismatch:'评分规则发生变化，不能直接比较这些分数或确认修复。',
    target_mismatch:'请求的 URL 不同，请比较同一页面以确认变化。',
    redirect_mismatch:'重定向后的最终 URL 不同，无法确认这些变化来自同一页面。',
    not_newer:'当前分析时间必须晚于基线，请在修改后重新分析。',
    coverage_changed:'检查覆盖范围改变，可以查看可比较的证据，但不能可靠比较分数。',
    weights_changed:'检查权重改变，可以查看可比较的证据，但不比较分数。'
  };

  function node(tag, className, text) {
    const element = document.createElement(tag);
    if (className) element.className = className;
    if (text !== undefined && text !== null) element.textContent = String(text);
    return element;
  }

  function plain(value, fallback = '未提供') {
    return value === null || value === undefined || value === '' ? fallback : String(value);
  }

  function score(value) {
    const number = Number(value);
    return Number.isFinite(number) ? Math.max(0, Math.min(100, Math.round(number))) : 0;
  }

  function areaLabel(area) { return AREA[area] || plain(area, '其他'); }
  function getIssues() { return currentReport?.issues || []; }
  function getChecks() { return (currentReport?.areas || []).flatMap((area) => (area.checks || []).map((check) => ({ ...check, area: check.area || area.area }))); }

  function dateLabel(value) {
    const date = new Date(value);
    return Number.isNaN(date.getTime()) ? '未提供' : date.toLocaleString('zh-CN', { dateStyle: 'medium', timeStyle: 'short' });
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
    $('submit').textContent = busy ? '分析中…' : '免费分析这个页面 →';
    $('retest-baseline').disabled = busy;
    $('save-baseline').disabled = busy;
    $('import-baseline').disabled = busy;
  }

  function validateUrl(raw) {
    if (!raw.trim()) throw new Error('请输入想分析的页面 URL。');
    let input = raw.trim();
    if (!/^[a-z][a-z\d+.-]*:/i.test(input)) input = `https://${input}`;
    let url;
    try { url = new URL(input); } catch { throw new Error('请检查地址，例如：https://example.com/page'); }
    if (!['http:', 'https:'].includes(url.protocol) || !url.hostname || !url.hostname.includes('.')) {
      throw new Error('请使用公开的 HTTP 或 HTTPS URL，例如：https://example.com');
    }
    if (url.username || url.password) throw new Error('请使用公开 URL，地址中不能包含用户名或密码。');
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
      card.append(top, bar, node('p', '', `${area?.checks?.length || 0} 项检查 · 启发式评分`));
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
    $('filter-count').textContent = `${filtered.length} / ${issues.length} 项优先问题已显示。`;
    if (!filtered.length) {
      container.append(node('div', 'empty-state', issues.length ? '没有符合筛选条件的问题，请选择其他领域或严重程度。' : '本次规则未发现问题。请结合检查项与方法局限进行复查。'));
      return;
    }
    filtered.forEach((issue) => {
      const card = node('article', 'issue-card');
      card.dataset.severity = Object.hasOwn(SEVERITY, issue.severity) ? issue.severity : 'low';
      const header = node('div', 'issue-heading');
      header.append(node('span', 'severity-tag', `严重程度 ${SEVERITY[issue.severity]?.toLowerCase() || '未提供'}`), node('span', 'area-tag', areaLabel(issue.area)), node('h4', '', plain(issue.title, '待关注项')));
      const fix = node('p', 'issue-fix');
      fix.append(node('strong', '', '复查建议：'), document.createTextNode(plain(issue.fix, '请查看检查项，并结合页面实际情况判断。')));
      card.append(header, node('p', '', plain(issue.detail, '请查看检查项了解更多细节。')), fix);
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
      container.append(node('p', 'empty-state', '此领域没有可用检查项。'));
      return;
    }
    checks.forEach((check, index) => {
      const item = node('details', 'check-item');
      item.dataset.checkId = `${plain(check.id, 'check')}-${index}`;
      const summary = node('summary');
      const status = node('span', 'check-status', STATUS[check.status] || '仅供参考');
      status.dataset.status = Object.hasOwn(STATUS, check.status) ? check.status : 'info';
      summary.append(status, node('span', '', plain(check.label, check.id)), node('span', 'area-tag', areaLabel(check.area)));
      const evidence = node('div', 'check-evidence');
      const list = node('dl');
      list.append(node('dt', '', '检测证据'), node('dd', '', plain(check.value, '此检查项没有额外检测值。')), node('dt', '', '建议'), node('dd', '', plain(check.hint, '请结合页面情况复核结果，此检查项暂无额外建议。')));
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
    $('report-domain').textContent = plain(report.domain, '已分析页面');
    $('report-summary').textContent = plain(report.score.summary, '请查看每项检查的证据来理解分数。');
    $('report-url').textContent = plain(report.target_url);
    $('report-final-url').textContent = plain(report.facts?.final_url, report.target_url);
    $('report-date').textContent = demo ? '虚构日期 · 演示示例' : `${dateLabel(report.scanned_at)} （本地时间）`;
    $('report-time').textContent = demo ? '虚构用时 · 3.2 秒' : `${(Math.max(0, Number(report.elapsed_ms) || 0) / 1000).toLocaleString('zh-CN', { maximumFractionDigits:1 })} s`;
    $('engine').textContent = plain(report.engine);
    $('rescan').textContent = demo ? '分析我的页面 ↗' : '再次分析 ↗';
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
    if (status === 429) return '已达到分析次数限制，请稍后重试。';
    if (status === 503) return '服务暂时繁忙，请稍后重试。';
    if (Array.isArray(data?.detail)) return '地址未通过验证，请检查 URL 后重试。';
    return `分析无法完成（HTTP ${status}），请稍后重试。`;
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
    showStatus('loading', '正在读取页面并检查信号…', '用时取决于目标网站响应，你可以随时取消等待。');
    controller = new AbortController();
    const requestController = controller;
    let timedOut = false;
    const timeout = window.setTimeout(() => { timedOut = true; requestController.abort(); }, 120000);
    try {
      const response = await fetch('/api/scan', { method:'POST', headers:{ 'Content-Type':'application/json', 'Accept':'application/json' }, body:JSON.stringify({ url, ai_summary:false, language:document.documentElement.lang }), signal:requestController.signal });
      let data;
      try { data = await response.json(); } catch {
        if (requestController.signal.aborted) throw new DOMException('Aborted', 'AbortError');
        throw new Error('服务器返回了意外响应，请稍后重试。');
      }
      if (!response.ok) throw new Error(errorMessage(data, response.status));
      if (!data || !data.score || !Array.isArray(data.areas) || !Array.isArray(data.issues)) throw new Error('收到的报告不完整，请重新分析。');
      showStatus('success', '分析完成，报告已准备好。', '查看证据并下载副本，便于之后对比。');
      renderReport(data);
    } catch (error) {
      if (error.name === 'AbortError') {
        showStatus(timedOut ? 'error' : 'cancelled', timedOut ? '分析超过等待时间。' : '已取消等待。', timedOut ? '目标网站可能响应较慢或阻止读取，请稍后重试。' : '服务器可能继续完成已发起的请求，你可以分析其他页面。');
      } else {
        showStatus('error', '无法分析此页面。', error instanceof TypeError ? '请检查网络后重试，服务也可能暂时不可用。' : error.message);
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
    [['基线页面',baseline.target_url],['最终 URL',baseline.facts?.final_url || baseline.target_url],['基线日期',dateLabel(baseline.scanned_at)],['版本：格式 / 评分 / 引擎',reportVersion(baseline)]].forEach(([label,value]) => {
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
      baselineStatus('已在此浏览器保存基线。修改页面后，可以重新分析。');
    } catch {
      baselineStatus('浏览器阻止了存储。基线仅在当前标签页有效，刷新或切换语言后会丢失。先前保存的副本可能仍然存在。');
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
        baselineStatus('已恢复当前浏览器中的基线，没有启动任何分析。');
      }
    } catch {
      baselineStatus('无法读取已保存的基线，可以导入有效 JSON，或仅在当前标签页使用基线。');
    }
    renderBaseline();
  }

  function baselineError(error) {
    baselineStatus(error.message === 'baseline_too_large' ? '文件或报告超过 1 MiB 限制，请选择更小的报告。' : '无法使用此文件，请导入有效的 MandAPI GEO JSON 报告，不接受演示数据或不完整文件。',true);
  }

  function diffGroups() {
    if (!comparison?.compatible) return [];
    return [['resolved',comparison.resolved],['new_issues',comparison.new_issues],['persistent',comparison.persistent],['unverified',comparison.unverified]].map(([key,items]) => [key,items || []]);
  }

  function diffExplanation(diff) {
    if (['previous_not_scored','previous_unknown','check_missing_before'].includes(diff.reason)) return '基线中的证据不足，不能把此问题认定为新增问题或退化。';
    if (diff.change === 'worsened') return '两次分析之间，此项状态变得更严重。';
    if (diff.change === 'improved') return '状态有所改善，但仍有需要关注的问题。';
    if (diff.change === 'resolved') return '同一检查项在最近分析中已通过，但这不能证明变化的原因。';
    if (diff.change === 'new_issue') return '此检查项新发现了一个问题。';
    if (diff.reason === 'check_missing') return '新报告中缺少此检查项，不能确认问题已修复。';
    if (diff.reason === 'not_scored' || diff.reason === 'unknown_status' || diff.change === 'unverified') return '新结果不能确认此问题是否已解决。';
    return '问题仍然存在，请先比较证据再采取行动。';
  }

  function comparisonReason() {
    if (comparison?.compatible && !comparison.score_comparable && !COMPARE_REASONS[comparison.score_reason]) return '没有足够的等价数据来比较分数，请只查看能够确认的检查项变化。';
    return COMPARE_REASONS[comparison?.reason] || COMPARE_REASONS[comparison?.score_reason] || '已比较检查项。只有版本、覆盖范围和权重相同时才比较分数。';
  }

  function appendEvidence(container,label,check,issue) {
    const side = node('div','diff-evidence');
    side.append(node('h5','',label),node('p','diff-status',check ? (STATUS[check.status] || '无法确认') : '缺少检查项'),node('p','',plain(check?.value,'暂无可用证据。')));
    if (issue?.severity) side.append(node('p','',`严重程度: ${SEVERITY[issue.severity] || plain(issue.severity)}`));
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
      $('comparison-notice').textContent = '无法可靠比较此报告，请重新分析页面并保存新基线。';
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
    [['基线页面',baseline.target_url],['基线最终 URL',baseline.facts?.final_url || baseline.target_url],['基线日期',dateLabel(baseline.scanned_at)],['基线版本',reportVersion(baseline)],['当前页面',currentReport.target_url],['当前最终 URL',currentReport.facts?.final_url || currentReport.target_url],['当前日期',dateLabel(currentReport.scanned_at)],['当前版本',reportVersion(currentReport)]].forEach(([label,value])=>{const row=node('div');row.append(node('dt','',label),node('dd','',value));metadata.append(row);});
    details.append(metadata);
    details.append(node('p','small muted','基线来自此浏览器或导入的 JSON 文件，服务器不认证其来源或完整性。'));
    if (!comparison.compatible) return;
    if (comparison.score_comparable) {
      Object.entries(comparison.score_delta || {}).filter(([key]) => key !== 'content').forEach(([key,value]) => {
        const item=node('div','delta-card');
        item.append(node('span','',key==='overall'?'总分':areaLabel(key)),node('strong','',`${value > 0 ? '+' : ''}${value}`),node('span','small muted','分，较基线变化'));
        scores.append(item);
      });
    }
    ['resolved','new_issues','persistent','unverified','worsened'].forEach((key) => {
      const item=node('div','diff-count');
      item.append(node('strong','',comparison.counts?.[key] || 0),node('span','',DIFF_LABELS[key]));
      counts.append(item);
    });
    details.append(node('p','small muted','“变得更严重”属于“仍然存在”的子集，证据缺失绝不视为修复。'));
    diffGroups().forEach(([key,items]) => {
      const group=node('section','diff-group');
      group.append(node('h4','',`${DIFF_LABELS[key]} (${items.length})`));
      if (!items.length) group.append(node('p','small muted','此类别没有问题。'));
      items.forEach((diff,index) => {
        const item=node('details','diff-item'); item.dataset.diffId=`${key}-${index}`;
        const summary=node('summary');
        summary.append(node('span','',plain(diff.label,diff.id)),node('span','area-tag',areaLabel(diff.area)));
        if (diff.change==='worsened' || diff.change==='improved') summary.append(node('span','tag',DIFF_LABELS[diff.change]));
        const body=node('div','diff-body'); body.append(node('p','small muted',diffExplanation(diff)));
        const evidence=node('div','diff-evidence-grid');
        appendEvidence(evidence,'之前 · 基线',diff.before,diff.before_issue);
        appendEvidence(evidence,'之后 · 当前分析',diff.after,diff.after_issue);
        body.append(evidence); item.append(summary,body); group.append(item);
      });
      details.append(group);
    });
  }

  function comparisonMarkdown() {
    if (!comparison || !baseline) return [];
    const lines=['## 修改复测比较','',`- 基线页面: ${markdownText(baseline.target_url)}`,`- 基线最终 URL: ${markdownText(baseline.facts?.final_url || baseline.target_url)}`,`- 基线日期: ${markdownText(baseline.scanned_at)}`,`- 基线版本: ${markdownText(reportVersion(baseline))}`,`- 当前页面: ${markdownText(currentReport.target_url)}`,`- 当前最终 URL: ${markdownText(currentReport.facts?.final_url || currentReport.target_url)}`,`- 当前日期: ${markdownText(currentReport.scanned_at)}`,`- 当前版本: ${markdownText(reportVersion(currentReport))}`,'',comparisonReason(),'','观察到的变化不能证明因果关系、排名、流量或 AI 引用。'];
    lines.push('','基线来自此浏览器或导入的 JSON 文件，服务器不认证其来源或完整性。');
    if (!comparison.compatible) { lines.push('','未确认任何修复或分数变化。'); return lines; }
    if (comparison.score_comparable) Object.entries(comparison.score_delta || {}).filter(([key])=>key!=='content').forEach(([key,value])=>lines.push(`- ${key==='overall'?'总分':areaLabel(key)}: ${value>0?'+':''}${value}`));
    diffGroups().forEach(([key,items]) => {
      lines.push('',`### ${DIFF_LABELS[key]} (${items.length})`,'');
      if (!items.length) lines.push('此类别没有问题。');
      items.forEach((diff) => {
        lines.push('',`#### ${markdownText(diff.label || diff.id)}`,'',diffExplanation(diff));
        [['之前 · 基线',diff.before,diff.before_issue],['之后 · 当前分析',diff.after,diff.after_issue]].forEach(([label,check,issue])=>lines.push('',`**${label}**`, `- Status: ${check?(STATUS[check.status] || '无法确认'):'缺少检查项'}`,`- 证据： ${markdownText(check?.value)}`,`- 严重程度: ${markdownText(issue?.severity ? SEVERITY[issue.severity] || issue.severity : null)}`,`- 建议： ${markdownText(check?.hint || issue?.fix)}`));
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
    try { window.localStorage.removeItem(BASELINE_KEY); storedBaselinePresent=false; baselineStatus('已清除此浏览器中的基线。'); }
    catch { baselineStatus('已清除当前标签页的基线。浏览器阻止了存储访问，如需删除先前保存的副本，请在浏览器设置中清除此站点数据。'); }
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
    const text = ['# MandAPI GEO 分析报告', ''];
    if (isDemo) text.push('> 演示：全部为虚构数据，未分析真实页面。', '');
    text.push(`- 请求页面: ${markdownText(r.target_url)}`, `- 最终 URL: ${markdownText(r.facts?.final_url || r.target_url)}`, `- 日期： ${markdownText(r.scanned_at)}`, `- 用时： ${markdownText(r.elapsed_ms)} ms`, `- 引擎： ${markdownText(r.engine)}`, '', `**范围：** ${SCOPE}`, '', '## 分数', '', `- 总分： ${score(r.score.overall)}/100`);
    Object.entries(AREA).forEach(([key, label]) => { if (r.areas.some((area) => area.area === key)) text.push(`- ${label}: ${score(r.score[key])}/100`); });
    text.push('', markdownText(r.score.summary), '', '## 修正优先级', '');
    if (!getIssues().length) text.push('规则未标记问题，但不保证页面不存在问题。', '');
    getIssues().forEach((issue) => text.push(`### ${markdownText(issue.title)}`, '', `领域: ${areaLabel(issue.area)} · 严重程度: ${SEVERITY[issue.severity] || '未提供'}`, '', markdownText(issue.detail), '', `**复查建议：** ${markdownText(issue.fix)}`, ''));
    text.push('## 全部检查项', '');
    getChecks().forEach((check) => text.push(`### ${markdownText(check.label)}`, '', `领域: ${areaLabel(check.area)} · Status: ${STATUS[check.status] || '仅供参考'}`, '', `**证据：** ${markdownText(check.value)}`, '', `**建议：** ${markdownText(check.hint)}`, ''));
    text.push('', `报告版本: ${markdownText(r.schema_version)}`, `评分版本: ${markdownText(r.scoring_version)}`);
    if (comparison && !isDemo) text.push('', ...comparisonMarkdown());
    return text.join('\n');
  }

  function download(format) {
    if (!currentReport) return;
    const report = isDemo ? { ...currentReport, demonstration:true, demonstration_notice:'虚构数据，未执行真实分析。' } : currentReport;
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
      target_url:'https://example.com/', domain:'example.com', scanned_at:'2026-09-26T09:00:00Z', elapsed_ms:3200, engine:'演示 — 虚构数据',
      score:{ overall:76, seo:84, geo:68, content:0, grade:'B', summary:'HTML 检查演示：描述长度、声明的作者信息和语义结构。分数与检测值均为虚构。' },
      facts:{ final_url:'https://example.com/' },
      areas:[
        { area:'seo', label:AREA.seo, score:84, checks:[{ id:'demo-https', area:'seo', label:'HTTPS 连接', status:'pass', value:'示例：页面使用 HTTPS。', hint:'保持证书有效，并重定向 HTTP 版本。' },{ id:'demo-description', area:'seo', label:'Meta description 长度', status:'warn', value:'30 个字符；葡语页面（虚构示例）。', hint:'长度只是编辑参考，不代表对描述含义或质量的判断。' },{ id:'demo-canonical', area:'seo', label:'规范 URL', status:'pass', value:'https://example.com/ (虚构 URL)', hint:'确认该 URL 对应页面的主要版本。' }] },
        { area:'geo', label:AREA.geo, score:68, checks:[{ id:'demo-author', area:'geo', label:'HTML 中声明的作者信息', status:'warn', value:'未找到声明的作者信息（虚构示例）。', hint:'检查 HTML 中是否有适当的作者标识，此检查不会核实资质。' },{ id:'demo-bots', area:'geo', label:'AI 爬虫规则', status:'info', value:'示例：此报告没有读取真实 robots.txt 文件。', hint:'分别检查针对搜索和模型训练的访问决定。' },{ id:'demo-extractable', area:'geo', label:'HTML 中文本的占比', status:'pass', value:'文本占 HTML 的 8.2%（虚构示例）。', hint:'这一占比是结构性启发指标，不衡量主题理解程度或引用概率。' },{ id:'demo-semantic', area:'geo', label:'语义 HTML', status:'warn', value:'未找到 <main> 或 <article> 标签（虚构示例）。', hint:'用合适的语义元素标明主要内容，不要仅为了得分而改变信息。' }] }
      ],
      issues:[
        { id:'demo-author', area:'geo', severity:'medium', title:'检查作者信息声明', detail:'此虚构示例中，HTML 未检测到声明的作者信息。', fix:'在适合该页面的情况下，于可见内容及相应标记中提供真实作者信息。' },
        { id:'demo-semantic', area:'geo', severity:'medium', title:'用语义 HTML 标明主要内容', detail:'此虚构示例中，HTML 不含 <main> 或 <article>。', fix:'检查结构，适当使用 <main> 标明主要内容，或用 <article> 标明独立内容。' },
        { id:'demo-description', area:'seo', severity:'low', title:'检查 meta description 长度', detail:'此虚构葡语示例中，描述有 30 个字符，工具没有评估其含义。', fix:'请结合页面与语言检查描述，长度本身不能决定质量或搜索结果中显示的摘要。' }
      ]
    }, true);
  });
})();
