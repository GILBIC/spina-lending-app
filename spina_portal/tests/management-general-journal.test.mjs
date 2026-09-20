import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';

import { availableRoleActions } from '../assets/roles.js';
import { SpinaApi } from '../assets/api.js';
import { mountManagementWorkspace } from '../assets/roles/management.js';
import { Element, fire } from './helpers/dom.mjs';

const managementSource = await readFile(
  new URL('../assets/roles/management.js', import.meta.url),
  'utf8',
);
const serviceWorkerSource = await readFile(
  new URL('../sw.js', import.meta.url),
  'utf8',
);

async function importJournalModule() {
  try {
    return await import('../assets/management-general-journal.js');
  } catch {
    return {};
  }
}

test('Management General Journal requires accounting.view and stays read-only in Web', () => {
  const withoutAccounting = availableRoleActions('management', [
    'management.dashboard.view',
  ]);
  const withAccounting = availableRoleActions('management', [
    'management.dashboard.view',
    'accounting.view',
    'accounting.journal.manage',
  ]);
  const employee = availableRoleActions('employee', ['accounting.view']);
  const collector = availableRoleActions('collector', ['accounting.view']);

  assert.equal(
    withoutAccounting.some((entry) => entry.key === 'management-general-journal'),
    false,
  );

  const action = withAccounting.find(
    (entry) => entry.key === 'management-general-journal',
  );

  assert.ok(action);
  assert.equal(
    action.path,
    '/api/v1/management/financial-accounting/journals',
  );
  assert.equal(action.permission, 'accounting.view');
  assert.equal(Object.hasOwn(action, 'method'), false);
  assert.equal(Object.hasOwn(action, 'financial'), false);

  assert.equal(
    employee.some((entry) => entry.path.includes('/financial-accounting/journals')),
    false,
  );
  assert.equal(
    collector.some((entry) => entry.path.includes('/financial-accounting/journals')),
    false,
  );
});

test('General Journal loaders use only the existing protected read endpoints', async () => {
  const journal = await importJournalModule();
  assert.equal(typeof journal.loadManagementGeneralJournal, 'function');
  assert.equal(typeof journal.loadManagementTrialBalance, 'function');

  const calls = [];
  const api = {
    async request(path, options = {}) {
      calls.push({ path, options });
      if (path.endsWith('/journals')) {
        return {
          entries: [],
          can_manage: true,
          automatic_loan_posting_enabled: false,
        };
      }
      return {
        trial_balance: {
          period_id: 'period-1',
          period_label: 'September 2026',
          total_debits: '1.00',
          total_credits: '1.00',
          balanced: true,
          lines: [],
        },
      };
    },
  };

  const journals = await journal.loadManagementGeneralJournal(api);
  const trialBalance = await journal.loadManagementTrialBalance(api);

  assert.equal(journals.can_manage, true);
  assert.equal(trialBalance.trial_balance.period_label, 'September 2026');
  assert.deepEqual(calls, [
    {
      path: '/api/v1/management/financial-accounting/journals',
      options: {},
    },
    {
      path: '/api/v1/management/financial-accounting/trial-balance',
      options: {},
    },
  ]);
});

