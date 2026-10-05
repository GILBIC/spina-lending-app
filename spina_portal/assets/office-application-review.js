import { bindOfficeWriteOwner } from './office-case-context.js';
import { createOfficeCaseContext } from './office-case-context.js';
import { sessionHasRole } from './roles.js';
import { mountOfficeApplicationEntry } from './office-application-entry.js';
import { mountOfficeEvidenceCapture } from './office-evidence-capture.js';
import { emptyState, errorCard, escapeHtml, hasPermission, loadingPanel } from './ui.js';

const mounts = new WeakMap();
const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
const DECIMAL = /^[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?$/;
const REQUEST = [
  ['requested_loan_type_id', 'Requested product (current catalog label)', 'uuid'],
  ['purpose', 'Purpose', 'text'],
  ['requested_amount', 'Requested amount', 'money'],
  ['requested_payment_arrangement', 'Requested payment arrangement', 'text'],
  ['requested_term', 'Requested term', 'text'],
  ['preferred_first_payment_date', 'Preferred first payment date', 'date'],
];
const REPAYMENT = [
  ['repayment_source', 'Repayment source', 'text'],
  ['source_details', 'Source details', 'text'],
  ['monthly_gross_income', 'Monthly gross income', 'money'],
  ['monthly_net_income', 'Monthly net income', 'money'],
  ['has_existing_obligations', 'Existing obligations', 'boolean'],
];
const OBLIGATION = [
  ['creditor', 'Creditor', 'text'],
  ['outstanding_balance', 'Outstanding balance', 'money'],
  ['periodic_payment_amount', 'Periodic payment amount', 'money'],
  ['payment_frequency', 'Payment frequency', 'text'],
  ['notes', 'Notes', 'text'],
];
const EMPLOYMENT = [
  ['employer_or_business_name', 'Employer or business name', 'text'],
  ['position_or_business_nature', 'Position or nature of business', 'text'],
  ['length_of_employment_or_operation', 'Length of employment or operation', 'text'],
  ['employer_or_business_address', 'Employer or business address', 'text'],
  ['contact_number', 'Employer or business contact number', 'text'],
];
const REFERENCE = [
  ['full_name', 'Name', 'text'], ['relationship', 'Relationship', 'text'],
  ['phone_number', 'Phone number', 'text'], ['address', 'Address', 'text'],
];

function isUuid(value) { return typeof value === 'string' && UUID.test(value); }
function isObject(value) { return value !== null && typeof value === 'object' && !Array.isArray(value); }
function positiveInteger(value) { return Number.isSafeInteger(value) && value > 0; }
function isNullable(value, kind) {
  if (value === null) return true;
  if (kind === 'boolean') return typeof value === 'boolean';
  if (typeof value !== 'string') return false;
  if (kind === 'uuid') return isUuid(value);
  if (kind === 'money') return DECIMAL.test(value);
  if (kind === 'date') return /^\d{4}-\d{2}-\d{2}$/.test(value)
    && !Number.isNaN(Date.parse(`${value}T00:00:00Z`));
  return true;
}

function hasKeys(object, keys) {
  return isObject(object) && Object.keys(object).length === keys.length
    && keys.every((key) => Object.hasOwn(object, key));
}

function validFields(object, fields, extraKeys = []) {
  return hasKeys(object, [...fields.map(([name]) => name), ...extraKeys])
    && fields.every(([name, , kind]) => isNullable(object[name], kind));
}

function validInformationShape(information) {
  return hasKeys(information, ['request', 'repayment'])
    || (hasKeys(information, ['request', 'repayment', 'details'])
      && hasKeys(information.details, ['schema_version', 'employment', 'references'])
      && information.details.schema_version === 1 && validFields(information.details.employment, EMPLOYMENT)
      && Array.isArray(information.details.references)
      && information.details.references.every((row) => validFields(row, REFERENCE)));
}

function missingLabels(information) {
  const labels = Object.fromEntries([
    ...REQUEST.slice(0, 5).map(([name, label]) => [`request.${name}`, label]),
    ...REPAYMENT.map(([name, label]) => [`repayment.${name}`, label]),
    ['repayment.obligations', 'Obligation details'],
  ]);
  information.repayment.obligations.forEach((row, index) => {
    for (const [name, label] of OBLIGATION.slice(0, 4)) {
      labels[`repayment.obligations[${index}].${name}`] = `Obligation ${index + 1}: ${label}`;
    }
  });
  return labels;
}

function validReview(review, clientId, reference) {
  if (!isObject(review)
    || !isUuid(review.client_id) || review.client_id.toLowerCase() !== clientId.toLowerCase()
    || !['application_id', 'application_version_id', 'cif_version_id'].every((name) => isUuid(review[name]))
    || review.application_reference !== reference
    || !positiveInteger(review.version_number) || !positiveInteger(review.cif_version_number)
    || review.review_scope !== 'loan_application_information_only'
    || !isNullable(review.requested_loan_type_name, 'text')
    || typeof review.recorded_at !== 'string'
    || !/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})$/.test(review.recorded_at)
    || Number.isNaN(Date.parse(review.recorded_at))
    || !validInformationShape(review.information)
    || !validFields(review.information.request, REQUEST)
    || !validFields(review.information.repayment, REPAYMENT, ['obligations'])) return false;
  const repayment = review.information.repayment;
  if (!Array.isArray(repayment.obligations)
    || !repayment.obligations.every((row) => validFields(row, OBLIGATION))
    || (repayment.has_existing_obligations === false && repayment.obligations.length)) return false;
  const labels = missingLabels(review.information);
  return Array.isArray(review.missing_fields)
    && review.missing_fields.every((field) => typeof field === 'string' && Object.hasOwn(labels, field));
}

