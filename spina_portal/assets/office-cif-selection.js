import { mountOfficeCifReview, isReviewForClient } from './office-cif-review.js';
import { mountOfficeCifCorrection } from './office-cif-correction.js';
import { mountOfficeCifWorkflow } from './office-cif-workflow.js';
import { sessionHasRole } from './roles.js';
import { emptyState, errorCard, hasPermission, loadingPanel } from './ui.js';
import { createOfficeCaseContext } from './office-case-context.js';

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

export function mountOfficeCifSelection({ root, api, session, getSession = () => session, signal, officeCaseContext, registerHandle, onContextChange, confirmDiscard = message => globalThis.confirm?.(message) === true }) {
  mountedSelections.get(root)?.();
  root.innerHTML = '';

  let disposed = false;
  let currentRequest;
  let lookupRequest;
  let form;
  let input;
  let clearButton;
  let statusRoot;
  let reviewRoot;
  let correctionRoot;
  let correctionCleanup;
  let workflowRoot;
  let workflowCleanup;
  let selected = null;
  let selectedReview = null;
  let revision = 0;
  let beginning = false;
  let beginUncertain = false;
  let recoveryCleanup;
  const coordinator = officeCaseContext ?? createOfficeCaseContext({getSession, confirmDiscard});
  const ownsCoordinator = !officeCaseContext;
  const children = () => [correctionCleanup, workflowCleanup].filter(Boolean);
  const isDirty = () => children().some(child => child.isDirty?.());
  const isWritePending = () => beginning || children().some(child => child.isWritePending?.());
  const isUncertain = () => beginUncertain || children().some(child => child.isUncertain?.());
  function edited() { revision++; coordinator.invalidateCandidate(); }
  function searchEdited() { lookupRequest = {}; coordinator.invalidateCandidate(); recoveryCleanup?.(); recoveryCleanup=null; if (statusRoot) statusRoot.innerHTML = ''; }
  function contextFor(selection, review) {
    return {mode:'saved-case', intakeReference:selection.application_reference, clientId:selection.client_id,
      stageFacts:{cif:{intakeReference:selection.application_reference, clientId:selection.client_id,
        ...(review ? {...(review.cif_version_id ? {cifVersionId:review.cif_version_id} : {}),versionNumber:review.version_number,
          ...(typeof review.status === 'string' ? {status:review.status} : {})} : {})}}};
  }
  function denyAccess(error) {
    if (disposed || mountedSelections.get(root) !== dispose) return;
    coordinator.dispose(); dispose();
    root.innerHTML = `<div role="alert">${errorCard(error, 'Office access is no longer available.')}</div>`;
  }
  async function beforeCorrection() {
    if (disposed || isWritePending() || isUncertain()) return false;
    if (workflowCleanup?.isDirty?.()) {
      const generation = coordinator.getGeneration(), before = revision;
      const accepted = await confirmDiscard('You have unsaved changes. Keep editing or discard changes?');
      if (!accepted || disposed || generation !== coordinator.getGeneration() || revision !== before || isWritePending() || isUncertain()) return false;
    }
    return !disposed;
  }

  function clearReview() {
    workflowCleanup?.(); workflowCleanup = null;
    if (workflowRoot) workflowRoot.innerHTML = '';
    if (reviewRoot) {
      // The review panel owns its request token. A null selection invalidates
      // any pending summary before clearing its message and previous PII.
      void mountOfficeCifReview({ root: reviewRoot, api, session, clientId: null });
      reviewRoot.innerHTML = '';
    }
  }

  function invalidate() {
    currentRequest = {};
    lookupRequest = {};
    correctionCleanup?.();
    correctionCleanup = null;
    if (correctionRoot) correctionRoot.innerHTML = '';
    clearReview();
    if (statusRoot) statusRoot.innerHTML = '';
    selected = null;
    selectedReview = null;
    beginUncertain = false;
    recoveryCleanup?.(); recoveryCleanup=null;
  }

  function dispose() {
    if (disposed) return;
    disposed = true;
    invalidate();
    form?.removeEventListener('submit', openReview);
    input?.removeEventListener('input', searchEdited);
    input?.removeEventListener('change', searchEdited);
    clearButton?.removeEventListener('click', clearSelection);
    signal?.removeEventListener('abort', dispose);
    root.querySelector('[data-close-cif-case]')?.removeEventListener('click', closeCase);
    if (input) input.value = '';
    if (mountedSelections.get(root) === dispose) {
      mountedSelections.delete(root);
      root.innerHTML = '';
    }
    if (ownsCoordinator) coordinator.dispose();
  }

  function clearSelection() {
    if (disposed) return;
    searchEdited();
    input.value = '';
    input.focus();
  }

  async function closeCase(event) {
    const button = event?.currentTarget;
    if (disposed) return;
    const accepted = await coordinator.requestTransition({kind:'close',targetStage:'cif'});
    if (disposed) return;
    if (accepted) input.focus(); else button?.focus();
  }

  async function openReview(event) {
    event.preventDefault();
    if (disposed) return;
    if (isWritePending() || isUncertain()) { statusRoot.textContent = 'Keep the current operation and reconcile it before changing case.'; return; }
    const request = {}; lookupRequest = request;
    const reference = input.value.trim();
    if (!reference) {
      statusRoot.innerHTML = `<div role="alert">${errorCard(new Error('Enter the office intake reference.'))}</div>`;
      input.focus();
      return;
    }
    statusRoot.innerHTML = loadingPanel('Finding office intake…');
    try {
      let selection, initialReview, initialError;
      const accepted = await coordinator.requestTransition({kind:'open',targetStage:'cif',candidate:async () => {
        try {
          selection = await api.request(`/api/v1/management/onboarding/applicants/by-reference/${encodeURIComponent(reference)}/cif-client`, {signal});
        } catch (error) {
          if ([401,403].includes(error?.status)) denyAccess(error);
          throw error;
        }
        if (disposed || lookupRequest !== request) return null;
        if (!matchesReference(selection, reference)) throw new Error('The office intake response is invalid or does not match the entered reference.');
        try {
          initialReview = await api.request(`/api/v1/management/clients/${encodeURIComponent(selection.client_id)}/cif/review-summary`, {signal});
          if (!isReviewForClient(initialReview, selection.client_id)) throw new Error('The CIF review response is invalid or does not match the selected Client.');
        } catch (error) {
          if ([401,403].includes(error?.status)) { denyAccess(error); throw error; }
          // The first selection may offer a draft when no CIF exists yet. An
          // unavailable replacement must never erase already authorized work.
          if (!selected && [404,409].includes(error?.status)) initialError = error;
          else throw error;
        }
        return contextFor(selection, initialReview);
      }});
      if (!accepted || disposed) {
        if (!disposed && lookupRequest === request) { statusRoot.textContent = 'Your existing work has been kept.'; form.querySelector('button[type="submit"]').focus(); }
        return false;
      }
      currentRequest = request; selected = selection;
      selectedReview = initialReview ?? null;
      let establishedCif = Boolean(initialReview);
      let correctionActive = false;
      input.value = selection.application_reference;
      onContextChange?.(coordinator.getContext());
      statusRoot.innerHTML = '';
      const savedRecovery = (description, reload) => {
        recoveryCleanup?.();
        statusRoot.innerHTML = `<p>${description} saved. Current CIF details are unavailable. Reload reads the saved record.</p><button type="button" data-reload-saved-cif>Reload saved CIF</button>`;
        const button = statusRoot.querySelector('[data-reload-saved-cif]');
        const read = async () => {
          if (disposed || currentRequest !== request || isDirty() || isWritePending() || isUncertain()) return;
          button.disabled=true;
          const value = await reload();
          if (disposed || currentRequest !== request) return;
          if (value) { recoveryCleanup?.(); recoveryCleanup=null; statusRoot.textContent=`${description} saved.`; }
          else savedRecovery(description,reload);
        };
        button.addEventListener('click',read);
        recoveryCleanup=()=>button.removeEventListener('click',read);
      };
      const offerFirstDraft = (error) => {
        if (disposed || currentRequest !== request || establishedCif || ![404, 409].includes(error?.status)) return;
        workflowRoot.innerHTML = '<p>No eligible current CIF is available. Start the first draft from this promoted Client when intake is eligible.</p><button type="button" data-begin-cif>Begin CIF draft</button><div data-begin-cif-status role="status"></div>';
        const button = workflowRoot.querySelector('[data-begin-cif]');
        const begin = async () => {
          if (isWritePending() || beginUncertain || establishedCif || disposed || currentRequest !== request) return;
          beginning = true; button.disabled = true;
          try {
            const result = await api.request(`/api/v1/management/clients/${encodeURIComponent(selection.client_id)}/cif/draft`, { method: 'POST', signal });
            if (disposed || currentRequest !== request) return;
            if (result?.client_id !== selection.client_id || !Number.isSafeInteger(result.version_number) || result.version_number < 1) {
              throw new Error('The draft response could not be verified. Reload this intake before continuing.');
            }
            // The acknowledged creation survives an unavailable subsequent read.
            // Only reads may reconcile it; a missing summary is not permission
            // to start a second creation operation.
            establishedCif = true;
            selectedReview = {version_number:result.version_number};
            coordinator.acceptVerifiedContext(contextFor(selection,selectedReview),coordinator.getGeneration());
            const review = await openSelected();
            if (!review && !disposed && currentRequest === request) savedRecovery('CIF draft',openSelected);
          } catch (failure) {
            if (disposed || currentRequest !== request) return;
            if ([401, 403].includes(failure?.status)) {
              denyAccess(failure); return;
            }
            beginUncertain = ![400,404,409,422].includes(failure?.status);
            workflowRoot.querySelector('[data-begin-cif-status]').innerHTML = errorCard(failure);
          } finally { beginning = false; if (!disposed && currentRequest === request) button.disabled = beginUncertain; }
        };
        button.addEventListener('click', begin);
        workflowCleanup = () => { button.removeEventListener('click', begin); workflowRoot.innerHTML = ''; };
      };
      const refreshReview = async (first = false) => {
        if (disposed || currentRequest !== request) return;
        workflowCleanup?.(); workflowCleanup = null;
        const generation = coordinator.getGeneration();
        const value = await mountOfficeCifReview({ root: reviewRoot, api, session, clientId: selection.client_id, onUnavailable: offerFirstDraft,
          ...(first === true ? {initialReview,initialError} : {}), onAccessDenied:denyAccess });
        if (value && !disposed && currentRequest === request) {
          establishedCif = true;
          selectedReview = value;
          coordinator.acceptVerifiedContext(contextFor(selection,value),generation);
          workflowCleanup = mountOfficeCifWorkflow({ root: workflowRoot, api, session, clientId: selection.client_id, signal,
            onChanged: refreshReview, onAccessDenied: denyAccess, onDraftChange:edited });
        }
        return value;
      };
      const openSelected = async (first = false) => {
        const review = await refreshReview(first);
        if (!review || disposed || currentRequest !== request) return;
        correctionCleanup?.();
        correctionCleanup = mountOfficeCifCorrection({
        root: correctionRoot, api, session, clientId: selection.client_id, signal,
        allowSuccessor: true, includeIdentity: true,
        beforeEditing:beforeCorrection, getGeneration:()=>coordinator.getGeneration(), onDraftChange:edited,
        onEditing: () => { correctionActive=true; clearReview(); },
        onClosed: () => { if(correctionActive){correctionActive=false;return refreshReview();} },
        onSaved: async saved => {
          if (disposed || currentRequest !== request) return;
          correctionActive = false;
          selectedReview = saved;
          establishedCif = true;
          coordinator.acceptVerifiedContext(contextFor(selection,saved),coordinator.getGeneration());
          statusRoot.textContent='CIF correction saved.';
          const value=await refreshReview();
          if (!value && !disposed && currentRequest === request) savedRecovery('CIF correction',refreshReview);
        },
        onAccessDenied: () => {
          if (disposed || currentRequest !== request) return;
          denyAccess(new Error('Office access is no longer available. Sign in again before continuing.'));
        },
        });
        return review;
      };
      await openSelected(true);
      return true;
    } catch (error) {
      if ([401,403].includes(error?.status)) { denyAccess(error); return; }
      if (disposed || lookupRequest !== request) return false;
      statusRoot.innerHTML = `<div role="alert">${errorCard(error, 'Office intake is unavailable.')}</div>`;
      return false;
    }
  }

  mountedSelections.set(root, dispose);
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

  root.innerHTML = `<p class="meta">Enter the reference recorded during office intake.</p>
  <form class="entry-form">
    <label>Office intake reference
      <input name="applicationReference" type="text" autocomplete="off" required />
    </label>
    <div class="action-row">
      <button class="button button-primary" type="submit">Open CIF review</button>
      <button class="button button-outline" type="button" data-clear-cif-search>Clear search</button>
      <button class="button button-outline" type="button" data-close-cif-case>Close case</button>
    </div>
  </form>
  <div data-office-cif-status role="status" aria-live="polite"></div>
  <div data-office-cif-review aria-live="polite"></div>
  <div data-office-cif-correction aria-live="polite"></div>
  <div data-office-cif-workflow aria-live="polite"></div>`;

  form = root.querySelector('form');
  input = form.querySelector('input');
  clearButton = form.querySelector('button[type="button"]');
  statusRoot = root.querySelector('[data-office-cif-status]');
  reviewRoot = root.querySelector('[data-office-cif-review]');
  correctionRoot = root.querySelector('[data-office-cif-correction]');
  workflowRoot = root.querySelector('[data-office-cif-workflow]');
  form.addEventListener('submit', openReview);
  input.addEventListener('input', searchEdited);
  input.addEventListener('change', searchEdited);
  clearButton.addEventListener('click', clearSelection);
  root.querySelector('[data-close-cif-case]').addEventListener('click', closeCase);
  const handle = {getContext:()=>!disposed && selected ? contextFor(selected,selectedReview) : null, isDirty, getRevision:()=>revision, isWritePending, isUncertain,
    openCase:reference => { if(disposed)return false;input.value=reference; return openReview({preventDefault(){}}); },
    resetCase:()=>{if(disposed || isWritePending() || isUncertain())return false; invalidate(); input.value=''; return true;},
    refreshReadOnly:()=>{if(isDirty() || isWritePending() || isUncertain() || !selected)return false; return handle.openCase(selected.application_reference);}, dispose};
  registerHandle?.(handle); if (ownsCoordinator) coordinator.registerStage('cif',handle);
  return dispose;
}
