import { normalizeRole } from './roles.js';
import { errorCard, escapeHtml, hasPermission } from './ui.js';

const mounts = new WeakMap();
const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
const SHA256 = /^[0-9a-f]{64}$/;
const object = value => value !== null && typeof value === 'object' && !Array.isArray(value);
const sameId = (left, right) => typeof left === 'string' && typeof right === 'string' && UUID.test(left) && left.toLowerCase() === right.toLowerCase();
function validDocument(value) { return object(value) && typeof value.version === 'string' && value.version.trim() && SHA256.test(value.sha256 || ''); }
function validContext(value, clientId, cifVersionId, optional) {
  const snapshot = value?.review_snapshot;
  return sameId(value?.client_id, clientId) && sameId(value?.cif_version_id, cifVersionId)
    && sameId(value.subject_id, cifVersionId) && value.application_id === null && value.application_version_id === null
    && value.purpose === 'privacy_acknowledgment' && typeof value.issuable === 'boolean'
    && typeof value.detail === 'string' && SHA256.test(value.snapshot_sha256 || '')
    && object(snapshot) && snapshot.schema_version === 1 && snapshot.scope === 'privacy_acknowledgment'
    && sameId(snapshot.client_id, clientId) && sameId(snapshot.cif_version_id, cifVersionId)
    && snapshot.optional_service_communications === optional
    && (!value.issuable || (validDocument(snapshot.notice) && validDocument(snapshot.consent)));
}
function validAcknowledgment(value, clientId, cifVersionId) {
  return object(value) && sameId(value.client_id, clientId) && sameId(value.cif_version_id, cifVersionId)
    && UUID.test(value.id || '') && typeof value.optional_service_communications === 'boolean'
    && typeof value.acknowledged_at === 'string' && !Number.isNaN(Date.parse(value.acknowledged_at))
    && ['notice', 'consent'].every(kind => validDocument({ version: value[`${kind}_version`], sha256: value[`${kind}_sha256`] }));
}