function display(value, kind = 'text') {
  if (value === null) return 'Not provided';
  if (kind === 'money') return `PHP ${value}`;
  if (kind === 'boolean') return value ? 'Yes' : 'No';
  return value;
}

function detail(label, value) {
  return `<div class="detail-item"><span>${escapeHtml(label)}</span><strong>${escapeHtml(value)}</strong></div>`;
}

function canonical(value) {
  if (Array.isArray(value)) return value.map(canonical);
  return isObject(value) ? Object.fromEntries(Object.keys(value).sort().map(key => [key, canonical(value[key])])) : value;
}

function printableCif(context, review) {
  const snapshot = context?.review_snapshot;
  const identities = ['client_id', 'cif_version_id', 'application_id', 'application_version_id'];
  if (!isObject(context) || context.purpose !== 'application_review' || !isObject(snapshot)
    || snapshot.schema_version !== 1 || snapshot.scope !== 'application_information_review'
    || !identities.every(key => context[key] === review[key] && snapshot[key] === review[key])
    || JSON.stringify(canonical(snapshot.information)) !== JSON.stringify(canonical(review.information))) return null;
  const cif = snapshot.cif_information;
  const names = ['full_name', 'phone_number', 'email', 'present_address'];
  if (!(hasKeys(cif, names) || hasKeys(cif, [...names, 'identity_information']))
    || !['full_name', 'phone_number', 'present_address'].every(key => typeof cif[key] === 'string')
    || !isNullable(cif.email, 'text')) return null;
  const identityFields = [['birth_date', 'Date of birth', 'date'], ['birth_place', 'Place of birth', 'text'],
    ['civil_status', 'Civil status', 'text'], ['citizenship', 'Citizenship', 'text']];
  if (Object.hasOwn(cif, 'identity_information') && !validFields(cif.identity_information, identityFields)) return null;
  return `<article><h2>Linked CIF version ${escapeHtml(review.cif_version_number)}</h2><div class="detail-grid">
    ${[['full_name', 'Full name'], ['phone_number', 'Phone number'], ['email', 'Email'], ['present_address', 'Residential address']].map(([name, label]) => detail(label, display(cif[name]))).join('')}
    ${cif.identity_information ? identityFields.map(([name, label]) => detail(label, display(cif.identity_information[name]))).join('') : ''}</div></article>`;
}

