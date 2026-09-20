import { sessionHasRole } from './roles.js';
import { emptyState, errorCard, escapeHtml, hasPermission, loadingPanel } from './ui.js';

const mounts = new WeakMap();
const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
const STATUSES = ['requirements_incomplete', 'under_verification', 'eligible_for_cif', 'requirements_rejected'];
const REQUIREMENTS = [
  ['national_id', 'National ID'], ['tin_id', 'TIN ID'],
  ['meralco_bill', 'Meralco bill'], ['collector_visit', 'Collector residence visit'],
];
const INTAKE_FIELDS = [
  ['full_name', 'Full name', 2, 200], ['phone_number', 'Phone number', 7, 40],
  ['email', 'Email (optional)', 0, 320], ['present_address', 'Present address', 5, 500],
  ['national_id_egov_evidence_reference', 'National ID external eGov evidence reference', 1, 500],
  ['tin_id_egov_evidence_reference', 'TIN ID external eGov evidence reference', 1, 500],
  ['meralco_bill_evidence_reference', 'Meralco bill external evidence reference', 1, 500],
];
const OFFICE = '/api/v1/management/onboarding/applicants';
const COLLECTOR = '/api/v1/collector/onboarding/applicants';

function object(value) { return value !== null && typeof value === 'object' && !Array.isArray(value); }
function nullableText(value) { return value === null || typeof value === 'string'; }
function uuid(value) { return typeof value === 'string' && UUID.test(value); }
function keys(value, expected) { return object(value) && expected.every((name) => Object.hasOwn(value, name)); }
function validRequirement(value, visit = false) {
  return keys(value, ['status', 'evidence_reference'])
    && ['pending', 'passed', 'failed'].includes(value.status)
    && nullableText(value.evidence_reference) && (!visit || nullableText(value.note));
}
function validCase(value, reference, collector) {
  if (!object(value) || !uuid(value.applicant_id) || typeof value.application_reference !== 'string'
    || value.application_reference.trim().toLowerCase() !== reference.toLowerCase()
    || !STATUSES.includes(value.status)
    || !['full_name', 'phone_number', 'present_address'].every((name) => typeof value[name] === 'string')) return false;
  if (collector) return validRequirement(value.collector_visit, true);
  return nullableText(value.email) && (value.client_id === null || uuid(value.client_id))
    && (value.status !== 'eligible_for_cif' || uuid(value.client_id))
    && value.privacy_consent === true && value.accuracy_declaration === true
    && Array.isArray(value.bypassed_requirements) && value.bypassed_requirements.every((name) => REQUIREMENTS.some(([key]) => name === key))
    && nullableText(value.bypass_reason) && keys(value.requirements, REQUIREMENTS.map(([name]) => name))
    && REQUIREMENTS.every(([name]) => validRequirement(value.requirements[name], name === 'collector_visit'));
}
function label(value) {
  return ({ requirements_incomplete: 'Requirements incomplete', under_verification: 'Under verification',
    eligible_for_cif: 'Eligible for CIF', requirements_rejected: 'Requirements rejected',
    pending: 'Pending', passed: 'Passed', failed: 'Failed' })[value] || value;
}
function fact(name, value) { return `<div class="detail-item"><span>${escapeHtml(name)}</span><strong>${escapeHtml(value ?? 'Not provided')}</strong></div>`; }
function decision(name, title) { return `<label>${escapeHtml(title)}<select name="${name}" required><option value="">Choose decision</option><option value="passed">Passed</option><option value="failed">Failed</option></select></label>`; }

export function mountOfficeOnboarding(options) {
  return mountOnboardingCase({ ...options, collector: false });
}

