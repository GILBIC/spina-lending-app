import {
  asArray,
  badge,
  emptyState,
  errorCard,
  escapeHtml,
  formatDate,
  formatDateTime,
  hasPermission,
  loadingPanel,
  setButtonBusy,
  showToast,
  titleCase,
} from './ui.js';


const CIF_PERMISSIONS = Object.freeze([
  'cif.view',
  'cif.prepare',
  'cif.verify',
  'cif.approve',
  'cif.reverification.manage',
  'identity_evidence.view',
  'identity_evidence.record',
  'identity_evidence.review',
]);

const ACCESS_PURPOSES = Object.freeze([
  ['cif_verification', 'CIF verification'],
  ['cif_reverification', 'CIF re-verification'],
  ['compliance_review', 'Compliance review'],
  ['dpo_audit', 'DPO audit'],
]);

const EVIDENCE_TYPES = Object.freeze([
  ['national_id_check', 'National ID Check / eVerify outcome'],
  ['government_id_metadata', 'Government ID metadata'],
  ['utility_proof', 'Utility residence proof'],
  ['residence_visit', 'Residence visit evidence'],
  ['approved_exception', 'Approved exception'],
]);

function permissionSet(session) {
  return new Set([
    ...asArray(session?.permissions),
    ...asArray(session?.user?.permissions),
  ].map((value) => String(value).trim()).filter(Boolean));
}

export function canMountCifWorkspace(role, session) {
  const normalizedRole = String(role || '').trim().toLowerCase();
  if (!['employee', 'management'].includes(normalizedRole)) return false;
  const permissions = permissionSet(session);
  return CIF_PERMISSIONS.some((permission) => permissions.has(permission));
}

function addressText(address) {
  if (!address || typeof address !== 'object') return '—';
  const ordered = [
    address.line1,
    address.line2,
    address.barangay,
    address.city_municipality,
    address.province,
    address.postal_code,
    address.landmark,
  ].map((value) => String(value || '').trim()).filter(Boolean);
  return ordered.length ? ordered.join(', ') : '—';
}

function optionMarkup(options, selected = '') {
  return options.map(([value, label]) =>
    `<option value="${escapeHtml(value)}"${value === selected ? ' selected' : ''}>${escapeHtml(label)}</option>`,
  ).join('');
}

function dateTimeLocalValue(value) {
  if (!value) return '';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '';
  const local = new Date(date.getTime() - date.getTimezoneOffset() * 60_000);
  return local.toISOString().slice(0, 16);
}

