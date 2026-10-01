import assert from 'node:assert/strict';
import test from 'node:test';

import {
  bindManagementLoanOperations,
  managementLoanOperationsMarkup,
} from '../assets/management-loan-operations.js';

const payload = {
  summary: {
    latest_collection_date: '2026-09-16',
    latest_day_amount: '71.00',
    latest_day_payment_count: 2,
    latest_day_unable_to_pay_count: 0,
    unremitted_amount: '584.00',
    unremitted_entry_count: 16,
    pending_remittance_amount: '21.00',
    pending_remittance_count: 1,
    received_remittance_amount: '563.00',
    received_remittance_count: 8,
    correction_count: 4,
    void_count: 1,
  },
  entries: [{
    transaction_id: 'tx-1',
    receipt_number: 'GBC-20260916-0000031',
    collection_date: '2026-09-16',
    accepted_at: '2026-09-16T18:48:00+08:00',
    client_code: 'TEST-7X7-001',
    client_name: 'TEST CLIENT 7X7',
    loan_number: 'TEST-7X7-REG-20260802',
    loan_type_name: 'Regular',
    collector_name: 'Test Collector',
    entry_type: 'payment',
    amount: '50.00',
    official_balance: '4600.00',
    covered_dates: [],
    edit_version: 0,
    status: 'unremitted',
    remittance_number: null,
    void_reason: null,
  }, {
    transaction_id: 'tx-2',
    receipt_number: 'GBC-20260904-0000028',
    collection_date: '2026-09-04',
    accepted_at: '2026-09-04T20:55:00+08:00',
    client_code: 'TEST-7X7-001',
    client_name: 'TEST CLIENT 7X7',
    loan_number: 'TEST-7X7-20260802',
    loan_type_name: '7x7',
    collector_name: 'Test Collector',
    entry_type: 'advance',
    amount: '21.00',
    official_balance: '3000.00',
    covered_dates: ['2026-09-04', '2026-09-05'],
    edit_version: 2,
    status: 'submitted',
    remittance_number: 'REM-20260904-000009',
    void_reason: null,
  }],
  audits: [{
    event_id: 'audit-1',
    event_type: 'correction',
    happened_at: '2026-08-24T16:46:00+08:00',
    transaction_id: 'tx-1',
    receipt_number: 'GBC-20260824-0000022',
    client_name: 'TEST CLIENT REGULAR',
    loan_number: 'TEST-REG-20260802',
    actor_name: 'Test Collector',
    reason: 'Acceptance correction test',
  }, {
    event_id: 'audit-2',
    event_type: 'void',
    happened_at: '2026-08-05T18:21:00+08:00',
    transaction_id: 'tx-3',
    receipt_number: 'GBC-20260805-0000008',
    client_name: 'TEST CLIENT REGULAR',
    loan_number: 'TEST-REG-20260802',
    actor_name: 'Gilbic Clarck San Jose',
    reason: 'Payment posted to the wrong borrower',
  }],
  notice: 'Loan Operations is a read-only monitoring view. Use the dedicated Direct Payment Entry, correction, remittance, and void workflows for authorized changes.',
};

test('Loan Operations groups summary into Latest day, Remittance, and Audit without recomputing server values', () => {
  const markup = managementLoanOperationsMarkup(payload);

  assert.match(markup, /data-loan-ops-summary-group="latest-day"/);
  assert.match(markup, />Latest collection day</);
  assert.match(markup, /₱71\.00/);
  assert.match(markup, /2 payments/);
  assert.match(markup, /0 unable to pay/);
  assert.match(markup, /Sep 16, 2026/);

  assert.match(markup, /data-loan-ops-summary-group="remittance"/);
  assert.match(markup, /₱584\.00/);
  assert.match(markup, /16 entries/);
  assert.match(markup, /₱21\.00/);
  assert.match(markup, /1 remittance/);
  assert.match(markup, /₱563\.00/);
  assert.match(markup, /8 remittances/);

  assert.match(markup, /data-loan-ops-summary-group="audit"/);
  assert.match(markup, /4 corrections/);
  assert.match(markup, /1 void/);
  assert.doesNotMatch(markup, /Payments \/ unable/);
  assert.doesNotMatch(markup, /Server-returned audit counts/);
});

