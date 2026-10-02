import assert from 'node:assert/strict';
import test from 'node:test';
import {setImmediate} from 'node:timers/promises';
import {Element, fire} from './helpers/dom.mjs';
import {mountManagementPortfolio} from '../assets/management-portfolio.js';
import {bindStaffDevices} from '../assets/roles/management.js';
import {managementAlertsAuditMarkup, bindManagementAlertsAudit} from '../assets/management-alerts-audit.js';
import {mountManagementFinancialStatements} from '../assets/management-financial-statements.js';

const id = number => `40000000-0000-4000-8000-${String(number).padStart(12, '0')}`;
const session = {user: {id: id(900), role: 'management'}, permissions: ['accounting.view', 'device.manage']};
const summary = {active_client_count: 75, active_loan_count: 150, active_remaining_total: '123456.78', overdue_active_count: 3};
const loan = number => ({loan_id: id(number), client_id: id(1000 + number), client_name: 'Same synthetic name',
  loan_number: `SYNTHETIC-${number}`, loan_status: 'active', client_status: 'active', principal: '1000.00',
  remaining_balance: '750.25', daily_amount: '25.00', paid_amount: '249.75', paid_percent: '24.98'});
const query = path => new URL(path, 'https://synthetic.invalid').searchParams;
const visible = (root, selector) => root.querySelectorAll(selector).filter(node => node.getAttribute('hidden') === null);
const click = async (root, selector) => {const button = root.querySelector(selector); assert.ok(button, selector); fire(button, 'click'); await setImmediate();};

test('Task5A failed page two retries its exact query/status/offset, then Previous returns to page one', async t => {
  const root = new Element(), calls = [];
  let failSecond = true;
  const handle = mountManagementPortfolio({root, getSession: () => session, api: {async request(path, options = {}) {
    calls.push({path, options}); const offset = Number(query(path).get('offset'));
    if (offset === 100 && failSecond) throw new Error('Synthetic page-two read unavailable');
    return {summary, loans: Array.from({length: offset === 0 ? 100 : 50}, (_, index) => loan(offset + index + 1))};
  }}});
  t.after(() => handle.dispose());
  const search = root.querySelector('[name="query"]'), status = root.querySelector('[name="status"]');
  search.value = 'same borrower & area'; status.value = 'paid'; await handle.refresh();
  assert.equal(root.querySelectorAll('[data-portfolio-open]').length, 100);
  await click(root, '[data-portfolio-next]');
  assert.equal(query(calls.at(-1).path).get('offset'), '100', 'This is a genuine page-two failure');
  assert.match(root.textContent, /Portfolio summary unavailable/);
  assert.equal(root.querySelector('[data-portfolio-previous]').disabled, false);
  assert.equal(root.querySelector('[data-portfolio-retry]').hidden, false);
  const failedPath = calls.at(-1).path;
  failSecond = false; await click(root, '[data-portfolio-retry]');
  assert.equal(calls.at(-1).path, failedPath, 'Retry does not jump back to page one or erase filters');
  assert.equal(root.querySelector('[name="query"]'), search);
  assert.equal(root.querySelector('[name="status"]'), status);
  assert.equal(search.value, 'same borrower & area'); assert.equal(status.value, 'paid');
  assert.equal(root.querySelectorAll('[data-portfolio-open]').length, 50);
  assert.match(root.querySelector('[data-portfolio-page]').textContent, /Page 2.*50 returned/);
  assert.match(root.querySelector('[data-portfolio-summary]').textContent, /123,456\.78/);
  await click(root, '[data-portfolio-previous]');
  assert.equal(query(calls.at(-1).path).get('offset'), '0');
  assert.equal(query(calls.at(-1).path).get('q'), 'same borrower & area');
  assert.equal(query(calls.at(-1).path).get('status'), 'paid');
  assert.equal(root.querySelectorAll('[data-portfolio-open]').length, 100);
  assert.ok(calls.every(call => !call.options.method || call.options.method === 'GET'));
});