function reviewMarkup(review) {
  const { request, repayment } = review.information;
  const product = request.requested_loan_type_id === null
    ? 'Not provided' : (review.requested_loan_type_name || 'Unavailable');
  const labels = missingLabels(review.information);
  return `<article class="data-card">
    <h3>Loan application review</h3>
    <p>Requested information only; approval and release are separate.</p>
    <div class="detail-grid">
      ${detail('Loan application reference', review.application_reference)}
      ${detail('Application version', review.version_number)}
      ${detail('Linked CIF version', review.cif_version_number)}
      ${detail('Recorded at', review.recorded_at.replace('T', ' ').replace(/Z$/, ' UTC'))}
    </div>
    <h4>Requested loan information</h4>
    <div class="detail-grid">${REQUEST.map(([name, label, kind]) => detail(label,
      name === 'requested_loan_type_id' ? product : display(request[name], kind))).join('')}</div>
    <h4>Repayment information</h4>
    <div class="detail-grid">${REPAYMENT.map(([name, label, kind]) => detail(label, display(repayment[name], kind))).join('')}</div>
    <h4>Declared obligations</h4>
    ${repayment.obligations.length ? `<div class="list-stack">${repayment.obligations.map((row, index) => `<section class="data-card"><h5>Obligation ${index + 1}</h5><div class="detail-grid">${OBLIGATION.map(([name, label, kind]) => detail(label, display(row[name], kind))).join('')}</div></section>`).join('')}</div>` : '<p>No obligation rows were provided.</p>'}
    ${review.information.details ? `<h4>Employment or business details</h4>
      <p>Declared information saved with this application version.</p>
      <div class="detail-grid">${EMPLOYMENT.map(([name, label]) => detail(label, display(review.information.details.employment[name]))).join('')}</div>
      <h4>References or emergency contacts</h4>
      ${review.information.details.references.length ? review.information.details.references.map((row, index) => `<section class="data-card"><h5>Reference ${index + 1}</h5><div class="detail-grid">${REFERENCE.map(([name, label]) => detail(label, display(row[name]))).join('')}</div></section>`).join('') : '<p>No reference rows were provided.</p>'}`
    : '<p>Employment and reference details were not recorded in this saved version.</p>'}
    <h4>Missing request and repayment facts</h4>
    <p>This list covers only request and repayment information. It does not assess whether the full application is complete or ready for approval.</p>
    ${review.missing_fields.length ? `<ul>${review.missing_fields.map((field) => `<li>${escapeHtml(labels[field])}</li>`).join('')}</ul>` : '<p>No missing request or repayment facts were reported.</p>'}
  </article>`;
}

