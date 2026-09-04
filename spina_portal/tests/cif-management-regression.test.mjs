import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';

import { cifRecordMarkup } from '../assets/cif-management.js';


const management = {
  user: {
    role: 'management',
    permissions: ['cif.prepare', 'cif.verify', 'cif.approve'],
  },
};


test('active and superseded CIF versions never render an edit form', () => {
  for (const lifecycle_state of ['active', 'superseded']) {
    const markup = cifRecordMarkup(
      {
        cif_id: '55555555-5555-4555-8555-555555555555',
        cif_number: 'CIF-0000000001',
        client_id: '44444444-4444-4444-8444-444444444444',
        client_name: 'Safe Client',
        form_version: 1,
        lifecycle_state,
        public_status: lifecycle_state === 'active' ? 'Active' : 'Superseded',
        legal_full_name: 'Safe Client',
        has_client_signature: true,
        source_digest: 'a'.repeat(64),
        updated_at: '2026-09-04T02:00:00+00:00',
      },
      management,
    );
    assert.doesNotMatch(markup, /cif-edit-draft/);
    assert.doesNotMatch(markup, /cif-verify-form/);
    assert.doesNotMatch(markup, /cif-activate-form/);
  }
});


test('editing a signed draft requires protected signature coordinates to be re-entered', () => {
  const markup = cifRecordMarkup(
    {
      cif_id: '55555555-5555-4555-8555-555555555555',
      cif_number: 'CIF-0000000001',
      client_id: '44444444-4444-4444-8444-444444444444',
      client_name: 'Safe Client',
      form_version: 1,
      lifecycle_state: 'draft',
      public_status: 'Draft',
      legal_full_name: 'Safe Client',
      has_client_signature: true,
      source_digest: null,
      updated_at: '2026-09-04T02:00:00+00:00',
    },
    management,
  );

  assert.match(markup, /name="client_signature_reference"[^>]* required/);
  assert.match(markup, /name="client_signature_digest"[^>]* required/);
});


test('restricted results update a body container without replacing the toolbar', async () => {
  const source = await readFile(
    new URL('../assets/cif-management.js', import.meta.url),
    'utf8',
  );

  assert.match(source, /restricted-evidence-toolbar/);
  assert.match(source, /restricted-evidence-body/);
  assert.match(source, /const target = section\.querySelector\('\.restricted-evidence-body'\)/);
  assert.match(source, /target\.innerHTML = restrictedEvidenceMarkup/);
});