function draftFormMarkup({ clientId = '', record = null, session }) {
  if (!hasPermission(session, 'cif.prepare')) return '';
  const draft = record || {};
  const present = draft.present_address || {};
  const permanent = draft.permanent_address || {};
  const livelihood = draft.livelihood_profile || {};
  const isEdit = Boolean(record?.cif_id);
  return `<form class="entry-form cif-draft-form${isEdit ? ' cif-edit-draft' : ' cif-create-draft'}"
      data-client-id="${escapeHtml(clientId || draft.client_id || '')}"
      data-cif-id="${escapeHtml(draft.cif_id || '')}"
      data-expected-updated-at="${escapeHtml(draft.updated_at || '')}">
    <div class="section-heading"><div><h3>${isEdit ? 'Edit draft CIF' : 'Create draft CIF'}</h3><p>Ordinary client information only. Identity evidence belongs in the restricted panel.</p></div></div>
    <div class="form-grid">
      <label>Legal full name<input name="legal_full_name" maxlength="200" required value="${escapeHtml(draft.legal_full_name || '')}" /></label>
      <label>Birth date<input name="birth_date" type="date" value="${escapeHtml(draft.birth_date || '')}" /></label>
      <label>Place of birth<input name="place_of_birth" maxlength="200" value="${escapeHtml(draft.place_of_birth || '')}" /></label>
      <label>Nationality<input name="nationality" maxlength="100" value="${escapeHtml(draft.nationality || '')}" /></label>
      <label>Civil status<input name="civil_status" maxlength="50" value="${escapeHtml(draft.civil_status || '')}" /></label>
      <label>Phone number<input name="phone_number" maxlength="40" value="${escapeHtml(draft.phone_number || '')}" /></label>
      <label>Email<input name="email" type="email" maxlength="254" value="${escapeHtml(draft.email || '')}" /></label>
      <label>Form schema version<input name="form_schema_version" maxlength="50" required value="${escapeHtml(draft.form_schema_version || '1')}" /></label>
    </div>
    <fieldset><legend>Present address</legend><div class="form-grid">
      <label>Address line<input name="present_line1" maxlength="300" value="${escapeHtml(present.line1 || '')}" /></label>
      <label>Barangay<input name="present_barangay" maxlength="200" value="${escapeHtml(present.barangay || '')}" /></label>
      <label>City / municipality<input name="present_city" maxlength="200" value="${escapeHtml(present.city_municipality || '')}" /></label>
      <label>Province<input name="present_province" maxlength="200" value="${escapeHtml(present.province || '')}" /></label>
      <label>Postal code<input name="present_postal_code" maxlength="30" value="${escapeHtml(present.postal_code || '')}" /></label>
      <label>Landmark<input name="present_landmark" maxlength="300" value="${escapeHtml(present.landmark || '')}" /></label>
    </div></fieldset>
    <fieldset><legend>Permanent address</legend><label class="check-row"><input name="same_as_present_address" type="checkbox"${draft.same_as_present_address ? ' checked' : ''} /> Same as present address</label><div class="form-grid">
      <label>Address line<input name="permanent_line1" maxlength="300" value="${escapeHtml(permanent.line1 || '')}" /></label>
      <label>Barangay<input name="permanent_barangay" maxlength="200" value="${escapeHtml(permanent.barangay || '')}" /></label>
      <label>City / municipality<input name="permanent_city" maxlength="200" value="${escapeHtml(permanent.city_municipality || '')}" /></label>
      <label>Province<input name="permanent_province" maxlength="200" value="${escapeHtml(permanent.province || '')}" /></label>
      <label>Postal code<input name="permanent_postal_code" maxlength="30" value="${escapeHtml(permanent.postal_code || '')}" /></label>
      <label>Landmark<input name="permanent_landmark" maxlength="300" value="${escapeHtml(permanent.landmark || '')}" /></label>
    </div></fieldset>
    <fieldset><legend>Basic livelihood profile</legend><div class="form-grid">
      <label>Kind<input name="livelihood_kind" maxlength="100" value="${escapeHtml(livelihood.kind || '')}" /></label>
      <label>Employer or business<input name="livelihood_employer" maxlength="300" value="${escapeHtml(livelihood.employer_or_business || '')}" /></label>
      <label>Position or activity<input name="livelihood_position" maxlength="300" value="${escapeHtml(livelihood.position_or_activity || '')}" /></label>
      <label>Years active<input name="livelihood_years" type="number" min="0" max="100" value="${escapeHtml(livelihood.years_active ?? '')}" /></label>
      <label class="span-two">Description<textarea name="livelihood_description" maxlength="300">${escapeHtml(livelihood.description || '')}</textarea></label>
    </div></fieldset>
    <fieldset><legend>Privacy and client signature reference</legend><div class="form-grid">
      <label>Privacy notice version<input name="privacy_notice_version" maxlength="100" value="${escapeHtml(draft.privacy_notice_version || '')}" /></label>
      <label>Acknowledged at<input name="privacy_acknowledged_at" type="datetime-local" value="${escapeHtml(dateTimeLocalValue(draft.privacy_acknowledged_at))}" /></label>
      <label>Restricted signature object reference<input name="client_signature_reference" maxlength="500" placeholder="restricted-signature://…" /></label>
      <label>Signature SHA-256<input name="client_signature_digest" minlength="64" maxlength="64" pattern="[0-9a-f]{64}" placeholder="64 lowercase hexadecimal characters" /></label>
    </div><p class="meta">${isEdit && draft.has_client_signature ? 'The current version has a signature reference. Re-enter both reference and digest only when replacing the draft source.' : 'No signature image is displayed or stored in this ordinary form.'}</p></fieldset>
    <button class="button button-primary" type="submit">${isEdit ? 'Save draft changes' : 'Create draft CIF'}</button>
  </form>`;
}