// The two role surfaces share selection and request disposal; their forms,
// response projections and mutation permissions remain specific to onboarding.
export function mountOnboardingCase({ root, api, session, signal, collector }) {
  mounts.get(root)?.();
  root.innerHTML = '';
  let disposed = false;
  let token;
  let state = 'idle';
  let record = null;
  let intakeUncertain = false;
  let caseListeners = [];
  const listeners = [];
  let caseRoot;
  let statusRoot;
  let referenceInput;
  let newButton;
  const canBypass = !collector && sessionHasRole(session, 'management') && hasPermission(session, 'client_onboarding.bypass');
  const base = collector ? COLLECTOR : OFFICE;

  function listen(element, event, handler, content = true) {
    element.addEventListener(event, handler);
    (content ? caseListeners : listeners).push(() => element.removeEventListener(event, handler));
  }
  function replaceCase(markup = '') {
    for (const remove of caseListeners) remove();
    caseListeners = [];
    if (!caseRoot) return;
    for (const control of [...caseRoot.querySelectorAll('input'), ...caseRoot.querySelectorAll('textarea'), ...caseRoot.querySelectorAll('select')]) {
      control.value = '';
      if (control.getAttribute('type') === 'checkbox') control.checked = false;
    }
    caseRoot.innerHTML = markup;
  }
  function invalidate() {
    token = {};
    record = null;
    state = 'idle';
    replaceCase();
    if (statusRoot) statusRoot.innerHTML = '';
  }
  function dispose() {
    if (disposed) return;
    disposed = true;
    invalidate();
    for (const remove of listeners) remove();
    signal?.removeEventListener('abort', dispose);
    if (referenceInput) referenceInput.value = '';
    root.innerHTML = '';
    if (mounts.get(root) === dispose) mounts.delete(root);
  }
  function current(request) { return !disposed && token === request; }
  function fail(error, reloadReference = null) {
    if ([401, 403].includes(error?.status)) {
      dispose();
      root.innerHTML = `<div role="alert">${errorCard(error, 'Onboarding access is unavailable.')}</div>`;
      return;
    }
    statusRoot.innerHTML = `<div role="alert">${errorCard(error)}</div>${reloadReference
      ? '<p>Reload the intake case before changing it again.</p><button type="button" class="button button-outline" data-reload-case>Reload intake case</button>' : ''}`;
    if (reloadReference) listen(statusRoot.querySelector('[data-reload-case]'), 'click', () => loadCase(reloadReference));
  }
  function field(name) { return caseRoot.querySelector(`[name="${name}"]`); }
  function setDisabled(disabled) {
    for (const selector of ['input', 'textarea', 'select', 'button']) {
      for (const element of caseRoot.querySelectorAll(selector)) element.disabled = disabled;
    }
    if (!disabled && !collector && record) {
      const eligibility = caseRoot.querySelector('[data-eligibility]');
      if (eligibility) eligibility.disabled = !REQUIREMENTS.every(([name]) => record.requirements[name].status === 'passed');
    }
  }
  function clear() {
    if (disposed) return;
    invalidate();
    referenceInput.value = '';
    referenceInput.focus();
  }

  async function loadCase(reference) {
    if (disposed) return;
    invalidate();
    const request = token;
    const selected = reference.trim();
    if (!selected) { fail(new Error('Enter the office intake reference.')); return; }
    state = 'loading';
    statusRoot.innerHTML = loadingPanel('Loading office intake record…');
    try {
      const result = await api.request(`${base}/by-reference/${encodeURIComponent(selected)}/${collector ? 'visit-case' : 'case'}`, { signal });
      if (!current(request)) return;
      if (!validCase(result, selected, collector)) throw new Error('The intake case response is invalid or does not match this reference.');
      record = result;
      referenceInput.value = result.application_reference;
      statusRoot.innerHTML = '';
      state = 'case';
      renderCase();
    } catch (error) { if (current(request)) { state = 'blocked'; fail(error); } }
  }

  async function mutate(path, body, { method = 'POST', intake = false, eligibility = false } = {}) {
    if (disposed || !['case', 'intake'].includes(state)) return;
    const selected = record?.application_reference;
    const request = {};
    token = request;
    state = 'saving';
    if (intake) { intakeUncertain = true; newButton.disabled = true; }
    setDisabled(true);
    statusRoot.innerHTML = loadingPanel('Recording office information…');
    try {
      const result = await api.request(path, { method, signal, ...(body === undefined ? {} : { body }) });
      if (!current(request)) return;
      if (!object(result) || !STATUSES.includes(result.status)
        || (intake && (typeof result.application_reference !== 'string' || !result.application_reference.trim()))
        || (eligibility && (result.status !== 'eligible_for_cif' || !uuid(result.client_id)))) {
        throw new Error('The saved result could not be verified.');
      }
      if (intake) { intakeUncertain = false; newButton.disabled = false; }
      await loadCase(intake ? result.application_reference : selected);
    } catch (error) {
      if (!current(request)) return;
      const retry = [400, 422].includes(error?.status);
      state = retry ? (intake ? 'intake' : 'case') : 'blocked';
      if (intake && retry) { intakeUncertain = false; newButton.disabled = false; }
      setDisabled(!retry);
      fail(error, !retry && !intake ? selected : null);
      if (intake && !retry && !disposed) statusRoot.innerHTML += '<p>The intake outcome is uncertain. Do not submit another intake; verify the office record before continuing.</p>';
    }
  }

  function renderIntake() {
    if (disposed || intakeUncertain) return;
    invalidate();
    state = 'intake';
    replaceCase(`<form class="entry-form" data-intake-form><h3>New office intake</h3>
      <p>Record evidence references from the approved external verification process. Entering a reference does not verify a document or pass a requirement.</p>
      ${INTAKE_FIELDS.map(([name, title, minimum, maximum]) => `<label>${escapeHtml(title)}${name === 'present_address'
        ? `<textarea name="${name}" minlength="${minimum}" maxlength="${maximum}" required></textarea>`
        : `<input type="${name === 'phone_number' ? 'tel' : 'text'}" name="${name}" maxlength="${maximum}"${minimum ? ` minlength="${minimum}" required` : ''} autocomplete="off" />`}</label>`).join('')}
      <label><input type="checkbox" name="privacy_consent" required />Applicant's required privacy consent has been recorded.</label>
      <label><input type="checkbox" name="accuracy_declaration" required />Applicant has declared the intake information accurate.</label>
      <button class="button button-primary" type="submit">Record office intake</button></form>`);
    listen(caseRoot.querySelector('form'), 'submit', (event) => {
      event.preventDefault();
      if (state !== 'intake') return;
      const values = {};
      for (const [name, title, minimum, maximum] of INTAKE_FIELDS) {
        const raw = field(name).value;
        const normalized = name === 'phone_number' ? raw.replace(/\D/g, '') : raw.trim().replace(/\s+/g, ' ');
        if (normalized.length < minimum || raw.length > maximum) { fail(new Error(`${title} is required within its allowed length.`)); return; }
        values[name] = name === 'email' && !raw.trim() ? null : raw;
      }
      if (!field('privacy_consent').checked || !field('accuracy_declaration').checked) {
        fail(new Error('Record the applicant’s required privacy consent and accuracy declaration before submitting.')); return;
      }
      mutate(OFFICE, { ...values, privacy_consent: true, accuracy_declaration: true }, { intake: true });
    });
  }

  function renderCase() {
    const currentCase = record;
    const requirements = collector ? [['collector_visit', 'Collector residence visit']] : REQUIREMENTS;
    const required = collector ? { collector_visit: record.collector_visit } : record.requirements;
    const nonPassed = collector ? [] : REQUIREMENTS.filter(([name]) => required[name].status !== 'passed');
    replaceCase(`<article class="data-card"><h3>Office intake case</h3><div class="detail-grid">
      ${fact('Office intake reference', record.application_reference)}${fact('Status', label(record.status))}
      ${fact('Full name', record.full_name)}${fact('Phone number', record.phone_number)}
      ${!collector ? fact('Email', record.email) : ''}${fact('Present address', record.present_address)}</div>
      <h4>${collector ? 'Residence visit record' : 'Pre-CIF requirements'}</h4>
      <p>Recorded external evidence references are shown for review. Requirement results remain separate from CIF liveness and loan approval.</p>
      <div class="detail-grid">${requirements.map(([name, title]) => `${fact(title, label(required[name].status))}${fact(`${title} evidence reference`, required[name].evidence_reference)}${name === 'collector_visit' ? fact('Visit note', required[name].note) : ''}`).join('')}</div>
      ${!collector ? `<p>Required privacy consent and accuracy declaration were recorded at intake.</p>${record.bypassed_requirements.length
        ? `<p>Management bypass: ${escapeHtml(record.bypassed_requirements.map((name) => REQUIREMENTS.find(([key]) => key === name)[1]).join(', '))}</p><p>${escapeHtml(record.bypass_reason)}</p>` : ''}` : ''}
      </article>
      ${collector ? `<form class="entry-form" data-visit-form><h4>Record residence visit</h4>${decision('result', 'Observed visit result')}
        <label>Visit note<textarea name="note" maxlength="500"></textarea></label>
        <label>External visit evidence reference (optional)<input name="evidence_reference" maxlength="500" autocomplete="off" /></label>
        <button class="button button-primary" type="submit">Record residence visit</button></form>`
        : record.status === 'eligible_for_cif' ? '<p class="notice-card">Eligible for CIF. Continue CIF work using this office intake reference. Eligibility alone does not create credentials or a loan.</p>'
          : `<form class="entry-form" data-document-review><h4>Review document requirements</h4>${REQUIREMENTS.slice(0, 3).map(([name, title]) => decision(`${name}_status`, title)).join('')}
            <button class="button button-primary" type="submit">Save document review</button></form>
            <p>Normal CIF eligibility requires all four requirements to be passed.</p><button class="button button-primary" type="button" data-eligibility${nonPassed.length ? ' disabled' : ''}>Approve CIF eligibility</button>
            ${canBypass && nonPassed.length ? `<form class="entry-form" data-bypass-form><h4>Management requirement bypass</h4><p>Select every currently non-passed requirement and record the reason. Original requirement results remain unchanged.</p>
              ${nonPassed.map(([name, title]) => `<label><input type="checkbox" name="bypass_${name}" />${escapeHtml(title)} (${escapeHtml(label(required[name].status))})</label>`).join('')}
              <label>Bypass reason<textarea name="bypass_reason" minlength="3" maxlength="500" required></textarea></label>
              <button class="button button-primary" type="submit">Approve requirement bypass</button></form>` : ''}`}`);
    if (collector) {
      listen(caseRoot.querySelector('[data-visit-form]'), 'submit', (event) => {
        event.preventDefault();
        if (state !== 'case') return;
        const result = field('result').value;
        if (!['passed', 'failed'].includes(result)) { fail(new Error('Choose the observed visit result.')); return; }
        mutate(`${COLLECTOR}/${encodeURIComponent(currentCase.applicant_id)}/visit`, {
          result, note: field('note').value, evidence_reference: field('evidence_reference').value.trim() || null,
        });
      });
    } else if (record.status !== 'eligible_for_cif') {
      listen(caseRoot.querySelector('[data-document-review]'), 'submit', (event) => {
        event.preventDefault();
        if (state !== 'case') return;
        const body = Object.fromEntries(REQUIREMENTS.slice(0, 3).map(([name]) => [`${name}_status`, field(`${name}_status`).value]));
        if (!Object.values(body).every((value) => ['passed', 'failed'].includes(value))) { fail(new Error('Choose an explicit decision for each document requirement.')); return; }
        mutate(`${OFFICE}/${encodeURIComponent(currentCase.applicant_id)}/document-requirements`, body, { method: 'PATCH' });
      });
      listen(caseRoot.querySelector('[data-eligibility]'), 'click', () => {
        if (!nonPassed.length) mutate(`${OFFICE}/${encodeURIComponent(currentCase.applicant_id)}/eligibility`, undefined, { eligibility: true });
      });
      if (canBypass && nonPassed.length) listen(caseRoot.querySelector('[data-bypass-form]'), 'submit', (event) => {
        event.preventDefault();
        if (state !== 'case') return;
        const selected = nonPassed.filter(([name]) => field(`bypass_${name}`).checked).map(([name]) => name);
        const reason = field('bypass_reason').value;
        if (selected.length !== nonPassed.length || reason.trim().replace(/\s+/g, ' ').length < 3 || reason.length > 500) {
          fail(new Error('Select every non-passed requirement and enter a bypass reason of 3–500 characters.')); return;
        }
        mutate(`${OFFICE}/${encodeURIComponent(currentCase.applicant_id)}/eligibility/bypass`, { bypassed_requirements: selected, reason }, { eligibility: true });
      });
    }
  }

  mounts.set(root, dispose);
  if (signal?.aborted) { dispose(); return dispose; }
  signal?.addEventListener('abort', dispose, { once: true });
  const permission = collector ? 'client_onboarding.visit.record' : 'client_onboarding.requirement.review';
  if (!(collector ? sessionHasRole(session, 'collector') : sessionHasRole(session, 'employee', 'management')) || !hasPermission(session, permission)) {
    root.innerHTML = emptyState('The required role and onboarding permission are needed.'); return dispose;
  }
  root.innerHTML = `<form class="entry-form" data-case-lookup><label>Office intake reference<input name="applicationReference" autocomplete="off" required /></label>
    <div class="action-row"><button class="button button-primary" type="submit">${collector ? 'Open residence visit' : 'Open intake case'}</button><button class="button button-outline" type="button" data-clear-case>Clear</button>
    ${collector ? '' : '<button class="button button-outline" type="button" data-new-intake>New office intake</button>'}</div></form>
    <div data-onboarding-status role="status" aria-live="polite"></div><div data-onboarding-case></div>`;
  caseRoot = root.querySelector('[data-onboarding-case]');
  statusRoot = root.querySelector('[data-onboarding-status]');
  referenceInput = root.querySelector('[name="applicationReference"]');
  listen(root.querySelector('[data-case-lookup]'), 'submit', (event) => { event.preventDefault(); loadCase(referenceInput.value); }, false);
  listen(referenceInput, 'input', invalidate, false);
  listen(referenceInput, 'change', invalidate, false);
  listen(root.querySelector('[data-clear-case]'), 'click', clear, false);
  if (!collector) { newButton = root.querySelector('[data-new-intake]'); listen(newButton, 'click', renderIntake, false); }
  return dispose;
}
