import assert from 'node:assert/strict';
import test from 'node:test';
import { mountCollectorWorkspace } from '../assets/roles/collector.js';
import { Element } from './helpers/dom.mjs';

import {
  buildCollectionSubmission,
  classifyLoanType,
} from '../assets/collector-contract.js';

const entry = {
  route_entry_id: 'route-entry-1',
  client_id: 'client-1',
  loan_id: 'loan-1',
  loan_type: 'Regular',
  route_revision: 'route-revision-7',
};

const base = {
  entry,
  routeDate: '2026-09-03',
  deviceId: 'spina-web-device-1',
  deviceSequence: 9,
  clientTransactionId: '11111111-2222-4333-8444-555555555555',
  recordedAt: '2026-09-02T23:45:00.000Z',
};

test('payment uses the supported collection protocol and matching idempotency identity', () => {
  const submission = buildCollectionSubmission({
    ...base,
    entryType: 'payment',
    amount: '150.00',
    note: 'Received in cash',
  });

  assert.deepEqual(submission.headers, {
    'Idempotency-Key': base.clientTransactionId,
    'X-Client-Transaction-Id': base.clientTransactionId,
    'X-Device-Id': base.deviceId,
    'X-Gilbic-Contract-Version': 'gilbic-collection-v1',
  });
  assert.deepEqual(submission.body, {
    client_transaction_id: base.clientTransactionId,
    route_entry_id: entry.route_entry_id,
    client_id: entry.client_id,
    loan_id: entry.loan_id,
    collection_date: base.routeDate,
    entry_type: 'payment',
    amount: '150.00',
    advance_from: null,
    advance_until: null,
    covered_dates: [],
    recorded_at: base.recordedAt,
    device_id: base.deviceId,
    device_sequence: 9,
    note: 'Received in cash',
    route_revision: entry.route_revision,
    payment_allocation_intent: 'scheduled',
    past_due_followup: null,
  });
});

test('unable-to-pay submission contains no amount and requires a Past Due reason', () => {
  const submission = buildCollectionSubmission({
    ...base,
    entryType: 'pass',
    amount: '999.00',
    note: 'Client has no cash today',
    pastDueFollowup: {
      reason_code: 'no_cash',
      note: 'Client has no cash today',
      promised_payment_date: null,
      promised_amount: null,
    },
  });

  assert.equal(submission.body.entry_type, 'pass');
  assert.equal(submission.body.amount, null);
  assert.deepEqual(submission.body.covered_dates, []);
  assert.equal(submission.body.payment_allocation_intent, 'scheduled');
  assert.deepEqual(submission.body.past_due_followup, {
    reason_code: 'no_cash',
    note: 'Client has no cash today',
    promised_payment_date: null,
    promised_amount: null,
  });
});

test('payment requires a positive peso amount', () => {
  assert.throws(
    () =>
      buildCollectionSubmission({
        ...base,
        entryType: 'payment',
        amount: '0',
      }),
    /greater than zero/i,
  );
});

test('pass requires an allowlisted Past Due reason', () => {
  assert.throws(
    () =>
      buildCollectionSubmission({
        ...base,
        entryType: 'pass',
        pastDueFollowup: { reason_code: 'invented' },
      }),
    /Past Due reason/i,
  );
});

test('invalid UUID, sequence, and entry type fail before network I/O', () => {
  assert.throws(
    () => buildCollectionSubmission({ ...base, clientTransactionId: 'not-a-uuid', entryType: 'payment', amount: '50' }),
    /UUID/i,
  );
  assert.throws(
    () => buildCollectionSubmission({ ...base, deviceSequence: 0, entryType: 'payment', amount: '50' }),
    /sequence/i,
  );
  assert.throws(
    () => buildCollectionSubmission({ ...base, entryType: 'invented', amount: '50' }),
    /Choose Payment/i,
  );
});

test('covered-date payment uses only explicitly selected saved dates and matching bounds', () => {
  const result=buildCollectionSubmission({...base,entryType:'advance',amount:'300.01',coveredDates:['2026-09-05','2026-09-03']});
  assert.deepEqual(result.body.covered_dates,['2026-09-03','2026-09-05']);
  assert.equal(result.body.advance_from,'2026-09-03');assert.equal(result.body.advance_until,'2026-09-05');
  assert.equal(result.body.amount,'300.01');
  assert.throws(()=>buildCollectionSubmission({...base,entryType:'advance',amount:'50'}),/covered date/i);
  assert.throws(()=>buildCollectionSubmission({...base,entryType:'advance',amount:'50',coveredDates:['2026-09-03','2026-09-03']}),/unique/i);
});