test('General Journal markup renders authoritative server values and no mutation controls', async () => {
  const journal = await importJournalModule();
  assert.equal(typeof journal.managementGeneralJournalMarkup, 'function');

  const markup = journal.managementGeneralJournalMarkup({
    journals: {
      entries: [
        {
          entry_id: 'entry-1',
          entry_number: 'GJ-2026-001',
          period_id: 'period-1',
          period_label: 'September 2026',
          posting_date: '2026-09-12',
          description: 'Server <journal> & evidence',
          status: 'posted',
          source_type: 'manual',
          source_reference: 'REF-1',
          reversal_of_entry_id: null,
          created_by_name: 'Manager <One>',
          posted_by_name: 'Manager & Two',
          created_at: '2026-09-12T09:00:00+08:00',
          posted_at: '2026-09-12T09:05:00+08:00',
          total_debit: '987.65',
          total_credit: '987.65',
          lines: [
            {
              line_number: 1,
              account_code: '1100',
              account_name: 'Cash <Main>',
              description: 'Debit line',
              debit: '11.00',
              credit: '0.00',
            },
            {
              line_number: 2,
              account_code: '4100',
              account_name: 'Interest & Fees',
              description: 'Credit line',
              debit: '0.00',
              credit: '22.00',
            },
          ],
        },
      ],
      can_manage: true,
      automatic_loan_posting_enabled: false,
    },
    trialBalance: {
      trial_balance: {
        period_id: 'period-1',
        period_label: 'September 2026',
        total_debits: '7777.00',
        total_credits: '6666.00',
        balanced: false,
        lines: [
          {
            account_code: '1100',
            account_name: 'Cash <Main>',
            account_type: 'asset',
            normal_balance: 'debit',
            total_debit: '44.00',
            total_credit: '0.00',
            debit_balance: '55.00',
            credit_balance: '0.00',
          },
        ],
      },
    },
  });

  assert.match(markup, /GJ-2026-001/);
  assert.match(markup, /September 2026/);
  assert.match(markup, /987\.65/);
  assert.match(markup, /7,777\.00/);
  assert.match(markup, /6,666\.00/);
  assert.match(markup, /Server &lt;journal&gt; &amp; evidence/);
  assert.match(markup, /Manager &lt;One&gt;/);
  assert.match(markup, /Manager &amp; Two/);
  assert.match(markup, /Cash &lt;Main&gt;/);
  assert.match(markup, /Interest &amp; Fees/);
  assert.doesNotMatch(markup, />33\.00</);
  assert.doesNotMatch(markup, />99\.00</);
  assert.doesNotMatch(markup, /Create journal|Edit journal|Post journal|Reverse journal|Cancel draft/i);
});

test('Management workspace mounts the isolated General Journal and Trial Balance read-only surface', () => {
  assert.match(managementSource, /management-general-journal\.js/);
  assert.match(managementSource, /loadManagementGeneralJournal/);
  assert.match(managementSource, /loadManagementTrialBalance/);
  assert.match(managementSource, /managementGeneralJournalMarkup/);
  assert.match(managementSource, /id="management-general-journal"/);
  assert.match(managementSource, /hasPermission\(session, 'accounting\.view'\)/);
  assert.doesNotMatch(managementSource, /accounting\.journal\.manage/);
});

test('installed Web shell precaches the isolated Management General Journal dependency', () => {
  assert.match(
    serviceWorkerSource,
    /'\/assets\/management-general-journal\.js'/,
  );
});

const tick = () => new Promise((resolve) => setImmediate(resolve));

async function exportHarness(t, request) {
  const journal = await importJournalModule();
  assert.equal(typeof journal.bindManagementAccountingExport, 'function');
  const root = new Element();
  root.innerHTML = journal.managementGeneralJournalMarkup();
  const downloads = [];
  const created = [];
  const revoked = [];
  const originalDocument = globalThis.document;
  globalThis.document = {
    createElement(tag) {
      assert.equal(tag, 'a');
      return { click() { downloads.push({ href: this.href, filename: this.download }); } };
    },
  };
  t.after(() => { globalThis.document = originalDocument; });
  t.mock.method(URL, 'createObjectURL', (blob) => {
    created.push(blob);
    return `blob:accounting-${created.length}`;
  });
  t.mock.method(URL, 'revokeObjectURL', (url) => revoked.push(url));
  const controller = new AbortController();
  const context = { root, api: { request }, signal: controller.signal };
  const dispose = journal.bindManagementAccountingExport(context);
  t.after(dispose);
  const form = root.querySelector('[data-accounting-export]');
  const start = form.querySelector('[name="start_date"]');
  const end = form.querySelector('[name="end_date"]');
  const button = form.querySelector('button');
  const status = root.querySelector('[data-accounting-export-status]');
  start.value = '2026-09-01';
  end.value = '2026-09-20';
  return { root, form, start, end, button, status, downloads, created, revoked, dispose, context, controller };
}