export function cifRecordMarkup(record, session) {
  if (!record) return '';
  const draft = String(record.lifecycle_state || '').toLowerCase() === 'draft';
  const canVerify = draft && hasPermission(session, 'cif.verify');
  const canApprove = draft && Boolean(record.source_digest) && hasPermission(session, 'cif.approve');
  const controls = [
    canVerify ? `<form class="entry-form cif-verify-form" data-cif-id="${escapeHtml(record.cif_id)}" data-expected-updated-at="${escapeHtml(record.updated_at || '')}"><label>Verification note<textarea name="review_note" minlength="3" maxlength="1000" required></textarea></label><button class="button button-secondary" type="submit">Verify frozen source</button></form>` : '',
    canApprove ? `<form class="entry-form cif-activate-form" data-cif-id="${escapeHtml(record.cif_id)}" data-source-digest="${escapeHtml(record.source_digest)}"><label>Approval note<textarea name="review_note" minlength="3" maxlength="1000" required></textarea></label><button class="button button-primary" type="submit">Activate CIF</button></form>` : '',
  ].join('');

  return `<article class="list-item cif-record" data-cif-id="${escapeHtml(record.cif_id || '')}">
    <div class="section-heading"><div><strong>${escapeHtml(record.cif_number || 'CIF')}</strong><div class="meta">Version ${escapeHtml(record.form_version ?? '—')} · ${escapeHtml(record.client_name || '')}</div></div>${badge(record.public_status || record.lifecycle_state || 'unknown')}</div>
    <div class="detail-grid">
      <div class="detail-item"><span>Legal name</span><strong>${escapeHtml(record.legal_full_name || '—')}</strong></div>
      <div class="detail-item"><span>Birth date</span><strong>${formatDate(record.birth_date)}</strong></div>
      <div class="detail-item"><span>Phone</span><strong>${escapeHtml(record.phone_number || '—')}</strong></div>
      <div class="detail-item"><span>Email</span><strong>${escapeHtml(record.email || '—')}</strong></div>
      <div class="detail-item"><span>Effective</span><strong>${formatDateTime(record.effective_at)}</strong></div>
      <div class="detail-item"><span>Expires</span><strong>${formatDateTime(record.expires_at)}</strong></div>
      <div class="detail-item"><span>Client signature</span><strong>${record.has_client_signature ? 'Recorded' : 'Not recorded'}</strong></div>
      <div class="detail-item"><span>New-credit eligibility</span><strong>${record.is_eligible_for_new_credit ? 'Eligible' : 'Not eligible'}</strong></div>
    </div>
    <p><strong>Present address:</strong> ${escapeHtml(addressText(record.present_address))}</p>
    <p><strong>Permanent address:</strong> ${escapeHtml(addressText(record.permanent_address))}</p>
    <p class="meta">Livelihood: ${escapeHtml(titleCase(record.livelihood_profile?.kind || 'not supplied'))} · Updated ${formatDateTime(record.updated_at)}</p>
    ${draftFormMarkup({ clientId: record.client_id, record, session })}
    ${controls}
  </article>`;
}

function requirementMarkup(items) {
  if (!items.length) return emptyState('No CIF re-verification requirement is recorded.');
  return `<div class="list-stack">${items.map((item) => `<article class="list-item"><div class="section-heading"><div><strong>${escapeHtml(titleCase(item.reason))}</strong><div class="meta">Opened ${formatDateTime(item.opened_at)}</div></div>${badge(item.status)}</div><p>${escapeHtml(item.note || '')}</p><span class="meta">Severity: ${escapeHtml(titleCase(item.severity || 'standard'))}</span></article>`).join('')}</div>`;
}

function clientResultMarkup(items) {
  if (!items.length) return emptyState('No client matches the current search.');
  return `<div class="list-stack">${items.map((client) => `<button class="list-item cif-select-client" type="button" data-client-id="${escapeHtml(client.client_id)}" data-client-code="${escapeHtml(client.client_code)}" data-client-name="${escapeHtml(client.client_name)}"><div class="section-heading"><div><strong>${escapeHtml(client.client_name || 'Client')}</strong><div class="meta">${escapeHtml(client.client_code || '')} · ${escapeHtml(client.area || '')}</div></div>${badge(client.active_cif_status || 'No active CIF')}</div><span class="meta">New-credit eligibility: ${client.is_eligible_for_new_credit ? 'Eligible' : 'Not eligible'}</span></button>`).join('')}</div>`;
}

