import { bindOfficeWriteOwner } from './office-case-context.js';
import { mountOfficeEvidenceCapture } from './office-evidence-capture.js';
import { mountOfficePrivacy } from './office-privacy.js';
import { sessionHasRole } from './roles.js';
import { emptyState, errorCard, escapeHtml, hasPermission, loadingPanel } from './ui.js';

const mounts = new WeakMap();
const FIELDS = ['full_name', 'phone_number', 'email', 'present_address'];
const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

function reviewInformation(review) {
  const information = Object.fromEntries(FIELDS.map(key => [key, review[key]]));
  if (review.identity_information != null) information.identity_information = { ...review.identity_information };
  return information;
}
function canonical(value) {
  if (Array.isArray(value)) return value.map(canonical);
  return value && typeof value === 'object' ? Object.fromEntries(Object.keys(value).sort().map(key => [key, canonical(value[key])])) : value;
}
function verifiedCifContext(context, review) {
  const expected = {schema_version:1,scope:'cif_information_review',client_id:review.client_id,
    cif_version_id:review.cif_version_id,information:reviewInformation(review)};
  return JSON.stringify(canonical(context.review_snapshot)) === JSON.stringify(canonical(expected)) ? '' : null;
}

export function mountOfficeCifWorkflow({ root, api, session, clientId, signal, onChanged, onOpened, onAccessDenied, onDraftChange }) {
  mounts.get(root)?.();
  let disposed = false; let busy = false; let review; let captured; let captureCleanup; let privacyCleanup;
  let writing = false, uncertain = false, revision = 0;
  let originalAction = null;
  api = bindOfficeWriteOwner(api, {isWritePending:()=>!disposed && writing,isUncertain:()=>!disposed && uncertain,dispose});
  const authorized = sessionHasRole(session,'employee','management') && hasPermission(session,'client_onboarding.requirement.review') && UUID.test(clientId);
  const children = () => [captureCleanup,privacyCleanup].filter(Boolean);
  const isDirty = () => !disposed && Boolean(captured || root.querySelector('[name="providerReference"]')?.value || root.querySelector('[name="providerPassed"]')?.checked || children().some(child=>child.isDirty?.()));
  const isWritePending = () => !disposed && (writing || children().some(child=>child.isWritePending?.()));
  const isUncertain = () => !disposed && (uncertain || children().some(child=>child.isUncertain?.()));
  function edited() { revision++; onDraftChange?.(); }
  const controller = new AbortController(); let removers = [];
  const base = `/api/v1/management/clients/${encodeURIComponent(clientId)}/cif`;
  const listen = (element, type, callback) => { element.addEventListener(type, callback); removers.push(() => element.removeEventListener(type, callback)); };
  function showTask(name) {
    if (disposed) return;
    for (const task of root.querySelectorAll('[data-cif-task]')) {
      if (task.getAttribute('data-cif-task') === name) { task.setAttribute('open',''); task.querySelector('summary')?.focus(); }
      else task.removeAttribute('open');
    }
  }
  function completeTask(name,label) {
    const task=root.querySelector(`[data-cif-task="${name}"]`);
    task?.setAttribute('data-complete','true');
    if(task)task.querySelector('summary').textContent=label;
  }
  function clear() {
    captureCleanup?.(); privacyCleanup?.(); captureCleanup = null; privacyCleanup = null;
    for (const remove of removers) remove(); removers = [];
    for (const input of root.querySelectorAll('input')) { input.value = ''; input.checked = false; }
    root.innerHTML = ''; captured = null;
  }
  function dispose() {
    if (disposed) return; disposed = true; controller.abort(); clear(); review = null; originalAction=null;
    signal?.removeEventListener('abort', dispose); if (mounts.get(root) === dispose) mounts.delete(root);
  }
  function fail(error) {
    if (disposed) return;
    if (writing) {uncertain = originalAction?.uncertain || !error?.beforeWrite && ![400,404,409,422].includes(error?.status);if(!uncertain)originalAction=null;else if(originalAction)originalAction.uncertain=true;}
    if ([401, 403].includes(error?.status)) { clear(); review = null; onAccessDenied?.(error); }
    if (error?.status === 409 && !uncertain) { captureCleanup?.(); captured = null; review = null; }
    const status = root.querySelector('[data-cif-workflow-status]');
    if (status) {
      status.innerHTML = errorCard(error);
      if(uncertain){
        const retryable=['confirm','activate','baseline'].includes(originalAction?.kind);
        status.innerHTML += retryable?'<p>The original CIF action remains protected.</p><button type="button" data-retry-cif-action>Retry original CIF action</button>':'<p>The baseline outcome is uncertain. Its original version and evidence remain protected; a general summary cannot establish this result.</p>';
        const retained=originalAction;
        if(retryable)listen(status.querySelector('[data-retry-cif-action]'),'click',()=>{if(originalAction!==retained || !uncertain)return;return retained.kind==='confirm'?confirm():retained.kind==='baseline'?baseline({preventDefault(){}}):activate();});
      }
      if (error?.status === 409 && !uncertain) {
        status.innerHTML += '<button type="button" data-reload-cif-workflow>Reload current review</button>';
        listen(status.querySelector('[data-reload-cif-workflow]'), 'click', open);
      }
    }
    else root.innerHTML = errorCard(error);
  }
  async function confirm() {
    if (disposed || busy || !captured || !review || (uncertain && originalAction?.kind!=='confirm')) return;
    busy = true; writing = true; const button = root.querySelector('[data-confirm-cif]'); button.disabled = true;
    const information = reviewInformation(review);
    originalAction ??= {kind:'confirm',body:{cif_version_id:review.cif_version_id,expected_information:information,applicant_confirmation_evidence_reference:captured.evidence_reference}};
    try {
      const result = await api.request(`${base}/review-confirmations`, { method: 'POST', signal: controller.signal,
        body: originalAction.body });
      if (disposed) return;
      if (result.client_id !== clientId || result.cif_version_id !== review.cif_version_id || !UUID.test(result.review_confirmation_id)) {
        throw new Error('Confirmation response could not be verified. Retry this exact signed review.');
      }
      captured = null;
      uncertain = false; originalAction=null;
      root.querySelector('[data-cif-workflow-status]').innerHTML = '<p>Applicant confirmation saved for this exact CIF version.</p>';
      completeTask('signature','2. Applicant signature — Confirmed');
      showTask('privacy');
    } catch (error) { fail(error); }
    finally { busy = false; writing = false; if (!disposed && captured && review) button.disabled = false; }
  }
  async function baseline(event) {
    event.preventDefault(); if (disposed || busy || !review || (uncertain && originalAction?.kind!=='baseline')) return;
    const reference = uncertain ? originalAction.body.evidence_reference : root.querySelector('[name="providerReference"]').value.trim();
    const checked = uncertain || root.querySelector('[name="providerPassed"]').checked;
    if (!reference || !checked) { fail(new Error('Record the controlled provider result only after baseline face and liveness verification passed.')); return; }
    busy = true; writing = true;
    originalAction ??= {kind:'baseline',body:{cif_version_id:review.cif_version_id,evidence_reference:reference,liveness_status:'passed'}};
    try {
      const result = await api.request(`${base}/baseline-live-face`, { method: 'PATCH', signal: controller.signal,
        body: originalAction.body });
      if (disposed) return;
      if (result.client_id !== clientId || result.version_number !== review.version_number || result.liveness_status !== 'passed') {
        throw new Error('Baseline result could not be verified. Reload the CIF before continuing.');
      }
      root.querySelector('[data-cif-workflow-status]').innerHTML = '<p>Controlled baseline verification result recorded.</p>';
      root.querySelector('[name="providerReference"]').value = '';
      root.querySelector('[name="providerPassed"]').checked = false; uncertain = false; originalAction=null;
      completeTask('identity','4. Identity verification — Recorded');
    } catch (error) { fail(error); } finally { busy = false; writing = false; }
  }
  async function activate() {
    if (disposed || busy || !review || (uncertain && originalAction?.kind!=='activate')) return; busy = true; writing = true;
    originalAction ??= {kind:'activate',body:{cif_version_id:review.cif_version_id}};
    try {
      const result = await api.request(`${base}/activate`, { method: 'POST', signal: controller.signal,
        body: originalAction.body });
      if (disposed) return;
      if (result.client_id !== clientId || result.version_number !== review.version_number || result.status !== 'active') {
        throw new Error('Activation response could not be verified. Reload the CIF.');
      }
      uncertain = false; originalAction=null; clear(); root.innerHTML = '<p>CIF activated. Earlier versions and servicing history remain available.</p>'; onChanged?.();
    } catch (error) { fail(error); } finally { busy = false; writing = false; }
  }
  async function open() {
    if (disposed || !authorized || busy || isDirty() || isWritePending() || isUncertain()) return false; busy = true; clear(); root.innerHTML = loadingPanel('Opening exact CIF review and signing controls…');
    try {
      const value = await api.request(`${base}/review-summary?include_identity_information=true`, { signal: controller.signal });
      if (disposed) return;
      if (!value || value.client_id !== clientId || !UUID.test(value.cif_version_id) || value.review_scope !== 'cif_information_only'
        || !FIELDS.every(key => typeof value[key] === 'string' || (key === 'email' && value[key] === null))) {
        throw new Error('The CIF review does not match this Client.');
      }
      review = value;
      const all = { ...Object.fromEntries(FIELDS.map(key => [key, review[key]])), ...(review.identity_information || {}) };
      const detailsMarkup=`<div class="detail-grid">${Object.entries(all).map(([key, value]) => `<div class="detail-item"><span>${escapeHtml(key.replaceAll('_', ' '))}</span><strong>${escapeHtml(value ?? 'Not provided')}</strong></div>`).join('')}</div>`;
      root.innerHTML = `<div class="office-cif-checklist"><p class="meta">Complete these steps for CIF version ${escapeHtml(review.version_number)}. Open any step to review it.</p>
        <details class="office-cif-task" data-cif-task="details" open><summary>1. Review details</summary><div class="office-cif-task-body">
        ${detailsMarkup}
        <button type="button" class="button button-primary" data-cif-next="signature">Continue to applicant signature</button></div></details>
        <details class="office-cif-task" data-cif-task="signature"><summary>2. Applicant signature</summary><div class="office-cif-task-body"><p>Signing the details in step 1 for <strong>${escapeHtml(review.full_name)}</strong>, CIF version ${escapeHtml(review.version_number)}. Review these details with the applicant before signing.</p><div class="office-cif-signing-grid"><div class="office-cif-signing-facts">${detailsMarkup}</div><div>
        <div data-signed-cif></div><button type="button" class="button button-primary" data-confirm-cif disabled>Confirm reviewed CIF information</button>
        </div></div></div></details>
        <details class="office-cif-task" data-cif-task="privacy"><summary>3. Privacy acknowledgment</summary><div class="office-cif-task-body"><div data-privacy-cif></div></div></details>
        <details class="office-cif-task" data-cif-task="identity"><summary>4. Identity verification</summary><div class="office-cif-task-body">
        ${review.status === 'draft' ? `<p>Record the result from the approved face and liveness verification process. This form does not perform a face scan.</p>
          <form data-baseline-cif class="entry-form"><label>Verification result reference<input name="providerReference" type="text" maxlength="500" autocomplete="off" required /></label>
          <label><input name="providerPassed" type="checkbox" required /> Baseline face and liveness verification passed.</label><button type="submit" class="button button-primary">Save verification result</button></form>` : '<p>This CIF is already active.</p>'}
        </div></details>
        ${review.status === 'draft' ? `<div class="office-cif-finish"><p>When the required review and verification are complete, Management can activate this CIF. SPINA checks the saved requirements before activation.</p>${sessionHasRole(session,'management')?'<button type="button" class="button button-outline" data-activate-cif>Activate verified CIF</button>':''}</div>`:''}
        <div data-cif-workflow-status role="status" aria-live="polite"></div></div>`;
      captureCleanup = mountOfficeEvidenceCapture({ root: root.querySelector('[data-signed-cif]'), api, session, clientId,
        cifVersionId: review.cif_version_id, purpose: 'cif_review', signal: controller.signal,
        verifiedContextMarkup: context => verifiedCifContext(context, review),
        onCaptured: record => { captured = record; edited(); root.querySelector('[data-confirm-cif]').disabled = false; }, onAccessDenied, onDraftChange:edited });
      privacyCleanup = mountOfficePrivacy({ root: root.querySelector('[data-privacy-cif]'), api, session, clientId,
        cifVersionId: review.cif_version_id, signal: controller.signal, onDraftChange:edited, onAccessDenied,
        onRecorded:()=>{completeTask('privacy','3. Privacy acknowledgment — Recorded');showTask('identity');} });
      listen(root.querySelector('[data-confirm-cif]'), 'click', confirm);
      for (const button of root.querySelectorAll('[data-cif-next]')) listen(button,'click',()=>showTask(button.getAttribute('data-cif-next')));
      if (review.status === 'draft') {
        listen(root.querySelector('[data-baseline-cif]'), 'submit', baseline);
        for (const input of root.querySelector('[data-baseline-cif]').querySelectorAll('input')) { listen(input,'input',edited);listen(input,'change',edited); }
        if (sessionHasRole(session, 'management')) listen(root.querySelector('[data-activate-cif]'), 'click', activate);
      }
      onOpened?.();
    } catch (error) { fail(error); } finally { busy = false; }
  }
  mounts.set(root, dispose); signal?.addEventListener('abort', dispose, { once: true });
  Object.assign(dispose, {getContext:()=>review ? {clientId,cifVersionId:review.cif_version_id,versionNumber:review.version_number} : null,
    isDirty,getRevision:()=>revision,isWritePending,isUncertain,openCase:open,
    resetCase:()=>{if(disposed || !authorized || isWritePending() || isUncertain())return false;clear();review=null;return true;},
    refreshReadOnly:open,dispose});
  if (signal?.aborted) { dispose(); return dispose; }
  if (!sessionHasRole(session, 'employee', 'management') || !hasPermission(session, 'client_onboarding.requirement.review') || !UUID.test(clientId)) {
    root.innerHTML = emptyState('Office access, onboarding review permission and a valid Client selection are required.');
    return dispose;
  }
  root.innerHTML = '<button type="button" class="button button-primary" data-open-cif-workflow>Review and sign CIF</button>';
  listen(root.querySelector('[data-open-cif-workflow]'), 'click', open);
  return dispose;
}