test('accounting export downloads the exact date scope through the authenticated device session', async (t) => {
  let respond;
  const requests = [];
  const api = new SpinaApi({
    sessionStore: {
      load: () => ({ access_token: 'synthetic-session' }),
      deviceId: () => 'synthetic-approved-device',
    },
    fetchImpl: (url, init) => {
      requests.push({ url, init });
      return new Promise((resolve) => { respond = resolve; });
    },
  });
  const h = await exportHarness(t, api.request.bind(api));
  h.start.value = '2024-01-01';
  h.end.value = '2024-12-31';
  const event = fire(h.form, 'submit');
  fire(h.form, 'submit');
  assert.equal(event.defaultPrevented, true);
  assert.equal(requests.length, 1);
  assert.equal(requests[0].url, '/api/v1/management/financial-accounting/export?start_date=2024-01-01&end_date=2024-12-31');
  assert.equal(requests[0].init.method, 'GET');
  assert.equal(requests[0].init.headers.Authorization, 'Bearer synthetic-session');
  assert.equal(requests[0].init.headers['X-Device-Id'], 'synthetic-approved-device');
  assert.equal(requests[0].init.cache, 'no-store');
  assert.equal(h.button.disabled, true);
  assert.equal(h.start.disabled, true);
  assert.equal(h.end.disabled, true);
  respond(new Response(new Blob(['zip bytes'], { type: 'application/zip' })));
  await tick();
  assert.equal(h.created.length, 1);
  assert.equal(await h.created[0].text(), 'zip bytes');
  assert.deepEqual(h.downloads, [{ href: 'blob:accounting-1', filename: 'spina-accounting-2024-01-01-to-2024-12-31.zip' }]);
  assert.equal(h.button.disabled, false);
  assert.equal(h.start.disabled, false);
  assert.match(h.status.textContent, /review copy.*download/i);
  assert.match(h.root.textContent, /BIR registration.*SAF/i);
  h.dispose();
  assert.deepEqual(h.revoked, ['blob:accounting-1']);
});

test('accounting export rejects missing, impossible, reversed and overlong dates before requesting', async (t) => {
  let calls = 0;
  const h = await exportHarness(t, async () => { calls += 1; });
  for (const [start, end] of [
    ['', '2026-09-01'], ['2026-02-30', '2026-03-01'], ['0000-01-01', '0000-01-01'],
    ['2026-09-20', '2026-09-01'], ['2024-01-01', '2025-01-01'], ['2026-9-1', '2026-09-20'],
  ]) {
    h.start.value = start;
    h.end.value = end;
    fire(h.form, 'submit');
    await tick();
    assert.equal(calls, 0);
    assert.match(h.status.textContent, /valid dates|366 days/i);
    assert.equal(h.button.disabled, false);
  }
});

test('accounting export accepts a single inclusive day', async (t) => {
  const paths = [];
  const h = await exportHarness(t, async (path) => {
    paths.push(path);
    return new Blob(['zip'], { type: 'application/zip' });
  });
  h.end.value = h.start.value;
  fire(h.form, 'submit');
  await tick();
  assert.deepEqual(paths, ['/api/v1/management/financial-accounting/export?start_date=2026-09-01&end_date=2026-09-01']);
  assert.equal(h.downloads.length, 1);
});

test('accounting export surfaces bounded server failures without downloading error payloads', async (t) => {
  let status = 413;
  const h = await exportHarness(t, async () => { throw Object.assign(new Error('<private error>'), { status }); });
  for (const [code, message] of [[413, /smaller date range/i], [409, /accounting records.*review/i], [503, /try again/i], [422, /valid dates|366 days/i], [0, /connection/i]]) {
    status = code;
    fire(h.form, 'submit');
    await tick();
    assert.match(h.status.textContent, message);
    assert.doesNotMatch(h.status.textContent, /private error/);
    assert.equal(h.status.getAttribute('role'), 'alert');
    assert.equal(h.button.disabled, false);
    assert.equal(h.downloads.length, 0);
  }
});

for (const code of [401, 403]) {
  test(`accounting export stops further requests after access failure ${code}`, async (t) => {
    let calls = 0;
    const h = await exportHarness(t, async () => { calls += 1; throw Object.assign(new Error('denied'), { status: code }); });
    fire(h.form, 'submit');
    await tick();
    fire(h.form, 'submit');
    await tick();
    assert.equal(calls, 1);
    assert.equal(h.button.disabled, true);
    assert.match(h.status.textContent, /sign in|access/i);
    assert.equal(h.created.length, 0);
  });
}

test('accounting export refuses empty or non-ZIP successful responses', async (t) => {
  let response;
  const h = await exportHarness(t, async () => response);
  for (response of [new Blob([], { type: 'application/zip' }), new Blob(['<html>Login</html>'], { type: 'text/html' }), { type: 'application/zip', size: 1 }]) {
    fire(h.form, 'submit');
    await tick();
    assert.equal(h.downloads.length, 0);
    assert.equal(h.button.disabled, false);
    assert.match(h.status.textContent, /valid.*file/i);
  }
});

