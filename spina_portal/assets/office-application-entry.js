import { normalizeRole } from './roles.js';
import { emptyState, errorCard, escapeHtml, hasPermission, loadingPanel } from './ui.js';

const mounts = new WeakMap();
const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
const DECIMAL = /^[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?$/;
const REQUEST = [
  ['requested_loan_type_id', 'Requested product', 'product'],
  ['purpose', 'Purpose', 'text'],
  ['requested_amount', 'Requested amount (PHP)', 'money'],
  ['requested_payment_arrangement', 'Requested payment arrangement', 'text'],
  ['requested_term', 'Requested term', 'text'],
  ['preferred_first_payment_date', 'Preferred first payment date', 'date'],
];
const REPAYMENT = [
  ['repayment_source', 'Repayment source', 'text'],
  ['source_details', 'Source details', 'text'],
  ['monthly_gross_income', 'Monthly gross income (PHP)', 'money'],
  ['monthly_net_income', 'Monthly net income (PHP)', 'money'],
  ['has_existing_obligations', 'Existing obligations', 'boolean'],
];
const OBLIGATION = [
  ['creditor', 'Creditor', 'text'],
  ['outstanding_balance', 'Outstanding balance (PHP)', 'money'],
  ['periodic_payment_amount', 'Periodic payment amount (PHP)', 'money'],
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

function object(value) { return value !== null && typeof value === 'object' && !Array.isArray(value); }
function uuid(value) { return typeof value === 'string' && UUID.test(value); }
function sameId(left, right) { return uuid(left) && uuid(right) && left.toLowerCase() === right.toLowerCase(); }
function positiveInteger(value) { return Number.isSafeInteger(value) && value > 0; }
function hasKeys(value, names) {
  return object(value) && Object.keys(value).length === names.length
    && names.every((name) => Object.hasOwn(value, name));
}
function nullable(value, kind) {
  if (value === null) return true;
  if (kind === 'boolean') return typeof value === 'boolean';
  if (typeof value !== 'string') return false;
  if (kind === 'product') return uuid(value);
  if (kind === 'money') return DECIMAL.test(value);
  if (kind === 'date') return /^\d{4}-\d{2}-\d{2}$/.test(value)
    && !Number.isNaN(Date.parse(`${value}T00:00:00Z`));
  return true;
}
function validFields(value, fields, extra = []) {
  return hasKeys(value, [...fields.map(([name]) => name), ...extra])
    && fields.every(([name, , kind]) => nullable(value[name], kind));
}
function validInformation(value) {
  return (hasKeys(value, ['request', 'repayment']) || (hasKeys(value, ['request', 'repayment', 'details'])
      && hasKeys(value.details, ['schema_version', 'employment', 'references'])
      && value.details.schema_version === 1 && validFields(value.details.employment, EMPLOYMENT)
      && Array.isArray(value.details.references) && value.details.references.every((row) => validFields(row, REFERENCE))))
    && validFields(value.request, REQUEST)
    && validFields(value.repayment, REPAYMENT, ['obligations'])
    && Array.isArray(value.repayment.obligations)
    && value.repayment.obligations.every((row) => validFields(row, OBLIGATION))
    && !(value.repayment.has_existing_obligations === false && value.repayment.obligations.length);
}
function sameInformation(left, right) {
  return REQUEST.every(([name]) => left.request[name] === right.request[name])
    && REPAYMENT.every(([name]) => left.repayment[name] === right.repayment[name])
    && left.repayment.obligations.length === right.repayment.obligations.length
    && left.repayment.obligations.every((row, index) => OBLIGATION.every(([name]) => row[name] === right.repayment.obligations[index][name]))
    && ((!left.details && !right.details) || (left.details && right.details
      && EMPLOYMENT.every(([name]) => left.details.employment[name] === right.details.employment[name])
      && left.details.references.length === right.details.references.length
      && left.details.references.every((row, index) => REFERENCE.every(([name]) => row[name] === right.details.references[index][name]))));
}
function validApplication(value, clientId, reference, enriched = false) {
  if (!object(value) || !sameId(value.client_id, clientId)
    || !['application_id', 'application_version_id', 'cif_version_id'].every((name) => uuid(value[name]))
    || value.application_reference !== reference || !positiveInteger(value.version_number)
    || value.review_scope !== 'loan_application_information_only' || !validInformation(value.information)
    || typeof value.recorded_at !== 'string'
    || !/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})$/.test(value.recorded_at)
    || Number.isNaN(Date.parse(value.recorded_at))) return false;
  const missing = new Set([
    ...REQUEST.slice(0, 5).map(([name]) => `request.${name}`),
    ...REPAYMENT.map(([name]) => `repayment.${name}`), 'repayment.obligations',
    ...value.information.repayment.obligations.flatMap((_, index) => OBLIGATION.slice(0, 4)
      .map(([name]) => `repayment.obligations[${index}].${name}`)),
  ]);
  return Array.isArray(value.missing_fields) && value.missing_fields.every((name) => missing.has(name))
    && (!enriched || (positiveInteger(value.cif_version_number)
      && (value.requested_loan_type_name === null || typeof value.requested_loan_type_name === 'string')));
}
function validContext(value, clientId) {
  if (!hasKeys(value, ['client_id', 'cif_version_id', 'cif_version_number', 'loan_types'])
    || !sameId(value.client_id, clientId) || !uuid(value.cif_version_id)
    || !positiveInteger(value.cif_version_number) || !Array.isArray(value.loan_types)) return false;
  const ids = new Set();
  return value.loan_types.every((product) => {
    if (!hasKeys(product, ['id', 'code', 'name']) || !uuid(product.id)
      || typeof product.code !== 'string' || typeof product.name !== 'string'
      || ids.has(product.id.toLowerCase())) return false;
    ids.add(product.id.toLowerCase());
    return true;
  });
}
function blank(fields) { return Object.fromEntries(fields.map(([name]) => [name, null])); }