function restrictedRecordForm({ clientId = '', cifId = '' } = {}) {
  return `<form class="entry-form restricted-evidence-record" data-cif-id="${escapeHtml(cifId)}">
    <div class="section-heading"><div><h4>Record restricted metadata</h4><p>Raw files and full ID numbers are prohibited. Store only an approved external restricted-object reference and its digest.</p></div></div>
    <input type="hidden" name="client_id" value="${escapeHtml(clientId)}" />
    <div class="form-grid">
      <label>Evidence type<select name="evidence_type">${optionMarkup(EVIDENCE_TYPES)}</select></label>
      <label>Verification method<input name="verification_method" maxlength="120" required /></label>
      <label>Outcome<select name="verification_outcome"><option value="verified">Verified</option><option value="not_verified">Not verified</option><option value="inconclusive">Inconclusive</option><option value="exception_approved">Exception approved</option></select></label>
      <label>Checked at<input name="checked_at" type="datetime-local" required /></label>
      <label>Document date<input name="document_date" type="date" /></label>
      <label>Document expiry<input name="document_expires_at" type="date" /></label>
      <label>Masked reference<input name="masked_reference" maxlength="120" placeholder="****-****-1234" required /></label>
      <label>Restricted object reference<input name="external_evidence_reference" maxlength="500" required /></label>
      <label>Evidence SHA-256<input name="evidence_digest" minlength="64" maxlength="64" pattern="[0-9a-f]{64}" required /></label>
      <label>Retention class<select name="retention_class"><option value="identity_verification">Identity verification</option><option value="residence_verification">Residence verification</option><option value="approved_exception">Approved exception</option></select></label>
      <label>Retain until<input name="retain_until" type="date" required /></label>
      <label class="check-row"><input name="legal_hold" type="checkbox" /> Legal hold</label>
    </div>
    <button class="button button-primary" type="submit">Record metadata</button>
  </form>`;
}

export function restrictedEvidenceMarkup(items, session, context = {}) {
  const records = asArray(items);
  const canRecord = hasPermission(session, 'identity_evidence.record');
  const canReview = hasPermission(session, 'identity_evidence.review');
  const list = records.length ? `<div class="list-stack">${records.map((item) => `<article class="list-item restricted-evidence-record-row" data-evidence-id="${escapeHtml(item.evidence_id)}"><div class="section-heading"><div><strong>${escapeHtml(titleCase(item.evidence_type || 'Evidence'))}</strong><div class="meta">Checked ${formatDateTime(item.checked_at)}</div></div>${badge(item.review_decision || item.verification_outcome || 'pending')}</div><div class="detail-grid"><div class="detail-item"><span>Masked reference</span><strong>${escapeHtml(item.masked_reference || '—')}</strong></div><div class="detail-item"><span>Retention class</span><strong>${escapeHtml(titleCase(item.retention_class || '—'))}</strong></div><div class="detail-item"><span>Document date</span><strong>${formatDate(item.document_date)}</strong></div><div class="detail-item"><span>Document expiry</span><strong>${formatDate(item.document_expires_at)}</strong></div></div>${canReview && !item.review_decision ? `<form class="entry-form restricted-evidence-review" data-evidence-id="${escapeHtml(item.evidence_id)}"><label>Decision<select name="decision"><option value="approved">Approve</option><option value="rejected">Reject</option></select></label><label>Review note<textarea name="review_note" minlength="3" maxlength="1000" required></textarea></label><button class="button button-secondary" type="submit">Save independent review</button></form>` : ''}</article>`).join('')}</div>` : emptyState('No restricted evidence metadata is recorded for this CIF.');
  return `${list}${canRecord ? restrictedRecordForm(context) : ''}`;
}

