import assert from 'node:assert/strict';
import test from 'node:test';

import { clientRenewalEligibilityRows } from '../assets/roles/client.js';

test('renewal eligibility displays missing signed authority without inventing zeros', () => {
  const html = clientRenewalEligibilityRows([{
    loan_number: 'REG-1', contractual_total: null, paid_amount: '1200.25',
    paid_percent: null, eligible: false,
    eligibility_message: 'A verified signed schedule is required.',
  }]);
  assert.match(html, /Unavailable/);
  assert.match(html, /1,200\.25/);
  assert.match(html, /A verified signed schedule is required/);
  assert.doesNotMatch(html, /0\.0%|₱0\.00/);
});

test('renewal eligibility displays the server percentage and safely escapes messages', () => {
  const html = clientRenewalEligibilityRows([{
    loan_number: 'REG-2', contractual_total: '3600.00', paid_amount: '1799.99',
    paid_percent: '50.0', eligible: false,
    eligibility_message: '<script>Below threshold</script>',
  }]);
  assert.match(html, /3,600\.00/);
  assert.match(html, /50\.0%/);
  assert.match(html, /&lt;script&gt;Below threshold&lt;\/script&gt;/);
  assert.doesNotMatch(html, /<script>/);
});