export function mountOfficePrivacy({root, api, session, clientId, cifVersionId, signal}) {
  mounts.get(root)?.();
  let disposed = false;
  let generation = 0;
  let busy = false;
  let context;
  let uncertain = false;
  const listeners = [];
  let documentListeners = [];
  const token = session?.access_token;
  function alive() {
    if (!disposed && (signal?.aborted || (api.sessionStore && api.sessionStore.load()?.access_token !== token))) dispose();
    return !disposed;
  }
  function dispose() {
    if (disposed) return;
    disposed = true; generation += 1; context = null;
    for (const [element, event, listener] of listeners) element.removeEventListener(event, listener);
    for (const remove of documentListeners) remove();
    documentListeners = [];
    listeners.length = 0;
    signal?.removeEventListener('abort', dispose);
    for (const input of root.querySelectorAll('input')) { input.value = ''; input.checked = false; }
    if (mounts.get(root) === dispose) { mounts.delete(root); root.innerHTML = ''; }
  }
  mounts.set(root, dispose);
  if (signal?.aborted) { dispose(); return dispose; }
  signal?.addEventListener('abort', dispose, {once:true});
  const role = normalizeRole(session?.user?.role || session?.user?.roles?.[0]);
  if (!['employee','management'].includes(role) || !hasPermission(session,'client_onboarding.requirement.review') || !UUID.test(clientId || '') || !UUID.test(cifVersionId || '')) {
    root.innerHTML = '<p>Open an authorized current CIF to view its privacy record.</p>'; return dispose;
  }
  root.innerHTML = `<h3>Privacy notice and consent</h3><p>Record this separately from application confirmation and final loan signing.</p>
    <label><input type="checkbox" name="optionalServiceCommunications" /> Optional service-related communications beyond necessary loan servicing</label>
    <p>This choice is optional and is not required for a loan.</p>
    <button type="button" class="button button-outline" data-privacy-refresh>Load current privacy documents</button>
    <div data-privacy-status role="status" aria-live="polite"></div>
    <div data-privacy-documents></div>
    <form data-privacy-confirm class="entry-form" hidden>
      <label>Signed privacy consent scan<input type="file" name="signedPrivacyScan" accept="application/pdf,image/png,image/jpeg" required /></label>
      <label><input type="checkbox" name="witnessedPrivacySignature" required /> I witnessed the borrower review these exact documents and sign the privacy acknowledgment with the choice shown above.</label>
      <button type="submit" class="button button-primary">Record privacy acknowledgment</button>
    </form>`;
  const status = root.querySelector('[data-privacy-status]');
  const documents = root.querySelector('[data-privacy-documents]');
  const form = root.querySelector('[data-privacy-confirm]');
  const optional = root.querySelector('[name="optionalServiceCommunications"]');
  const fileInput = root.querySelector('[name="signedPrivacyScan"]');
  const witness = root.querySelector('[name="witnessedPrivacySignature"]');
  const refresh = root.querySelector('[data-privacy-refresh]');
  optional.checked = false;
  witness.checked = false;
  const prefix = `/api/v1/management/clients/${encodeURIComponent(clientId)}`;
  function listen(element,event,handler) { element.addEventListener(event,handler); listeners.push([element,event,handler]); }
  function controls() {
    optional.disabled = busy; refresh.disabled = busy;
    for (const element of [...form.querySelectorAll('input'), ...form.querySelectorAll('button')]) element.disabled = busy || uncertain;
  }
  function invalidate() {
    for (const remove of documentListeners) remove();
    documentListeners = [];
    generation += 1; context = null; form.hidden = true; documents.innerHTML = '';
    fileInput.value = ''; witness.checked = false; status.innerHTML = '';
  }
  async function load() {
    if (!alive() || busy) return;
    invalidate(); const current = generation; busy = true; controls();
    try {
      const result = await api.request(`${prefix}/privacy/context?cif_version_id=${encodeURIComponent(cifVersionId)}&optional_service_communications=${optional.checked}`, {signal});
      if (!alive() || generation !== current) return;
      if (!validContext(result, clientId, cifVersionId, optional.checked)) throw new Error('Privacy record does not match this CIF and choice.');
      context = result; uncertain = false;
      status.textContent = result.detail;
      if (result.acknowledgment) {
        const ack = result.acknowledgment;
        if (!validAcknowledgment(ack, clientId, cifVersionId)) throw new Error('Privacy acknowledgment identity is invalid.');
        status.textContent += ` Previous acknowledgment recorded on ${ack.acknowledged_at}; notice ${ack.notice_version}, consent ${ack.consent_version}; optional communications: ${ack.optional_service_communications ? 'selected' : 'not selected'}.`;
      }
      if (result.issuable) {
        documents.innerHTML = ['notice','consent'].map(kind => `<p>${escapeHtml(kind)} version ${escapeHtml(result.review_snapshot[kind]?.version)} <button type="button" class="button button-outline" data-privacy-document="${kind}">Download ${kind}</button></p>`).join('');
        for (const button of documents.querySelectorAll('[data-privacy-document]')) {
          const download = async () => {
          if (!alive() || busy || context !== result) return;
          button.disabled = true;
          try {
            const kind = button.getAttribute('data-privacy-document');
            const expectedHash = result.review_snapshot[kind].sha256;
            const blob = await api.request(`${prefix}/privacy/documents/${kind}?cif_version_id=${encodeURIComponent(cifVersionId)}&expected_sha256=${expectedHash}`, {responseType:'blob',signal});
            if (!alive() || context !== result) return;
            if (!(blob instanceof Blob) || blob.type !== 'application/pdf' || !blob.size || blob.size > 10485760) throw new Error('The privacy document is invalid. Load the current record.');
            const digest = [...new Uint8Array(await crypto.subtle.digest('SHA-256', await blob.arrayBuffer()))].map(value => value.toString(16).padStart(2, '0')).join('');
            if (!alive() || context !== result) return;
            if (digest !== expectedHash) throw new Error('The privacy document changed. Load the current record before signing.');
            const url = URL.createObjectURL(blob);
            const anchor = document.createElement('a'); anchor.href = url; anchor.download = `privacy-${kind}.pdf`; anchor.click();
            setTimeout(() => URL.revokeObjectURL(url), 1000);
          } catch(error) { if(alive() && context === result) { if ([401,403].includes(error?.status)) { dispose(); return; } invalidate(); status.innerHTML = errorCard(error); } }
          finally { if(alive()) button.disabled = false; }
          };
          button.addEventListener('click', download);
          documentListeners.push(() => button.removeEventListener('click', download));
        }
        form.hidden = false;
      }
    } catch(error) { if(alive() && generation === current) { if ([401,403].includes(error?.status)) { dispose(); return; } context = null; form.hidden = true; documents.innerHTML = ''; status.innerHTML = errorCard(error); } }
    finally { if(alive()) { busy = false; controls(); } }
  }
  listen(optional,'change',invalidate);
  listen(refresh,'click',load);
  listen(form,'submit',async event => {
    event.preventDefault();
    if (!alive() || busy || uncertain || !context?.issuable || !witness.checked) return;
    const file = fileInput.files?.[0];
    if (!file || !['application/pdf','image/png','image/jpeg'].includes(file.type) || file.size <= 0 || file.size > 10485760) { status.textContent = 'Choose a signed PDF, PNG or JPEG of at most 10 MiB.'; return; }
    const selected = context; const current = generation; busy = true; controls();
    try {
      const query = new URLSearchParams({purpose:'privacy_acknowledgment', cif_version_id:cifVersionId, optional_service_communications:String(optional.checked), request_id:crypto.randomUUID(), expected_snapshot_sha256:selected.snapshot_sha256, witnessed_wet_signature:'true'});
      const capture = await api.request(`${prefix}/review-evidence?${query}`, {method:'POST',rawBody:file,headers:{'Content-Type':file.type},signal});
      if (!alive() || current !== generation) return;
      if (!sameId(capture?.client_id, clientId) || !sameId(capture?.cif_version_id, cifVersionId) || capture.application_id !== null || capture.application_version_id !== null || capture.purpose !== 'privacy_acknowledgment' || capture.snapshot_sha256 !== selected.snapshot_sha256 || !UUID.test(capture.evidence_id || '') || capture.evidence_reference !== `office-evidence:${capture.evidence_id}`) throw new Error('Signed privacy capture does not match the review.');
      const saved = await api.request(`${prefix}/privacy/acknowledgments`, {method:'POST',body:{cif_version_id:cifVersionId, optional_service_communications:optional.checked, evidence_reference:capture.evidence_reference},signal});
      if (!alive() || current !== generation) return;
      if (!validAcknowledgment(saved, clientId, cifVersionId)
        || saved.optional_service_communications !== selected.review_snapshot.optional_service_communications
        || !sameId(saved.evidence_id, capture.evidence_id)
        || !['notice','consent'].every(kind => saved[`${kind}_version`] === selected.review_snapshot[kind].version && saved[`${kind}_sha256`] === selected.review_snapshot[kind].sha256)) throw new Error('Reload to reconcile the privacy acknowledgment.');
      status.textContent = 'Privacy acknowledgment recorded. Application confirmation and loan signing remain separate.';
      invalidate(); status.textContent = 'Privacy acknowledgment recorded. Load the current record to review it.';
    } catch(error) { if(alive() && current === generation) { if ([401,403].includes(error?.status)) { dispose(); return; } uncertain = true; status.innerHTML = errorCard(error) + '<p>Load the current privacy record before another attempt.</p>'; } }
    finally { if(alive()) { busy = false; controls(); } }
  });
  void load();
  return dispose;
}
