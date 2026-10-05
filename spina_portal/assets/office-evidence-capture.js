import { bindOfficeWriteOwner } from './office-case-context.js';
import { mountOfficeSignatureInput, signatureAttestation } from './office-signature-input.js';
import { sessionHasRole } from './roles.js';
import { emptyState, errorCard, hasPermission, loadingPanel } from './ui.js';

const mounts = new WeakMap();
const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
const TYPES = ['application/pdf', 'image/png', 'image/jpeg'];

/** Capture witnessed signing against a server-owned exact review snapshot. */
export function mountOfficeEvidenceCapture({
  root, api, session, clientId, cifVersionId, purpose, applicationId, applicationVersionId,
  signal, onCaptured, onAccessDenied, onDraftChange, verifiedContextMarkup,
}) {
  mounts.get(root)?.();
  let disposed = false; let context; let requestId; let selectedFile; let busy = false;
  let removers = [];
  let revision = 0, uncertain = false;
  let signatureInput, selectedMethod;
  api = bindOfficeWriteOwner(api, {isWritePending:()=>!disposed && busy,isUncertain:()=>!disposed && uncertain,dispose});
  const authorized = sessionHasRole(session,'employee','management') && hasPermission(session,'client_onboarding.requirement.review') && UUID.test(clientId) && UUID.test(cifVersionId) && ['cif_review','application_review'].includes(purpose) && (purpose !== 'application_review' || (UUID.test(applicationId) && UUID.test(applicationVersionId)));
  const isDirty = () => !disposed && Boolean(signatureInput?.isDirty() || root.querySelector('[name="signedScan"]')?.files?.length || root.querySelector('[name="witnessed"]')?.checked);
  function edited() { revision++; onDraftChange?.(); }
  const controller = new AbortController();
  const base = `/api/v1/management/clients/${encodeURIComponent(clientId)}/review-evidence`;
  const source = new URLSearchParams({ purpose, cif_version_id: cifVersionId });
  if (applicationId) source.set('application_id', applicationId);
  if (applicationVersionId) source.set('application_version_id', applicationVersionId);
  const listen = (element, event, handler) => {
    element.addEventListener(event, handler); removers.push(() => element.removeEventListener(event, handler));
  };
  function clear() {
    signatureInput?.dispose(); signatureInput = null;
    for (const remove of removers) remove(); removers = [];
    for (const input of root.querySelectorAll('input')) { input.value = ''; input.checked = false; }
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
    if (!uncertain && !root.querySelector('[name="witnessed"]').checked) {
      fail(new Error('Witness the applicant sign this exact review before saving.')); return;
    }
    busy = true; signatureInput?.setDisabled(true);
    root.querySelector('button[type="submit"]').disabled = true;
    for (const input of root.querySelectorAll('input')) input.disabled = true;
    let file, method;
    try {
      ({file, method} = uncertain ? {file:selectedFile,method:selectedMethod} : await signatureInput.getEvidence());
      if (disposed || !context) return;
      if (!file || !TYPES.includes(file.type) || file.size < 1 || file.size > 10 * 1024 * 1024) throw new Error('Draw a signature or choose a PDF, PNG or JPEG signed scan of at most 10 MiB.');
    } catch (error) {
      if (!disposed) {busy=false;signatureInput?.setDisabled(false);for(const input of root.querySelectorAll('input'))input.disabled=false;root.querySelector('button[type="submit"]').disabled=false;fail(error);}
      return;
    }
    if (selectedFile !== file || selectedMethod !== method) { selectedFile = file; selectedMethod = method; requestId = crypto.randomUUID(); }
    const query = new URLSearchParams(source);
    query.set('request_id', requestId); query.set('expected_snapshot_sha256', context.snapshot_sha256);
    for (const [key,value] of Object.entries(signatureAttestation(method))) query.set(key,value);
    const wasUncertain=uncertain;
    root.querySelector('[data-capture-status]').innerHTML = loadingPanel('Saving signed review evidence…');
    try {
      const record = await api.request(`${base}?${query}`, {
        method: 'POST', rawBody: file, headers: { 'Content-Type': file.type }, signal: controller.signal,
      });
      if (disposed) return;
      if (!matches(record) || record.snapshot_sha256 !== context.snapshot_sha256 || !UUID.test(record.evidence_id)
        || (method === 'screen_signature' && record.capture_method !== method)
        || record.evidence_reference !== `office-evidence:${record.evidence_id}`) {
        throw new Error('The signed evidence response could not be verified. Retry this same file before confirming.');
      }
      context = null; selectedFile = null; clear();
      uncertain = false;
      root.innerHTML = '<p>Signed review evidence saved for this exact version.</p><button type="button" data-download-signed>Download saved signed copy</button><div data-capture-status role="status"></div>';
      listen(root.querySelector('[data-download-signed]'), 'click', () => download(record));
      onCaptured?.(record);
    } catch (error) {
      if (disposed) return;
      if (error?.status === 409 && !wasUncertain) {
        uncertain = false;
        context = null; selectedFile = null; clear();
        root.innerHTML = `${errorCard(error)}<p>Reload this review before capturing another signed copy.</p>`;
      } else { uncertain = wasUncertain || !error?.beforeWrite && ![400,404,413,415,422].includes(error?.status); fail(error); }
    } finally {
      busy = false;
      const submit = root.querySelector('button[type="submit"]'); if (submit && context) {submit.disabled = false;submit.textContent=uncertain?'Retry original signed evidence':'Save signature';}
      for(const input of root.querySelectorAll('input'))input.disabled=uncertain;
      signatureInput?.setDisabled(uncertain);
    }
  }
  async function load() {
    root.innerHTML = loadingPanel('Preparing exact signed review capture…');
    try {
      const value = await api.request(`${base}/context?${source}`, { signal: controller.signal });
      if (disposed) return;
      if (!matches(value)) throw new Error('The signed review context does not match this selection.');
      if (value.issuance_ready === false) throw new Error('The controlled document is not ready for signing.');
      // Callers bind the snapshot to displayed facts and may render additional linked facts.
      const reviewMarkup = verifiedContextMarkup ? verifiedContextMarkup(value) : '';
      if (typeof reviewMarkup !== 'string') throw new Error('The signing information changed or could not be verified. Reload current review before signing.');
      context = value;
      root.innerHTML = `${reviewMarkup}<form class="entry-form office-signing-form"><p>Review the saved facts with the applicant. They can sign on screen or sign a paper copy. The stored capture time records when the evidence was received.</p>
        <div data-office-signature></div>
        <label>Signed review scan <input name="signedScan" type="file" accept="application/pdf,image/png,image/jpeg" required /></label>
        <label><input name="witnessed" type="checkbox" required /> I witnessed the applicant sign this exact review.</label>
        <button class="button button-primary" type="submit">Save signature</button>
      </form><div data-capture-status role="status" aria-live="polite"></div>`;
      signatureInput = mountOfficeSignatureInput({root:root.querySelector('[data-office-signature]'),fileInput:root.querySelector('[name="signedScan"]'),onChange:()=>{const witness=root.querySelector('[name="witnessed"]');if(witness)witness.checked=false;edited();}});
      listen(root.querySelector('form'), 'submit', capture);
      for (const input of root.querySelectorAll('input')) { listen(input,'input',edited); listen(input,'change',edited); }
    } catch (error) { fail(error); }
  }
  mounts.set(root, dispose);
  Object.assign(dispose, {getContext:()=>context ? {clientId,cifVersionId,purpose,applicationId,applicationVersionId} : null,
    isDirty,getRevision:()=>revision,isWritePending:()=>!disposed && busy,isUncertain:()=>!disposed && uncertain,
    openCase:()=>disposed || !authorized || isDirty() || busy || uncertain ? false : load(),
    resetCase:()=>{if(disposed || !authorized || busy || uncertain)return false;context=null;selectedFile=null;clear();return true;},
    refreshReadOnly:()=>disposed || !authorized || isDirty() || busy || uncertain ? false : load(),dispose});
  signal?.addEventListener('abort', dispose, { once: true });
  if (signal?.aborted) { dispose(); return dispose; }
  if (!sessionHasRole(session, 'employee', 'management') || !hasPermission(session, 'client_onboarding.requirement.review')) {
    root.innerHTML = emptyState('Office access and onboarding review permission are required.');
  } else if (!UUID.test(clientId) || !UUID.test(cifVersionId) || !['cif_review', 'application_review'].includes(purpose)
    || (purpose === 'application_review' && (!UUID.test(applicationId) || !UUID.test(applicationVersionId)))) {
    root.innerHTML = errorCard(new Error('A valid exact review selection is required.'));
  } else void load();
  return dispose;
}
