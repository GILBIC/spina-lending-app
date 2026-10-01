import assert from 'node:assert/strict';
import test from 'node:test';

import {
  bindManagementAccountingExport,
  managementGeneralJournalMarkup,
} from '../assets/management-general-journal.js';
import { Element, fire } from './helpers/dom.mjs';

const zeroLine = (code, name, type = 'asset', normal = 'debit') => ({
  account_code: code,
  account_name: name,
  account_type: type,
  normal_balance: normal,
  total_debit: '0.00',
  total_credit: '0.00',
  debit_balance: '0.00',
  credit_balance: '0.00',
});

function zeroPayload() {
  return {
    journals: {
      can_manage: true,
      automatic_loan_posting_enabled: false,
      entries: [],
    },
    trialBalance: {
      trial_balance: {
        period_id: null,
        period_label: null,
        total_debits: '0.00',
        total_credits: '0.00',
        balanced: true,
        lines: [
          zeroLine('1010', 'Cash - Office'),
          zeroLine('1030', 'Cash - Bank / GCash'),
          zeroLine('5200', 'Rent Expense', 'expense'),
        ],
      },
    },
  };
}

test('all-zero Trial Balance uses one compact no-activity state and preserves full accounts under disclosure', () => {
  const markup = managementGeneralJournalMarkup(zeroPayload());

  assert.match(markup, /data-trial-balance-zero/);
  assert.match(markup, /No posted journal activity yet/i);
  assert.match(markup, /Total debits/);
  assert.match(markup, /Total credits/);
  assert.match(markup, /₱0\.00/);
  assert.match(markup, /Balanced · no posted activity/i);
  assert.match(markup, /All posted activity/i);
  assert.match(markup, /<details[^>]*data-trial-balance-all-accounts/);
  assert.match(markup, />Show all accounts</);

  const zeroState = markup.split('data-trial-balance-zero')[1] || '';
  const beforeAllAccounts = zeroState.split('data-trial-balance-all-accounts')[0] || '';
  assert.doesNotMatch(beforeAllAccounts, /Cash - Office/);
  assert.match(markup, /Cash - Office/);
  assert.match(markup, /Cash - Bank \/ GCash/);
  assert.match(markup, /Rent Expense/);
});

test('Trial Balance prioritizes nonzero accounts while preserving zero accounts in Show all accounts', () => {
  const payload = zeroPayload();
  payload.trialBalance.trial_balance.total_debits = '125.50';
  payload.trialBalance.trial_balance.total_credits = '125.50';
  payload.trialBalance.trial_balance.lines = [
    {
      ...zeroLine('1010', 'Cash - Office'),
      total_credit: '125.50',
      credit_balance: '125.50',
    },
    zeroLine('1030', 'Cash - Bank / GCash'),
    {
      ...zeroLine('5210', 'Utilities Expense', 'expense'),
      total_debit: '125.50',
      debit_balance: '125.50',
    },
  ];

  const markup = managementGeneralJournalMarkup(payload);
  const primary = markup.split('<details data-trial-balance-all-accounts')[0] || '';

  assert.match(primary, /Cash - Office/);
  assert.match(primary, /Utilities Expense/);
  assert.doesNotMatch(primary, /Cash - Bank \/ GCash/);
  assert.match(markup, /Cash - Bank \/ GCash/);
  assert.match(markup, /₱125\.50/);
  assert.match(markup, /class="mobile-card-table trial-balance-table"/);
  for (const label of ['Account', 'Debit', 'Credit', 'Ending balance']) {
    assert.match(markup, new RegExp(`data-label="${label}"`));
  }
});

test('General Journal and Trial Balance are local views with General Journal visible first', () => {
  const markup = managementGeneralJournalMarkup(zeroPayload());

  assert.match(markup, /data-accounting-book-tab="journal"[^>]*aria-selected="true"/);
  assert.match(markup, /data-accounting-book-tab="trial-balance"[^>]*aria-selected="false"/);
  assert.match(markup, /data-accounting-book-panel="journal"(?![^>]*hidden)/);
  assert.match(markup, /data-accounting-book-panel="trial-balance" hidden/);
  assert.match(markup, />General Journal</);
  assert.match(markup, />Trial Balance</);
});

test('switching General Journal and Trial Balance views makes no API request', () => {
  const root = new Element();
  root.innerHTML = managementGeneralJournalMarkup(zeroPayload());
  let requests = 0;
  const dispose = bindManagementAccountingExport({
    root,
    api: { request: async () => { requests += 1; } },
  });

  const trialTab = root.querySelector('[data-accounting-book-tab="trial-balance"]');
  fire(trialTab, 'click');

  assert.equal(requests, 0);
  assert.equal(root.querySelector('[data-accounting-book-panel="journal"]').getAttribute('hidden'), '');
  assert.equal(root.querySelector('[data-accounting-book-panel="trial-balance"]').getAttribute('hidden'), null);
  assert.equal(trialTab.getAttribute('aria-selected'), 'true');

  dispose();
});

test('accounting export is secondary and the main notice uses operational wording', () => {
  const markup = managementGeneralJournalMarkup(zeroPayload());

  assert.match(markup, /Review drafts before posting\. Automatic posting is off\./i);
  assert.doesNotMatch(markup, /Automatic loan posting is not enabled/i);
  assert.match(markup, /<details[^>]*data-accounting-export-details/);
  assert.match(markup, />Export accounting books</);
  assert.match(markup, /BIR registration and SAF acceptance/i);

  const beforeExport = markup.split('data-accounting-export-details')[0] || '';
  assert.doesNotMatch(beforeExport, /Download accounting review copy/);
});