export function cifWorkspaceMarkup(session) {
  const canView = hasPermission(session, 'cif.view');
  const canPrepare = hasPermission(session, 'cif.prepare');
  const hasRestricted = ['identity_evidence.view', 'identity_evidence.record', 'identity_evidence.review'].some((permission) => hasPermission(session, permission));
  return `<section class="section-card" id="cif-workspace">
    <div class="section-heading"><div><h2>Client Information Forms</h2><p>Versioned client identity and residence information, separate from every loan application.</p></div></div>
    ${canView ? `<form class="search-bar cif-client-search"><input name="query" minlength="1" maxlength="200" placeholder="Client code or name" required /><button class="button button-primary" type="submit">Search clients</button></form><div class="cif-client-results">${emptyState('Search for a client to review CIF versions.')}</div>` : '<div class="notice-card warning">Your account cannot view CIF records.</div>'}
    ${canPrepare ? '<div class="cif-create-draft notice-card">Select a client to create or edit a draft CIF.</div>' : ''}
    <div class="cif-client-detail"></div>
    ${hasRestricted ? `<details class="restricted-evidence-panel"><summary>Restricted verification evidence</summary><div class="notice-card warning"><strong>Restricted metadata only.</strong> Raw files and full ID numbers are prohibited. Every access requires a purpose and is logged.</div><div class="restricted-evidence-content">${emptyState('Select a CIF, purpose, then load restricted metadata.')}</div></details>` : ''}
  </section>`;
}

export function buildRestrictedRequestOptions({ method = 'GET', purpose, requestId, body } = {}) {
  const options = {
    method: String(method || 'GET').toUpperCase(),
    headers: {
      'X-Access-Purpose': String(purpose || '').trim(),
      'X-Request-Id': String(requestId || '').trim(),
    },
  };
  if (body !== undefined) options.body = body;
  return options;
}

function uuid() {
  if (typeof globalThis.crypto?.randomUUID === 'function') return globalThis.crypto.randomUUID();
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (character) => {
    const random = Math.floor(Math.random() * 16);
    const value = character === 'x' ? random : (random & 0x3) | 0x8;
    return value.toString(16);
  });
}

function optionalText(data, name) {
  const value = String(data.get(name) || '').trim();
  return value || null;
}

function addressFromForm(data, prefix) {
  return Object.fromEntries([
    ['line1', optionalText(data, `${prefix}_line1`)],
    ['barangay', optionalText(data, `${prefix}_barangay`)],
    ['city_municipality', optionalText(data, `${prefix}_city`)],
    ['province', optionalText(data, `${prefix}_province`)],
    ['postal_code', optionalText(data, `${prefix}_postal_code`)],
    ['landmark', optionalText(data, `${prefix}_landmark`)],
  ].filter(([, value]) => value != null));
}

function livelihoodFromForm(data) {
  const years = optionalText(data, 'livelihood_years');
  return Object.fromEntries([
    ['kind', optionalText(data, 'livelihood_kind')],
    ['employer_or_business', optionalText(data, 'livelihood_employer')],
    ['position_or_activity', optionalText(data, 'livelihood_position')],
    ['description', optionalText(data, 'livelihood_description')],
    ['years_active', years == null ? null : Number(years)],
  ].filter(([, value]) => value != null && value !== ''));
}

function toIso(value) {
  const normalized = String(value || '').trim();
  if (!normalized) return null;
  const date = new Date(normalized);
  return Number.isNaN(date.getTime()) ? null : date.toISOString();
}

function draftBody(form) {
  const data = new FormData(form);
  const same = data.get('same_as_present_address') === 'on';
  const present = addressFromForm(data, 'present');
  return {
    legal_full_name: String(data.get('legal_full_name') || '').trim(),
    birth_date: optionalText(data, 'birth_date'),
    place_of_birth: String(data.get('place_of_birth') || '').trim(),
    nationality: String(data.get('nationality') || '').trim(),
    civil_status: String(data.get('civil_status') || '').trim(),
    phone_number: String(data.get('phone_number') || '').trim(),
    email: optionalText(data, 'email'),
    present_address: present,
    permanent_address: same ? present : addressFromForm(data, 'permanent'),
    same_as_present_address: same,
    livelihood_profile: livelihoodFromForm(data),
    privacy_notice_version: String(data.get('privacy_notice_version') || '').trim(),
    privacy_acknowledged_at: toIso(data.get('privacy_acknowledged_at')),
    client_signature_reference: String(data.get('client_signature_reference') || '').trim(),
    client_signature_digest: optionalText(data, 'client_signature_digest'),
    form_schema_version: String(data.get('form_schema_version') || '1').trim(),
  };
}

