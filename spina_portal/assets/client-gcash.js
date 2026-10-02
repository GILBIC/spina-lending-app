import { asArray, clearButtonBusyFocus, escapeHtml, setButtonBusy, showToast } from './ui.js';
import { classifyLoanType } from './collector-contract.js';
import { formatAuthoritativeMoney } from './client-schedule.js';

const MONEY_PATTERN = /^\d+(?:\.\d{1,2})?$/;

function normalizeSelections(selections) {
  const normalized = [];
  for (const selection of asArray(selections)) {
    const loanId = String(selection?.loanId ?? '').trim();
    if (!loanId) {
      throw new TypeError('Choose a loan before continuing to GCash.');
    }
    const rawAmount = String(selection?.amount ?? '').trim().replaceAll(',', '');
    if (!MONEY_PATTERN.test(rawAmount)) {
      throw new TypeError('GCash amount must be a valid peso amount.');
    }
    const [rawWhole, rawFraction = ''] = rawAmount.split('.');
    const whole = rawWhole.replace(/^0+(?=\d)/, '') || '0';
    const fraction = rawFraction.padEnd(2, '0');
    if (!/[1-9]/.test(`${whole}${fraction}`)) {
      throw new TypeError('GCash amount must be above zero.');
    }
    normalized.push({ loan_id: loanId, amount: `${whole}.${fraction}` });
  }
  if (!normalized.length) {
    throw new TypeError('Select at least one active loan before continuing to GCash.');
  }
  return normalized;
}

function defaultIdempotencyKey() {
  const randomUuid = globalThis.crypto?.randomUUID?.();
  if (!randomUuid) {
    throw new Error('Secure browser randomness is required before starting GCash checkout.');
  }
  return `web-${Date.now()}-${randomUuid}`;
}

function safeCheckoutUrl(value) {
  const raw = String(value ?? '').trim();
  if (!raw) return null;
  try {
    const url = new URL(raw);
    if (url.protocol !== 'https:' && url.protocol !== 'http:') return null;
    return url.href;
  } catch {
    return null;
  }
}

export function buildClientGcashIntentRequest({ idempotencyKey, selections }) {
  const key = String(idempotencyKey ?? '').trim();
  if (key.length < 8) {
    throw new TypeError('GCash retry key is invalid.');
  }
  return {
    idempotency_key: key,
    allocations: normalizeSelections(selections),
  };
}

export function createClientGcashActions({ api, keyFactory = defaultIdempotencyKey }) {
  let retryKey = null;let retryBody=null;
  return {
    async start(selections) {
      const normalizedSelections = normalizeSelections(selections).map((item) => ({
        loanId: item.loan_id,
        amount: item.amount,
      }));
      retryKey ||= keyFactory();
      const body = retryBody ||= buildClientGcashIntentRequest({
        idempotencyKey: retryKey,
        selections: normalizedSelections,
      });
      const intent = await api.request('/api/v1/client/gcash/payment-intents', {
        method: 'POST',
        body,
      });
      retryKey = null;retryBody=null;
      return intent;
    },
    async refresh(intentId) {
      const normalizedIntentId = String(intentId ?? '').trim();
      if (!normalizedIntentId) {
        throw new TypeError('GCash payment intent is required.');
      }
      return api.request(
        `/api/v1/client/gcash/payment-intents/${encodeURIComponent(normalizedIntentId)}`,
      );
    },
  };
}

function renderLoanGroup(label, loans) {
  if (!loans.length) return '';
  return `<div class="list-stack">
    <h3>${escapeHtml(label)}</h3>
    ${loans
      .map(
        (loan) => `<label class="list-item" data-gcash-loan-row>
          <span><input type="checkbox" data-gcash-select value="${escapeHtml(loan.loan_id)}" /> <strong>${escapeHtml(loan.loan_number || 'Loan')}</strong></span>
          <span class="meta">Official balance ${formatAuthoritativeMoney(loan.remaining_balance)}</span>
          <input data-gcash-amount inputmode="decimal" autocomplete="off" value="" placeholder="Amount" aria-label="GCash amount for ${escapeHtml(loan.loan_number || 'loan')}" />
        </label>`,
      )
      .join('')}
  </div>`;
}

