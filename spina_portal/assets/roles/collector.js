import { buildCollectionSubmission, classifyLoanType } from '../collector-contract.js';
import { buildCollectorRouteViewModel } from '../presenters.js';
import {
  asArray,
  badge,
  emptyState,
  errorCard,
  escapeHtml,
  formatDate,
  formatDateTime,
  formatMoney,
  hasPermission,
  loadingPanel,
  metricCard,
  settledRequest,
  setButtonBusy,
  showToast,
} from '../ui.js';

function numeric(value) {
  const amount = Number(String(value ?? '0').replaceAll(',', ''));
  return Number.isFinite(amount) ? amount : 0;
}

function withAttention(route) {
  return {
    ...route,
    entries: asArray(route.entries).map((entry) => {
      const remainingToday = numeric(entry.contract_today_unpaid_amount);
      const attentionRequired =
        entry.processed_today === true &&
        entry.today_entry_type === 'payment' &&
        remainingToday > 0;
      return {
        ...entry,
        attention_required: entry.attention_required === true || attentionRequired,
        attention_reason:
          entry.attention_reason ||
          (attentionRequired ? `Short ${formatMoney(remainingToday)}` : ''),
      };
    }),
  };
}

function entryStatus(entry) {
  if (entry.attention_required) return badge(entry.attention_reason || 'attention', 'warning');
  if (entry.processed_today) return badge(entry.today_entry_type || 'collected', 'success');
  if (entry.contract_today_already_covered) return badge('ADV covered', 'success');
  return badge(entry.status || 'not collected', 'warning');
}

function entryForm(entry, defaultAmount) {
  return `<form class="entry-form collector-entry-form" data-route-entry-id="${escapeHtml(entry.route_entry_id)}" hidden style="grid-column:1/-1">
    <input type="hidden" name="entryType" value="payment" />
    <label class="payment-only">Amount<input name="amount" inputmode="decimal" value="${escapeHtml(defaultAmount)}" required /></label>
    <label class="pass-only" hidden>Past Due reason<select name="reasonCode"><option value="no_cash">No cash</option><option value="client_absent">Client absent</option><option value="business_slow">Business slow</option><option value="sick_hospital">Sick / hospital</option><option value="emergency">Emergency</option><option value="other">Other</option></select></label>
    <label>Note<textarea name="note" maxlength="500" placeholder="Short factual note"></textarea></label>
    <div class="action-row"><button class="button button-primary" type="submit">Save official entry</button><button class="button button-quiet cancel-entry" type="button">Cancel</button></div>
  </form>`;
}

function ledgerRow(entry, canCreate, online) {
  const type = classifyLoanType(entry.loan_type);
  const canEnter = canCreate && online && entry.can_enter_payment === true && entry.processed_today !== true;
  const defaultAmount =
    numeric(entry.contract_today_unpaid_amount) > 0
      ? Number(entry.contract_today_unpaid_amount).toFixed(2)
      : numeric(entry.daily_amount) > 0
        ? Number(entry.daily_amount).toFixed(2)
        : '';
  return `<div class="ledger-row ${entry.attention_required || !entry.processed_today ? 'needs-attention' : ''}" data-entry-row="${escapeHtml(entry.route_entry_id)}">
    <div class="ledger-cell"><strong class="ledger-client">${escapeHtml(entry.client_name || 'Client')}</strong><small>${escapeHtml(entry.note || entry.today_note || entry.collection_message || '')}</small></div>
    <div class="ledger-cell"><span class="badge ${type === 'seven-by-seven' ? 'info' : 'warning'}">${type === 'seven-by-seven' ? '7x7' : escapeHtml(entry.loan_type || 'Regular')}</span><small>${escapeHtml(entry.contract_payment_frequency || '')}</small></div>
    <div class="ledger-cell"><small>Daily / today</small><strong>${formatMoney(entry.contract_today_unpaid_amount || entry.daily_amount)}</strong><small>Balance ${formatMoney(entry.remaining_balance)}</small></div>
    <div class="ledger-cell">${entryStatus(entry)}${entry.pass_count ? `<small>Missed / PASS ${escapeHtml(entry.pass_count)}</small>` : ''}${entry.advance_until ? `<small>ADV to ${formatDate(entry.advance_until)}</small>` : ''}</div>
    <div class="ledger-actions action-row">
      ${canEnter ? `<button class="button button-primary button-small collection-action" type="button" data-entry-action="payment" data-entry-id="${escapeHtml(entry.route_entry_id)}">Payment</button><button class="button button-outline button-small collection-action" type="button" data-entry-action="pass" data-entry-id="${escapeHtml(entry.route_entry_id)}">Unable to pay</button>` : `<span class="meta">${online ? (entry.processed_today ? 'Recorded today' : escapeHtml(entry.contract_readiness_message || 'Entry unavailable')) : 'Offline — read only'}</span>`}
    </div>
    ${canEnter ? entryForm(entry, defaultAmount) : ''}
  </div>`;
}