function selectedPurpose(section) {
  return section.querySelector('.restricted-access-purpose')?.value || 'cif_verification';
}

function restrictedToolbar(forms, session) {
  if (!forms.length || !hasPermission(session, 'identity_evidence.view')) return '';
  return `<div class="entry-form restricted-evidence-toolbar"><label>CIF version<select class="restricted-cif-selector">${forms.map((form) => `<option value="${escapeHtml(form.cif_id)}" data-client-id="${escapeHtml(form.client_id)}">${escapeHtml(form.cif_number)} · ${escapeHtml(form.public_status)}</option>`).join('')}</select></label><label>Access purpose<select class="restricted-access-purpose">${optionMarkup(ACCESS_PURPOSES)}</select></label><button class="button button-secondary restricted-evidence-load" type="button">Load restricted metadata</button></div>`;
}

function renderClientDetail(section, session, selected, payload) {
  const forms = asArray(payload?.forms);
  const requirements = asArray(payload?.reverification);
  const hasDraft = forms.some((item) => String(item.lifecycle_state).toLowerCase() === 'draft');
  const reverifyForm = hasPermission(session, 'cif.reverification.manage') ? `<form class="entry-form cif-reverification-form" data-client-id="${escapeHtml(selected.client_id)}"><label>Reason<select name="reason"><option value="material_identity_change">Material identity change</option><option value="address_change">Address change</option><option value="contact_change">Contact change</option><option value="document_expiry">Document expiry</option><option value="discrepancy">Discrepancy</option><option value="suspicious_activity">Suspicious activity</option><option value="approved_risk_event">Approved risk event</option></select></label><label>Severity<select name="severity"><option value="standard">Standard</option><option value="high">High</option></select></label><label>Note<textarea name="note" minlength="3" maxlength="1000" required></textarea></label><button class="button button-secondary" type="submit">Open re-verification</button></form>` : '';
  section.querySelector('.cif-client-detail').innerHTML = `<article class="data-card"><div class="section-heading"><div><h3>${escapeHtml(selected.client_name || 'Client')}</h3><p>${escapeHtml(selected.client_code || '')}</p></div></div>${!hasDraft ? draftFormMarkup({ clientId: selected.client_id, session }) : ''}</article><div class="section-heading"><div><h3>CIF versions</h3></div></div>${forms.length ? `<div class="list-stack">${forms.map((form) => cifRecordMarkup(form, session)).join('')}</div>` : emptyState('No CIF version is recorded for this client.')}${reverifyForm}<div class="section-heading"><div><h3>Re-verification requirements</h3></div></div>${requirementMarkup(requirements)}`;
  const restricted = section.querySelector('.restricted-evidence-content');
  if (restricted) restricted.innerHTML = `${restrictedToolbar(forms, session)}${emptyState('Choose a CIF and load restricted metadata for an approved purpose.')}`;
}

async function loadClient(context, section, session, selected) {
  const target = section.querySelector('.cif-client-detail');
  target.innerHTML = loadingPanel('Loading CIF versions…');
  try {
    const payload = await context.api.request(`/api/v1/management/clients/${encodeURIComponent(selected.client_id)}/cifs`);
    renderClientDetail(section, session, selected, payload);
    bindCifActions(context, section, session, selected);
  } catch (error) {
    target.innerHTML = errorCard(error);
  }
}

