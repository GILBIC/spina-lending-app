import { asArray, escapeHtml, setButtonBusy, showToast } from './ui.js';
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
  let retryKey = null;
  return {
    async start(selections) {
      const normalizedSelections = normalizeSelections(selections).map((item) => ({
        loanId: item.loan_id,
        amount: item.amount,
      }));
      retryKey ||= keyFactory();
      const body = buildClientGcashIntentRequest({
        idempotencyKey: retryKey,
        selections: normalizedSelections,
      });
      const intent = await api.request('/api/v1/client/gcash/payment-intents', {
        method: 'POST',
        body,
      });
      retryKey = null;
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
    <div class="inline-actions">
      ${checkoutUrl ? `<a class="button button-primary" href="${escapeHtml(checkoutUrl)}" target="_blank" rel="noopener noreferrer">Open GCash checkout</a>` : ''}
      ${intent.intent_id ? `<button class="button button-secondary" type="button" data-gcash-refresh-intent="${escapeHtml(intent.intent_id)}">Refresh status</button>` : ''}
    </div>
    <p class="meta">${intent.official_payment_posted === true ? 'Official SPINA payment posted.' : 'Provider status is not yet an official SPINA payment.'}</p>
  </div>`;
}

export function renderClientGcashPanel({ capability = {}, loans = [], intent = null } = {}) {
  const activeLoans = asArray(loans).filter(
    (loan) => String(loan?.status ?? loan?.loan_status ?? '').trim().toLowerCase() === 'active',
  );
  const message = escapeHtml(
    capability.message ||
      capability.official_payment_rule ||
      'Ask your collector or office for the approved payment instructions.',
  );
  if (capability.payment_available !== true) {
    return `<div data-client-gcash-panel class="notice-card warning"><strong>GCash checkout not connected</strong><br>${message}</div>`;
  }
  if (!activeLoans.length) {
    return `<div data-client-gcash-panel class="notice-card"><strong>GCash checkout available</strong><br>No active loan is available for payment.</div>`;
  }

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
  const { root, api } = context;
  const form = root.querySelector('#client-gcash-form');
  const statusPanel = root.querySelector('[data-client-gcash-status]');
  if (!form || !statusPanel) return;

  const actions = createClientGcashActions({ api });

  const bindIntentControls = () => {
    const refreshButton = statusPanel.querySelector('[data-gcash-refresh-intent]');
    refreshButton?.addEventListener('click', async () => {
      const intentId = String(refreshButton.dataset.gcashRefreshIntent || '').trim();
      if (!intentId) return;
      setButtonBusy(refreshButton, true, 'Refreshing…');
      try {
        const intent = await actions.refresh(intentId);
        statusPanel.innerHTML = renderClientGcashIntent(intent);
        bindIntentControls();
      } catch (error) {
        showToast(error?.message || 'GCash status could not be refreshed.', 'error');
        setButtonBusy(refreshButton, false);
      }
    });
  };

  form.addEventListener('submit', async (event) => {
    event.preventDefault();
    const button = form.querySelector('button[type="submit"]');
    setButtonBusy(button, true, 'Preparing GCash…');
    try {
      const intent = await actions.start(readSelections(form));
      statusPanel.innerHTML = renderClientGcashIntent(intent);
      bindIntentControls();
      showToast('GCash checkout prepared. Complete it with the provider, then refresh status.', 'success');
    } catch (error) {
      showToast(error?.message || 'GCash checkout could not be started.', 'error');
    } finally {
      setButtonBusy(button, false);
    }
  });
}
