'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const { validateReport, compareReports } = require('../../web/assets/comparison.js');

function check(id = 'seo.title', status = 'warn', patch = {}) {
  return { id, area: 'seo', label: 'Page title', status, weight: 2, value: 'Observed title', hint: 'Review the title', ...patch };
}

function report(checks = [check()], patch = {}) {
  return {
    target_url: 'https://example.com/page', domain: 'example.com', scanned_at: '2026-09-26T10:00:00Z',
    engine: 'rules-v2', schema_version: 1, scoring_version: 'readiness-2026-09-26', scope: 'single_page',
    score: { overall: 50, seo: 50, geo: 0, content: 0 },
    facts: { final_url: 'https://example.com/page', text: 'Not retained in the local baseline' },
    areas: [{ area: 'seo', label: 'SEO', score: 50, checks }],
    issues: checks.filter((item) => ['warn', 'fail'].includes(item.status)).map((item) => ({
      id: item.id, area: item.area, severity: 'high', title: 'Review this check', detail: 'Evidence description', fix: 'Review its source',
    })), ...patch,
  };
}

function later(checks, patch = {}) {
  return report(checks, { scanned_at: '2026-09-27T10:00:00+00:00', ...patch });
}

function invalid(value, code) {
  assert.throws(() => validateReport(value), (error) => error.code === code && error.message === code);
}

test('works as a browser global without DOM and as a CommonJS module', () => {
  const context = vm.createContext({ URL });
  vm.runInContext(fs.readFileSync(path.join(__dirname, '../../web/assets/comparison.js'), 'utf8'), context);
  assert.equal(typeof context.GeoComparison.validateReport, 'function');
  assert.equal(typeof context.GeoComparison.compareReports, 'function');
  assert.equal(Object.isFrozen(context.GeoComparison), true);
});

test('normalizes a compact baseline, preserving delivery evidence and versions', () => {
  const source = report();
  const normalized = validateReport(source);
  assert.equal(normalized.scanned_at, '2026-09-26T10:00:00.000Z');
  assert.equal(normalized.schema_version, 1);
  assert.equal(normalized.scoring_version, 'readiness-2026-09-26');
  assert.deepEqual(normalized.facts, { final_url: source.facts.final_url });
  assert.equal(normalized.areas[0].checks[0].hint, 'Review the title');
  assert.equal(normalized.issues[0].fix, 'Review its source');
  assert.deepEqual(validateReport(normalized), normalized);
  normalized.areas[0].checks[0].value = 'Changed';
  assert.equal(source.areas[0].checks[0].value, 'Observed title');
});

test('only warn or fail changing to pass resolves an issue', () => {
  for (const status of ['warn', 'fail']) {
    const comparison = compareReports(report([check('seo.title', status)]), later([check('seo.title', 'pass')], { score: { overall: 100, seo: 100, geo: 0, content: 0 } }));
    assert.equal(comparison.compatible, true);
    assert.equal(comparison.counts.resolved, 1);
    assert.equal(comparison.resolved[0].before.status, status);
    assert.equal(comparison.resolved[0].after.status, 'pass');
    assert.equal(comparison.resolved[0].before_issue.fix, 'Review its source');
    assert.equal(comparison.resolved[0].after_issue, null);
    assert.equal(comparison.score_comparable, true);
    assert.equal(comparison.score_delta.overall, 50);
  }
});

test('informational, unknown and missing checks never turn a previous failure into a fix', () => {
  const previous = report([check('seo.title', 'fail'), check('seo.other', 'pass')]);
  for (const [status, reason] of [['info', 'not_scored'], ['unknown', 'unknown_status'], [null, 'check_missing']]) {
    const next = [check('seo.other', 'pass')];
    if (status) next.push(check('seo.title', status));
    const comparison = compareReports(previous, later(next));
    assert.equal(comparison.counts.resolved, 0);
    assert.equal(comparison.counts.unverified, 1);
    assert.equal(comparison.unverified[0].reason, reason);
    assert.equal(comparison.score_comparable, false);
    assert.equal(comparison.score_reason, 'coverage_changed');
    assert.equal('score_delta' in comparison, false);
  }
});