export function renderClientGcashIntent(intent = {}) {
  const checkoutUrl = safeCheckoutUrl(intent.checkout_url);
  const paymentCode = typeof intent.qr_value === 'string' && intent.qr_value.trim() ? intent.qr_value : '';
  return `<div class="notice-card" data-client-gcash-intent>
    <div class="section-heading">
      <div><strong>GCash payment status</strong><div class="meta">Intent ${escapeHtml(intent.intent_id || '—')}</div></div>
      <span class="badge info">${escapeHtml(intent.status || 'unknown')}</span>
    </div>
    <div class="kv-list">
      <div class="kv-row"><span>Amount</span><strong>${formatAuthoritativeMoney(intent.amount)}</strong></div>
      <div class="kv-row"><span>Provider</span><strong>${escapeHtml(intent.provider || '—')}</strong></div>
      <div class="kv-row"><span>Mode</span><strong>${escapeHtml(intent.mode || '—')}</strong></div>
    </div>
    ${paymentCode ? `<label>GCash QR/payment code<textarea data-gcash-payment-code readonly rows="3">${escapeHtml(paymentCode)}</textarea></label>
      <button class="button button-secondary" type="button" data-gcash-copy-code>Copy payment code</button>
      <p class="meta" data-gcash-copy-status role="status">Use this provider code according to its payment instructions.</p>` : ''}
    <div class="inline-actions">
      ${checkoutUrl ? `<a class="button button-primary" href="${escapeHtml(checkoutUrl)}" target="_blank" rel="noopener noreferrer">Open GCash checkout</a>` : ''}
      ${intent.intent_id ? `<button class="button button-secondary" type="button" data-gcash-refresh-intent="${escapeHtml(intent.intent_id)}">Refresh status</button>` : ''}
    </div>
    <p class="meta">${intent.official_payment_posted === true ? 'Official SPINA payment posted.' : 'Provider status is not yet an official SPINA payment.'}</p>
  </div>`;
}

export function validClientGcashCapability(value) {
  return value !== null && typeof value === 'object' && !Array.isArray(value) && typeof value.payment_available === 'boolean';
}

function paymentOptionsState({ capability, loans, loansState, capabilityState }) {
  if (capabilityState && capabilityState.status !== 'ready') return { available: false, message: capabilityState.status === 'loading' ? 'Loading payment configuration…' : 'Payment configuration unavailable. Retry payment options.', retry: capabilityState.status === 'loading' ? null : 'gcash' };
  if (!validClientGcashCapability(capability)) return { available: false, message: 'Payment configuration unavailable. Retry payment options.', retry: 'gcash' };
  if (!capability.payment_available) return { available: false, message: `GCash checkout not connected. ${capability.message || capability.official_payment_rule || 'Ask your collector or office for the approved payment instructions.'}` };
  if (loansState && loansState.status !== 'ready') return { available: false, message: loansState.status === 'loading' ? 'Loading loan records before checkout…' : 'Loan records unavailable. Retry before selecting a loan for checkout.', retry: loansState.status === 'loading' ? null : 'loans' };
  const activeLoans = asArray(loans).filter(
    (loan) => String(loan?.status ?? loan?.loan_status ?? '').trim().toLowerCase() === 'active',
  );
  return { available: activeLoans.length > 0, activeLoans, message: activeLoans.length ? '' : 'GCash checkout available. No active loan is available for payment.' };
}

function paymentOptionsNotice(state) {
  return state.message ? `<div class="notice-card ${state.available ? '' : 'warning'}" role="status">${escapeHtml(state.message)}${state.retry ? `<button class="button button-secondary" type="button" data-gcash-read-retry="${state.retry}">Retry ${state.retry === 'loans' ? 'loan records' : 'payment options'}</button>` : ''}</div>` : '';
}

