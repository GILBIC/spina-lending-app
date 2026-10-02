import { badge, emptyState, escapeHtml, formatDateTime, titleCase } from './ui.js';

function normalizedStatus(value) {
  return String(value ?? '').trim().toLowerCase();
}

function normalizedRoles(account) {
  return Array.isArray(account?.roles)
    ? account.roles.map((role) => String(role).trim().toLowerCase()).filter(Boolean)
    : [];
}

export function deviceAction(status) {
  return switchStatus(normalizedStatus(status));
}

function switchStatus(status) {
  if (status === 'pending') {
    return { nextStatus: 'active', label: 'Approve device' };
  }
  if (status === 'active') {
    return { nextStatus: 'revoked', label: 'Revoke access' };
  }
  if (status === 'revoked') {
    return { nextStatus: 'active', label: 'Restore access' };
  }
  return null;
}

export async function loadManagedDevices(api, userId) {
  const result = await api.request(
    `/api/v1/management/accounts/${encodeURIComponent(String(userId))}/devices`,
  );
  return Array.isArray(result?.devices) ? result.devices : [];
}

export async function changeManagedDeviceStatus(api, deviceId, status) {
  const normalized = normalizedStatus(status);
  if (!['active', 'revoked'].includes(normalized)) {
    throw new TypeError('Managed device status must be active or revoked.');
  }
  return api.request(
    `/api/v1/management/devices/${encodeURIComponent(String(deviceId))}/status`,
    {
      method: 'PATCH',
      body: { status: normalized },
    },
  );
}

function platformLabel(value) {
  const normalized = String(value ?? '').trim().toLowerCase();
  if (normalized === 'android') return 'Android';
  if (normalized === 'ios') return 'iOS';
  if (normalized === 'web') return 'Web';
  if (normalized === 'desktop') return 'Desktop';
  return normalized ? 'Device' : 'Unknown device';
}

function deviceCard(device, index, canManageDevices) {
  const action = canManageDevices ? deviceAction(device?.status) : null;
  const version = String(device?.app_version ?? '').trim() || 'Not reported';
  const lastSeen = device?.last_seen_at ? formatDateTime(device.last_seen_at) : 'Not yet reported';
  return `<article class="data-card managed-device-card" data-managed-device-status="${escapeHtml(normalizedStatus(device?.status) || 'unknown')}">
    <div class="section-heading">
      <div><h3>${escapeHtml(platformLabel(device?.platform))}</h3><p>App version ${escapeHtml(version)}</p></div>
      ${badge(device?.status || 'unknown')}
    </div>
    <div class="kv-list">
      <div class="kv-row"><span>Registered</span><strong>${formatDateTime(device?.registered_at)}</strong></div>
      <div class="kv-row"><span>Last seen</span><strong>${lastSeen}</strong></div>
    </div>
    ${action ? `<div class="action-row"><button class="button ${action.nextStatus === 'revoked' ? 'button-danger' : 'button-outline'} managed-device-action" type="button" data-managed-device-index="${index}" data-next-device-status="${escapeHtml(action.nextStatus)}">${escapeHtml(action.label)}</button></div>` : ''}
  </article>`;
}

export function renderManagedDevicePanel(
  account,
  devices,
  { canManageDevices = false } = {},
) {
  const safeDevices = Array.isArray(devices) ? devices : [];
  const name = account?.full_name || account?.username || 'Staff account';
  const username = account?.username ? `@${account.username}` : '';
  const roles = normalizedRoles(account);
  const roleText = roles.length ? roles.map(titleCase).join(', ') : 'Role not reported';
  const permissionNotice = canManageDevices
    ? ''
    : '<div class="notice-card warning">Device management permission is required to inspect, approve, revoke, or restore registered devices.</div>';
  const counts = { active: 0, pending: 0, revoked: 0, other: 0 };
  for (const device of safeDevices) {
    const status = normalizedStatus(device?.status);
    counts[['active', 'pending', 'revoked'].includes(status) ? status : 'other'] += 1;
  }
  const summary = canManageDevices || safeDevices.length ? `<p class="managed-device-summary">${safeDevices.length} ${safeDevices.length === 1 ? 'device' : 'devices'} · ${counts.active} active · ${counts.pending} pending · ${counts.revoked} revoked${counts.other ? ` · ${counts.other} other` : ''}</p>` : '';
  const filters = safeDevices.length ? `<div class="managed-device-filters" role="group" aria-label="Filter registered devices">${['all', 'active', 'pending', 'revoked'].map((status) => `<button class="button button-quiet button-small" type="button" data-managed-device-filter="${status}" aria-pressed="${status === 'all'}">${titleCase(status)}</button>`).join('')}</div>` : '';
  const cards = safeDevices.length
    ? `<div class="managed-device-list">${safeDevices
        .map((device, index) => deviceCard(device, index, canManageDevices))
        .join('')}</div><p class="meta" role="status" data-managed-device-filter-empty hidden>No devices match this status.</p>`
    : emptyState(
        canManageDevices
          ? 'No registered devices were returned by the server for this staff account.'
          : 'Registered device details are available only with device management permission.',
      );

  return `<div class="section-heading">
    <div><h3 tabindex="-1" data-managed-device-heading>${escapeHtml(name)}</h3><p>${escapeHtml(username)}${username ? ' · ' : ''}${escapeHtml(roleText)}</p></div>
    <button class="button button-quiet button-small" type="button" data-managed-device-close>Close</button>
  </div>
  ${permissionNotice}
  ${summary}${filters}
  ${cards}<p class="meta" data-managed-device-visible></p><button class="button button-outline" type="button" data-managed-device-more hidden>Show 10 more devices</button>`;
}

export function bindManagedDevicePanel(root, {state = {}} = {}) {
  if (!root) return () => {};
  const buttons = root.querySelectorAll('[data-managed-device-filter]');
  const cards = root.querySelectorAll('[data-managed-device-status]');
  const empty = root.querySelector('[data-managed-device-filter-empty]');
  const more = root.querySelector('[data-managed-device-more]');
  const count = root.querySelector('[data-managed-device-visible]');
  const listeners = [];
  const statuses=Array.from(cards).map(card=>card.getAttribute('data-managed-device-status'));
  if(!['all','active','pending','revoked'].includes(state.filter))state.filter=statuses.includes('pending')?'pending':statuses.includes('active')?'active':'all';
  let cap=10;
  function render() {
    let matched=0,visible=0;
    for(const card of cards) {
      const match=state.filter==='all'||card.getAttribute('data-managed-device-status')===state.filter;
      if(match)matched++;
      if(match&&matched<=cap){card.removeAttribute('hidden');visible++;}else card.setAttribute('hidden','');
    }
    for(const button of buttons)button.setAttribute('aria-pressed',String(button.getAttribute('data-managed-device-filter')===state.filter));
    if(matched)empty?.setAttribute('hidden','');else empty?.removeAttribute('hidden');
    if(count)count.textContent=`${visible} visible · ${matched} matching · ${cards.length} loaded devices`;
    if(more)more.hidden=matched<=cap;
  }
  for (const button of buttons) {
    const filter = () => {
      const status = button.getAttribute('data-managed-device-filter');
      if (!['all', 'active', 'pending', 'revoked'].includes(status)) return;
      state.filter=status;cap=10;render();
    };
    button.addEventListener('click', filter);
    listeners.push(() => button.removeEventListener('click', filter));
  }
  const showMore=()=>{cap+=10;render();};more?.addEventListener('click',showMore);listeners.push(()=>more?.removeEventListener('click',showMore));render();
  return () => { for (const remove of listeners) remove(); };
}
