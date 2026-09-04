const ALLOWED_EVIDENCE_PURPOSES = new Set([
  'initial_cif_verification',
  'reverification',
  'discrepancy_review',
  'compliance_review',
  'legal_hold',
  'retention_disposal',
]);

const UUID_PATTERN =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

function escapeHtml(value) {
  return String(value ?? '')
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#039;');
}

function hasPermission(permissions, permission) {
  return new Set(permissions ?? []).has(permission);
}

function formatDateTime(value) {
  if (!value) return 'Not set';
  const date = new Date(value);
  if (Number.isNaN(date.valueOf())) return 'Invalid date';
  return date.toLocaleString('en-PH', {
    year: 'numeric',
    month: 'short',
    day: '2-digit',
  });
}

function label(value) {
  return String(value ?? '')
    .split('_')
    .filter(Boolean)
    .map((part) => part[0].toUpperCase() + part.slice(1))
    .join(' ');
}

function addressLine(address = {}) {
  const fields = [
    address.line1,
    address.line2,
    address.barangay,
    address.city_municipality,
    address.province,
  ].filter(Boolean);
  return fields.length ? fields.join(', ') : 'Not recorded';
}

function cifVersionRows(cifs, selectedId) {
  if (!cifs.length) {
    return '<p class="muted">No Client Information Form has been created.</p>';
  }
  return `
    <div class="cif-version-list">
      ${cifs
        .map(
          (cif) => `
            <button
              type="button"
              class="cif-version-row${cif.cif_id === selectedId ? ' is-selected' : ''}"
              data-cif-id="${escapeHtml(cif.cif_id)}"
            >
              <span><strong>${escapeHtml(cif.cif_number)}</strong> · Version ${escapeHtml(cif.form_version)}</span>
              <span class="status-pill">${escapeHtml(cif.status)}</span>
            </button>
          `,
        )
        .join('')}
    </div>
  `;
}

function actionMarkup(cif, permissions) {
  if (!cif) return '';
  const actions = [];
  if (cif.durable_state === 'draft' && hasPermission(permissions, 'cif.prepare')) {
    actions.push(
      '<button type="button" data-cif-action="edit">Edit draft</button>',
    );
  }
  if (cif.durable_state === 'draft' && hasPermission(permissions, 'cif.verify')) {
    actions.push(
      '<button type="button" data-cif-action="verify">Verify source</button>',
    );
  }
  if (cif.durable_state === 'draft' && hasPermission(permissions, 'cif.approve')) {
    actions.push(
      '<button type="button" data-cif-action="activate">Activate CIF</button>',
    );
  }
  if (cif.durable_state === 'active' && hasPermission(permissions, 'cif.reverification.open')) {
    actions.push(
      '<button type="button" data-cif-action="reverify">Require re-verification</button>',
    );
  }
  if (!actions.length) return '';
  return `<div class="button-row">${actions.join('')}</div>`;
}

function selectedCifMarkup(cif, permissions) {
  if (!cif) {
    return '<p class="muted">Select a CIF version to review its ordinary fields.</p>';
  }
  const eligibility = cif.is_eligible_for_new_credit
    ? 'Eligible for new credit'
    : 'Not eligible for new credit';
  const reverification = cif.reverification_required
    ? '<p class="warning-text">Early re-verification is required.</p>'
    : '';
  const collectionContinuity = cif.allows_existing_obligation_servicing
    ? 'Existing-loan payments remain allowed.'
    : 'Existing-loan servicing status unavailable.';

  return `
    <article class="cif-detail-card" data-selected-cif="${escapeHtml(cif.cif_id)}">
      <div class="section-heading">
        <div>
          <h3>${escapeHtml(cif.cif_number)} · Version ${escapeHtml(cif.form_version)}</h3>
          <p>${escapeHtml(cif.status)} · ${escapeHtml(eligibility)}</p>
        </div>
        <span class="status-pill">${escapeHtml(cif.status)}</span>
      </div>
      ${reverification}
      <p class="muted">${escapeHtml(collectionContinuity)}</p>
      <dl class="detail-grid">
        <div><dt>Client name</dt><dd>${escapeHtml(cif.legal_full_name)}</dd></div>
        <div><dt>Phone</dt><dd>${escapeHtml(cif.phone_number || 'Not recorded')}</dd></div>
        <div><dt>Present address</dt><dd>${escapeHtml(addressLine(cif.present_address))}</dd></div>
        <div><dt>Livelihood</dt><dd>${escapeHtml(cif.livelihood_profile?.occupation || 'Not recorded')}</dd></div>
        <div><dt>Expiry</dt><dd>${escapeHtml(formatDateTime(cif.expires_at))}</dd></div>
        <div><dt>Draft revision</dt><dd>${escapeHtml(cif.draft_revision)}</dd></div>
      </dl>
      ${actionMarkup(cif, permissions)}
    </article>
  `;
}

function evidenceMarkup(evidence, permissions) {
  if (!hasPermission(permissions, 'identity_evidence.view')) return '';
  const rows = evidence.length
    ? evidence
        .map(
          (item) => `
            <div class="restricted-evidence-row">
              <div>
                <strong>${escapeHtml(label(item.evidence_type))}</strong>
                <p>${escapeHtml(label(item.verification_result))} · ${escapeHtml(item.masked_reference || 'No masked reference')}</p>
              </div>
              <div>
                <span class="status-pill">${escapeHtml(label(item.review_state))}</span>
                <small>${escapeHtml(formatDateTime(item.checked_at))}</small>
              </div>
            </div>
          `,
        )
        .join('')
    : '<p class="muted">No restricted verification metadata is loaded for this purpose.</p>';
  return `
    <section class="section-card restricted-evidence-panel">
      <div class="section-heading">
        <div>
          <h3>Restricted verification evidence</h3>
          <p>Metadata only. Access requires an approved purpose and is logged.</p>
        </div>
      </div>
      ${rows}
      ${
        hasPermission(permissions, 'identity_evidence.manage')
          ? '<button type="button" data-cif-action="add-evidence">Add evidence metadata</button>'
          : ''
      }
    </section>
  `;
}

export function buildRestrictedEvidenceHeaders({ purpose, requestId }) {
  const normalizedPurpose = String(purpose ?? '').trim().toLowerCase();
  if (!ALLOWED_EVIDENCE_PURPOSES.has(normalizedPurpose)) {
    throw new Error('A valid restricted evidence purpose is required.');
  }
  const normalizedRequestId = String(requestId ?? '').trim();
  if (!UUID_PATTERN.test(normalizedRequestId)) {
    throw new Error('A valid restricted evidence request id is required.');
  }
  return {
    'X-Evidence-Purpose': normalizedPurpose,
    'X-Request-Id': normalizedRequestId,
  };
}

export function cifManagementMarkup({
  clientId = '',
  cifs = [],
  selectedCif = null,
  permissions = [],
  evidence = [],
} = {}) {
  const canPrepare = hasPermission(permissions, 'cif.prepare');
  return `
    <section class="section-card cif-management" data-client-id="${escapeHtml(clientId)}">
      <div class="section-heading">
        <div>
          <h2>Client Information Form</h2>
          <p>Permanent client information is versioned separately from each loan application.</p>
        </div>
        ${canPrepare ? '<button type="button" data-cif-action="new">New CIF draft</button>' : ''}
      </div>
      <div class="cif-management-layout">
        <aside>${cifVersionRows(cifs, selectedCif?.cif_id)}</aside>
        <div>${selectedCifMarkup(selectedCif, permissions)}</div>
      </div>
    </section>
    ${evidenceMarkup(evidence, permissions)}
  `;
}
