import { sessionHasRole } from './roles.js';
import { emptyState, errorCard, escapeHtml, hasPermission, loadingPanel } from './ui.js';

const mounts = new WeakMap();
const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
const INFORMATION = ['full_name', 'phone_number', 'email', 'present_address'];
const FIELDS = [
  ['full_name', 'Full name', 2, 200],
  ['phone_number', 'Phone number', 7, 40],
  ['email', 'Email (optional)', 0, 320],
  ['present_address', 'Present address', 5, 500],
  ['reason', 'Reason for correction', 3, 500],
];

function validReview(review, clientId, expected) {
  return review !== null && typeof review === 'object' && !Array.isArray(review)
    && typeof review.client_id === 'string' && UUID.test(review.client_id)
    && review.client_id.toLowerCase() === clientId.toLowerCase()
    && typeof review.cif_version_id === 'string' && UUID.test(review.cif_version_id)
    && Number.isSafeInteger(review.version_number) && review.version_number > 0
    && review.review_scope === 'cif_information_only'
    && INFORMATION.every((field) => typeof review[field] === 'string'
      || (field === 'email' && review[field] === null))
    && (!expected || (review.cif_version_id.toLowerCase() === expected.cif_version_id.toLowerCase()
      && review.version_number === expected.version_number));
}

function editedInformation(fields) {
  const values = Object.fromEntries(FIELDS.map(([name]) => [name, fields[name].value]));
  for (const [name, label, minimum, maximum] of FIELDS) {
    const raw = values[name];
    const normalized = name === 'phone_number'
      ? raw.replace(/\D/g, '') : raw.trim().replace(/\s+/g, ' ');
    if (raw.length > maximum || normalized.length < minimum) {
      throw new Error(`${label} must contain ${minimum ? `${minimum}–` : 'at most '}${maximum} characters${name === 'phone_number' ? ', including at least 7 digits' : ''}.`);
    }
  }
  return {
    information: Object.fromEntries(INFORMATION.map((name) => [
      name, name === 'email' && !values[name].trim() ? null : values[name],
    ])),
    reason: values.reason,
  };
}

