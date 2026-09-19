import { normalizeRole } from './roles.js';
import { emptyState, errorCard, hasPermission, loadingPanel } from './ui.js';

const mounts = new WeakMap();
const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
const TYPES = ['application/pdf', 'image/png', 'image/jpeg'];

/** Capture an actual witnessed paper signature scan against a server-owned snapshot. */
export function mountOfficeEvidenceCapture({
  root, api, session, clientId, cifVersionId, purpose, applicationId, applicationVersionId,
  signal, onCaptured, onAccessDenied,
}) {
  mounts.get(root)?.();
  let disposed = false; let context; let requestId; let selectedFile; let busy = false;
  let removers = [];
  const controller = new AbortController();
  const base = `/api/v1/management/clients/${encodeURIComponent(clientId)}/review-evidence`;
  const source = new URLSearchParams({ purpose, cif_version_id: cifVersionId });
  if (applicationId) source.set('application_id', applicationId);
  if (applicationVersionId) source.set('application_version_id', applicationVersionId);
  const listen = (element, event, handler) => {
    element.addEventListener(event, handler); removers.push(() => element.removeEventListener(event, handler));
  };
  function clear() {
    for (const remove of removers) remove(); removers = [];
    for (const input of root.querySelectorAll('input')) input.value = '';
    root.innerHTML = '';
  }
  function dispose() {
    if (disposed) return; disposed = true; controller.abort(); context = null; selectedFile = null;
    clear(); signal?.removeEventListener('abort', dispose);
    if (mounts.get(root) === dispose) mounts.delete(root);
  }
  function fail(error) {
    if (disposed) return;
    if ([401, 403].includes(error?.status)) {
      context = null; selectedFile = null; clear(); root.innerHTML = errorCard(error);
      onAccessDenied?.(error); return;
    }
    const status = root.querySelector('[data-capture-status]');
    if (status) status.innerHTML = errorCard(error);
    else root.innerHTML = errorCard(error);
  }
  function matches(value) {
    return value && value.client_id === clientId && value.cif_version_id === cifVersionId
      && value.purpose === purpose && /^[0-9a-f]{64}$/.test(value.snapshot_sha256)
      && (!applicationId || value.application_id === applicationId)
      && (!applicationVersionId || value.application_version_id === applicationVersionId);
  }
  async function download(record) {
    try {
      const blob = await api.request(`${base}/${record.evidence_id}`, { responseType: 'blob', signal: controller.signal });
      if (disposed) return;
      const url = URL.createObjectURL(blob); const link = document.createElement('a');
      link.href = url; link.download = `signed-review-${record.evidence_id}`; link.click();
      // The browser has received its download request; revoke the temporary local URL.
      setTimeout(() => URL.revokeObjectURL(url), 1000);
    } catch (error) { fail(error); }
  }
  async function capture(event) {
    event.preventDefault(); if (disposed || busy || !context) return;
    const file = root.querySelector('[name="signedScan"]').files?.[0];
    if (!root.querySelector('[name="witnessed"]').checked || !file) {
      fail(new Error('Witness the applicant’s wet signature and select the signed scan.')); return;
    }
    if (!TYPES.includes(file.type) || file.size < 1 || file.size > 10 * 1024 * 1024) {
      fail(new Error('Choose a PDF, PNG or JPEG signed scan of at most 10 MiB.')); return;
    }
    if (selectedFile !== file) { selectedFile = file; requestId = crypto.randomUUID(); }
    const query = new URLSearchParams(source);
    query.set('request_id', requestId); query.set('expected_snapshot_sha256', context.snapshot_sha256);
    query.set('witnessed_wet_signature', 'true');
    busy = true; root.querySelector('button[type="submit"]').disabled = true;
    root.querySelector('[data-capture-status]').innerHTML = loadingPanel('Saving signed review evidence…');
    try {
      const record = await api.request(`${base}?${query}`, {
        method: 'POST', rawBody: file, headers: { 'Content-Type': file.type }, signal: controller.signal,
      });
      if (disposed) return;
      if (!matches(record) || record.snapshot_sha256 !== context.snapshot_sha256 || !UUID.test(record.evidence_id)
        || record.evidence_reference !== `office-evidence:${record.evidence_id}`) {
        throw new Error('The signed evidence response could not be verified. Retry this same file before confirming.');
      }
      context = null; selectedFile = null; clear();
      root.innerHTML = '<p>Signed review evidence saved for this exact version.</p><button type="button" data-download-signed>Download saved signed copy</button><div data-capture-status role="status"></div>';
      listen(root.querySelector('[data-download-signed]'), 'click', () => download(record));
      onCaptured?.(record);
    } catch (error) {
      if (disposed) return;
      if (error?.status === 409) {
        context = null; selectedFile = null; clear();
        root.innerHTML = `${errorCard(error)}<p>Reload this review before capturing another signed copy.</p>`;
      } else fail(error);
    } finally {
      busy = false;
      const submit = root.querySelector('button[type="submit"]'); if (submit && context) submit.disabled = false;
    }
  }
  async function load() {
    root.innerHTML = loadingPanel('Preparing exact signed review capture…');
    try {
      const value = await api.request(`${base}/context?${source}`, { signal: controller.signal });
      if (disposed) return;
      if (!matches(value)) throw new Error('The signed review context does not match this selection.');
      if (value.issuance_ready === false) throw new Error('The controlled document is not ready for signing.');
      context = value;
      root.innerHTML = `<form class="entry-form"><p>Review the saved facts with the applicant, witness their wet signature, then attach the signed paper copy. The stored capture time records upload time.</p>
        <label>Signed review scan <input name="signedScan" type="file" accept="application/pdf,image/png,image/jpeg" required /></label>
        <label><input name="witnessed" type="checkbox" required /> I witnessed the applicant sign this exact review.</label>
        <button class="button button-primary" type="submit">Save signed review evidence</button>
      </form><div data-capture-status role="status" aria-live="polite"></div>`;
      listen(root.querySelector('form'), 'submit', capture);
    } catch (error) { fail(error); }
  }
  mounts.set(root, dispose);
  signal?.addEventListener('abort', dispose, { once: true });
  if (signal?.aborted) { dispose(); return dispose; }
  const role = normalizeRole(session?.user?.role || session?.user?.roles?.[0]);
  if (!['employee', 'management'].includes(role) || !hasPermission(session, 'client_onboarding.requirement.review')) {
    root.innerHTML = emptyState('Office access and onboarding review permission are required.');
  } else if (!UUID.test(clientId) || !UUID.test(cifVersionId) || !['cif_review', 'application_review'].includes(purpose)
    || (purpose === 'application_review' && (!UUID.test(applicationId) || !UUID.test(applicationVersionId)))) {
    root.innerHTML = errorCard(new Error('A valid exact review selection is required.'));
  } else void load();
  return dispose;
}