test('Task5A an empty next page remains recoverable, and a changed status restarts at offset zero', async t => {
  const root = new Element(), calls = [];
  const handle = mountManagementPortfolio({root, getSession: () => session, api: {async request(path) {
    calls.push(path);
    return {summary, loans: query(path).get('offset') === '0' ? Array.from({length: 100}, (_, i) => loan(i + 1)) : []};
  }}});
  t.after(() => handle.dispose());
  await handle.refresh(); await click(root, '[data-portfolio-next]');
  assert.match(root.querySelector('[data-portfolio-page]').textContent, /Page 2.*0 returned/);
  assert.match(root.querySelector('#management-loan-results').textContent, /No loan matches/);
  assert.equal(root.querySelector('[data-portfolio-next]').disabled, true);
  assert.equal(root.querySelector('[data-portfolio-previous]').disabled, false);
  assert.match(root.querySelector('[data-portfolio-summary]').textContent, /123,456\.78/);
  await click(root, '[data-portfolio-previous]');
  assert.equal(root.querySelectorAll('[data-portfolio-open]').length, 100);
  await click(root, '[data-portfolio-next]');
  root.querySelector('[name="status"]').value = 'all';
  fire(root.querySelector('#management-loan-search'), 'submit'); await setImmediate();
  assert.equal(query(calls.at(-1)).get('status'), 'all');
  assert.equal(query(calls.at(-1)).get('offset'), '0');
  assert.equal(root.querySelector('[data-portfolio-previous]').disabled, true);
});

test('Task5A exact loan detail distinguishes missing facts from explicit zeros and clears a removed record', async t => {
  const root = new Element(); let removed = false;
  const selected = {...loan(1), principal: null, remaining_balance: '0.00', daily_amount: null,
    paid_amount: '0.00', paid_percent: '0.00', pass_count: 0, payment_count: null};
  const handle = mountManagementPortfolio({root, getSession: () => session, api: {async request() {
    return {summary, loans: removed ? [loan(2)] : [selected, loan(2)]};
  }}});
  t.after(() => handle.dispose());
  await handle.refresh(); await click(root, `[data-portfolio-open="${selected.loan_id}"]`);
  const detail = root.querySelector('[data-portfolio-detail]');
  const facts = new Map(detail.querySelectorAll('.detail-item').map(node => [node.querySelector('span').textContent, node.querySelector('strong').textContent]));
  assert.equal(facts.get('Principal'), '—'); assert.equal(facts.get('Agreed daily amount'), '—');
  assert.equal(facts.get('Official balance'), '₱0.00'); assert.equal(facts.get('Paid amount'), '₱0.00');
  assert.equal(facts.get('Paid percentage'), '0.00%'); assert.equal(facts.get('PASS count'), '0');
  assert.equal(facts.get('Payment count'), '—');
  assert.match(detail.textContent, /SYNTHETIC-1/); assert.doesNotMatch(detail.textContent, /SYNTHETIC-2/);
  removed = true; await handle.refresh();
  assert.equal(detail.hidden, true); assert.equal(detail.innerHTML, '');
  assert.equal(root.querySelector(`[data-portfolio-open="${selected.loan_id}"]`), null);
});

