import assert from 'node:assert/strict';
import { setImmediate } from 'node:timers/promises';
import test from 'node:test';

import { managementGeneralJournalMarkup } from '../assets/management-general-journal.js';
import { mountManagementJournalActions } from '../assets/management-journal-actions.js';
import { Element, fire } from './helpers/dom.mjs';

const tick = async () => {
  await setImmediate();
  await setImmediate();
};

const line = (account_code, description, debit, credit) => ({
  account_code,
  account_name: account_code === '1010' ? 'Cash - Office' : 'Capital',
  description,
  debit,
  credit,
});

const manualDraft = {
  entry_id: 'entry-draft',
  entry_number: 'JE-DRAFT',
  posting_date: '2026-10-01',
  period_label: 'October 2026',
  description: 'Office expense draft',
  status: 'draft',
  source_type: 'manual',
  source_reference: '',
  created_by_name: 'Manager',
  posted_by_name: '',
  total_debit: '125.00',
  total_credit: '125.00',
  created_at: '2026-10-01T09:00:00+08:00',
  posted_at: null,
  lines: [
    line('5200', 'Expense', '125.00', '0.00'),
    line('1010', 'Cash', '0.00', '125.00'),
  ],
};

const reversalDraft = {
  ...manualDraft,
  entry_id: 'entry-reversal-draft',
  entry_number: 'JE-REV-DRAFT',
  description: 'Reversal draft',
  source_type: 'reversal',
  reversal_of_entry_id: 'old-entry',
};

const postedOriginal = {
  ...manualDraft,
  entry_id: 'entry-posted',
  entry_number: 'JE-POSTED',
  description: 'Posted original',
  status: 'posted',
  posted_at: '2026-10-01T10:00:00+08:00',
};

const postedReversal = {
  ...postedOriginal,
  entry_id: 'entry-posted-reversal',
  entry_number: 'JE-POSTED-REV',
  description: 'Posted reversal',
  source_type: 'reversal',
  reversal_of_entry_id: 'another-old-entry',
};

const journals = {
  can_manage: true,
  automatic_loan_posting_enabled: false,
  entries: [manualDraft, reversalDraft, postedOriginal, postedReversal],
};

const trialBalance = {
  trial_balance: {
    total_debits: '0.00',
    total_credits: '0.00',
    balanced: true,
    lines: [],
  },
};

function pageMarkup(currentJournals = journals) {
  return `<div id="evidence">${managementGeneralJournalMarkup({
    journals: currentJournals,
    trialBalance,
  })}</div><div id="actions"></div>`;
}

test('General Journal evidence renders each entry once and provides one action slot per entry', () => {
  const markup = managementGeneralJournalMarkup({ journals, trialBalance });
  const root = new Element();
  root.innerHTML = markup;

  for (const entry of journals.entries) {
    assert.equal(
      root.querySelectorAll('h3').filter((heading) => heading.textContent === entry.entry_number).length,
      1,
      entry.entry_number,
    );
    assert.match(
      markup,
      new RegExp(`data-journal-actions-for="${entry.entry_id}"`),
    );
  }
  assert.doesNotMatch(markup, /<h3>Journal actions<\/h3>/);
});

test('integrated Journal actions decorate evidence cards without rendering a second journal list or initial refetch', async (t) => {
  const page = new Element();
  page.innerHTML = pageMarkup();
  const evidenceRoot = page.querySelector('#evidence');
  const actionRoot = page.querySelector('#actions');
  const calls = [];
  const controller = new AbortController();
  t.after(() => controller.abort());

  const dispose = mountManagementJournalActions({
    root: actionRoot,
    evidenceRoot,
    initialJournals: journals,
    session: {
      user: { role: 'management' },
      permissions: ['accounting.view', 'accounting.journal.manage'],
    },
    signal: controller.signal,
    confirm: () => true,
    api: {
      async request(path, options = {}) {
        calls.push({ path, options });
        return journals;
      },
    },
  });
  t.after(dispose);
  await tick();

  assert.equal(calls.length, 0, 'initial authoritative journal response is reused');
  assert.equal((page.textContent.match(/Office expense draft/g) || []).length, 1);
  assert.equal((page.textContent.match(/Posted original/g) || []).length, 1);
  assert.doesNotMatch(actionRoot.textContent, /JE-DRAFT|Office expense draft|Posted original/);
  assert.ok(actionRoot.querySelector('[data-journal-create]'));

  const draftSlot = evidenceRoot.querySelector('[data-journal-actions-for="entry-draft"]');
  assert.ok(draftSlot.querySelector('[data-journal-edit]'));
  assert.ok(draftSlot.querySelector('[data-journal-cancel]'));
  assert.ok(draftSlot.querySelector('[data-journal-post]'));
  assert.equal(draftSlot.querySelector('[data-journal-reverse]'), null);

  const reversalSlot = evidenceRoot.querySelector('[data-journal-actions-for="entry-reversal-draft"]');
  assert.ok(reversalSlot.querySelector('[data-journal-post]'));
  assert.equal(reversalSlot.querySelector('[data-journal-edit]'), null);
  assert.equal(reversalSlot.querySelector('[data-journal-cancel]'), null);

  const postedSlot = evidenceRoot.querySelector('[data-journal-actions-for="entry-posted"]');
  assert.ok(postedSlot.querySelector('[data-journal-reverse]'));
  assert.equal(postedSlot.querySelector('[data-journal-post]'), null);

  const postedReversalSlot = evidenceRoot.querySelector('[data-journal-actions-for="entry-posted-reversal"]');
  assert.equal(postedReversalSlot.querySelector('button'), null);
});