function routeMarkup(model, canCreate, online) {
  if (!model.totalCount) return emptyState('No assigned route entry is available for today.');
  return model.areaGroups
    .map(
      (group) => `<section class="ledger-area">
        <header class="ledger-area-header"><strong>${escapeHtml(group.name)}</strong><span>${escapeHtml(group.processedCount)} / ${escapeHtml(group.totalCount)} processed · ${escapeHtml(group.unresolvedCount)} unresolved</span></header>
        <div class="ledger-list">${group.entries.map((entry) => ledgerRow(entry, canCreate, online)).join('')}</div>
      </section>`,
    )
    .join('');
}

function unresolvedMarkup(items) {
  if (!items.length) return `<div class="notice-card"><strong>Route review clear.</strong><br>Every current route row is processed with no detected short balance.</div>`;
  return `<div class="table-wrap"><table><thead><tr><th>Area</th><th>Client</th><th>Loan</th><th>Reason</th><th>Today</th></tr></thead><tbody>${items
    .map(
      (entry) => `<tr><td>${escapeHtml(entry.area || '—')}</td><td><strong>${escapeHtml(entry.client_name || 'Client')}</strong></td><td>${escapeHtml(entry.loan_type || '—')}</td><td>${escapeHtml(entry.attention_reason || (entry.processed_today ? 'Needs review' : 'Not collected'))}</td><td>${formatMoney(entry.contract_today_unpaid_amount || entry.daily_amount)}</td></tr>`,
    )
    .join('')}</tbody></table></div>`;
}

function remittanceHistory(items) {
  if (!items.length) return emptyState('No remittance history is available.');
  return `<div class="list-stack">${items
    .slice(0, 30)
    .map(
      (item) => `<article class="list-item"><div class="section-heading"><div><strong>${escapeHtml(item.remittance_number || 'Remittance')}</strong><div class="meta">${formatDate(item.collection_date)} · To ${escapeHtml(item.recipient_name || 'recipient')}</div></div>${badge(item.status)}</div><div class="detail-grid"><div class="detail-item"><span>Total</span><strong>${formatMoney(item.total_amount)}</strong></div><div class="detail-item"><span>Clients</span><strong>${escapeHtml(item.client_count ?? '—')}</strong></div><div class="detail-item"><span>Transactions</span><strong>${escapeHtml(item.transaction_count ?? '—')}</strong></div></div></article>`,
    )
    .join('')}</div>`;
}

function remittanceSection(routeDate, preview, recipients, history, errors, canCreate) {
  return `<section class="section-card" id="collector-remittance">
    <div class="section-heading"><div><h2>Remittance</h2><p>Submit only after reviewing the complete server-calculated collection summary.</p></div></div>
    ${errors.preview ? errorCard(errors.preview) : `<div class="metric-grid">${metricCard('Cash total', formatMoney(preview.total_amount || 0))}${metricCard('Transactions', escapeHtml(preview.transaction_count ?? 0))}${metricCard('Clients', escapeHtml(preview.client_count ?? 0))}${metricCard('Unable to pay', escapeHtml(preview.unable_to_pay_count ?? 0))}</div>`}
    ${canCreate && recipients.length ? `<form id="collector-remittance-form" class="entry-form"><label>Recipient<select name="recipientUserId" required>${recipients.map((recipient) => `<option value="${escapeHtml(recipient.user_id)}">${escapeHtml(recipient.full_name)} · ${escapeHtml(recipient.role_name)}</option>`).join('')}</select></label><label>Collection date<input name="collectionDate" type="date" value="${escapeHtml(routeDate || '')}" readonly /></label><label>Note<textarea name="note" maxlength="500"></textarea></label><button class="button button-primary" type="submit" ${numeric(preview.total_amount) <= 0 ? 'disabled' : ''}>Submit remittance</button></form>` : canCreate ? emptyState('No eligible remittance recipient is available.') : `<div class="notice-card warning">Your account can view remittance history but cannot create a remittance.</div>`}
    <div class="section-heading" style="margin-top:1rem"><div><h2>History</h2></div></div>
    ${errors.history ? errorCard(errors.history) : remittanceHistory(history)}
  </section>`;
}

