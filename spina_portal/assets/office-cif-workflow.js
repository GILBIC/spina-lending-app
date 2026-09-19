import { mountOfficeEvidenceCapture } from './office-evidence-capture.js';
import { mountOfficePrivacy } from './office-privacy.js';
import { normalizeRole } from './roles.js';
import { emptyState, errorCard, escapeHtml, hasPermission, loadingPanel } from './ui.js';

const mounts = new WeakMap();
const FIELDS = ['full_name', 'phone_number', 'email', 'present_address'];
const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

export function mountOfficeCifWorkflow({ root, api, session, clientId, signal, onChanged, onAccessDenied }) {
  mounts.get(root)?.();
  let disposed = false; let busy = false; let review; let captured; let captureCleanup; let privacyCleanup;
  const controller = new AbortController(); let removers = [];
  const base = `/api/v1/management/clients/${encodeURIComponent(clientId)}/cif`;
  const role = normalizeRole(session?.user?.role || session?.user?.roles?.[0]);
  const listen = (element, type, callback) => { element.addEventListener(type, callback); removers.push(() => element.removeEventListener(type, callback)); };
  function clear() {
    captureCleanup?.(); privacyCleanup?.(); captureCleanup = null; privacyCleanup = null;
    for (const remove of removers) remove(); removers = [];
    for (const input of root.querySelectorAll('input')) input.value = '';
    root.innerHTML = ''; captured = null;
  }
  function dispose() {
    if (disposed) return; disposed = true; controller.abort(); clear(); review = null;
    signal?.removeEventListener('abort', dispose); if (mounts.get(root) === dispose) mounts.delete(root);
  }
  function fail(error) {
    if (disposed) return;
    if ([401, 403].includes(error?.status)) { clear(); review = null; onAccessDenied?.(error); }
    if (error?.status === 409) { captureCleanup?.(); captured = null; review = null; }
    const status = root.querySelector('[data-cif-workflow-status]');
    if (status) {
      status.innerHTML = errorCard(error);
      if (error?.status === 409) {
        status.innerHTML += '<button type="button" data-reload-cif-workflow>Reload current review</button>';
        listen(status.querySelector('[data-reload-cif-workflow]'), 'click', open);
      }
    }
    else root.innerHTML = errorCard(error);
  }
  async function confirm() {
    if (disposed || busy || !captured || !review) return;
    busy = true; const button = root.querySelector('[data-confirm-cif]'); button.disabled = true;
    const information = Object.fromEntries(FIELDS.map(key => [key, review[key]]));
    if (review.identity_information != null) information.identity_information = { ...review.identity_information };
    try {
      const result = await api.request(`${base}/review-confirmations`, { method: 'POST', signal: controller.signal,
        body: { cif_version_id: review.cif_version_id, expected_information: information,
          applicant_confirmation_evidence_reference: captured.evidence_reference } });
      if (disposed) return;
      if (result.client_id !== clientId || result.cif_version_id !== review.cif_version_id || !UUID.test(result.review_confirmation_id)) {
        throw new Error('Confirmation response could not be verified. Retry this exact signed review.');
      }
      captured = null;
      root.querySelector('[data-cif-workflow-status]').innerHTML = '<p>Applicant confirmation saved for this exact CIF version.</p>';
    } catch (error) { fail(error); }
    finally { busy = false; if (!disposed && captured && review) button.disabled = false; }
  }
  async function baseline(event) {
    event.preventDefault(); if (disposed || busy || !review) return;
    const reference = root.querySelector('[name="providerReference"]').value.trim();
    const checked = root.querySelector('[name="providerPassed"]').checked;
    if (!reference || !checked) { fail(new Error('Record the controlled provider result only after baseline face and liveness verification passed.')); return; }
    busy = true;
    try {
      const result = await api.request(`${base}/baseline-live-face`, { method: 'PATCH', signal: controller.signal,
        body: { cif_version_id: review.cif_version_id, evidence_reference: reference, liveness_status: 'passed' } });
      if (disposed) return;
      if (result.client_id !== clientId || result.version_number !== review.version_number || result.liveness_status !== 'passed') {
        throw new Error('Baseline result could not be verified. Reload the CIF before continuing.');
      }
      root.querySelector('[data-cif-workflow-status]').innerHTML = '<p>Controlled baseline verification result recorded.</p>';
      root.querySelector('[name="providerReference"]').value = '';
    } catch (error) { fail(error); } finally { busy = false; }
  }
  async function activate() {
    if (disposed || busy || !review) return; busy = true;
    try {
      const result = await api.request(`${base}/activate`, { method: 'POST', signal: controller.signal,
        body: { cif_version_id: review.cif_version_id } });
      if (disposed) return;
      if (result.client_id !== clientId || result.version_number !== review.version_number || result.status !== 'active') {
        throw new Error('Activation response could not be verified. Reload the CIF.');
      }
      clear(); root.innerHTML = '<p>CIF activated. Earlier versions and servicing history remain available.</p>'; onChanged?.();
    } catch (error) { fail(error); } finally { busy = false; }
  }
  async function open() {
    if (disposed || busy) return; busy = true; clear(); root.innerHTML = loadingPanel('Opening exact CIF review and signing controls…');
    try {
      const value = await api.request(`${base}/review-summary?include_identity_information=true`, { signal: controller.signal });
      if (disposed) return;
      if (!value || value.client_id !== clientId || !UUID.test(value.cif_version_id) || value.review_scope !== 'cif_information_only'
        || !FIELDS.every(key => typeof value[key] === 'string' || (key === 'email' && value[key] === null))) {
        throw new Error('The CIF review does not match this Client.');
      }
      review = value;
      const all = { ...Object.fromEntries(FIELDS.map(key => [key, review[key]])), ...(review.identity_information || {}) };
      root.innerHTML = `<h3>Applicant review and confirmation</h3><p>CIF version ${escapeHtml(review.version_number)}</p>
        <div class="detail-grid">${Object.entries(all).map(([key, value]) => `<div class="detail-item"><span>${escapeHtml(key.replaceAll('_', ' '))}</span><strong>${escapeHtml(value ?? 'Not provided')}</strong></div>`).join('')}</div>
        <div data-signed-cif></div><button type="button" class="button button-primary" data-confirm-cif disabled>Confirm reviewed CIF information</button>
        <div data-privacy-cif></div>
        ${review.status === 'draft' ? `<h3>Controlled baseline verification</h3><p>Use the result from the approved face and liveness verification process. This form records its result; it does not perform a face scan.</p>
          <form data-baseline-cif class="entry-form"><label>Verification provider evidence reference<input name="providerReference" type="text" maxlength="500" autocomplete="off" required /></label>
          <label><input name="providerPassed" type="checkbox" required /> Baseline face and liveness verification passed.</label><button type="submit">Record verified baseline</button></form>
          ${role === 'management' ? '<button type="button" data-activate-cif>Activate verified CIF</button>' : '<p>Management activates the CIF after the required review and verification.</p>'}` : '<p>This CIF is already active.</p>'}
        <div data-cif-workflow-status role="status" aria-live="polite"></div>`;
      captureCleanup = mountOfficeEvidenceCapture({ root: root.querySelector('[data-signed-cif]'), api, session, clientId,
        cifVersionId: review.cif_version_id, purpose: 'cif_review', signal: controller.signal,
        onCaptured: record => { captured = record; root.querySelector('[data-confirm-cif]').disabled = false; }, onAccessDenied });
      privacyCleanup = mountOfficePrivacy({ root: root.querySelector('[data-privacy-cif]'), api, session, clientId,
        cifVersionId: review.cif_version_id, signal: controller.signal });
      listen(root.querySelector('[data-confirm-cif]'), 'click', confirm);
      if (review.status === 'draft') {
        listen(root.querySelector('[data-baseline-cif]'), 'submit', baseline);
        if (role === 'management') listen(root.querySelector('[data-activate-cif]'), 'click', activate);
      }
    } catch (error) { fail(error); } finally { busy = false; }
  }
  mounts.set(root, dispose); signal?.addEventListener('abort', dispose, { once: true });
  if (signal?.aborted) { dispose(); return dispose; }
  if (!['employee', 'management'].includes(role) || !hasPermission(session, 'client_onboarding.requirement.review') || !UUID.test(clientId)) {
    root.innerHTML = emptyState('Office access, onboarding review permission and a valid Client selection are required.');
    return dispose;
  }
  root.innerHTML = '<button type="button" data-open-cif-workflow>Open signing, privacy and verification</button>';
  listen(root.querySelector('[data-open-cif-workflow]'), 'click', open);
  return dispose;
}
