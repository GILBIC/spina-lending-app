import assert from 'node:assert/strict';
import test from 'node:test';

import * as clientRole from '../assets/roles/client.js';

test('Client Web renewal exposes cancellation only for a pending request', () => {
  assert.equal(typeof clientRole.clientRenewalRows, 'function');

  const html = clientRole.clientRenewalRows([
    {
      request_id: 'renewal-pending',
      loan_number: 'REG-001',
      requested_amount: '6000.00',
      submitted_at: '2026-09-13T01:00:00Z',
      status: 'pending',
    },
    {
      request_id: 'renewal-approved',
      loan_number: 'REG-002',
      requested_amount: '7000.00',
      submitted_at: '2026-09-13T01:05:00Z',
      status: 'approved',
    },
    {
      request_id: 'renewal-cancelled',
      loan_number: 'REG-003',
      requested_amount: '8000.00',
      submitted_at: '2026-09-13T01:10:00Z',
      status: 'cancelled',
    },
  ]);

  assert.match(html, /data-client-renewal-cancel="renewal-pending"/);
  assert.doesNotMatch(html, /data-client-renewal-cancel="renewal-approved"/);
  assert.doesNotMatch(html, /data-client-renewal-cancel="renewal-cancelled"/);
});

test('Client Web renewal cancellation requires confirmation before protected POST', async () => {
  assert.equal(typeof clientRole.requestClientRenewalCancellation, 'function');

  const calls = [];
  const api = {
    async request(path, options) {
      calls.push({ path, options });
      return { request: { request_id: 'renewal-pending', status: 'cancelled' } };
    },
  };

  const cancelled = await clientRole.requestClientRenewalCancellation({
    api,
    requestId: 'renewal-pending',
    confirmCancel: () => false,
  });
  assert.equal(cancelled, false);
  assert.equal(calls.length, 0);

  const confirmed = await clientRole.requestClientRenewalCancellation({
    api,
    requestId: 'renewal-pending',
    confirmCancel: () => true,
  });
  assert.equal(confirmed, true);
  assert.deepEqual(calls, [
    {
      path: '/api/v1/client/renewals/renewal-pending/cancel',
      options: { method: 'POST' },
    },
  ]);
});