export function renderClientGcashPanel({ capability = {}, loans = [], loansState, capabilityState, intent = null } = {}) {
  const state = paymentOptionsState({ capability, loans, loansState, capabilityState });
  if (!state.available) return `<div data-client-gcash-panel><div data-client-gcash-read-state>${paymentOptionsNotice(state)}</div></div>`;
  const { activeLoans } = state;
  const message = escapeHtml(
    capability.message ||
      capability.official_payment_rule ||
      'Ask your collector or office for the approved payment instructions.',
  );
  const regularLoans = activeLoans.filter(
    (loan) => classifyLoanType(loan.loan_type_name ?? loan.loan_type_code) === 'regular',
  );
  const sevenBySevenLoans = activeLoans.filter(
    (loan) => classifyLoanType(loan.loan_type_name ?? loan.loan_type_code) === 'seven-by-seven',
  );
  const otherLoans = activeLoans.filter((loan) => {
    const type = classifyLoanType(loan.loan_type_name ?? loan.loan_type_code);
    return type !== 'regular' && type !== 'seven-by-seven';
  });

  return `<div data-client-gcash-panel>
    <div class="notice-card"><strong>Pay with GCash</strong><br>${message}</div>
    <div data-client-gcash-read-state></div>
    <form id="client-gcash-form" class="entry-form">
      ${renderLoanGroup('Regular', regularLoans)}
      ${renderLoanGroup('7x7', sevenBySevenLoans)}
      ${renderLoanGroup('Other active loans', otherLoans)}
      <button class="button button-primary" type="submit">Continue to GCash</button>
    </form>
    <p class="meta">${escapeHtml(capability.official_payment_rule || 'Opening or completing provider checkout does not itself create an official SPINA payment.')}</p>
    <div data-client-gcash-status>${intent ? renderClientGcashIntent(intent) : ''}</div>
  </div>`;
}

function readSelections(form) {
  const selections = [];
  for (const row of form.querySelectorAll('[data-gcash-loan-row]')) {
    const checkbox = row.querySelector('[data-gcash-select]');
    const amount = row.querySelector('[data-gcash-amount]');
    if (checkbox?.checked) {
      selections.push({ loanId: checkbox.value, amount: amount?.value ?? '' });
    }
  }
  return selections;
}

