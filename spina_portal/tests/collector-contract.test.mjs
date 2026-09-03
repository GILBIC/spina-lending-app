import assert from 'node:assert/strict';
import test from 'node:test';

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

test('payment submission keeps body and headers on the same idempotency identity', () => {
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
    'X-Gilbic-Contract-Version': '1',
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
    () => buildCollectionSubmission({ ...base, entryType: 'advance', amount: '50' }),
    /supports Payment and Unable to pay/i,
  );
});

test('loan classification keeps Regular and 7x7 visually separate', () => {
  assert.equal(classifyLoanType('Regular Loan'), 'regular');
  assert.equal(classifyLoanType('7x7'), 'seven-by-seven');
  assert.equal(classifyLoanType('7 × 7 Daily'), 'seven-by-seven');
  assert.equal(classifyLoanType('Special'), 'other');
});