function bindSearch(context, section, session) {
  const form = section.querySelector('.cif-client-search');
  form?.addEventListener('submit', async (event) => {
    event.preventDefault();
    const button = form.querySelector('button[type="submit"]');
    const query = String(new FormData(form).get('query') || '').trim();
    const target = section.querySelector('.cif-client-results');
    setButtonBusy(button, true, 'Searching…');
    target.innerHTML = loadingPanel('Searching clients…');
    try {
      const clients = asArray(await context.api.request(`/api/v1/management/cif-clients?q=${encodeURIComponent(query)}`));
      target.innerHTML = clientResultMarkup(clients);
      for (const select of target.querySelectorAll('.cif-select-client')) {
        select.addEventListener('click', () => loadClient(context, section, session, {
          client_id: select.dataset.clientId,
          client_code: select.dataset.clientCode,
          client_name: select.dataset.clientName,
        }));
      }
    } catch (error) {
      target.innerHTML = errorCard(error);
    } finally {
      setButtonBusy(button, false);
    }
  });
}

function bindCifActions(context, section, session, selected) {
  for (const form of section.querySelectorAll('.cif-draft-form')) {
    form.addEventListener('submit', async (event) => {
      event.preventDefault();
      const button = form.querySelector('button[type="submit"]');
      setButtonBusy(button, true, 'Saving…');
      try {
        const cifId = form.dataset.cifId;
        const path = cifId
          ? `/api/v1/management/cifs/${encodeURIComponent(cifId)}`
          : `/api/v1/management/clients/${encodeURIComponent(form.dataset.clientId)}/cifs`;
        const body = cifId ? {
          expected_updated_at: form.dataset.expectedUpdatedAt,
          draft: draftBody(form),
        } : draftBody(form);
        await context.api.request(path, { method: cifId ? 'PATCH' : 'POST', body });
        showToast(cifId ? 'Draft CIF updated.' : 'Draft CIF created.', 'success');
        await loadClient(context, section, session, selected);
      } catch (error) {
        showToast(error.message, 'error');
        setButtonBusy(button, false);
      }
    });
  }

  for (const form of section.querySelectorAll('.cif-verify-form')) {
    form.addEventListener('submit', async (event) => {
      event.preventDefault();
      const button = form.querySelector('button[type="submit"]');
      const note = String(new FormData(form).get('review_note') || '').trim();
      if (!globalThis.confirm?.('Verify and freeze the current ordinary CIF source?')) return;
      setButtonBusy(button, true, 'Verifying…');
      try {
        await context.api.request(`/api/v1/management/cifs/${encodeURIComponent(form.dataset.cifId)}/verify`, {
          method: 'POST',
          body: { expected_updated_at: form.dataset.expectedUpdatedAt, review_note: note },
        });
        showToast('CIF source verified.', 'success');
        await loadClient(context, section, session, selected);
      } catch (error) {
        showToast(error.message, 'error');
        setButtonBusy(button, false);
      }
    });
  }

  for (const form of section.querySelectorAll('.cif-activate-form')) {
    form.addEventListener('submit', async (event) => {
      event.preventDefault();
      const button = form.querySelector('button[type="submit"]');
      const note = String(new FormData(form).get('review_note') || '').trim();
      if (!globalThis.confirm?.('Activate this verified CIF and supersede any prior active version?')) return;
      setButtonBusy(button, true, 'Activating…');
      try {
        await context.api.request(`/api/v1/management/cifs/${encodeURIComponent(form.dataset.cifId)}/activate`, {
          method: 'POST',
          body: { expected_source_digest: form.dataset.sourceDigest, review_note: note },
        });
        showToast('CIF activated.', 'success');
        await loadClient(context, section, session, selected);
      } catch (error) {
        showToast(error.message, 'error');
        setButtonBusy(button, false);
      }
    });
  }

  const reverify = section.querySelector('.cif-reverification-form');
  reverify?.addEventListener('submit', async (event) => {
    event.preventDefault();
    const data = new FormData(reverify);
    const button = reverify.querySelector('button[type="submit"]');
    setButtonBusy(button, true, 'Opening…');
    try {
      await context.api.request(`/api/v1/management/clients/${encodeURIComponent(reverify.dataset.clientId)}/cif-reverification`, {
        method: 'POST',
        body: {
          reason: data.get('reason'),
          severity: data.get('severity'),
          note: String(data.get('note') || '').trim(),
        },
      });
      showToast('CIF re-verification requirement opened.', 'success');
      await loadClient(context, section, session, selected);
    } catch (error) {
      showToast(error.message, 'error');
      setButtonBusy(button, false);
    }
  });

  bindRestrictedActions(context, section, session, selected);
}