test('short payment carries promised date and amount while explicit extra choice stays server-owned', () => {
  const promise=buildCollectionSubmission({...base,entryType:'payment',amount:'50.01',pastDueFollowup:{reason_code:'promised_to_pay_later',note:'Client promised tomorrow',promised_payment_date:'2026-09-04',promised_amount:'99.99'}});
  assert.equal(promise.body.past_due_followup.promised_amount,'99.99');assert.equal(promise.body.past_due_followup.promised_payment_date,'2026-09-04');
  const extra=buildCollectionSubmission({...base,entryType:'payment',amount:'250.01',paymentAllocationIntent:'extra_as_principal_reduction'});
  assert.equal(extra.body.payment_allocation_intent,'extra_as_principal_reduction');assert.deepEqual(extra.body.covered_dates,[]);
  assert.throws(()=>buildCollectionSubmission({...base,entryType:'payment',amount:'50',paymentAllocationIntent:'voluntary_extra'}),/supported payment allocation/i);
});

test('loan classification keeps Regular and 7x7 visually separate', () => {
  assert.equal(classifyLoanType('Regular Loan'), 'regular');
  assert.equal(classifyLoanType('7x7'), 'seven-by-seven');
  assert.equal(classifyLoanType('7 × 7 Daily'), 'seven-by-seven');
  assert.equal(classifyLoanType('Special'), 'other');
});

test('payment and promises preserve every supported cent as decimal text', () => {
  for (const [amount, expected] of [
    ['100.01', '100.01'], ['001,234.5', '1234.50'],
    ['1000000000000000.01', '1000000000000000.01'],
    ['9999999999999999.99', '9999999999999999.99'],
  ]) {
    const submission = buildCollectionSubmission({ ...base, entryType: 'payment', amount });
    assert.equal(submission.body.amount, expected);
    const promise = buildCollectionSubmission({ ...base, entryType: 'pass', pastDueFollowup: {
      reason_code: 'promised_to_pay_later', promised_payment_date: base.routeDate,
      promised_amount: amount,
    } });
    assert.equal(promise.body.past_due_followup.promised_amount, expected);
  }
});

test('payment rejects invalid syntax, fractional cents and server-capacity overflow', () => {
  for (const amount of ['', '0', '-1', '1.001', '1e3', 'NaN', 'Infinity', '10000000000000000', '10000000000000000.01']) {
    assert.throws(() => buildCollectionSubmission({ ...base, entryType: 'payment', amount }), TypeError, amount);
  }
});

test('already-lossy numeric input is rejected instead of inventing cents', () => {
  assert.throws(() => buildCollectionSubmission({ ...base, entryType: 'payment', amount: 1000000000000000.01 }), TypeError);
});

test('collector form defaults preserve server cents before submission', async () => {
  const controller = new AbortController();
  const root = new Element();
  root.dataset = {};
  try {
    await mountCollectorWorkspace({
      root, signal: controller.signal, setNavigation() {},
      session: { user: { role: 'collector' }, permissions: ['route.view', 'collection.create'] },
      api: { async request(path) {
        return path === '/api/v1/collector/routes/today' ? {
          route_date: base.routeDate,
          entries: [{ ...entry, can_enter_payment: true, daily_amount: '1000000000000000.01', contract_today_unpaid_amount: '1000000000000000.02' }],
        } : {};
      } },
    });
    const amount = root.querySelector('input[name="amount"]').value;
    assert.equal(amount, '1000000000000000.02');
    assert.equal(buildCollectionSubmission({ ...base, entryType: 'payment', amount }).body.amount, amount);
  } finally {
    controller.abort();
  }
});

test('recorded receipt keeps the server correction explanation visible beside its note', async () => {
  const controller = new AbortController();
  const root = new Element();
  root.dataset = {};
  const calls = [];
  const reason = 'This collection cannot be edited here. Ask Management to review the correction.';
  try {
    await mountCollectorWorkspace({
      root, signal: controller.signal, setNavigation() {},
      session: { user: { role: 'collector' }, permissions: ['route.view', 'collection.create', 'collection.correct.own_unremitted'] },
      api: { async request(path, options) {
        calls.push({path, options});
        return path === '/api/v1/collector/routes/today' ? {
          route_date: base.routeDate,
          entries: [{ ...entry, processed_today: true, can_enter_payment: true, can_edit_today: false,
            today_is_locked: false, today_transaction_id: 'receipt-1',
            note: 'Cash counted', collection_message: reason }],
        } : {};
      } },
    });
    const row = root.querySelector('[data-entry-row="route-entry-1"]');
    assert.ok(row.textContent.includes('Cash counted'));
    assert.ok(row.textContent.includes(reason));
    assert.equal(root.querySelector('[data-load-schedule]'), null);
    assert.equal(root.querySelector('[data-dates-form]'), null);
    assert.equal(calls.some(({options}) => options?.method === 'PATCH'), false);
  } finally {
    controller.abort();
  }
});