test('Task6 filtered Pending actions use original device IDs and preserve an explicitly empty Pending filter', async t => {
  const root = new Element(), account = {id: id(700), full_name: 'Synthetic Staff', roles: ['employee']}, calls = [];
  const devices = Array.from({length: 36}, (_, index) => ({id: id(710 + index), status: [12, 29].includes(index) ? 'pending' : 'active', platform: 'web'}));
  root.innerHTML = `<h2 data-management-staff-heading></h2><button data-manage-staff-id="${account.id}">Manage devices</button><div id="management-staff-device-detail" hidden></div>`;
  const previousConfirm = globalThis.confirm; globalThis.confirm = () => true;
  t.after(() => {globalThis.confirm = previousConfirm;});
  const context = {root, session, api: {async request(path, options = {}) {
    calls.push({path, options});
    if (options.method === 'PATCH') {
      const target = devices.find(device => path === `/api/v1/management/devices/${device.id}/status`);
      assert.ok(target, 'The mutation must address an original server device identity');
      target.status = options.body.status; return {device: {...target}};
    }
    assert.equal(path, `/api/v1/management/accounts/${account.id}/devices`);
    return {devices: structuredClone(devices)};
  }}};
  const cleanup = bindStaffDevices(context, [account]); t.after(cleanup);
  await click(root, '[data-manage-staff-id]');
  const panel = root.querySelector('#management-staff-device-detail');
  await click(panel, '[data-managed-device-filter="pending"]');
  const visiblePending = visible(panel, '[data-managed-device-status]');
  assert.equal(visiblePending.length, 2);
  fire(visiblePending[1].querySelector('.managed-device-action'), 'click'); await setImmediate();
  const firstWrite = calls.find(call => call.options.method === 'PATCH');
  assert.equal(firstWrite.path, `/api/v1/management/devices/${id(739)}/status`);
  assert.deepEqual(firstWrite.options.body, {status: 'active'});
  assert.equal(visible(panel, '[data-managed-device-status]').length, 1);
  fire(visible(panel, '[data-managed-device-status]')[0].querySelector('.managed-device-action'), 'click'); await setImmediate();
  const writes = calls.filter(call => call.options.method === 'PATCH');
  assert.deepEqual(writes.map(call => call.path), [id(739), id(722)].map(device => `/api/v1/management/devices/${device}/status`));
  assert.equal(context.staffDeviceFilters.get(account.id).filter, 'pending');
  assert.equal(panel.querySelector('[data-managed-device-filter="pending"]').getAttribute('aria-pressed'), 'true');
  assert.equal(visible(panel, '[data-managed-device-status]').length, 0);
  assert.equal(panel.querySelector('[data-managed-device-filter-empty]').getAttribute('hidden'), null);
  assert.match(panel.querySelector('[data-managed-device-visible]').textContent, /0 visible.*0 matching.*36 loaded/);
  await click(panel, '[data-managed-device-filter="all"]');
  assert.equal(visible(panel, '[data-managed-device-status]').length, 10);
});

for (const size of [0, 12, 100]) {
  test(`Task6 audit ${size} keeps distinct same-title events in server order through complete loaded expansion`, t => {
    const root = new Element();
    const events = Array.from({length: size}, (_, index) => ({event_key: `synthetic-event-${index}`, title: 'Repeated title',
      domain: index === size - 1 ? 'unknown_domain' : 'approvals', occurred_at: '2026-10-03T01:00:00Z',
      severity: 'warning', actor_name: 'Synthetic Maker', checker_name: 'Synthetic Checker', reason: `Reason ${index}`}));
    root.innerHTML = managementAlertsAuditMarkup({window_days: 30, limit: 100, event_total_count: size + 50,
      visible_domains: ['approvals'], alerts: [], events});
    const cleanup = bindManagementAlertsAudit(root); t.after(cleanup);
    assert.equal(visible(root, '[data-audit-event-key]').length, Math.min(10, size));
    const more = root.querySelector('[data-audit-more]');
    for (let step = 10; step < size; step += 10) fire(more, 'click');
    assert.deepEqual(visible(root, '[data-audit-event-key]').map(node => node.getAttribute('data-audit-event-key')), events.map(event => event.event_key));
    assert.equal(more.hidden, true);
    assert.match(root.textContent, new RegExp(`${size + 50} authorized events`));
    assert.match(root.querySelector('[data-audit-visible]').textContent, new RegExp(`${size} loaded events`));
    if (!size) assert.match(root.textContent, /No audit events in this snapshot/);
    if (size) {
      const last = root.querySelectorAll('[data-audit-event-key]').at(-1);
      assert.match(last.textContent, /Maker: Synthetic Maker/); assert.match(last.textContent, /Checker: Synthetic Checker/);
      assert.match(last.textContent, new RegExp(`Reason ${size - 1}`));
      fire(root.querySelector('[data-alert-domain-filter="approvals"]'), 'click');
      assert.equal(visible(root, '[data-audit-event-key]').length, Math.min(10, size - 1));
      assert.equal(root.querySelectorAll('[data-audit-event-key]').length, size, 'Filtering never discards loaded evidence');
      fire(root.querySelector('[data-alert-domain-filter="all"]'), 'click');
      assert.equal(visible(root, '[data-audit-event-key]').length, Math.min(10, size));
    }
  });
}