function activityMarkup(items) {
  if (!items.length) return emptyState('No Collector update is available.');
  return `<div class="timeline">${items.slice(0, 30).map((item) => `<article class="timeline-item"><strong>${escapeHtml(item.title || item.notification_type || 'Update')}</strong><span>${escapeHtml(item.message || '')}</span><span class="meta">${formatDateTime(item.created_at)}</span></article>`).join('')}</div>`;
}

function lockFinancialEntry(root, message) {
  root.dataset.financialLocked = 'true';
  for (const control of root.querySelectorAll('.collection-action, .collector-entry-form input, .collector-entry-form select, .collector-entry-form textarea, .collector-entry-form button, #collector-remittance-form input, #collector-remittance-form select, #collector-remittance-form textarea, #collector-remittance-form button')) {
    control.disabled = true;
  }
  const existing = root.querySelector('#collector-uncertain-lock');
  if (!existing) {
    root.insertAdjacentHTML('afterbegin', `<div id="collector-uncertain-lock" class="notice-card danger"><strong>Financial entry locked for reconciliation.</strong><br>${escapeHtml(message)} Use Refresh to load authoritative SPINA state before any new attempt.</div>`);
  }
}

function bindRouteActions(context, entryMap) {
  for (const button of context.root.querySelectorAll('.collection-action')) {
    button.addEventListener('click', () => {
      const row = context.root.querySelector(`[data-entry-row="${CSS.escape(button.dataset.entryId)}"]`);
      const form = row?.querySelector('.collector-entry-form');
      if (!form) return;
      const isPass = button.dataset.entryAction === 'pass';
      form.hidden = false;
      form.elements.entryType.value = isPass ? 'pass' : 'payment';
      form.querySelector('.payment-only').hidden = isPass;
      form.querySelector('.pass-only').hidden = !isPass;
      form.elements.amount.required = !isPass;
      form.elements.reasonCode.required = isPass;
      form.scrollIntoView({ behavior: 'smooth', block: 'center' });
    });
  }
  for (const form of context.root.querySelectorAll('.collector-entry-form')) {
    form.querySelector('.cancel-entry')?.addEventListener('click', () => {
      form.reset();
      form.hidden = true;
    });
    form.addEventListener('submit', async (event) => {
      event.preventDefault();
      if (context.root.dataset.financialLocked === 'true') return;
      const entry = entryMap.get(form.dataset.routeEntryId);
      if (!entry) {
        showToast('The route entry is stale. Refresh the route.', 'error');
        return;
      }
      const data = new FormData(form);
      const entryType = String(data.get('entryType') || 'payment');
      const note = String(data.get('note') || '').trim();
      const clientTransactionId = globalThis.crypto.randomUUID();
      const submission = buildCollectionSubmission({
        entry,
        routeDate: context.routeDate,
        entryType,
        amount: data.get('amount'),
        note,
        pastDueFollowup: entryType === 'pass' ? {
          reason_code: data.get('reasonCode'),
          note,
          promised_payment_date: null,
          promised_amount: null,
        } : null,
        deviceId: context.sessionStore.deviceId(),
        deviceSequence: context.sessionStore.nextDeviceSequence(),
        clientTransactionId,
        recordedAt: new Date().toISOString(),
      });
      const submitButton = form.querySelector('button[type="submit"]');
      setButtonBusy(submitButton, true, 'Saving…');
      try {
        const result = await context.api.request('/api/v1/collector/collections', {
          method: 'POST',
          headers: submission.headers,
          body: submission.body,
          financial: true,
        });
        const receipt = result?.receipt_number ? ` Receipt ${result.receipt_number}.` : '';
        const balance = result?.official_balance != null ? ` Official balance ${formatMoney(result.official_balance)}.` : '';
        showToast(`${result?.message || 'Official entry saved.'}${receipt}${balance}`, 'success', 7600);
        await mountCollectorWorkspace(context);
      } catch (error) {
        if (error.code === 'network_uncertain') {
          context.uncertainCollection = submission;
          lockFinancialEntry(context.root, error.message);
        }
        showToast(error.message, 'error', 7600);
        setButtonBusy(submitButton, false);
      }
    });
  }
}

function bindRemittance(context) {
  const form = context.root.querySelector('#collector-remittance-form');
  form?.addEventListener('submit', async (event) => {
    event.preventDefault();
    if (context.root.dataset.financialLocked === 'true') return;
    const data = new FormData(form);
    const button = form.querySelector('button[type="submit"]');
    setButtonBusy(button, true, 'Submitting…');
    try {
      const result = await context.api.request('/api/v1/collector/remittances', {
        method: 'POST',
        financial: true,
        body: {
          recipient_user_id: data.get('recipientUserId'),
          collection_date: data.get('collectionDate'),
          note: String(data.get('note') || '').trim(),
        },
      });
      showToast(`Remittance ${result.remittance_number || ''} submitted for recipient review.`, 'success');
      await mountCollectorWorkspace(context);
    } catch (error) {
      if (error.code === 'network_uncertain') {
        lockFinancialEntry(context.root, error.message);
      }
      showToast(error.message, 'error');
      setButtonBusy(button, false);
    }
  });
}