export function bindClientGcashPanel(context) {
  const { root, api, signal } = context;
  let disposed = false, saving = false;
  const removers = [], retryRemovers = [];
  const current = () => !disposed && !signal?.aborted && (context.clientIsCurrent?.() ?? true);
  const form = root.querySelector('#client-gcash-form');
  const statusPanel = root.querySelector('[data-client-gcash-status]');
  const button = form?.querySelector('button[type="submit"]');
  const listen = (element, type, handler, list = removers) => {
    if (!element) return;
    element.addEventListener(type, handler);
    list.push(() => element.removeEventListener(type, handler));
  };
  function updateReadState() {
    if (!current()) return;
    for (const remove of retryRemovers.splice(0)) remove();
    if (context.clientReads) {
      const loansState = context.clientReads.state('loans'), capabilityState = context.clientReads.state('gcash');
      const state = paymentOptionsState({ loansState, capabilityState, loans: loansState.data?.loans, capability: capabilityState.data });
      if (state.available && form && !readSelections(form).every(selection => state.activeLoans.some(loan => loan.loan_id === selection.loanId))) {
        state.available = false;
        state.message = 'Your selected loan is no longer available for checkout. Your draft is retained; review current loans before continuing.';
      }
      const notice = root.querySelector('[data-client-gcash-read-state]');
      if (notice) notice.innerHTML = paymentOptionsNotice(state);
      if (button) button.disabled = saving || !state.available;
    }
    for (const retry of root.querySelectorAll('[data-gcash-read-retry]')) listen(retry, 'click', () => {
      if (current()) void context.clientLoad?.(retry.getAttribute('data-gcash-read-retry'), { refresh: true });
    }, retryRemovers);
  }
  function dispose() {
    if (disposed) return;
    disposed = true;
    for (const remove of [...removers, ...retryRemovers]) remove();
    signal?.removeEventListener('abort', dispose);
    clearButtonBusyFocus(button);
    for (const input of form?.querySelectorAll('input') || []) { input.value = ''; input.checked = false; input.disabled = true; }
    if (button) button.disabled = true;
    if (statusPanel) { const code = statusPanel.querySelector('[data-gcash-payment-code]'); if (code) code.value = ''; statusPanel.innerHTML = ''; }
  }
  function denied(error) {
    if (![401, 403].includes(error?.status)) return false;
    context.clientCleanup?.();
    dispose();
    return true;
  }
  signal?.addEventListener('abort', dispose, { once: true });
  const handle = { updateReadState, dispose };
  if (signal?.aborted) { dispose(); return handle; }
  updateReadState();
  if (!form || !statusPanel) return handle;

  const actions = createClientGcashActions({ api: { request: (path, options = {}) => api.request(path, { ...options, signal }) } });

  const bindIntentControls = (intent = null) => {
    const codeField = statusPanel.querySelector('[data-gcash-payment-code]');
    if (codeField && typeof intent?.qr_value === 'string') codeField.value = intent.qr_value;
    const copyStatus = statusPanel.querySelector('[data-gcash-copy-status]');
    listen(statusPanel.querySelector('[data-gcash-copy-code]'), 'click', async () => {
      if (!current() || !codeField?.value) return;
      try {
        await globalThis.navigator.clipboard.writeText(codeField.value);
        if (current()) copyStatus.textContent = 'Payment code copied. Follow the provider’s payment instructions.';
      } catch {
        if (!current()) return;
        codeField.focus();
        codeField.select?.();
        copyStatus.textContent = 'Select and copy the payment code above.';
      }
    });
    const refreshButton = statusPanel.querySelector('[data-gcash-refresh-intent]');
    listen(refreshButton, 'click', async () => {
      const intentId = String(refreshButton.getAttribute('data-gcash-refresh-intent') || '').trim();
      if (!intentId||refreshButton.disabled||!current()) return;
      setButtonBusy(refreshButton, true, 'Refreshing…');
      try {
        const intent = await actions.refresh(intentId);
        if(!current())return;statusPanel.innerHTML = renderClientGcashIntent(intent);
        bindIntentControls(intent);
      } catch (error) {
        if (!current()) return;
        if (denied(error)) return;
        showToast(error?.message || 'GCash status could not be refreshed.', 'error');
        setButtonBusy(refreshButton, false);
      }
    });
  };

  listen(form, 'submit', async (event) => {
    event.preventDefault();
    if(!current()||saving||button.disabled)return;const loansState=context.clientReads?.state('loans');const capabilityState=context.clientReads?.state('gcash');if(loansState&&(loansState.status!=='ready'||capabilityState?.status!=='ready'||!validClientGcashCapability(capabilityState.data)||capabilityState.data.payment_available!==true)){showToast('Refresh loan records and payment options before checkout.','error');return;}
    if(loansState&&!readSelections(form).every(selection=>asArray(loansState.data?.loans).some(loan=>loan.loan_id===selection.loanId&&String(loan.status||loan.loan_status).toLowerCase()==='active'))){showToast('This loan selection has changed. Review current loans before checkout.','error');return;}
    saving = true;setButtonBusy(button, true, 'Preparing GCash…');
    try {
      const intent = await actions.start(readSelections(form));
      if (!current()) return;
      statusPanel.innerHTML = renderClientGcashIntent(intent);
      bindIntentControls(intent);
      showToast('GCash checkout prepared. Complete it with the provider, then refresh status.', 'success');
    } catch (error) {
      if (!current()) return;
      if (denied(error)) return;
      showToast(error?.message || 'GCash checkout could not be started.', 'error');
    } finally {
      saving = false;
      if (current()) { setButtonBusy(button, false); updateReadState(); }
    }
  });
  bindIntentControls();
  return handle;
}
