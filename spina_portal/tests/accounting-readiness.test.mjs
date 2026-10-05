import assert from 'node:assert/strict';
import test from 'node:test';
import { mountAccountingReadiness } from '../assets/management-general-journal.js';
import { mountManagementAccounting } from '../assets/management-accounting.js';
import { financialStatementsMarkup } from '../assets/management-financial-statements.js';
import { Element, fire } from './helpers/dom.mjs';

const base = '/api/v1/management/financial-accounting';
const period = '00000000-0000-4000-8000-000000000001';
const tick = () => new Promise((resolve) => setImmediate(resolve));
const configured = { book: { status: 'configured', book_id: period, kind: 'owner_operations', entity_label: 'Owner <private> operations' } };
const coverage = (reason = 'Mapping requires review') => ({ source_coverage: {
  fiscal_period_id: period,
  comprehensive_source_coverage: false, source_families: ['treasury', 'collector'],
  limit: 100, offset: 0, blocker_count: 1,
  blockers: [{ source_type: 'treasury_receipt', source_id: 'source-private', effective_date: '2026-09-30', amount: '90071992547409.93', reason }],
} });

test('book identity and posted-ledger scope never imply complete accounting readiness', async () => {
  const root = new Element(); const calls = [];
  const dispose = mountAccountingReadiness({ root, api: { async request(path, options) { calls.push({ path, options }); return configured; } } });
  await tick();
  assert.equal(calls[0].path, `${base}/book`);
  assert.ok(calls[0].options.signal instanceof AbortSignal);
  assert.match(root.textContent, /Owner operations/);
  assert.match(root.innerHTML, /Owner &lt;private&gt; operations/);
  assert.match(root.textContent, /Immutable book identity/);
  assert.match(root.textContent, /posted ledger only/i);
  assert.match(root.textContent, /does not establish accounting readiness/i);
  dispose(); assert.equal(root.textContent, '');
});

test('unconfigured identity is explicit and failed reads are not called unconfigured', async () => {
  const root = new Element();
  const dispose = mountAccountingReadiness({ root, api: { async request() { return { book: { status: 'unconfigured', book_id: null, kind: null, entity_label: null } }; } } });
  await tick(); assert.match(root.textContent, /Book identity is unconfigured/); dispose();
  mountAccountingReadiness({ root, api: { async request() { throw Object.assign(new Error('Denied'), { status: 403 }); } } });
  await tick(); assert.match(root.textContent, /Accounting access is unavailable/); assert.doesNotMatch(root.textContent, /unconfigured/);
});

test('period blockers preserve exact evidence and expose partial coverage even with no blockers', async () => {
  const root = new Element(); const calls = [];
  const dispose = mountAccountingReadiness({ root, periodId: period, showBook: false, api: { async request(path) { calls.push(path); return coverage('Unmapped <source>'); } } });
  await tick();
  assert.deepEqual(calls, [`${base}/period-close/${period}/source-blockers`]);
  assert.match(root.textContent, /Treasury, Collector/);
  assert.match(root.textContent, /Partial source coverage/);
  assert.match(root.textContent, /source-private/);
  assert.match(root.textContent, /90,071,992,547,409\.93/);
  assert.match(root.innerHTML, /Unmapped &lt;source&gt;/);
  dispose();
  mountAccountingReadiness({ root, periodId: period, showBook: false, api: { async request() { return { source_coverage: { ...coverage().source_coverage, blockers: [], blocker_count: 0 } }; } } });
  await tick(); assert.match(root.textContent, /No blockers returned for these source families/); assert.match(root.textContent, /does not certify readiness/);
});