export async function mountCollectorWorkspace(context) {
  const { root, api, session, setNavigation } = context;
  const online = globalThis.navigator?.onLine !== false;
  const canViewRoute = hasPermission(session, 'route.view');
  const canCreate = hasPermission(session, 'collection.create');
  const canCreateRemittance = hasPermission(session, 'remittance.create');
  const canViewRemittance = hasPermission(session, 'remittance.view') || canCreateRemittance;
  setNavigation([
    { id: 'collector-overview', label: "Today's route" },
    { id: 'collector-master-review', label: 'Master Review' },
    ...(canViewRemittance ? [{ id: 'collector-remittance', label: 'Remittance' }] : []),
    { id: 'collector-updates', label: 'Updates' },
  ]);
  root.innerHTML = loadingPanel('Loading the authoritative Collector route…');
  root.dataset.financialLocked = 'false';

  const [routeResult, account, activity, history] = await Promise.all([
    canViewRoute
      ? settledRequest(api, '/api/v1/collector/routes/today', {}, { route_date: null, areas: [], entries: [] })
      : Promise.resolve({ data: { route_date: null, areas: [], entries: [] }, error: new Error('Route permission is required.') }),
    settledRequest(api, '/api/v1/account', {}, {}),
    settledRequest(api, '/api/v1/activity-notifications', {}, []),
    canViewRemittance
      ? settledRequest(api, '/api/v1/remittances', {}, [])
      : Promise.resolve({ data: [], error: null }),
  ]);
  const route = withAttention(routeResult.data);
  context.routeDate = route.route_date;
  const [recipients, preview] = canCreateRemittance && route.route_date
    ? await Promise.all([
        settledRequest(api, '/api/v1/collector/remittances/recipients', {}, []),
        settledRequest(api, `/api/v1/collector/remittances/preview?collection_date=${encodeURIComponent(route.route_date)}`, {}, {}),
      ])
    : [{ data: [], error: null }, { data: {}, error: null }];
  const model = buildCollectorRouteViewModel(route);
  const entryMap = new Map(model.entries.map((entry) => [String(entry.route_entry_id), entry]));
  const profile = account.data?.profile ?? {};

  root.innerHTML = `<header class="workspace-header" id="collector-overview">
    <div><p class="eyebrow">Collector workspace</p><h1>${escapeHtml(model.collectorName || profile.full_name || 'Collector')}</h1><p>${formatDate(model.routeDate)} · Ledger-first assigned route. Official payments are accepted online by SPINA only.</p></div>
    ${online ? `<span class="status-chip online">Online collection enabled</span>` : `<span class="status-chip offline">Offline copy — read only</span>`}
  </header>
  ${!online ? `<div class="notice-card danger"><strong>No payment is accepted or queued while offline.</strong><br>Reconnect and refresh the route before collecting.</div>` : ''}
  <section class="metric-grid">
    ${metricCard('Expected today', formatMoney(model.expectedTotal))}
    ${metricCard('Route clients / loans', escapeHtml(model.totalCount))}
    ${metricCard('Processed', escapeHtml(model.processedCount))}
    ${metricCard('Needs action', escapeHtml(model.unresolved.length))}
  </section>
  <section class="section-card">
    <div class="section-heading"><div><h2>Assigned area ledger</h2><p>Regular and 7x7 rows stay separate under the same Client context.</p></div></div>
    ${routeResult.error ? errorCard(routeResult.error) : routeMarkup(model, canCreate, online)}
  </section>
  <section class="section-card" id="collector-master-review">
    <div class="section-heading"><div><h2>Master Review</h2><p>Every assigned-area row still requiring action before route completion.</p></div></div>
    ${unresolvedMarkup(model.unresolved)}
  </section>
  ${canViewRemittance ? remittanceSection(route.route_date, preview.data, recipients.data, history.data, { preview: preview.error, history: history.error }, canCreateRemittance) : ''}
  <section class="section-card" id="collector-updates"><div class="section-heading"><div><h2>Updates</h2><p>Activity and notices intended for this Collector account.</p></div></div>${activity.error ? errorCard(activity.error) : activityMarkup(activity.data)}</section>`;

  bindRouteActions(context, entryMap);
  bindRemittance(context);
}
