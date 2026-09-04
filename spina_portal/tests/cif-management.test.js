import test from 'node:test';
import assert from 'node:assert/strict';

import {
  buildRestrictedEvidenceHeaders,
  cifManagementMarkup,
} from '../assets/cif-management.js';

const activeCif = {
  cif_id: '11111111-1111-1111-1111-111111111111',
  cif_number: 'CIF-0000000001',
  form_version: 1,
  durable_state: 'active',
  status: 'Active',
  is_eligible_for_new_credit: true,
  reverification_required: false,
  allows_existing_obligation_servicing: true,
  expires_at: '2031-09-04T00:00:00+00:00',
  legal_full_name: 'Maria Dela Cruz',
  phone_number: '09171234567',
  present_address: { barangay: 'San Roque', city_municipality: 'Cardona' },
  livelihood_profile: { occupation: 'Store owner' },
  draft_revision: 1,
};

test('renders lifecycle and collection-continuity status clearly', () => {
  const html = cifManagementMarkup({
    clientId: 'client-1',
    cifs: [activeCif],
    selectedCif: activeCif,
    permissions: ['cif.view'],
  });

  assert.match(html, /CIF-0000000001/);
  assert.match(html, /Active/);
  assert.match(html, /Eligible for new credit/);
  assert.match(html, /Existing-loan payments remain allowed/);
});

test('hides workflow actions without exact permissions', () => {
  const html = cifManagementMarkup({
    clientId: 'client-1',
    cifs: [activeCif],
    selectedCif: activeCif,
    permissions: ['cif.view'],
  });

  assert.doesNotMatch(html, /data-cif-action="verify"/);
  assert.doesNotMatch(html, /data-cif-action="activate"/);
  assert.doesNotMatch(html, /Restricted verification evidence/);
});

test('renders restricted metadata without raw upload controls', () => {
  const html = cifManagementMarkup({
    clientId: 'client-1',
    cifs: [activeCif],
    selectedCif: activeCif,
    permissions: ['cif.view', 'identity_evidence.view'],
    evidence: [
      {
        evidence_type: 'national_id_check',
        verification_result: 'verified',
        masked_reference: '****-****-1234',
        review_state: 'verified',
        checked_at: '2026-09-04T00:00:00+00:00',
      },
    ],
  });

  assert.match(html, /Restricted verification evidence/);
  assert.match(html, /\*\*\*\*-\*\*\*\*-1234/);
  assert.doesNotMatch(html, /type="file"/i);
  assert.doesNotMatch(html, /raw document/i);
  assert.doesNotMatch(html, /national id number/i);
});

test('escapes client-provided values', () => {
  const html = cifManagementMarkup({
    clientId: 'client-1',
    cifs: [],
    selectedCif: {
      ...activeCif,
      legal_full_name: '<script>alert(1)</script>',
    },
    permissions: ['cif.view'],
  });

  assert.doesNotMatch(html, /<script>/);
  assert.match(html, /&lt;script&gt;/);
});

test('builds purpose-bound restricted request headers', () => {
  assert.deepEqual(
    buildRestrictedEvidenceHeaders({
      purpose: 'compliance_review',
      requestId: 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa',
    }),
    {
      'X-Evidence-Purpose': 'compliance_review',
      'X-Request-Id': 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa',
    },
  );
});

test('rejects missing purpose or malformed request id', () => {
  assert.throws(
    () => buildRestrictedEvidenceHeaders({ purpose: '', requestId: 'bad' }),
    /purpose/i,
  );
  assert.throws(
    () => buildRestrictedEvidenceHeaders({
      purpose: 'compliance_review',
      requestId: 'bad',
    }),
    /request id/i,
  );
});