export function mountOfficeCifCorrection({
  root, api, session, clientId, signal, onEditing, onClosed, onSaved, onAccessDenied,
  allowSuccessor = false, includeIdentity = false,
}) {
  mounts.get(root)?.();
  root.innerHTML = '';
  let disposed = false;
  let request;
  let state = 'idle';
  let original = null;
  let expectedInformation = null;
  let fields = {};
  let listeners = [];
  let successor = false;
  const identityFields = ['birth_date', 'birth_place', 'civil_status', 'citizenship'];

  function listen(element, event, handler) {
    element.addEventListener(event, handler);
    listeners.push(() => element.removeEventListener(event, handler));
  }

  function replaceContent(markup) {
    for (const remove of listeners) remove();
    listeners = [];
    for (const element of [...root.querySelectorAll('input'), ...root.querySelectorAll('textarea')]) {
      element.value = '';
    }
    fields = {};
    root.innerHTML = markup;
  }

  function clearSnapshot() {
    request = {};
    original = null;
    expectedInformation = null;
  }

  function dispose() {
    if (disposed) return;
    disposed = true;
    clearSnapshot();
    replaceContent('');
    signal?.removeEventListener('abort', dispose);
    if (mounts.get(root) === dispose) mounts.delete(root);
  }

  function current(token) {
    return !disposed && request === token;
  }

  function start() {
    state = 'idle';
    replaceContent('<button class="button button-outline" type="button" data-correct-cif>Correct information</button>');
    listen(root.querySelector('[data-correct-cif]'), 'click', loadCurrent);
  }

  function cancel() {
    if (disposed) return;
    clearSnapshot();
    start();
    onClosed?.();
  }

  function cancelMarkup() {
    return '<button class="button button-outline" type="button" data-cancel-cif>Cancel</button>';
  }

  function bindCancel() {
    listen(root.querySelector('[data-cancel-cif]'), 'click', cancel);
  }

  function denyAccess(error) {
    clearSnapshot();
    state = 'denied';
    replaceContent(`<div role="alert">${errorCard(error, 'Office access is required for correction.')}</div>`);
    onAccessDenied?.(error);
  }

  function reloadMarkup() {
    return '<button class="button button-outline" type="button" data-reload-cif>Reload current CIF</button>';
  }

  function showError(error, reload = false) {
    const status = root.querySelector('[data-correction-status]');
    status.innerHTML = `<div role="alert">${errorCard(error)}</div>${reload
      ? `<p>Reload the current CIF before saving again.</p>${reloadMarkup()}` : ''}`;
    if (reload) listen(status.querySelector('[data-reload-cif]'), 'click', loadCurrent);
  }

  function setFieldsDisabled(disabled) {
    for (const field of Object.values(fields)) field.disabled = disabled;
    root.querySelector('button[type="submit"]').disabled = disabled;
  }

  function renderForm(review) {
    state = 'editing';
    original = { cif_version_id: review.cif_version_id, version_number: review.version_number };
    expectedInformation = Object.fromEntries(INFORMATION.map((name) => [name, review[name]]));
    if (review.identity_information != null) expectedInformation.identity_information = { ...review.identity_information };
    replaceContent(`<form class="entry-form">
      ${FIELDS.map(([name, label, minimum, maximum]) => {
        const attributes = `name="${name}" maxlength="${maximum}"${minimum ? ` minlength="${minimum}" required` : ''}`;
        return `<label>${label}${['present_address', 'reason'].includes(name)
          ? `<textarea ${attributes}></textarea>` : `<input type="${name === 'phone_number' ? 'tel' : 'text'}" ${attributes} autocomplete="off" />`}</label>`;
      }).join('')}
      ${includeIdentity ? identityFields.map(name => `<label>${name.replaceAll('_', ' ')} (optional)<input name="${name}" type="${name === 'birth_date' ? 'date' : 'text'}" maxlength="${name === 'birth_place' ? 300 : 100}" autocomplete="off" /></label>`).join('') : ''}
      ${successor ? '<p>A new CIF draft will preserve the earlier review and activation history. This new draft requires fresh review and verification.</p>' : ''}
      <div class="action-row"><button class="button button-primary" type="submit">${successor ? 'Start new review cycle' : 'Save correction'}</button>${cancelMarkup()}</div>
    </form><div data-correction-status role="status" aria-live="polite"></div>`);
    fields = Object.fromEntries(FIELDS.map(([name]) => [name, root.querySelector(`[name="${name}"]`)]));
    for (const name of INFORMATION) fields[name].value = review[name] ?? '';
    if (includeIdentity) for (const name of identityFields) {
      fields[name] = root.querySelector(`[name="${name}"]`);
      fields[name].value = review.identity_information?.[name] ?? '';
    }
    listen(root.querySelector('form'), 'submit', save);
    bindCancel();
  }

  async function loadCurrent() {
    if (disposed || state === 'denied' || state === 'saving') return;
    clearSnapshot();
    const token = request;
    state = 'loading';
    replaceContent(`${loadingPanel('Loading current CIF for correction…')}${cancelMarkup()}`);
    bindCancel();
    onEditing?.();
    if (!current(token)) return;
    try {
      const review = await api.request(
        `/api/v1/management/clients/${encodeURIComponent(clientId)}/cif/review-summary?include_correction_availability=true${includeIdentity ? '&include_identity_information=true' : ''}`,
      );
      if (!current(token)) return;
      if (!validReview(review, clientId) || typeof review.can_correct_information !== 'boolean') {
        throw new Error('The current CIF response is invalid or does not match this Client.');
      }
      successor = !review.can_correct_information && allowSuccessor;
      if (!review.can_correct_information && !allowSuccessor) {
        state = 'unavailable';
        replaceContent(`<p class="notice-card">This CIF is read-only. Corrections are unavailable for its current state.</p>
          <div class="detail-grid">${FIELDS.slice(0, 4).map(([name, label]) => `<div class="detail-item"><span>${label}</span><strong>${escapeHtml(review[name] ?? 'Not provided')}</strong></div>`).join('')}</div>
          ${cancelMarkup()}`);
        bindCancel();
        return;
      }
      renderForm(review);
    } catch (error) {
      if (!current(token)) return;
      if ([401, 403].includes(error?.status)) {
        denyAccess(error);
        return;
      }
      state = 'blocked';
      replaceContent(`<div data-correction-status role="status" aria-live="polite"></div>${cancelMarkup()}`);
      showError(error, true);
      bindCancel();
    }
  }

  async function save(event) {
    event.preventDefault();
    if (disposed || state !== 'editing') return;
    let edited;
    try {
      edited = editedInformation(fields);
      if (includeIdentity) {
        const identity = Object.fromEntries(identityFields.map(name => [name, fields[name].value.trim() || null]));
        if (expectedInformation.identity_information || Object.values(identity).some(value => value !== null)) {
          edited.information.identity_information = identity;
        }
      }
    } catch (error) {
      showError(error);
      return;
    }
    const token = {};
    request = token;
    state = 'saving';
    setFieldsDisabled(true);
    root.querySelector('[data-correction-status]').innerHTML = loadingPanel('Saving correction…');
    let saved;
    try {
      saved = await api.request(
        `/api/v1/management/clients/${encodeURIComponent(clientId)}/cif/${successor ? 'review-cycles' : 'draft-information'}`,
        {
          method: successor ? 'POST' : 'PATCH',
          body: {
            cif_version_id: original.cif_version_id,
            expected_information: { ...expectedInformation },
            corrected_information: edited.information,
            reason: edited.reason,
          },
        },
      );
      if (!current(token)) return;
      if (!validReview(saved, clientId, successor ? null : original)
        || (successor && (saved.cif_version_id === original.cif_version_id || saved.version_number <= original.version_number))) {
        throw new Error('The save response could not be verified.');
      }
    } catch (error) {
      if (!current(token)) return;
      if ([401, 403].includes(error?.status)) {
        denyAccess(error);
        return;
      }
      const canRetry = [400, 422].includes(error?.status);
      state = canRetry ? 'editing' : 'blocked';
      setFieldsDisabled(!canRetry);
      showError(error, !canRetry);
      return;
    }
    clearSnapshot();
    start();
    onSaved?.(saved);
  }

  mounts.set(root, dispose);
  if (signal?.aborted) {
    dispose();
    return dispose;
  }
  signal?.addEventListener('abort', dispose, { once: true });
  if (!sessionHasRole(session, 'employee', 'management')
    || !hasPermission(session, 'client_onboarding.requirement.review')) {
    replaceContent(emptyState('Office access and onboarding review permission are required.'));
  } else if (typeof clientId !== 'string' || !UUID.test(clientId)) {
    replaceContent(emptyState('A valid Client selection is required.'));
  } else start();
  return dispose;
}