export function mountOfficeApplicationReview({ root, api, session, signal, onContextChange, officeCaseContext, registerHandle, getSession = () => session, confirmDiscard }) {
  mounts.get(root)?.();
  root.innerHTML = '';
  let disposed = false;
  let currentRequest;
  let form;
  let intakeInput;
  let applicationInput;
  let clearButton;
  let statusRoot;
  let reviewRoot;
  let entryRoot;
  let entryCleanup;
  let newButton;
  let selectedReview;
  let confirmationCleanup;
  let printCleanup;
  let creating = false;
  let selectedContext = null, lookupRequest = {}, revision = 0, confirmationHandle = null;
  const coordinator = officeCaseContext ?? createOfficeCaseContext({getSession,confirmDiscard});
  api = bindOfficeWriteOwner(api, {dispose}, coordinator);
  const ownsCoordinator = !officeCaseContext;
  const children = () => [entryCleanup,confirmationHandle].filter(Boolean);
  const isDirty = () => children().some(child=>child.isDirty?.());
  const isWritePending = () => children().some(child=>child.isWritePending?.());
  const isUncertain = () => children().some(child=>child.isUncertain?.());
  function edited() {revision++;coordinator.invalidateCandidate();}
  function searchEdited() {lookupRequest={};coordinator.invalidateCandidate(); if(statusRoot)statusRoot.innerHTML='';}
  function contextFor(selection,review) {return {mode:'saved-case',intakeReference:selection.application_reference,clientId:selection.client_id,
    applicationReference:review.application_reference,applicationId:review.application_id,applicationVersionId:review.application_version_id,applicationSaved:true,
    stageFacts:{application:{intakeReference:selection.application_reference,clientId:review.client_id,applicationReference:review.application_reference,
      applicationId:review.application_id,applicationVersionId:review.application_version_id,versionNumber:review.version_number,status:'Saved application version'}}};}
  function denyAccess(error) {if(disposed || mounts.get(root)!==dispose)return;coordinator.dispose();dispose();root.innerHTML=errorCard(error);}


  function invalidate() {
    currentRequest = {};
    entryCleanup?.();
    entryCleanup = null;
    confirmationCleanup?.();
    confirmationCleanup = null;
    printCleanup?.();
    printCleanup = null;
    selectedReview = null;
    selectedContext = null; confirmationHandle = null;
    if (reviewRoot) reviewRoot.innerHTML = '';
    if (statusRoot) statusRoot.innerHTML = '';
  }

  function dispose() {
    if (disposed) return;
    disposed = true;
    invalidate();
    form?.removeEventListener('submit', openReview);
    for (const input of [intakeInput, applicationInput]) {
      input?.removeEventListener('input', searchEdited);
      input?.removeEventListener('change', searchEdited);
      if (input) input.value = '';
    }
    clearButton?.removeEventListener('click', clear);
    newButton?.removeEventListener('click', createApplication);
    signal?.removeEventListener('abort', dispose);
    if(ownsCoordinator)coordinator.dispose();
    if (mounts.get(root) === dispose) {
      mounts.delete(root);
      root.innerHTML = '';
    }
  }

  function clear() {
    if (disposed) return;
    searchEdited();
    intakeInput.value = '';
    applicationInput.value = '';
    intakeInput.focus();
  }

  async function openReview(event, expected = null) {
    event?.preventDefault();
    if (disposed) return;
    if(isWritePending() || isUncertain()){statusRoot.textContent='Keep the current operation and reconcile it before changing case.';return false;}
    const token = {}; lookupRequest = token;
    const intakeReference = intakeInput.value.trim();
    const applicationReference = applicationInput.value.trim();
    if (!intakeReference || !applicationReference) {
      statusRoot.innerHTML = `<div role="alert">${errorCard(new Error('Enter both the office intake reference and loan application reference.'))}</div>`;
      return;
    }
    statusRoot.innerHTML = loadingPanel('Loading saved application information…');
    try {
      let selection, review;
      const accepted = await coordinator.requestTransition({kind:'open',targetStage:'application',candidate:async()=>{
        try {selection = await api.request(`/api/v1/management/onboarding/applicants/by-reference/${encodeURIComponent(intakeReference)}/cif-client`,{signal});}catch(error){if([401,403].includes(error?.status))denyAccess(error);throw error;}
        if(disposed || lookupRequest !== token)return null;
        if (!isObject(selection) || !isUuid(selection.client_id) || typeof selection.application_reference !== 'string'
          || selection.application_reference.trim().toLowerCase() !== intakeReference.toLowerCase()
          || (expected?.clientId && selection.client_id.toLowerCase() !== expected.clientId.toLowerCase())) throw new Error('The office intake response is invalid or does not match the selected Client.');
        try {review = await api.request(`/api/v1/management/clients/${encodeURIComponent(selection.client_id)}/loan-applications/by-reference/${encodeURIComponent(applicationReference)}/review-summary`,{signal});}catch(error){if([401,403].includes(error?.status))denyAccess(error);throw error;}
        if(disposed || lookupRequest !== token)return null;
        if (!validReview(review, selection.client_id, applicationReference)
          || (expected && Object.hasOwn(expected,'applicationId') && (typeof expected.applicationId!=='string' || review.application_id.toLowerCase() !== expected.applicationId.toLowerCase()))
          || (expected && Object.hasOwn(expected,'applicationVersionId') && (typeof expected.applicationVersionId!=='string' || review.application_version_id.toLowerCase() !== expected.applicationVersionId.toLowerCase()))
          || (expected && Object.hasOwn(expected,'versionNumber') && review.version_number !== expected.versionNumber)) throw new Error('The application response is invalid or the selected application or saved version changed. Refresh the applications list and select it again.');
        return contextFor(selection,review);
      }});
      if(!accepted || disposed){if(!disposed && lookupRequest===token){statusRoot.textContent='Your existing work has been kept.';form.querySelector('button[type="submit"]').focus();}return false;}
      currentRequest=token; selectedContext=contextFor(selection,review);
      intakeInput.value=selection.application_reference; applicationInput.value=review.application_reference;
      onContextChange?.(coordinator.getContext());
      statusRoot.innerHTML = '';
      selectedReview = review;
      reviewRoot.innerHTML = `${reviewMarkup(review)}<button class="button button-outline" type="button" data-edit-application>Edit application information</button>
        <button class="button button-outline" type="button" data-prepare-application-confirmation${review.missing_fields.length ? ' disabled' : ''}>Prepare applicant confirmation</button>
        <button class="button button-outline" type="button" data-print-application>Print saved application review</button>
        ${review.missing_fields.length ? '<p>Complete the missing request and repayment facts before applicant confirmation.</p>' : ''}
        <div data-application-confirmation></div>`;
      reviewRoot.querySelector('[data-edit-application]').addEventListener('click', () => {
        if (selectedReview === review) openEntry(review.client_id, review);
      });
      reviewRoot.querySelector('[data-prepare-application-confirmation]').addEventListener('click', () => {
        if (selectedReview === review && !review.missing_fields.length) prepareConfirmation(review);
      });
      reviewRoot.querySelector('[data-print-application]').addEventListener('click', () => {
        if (selectedReview === review) printReview(review);
      });
      return true;
    } catch (error) {
      if([401,403].includes(error?.status)){denyAccess(error);return false;}
      if (disposed || lookupRequest !== token) return false;
      statusRoot.innerHTML = `<div role="alert">${errorCard(error, 'Application review is unavailable.')}</div>`;
      return false;
    }
  }

  async function printReview(review) {
    if (disposed || selectedReview !== review || printCleanup) return;
    const token = currentRequest;
    let frame;
    let cancelled = false;
    const button = reviewRoot.querySelector('[data-print-application]');
    button.disabled = true;
    const cleanup = () => {
      cancelled = true;
      if (frame) { frame.onload = null; frame.remove(); frame.srcdoc = ''; }
      if (printCleanup === cleanup) printCleanup = null;
      if (!disposed && selectedReview === review) button.disabled = false;
    };
    printCleanup = cleanup;
    const active = () => !disposed && !cancelled && currentRequest === token && selectedReview === review;
    try {
      const query = new URLSearchParams({ purpose: 'application_review', cif_version_id: review.cif_version_id,
        application_id: review.application_id, application_version_id: review.application_version_id });
      const context = await api.request(`/api/v1/management/clients/${encodeURIComponent(review.client_id)}/review-evidence/context?${query}`, { signal });
      if (!active()) return;
      const cif = printableCif(context, review);
      if (!cif) throw new Error('The printable review does not match this saved application and attached CIF.');
      frame = document.createElement('iframe');
      frame.setAttribute('title', 'Saved application review print copy');
      frame.setAttribute('sandbox', 'allow-modals allow-same-origin');
      frame.style.cssText = 'position:fixed;width:0;height:0;border:0;';
      frame.onload = () => {
        if (!active()) return;
        try { frame.contentWindow.focus(); frame.contentWindow.print(); }
        finally { cleanup(); }
      };
      frame.srcdoc = `<!doctype html><html><head><meta charset="utf-8"><meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'"><title>Saved application review</title><style>body{font:12pt Arial,sans-serif;color:#000;margin:20mm}.detail-grid{display:grid;grid-template-columns:1fr 1fr;gap:10pt}.detail-item span,.detail-item strong{display:block;overflow-wrap:anywhere}.detail-item span{font-size:10pt;font-weight:normal}h2,h3,h4,h5{break-after:avoid}article,section{margin-bottom:16pt}section{break-inside:avoid}</style></head><body>${cif}${reviewMarkup(review)}</body></html>`;
      document.body.appendChild(frame);
    } catch (error) {
      if (active()) {
        if ([401,403].includes(error?.status)) { coordinator.dispose();dispose(); return; }
        statusRoot.innerHTML = errorCard(error);
      }
      cleanup();
    }
  }

  function prepareConfirmation(review) {
    if (disposed || selectedReview !== review || isWritePending() || isUncertain() || confirmationHandle?.isDirty?.()) return;
    confirmationCleanup?.();
    const token = currentRequest;
    const container = reviewRoot.querySelector('[data-application-confirmation]');
    const prepare = reviewRoot.querySelector('[data-prepare-application-confirmation]');
    prepare.disabled = true;
    container.innerHTML = '<h4>Applicant review confirmation</h4><p>This confirms the reviewed application information only. Approval, final loan signing, and release remain separate.</p><div data-application-signed-evidence></div><button type="button" class="button button-primary" data-confirm-application disabled>Record application confirmation</button><div data-application-confirmation-status role="status" aria-live="polite"></div>';
    const status = container.querySelector('[data-application-confirmation-status]');
    const confirm = container.querySelector('[data-confirm-application]');
    let evidence;
    let pending = false, uncertain = false;
    let closed = false;
    const active = () => !disposed && !closed && currentRequest === token && selectedReview === review;
    const confirmationApi = bindOfficeWriteOwner(api,{isWritePending:()=>active() && pending,isUncertain:()=>active() && uncertain});
    const captureCleanup = mountOfficeEvidenceCapture({
      root: container.querySelector('[data-application-signed-evidence]'), api, session,
      clientId: review.client_id, cifVersionId: review.cif_version_id, purpose: 'application_review',
      applicationId: review.application_id, applicationVersionId: review.application_version_id, signal,
      verifiedContextMarkup: context => printableCif(context, review),
      onDraftChange:edited,
      onCaptured(record) { if (active()) { evidence = record; edited();confirm.disabled = false; } },
      onAccessDenied() { if (active()) {coordinator.dispose();dispose();} },
    });
    function cleanup() {
      if (closed) return;
      closed = true;
      evidence = null;
      captureCleanup();
      confirmationHandle=null;
      confirm.removeEventListener('click', saveConfirmation);
      container.innerHTML = '';
    }
    async function saveConfirmation() {
      if (!active() || pending || !evidence) return;
      const wasUncertain=uncertain;
      pending = true; uncertain = true;
      confirm.disabled = true;
      status.innerHTML = loadingPanel('Recording applicant confirmation…');
      try {
        const saved = await confirmationApi.request(`/api/v1/management/clients/${encodeURIComponent(review.client_id)}/loan-applications/${encodeURIComponent(review.application_id)}/review-confirmations`, {
          method: 'POST', signal, body: { application_version_id: review.application_version_id, applicant_confirmation_evidence_reference: evidence.evidence_reference },
        });
        if (!active()) return;
        if (!isObject(saved) || !isUuid(saved.review_confirmation_id)
          || !['client_id', 'application_id', 'application_version_id', 'cif_version_id'].every(name => isUuid(saved[name]) && saved[name].toLowerCase() === review[name].toLowerCase())
          || saved.review_scope !== 'loan_application_information_only'
          || typeof saved.confirmed_at !== 'string' || Number.isNaN(Date.parse(saved.confirmed_at))) {
          throw new Error('The application confirmation response could not be verified.');
        }
        uncertain=false;captureCleanup();
        evidence = null;
        status.textContent = 'Applicant application review confirmed. Approval, final loan signing, and release remain separate.';
      } catch (error) {
        if (!active()) return;
        if ([401, 403].includes(error?.status)) { coordinator.dispose();dispose(); return; }
        const retry = !wasUncertain && (error?.beforeWrite || [400, 422].includes(error?.status));
        if (retry) {uncertain=false;confirm.disabled = false;}
        else {confirm.disabled=false;confirm.textContent='Retry original application confirmation';}
        status.innerHTML = `${errorCard(error)}${retry ? '' : '<p>The original confirmation evidence and saved version are retained. Retry only this exact confirmation.</p>'}`;
      } finally { pending = false; }
    }
    confirm.addEventListener('click', saveConfirmation);
    confirmationCleanup = cleanup;
    confirmationHandle={isDirty:()=>Boolean(evidence)||captureCleanup.isDirty?.(),isWritePending:()=>pending||captureCleanup.isWritePending?.(),isUncertain:()=>uncertain||captureCleanup.isUncertain?.()};
  }

  function openEntry(clientId, review = null) {
    if (disposed || isWritePending() || isUncertain() || confirmationHandle?.isDirty?.()) return;
    const retainedContext=selectedContext;
    invalidate(); selectedContext=retainedContext;
    applicationInput.value=review?.application_reference ?? retainedContext?.applicationReference ?? applicationInput.value;
    if(retainedContext?.intakeReference)intakeInput.value=retainedContext.intakeReference;
    const token = currentRequest;
    entryCleanup = mountOfficeApplicationEntry({
      root: entryRoot, api, session, signal, clientId,
      applicationReference: applicationInput.value.trim(), review, onDraftChange:edited, onAccessDenied:denyAccess,
      onSaved(saved) {
        if (!disposed && currentRequest === token) {
          applicationInput.value = saved.application_reference;
          const selection={application_reference:coordinator.getContext().intakeReference,client_id:saved.client_id};
          selectedContext=contextFor(selection,saved); entryCleanup=null;
          const savedContext=selectedContext;
          const offerSavedRead=message=>{if(disposed)return;statusRoot.innerHTML=`<p>Application version ${escapeHtml(saved.version_number)} saved. ${message}</p><button type="button" class="button button-outline" data-reload-saved-application>Open saved application</button>`;
            statusRoot.querySelector('[data-reload-saved-application]').addEventListener('click',async()=>{const loaded=await handle.openCase(savedContext);if(!loaded && !disposed)offerSavedRead('Current details are unavailable or protected work has been kept. Opening reads the saved application before any replacement.');});};
          if(!coordinator.acceptVerifiedContext(savedContext,coordinator.getGeneration())){
            coordinator.detachReleaseFact(savedContext);
            offerSavedRead('Approval & release work remains attached to the previously selected version. Open this saved application to verify and deliberately change that selection.');return;
          }
          void openReview(null,savedContext).then(loaded=>{if(!loaded && !disposed && currentRequest===token)offerSavedRead('Current details are unavailable. Opening reads the saved application; it does not repeat the save.');});
        }
      },
      onCancel({ reload = false } = {}) {
        if (disposed || currentRequest !== token) return;
        invalidate();
        if (reload || review) openReview();
      },
    });
  }

  async function createApplication() {
    if (disposed || creating || isWritePending() || isUncertain()) return;
    if (entryCleanup) {
      statusRoot.textContent = 'Your application draft is already open below. Continue it, or use its Cancel or Reload action before starting another.';
      return;
    }
    const token = currentRequest;
    const caseGeneration = coordinator.getGeneration();
    const intakeReference = intakeInput.value.trim();
    if (!intakeReference) {
      statusRoot.innerHTML = `<div role="alert">${errorCard(new Error('Enter the office intake reference. A new application reference will be generated.'))}</div>`;
      return;
    }
    creating = true;
    newButton.disabled = true;
    statusRoot.innerHTML = loadingPanel('Loading application entry…');
    try {
      const selection = await api.request(`/api/v1/management/onboarding/applicants/by-reference/${encodeURIComponent(intakeReference)}/cif-client`);
      if (disposed || currentRequest !== token) return;
      if (!isObject(selection) || !isUuid(selection.client_id)
        || typeof selection.application_reference !== 'string'
        || selection.application_reference.trim().toLowerCase() !== intakeReference.toLowerCase()) {
        throw new Error('The office intake response is invalid or does not match the entered reference.');
      }
      if (caseGeneration !== coordinator.getGeneration()) {
        throw new Error('The selected case changed while this intake was loading. No application draft was opened. Check the selected case and try New application again.');
      }
      const draftReference = applicationInput.value.trim() || `LOAN-${crypto.randomUUID()}`;
      const draftContext={mode:'saved-case',intakeReference:selection.application_reference,clientId:selection.client_id,
        applicationReference:draftReference,applicationId:null,applicationVersionId:null,applicationSaved:false};
      const selected=coordinator.getContext();
      const matchesSelected=(!selected.intakeReference || selected.intakeReference.toLowerCase()===selection.application_reference.toLowerCase())
        && (!selected.clientId || selected.clientId.toLowerCase()===selection.client_id.toLowerCase());
      const accepted=matchesSelected && (selected.applicationId || selected.applicationVersionId || selected.stageFacts.application
        ? await coordinator.requestTransition({kind:'open',targetStage:'application',candidate:draftContext})
        : coordinator.acceptVerifiedContext(draftContext,caseGeneration));
      if (!accepted || onContextChange?.(draftContext) === false) {
        throw new Error('This intake does not match the selected case. Your selected case has been kept. Return to the selected intake or close the current case before starting another application.');
      }
      selectedContext=draftContext;
      applicationInput.value = draftReference;
      openEntry(selection.client_id);
    } catch (error) {
      if (disposed || currentRequest !== token) return;
      statusRoot.innerHTML = `<div role="alert">${errorCard(error, 'Application entry is unavailable.')}</div>`;
    } finally { creating = false; if (!disposed) newButton.disabled = false; }
  }

  mounts.set(root, dispose);
  if (signal?.aborted) {
    dispose();
    return dispose;
  }
  signal?.addEventListener('abort', dispose, { once: true });
  if (!sessionHasRole(session, 'employee', 'management')
    || !hasPermission(session, 'client_onboarding.requirement.review')) {
    root.innerHTML = emptyState('Office access and onboarding review permission are required.');
    return dispose;
  }
  root.innerHTML = `<form class="entry-form">
    <label>Office intake reference<input name="intakeReference" type="text" autocomplete="off" required /></label>
    <label>Loan application reference<input name="applicationReference" type="text" autocomplete="off" placeholder="Automatic for a new application" required /><span class="meta">Leave blank for New application. Enter a reference only to open an existing application.</span></label>
    <div class="action-row"><button class="button button-primary" type="submit">Open application review</button><button class="button button-outline" type="button">Clear</button><button class="button button-outline" type="button" data-new-application>New application</button></div>
  </form>
  <div data-application-review-status role="status" aria-live="polite"></div>
  <div data-application-review-information aria-live="polite"></div>
  <div data-application-entry></div>`;
  form = root.querySelector('form');
  intakeInput = form.querySelector('[name="intakeReference"]');
  applicationInput = form.querySelector('[name="applicationReference"]');
  clearButton = form.querySelector('button[type="button"]');
  statusRoot = root.querySelector('[data-application-review-status]');
  reviewRoot = root.querySelector('[data-application-review-information]');
  entryRoot = root.querySelector('[data-application-entry]');
  newButton = form.querySelector('[data-new-application]');
  form.addEventListener('submit', openReview);
  for (const input of [intakeInput, applicationInput]) {
    input.addEventListener('input', searchEdited);
    input.addEventListener('change', searchEdited);
  }
  clearButton.addEventListener('click', clear);
  newButton.addEventListener('click', createApplication);
  const handle={getContext:()=>!disposed?selectedContext:null,isDirty,isWritePending,isUncertain,getRevision:()=>revision,
    openCase:selection=>{if(disposed || !selection || typeof selection!=='object')return false; intakeInput.value=selection.intakeReference ?? '';applicationInput.value=selection.applicationReference ?? '';return openReview(null,selection);},
    resetCase:()=>{if(disposed || isWritePending() || isUncertain())return false;invalidate();intakeInput.value='';applicationInput.value='';return true;},
    refreshReadOnly:()=>{if(entryCleanup?.isUncertain?.())return entryCleanup.refreshReadOnly();if(!selectedContext || isDirty() || isWritePending() || isUncertain())return false;return handle.openCase(selectedContext);},dispose};
  Object.assign(dispose,handle);registerHandle?.(handle);if(ownsCoordinator)coordinator.registerStage('application',handle);
  return dispose;
}
