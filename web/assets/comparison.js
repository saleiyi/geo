/* Evidence comparison only. Imported reports are not authenticated. No DOM or network access. */
(function (root, factory) {
  'use strict';
  const api = factory();
  if (typeof module === 'object' && module.exports) module.exports = api;
  else root.GeoComparison = api;
})(typeof globalThis === 'object' ? globalThis : this, function () {
  'use strict';

  const AREAS = new Set(['seo', 'geo', 'content']);
  const STATUSES = new Set(['pass', 'warn', 'fail', 'info', 'unknown']);
  const SEVERITIES = new Set(['critical', 'high', 'medium', 'low']);
  const SCORE_FIELDS = ['overall', 'seo', 'geo', 'content'];
  const own = (object, key) => Object.prototype.hasOwnProperty.call(object, key);
  const isRecord = (value) => value !== null && typeof value === 'object' && !Array.isArray(value)
    && (Object.getPrototypeOf(value) === Object.prototype || Object.getPrototypeOf(value) === null);
  const problem = (check) => check && (check.status === 'warn' || check.status === 'fail');
  const keyFor = (value) => `${value.area}:${value.id}`;

  function reject(code) {
    const error = new Error(code);
    error.code = code;
    throw error;
  }

  function record(value, code = 'invalid_report') {
    if (!isRecord(value)) reject(code);
    return value;
  }

  function text(value, code, max = 12000, optional = false) {
    if (optional && (value === undefined || value === null)) return null;
    if (typeof value !== 'string' || value.length > max || (!optional && !value.trim())) reject(code);
    return value;
  }

  function identifier(value, code) {
    if (typeof value !== 'string' || !/^[a-zA-Z0-9][a-zA-Z0-9._:-]{0,119}$/.test(value)) reject(code);
    return value;
  }

  function engineIdentifier(value) {
    // scanner.scan emits rules-v2+llm when its optional summary succeeds.
    // Keep the suffix for exact engine compatibility without relaxing check IDs.
    if (typeof value !== 'string' || !/^[a-zA-Z0-9][a-zA-Z0-9._:+-]{0,119}$/.test(value)) reject('invalid_version');
    return value;
  }

  function boundedNumber(value, code) {
    if (typeof value !== 'number' || !Number.isFinite(value) || value < 0 || value > 100) reject(code);
    return value;
  }

  function url(value) {
    text(value, 'invalid_url', 4096);
    if (value.trim() !== value || !/^https?:\/\//i.test(value) || /[\u0000-\u0020\u007f\\]/.test(value)) reject('invalid_url');
    let parsed;
    try { parsed = new URL(value); } catch (_) { reject('invalid_url'); }
    if (!['http:', 'https:'].includes(parsed.protocol) || !parsed.hostname || parsed.username || parsed.password) reject('invalid_url');
    parsed.hash = '';
    return parsed.href;
  }

  function date(value) {
    text(value, 'invalid_date', 64);
    const match = /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2}):(\d{2})(?:\.\d{1,9})?(Z|[+-]\d{2}:\d{2})$/.exec(value);
    if (!match) reject('invalid_date');
    const [, year, month, day, hour, minute, second, zone] = match;
    const leap = Number(year) % 4 === 0 && (Number(year) % 100 !== 0 || Number(year) % 400 === 0);
    const days = [31, leap ? 29 : 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31];
    if (+month < 1 || +month > 12 || +day < 1 || +day > days[+month - 1] || +hour > 23 || +minute > 59 || +second > 59
      || (zone !== 'Z' && (+zone.slice(1, 3) > 23 || +zone.slice(4, 6) > 59))) reject('invalid_date');
    const timestamp = Date.parse(value);
    if (!Number.isFinite(timestamp)) reject('invalid_date');
    return new Date(timestamp).toISOString();
  }

  function version(value, numeric) {
    if (value === undefined || value === null) return null;
    if (numeric) {
      if (!Number.isSafeInteger(value) || value < 1) reject('invalid_version');
      return value;
    }
    return identifier(value, 'invalid_version');
  }

  /** Return a fresh, compact JSON-safe report. Missing legacy versions stay null. */
  function validateReport(input) {
    const source = record(input);
    if ((own(source, 'demonstration') && source.demonstration !== false) || source.isDemo === true
      || (typeof source.engine === 'string' && /demo|demonstra/i.test(source.engine))) reject('demo_report');
    if (source.scope !== undefined && source.scope !== 'single_page') reject('unsupported_scope');
    const target = url(source.target_url);
    const finalUrl = url(record(source.facts).final_url);
    const rawDomain = text(source.domain, 'invalid_url', 512);
    if (/[\s\/@?#\\]/.test(rawDomain)) reject('invalid_url');
    let domain;
    try { domain = new URL(`${new URL(finalUrl).protocol}//${rawDomain}`).host; } catch (_) { reject('invalid_url'); }
    if (!domain || domain !== new URL(finalUrl).host) reject('invalid_url');
    const scannedAt = date(source.scanned_at);
    const engine = engineIdentifier(source.engine);
    const schemaVersion = version(source.schema_version, true);
    const scoringVersion = version(source.scoring_version, false);
    const sourceScore = record(source.score, 'invalid_score');
    const score = { overall: boundedNumber(sourceScore.overall, 'invalid_score') };
    SCORE_FIELDS.slice(1).forEach((field) => {
      if (own(sourceScore, field)) score[field] = boundedNumber(sourceScore[field], 'invalid_score');
    });
    if (!Array.isArray(source.areas) || source.areas.length < 1 || source.areas.length > AREAS.size) reject('invalid_checks');
    const areaIds = new Set();
    const checkIds = new Set();
    let checkCount = 0;
    const areas = source.areas.map((rawArea) => {
      const area = record(rawArea, 'invalid_checks');
      if (!AREAS.has(area.area) || areaIds.has(area.area) || !Array.isArray(area.checks)) reject('invalid_checks');
      areaIds.add(area.area);
      if (!own(score, area.area)) reject('invalid_score');
      if (own(area, 'score')) boundedNumber(area.score, 'invalid_score');
      checkCount += area.checks.length;
      if (checkCount > 200) reject('too_many_checks');
      return {
        area: area.area,
        label: text(area.label, 'invalid_checks', 500, true) || area.area,
        score: score[area.area],
        checks: area.checks.map((rawCheck) => {
          const check = record(rawCheck, 'invalid_checks');
          const id = identifier(check.id, 'invalid_checks');
          if ((check.area !== undefined && check.area !== area.area) || !STATUSES.has(check.status)) reject('invalid_checks');
          const key = keyFor({ area: area.area, id });
          if (checkIds.has(key)) reject('duplicate_check');
          checkIds.add(key);
          return {
            id, area: area.area,
            label: text(check.label, 'invalid_checks', 500),
            status: check.status,
            weight: check.weight === undefined || check.weight === null ? null : boundedNumber(check.weight, 'invalid_weight'),
            value: text(check.value, 'invalid_checks', 12000, true),
            hint: text(check.hint, 'invalid_checks', 12000, true),
          };
        }),
      };
    });
    if (checkCount < 1) reject('invalid_checks');
    if (!Array.isArray(source.issues)) reject('invalid_issues');
    if (source.issues.length > 200) reject('too_many_issues');
    const issueIds = new Set();
    const issues = source.issues.map((rawIssue) => {
      const issue = record(rawIssue, 'invalid_issues');
      const id = identifier(issue.id, 'invalid_issues');
      if (!AREAS.has(issue.area) || !SEVERITIES.has(issue.severity)) reject('invalid_issues');
      const key = keyFor(issue);
      if (issueIds.has(key)) reject('duplicate_issue');
      if (!checkIds.has(key)) reject('invalid_issues');
      issueIds.add(key);
      return {
        id, area: issue.area, severity: issue.severity,
        title: text(issue.title, 'invalid_issues', 1000),
        detail: text(issue.detail, 'invalid_issues', 12000, true),
        fix: text(issue.fix, 'invalid_issues', 12000, true),
      };
    });
    return {
      target_url: target, domain, scanned_at: scannedAt, engine,
      schema_version: schemaVersion, scoring_version: scoringVersion, scope: 'single_page',
      score, facts: { final_url: finalUrl }, areas, issues,
    };
  }

  function meta(report) {
    return {
      target_url: report.target_url, final_url: report.facts.final_url, domain: report.domain,
      scanned_at: report.scanned_at, engine: report.engine, schema_version: report.schema_version,
      scoring_version: report.scoring_version, score: { ...report.score },
    };
  }

  function indexChecks(report) {
    return new Map(report.areas.flatMap((area) => area.checks).map((check) => [keyFor(check), check]));
  }

  function scoreCompatibility(before, after, oldChecks, newChecks) {
    if (SCORE_FIELDS.some((field) => own(before.score, field) !== own(after.score, field))) return 'score_fields_changed';
    if (before.areas.map((area) => area.area).sort().join() !== after.areas.map((area) => area.area).sort().join()) return 'coverage_changed';
    const all = [...oldChecks.values(), ...newChecks.values()];
    if (all.some((check) => check.weight === null)) return 'weights_missing';
    if ([...oldChecks].some(([key, check]) => newChecks.has(key) && check.weight !== newChecks.get(key).weight)) return 'weights_changed';
    const scored = (checks) => new Map([...checks].filter(([, check]) => check.weight > 0 && ['pass', 'warn', 'fail'].includes(check.status)));
    const oldScored = scored(oldChecks);
    const newScored = scored(newChecks);
    if (!oldScored.size || !newScored.size) return 'no_scored_checks';
    if (oldScored.size !== newScored.size || [...oldScored.keys()].some((key) => !newScored.has(key))) return 'coverage_changed';
    return null;
  }

  /** Compare observed check states, never infer traffic, rankings or citations. */
  function compareReports(beforeInput, afterInput) {
    const before = validateReport(beforeInput);
    const after = validateReport(afterInput);
    const result = {
      compatible: false, reason: null, score_comparable: false, score_reason: null,
      resolved: [], new_issues: [], persistent: [], changed: [], unverified: [],
      counts: { resolved: 0, new_issues: 0, persistent: 0, changed: 0, unverified: 0, worsened: 0, improved: 0 },
      older: meta(before), current: meta(after),
    };
    if (!before.schema_version || !after.schema_version || !before.scoring_version || !after.scoring_version) result.reason = 'missing_version';
    else if (before.schema_version !== after.schema_version || before.schema_version !== 1) result.reason = 'schema_mismatch';
    else if (before.engine !== after.engine) result.reason = 'engine_mismatch';
    else if (before.scoring_version !== after.scoring_version) result.reason = 'scoring_mismatch';
    else if (before.target_url !== after.target_url) result.reason = 'target_mismatch';
    else if (before.facts.final_url !== after.facts.final_url) result.reason = 'redirect_mismatch';
    else if (Date.parse(after.scanned_at) <= Date.parse(before.scanned_at)) result.reason = 'not_newer';
    if (result.reason) return result;
    result.compatible = true;

    const oldChecks = indexChecks(before);
    const newChecks = indexChecks(after);
    const oldIssues = new Map(before.issues.map((issue) => [keyFor(issue), issue]));
    const newIssues = new Map(after.issues.map((issue) => [keyFor(issue), issue]));
    result.score_reason = scoreCompatibility(before, after, oldChecks, newChecks);
    result.score_comparable = result.score_reason === null;
    if (result.score_comparable) {
      result.score_delta = {};
      SCORE_FIELDS.forEach((field) => {
        if (own(before.score, field) && own(after.score, field)) result.score_delta[field] = Math.round((after.score[field] - before.score[field]) * 1000000) / 1000000;
      });
    }

    const keys = new Set([...oldChecks.keys(), ...newChecks.keys()]);
    keys.forEach((key) => {
      const older = oldChecks.get(key) || null;
      const current = newChecks.get(key) || null;
      const source = current || older;
      const entry = {
        id: source.id, area: source.area, label: source.label,
        before: older, after: current, before_issue: oldIssues.get(key) || null,
        after_issue: newIssues.get(key) || null, change: 'unchanged', reason: null,
      };
      if (problem(older)) {
        if (current?.status === 'pass') {
          entry.change = 'resolved';
          result.resolved.push(entry);
        } else if (problem(current)) {
          entry.change = older.status === current.status ? 'persistent' : current.status === 'fail' ? 'worsened' : 'improved';
          result.persistent.push(entry);
        } else {
          entry.change = 'unverified';
          entry.reason = !current ? 'check_missing' : current.status === 'info' ? 'not_scored' : 'unknown_status';
          result.unverified.push(entry);
        }
      } else if (problem(current)) {
        if (older?.status === 'pass') {
          entry.change = 'new_issue';
          result.new_issues.push(entry);
        } else {
          // A missing or unscored baseline cannot establish a newly introduced issue.
          entry.change = 'unverified';
          entry.reason = !older ? 'check_missing_before' : older.status === 'info' ? 'previous_not_scored' : 'previous_unknown';
          result.unverified.push(entry);
        }
      } else if (older?.status !== current?.status) entry.change = 'status_changed';
      if (older?.status !== current?.status) result.changed.push(entry);
    });
    ['resolved', 'new_issues', 'persistent', 'changed', 'unverified'].forEach((name) => { result.counts[name] = result[name].length; });
    result.counts.worsened = result.changed.filter((entry) => entry.change === 'worsened').length;
    result.counts.improved = result.changed.filter((entry) => entry.change === 'improved').length;
    return result;
  }

  return Object.freeze({ validateReport, compareReports });
});