const PERIOD_A = id(800), PERIOD_B = id(801);
const periods = [{period_id: PERIOD_A, label: 'Synthetic August', status: 'closed'}, {period_id: PERIOD_B, label: 'Synthetic September', status: 'open'}];
function statementPack(periodId) {
  const first = periodId === PERIOD_A;
  return {statements: {
    period: {...periods[first ? 0 : 1], start_date: first ? '2026-08-01' : '2026-09-01', end_date: first ? '2026-08-31' : '2026-09-30'},
    source: 'posted_general_ledger_only',
    profit_or_loss: {income_lines: [], expense_lines: [], total_income: first ? '100.01' : '90071992547409.91',
      total_expenses: first ? '223.46' : '0.00', net_income: first ? '-123.45' : '90071992547409.91'},
    financial_position: {asset_lines: [], liability_lines: [], equity_lines: [], total_assets: first ? '876.55' : '90071992547409.91',
      total_liabilities: '0.00', recorded_equity: first ? '1000.00' : '0.00', unclosed_earnings_to_date: first ? '-123.45' : '90071992547409.91',
      total_equity: first ? '876.55' : '90071992547409.91', total_liabilities_and_equity: first ? '876.55' : '90071992547409.91', balanced: true},
  }};
}

test('Task7A period switching displays distinct exact totals, negative income and server period status using GET only', async t => {
  const root = new Element(), calls = [];
  const handle = mountManagementFinancialStatements({root, getSession: () => session, api: {async request(path, options = {}) {
    calls.push({path, options});
    if (path.endsWith('/financial-accounting')) return {fiscal_periods: periods};
    return statementPack(query(path).get('period_id') || PERIOD_A);
  }}}); t.after(() => handle.dispose());
  await handle.refresh(); const select = root.querySelector('[data-statement-period]'), results = root.querySelector('[data-statement-results]');
  assert.equal(select.value, PERIOD_A); assert.match(results.textContent, /Synthetic August/);
  assert.match(results.textContent, /-₱123\.45/); assert.match(results.textContent, /₱876\.55/);
  assert.match(results.textContent, /closed/); assert.match(results.textContent, /Posted General Ledger only/);
  select.value = PERIOD_B; fire(select, 'change'); await setImmediate();
  assert.match(results.textContent, /Synthetic September/);
  assert.match(results.textContent, /₱90,071,992,547,409\.91/);
  assert.doesNotMatch(results.textContent, /-₱123\.45|Synthetic August/);
  assert.match(results.textContent, /Open period.*provisional/i);
  assert.ok(calls.every(({options}) => !options.method || options.method === 'GET'));
  assert.equal(calls.at(-1).path, `/api/v1/management/financial-accounting/statements?period_id=${PERIOD_B}`);
});

test('Task7A no-period is distinct from a failed period read; Retry preserves selection and never creates a period', async t => {
  const root = new Element(), calls = []; let mode = 'empty';
  const handle = mountManagementFinancialStatements({root, getSession: () => session, api: {async request(path, options = {}) {
    calls.push({path, options});
    if (path.endsWith('/financial-accounting')) {
      if (mode === 'failure') throw new Error('Synthetic periods unavailable');
      return {fiscal_periods: mode === 'empty' ? [] : periods};
    }
    if (mode === 'statement-failure') throw new Error('Synthetic statement unavailable');
    return statementPack(query(path).get('period_id') || PERIOD_A);
  }}}); t.after(() => handle.dispose());
  const results = root.querySelector('[data-statement-results]'), retry = root.querySelector('[data-statement-retry]');
  await handle.refresh(); assert.match(results.textContent, /No accounting period is available/);
  assert.equal(retry.hidden, true); assert.equal(calls.length, 1);
  mode = 'failure'; await handle.refresh();
  assert.match(results.textContent, /Synthetic periods unavailable/);
  assert.doesNotMatch(results.textContent, /No accounting period/); assert.equal(retry.hidden, false);
  mode = 'ready'; await click(root, '[data-statement-retry]');
  const select = root.querySelector('[data-statement-period]'); select.value = PERIOD_B;
  mode = 'statement-failure'; fire(select, 'change'); await setImmediate();
  assert.equal(select.value, PERIOD_B); assert.match(results.textContent, /Synthetic statement unavailable/);
  assert.doesNotMatch(results.textContent, /Synthetic August|₱100\.01/); assert.equal(retry.hidden, false);
  mode = 'ready'; await click(root, '[data-statement-retry]');
  assert.equal(root.querySelector('[data-statement-period]'), select); assert.equal(select.value, PERIOD_B);
  assert.match(results.textContent, /Synthetic September/); assert.equal(retry.hidden, true);
  assert.ok(calls.every(({options}) => !options.method || options.method === 'GET'));
});
