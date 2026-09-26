'use strict';

(() => {
  const $ = (id) => document.getElementById(id);
  const form = $('scan-form');
  if (!form) return;

  const AREA = { seo: '技术 SEO', geo: 'AI 搜索就绪度', content: '内容' };
  const SEVERITY = { critical: '严重', high: '高', medium: '中', low: '低' };
  const STATUS = { pass: '已通过', warn: '需关注', fail: '未通过', info: '仅供参考' };
  const SCOPE = '单页 HTML 与公开辅助文件。不执行 JavaScript、不抓取全站、不追踪排名或引用。启发式评分不保证排名。';
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
    $('submit').textContent = busy ? '分析中…' : '分析页面 →';
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
    $('results').hidden = false;
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
      target_url:'https://example.com/', domain:'example.com', scanned_at:'2026-09-26T09:00:00Z', elapsed_ms:3200, engine:'演示 — 虚构数据',
      score:{ overall:76, seo:84, geo:68, content:0, grade:'B', summary:'演示示例：技术基础较好，页面描述与内容身份信息仍可改进。分数均为虚构。' },
      facts:{ final_url:'https://example.com/' },
      areas:[
        { area:'seo', label:AREA.seo, score:84, checks:[{ id:'demo-https', area:'seo', label:'HTTPS 连接', status:'pass', value:'示例：页面使用 HTTPS。', hint:'保持证书有效，并重定向 HTTP 版本。' },{ id:'demo-description', area:'seo', label:'页面描述', status:'warn', value:'虚构示例：描述过于笼统，没有说明服务内容。', hint:'编写具体描述，概括此页面的用途。' },{ id:'demo-canonical', area:'seo', label:'规范 URL', status:'pass', value:'https://example.com/ (虚构 URL)', hint:'确认该 URL 对应页面的主要版本。' }] },
        { area:'geo', label:AREA.geo, score:68, checks:[{ id:'demo-author', area:'geo', label:'内容负责人', status:'warn', value:'示例：未找到明确的内容负责人信息。', hint:'适当时标明作者、相关经验或内容负责机构。' },{ id:'demo-bots', area:'geo', label:'AI 爬虫规则', status:'info', value:'示例：此报告没有读取真实 robots.txt 文件。', hint:'分别检查针对搜索和模型训练的访问决定。' },{ id:'demo-headings', area:'geo', label:'标题结构', status:'pass', value:'示例：一个主标题与描述清晰的章节。', hint:'用标题帮助读者找到答案，避免刻意堆砌词语。' },{ id:'demo-answer', area:'geo', label:'回答读者需求', status:'warn', value:'示例：正文没有说明服务包含哪些内容。', hint:'先回答核心问题，再说明条件、示例与限制。' }] }
      ],
      issues:[
        { id:'demo-description', area:'seo', severity:'high', title:'让页面描述更具体', detail:'此虚构示例中，描述过于笼统，没有说明页面提供的内容。', fix:'用有用的一句话概括服务与目标人群，避免堆砌关键词。' },
        { id:'demo-author', area:'geo', severity:'medium', title:'明确内容由谁负责', detail:'此虚构示例中，没有清楚标明负责的个人或组织。', fix:'补充可核实的身份信息与相关背景。' },
        { id:'demo-answer', area:'geo', severity:'low', title:'更清楚地说明服务', detail:'此虚构示例中，读者需要到其他页面寻找基本信息。', fix:'根据真实情况说明包含内容、适用人群与相关条件。' }
      ]
    }, true);
  });
})();