test('integrated posting refreshes authoritative evidence once and keeps one visual journal copy', async (t) => {
  const page = new Element();
  page.innerHTML = pageMarkup({
    ...journals,
    entries: [manualDraft],
  });
  const evidenceRoot = page.querySelector('#evidence');
  const actionRoot = page.querySelector('#actions');
  const controller = new AbortController();
  const calls = [];
  const posted = { ...manualDraft, status: 'posted', posted_at: '2026-10-01T10:00:00+08:00' };
  const refreshed = { ...journals, entries: [posted] };
  t.after(() => controller.abort());

  const dispose = mountManagementJournalActions({
    root: actionRoot,
    evidenceRoot,
    initialJournals: { ...journals, entries: [manualDraft] },
    session: {
      user: { role: 'management' },
      permissions: ['accounting.view', 'accounting.journal.manage'],
    },
    signal: controller.signal,
    confirm: () => true,
    api: {
      async request(path, options = {}) {
        calls.push({ path, options });
        if (options.method === 'POST') return { entry: posted };
        return refreshed;
      },
    },
    onSaved: async (freshJournals) => {
      evidenceRoot.innerHTML = managementGeneralJournalMarkup({
        journals: freshJournals,
        trialBalance,
      });
    },
  });
  t.after(dispose);
  await tick();

  fire(
    evidenceRoot
      .querySelector('[data-journal-actions-for="entry-draft"]')
      .querySelector('[data-journal-post]'),
    'click',
  );
  await tick();
  await tick();

  assert.equal(
    calls.filter((call) => call.path.endsWith('/entry-draft/post')).length,
    1,
  );
  assert.equal(
    calls.filter((call) => call.path === '/api/v1/management/financial-accounting/journals' && !call.options.method).length,
    1,
  );
  assert.equal((page.textContent.match(/Office expense draft/g) || []).length, 1);
  assert.equal(
    evidenceRoot
      .querySelector('[data-journal-actions-for="entry-draft"]')
      .querySelector('[data-journal-post]'),
    null,
  );
});

for (const failure of [409, 503, 'refresh']) test(`integrated journal ${failure} failure locks external controls until a fresh authoritative reload`, async (t) => {
  const page = new Element();
  const initial = { ...journals, entries: [manualDraft] };
  page.innerHTML = pageMarkup(initial);
  const evidenceRoot = page.querySelector('#evidence');
  const root = page.querySelector('#actions');
  const calls = [];
  let failing = true;
  const posted = { ...manualDraft, status: 'posted' };
  const refreshed = { ...journals, entries: [posted] };
  const dispose = mountManagementJournalActions({
    root, evidenceRoot, initialJournals: initial,
    session: { user: { role: 'management' }, permissions: ['accounting.view', 'accounting.journal.manage'] },
    confirm: () => true,
    api: { request: async (path, options = {}) => {
      calls.push({ path, options });
      if (options.method) {
        if (failure !== 'refresh' && failing) throw Object.assign(new Error('Synthetic failure'), { status: failure });
        return { entry: posted };
      }
      if (failure === 'refresh' && failing) throw new Error('Synthetic refresh failure');
      return refreshed;
    } },
    onSaved: async (freshJournals) => {
      evidenceRoot.innerHTML = managementGeneralJournalMarkup({ journals: freshJournals, trialBalance });
    },
  });
  t.after(dispose);
  assert.equal(calls.length, 0);
  const oldPost = evidenceRoot.querySelector('[data-journal-post]');
  fire(oldPost, 'click');
  await tick();
  assert.equal(evidenceRoot.querySelector('[data-journal-post]').disabled, true);
  assert.equal(root.querySelector('[data-journal-create]').disabled, true);
  assert.equal(root.querySelector('[data-journal-refresh]').disabled, false);
  fire(oldPost, 'click');
  await tick();
  assert.equal(calls.filter((call) => call.options.method).length, 1);
  failing = false;
  const readsBeforeRefresh = calls.filter((call) => !call.options.method).length;
  fire(root.querySelector('[data-journal-refresh]'), 'click');
  await tick();
  assert.equal(calls.filter((call) => !call.options.method).length, readsBeforeRefresh + 1);
  assert.equal(evidenceRoot.querySelector('[data-journal-post]'), null);
  assert.ok(evidenceRoot.querySelector('[data-journal-reverse]'));
  fire(oldPost, 'click');
  await tick();
  assert.equal(calls.filter((call) => call.options.method).length, 1);
});

test('integrated authorization failure clears external journal evidence and detached actions', async (t) => {
  const page = new Element();
  page.innerHTML = pageMarkup({ ...journals, entries: [manualDraft] });
  const evidenceRoot = page.querySelector('#evidence');
  const root = page.querySelector('#actions');
  let mutations = 0;
  const dispose = mountManagementJournalActions({
    root, evidenceRoot, initialJournals: { ...journals, entries: [manualDraft] },
    session: { user: { role: 'management' }, permissions: ['accounting.view', 'accounting.journal.manage'] },
    confirm: () => true,
    api: { request: async () => { mutations++; throw Object.assign(new Error('Private backend detail'), { status: 403 }); } },
  });
  t.after(dispose);
  const oldPost = evidenceRoot.querySelector('[data-journal-post]');
  fire(oldPost, 'click');
  await tick();
  assert.equal(evidenceRoot.innerHTML, '');
  assert.doesNotMatch(root.textContent, /Private backend detail/);
  assert.match(root.textContent, /Sign in again/);
  fire(oldPost, 'click');
  await tick();
  assert.equal(mutations, 1);
});