function bindRestrictedActions(context, section, session, selected) {
  const load = section.querySelector('.restricted-evidence-load');
  load?.addEventListener('click', async () => {
    const selector = section.querySelector('.restricted-cif-selector');
    const cifId = selector?.value;
    if (!cifId) return;
    const target = section.querySelector('.restricted-evidence-content');
    const toolbar = restrictedToolbar(asArray(selector.options).map((option) => ({
      cif_id: option.value,
      client_id: option.dataset.clientId,
      cif_number: option.textContent,
      public_status: '',
    })), session);
    setButtonBusy(load, true, 'Loading…');
    try {
      const records = await context.api.request(
        `/api/v1/management/cifs/${encodeURIComponent(cifId)}/verification-evidence`,
        buildRestrictedRequestOptions({
          purpose: selectedPurpose(section),
          requestId: uuid(),
        }),
      );
      target.innerHTML = `${toolbar}${restrictedEvidenceMarkup(records, session, { clientId: selected.client_id, cifId })}`;
      bindRestrictedActions(context, section, session, selected);
    } catch (error) {
      target.innerHTML = `${toolbar}${errorCard(error)}`;
      bindRestrictedActions(context, section, session, selected);
    }
  });

  const record = section.querySelector('.restricted-evidence-record');
  record?.addEventListener('submit', async (event) => {
    event.preventDefault();
    const data = new FormData(record);
    const button = record.querySelector('button[type="submit"]');
    setButtonBusy(button, true, 'Recording…');
    try {
      await context.api.request(
        `/api/v1/management/cifs/${encodeURIComponent(record.dataset.cifId)}/verification-evidence`,
        buildRestrictedRequestOptions({
          method: 'POST',
          purpose: selectedPurpose(section),
          requestId: uuid(),
          body: {
            client_id: data.get('client_id'),
            evidence_type: data.get('evidence_type'),
            verification_method: String(data.get('verification_method') || '').trim(),
            verification_outcome: data.get('verification_outcome'),
            checked_at: toIso(data.get('checked_at')),
            document_date: optionalText(data, 'document_date'),
            document_expires_at: optionalText(data, 'document_expires_at'),
            masked_reference: String(data.get('masked_reference') || '').trim(),
            external_evidence_reference: String(data.get('external_evidence_reference') || '').trim(),
            evidence_digest: String(data.get('evidence_digest') || '').trim(),
            retention_class: data.get('retention_class'),
            retain_until: data.get('retain_until'),
            legal_hold: data.get('legal_hold') === 'on',
            supersedes_evidence_id: null,
          },
        }),
      );
      showToast('Restricted evidence metadata recorded.', 'success');
      section.querySelector('.restricted-evidence-load')?.click();
    } catch (error) {
      showToast(error.message, 'error');
      setButtonBusy(button, false);
    }
  });

  for (const form of section.querySelectorAll('.restricted-evidence-review')) {
    form.addEventListener('submit', async (event) => {
      event.preventDefault();
      const data = new FormData(form);
      const button = form.querySelector('button[type="submit"]');
      if (!globalThis.confirm?.('Save this independent restricted-evidence review?')) return;
      setButtonBusy(button, true, 'Reviewing…');
      try {
        await context.api.request(
          `/api/v1/management/verification-evidence/${encodeURIComponent(form.dataset.evidenceId)}/review`,
          buildRestrictedRequestOptions({
            method: 'POST',
            purpose: selectedPurpose(section),
            requestId: uuid(),
            body: {
              decision: data.get('decision'),
              review_note: String(data.get('review_note') || '').trim(),
            },
          }),
        );
        showToast('Restricted evidence review saved.', 'success');
        section.querySelector('.restricted-evidence-load')?.click();
      } catch (error) {
        showToast(error.message, 'error');
        setButtonBusy(button, false);
      }
    });
  }
}

export async function mountCifWorkspace(context) {
  if (!canMountCifWorkspace(context.role, context.session)) return;
  context.root.insertAdjacentHTML('beforeend', cifWorkspaceMarkup(context.session));
  const section = context.root.querySelector('#cif-workspace');
  if (!section) return;
  bindSearch(context, section, context.session);
}
