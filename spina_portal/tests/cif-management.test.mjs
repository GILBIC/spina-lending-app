import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';

import {
  buildRestrictedRequestOptions,
  canMountCifWorkspace,
  cifRecordMarkup,
  cifWorkspaceMarkup,
  restrictedEvidenceMarkup,
} from '../assets/cif-management.js';


const employeeView = {
  user: { role: 'employee', permissions: ['cif.view'] },
};
const employeePrepare = {
  user: { role: 'employee', permissions: ['cif.view', 'cif.prepare'] },
};
const managementAll = {
  user: {
    role: 'management',
    permissions: [
      'cif.view',
      'cif.prepare',
      'cif.verify',
      'cif.approve',
      'cif.reverification.manage',
      'identity_evidence.view',
      'identity_evidence.record',
      'identity_evidence.review',
    ],
  },
};


test('CIF workspace mounts only for Employee or Management with a CIF permission', () => {
  assert.equal(canMountCifWorkspace('employee', employeeView), true);
  assert.equal(canMountCifWorkspace('management', managementAll), true);
  assert.equal(
    canMountCifWorkspace('collector', {
      user: { role: 'collector', permissions: ['cif.view'] },
    }),
    false,
  );
  assert.equal(
    canMountCifWorkspace('client', {
      user: { role: 'client', permissions: ['cif.view'] },
    }),
    false,
  );
  assert.equal(
    canMountCifWorkspace('employee', { user: { role: 'employee', permissions: [] } }),
    false,
  );
});


test('workspace markup exposes controls only for exact permissions', () => {
  const viewOnly = cifWorkspaceMarkup(employeeView);
  assert.match(viewOnly, /id="cif-workspace"/);
  assert.match(viewOnly, /cif-client-search/);
  assert.doesNotMatch(viewOnly, /cif-create-draft/);
  assert.doesNotMatch(viewOnly, /restricted-evidence-panel/);

  const prepare = cifWorkspaceMarkup(employeePrepare);
  assert.match(prepare, /cif-create-draft/);
  assert.doesNotMatch(prepare, /cif-verify-form/);
  assert.doesNotMatch(prepare, /cif-activate-form/);

  const management = cifWorkspaceMarkup(managementAll);
  assert.match(management, /cif-create-draft/);
  assert.match(management, /restricted-evidence-panel/);
  assert.match(management, /Raw files and full ID numbers are prohibited/);
});


test('ordinary CIF record markup never contains restricted evidence fields', () => {
  const markup = cifRecordMarkup(
    {
      cif_id: '55555555-5555-4555-8555-555555555555',
      cif_number: 'CIF-0000000001',
      client_id: '44444444-4444-4444-8444-444444444444',
      client_name: 'Safe Client',
      form_version: 1,
      public_status: 'Draft',
      lifecycle_state: 'draft',
      legal_full_name: 'Safe Client',
      phone_number: '09170000000',
      email: 'safe@example.com',
      present_address: { line1: 'Safe present', province: 'Rizal' },
      permanent_address: { line1: 'Safe permanent', province: 'Rizal' },
      livelihood_profile: { kind: 'self_employed' },
      has_client_signature: true,
      source_digest: 'a'.repeat(64),
      updated_at: '2026-09-04T02:00:00+00:00',
    },
    managementAll,
  ).toLowerCase();

  assert.match(markup, /cif-verify-form/);
  assert.match(markup, /cif-activate-form/);
  for (const forbidden of [
    'external_evidence_reference',
    'evidence_digest',
    'masked_reference',
    'verification_outcome',
    'national_id_number',
    'utility document',
    'visit photo',
    'raw_content',
  ]) {
    assert.equal(markup.includes(forbidden), false, forbidden);
  }
});


test('restricted panel uses allowlisted metadata and rejects raw-upload concepts', () => {
  const markup = restrictedEvidenceMarkup(
    [
      {
        evidence_id: '66666666-6666-4666-8666-666666666666',
        evidence_type: 'national_id_check',
        verification_outcome: 'verified',
        masked_reference: '****-****-1234',
        checked_at: '2026-09-04T02:00:00+00:00',
        retention_class: 'identity_verification',
        review_decision: null,
      },
    ],
    managementAll,
  ).toLowerCase();

  assert.match(markup, /masked reference/);
  assert.match(markup, /retention class/);
  assert.match(markup, /restricted-evidence-review/);
  for (const forbidden of [
    'type="file"',
    'name="otp"',
    'name="mpin"',
    'name="password"',
    'name="national_id_number"',
    'name="provider_payload"',
    'name="phone_contacts"',
  ]) {
    assert.equal(markup.includes(forbidden), false, forbidden);
  }
});


test('restricted requests carry purpose and a fresh request UUID', () => {
  const options = buildRestrictedRequestOptions({
    method: 'POST',
    purpose: 'compliance_review',
    requestId: '77777777-7777-4777-8777-777777777777',
    body: { decision: 'approved' },
  });

  assert.deepEqual(options, {
    method: 'POST',
    headers: {
      'X-Access-Purpose': 'compliance_review',
      'X-Request-Id': '77777777-7777-4777-8777-777777777777',
    },
    body: { decision: 'approved' },
  });
});


test('app shell owns shared CIF mounting and Client or Collector modules do not import it', async () => {
  const [app, employee, management, collector, client] = await Promise.all([
    readFile(new URL('../assets/app.js', import.meta.url), 'utf8'),
    readFile(new URL('../assets/roles/employee.js', import.meta.url), 'utf8'),
    readFile(new URL('../assets/roles/management.js', import.meta.url), 'utf8'),
    readFile(new URL('../assets/roles/collector.js', import.meta.url), 'utf8'),
    readFile(new URL('../assets/roles/client.js', import.meta.url), 'utf8'),
  ]);

  assert.match(app, /from '\.\/cif-management\.js'/);
  assert.match(app, /canMountCifWorkspace/);
  assert.match(app, /mountCifWorkspace/);
  assert.equal(employee.includes('cif-management'), false);
  assert.equal(management.includes('cif-management'), false);
  assert.equal(collector.includes('cif-management'), false);
  assert.equal(client.includes('cif-management'), false);
});
