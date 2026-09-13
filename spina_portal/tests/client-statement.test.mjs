import assert from 'node:assert/strict';
import test from 'node:test';

async function loadStatementModule() {
  try {
    return await import('../assets/client-statement.js');
  } catch {
    return {};
  }
}

test('Client statement renders exact server loan and payment values', async () => {
  const module = await loadStatementModule();
  assert.equal(typeof module.renderClientStatement, 'function');

  const html = module.renderClientStatement({
    client: {
      client_code: 'TEST-REG-001',
      client_name: 'TEST CLIENT REGULAR',
      area: 'Cardona',
      status: 'active',
    },
    loans: [
      {
        loan_id: 'loan-1',
        loan_number: 'TEST-REG-20260802',
        loan_type_name: 'Regular',
        principal: '90071992547409.91',
        daily_amount: '200.00',
        remaining_balance: '90071992547359.91',
        status: 'active',
        date_released: '2026-08-02',
        due_date: '2026-11-30',
      },
    ],
    payments: [
      {
        transaction_id: 'payment-1',
        receipt_number: 'GBC-20260806-00000010',
        loan_number: 'TEST-REG-20260802',
        loan_type_name: 'Regular',
        collection_date: '2026-08-06',
        amount: '50.00',
        official_balance: '90071992547359.91',
        status: 'posted',
        is_voided: false,
      },
    ],
  });

  assert.match(html, /Statement of Account/);
  assert.match(html, /TEST CLIENT REGULAR/);
  assert.match(html, /TEST-REG-20260802/);
  assert.match(html, /₱90,071,992,547,409\.91/);
  assert.match(html, /₱90,071,992,547,359\.91/);
  assert.match(html, /GBC-20260806-00000010/);
  assert.doesNotMatch(html, /progress/i);
  assert.doesNotMatch(html, /next payment/i);
  assert.doesNotMatch(html, /overdue/i);
  assert.doesNotMatch(html, /download/i);
});

test('Client workspace consumes the protected statement endpoint', async () => {
  const { readFile } = await import('node:fs/promises');
  const source = await readFile(new URL('../assets/roles/client.js', import.meta.url), 'utf8');
  assert.match(source, /\/api\/v1\/client\/statement/);
  assert.match(source, /renderClientStatement/);
  assert.match(source, /client-statement/);
});
