import assert from 'node:assert/strict';
import test from 'node:test';

async function loadClientGcashModule() {
  try {
    return await import('../assets/client-gcash.js');
  } catch {
    return {};
  }
}

test('Client Web GCash renders active Regular and 7x7 loans with blank manual amounts', async () => {
  const module = await loadClientGcashModule();
  assert.equal(typeof module.renderClientGcashPanel, 'function');

  const html = module.renderClientGcashPanel({
    capability: {
      payment_available: true,
      provider: 'test-provider',
      mode: 'sandbox',
      message: 'Sandbox checkout is available.',
      official_payment_rule: 'Provider checkout is not yet an official SPINA payment.',
    },
    loans: [
      {
        loan_id: 'regular-1',
        loan_number: 'REG-001',
        loan_type_name: 'Regular',
        status: 'active',
        remaining_balance: '5000.00',
        daily_amount: '200.00',
      },
      {
        loan_id: 'seven-1',
        loan_number: '7X7-001',
        loan_type_name: '7x7',
        status: 'active',
        remaining_balance: '3000.00',
        daily_amount: '50.00',
      },
      {
        loan_id: 'closed-1',
        loan_number: 'OLD-001',
        loan_type_name: 'Regular',
        status: 'closed',
        remaining_balance: '0.00',
      },
    ],
  });

  assert.match(html, /Pay with GCash/);
  assert.match(html, /Regular/);
  assert.match(html, /REG-001/);
  assert.match(html, /7x7/);
  assert.match(html, /7X7-001/);
  assert.doesNotMatch(html, /OLD-001/);
  assert.match(html, /data-gcash-amount[^>]*value=""/);
  assert.doesNotMatch(html, /value="200\.00"/);
  assert.doesNotMatch(html, /value="50\.00"/);
});

test('Client Web GCash keeps allocation money as exact text', async () => {
  const module = await loadClientGcashModule();
  assert.equal(typeof module.buildClientGcashIntentRequest, 'function');

  const request = module.buildClientGcashIntentRequest({
    idempotencyKey: 'web-key-12345678',
    selections: [
      { loanId: 'loan-1', amount: '90071992547409.91' },
      { loanId: 'loan-2', amount: '50.5' },
    ],
  });

  assert.deepEqual(request, {
    idempotency_key: 'web-key-12345678',
    allocations: [
      { loan_id: 'loan-1', amount: '90071992547409.91' },
      { loan_id: 'loan-2', amount: '50.50' },
    ],
  });
  assert.throws(
    () =>
      module.buildClientGcashIntentRequest({
        idempotencyKey: 'web-key-12345678',
        selections: [{ loanId: 'loan-1', amount: '0.00' }],
      }),
    /above zero/i,
  );
  assert.throws(
    () =>
      module.buildClientGcashIntentRequest({
        idempotencyKey: 'web-key-12345678',
        selections: [{ loanId: 'loan-1', amount: '10.001' }],
      }),
    /valid peso amount/i,
  );
});

test('Client Web GCash reuses one idempotency key after uncertain create failure', async () => {
  const module = await loadClientGcashModule();
  assert.equal(typeof module.createClientGcashActions, 'function');

  const calls = [];
  let keyCalls = 0;
  const keys = ['web-key-aaaaaaaa', 'web-key-bbbbbbbb'];
  const api = {
    async request(path, options = {}) {
      calls.push({ path, options });
      if (calls.length === 1) throw new Error('network uncertain');
      return {
        intent_id: 'intent/1',
        status: 'provider_pending',
        amount: '90071992547409.91',
      };
    },
  };
  const actions = module.createClientGcashActions({
    api,
    keyFactory: () => keys[keyCalls++],
  });
  const selections = [{ loanId: 'loan-1', amount: '90071992547409.91' }];

  await assert.rejects(() => actions.start(selections), /network uncertain/);
  const intent = await actions.start(selections);

  assert.equal(intent.intent_id, 'intent/1');
  assert.equal(calls[0].path, '/api/v1/client/gcash/payment-intents');
  assert.equal(calls[1].path, '/api/v1/client/gcash/payment-intents');
  assert.equal(calls[0].options.method, 'POST');
  assert.equal(calls[0].options.body.idempotency_key, 'web-key-aaaaaaaa');
  assert.equal(calls[1].options.body.idempotency_key, 'web-key-aaaaaaaa');
  assert.equal(keyCalls, 1);

  await actions.start([{ loanId: 'loan-1', amount: '1.00' }]);
  assert.equal(calls[2].options.body.idempotency_key, 'web-key-bbbbbbbb');
  assert.equal(keyCalls, 2);
});

test('Client Web GCash refreshes the protected intent and renders server status exactly', async () => {
  const module = await loadClientGcashModule();
  assert.equal(typeof module.createClientGcashActions, 'function');
  assert.equal(typeof module.renderClientGcashIntent, 'function');

  let requestedPath = null;
  const actions = module.createClientGcashActions({
    api: {
      async request(path) {
        requestedPath = path;
        return {
          intent_id: 'intent/1',
          status: 'provider_pending',
          amount: '90071992547409.91',
          checkout_url: 'https://pay.example.test/checkout/1',
          official_payment_posted: false,
        };
      },
    },
    keyFactory: () => 'unused-key',
  });

  const intent = await actions.refresh('intent/1');
  const html = module.renderClientGcashIntent(intent);

  assert.equal(
    requestedPath,
    '/api/v1/client/gcash/payment-intents/intent%2F1',
  );
  assert.match(html, /provider_pending/);
  assert.match(html, /₱90,071,992,547,409\.91/);
  assert.match(html, /https:\/\/pay\.example\.test\/checkout\/1/);
  assert.match(html, /not yet an official SPINA payment/i);
});