test('only previously passing checks establish new issues; absent or uncertain evidence stays unverified', () => {
  const previous = report([check('seo.pass', 'pass'), check('seo.info', 'info'), check('seo.unknown', 'unknown')]);
  const next = later([check('seo.pass', 'warn'), check('seo.info', 'fail'), check('seo.absent', 'warn'), check('seo.unknown', 'fail')]);
  const comparison = compareReports(previous, next);
  assert.deepEqual(comparison.new_issues.map((entry) => entry.id), ['seo.pass']);
  assert.equal(comparison.counts.unverified, 3);
  assert.deepEqual(Object.fromEntries(comparison.unverified.map((entry) => [entry.id, entry.reason])), {
    'seo.info': 'previous_not_scored', 'seo.unknown': 'previous_unknown', 'seo.absent': 'check_missing_before',
  });
  assert.equal(comparison.counts.worsened, 0);
  assert.equal(comparison.counts.resolved, 0);
});

test('a sitemap timeout followed by HTTP 404 supplies new evidence, not evidence of a new regression', () => {
  // These states and weights are emitted by seo.analyze for an unverified sitemap
  // request followed by a confirmed 404/410 response. Neither proves prior health.
  const previous = report([check(), check('seo.sitemap', 'info', {
    label: 'sitemap.xml', weight: 0, value: 'não verificado',
    hint: 'Falha de consulta não comprova ausência.',
  })]);
  const current = later([check(), check('seo.sitemap', 'warn', {
    label: 'sitemap.xml', weight: 1, value: 'não encontrado (HTTP 404/410)',
    hint: 'Um sitemap pode existir em outro caminho.',
  })]);
  const issue = current.issues.find((item) => item.id === 'seo.sitemap');
  issue.severity = 'low';
  issue.title = 'Sitemap não encontrado nos endereços consultados';
  const comparison = compareReports(previous, current);
  assert.equal(comparison.compatible, true);
  assert.equal(comparison.counts.new_issues, 0);
  assert.equal(comparison.counts.worsened, 0);
  assert.equal(comparison.counts.unverified, 1);
  assert.equal(comparison.unverified[0].id, 'seo.sitemap');
  assert.equal(comparison.unverified[0].reason, 'previous_not_scored');
  assert.equal(comparison.unverified[0].before.value, 'não verificado');
  assert.equal(comparison.unverified[0].after.value, 'não encontrado (HTTP 404/410)');
  assert.equal(comparison.unverified[0].before_issue, null);
  assert.equal(comparison.unverified[0].after_issue.severity, 'low');
  assert.equal(comparison.score_comparable, false);
  assert.equal(comparison.score_reason, 'weights_changed');
  assert.equal('score_delta' in comparison, false);
});

test('worsening and partial improvement remain unresolved and are counted separately', () => {
  const previous = report([check('seo.worse', 'warn'), check('seo.better', 'fail'), check('seo.same', 'warn')]);
  const next = later([check('seo.worse', 'fail'), check('seo.better', 'warn'), check('seo.same', 'warn')]);
  const comparison = compareReports(previous, next);
  assert.equal(comparison.counts.persistent, 3);
  assert.equal(comparison.counts.resolved, 0);
  assert.equal(comparison.counts.new_issues, 0);
  assert.equal(comparison.counts.worsened, 1);
  assert.equal(comparison.counts.improved, 1);
  assert.deepEqual(comparison.changed.map((entry) => entry.change), ['worsened', 'improved']);
});

test('the check evidence, not issue presence or translated wording, determines a fix', () => {
  const previous = report([check('seo.title', 'warn', { label: '页面标题', value: '旧标题', hint: '修改标题' })]);
  const next = later([check('seo.title', 'fail', { label: 'Page title', value: 'Missing', hint: 'Add a title' })], { issues: [] });
  const comparison = compareReports(previous, next);
  assert.equal(comparison.counts.resolved, 0);
  assert.equal(comparison.counts.persistent, 1);
  assert.equal(comparison.counts.worsened, 1);
  assert.equal(comparison.persistent[0].before.label, '页面标题');
  assert.equal(comparison.persistent[0].after.label, 'Page title');
});