test('Loan Operations uses Activity and Corrections & voids local views', () => {
  const markup = managementLoanOperationsMarkup(payload);

  assert.match(markup, /data-loan-ops-tab="activity"/);
  assert.match(markup, /data-loan-ops-tab="audits"/);
  assert.match(markup, /data-loan-ops-panel="activity"/);
  assert.match(markup, /data-loan-ops-panel="audits" hidden/);
  assert.match(markup, />Collection activity</);
  assert.match(markup, />Corrections &amp; voids</);
});

test('Collection activity prioritizes business facts and keeps technical revision data inside details', () => {
  const markup = managementLoanOperationsMarkup(payload);

  assert.match(markup, /class="loan-operation-card"/);
  assert.match(markup, /TEST CLIENT 7X7/);
  assert.match(markup, /GBC-20260916-0000031/);
  assert.match(markup, /₱50\.00/);
  assert.match(markup, /Official balance/);
  assert.match(markup, /₱4,600\.00/);
  assert.match(markup, /<details[^>]*data-loan-ops-technical/);
  assert.match(markup, /edit v0/);
  assert.match(markup, /entry type/i);

  const firstCard = markup.split('loan-operation-card')[1] || '';
  const visibleBeforeDetails = firstCard.split('<details')[0] || '';
  assert.doesNotMatch(visibleBeforeDetails, /edit v0/);
  assert.doesNotMatch(visibleBeforeDetails, /entry type/i);

  assert.match(markup, /Sep 4, 2026, Sep 5, 2026/);
  assert.doesNotMatch(visibleBeforeDetails, />—</);
});

test('Loan Operations binding switches local views without issuing another server request', () => {
  const listeners = {};
  const tabs = [
    {
      attrs: {'data-loan-ops-tab':'activity','aria-selected':'true'},
      addEventListener(type, handler){ listeners.activity = handler; },
      getAttribute(name){ return this.attrs[name] ?? null; },
      setAttribute(name,value){ this.attrs[name]=value; },
    },
    {
      attrs: {'data-loan-ops-tab':'audits','aria-selected':'false'},
      addEventListener(type, handler){ listeners.audits = handler; },
      getAttribute(name){ return this.attrs[name] ?? null; },
      setAttribute(name,value){ this.attrs[name]=value; },
    },
  ];
  const panels = [
    {
      attrs: {'data-loan-ops-panel':'activity'},
      getAttribute(name){ return this.attrs[name] ?? null; },
      setAttribute(name,value){ this.attrs[name]=value; },
      removeAttribute(name){ delete this.attrs[name]; },
    },
    {
      attrs: {'data-loan-ops-panel':'audits',hidden:''},
      getAttribute(name){ return this.attrs[name] ?? null; },
      setAttribute(name,value){ this.attrs[name]=value; },
      removeAttribute(name){ delete this.attrs[name]; },
    },
  ];
  const form = {
    addEventListener(){},
    querySelector(selector){
      if (selector === '[name="q"]') return {value:''};
      if (selector === '[name="status"]') return {value:'all',addEventListener(){}};
      return null;
    },
  };
  const root = {
    querySelector(selector){
      if (selector === '#management-loan-operations-search') return form;
      if (selector === '#management-loan-operations-results') return {innerHTML:''};
      return null;
    },
    querySelectorAll(selector){
      if (selector === '[data-loan-ops-tab]') return tabs;
      if (selector === '[data-loan-ops-panel]') return panels;
      return [];
    },
  };
  let requests = 0;
  bindManagementLoanOperations({root,api:{request:async()=>{requests++;return payload;}}});

  listeners.audits({preventDefault(){}});
  assert.equal(requests,0);
  assert.equal(panels[0].attrs.hidden,'');
  assert.equal(panels[1].attrs.hidden,undefined);
  assert.equal(tabs[0].attrs['aria-selected'],'false');
  assert.equal(tabs[1].attrs['aria-selected'],'true');
});
