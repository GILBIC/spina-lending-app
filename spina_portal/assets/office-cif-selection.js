import { mountOfficeCifReview } from './office-cif-review.js';
import { normalizeRole } from './roles.js';
import { emptyState, errorCard, hasPermission, loadingPanel } from './ui.js';

const mountedSelections = new WeakMap();
const UUID_PATTERN = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

function matchesReference(selection, reference) {
  return selection !== null
    && typeof selection === 'object'
    && !Array.isArray(selection)
    && typeof selection.application_reference === 'string'
    && selection.application_reference.trim().toLowerCase() === reference.toLowerCase()
    && typeof selection.client_id === 'string'
    && UUID_PATTERN.test(selection.client_id);
}

export function mountOfficeCifSelection({ root, api, session, signal }) {
  mountedSelections.get(root)?.();
  root.innerHTML = '';

  let disposed = false;
  let currentRequest;
  let form;
  let input;
  let clearButton;
  let statusRoot;
  let reviewRoot;

  function invalidate() {
    currentRequest = {};
    if (reviewRoot) {
      // The review panel owns its request token. A null selection invalidates
      // any pending summary before clearing its message and previous PII.
      void mountOfficeCifReview({ root: reviewRoot, api, session, clientId: null });
      reviewRoot.innerHTML = '';
    }
    if (statusRoot) statusRoot.innerHTML = '';
  }

  function dispose() {
    if (disposed) return;
    disposed = true;
    invalidate();
    form?.removeEventListener('submit', openReview);
    input?.removeEventListener('input', invalidate);
    input?.removeEventListener('change', invalidate);
    clearButton?.removeEventListener('click', clearSelection);
    signal?.removeEventListener('abort', dispose);
    if (input) input.value = '';
    if (mountedSelections.get(root) === dispose) {
      mountedSelections.delete(root);
      root.innerHTML = '';
    }
  }

  function clearSelection() {
    if (disposed) return;
    invalidate();
    input.value = '';
    input.focus();
  }

  async function openReview(event) {
    event.preventDefault();
    if (disposed) return;
    invalidate();
    const request = currentRequest;
    const reference = input.value.trim();
    if (!reference) {
      statusRoot.innerHTML = `<div role="alert">${errorCard(new Error('Enter the office intake reference.'))}</div>`;
      input.focus();
      return;
    }
    statusRoot.innerHTML = loadingPanel('Finding office intake…');
    try {
      const selection = await api.request(
        `/api/v1/management/onboarding/applicants/by-reference/${encodeURIComponent(reference)}/cif-client`,
      );
      if (disposed || currentRequest !== request) return;
      if (!matchesReference(selection, reference)) {
        throw new Error('The office intake response is invalid or does not match the entered reference.');
      }
      statusRoot.innerHTML = '';
      await mountOfficeCifReview({ root: reviewRoot, api, session, clientId: selection.client_id });
    } catch (error) {
      if (disposed || currentRequest !== request) return;
      statusRoot.innerHTML = `<div role="alert">${errorCard(error, 'Office intake is unavailable.')}</div>`;
    }
  }

  mountedSelections.set(root, dispose);
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

  root.innerHTML = `<p class="meta">Enter the reference recorded during office intake.</p>
  <form class="entry-form">
    <label>Office intake reference
      <input name="applicationReference" type="text" autocomplete="off" required />
    </label>
    <div class="action-row">
      <button class="button button-primary" type="submit">Open CIF review</button>
      <button class="button button-outline" type="button">Clear</button>
    </div>
  </form>
  <div data-office-cif-status role="status" aria-live="polite"></div>
  <div data-office-cif-review aria-live="polite"></div>`;

  form = root.querySelector('form');
  input = form.querySelector('input');
  clearButton = form.querySelector('button[type="button"]');
  statusRoot = root.querySelector('[data-office-cif-status]');
  reviewRoot = root.querySelector('[data-office-cif-review]');
  form.addEventListener('submit', openReview);
  input.addEventListener('input', invalidate);
  input.addEventListener('change', invalidate);
  clearButton.addEventListener('click', clearSelection);
  return dispose;
}