test('normalizes fragments, hostname case and default ports without collapsing distinct URLs', () => {
  const previous = report([check()], { target_url: 'https://EXAMPLE.com:443/page#old', facts: { final_url: 'https://EXAMPLE.com:443/page#old' } });
  const next = later([check('seo.title', 'pass')], { target_url: 'https://example.com/page#new', facts: { final_url: 'https://example.com/page#new' } });
  assert.equal(compareReports(previous, next).compatible, true);
  for (const target_url of ['http://example.com/page', 'https://example.com/page/', 'https://example.com/Page', 'https://example.com/page?a=1', 'https://different.example/page']) {
    const comparison = compareReports(previous, later([check()], { target_url }));
    assert.equal(comparison.compatible, false);
    assert.equal(comparison.reason, 'target_mismatch');
    assert.equal('score_delta' in comparison, false);
  }
});

test('refuses comparison after redirect destination changes', () => {
  const comparison = compareReports(report(), later([check()], { domain: 'elsewhere.example', facts: { final_url: 'https://elsewhere.example/new' } }));
  assert.equal(comparison.compatible, false);
  assert.equal(comparison.reason, 'redirect_mismatch');
});

test('legacy reports import but do not produce comparable states or score claims', () => {
  const legacy = report();
  delete legacy.schema_version;
  delete legacy.scoring_version;
  const normalized = validateReport(legacy);
  assert.equal(normalized.schema_version, null);
  assert.equal(normalized.scoring_version, null);
  const comparison = compareReports(normalized, later([check('seo.title', 'pass')]));
  assert.equal(comparison.reason, 'missing_version');
  assert.equal(comparison.compatible, false);
  assert.equal(comparison.counts.resolved, 0);
  assert.equal('score_delta' in comparison, false);
});

test('rejects engine, schema and scoring version mismatch including unsupported matching schema', () => {
  for (const [patch, reason] of [[{ engine: 'rules-v3' }, 'engine_mismatch'], [{ schema_version: 2 }, 'schema_mismatch'], [{ scoring_version: 'new-score' }, 'scoring_mismatch']]) {
    const comparison = compareReports(report(), later([check()], patch));
    assert.equal(comparison.compatible, false);
    assert.equal(comparison.reason, reason);
    assert.equal('score_delta' in comparison, false);
  }
  assert.equal(compareReports(report(undefined, { schema_version: 2 }), later(undefined, { schema_version: 2 })).reason, 'schema_mismatch');
});

test('imports and compares the optional-summary engine emitted by the scanner', () => {
  const previous = report([check('seo.title', 'warn')], { engine: 'rules-v2+llm', ai_summary: 'Earlier optional summary' });
  const next = later([check('seo.title', 'pass')], { engine: 'rules-v2+llm', ai_summary: 'Later optional summary' });
  const normalized = validateReport(previous);
  assert.equal(normalized.engine, 'rules-v2+llm');
  assert.equal('ai_summary' in normalized, false);
  assert.deepEqual(validateReport(normalized), normalized);
  const comparison = compareReports(normalized, next);
  assert.equal(comparison.compatible, true);
  assert.equal(comparison.score_comparable, true);
  assert.equal(comparison.counts.resolved, 1);
  assert.equal(comparison.older.engine, 'rules-v2+llm');
  assert.equal(comparison.current.engine, 'rules-v2+llm');
});

test('the optional-summary suffix remains part of engine compatibility', () => {
  for (const [beforeEngine, afterEngine] of [['rules-v2', 'rules-v2+llm'], ['rules-v2+llm', 'rules-v2']]) {
    const comparison = compareReports(report(undefined, { engine: beforeEngine }), later(undefined, { engine: afterEngine }));
    assert.equal(comparison.compatible, false);
    assert.equal(comparison.reason, 'engine_mismatch');
    assert.equal(comparison.score_comparable, false);
    assert.equal('score_delta' in comparison, false);
  }
});

