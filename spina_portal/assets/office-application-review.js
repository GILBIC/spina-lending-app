import { normalizeRole } from './roles.js';
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
    || !hasKeys(review.information, ['request', 'repayment'])
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
    <h4>Missing request and repayment facts</h4>
    <p>This list covers only request and repayment information. It does not assess whether the full application is complete or ready for approval.</p>
    ${review.missing_fields.length ? `<ul>${review.missing_fields.map((field) => `<li>${escapeHtml(labels[field])}</li>`).join('')}</ul>` : '<p>No missing request or repayment facts were reported.</p>'}
  </article>`;
}

export function mountOfficeApplicationReview({ root, api, session, signal }) {
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

  function invalidate() {
    currentRequest = {};
    if (reviewRoot) reviewRoot.innerHTML = '';
    if (statusRoot) statusRoot.innerHTML = '';
  }

  function dispose() {
    if (disposed) return;
    disposed = true;
    invalidate();
    form?.removeEventListener('submit', openReview);
    for (const input of [intakeInput, applicationInput]) {
      input?.removeEventListener('input', invalidate);
      input?.removeEventListener('change', invalidate);
      if (input) input.value = '';
    }
    clearButton?.removeEventListener('click', clear);
    signal?.removeEventListener('abort', dispose);
    if (mounts.get(root) === dispose) {
      mounts.delete(root);
      root.innerHTML = '';
    }
  }

  function clear() {
    if (disposed) return;
    invalidate();
    intakeInput.value = '';
    applicationInput.value = '';
    intakeInput.focus();
  }

  async function openReview(event) {
    event.preventDefault();
    if (disposed) return;
    invalidate();
    const token = currentRequest;
    const intakeReference = intakeInput.value.trim();
    const applicationReference = applicationInput.value.trim();
    if (!intakeReference || !applicationReference) {
      statusRoot.innerHTML = `<div role="alert">${errorCard(new Error('Enter both the office intake reference and loan application reference.'))}</div>`;
      return;
    }
    statusRoot.innerHTML = loadingPanel('Loading saved application information…');
    try {
      const selection = await api.request(
        `/api/v1/management/onboarding/applicants/by-reference/${encodeURIComponent(intakeReference)}/cif-client`,
      );
      if (disposed || currentRequest !== token) return;
      if (!isObject(selection) || !isUuid(selection.client_id)
        || typeof selection.application_reference !== 'string'
        || selection.application_reference.trim().toLowerCase() !== intakeReference.toLowerCase()) {
        throw new Error('The office intake response is invalid or does not match the entered reference.');
      }
      const review = await api.request(
        `/api/v1/management/clients/${encodeURIComponent(selection.client_id)}/loan-applications/by-reference/${encodeURIComponent(applicationReference)}/review-summary`,
      );
      if (disposed || currentRequest !== token) return;
      if (!validReview(review, selection.client_id, applicationReference)) {
        throw new Error('The application review response is invalid or does not match the selected Client and application.');
      }
      statusRoot.innerHTML = '';
      reviewRoot.innerHTML = reviewMarkup(review);
    } catch (error) {
      if (disposed || currentRequest !== token) return;
      statusRoot.innerHTML = `<div role="alert">${errorCard(error, 'Application review is unavailable.')}</div>`;
    }
  }

  mounts.set(root, dispose);
  if (signal?.aborted) {
    dispose();
    return dispose;
  }
  signal?.addEventListener('abort', dispose, { once: true });
  const role = normalizeRole(session?.user?.role || session?.user?.roles?.[0]);
  if (!['employee', 'management'].includes(role)
    || !hasPermission(session, 'client_onboarding.requirement.review')) {
    root.innerHTML = emptyState('Office access and onboarding review permission are required.');
    return dispose;
  }
  root.innerHTML = `<form class="entry-form">
    <label>Office intake reference<input name="intakeReference" type="text" autocomplete="off" required /></label>
    <label>Loan application reference<input name="applicationReference" type="text" autocomplete="off" required /></label>
    <div class="action-row"><button class="button button-primary" type="submit">Open application review</button><button class="button button-outline" type="button">Clear</button></div>
  </form>
  <div data-application-review-status role="status" aria-live="polite"></div>
  <div data-application-review-information aria-live="polite"></div>`;
  form = root.querySelector('form');
  intakeInput = form.querySelector('[name="intakeReference"]');
  applicationInput = form.querySelector('[name="applicationReference"]');
  clearButton = form.querySelector('button[type="button"]');
  statusRoot = root.querySelector('[data-application-review-status]');
  reviewRoot = root.querySelector('[data-application-review-information]');
  form.addEventListener('submit', openReview);
  for (const input of [intakeInput, applicationInput]) {
    input.addEventListener('input', invalidate);
    input.addEventListener('change', invalidate);
  }
  clearButton.addEventListener('click', clear);
  return dispose;
}