test('restricted blockers remain counted without exposing private identifiers or amounts', async () => {
  const root = new Element();
  mountAccountingReadiness({ root, periodId: period, showBook: false, api: { async request() { return { source_coverage: { ...coverage().source_coverage, blocker_count: 120, blockers: [{ source_type: 'restricted_source', source_id: null, effective_date: null, amount: null, reason: 'treasury_account_access_required' }] } }; } } });
  await tick();
  assert.match(root.textContent, /Restricted source — Treasury account access required/);
  assert.match(root.textContent, /Showing 1–1 of 120 source blockers/);
  assert.match(root.textContent, /full blocker inventory is not shown/);
  assert.doesNotMatch(root.textContent, /Source reference|PHP|2026-09-30|null|No blockers returned/);
});

test('missing optional source amount remains a blocker and is never displayed as zero', async () => {
  const root = new Element(); const payload = coverage(); payload.source_coverage.blockers[0].amount = null;
  mountAccountingReadiness({ root, periodId: period, showBook: false, api: { async request() { return payload; } } });
  await tick(); assert.match(root.textContent, /Amount unavailable/); assert.match(root.textContent, /source-private/); assert.doesNotMatch(root.textContent, /0\.00/);
});

test('source coverage for a different period is rejected', async () => {
  const root = new Element(); const payload = coverage(); payload.source_coverage.fiscal_period_id = '00000000-0000-4000-8000-000000000002';
  mountAccountingReadiness({ root, periodId: period, showBook: false, api: { async request() { return payload; } } });
  await tick(); assert.match(root.textContent, /Source coverage is unavailable/); assert.doesNotMatch(root.textContent, /source-private/);
});

test('remount and session abort discard late private source rows', async () => {
  const root = new Element(); let finish;
  const old = mountAccountingReadiness({ root, periodId: period, showBook: false, api: { request() { return new Promise((resolve) => { finish = resolve; }); } } });
  const controller = new AbortController();
  mountAccountingReadiness({ root, signal: controller.signal, api: { async request() { return configured; } } });
  await tick(); finish(coverage()); await tick();
  assert.doesNotMatch(root.textContent, /source-private/); old(); assert.match(root.textContent, /Immutable book identity/);
  controller.abort(); assert.equal(root.textContent, '');
});

test('malformed source coverage cannot become an empty successful check', async () => {
  const root = new Element();
  mountAccountingReadiness({ root, periodId: period, showBook: false, api: { async request() { return { source_coverage: { comprehensive_source_coverage: false, source_families: ['treasury'] } }; } } });
  await tick(); assert.match(root.textContent, /Source coverage is unavailable/); assert.doesNotMatch(root.textContent, /No blockers returned/);
});

test('balanced financial statements retain the posted-ledger readiness limitation', () => {
  const markup = financialStatementsMarkup({ statements: { source: 'posted_general_ledger_only', period: {}, profit_or_loss: {}, financial_position: { balanced: true } } });
  assert.match(markup, /posted ledger only/);
  assert.match(markup, /does not establish accounting readiness/);
});

test('period-close source review uses the selected period and discards rows after workflow change', async () => {
  const root = new Element(); const calls = []; let complete;
  const dispose = await mountManagementAccounting({ root,
    session: { user: { role: 'Management', roles: ['management'] }, permissions: ['accounting.view'] },
    api: { async request(path) {
      calls.push(path);
      if (path.endsWith('/book')) return configured;
      if (path.endsWith('/source-blockers')) return new Promise((resolve) => { complete = resolve; });
      if (path.endsWith('/period-close')) return { items: [{ fiscal_period_id: period, label: 'September', close_status: 'blocked' }] };
      return { fiscal_periods: [], accounts: [] };
    } },
  });
  fire(root.querySelector('[data-accounting-tab="close"]'), 'click'); await tick();
  fire(root.querySelector('[data-close-sources="0"]'), 'click'); await tick();
  assert.ok(calls.includes(`${base}/period-close/${period}/source-blockers`));
  fire(root.querySelector('[data-accounting-tab="periods"]'), 'click'); await tick();
  complete(coverage()); await tick();
  assert.doesNotMatch(root.textContent, /source-private/); dispose();
});