test('accepting an engine suffix preserves bounded metadata and strict check IDs', () => {
  for (const engine of [null, {}, '', 'rules-v2+llm\n', ' rules-v2+llm', 'rules-v2 +llm', 'rules-v2+<script>', 'r'.repeat(121)]) {
    invalid(report(undefined, { engine }), 'invalid_version');
  }
  invalid(report([check('seo.title+suffix')]), 'invalid_checks');
});

test('same timestamps and time reversal cannot establish progress', () => {
  for (const scanned_at of ['2026-09-26T10:00:00Z', '2026-09-26T18:00:00+08:00', '2026-09-25T10:00:00Z']) {
    assert.equal(compareReports(report(), later([check()], { scanned_at })).reason, 'not_newer');
  }
});

test('score comparisons require the same weighted coverage, not merely a matching version', () => {
  const previous = report([check('seo.title', 'warn'), check('seo.other', 'pass')]);
  const cases = [
    [[check('seo.title', 'pass', { weight: 3 }), check('seo.other', 'pass')], 'weights_changed'],
    [[check('seo.title', 'pass', { weight: null }), check('seo.other', 'pass')], 'weights_missing'],
    [[check('seo.title', 'pass'), check('seo.other', 'info')], 'coverage_changed'],
    [[check('seo.title', 'pass'), check('seo.other', 'pass'), check('seo.new', 'pass')], 'coverage_changed'],
    [[check('seo.title', 'pass', { weight: 0 }), check('seo.other', 'pass')], 'weights_changed'],
  ];
  for (const [checks, expected] of cases) {
    const comparison = compareReports(previous, later(checks));
    assert.equal(comparison.compatible, true);
    assert.equal(comparison.counts.resolved, 1);
    assert.equal(comparison.score_comparable, false);
    assert.equal(comparison.score_reason, expected);
    assert.equal('score_delta' in comparison, false);
  }
});

test('changed weights on informational checks also disallow a score delta', () => {
  const previous = report([check(), check('seo.info', 'info', { weight: 0 })]);
  const next = later([check(), check('seo.info', 'info', { weight: 1 })]);
  const comparison = compareReports(previous, next);
  assert.equal(comparison.compatible, true);
  assert.equal(comparison.score_comparable, false);
  assert.equal(comparison.score_reason, 'weights_changed');
});

test('missing score fields or entirely unscored evidence prevents quantitative claims', () => {
  const fewerFields = later([check()], { score: { overall: 50, seo: 50 } });
  assert.equal(compareReports(report(), fewerFields).score_reason, 'score_fields_changed');
  const previous = report([check('seo.info', 'info', { weight: 0 })]);
  assert.equal(compareReports(previous, later([check('seo.info', 'info', { weight: 0 })])).score_reason, 'no_scored_checks');
});

test('check identity contains both area and stable id', () => {
  const previous = report([check('same.id', 'fail')]);
  previous.areas.push({ area: 'geo', label: 'GEO', score: 50, checks: [check('same.id', 'warn', { area: 'geo' })] });
  const next = JSON.parse(JSON.stringify(previous));
  next.scanned_at = '2026-09-27T10:00:00Z';
  next.areas[1].checks[0].status = 'pass';
  const comparison = compareReports(previous, next);
  assert.equal(comparison.counts.resolved, 1);
  assert.equal(comparison.resolved[0].area, 'geo');
  assert.equal(comparison.counts.persistent, 1);
  assert.equal(comparison.persistent[0].area, 'seo');
});

test('malicious text stays text and arbitrary object keys are not merged', () => {
  const malicious = '<img src=x onerror=alert(1)><script>throw 1</script>';
  const source = report([check('seo.title', 'warn', { label: malicious, value: malicious, hint: malicious })]);
  source.issues[0].detail = malicious;
  const parsed = JSON.parse(JSON.stringify(source).replace('"target_url":', '"__proto__":{"polluted":true},"constructor":{"prototype":{"polluted":true}},"target_url":'));
  const normalized = validateReport(parsed);
  assert.equal(normalized.areas[0].checks[0].value, malicious);
  assert.equal(normalized.issues[0].detail, malicious);
  assert.equal(Object.hasOwn(normalized, '__proto__'), false);
  assert.equal(Object.hasOwn(normalized, 'constructor'), false);
  assert.equal({}.polluted, undefined);
});