test('disposed accounting export aborts and ignores a late private response', async (t) => {
  let resolve;
  let signal;
  const h = await exportHarness(t, (_path, options) => {
    signal = options.signal;
    return new Promise((done) => { resolve = done; });
  });
  fire(h.form, 'submit');
  h.controller.abort();
  const status = h.status.textContent;
  resolve(new Blob(['private zip'], { type: 'application/zip' }));
  await tick();
  fire(h.form, 'submit');
  assert.equal(signal.aborted, true);
  assert.equal(h.created.length, 0);
  assert.equal(h.status.textContent, status);
});

test('rebinding accounting export cancels the previous pending response and listener', async (t) => {
  let resolve;
  const h = await exportHarness(t, () => new Promise((done) => { resolve = done; }));
  fire(h.form, 'submit');
  const journal = await importJournalModule();
  let calls = 0;
  const dispose = journal.bindManagementAccountingExport({ ...h.context, api: { request: async () => {
    calls += 1;
    return new Blob(['new zip'], { type: 'application/zip' });
  } } });
  t.after(dispose);
  resolve(new Blob(['old private zip'], { type: 'application/zip' }));
  fire(h.form, 'submit');
  await tick();
  assert.equal(calls, 1);
  assert.equal(h.created.length, 1);
  assert.equal(await h.created[0].text(), 'new zip');
});

test('accounting download URLs expire and are not revoked twice on disposal', async (t) => {
  const h = await exportHarness(t, async () => new Blob(['zip'], { type: 'application/zip' }));
  fire(h.form, 'submit');
  await tick();
  assert.deepEqual(h.revoked, []);
  await new Promise((resolve) => setTimeout(resolve, 1100));
  assert.deepEqual(h.revoked, ['blob:accounting-1']);
  h.dispose();
  assert.deepEqual(h.revoked, ['blob:accounting-1']);
});

test('a browser download failure releases its private object URL and leaves retry available', async (t) => {
  const h = await exportHarness(t, async () => new Blob(['zip'], { type: 'application/zip' }));
  globalThis.document.createElement = () => ({ click() { throw new Error('browser download blocked'); } });
  fire(h.form, 'submit');
  await tick();
  assert.deepEqual(h.revoked, ['blob:accounting-1']);
  assert.equal(h.button.disabled, false);
  assert.doesNotMatch(h.status.textContent, /download prepared/i);
});

test('Management workspace hides accounting downloads without the exact view permission', async (t) => {
  const h = await exportHarness(t, async () => ({}));
  h.context.setNavigation = () => {};
  for (const permissions of [[], ['accounting.view.extra']]) {
    h.context.session = { user: { role: 'management' }, permissions };
    await mountManagementWorkspace(h.context);
    assert.equal(h.root.querySelector('[data-accounting-export]'), null);
    assert.equal(h.context.accountingExportCleanup, null);
  }
});

test('Management workspace connects accounting download and disposes it before remount', async (t) => {
  let respond;
  let exportSignal;
  let exportCalls = 0;
  const h = await exportHarness(t, async (path, options) => {
    if (path.includes('/financial-accounting/export?')) {
      exportCalls += 1;
      exportSignal = options.signal;
      return new Promise((resolve) => { respond = resolve; });
    }
    return {};
  });
  h.context.session = { user: { role: 'management' }, permissions: ['accounting.view'] };
  h.context.setNavigation = () => {};
  await mountManagementWorkspace(h.context);
  t.after(() => h.context.accountingExportCleanup?.());
  const form = h.root.querySelector('[data-accounting-export]');
  form.querySelector('[name="start_date"]').value = '2026-09-01';
  form.querySelector('[name="end_date"]').value = '2026-09-20';
  fire(form, 'submit');
  assert.equal(exportCalls, 1);
  await mountManagementWorkspace(h.context);
  assert.equal(exportSignal.aborted, true);
  fire(form, 'submit');
  respond(new Blob(['old private zip'], { type: 'application/zip' }));
  await tick();
  assert.equal(exportCalls, 1);
  assert.equal(h.created.length, 0);
  assert.notEqual(h.root.querySelector('[data-accounting-export]'), form);
});
