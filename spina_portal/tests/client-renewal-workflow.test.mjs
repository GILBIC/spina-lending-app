import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';

import * as clientRole from '../assets/roles/client.js';

const clientRoleSource = await readFile(
  new URL('../assets/roles/client.js', import.meta.url),
  'utf8',
);

test('Client Web renewal workflow renders only server-authorized continuation actions', () => {
  assert.equal(typeof clientRole.clientRenewalWorkflowRows, 'function');

  const html = clientRole.clientRenewalWorkflowRows([
    {
      request_id: 'request-approved',
      loan_number: 'REG-1001',
      loan_type_name: 'Regular',
      status: 'approved',
      requested_amount: '9999999.99',
      approved_principal: '9999999.99',
      client_decision: null,
      office_processing_required: false,
      signers: [],
    },
    {
      request_id: 'request-accepted',
      loan_number: 'REG-1002',
      loan_type_name: 'Regular',
      status: 'approved',
      requested_amount: '5000.00',
      approved_principal: '5000.00',
      client_decision: 'accepted',
      office_processing_required: false,
      signer_readiness_status: 'pending',
      signers: [
        {
          signer_id: 'borrower-signer',
          party_role: 'borrower',
          full_name: 'Borrower One',
          has_app: true,
          government_id_verified: true,
          selfie_verified: true,
          signed: false,
        },
        {
          signer_id: 'guarantor-signer',
          party_role: 'guarantor',
          full_name: 'Guarantor One',
          has_app: true,
          government_id_verified: true,
          selfie_verified: true,
          signed: false,
        },
      ],
      net_release_amount: '4200.00',
      cash_given_to_client_at: '2026-09-13T03:00:00+00:00',
      client_cash_confirmed_at: null,
    },
  ]);

  assert.match(html, /₱9,999,999\.99/);
  assert.match(html, /data-client-renewal-decision-request="request-approved"/);
  assert.match(html, /data-client-renewal-decision="accepted"/);
  assert.match(html, /data-client-renewal-decision="declined"/);
  assert.match(html, /data-client-renewal-sign-request="request-accepted"/);
  assert.match(html, /data-client-renewal-sign-signer="borrower-signer"/);
  assert.doesNotMatch(html, /data-client-renewal-sign-signer="guarantor-signer"/);
  assert.match(html, /data-client-renewal-cash-confirm="request-accepted"/);
  assert.match(html, /I Received the Cash/);
});

test('Client Web renewal decision requires explicit confirmation before protected POST', async () => {
  assert.equal(typeof clientRole.requestClientRenewalDecision, 'function');
  const calls = [];
  const api = {
    async request(path, options) {
      calls.push({ path, options });
      return { request: { request_id: 'request/1', client_decision: 'accepted' } };
    },
  };

  const cancelled = await clientRole.requestClientRenewalDecision({
    api,
    requestId: 'request/1',
    decision: 'accepted',
    confirmAction: () => false,
  });
  assert.equal(cancelled, false);
  assert.equal(calls.length, 0);

  const confirmed = await clientRole.requestClientRenewalDecision({
    api,
    requestId: 'request/1',
    decision: 'accepted',
    confirmAction: () => true,
  });
  assert.equal(confirmed, true);
  assert.deepEqual(calls, [
    {
      path: '/api/v1/client/renewals/request%2F1/decision',
      options: { method: 'POST', body: { decision: 'accepted' } },
    },
  ]);
});

test('Client Web renewal signature requires explicit confirmation and posts only the selected signer', async () => {
  assert.equal(typeof clientRole.requestClientRenewalSignature, 'function');
  const calls = [];
  const api = {
    async request(path, options) {
      calls.push({ path, options });
      return { request: { request_id: 'request/2' } };
    },
  };

  const confirmed = await clientRole.requestClientRenewalSignature({
    api,
    requestId: 'request/2',
    signerId: 'signer/2',
    confirmAction: () => true,
  });
  assert.equal(confirmed, true);
  assert.deepEqual(calls, [
    {
      path: '/api/v1/renewals/request%2F2/signers/signer%2F2/sign',
      options: { method: 'POST', body: {} },
    },
  ]);
});

test('Client Web cash confirmation requires explicit confirmation before protected POST', async () => {
  assert.equal(typeof clientRole.requestClientRenewalCashConfirmation, 'function');
  const calls = [];
  const api = {
    async request(path, options) {
      calls.push({ path, options });
      return { request: { request_id: 'request/3', client_cash_confirmed_at: 'now' } };
    },
  };

  const confirmed = await clientRole.requestClientRenewalCashConfirmation({
    api,
    requestId: 'request/3',
    confirmAction: () => true,
  });
  assert.equal(confirmed, true);
  assert.deepEqual(calls, [
    {
      path: '/api/v1/client/renewals/request%2F3/cash-confirm',
      options: { method: 'POST', body: {} },
    },
  ]);
});

test('Client workspace consumes the protected renewal-workflow endpoint', () => {
  assert.match(clientRoleSource, /settledRequest\(api, '\/api\/v1\/client\/renewal-workflow'/);
  assert.match(clientRoleSource, /clientRenewalWorkflowRows\(/);
  assert.match(clientRoleSource, /bindClientRenewalWorkflowActions\(context\)/);
});