test('invalid top-level types and damaged structures are rejected without coercion', () => {
  for (const input of [null, [], '{}', 12, true, new Date(), { ...report(), facts: [] }]) invalid(input, 'invalid_report');
  for (const areas of [null, [], {}, [{ area: 'seo', checks: 'no' }], [{ area: 'bogus', checks: [] }]]) invalid(report(undefined, { areas }), 'invalid_checks');
  invalid(report(undefined, { issues: {} }), 'invalid_issues');
  invalid(report(undefined, { score: null }), 'invalid_score');
  invalid(report(undefined, { score: { overall: 50 } }), 'invalid_score');
  for (const value of ['50', -1, 101, NaN, Infinity, null]) invalid(report(undefined, { score: { overall: value, seo: 50 } }), 'invalid_score');
  invalid(report([check('seo.title', 'bogus')]), 'invalid_checks');
  invalid(report([check('seo.title', 'warn', { value: {} })]), 'invalid_checks');
  invalid(report([check('seo.title', 'warn', { area: 'geo' })]), 'invalid_checks');
});

test('credentials, misleading domains and non-HTTP URLs are rejected', () => {
  for (const target_url of ['javascript:alert(1)', 'file:///tmp/report', 'https://name:pass@example.com/', 'https://example.com\\@evil.com/', ' https://example.com', 'https://example.com/\n']) invalid(report(undefined, { target_url }), 'invalid_url');
  for (const domain of ['different.example', 'example.com/path', 'user@example.com', 'example.com?x', '<script>']) invalid(report(undefined, { domain }), 'invalid_url');
  invalid(report(undefined, { facts: { final_url: 'https://user:pass@example.com/' } }), 'invalid_url');
  invalid(report(undefined, { facts: {} }), 'invalid_url');
});

test('dates must represent actual dates and include timezone information', () => {
  for (const scanned_at of ['yesterday', '2026-02-30T10:00:00Z', '2025-02-29T10:00:00Z', '2026-09-26', '2026-09-26T10:00:00', '2026-09-26T24:00:00Z', '2026-09-26T10:00:00+25:00', null]) invalid(report(undefined, { scanned_at }), 'invalid_date');
  assert.equal(validateReport(report(undefined, { scanned_at: '2024-02-29T18:00:00+08:00' })).scanned_at, '2024-02-29T10:00:00.000Z');
});

test('duplicate IDs, demo data and incompatible report scopes cannot become baselines', () => {
  invalid(report([check(), check()], { issues: [] }), 'duplicate_check');
  const duplicateIssues = report();
  duplicateIssues.issues.push({ ...duplicateIssues.issues[0] });
  invalid(duplicateIssues, 'duplicate_issue');
  const orphanIssue = report();
  orphanIssue.issues[0].id = 'seo.not_present';
  invalid(orphanIssue, 'invalid_issues');
  invalid(report(undefined, { demonstration: true }), 'demo_report');
  invalid(report(undefined, { demonstration: 'false' }), 'demo_report');
  invalid(report(undefined, { engine: 'demonstracao' }), 'demo_report');
  invalid(report(undefined, { scope: 'full_site' }), 'unsupported_scope');
});

test('bounded counts, text, stable identifiers, weights and versions reject corrupt inputs', () => {
  invalid(report(Array.from({ length: 201 }, (_, index) => check(`seo.${index}`, 'pass'))), 'too_many_checks');
  invalid(report(undefined, { issues: Array.from({ length: 201 }, () => ({})) }), 'too_many_issues');
  invalid(report([check('bad id')]), 'invalid_checks');
  invalid(report([check('seo.title', 'warn', { value: 'x'.repeat(12001) })]), 'invalid_checks');
  for (const weight of [-1, 101, NaN, Infinity, '1']) invalid(report([check('seo.title', 'warn', { weight })]), 'invalid_weight');
  for (const schema_version of [0, -1, 1.5, '1']) invalid(report(undefined, { schema_version }), 'invalid_version');
  invalid(report(undefined, { scoring_version: {} }), 'invalid_version');
});
