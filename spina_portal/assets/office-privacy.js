import { bindOfficeWriteOwner, officeSessionOwner } from './office-case-context.js';
import { mountOfficeSignatureInput, signatureAttestation } from './office-signature-input.js';
import { sessionHasRole } from './roles.js';
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

export function mountOfficePrivacy({root, api, session, clientId, cifVersionId, signal, onDraftChange, onAccessDenied}) {
  mounts.get(root)?.();
  let disposed = false;
  let generation = 0;
  let busy = false;
  let context;
  let uncertain = false;
  let operation = null;
  let writing = false, revision = 0;
  let savedOptional = false;
  let signatureInput;
  const blockedDocuments = new Set();
  api = bindOfficeWriteOwner(api, {isWritePending:()=>!disposed && writing,isUncertain:()=>!disposed && uncertain,dispose});
  const authorized = sessionHasRole(session,'employee','management') && hasPermission(session,'client_onboarding.requirement.review') && UUID.test(clientId || '') && UUID.test(cifVersionId || '');
  const isDirty = () => !disposed && (signatureInput?.isDirty() || [...root.querySelectorAll('input')].some(input => input.getAttribute('type') === 'file' ? Boolean(input.files?.length) : input.getAttribute('name') === 'optionalServiceCommunications' ? Boolean(input.checked) !== savedOptional : Boolean(input.checked)));
  function edited() { revision++; onDraftChange?.(); }
  function deny(error) { dispose(); onAccessDenied?.(error); }
  const listeners = [];
  let documentListeners = [];
  const mountedOwner = officeSessionOwner(session);
  const mountedDevice = api.sessionStore?.deviceId?.();
  function alive() {
    if (!disposed && (signal?.aborted || api.isOfficeCurrent?.() === false || (api.sessionStore && (officeSessionOwner(api.sessionStore.load()) !== mountedOwner || api.sessionStore.deviceId?.() !== mountedDevice)))) dispose();
    return !disposed;
  }
  function dispose() {
    if (disposed) return;
    disposed = true; generation += 1; context = null; operation = null;
    signatureInput?.dispose(); signatureInput=null;
    for (const [element, event, listener] of listeners) element.removeEventListener(event, listener);
    for (const remove of documentListeners) remove();
    documentListeners = [];
    listeners.length = 0;
    signal?.removeEventListener('abort', dispose);
    for (const input of root.querySelectorAll('input')) { input.value = ''; input.checked = false; }
    if (mounts.get(root) === dispose) { mounts.delete(root); root.innerHTML = ''; }
  }
  mounts.set(root, dispose);
  Object.assign(dispose, {getContext:()=>context ? {clientId,cifVersionId} : null,isDirty,getRevision:()=>revision,
    isWritePending:()=>!disposed && writing,isUncertain:()=>!disposed && uncertain,
    openCase:()=>disposed || !authorized || isDirty() || busy || uncertain ? false : load(),
    resetCase:()=>{if(disposed || !authorized || writing || uncertain)return false;invalidate();optional.checked=false;savedOptional=false;return true;},
    refreshReadOnly:()=>disposed || !authorized || busy ? false : uncertain ? reconcile() : isDirty() ? false : load(),dispose});
  if (signal?.aborted) { dispose(); return dispose; }
  signal?.addEventListener('abort', dispose, {once:true});
  if (!sessionHasRole(session, 'employee', 'management') || !hasPermission(session,'client_onboarding.requirement.review') || !UUID.test(clientId || '') || !UUID.test(cifVersionId || '')) {
    root.innerHTML = '<p>Open an authorized current CIF to view its privacy record.</p>'; return dispose;
  }
  root.innerHTML = `<h3>Privacy notice and consent</h3><p>Record this separately from application confirmation and final loan signing.</p>
    <label><input type="checkbox" name="optionalServiceCommunications" /> Optional service-related communications beyond necessary loan servicing</label>
    <p>This choice is optional and is not required for a loan.</p>
    <button type="button" class="button button-outline" data-privacy-refresh>Load current privacy documents</button>
    <div data-privacy-status role="status" aria-live="polite"></div>
    <div data-privacy-documents></div>
    <form data-privacy-confirm class="entry-form office-signing-form" hidden>
      <div data-privacy-signature></div>
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
  signatureInput = mountOfficeSignatureInput({root:root.querySelector('[data-privacy-signature]'),fileInput,onChange:()=>{witness.checked=false;edited();}});
  const prefix = `/api/v1/management/clients/${encodeURIComponent(clientId)}`;
  function listen(element,event,handler) { element.addEventListener(event,handler); listeners.push([element,event,handler]); }
  function controls() {
    signatureInput?.setDisabled(busy || uncertain || !context?.issuable || blockedDocuments.size > 0);
    optional.disabled = busy || uncertain; refresh.disabled = busy;
    for (const element of [...form.querySelectorAll('input'), ...form.querySelectorAll('button'), ...documents.querySelectorAll('button')]) element.disabled = busy || uncertain;
    form.querySelector('button[type="submit"]').disabled = busy || uncertain || blockedDocuments.size > 0;
  }
  function invalidate() {
    if (operation) return false;
    for (const remove of documentListeners) remove();
    documentListeners = [];
    generation += 1; context = null; form.hidden = true; documents.innerHTML = '';
    blockedDocuments.clear();
    fileInput.value = ''; witness.checked = false; status.innerHTML = '';
    signatureInput?.reset();
  }
  async function load() {
    if (!alive() || busy) return;
    if (uncertain) return reconcile();
    if (context && isDirty()) return false;
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
          if (!alive() || busy || operation || context !== result) return;
          button.disabled = true;
          const kind = button.getAttribute('data-privacy-document');
          let invalidDocument = false;
          try {
            const expectedHash = result.review_snapshot[kind].sha256;
            const blob = await api.request(`${prefix}/privacy/documents/${kind}?cif_version_id=${encodeURIComponent(cifVersionId)}&expected_sha256=${expectedHash}`, {responseType:'blob',signal});
            if (!alive() || operation || context !== result) return;
            invalidDocument = true;
            if (!(blob instanceof Blob) || blob.type !== 'application/pdf' || !blob.size || blob.size > 10485760) {
              throw new Error('The privacy document is invalid.');
            }
            const digest = [...new Uint8Array(await crypto.subtle.digest('SHA-256', await blob.arrayBuffer()))].map(value => value.toString(16).padStart(2, '0')).join('');
            if (!alive() || operation || context !== result) return;
            if (digest !== expectedHash) {
              throw new Error('The privacy document does not match the displayed source.');
            }
            blockedDocuments.delete(kind);
            status.textContent = blockedDocuments.size ? 'Privacy signing is blocked. Retry each failed document download to verify the displayed source. Your draft is retained.' : result.detail;
            controls();
            const url = URL.createObjectURL(blob);
            const anchor = document.createElement('a'); anchor.href = url; anchor.download = `privacy-${kind}.pdf`; anchor.click();
            setTimeout(() => URL.revokeObjectURL(url), 1000);
          } catch(error) {
            if (!alive()) return;
            if ([401,403].includes(error?.status)) { deny(error); return; }
            // A document read may predate Save. It does not own that command or its File.
            if (operation || context !== result) return;
            if (invalidDocument || error?.status === 409) blockedDocuments.add(kind);
            status.innerHTML = errorCard(error) + (blockedDocuments.size ? '<p>Privacy signing is blocked. Retry each failed document download to verify the displayed source. Your draft is retained.</p>' : '');
            controls();
          } finally { if(alive()) button.disabled = busy || uncertain; }
          };
          button.addEventListener('click', download);
          documentListeners.push(() => button.removeEventListener('click', download));
        }
        form.hidden = false;
      }
    } catch(error) { if(alive() && generation === current) { if ([401,403].includes(error?.status)) { deny(error); return; } context = null; form.hidden = true; documents.innerHTML = ''; status.innerHTML = errorCard(error); } }
    finally { if(alive()) { busy = false; controls(); } }
  }
  listen(optional,'change',()=>{if(busy || uncertain){optional.checked=operation?.optional ?? savedOptional;return;}invalidate();});
  for (const input of root.querySelectorAll('input')) { listen(input,'input',edited); listen(input,'change',edited); }
  listen(refresh,'click',load);
  function validSaved(saved, selected, capture) {
    return validAcknowledgment(saved, clientId, cifVersionId)
      && saved.optional_service_communications === selected.review_snapshot.optional_service_communications
      && sameId(saved.evidence_id, capture?.evidence_id)
      && ['notice','consent'].every(kind => saved[`${kind}_version`] === selected.review_snapshot[kind].version && saved[`${kind}_sha256`] === selected.review_snapshot[kind].sha256);
  }
  function completed() {
    savedOptional = operation.optional; optional.checked = savedOptional;
    uncertain = false; operation = null; invalidate();
    status.textContent = 'Privacy acknowledgment recorded. Load the current record to review it.';
  }
  function recovery(message) {
    status.innerHTML = `<p>${escapeHtml(message)}</p><p>Reconcile before another attempt. The original signed File, choice and request are retained. Load checks the original record; Retry repeats only that exact operation.</p><button type="button" data-privacy-retry>Retry original privacy acknowledgment</button>`;
    const retained=operation;
    status.querySelector('[data-privacy-retry]').addEventListener('click',()=>{if(operation===retained && uncertain)void save();});
  }
  async function reconcile() {
    if (!alive() || busy || !operation) return false;
    busy = true; controls();
    try {
      const value = await api.request(`${prefix}/privacy/context?cif_version_id=${encodeURIComponent(cifVersionId)}&optional_service_communications=${operation.optional}`, {signal});
      if (!alive()) return false;
      if (!validContext(value,clientId,cifVersionId,operation.optional)) throw new Error('The privacy recovery response does not match the original choice.');
      if (operation.capture && validSaved(value.acknowledgment,operation.selected,operation.capture)) { completed(); return true; }
      recovery('The current record does not yet prove the original acknowledgment.'); return false;
    } catch(error) {
      if (alive()) { if ([401,403].includes(error?.status)) deny(error); else recovery(error.message); }
      return false;
    } finally { if (alive()) {busy=false;controls();} }
  }
  async function save(event) {
    event?.preventDefault();
    if (!alive() || busy || (!operation && (!context?.issuable || blockedDocuments.size || !witness.checked))) return;
    if (!operation) {
      let file, method;
      const selected=context, choice=optional.checked, current=generation;
      busy=true;writing=true;controls();
      try {
        ({file,method}=await signatureInput.getEvidence());
        if (!alive()) return;
        if (generation!==current || selected!==context || choice!==optional.checked || blockedDocuments.size) throw new Error('Privacy documents changed. Review them before signing.');
      } catch(error) {
        if(alive()){status.innerHTML=errorCard(error);busy=false;writing=false;controls();}
        return;
      }
      if (!file || !['application/pdf','image/png','image/jpeg'].includes(file.type) || file.size <= 0 || file.size > 10485760) { status.textContent = 'Draw a signature or choose a signed PDF, PNG or JPEG of at most 10 MiB.';busy=false;writing=false;controls();return; }
      operation = {file,method,selected,optional:choice,capture:null,
        query:new URLSearchParams({purpose:'privacy_acknowledgment', cif_version_id:cifVersionId, optional_service_communications:String(choice), request_id:crypto.randomUUID(), expected_snapshot_sha256:selected.snapshot_sha256,...signatureAttestation(method)})};
    }
    const original=operation;
    busy=true;writing=true;controls();
    try {
      if (!original.capture) {
        const capture = await api.request(`${prefix}/review-evidence?${original.query}`, {method:'POST',rawBody:original.file,headers:{'Content-Type':original.file.type},signal});
        if (!alive() || operation !== original) return;
        if (!sameId(capture?.client_id,clientId) || !sameId(capture?.cif_version_id,cifVersionId) || capture.application_id !== null || capture.application_version_id !== null || capture.purpose !== 'privacy_acknowledgment' || capture.snapshot_sha256 !== original.selected.snapshot_sha256 || (original.method==='screen_signature' && capture.capture_method!==original.method) || !UUID.test(capture.evidence_id || '') || capture.evidence_reference !== `office-evidence:${capture.evidence_id}`) throw new Error('Signed privacy capture does not match the review.');
        original.capture=capture;
      }
      const saved=await api.request(`${prefix}/privacy/acknowledgments`,{method:'POST',body:{cif_version_id:cifVersionId,optional_service_communications:original.optional,evidence_reference:original.capture.evidence_reference},signal});
      if (!alive() || operation !== original) return;
      if (!validSaved(saved,original.selected,original.capture)) throw new Error('The privacy acknowledgment could not be verified.');
      completed();
    } catch(error) {
      if (alive() && operation===original) {
        if ([401,403].includes(error?.status)) {deny(error);return;}
        if((error?.beforeWrite || [413,415].includes(error?.status)) && !uncertain && !original.capture) {operation=null;status.innerHTML=errorCard(error);}
        else {uncertain=true;optional.checked=original.optional;recovery(error.message);}
      }
    } finally {writing=false;if(alive()){busy=false;controls();}}
  }
  listen(form,'submit',event=>{event.preventDefault();if(!uncertain)void save();});
  void load();
  return dispose;
}