export function mountOfficeApplicationEntry({
  root, api, session, clientId, applicationReference, review = null, signal, onSaved, onCancel,
}) {
  mounts.get(root)?.();
  root.innerHTML = '';
  let disposed = false;
  let request;
  let state = 'loading';
  let needsReconciliation = false;
  let reference = typeof applicationReference === 'string' ? applicationReference.trim() : '';
  let original = null;
  let context = null;
  let fields = {};
  let rowCount = 0;
  let referenceCount = 0;
  let listeners = [];

  function listen(element, event, handler) {
    element.addEventListener(event, handler);
    listeners.push(() => element.removeEventListener(event, handler));
  }

  function replaceContent(markup) {
    for (const remove of listeners) remove();
    listeners = [];
    for (const element of [...root.querySelectorAll('input'), ...root.querySelectorAll('textarea'), ...root.querySelectorAll('select')]) {
      element.value = '';
      if (element.getAttribute('type') === 'checkbox') element.checked = false;
    }
    fields = {};
    root.innerHTML = markup;
  }

  function dispose() {
    if (disposed) return;
    disposed = true;
    request = {};
    context = null;
    original = null;
    review = null;
    reference = '';
    onSaved = null;
    onCancel = null;
    replaceContent('');
    signal?.removeEventListener('abort', dispose);
    if (mounts.get(root) === dispose) mounts.delete(root);
  }

  function current(token) { return !disposed && request === token; }
  function close(reload) {
    if (disposed) return;
    const callback = onCancel;
    const reconcile = reload || needsReconciliation;
    dispose();
    callback?.({ reload: reconcile });
  }
  function cancelMarkup() { return '<button class="button button-outline" type="button" data-cancel-application>Cancel</button>'; }
  function bindCancel() { listen(root.querySelector('[data-cancel-application]'), 'click', () => close(false)); }
  function showError(error, reload = false) {
    const status = root.querySelector('[data-entry-status]');
    status.innerHTML = `<div role="alert">${errorCard(error)}</div>${reload
      ? '<p>Reload the application before saving again.</p><button class="button button-outline" type="button" data-reload-application>Reload application</button>' : ''}`;
    if (reload) listen(status.querySelector('[data-reload-application]'), 'click', () => close(true));
  }
  function denyAccess(error) {
    request = {};
    state = 'denied';
    original = null;
    context = null;
    replaceContent(`<div role="alert">${errorCard(error, 'Office access is required for application entry.')}</div>${cancelMarkup()}`);
    bindCancel();
  }
  function sourceChanged() { return original && !sameId(original.cif_version_id, context.cif_version_id); }
  function sourceChosen() { return !sourceChanged() || fields.use_current_cif?.checked === true; }
  function updateSave() {
    root.querySelector('button[type="submit"]').disabled = state !== 'editing' || !sourceChosen();
  }
  function setDisabled(disabled) {
    for (const field of Object.values(fields)) field.disabled = disabled;
    for (const button of root.querySelectorAll('[data-obligation-action]')) button.disabled = disabled;
    for (const button of root.querySelectorAll('[data-reference-action]')) button.disabled = disabled;
    updateSave();
  }

  function fieldMarkup([name, label, kind], prefix = '') {
    const fieldName = `${prefix}${name}`;
    let control;
    if (kind === 'product') {
      const selected = original?.information.request.requested_loan_type_id;
      const unavailable = selected && !context.loan_types.some((product) => sameId(product.id, selected));
      control = `<select name="${fieldName}"><option value="">Not provided</option>
        ${context.loan_types.map((product) => `<option value="${escapeHtml(product.id)}">${escapeHtml(product.name)} (${escapeHtml(product.code)})</option>`).join('')}
        ${unavailable ? `<option value="${escapeHtml(selected)}">Previously selected product (unavailable in current catalog)</option>` : ''}</select>`;
    } else if (kind === 'boolean') {
      control = `<select name="${fieldName}"><option value="">Not provided</option><option value="true">Yes</option><option value="false">No</option></select>`;
    } else if (['purpose', 'source_details', 'notes'].includes(name)) {
      control = `<textarea name="${fieldName}"></textarea>`;
    } else {
      control = `<input type="${kind === 'date' ? 'date' : 'text'}" name="${fieldName}"${kind === 'money' ? ' inputmode="decimal"' : ''} autocomplete="off" />`;
    }
    return `<label>${escapeHtml(label)}${control}</label>`;
  }

  function readInformation() {
    function values(definitions, prefix = '') {
      return Object.fromEntries(definitions.map(([name, , kind]) => {
        const raw = fields[`${prefix}${name}`].value;
        if (kind === 'boolean') {
          if (!['', 'true', 'false'].includes(raw)) throw new Error('Choose Yes, No, or Not provided for existing obligations.');
          return [name, raw === '' ? null : raw === 'true'];
        }
        return [name, raw.trim() ? raw : null];
      }));
    }
    const information = {
      request: values(REQUEST),
      repayment: { ...values(REPAYMENT), obligations: Array.from({ length: rowCount }, (_, index) => values(OBLIGATION, `obligation_${index}_`)) },
    };
    const employment = values(EMPLOYMENT);
    if (original?.information.details || referenceCount || Object.values(employment).some((value) => value !== null)) {
      information.details = { schema_version: 1, employment,
        references: Array.from({ length: referenceCount }, (_, index) => values(REFERENCE, `reference_${index}_`)) };
    }
    return information;
  }

  function changeRows(index, references = false) {
    if (disposed || state !== 'editing') return;
    const values = readInformation();
    const selectedSource = sourceChosen();
    if (references && !values.details) values.details = { schema_version: 1, employment: blank(EMPLOYMENT), references: [] };
    const rows = references ? values.details.references : values.repayment.obligations;
    if (index === null) rows.push(blank(references ? REFERENCE : OBLIGATION));
    else rows.splice(index, 1);
    renderForm(values, selectedSource);
  }

  function renderForm(information, selectedSource = false) {
    state = 'editing';
    rowCount = information.repayment.obligations.length;
    referenceCount = information.details?.references.length ?? 0;
    replaceContent(`<form class="entry-form">
      <h3>${original ? 'Edit application information' : 'New application'}</h3>
      <p>Loan application reference: ${escapeHtml(reference)}</p>
      <p>Source CIF version ${escapeHtml(context.cif_version_number)}</p>
      ${sourceChanged() ? `<p>Saved application uses CIF version ${escapeHtml(original.cif_version_number)}. A newer source is available.</p>
        <label><input type="checkbox" name="use_current_cif" />Use current CIF version ${escapeHtml(context.cif_version_number)} for this new application version</label>` : ''}
      <p>Requested information only; approval and release are separate. You can save an incomplete draft. Blank fields mean Not provided.</p>
      <h4>Requested loan information</h4>${REQUEST.map((definition) => fieldMarkup(definition)).join('')}
      <h4>Repayment information</h4>${REPAYMENT.map((definition) => fieldMarkup(definition)).join('')}
      <h4>Declared obligations</h4>
      ${information.repayment.obligations.map((_, index) => `<section class="data-card"><h5>Obligation ${index + 1}</h5>${OBLIGATION.map((definition) => fieldMarkup(definition, `obligation_${index}_`)).join('')}
        <button class="button button-outline" type="button" data-obligation-action="remove-${index}">Remove obligation ${index + 1}</button></section>`).join('')}
      <button class="button button-outline" type="button" data-obligation-action="add">Add obligation</button>
      <h4>Employment or business details</h4>
      <p>Optional declared information. These entries do not verify employment, income, or a reference.</p>
      ${EMPLOYMENT.map((definition) => fieldMarkup(definition)).join('')}
      <h4>References or emergency contacts</h4><p>Optional; add the contacts the applicant provides.</p>
      ${(information.details?.references ?? []).map((_, index) => `<section class="data-card"><h5>Reference ${index + 1}</h5>${REFERENCE.map((definition) => fieldMarkup(definition, `reference_${index}_`)).join('')}
        <button class="button button-outline" type="button" data-reference-action="remove-${index}">Remove reference ${index + 1}</button></section>`).join('')}
      <button class="button button-outline" type="button" data-reference-action="add">Add reference</button>
      <div class="action-row"><button class="button button-primary" type="submit">Save application</button>${cancelMarkup()}</div>
    </form><div data-entry-status role="status" aria-live="polite"></div>`);
    function fill(definitions, values, prefix = '') {
      for (const [name] of definitions) {
        const element = root.querySelector(`[name="${prefix}${name}"]`);
        fields[`${prefix}${name}`] = element;
        element.value = values[name] === null ? '' : String(values[name]);
      }
    }
    fill(REQUEST, information.request);
    fill(REPAYMENT, information.repayment);
    information.repayment.obligations.forEach((row, index) => fill(OBLIGATION, row, `obligation_${index}_`));
    fill(EMPLOYMENT, information.details?.employment ?? blank(EMPLOYMENT));
    information.details?.references.forEach((row, index) => fill(REFERENCE, row, `reference_${index}_`));
    if (sourceChanged()) {
      fields.use_current_cif = root.querySelector('[name="use_current_cif"]');
      fields.use_current_cif.checked = selectedSource;
      listen(fields.use_current_cif, 'change', updateSave);
    }
    listen(root.querySelector('form'), 'submit', save);
    listen(root.querySelector('[data-obligation-action="add"]'), 'click', () => changeRows(null));
    information.repayment.obligations.forEach((_, index) => {
      listen(root.querySelector(`[data-obligation-action="remove-${index}"]`), 'click', () => changeRows(index));
    });
    listen(root.querySelector('[data-reference-action="add"]'), 'click', () => changeRows(null, true));
    information.details?.references.forEach((_, index) => {
      listen(root.querySelector(`[data-reference-action="remove-${index}"]`), 'click', () => changeRows(index, true));
    });
    bindCancel();
    updateSave();
  }

  async function loadContext() {
    const token = {};
    request = token;
    replaceContent(`${loadingPanel('Loading application entry context…')}<div data-entry-status role="status" aria-live="polite"></div>${cancelMarkup()}`);
    bindCancel();
    try {
      const value = await api.request(`/api/v1/management/clients/${encodeURIComponent(clientId)}/loan-applications/entry-context`, { signal });
      if (!current(token)) return;
      if (!validContext(value, clientId) || (original && sameId(original.cif_version_id, value.cif_version_id)
        && original.cif_version_number !== value.cif_version_number)) {
        throw new Error('The application entry context is invalid or does not match this Client.');
      }
      context = value;
      renderForm(original?.information ?? { request: blank(REQUEST), repayment: { ...blank(REPAYMENT), obligations: [] } });
    } catch (error) {
      if (!current(token)) return;
      if ([401, 403].includes(error?.status)) { denyAccess(error); return; }
      state = 'blocked';
      replaceContent(`<div data-entry-status role="status" aria-live="polite"></div>${cancelMarkup()}`);
      showError(error, true);
      bindCancel();
    }
  }

  function validSave(saved, information) {
    if (!validApplication(saved, clientId, reference) || !sameId(saved.cif_version_id, context.cif_version_id)) return false;
    if (!original) return saved.version_number === 1;
    if (!sameId(saved.application_id, original.application_id)) return false;
    if (saved.version_number === original.version_number + 1) return !sameId(saved.application_version_id, original.application_version_id);
    return saved.version_number === original.version_number
      && sameId(saved.application_version_id, original.application_version_id)
      && sameInformation(information, original.information) && sameInformation(saved.information, original.information);
  }

  async function save(event) {
    event.preventDefault();
    if (disposed || state !== 'editing' || !sourceChosen()) return;
    let information;
    try {
      information = readInformation();
      if (information.repayment.has_existing_obligations === false && information.repayment.obligations.length) {
        throw new Error('Remove the obligation rows or change the existing obligations answer before saving.');
      }
      const product = information.request.requested_loan_type_id;
      if (product !== null && !context.loan_types.some((item) => sameId(item.id, product))
        && !sameId(original?.information.request.requested_loan_type_id, product)) {
        throw new Error('Choose a product from the current catalog.');
      }
    } catch (error) { showError(error); return; }
    const token = {};
    request = token;
    state = 'saving';
    needsReconciliation = true;
    setDisabled(true);
    root.querySelector('[data-entry-status]').innerHTML = loadingPanel('Saving application information…');
    let saved;
    try {
      const base = `/api/v1/management/clients/${encodeURIComponent(clientId)}/loan-applications`;
      saved = await api.request(original ? `${base}/${encodeURIComponent(original.application_id)}/draft-versions` : `${base}/drafts`, {
        method: 'POST', signal,
        body: original
          ? { cif_version_id: context.cif_version_id, expected_version_number: original.version_number, information }
          : { cif_version_id: context.cif_version_id, application_reference: reference, information },
      });
      if (!current(token)) return;
      if (!validSave(saved, information)) throw new Error('The application save response could not be verified.');
    } catch (error) {
      if (!current(token)) return;
      if ([401, 403].includes(error?.status)) { needsReconciliation = false; denyAccess(error); return; }
      const retry = [400, 422].includes(error?.status);
      if (retry) needsReconciliation = false;
      state = retry ? 'editing' : 'blocked';
      setDisabled(!retry);
      showError(error, !retry);
      return;
    }
    const callback = onSaved;
    dispose();
    callback?.(saved);
  }

  mounts.set(root, dispose);
  if (signal?.aborted) { dispose(); return dispose; }
  signal?.addEventListener('abort', dispose, { once: true });
  const role = normalizeRole(session?.user?.role || session?.user?.roles?.[0]);
  if (!['employee', 'management'].includes(role) || !hasPermission(session, 'client_onboarding.requirement.review')) {
    state = 'denied';
    replaceContent(emptyState('Office access and onboarding review permission are required.'));
  } else if (!uuid(clientId) || !reference || (review !== null && !validApplication(review, clientId, reference, true))) {
    state = 'blocked';
    replaceContent(emptyState('A valid Client, application reference, and saved review are required.'));
  } else {
    original = review === null ? null : structuredClone(review);
    loadContext();
  }
  review = null;
  return dispose;
}
