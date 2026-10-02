import {
  asArray,
  badge,
  emptyState,
  errorCard,
  escapeHtml,
  formatDateTime,
  hasPermission,
  setButtonBusy,
  clearButtonBusyFocus,
  showToast,
} from './ui.js';

function activityRows(items,limit=50) {
  if (!items.length) return emptyState('No Employee update is available.');
  return `<div class="timeline">${items
    .slice(0, limit)
    .map(
      (item) => `<article class="timeline-item">
        <strong>${escapeHtml(item.title || item.notification_type || 'SPINA update')}</strong>
        <span>${escapeHtml(item.message || '')}</span>
        <span class="meta">${escapeHtml(item.sender_name || '')}${item.created_at ? ` · ${formatDateTime(item.created_at)}` : ''}</span>
      </article>`,
    )
    .join('')}</div>`;
}

function supportQueue(items) {
  if (!items.length) return emptyState('No open Client support request is assigned to this queue.');
  return `<div class="list-stack">${items
    .map(
      (request) => `<article class="list-item">
        <div class="section-heading">
          <div>
            <strong>${escapeHtml(request.client_name || request.client_code || 'Client')}</strong>
            <div class="meta">${escapeHtml(request.category || 'other')} · ${escapeHtml(request.subject || 'Support')}</div>
          </div>
          <span data-support-status tabindex="-1">${badge(request.status)}</span>
        </div>
        <p>${escapeHtml(request.message || '')}</p>
        ${request.reference_text ? `<p class="meta">Reference: ${escapeHtml(request.reference_text)}</p>` : ''}
        <div data-support-response>${request.management_response ? `<div class="notice-card"><strong>Current response:</strong> ${escapeHtml(request.management_response)}</div>` : ''}</div>
        <form class="entry-form employee-support-review" data-request-id="${escapeHtml(request.request_id)}" data-support-state="${escapeHtml(request.status)}">
          <label>Action<select name="action"><option value="answered">Answer</option><option value="resolved">Resolve</option></select></label>
          <label>Response<textarea name="response" minlength="3" maxlength="2000" required></textarea></label>
          <button class="button button-primary" type="submit">Save response</button>
        </form>
      </article>`,
    )
    .join('')}</div>`;
}

function accountSection(account) {
  const profile = account.profile ?? {};
  const devices = asArray(account.devices);
  return `<div class="card-grid">
    <article class="data-card"><h3>Employee account</h3><div class="kv-list">
      <div class="kv-row"><span>Name</span><strong>${escapeHtml(profile.full_name || '—')}</strong></div>
      <div class="kv-row"><span>Username</span><strong>${escapeHtml(profile.username || '—')}</strong></div>
      <div class="kv-row"><span>Role</span><strong>${escapeHtml(profile.role || 'Employee')}</strong></div>
      <div class="kv-row"><span>Status</span>${badge(profile.status || 'unknown')}</div>
    </div></article>
    <article class="data-card"><h3>Devices</h3>${devices.length ? `<div class="list-stack">${devices.map((device) => `<div class="list-item"><strong>${escapeHtml(device.platform || 'Device')} ${device.is_current ? '· This device' : ''}</strong><span class="meta">Version ${escapeHtml(device.app_version || '—')} · ${formatDateTime(device.last_seen_at)}</span>${badge(device.status)}</div>`).join('')}</div>` : emptyState('No device record is available.')}</article>
  </div>`;
}

function bindActions(context,{isCurrent=()=>true,onDenied=()=>{}}={}) {
  const signal = context.signal;
  for (const form of context.root.querySelectorAll('.employee-support-review')) {
    context.employeeSupportBindings ||= new WeakSet();
    if(context.employeeSupportBindings.has(form))continue;
    context.employeeSupportBindings.add(form);
    form.addEventListener('submit', async (event) => {
      event.preventDefault();
      const button = form.querySelector('button[type="submit"]');
      if (button.disabled || form.hidden || signal?.aborted || !isCurrent()) return;
      const currentSession=context.getSession?context.getSession():context.session;
      if(!currentSession||!hasPermission(currentSession,'support.manage')){onDenied();return;}
      const current = () => !signal?.aborted && form.isConnected && isCurrent();
      setButtonBusy(button, true, 'Saving…');
      context.employeeSupportPending=true;
      const data = new FormData(form);
      const response = String(data.get('response') || '').trim();
      let completed = false;
      try {
        const result = await context.api.request(`/api/v1/management/support/${encodeURIComponent(form.dataset.requestId)}/review`, {
          method: 'POST',
          body: {
            action: data.get('action'),
            response,
          },
        });
        if (!current()) return;
        if (!hasPermission(context.getSession?context.getSession():context.session,'support.manage')) {onDenied();return;}
        const record = result?.request;
        if (record?.request_id !== form.dataset.requestId || !['answered', 'resolved'].includes(record.status) || typeof record.management_response !== 'string') throw new Error('The saved response could not be confirmed. Refresh the support queue before trying again.');
        const card = form.parentElement;
        card.querySelector('[data-support-status]').innerHTML = badge(record.status);
        card.querySelector('[data-support-response]').innerHTML = `<div class="notice-card"><strong>Current response:</strong> ${escapeHtml(record.management_response)}</div>`;
        const responseInput = form.querySelector('[name="response"]');
        if (responseInput.value.trim() === response) responseInput.value = '';
        form.setAttribute('data-support-state', record.status);
        const openCount = [...context.root.querySelectorAll('[data-support-state]')].filter(item => item.getAttribute('data-support-state') === 'open').length;
        for (const count of context.root.querySelectorAll('[data-support-count]')) count.textContent = String(openCount);
        completed = true;
        showToast('Client support response saved.', 'success');
      } catch (error) {
        if (current()) {
          if ([401,403].includes(error?.status)) onDenied(error);
          else showToast(error.message, 'error');
        }
      } finally {
        context.employeeSupportPending=false;
        if (current()) setButtonBusy(button, false);
        else clearButtonBusyFocus(button);
      }
      if (completed && current()) {
        if (button.ownerDocument.activeElement === button && !form.closest('[hidden]')) form.parentElement.querySelector('[data-support-status]').focus({ preventScroll: true });
        form.hidden = true;
      }
    });
  }
}


export {activityRows,supportQueue,accountSection,bindActions};
