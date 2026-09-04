import { badge, emptyState, escapeHtml, formatDateTime } from './ui.js';

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
    return { nextStatus: 'active', label: 'Approve phone' };
  }
  if (status === 'active') {
    return { nextStatus: 'revoked', label: 'Revoke phone' };
  }
  if (status === 'revoked') {
    return { nextStatus: 'active', label: 'Restore phone' };
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

function deviceConsequence(account, device, action) {
  const roles = normalizedRoles(account);
  const isCollector = roles.includes('collector');
  const status = normalizedStatus(device?.status);
  if (status === 'pending' && action?.nextStatus === 'active' && isCollector) {
    return 'Approving this phone may revoke another active Collector phone for this account.';
  }
  if (status === 'pending' && action?.nextStatus === 'active') {
    return 'Approving this phone allows protected SPINA access for this account.';
  }
  if (status === 'active' && action?.nextStatus === 'revoked') {
    return 'Revoking this phone blocks future protected requests from this device.';
  }
  if (status === 'revoked' && action?.nextStatus === 'active') {
    return 'Restoring this phone allows protected requests again.';
  }
  return '';
}

function deviceCard(account, device, index, canManageDevices) {
  const action = canManageDevices ? deviceAction(device?.status) : null;
  const consequence = action ? deviceConsequence(account, device, action) : '';
  const version = String(device?.app_version ?? '').trim() || 'Not reported';
  const lastSeen = device?.last_seen_at ? formatDateTime(device.last_seen_at) : 'Not yet reported';
  return `<article class="data-card">
    <div class="section-heading">
      <div><h3>${escapeHtml(platformLabel(device?.platform))}</h3><p>App version ${escapeHtml(version)}</p></div>
      ${badge(device?.status || 'unknown')}
    </div>
    <div class="kv-list">
      <div class="kv-row"><span>Registered</span><strong>${formatDateTime(device?.registered_at)}</strong></div>
      <div class="kv-row"><span>Last seen</span><strong>${lastSeen}</strong></div>
    </div>
    ${consequence ? `<div class="notice-card warning">${escapeHtml(consequence)}</div>` : ''}
    ${action ? `<div class="action-row"><button class="button ${action.nextStatus === 'revoked' ? 'button-outline' : 'button-primary'} managed-device-action" type="button" data-managed-device-index="${index}" data-next-device-status="${escapeHtml(action.nextStatus)}">${escapeHtml(action.label)}</button></div>` : ''}
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
  const roleText = roles.length ? roles.join(', ') : 'role not reported';
  const permissionNotice = canManageDevices
    ? ''
    : '<div class="notice-card warning">Device management permission is required to approve, revoke, or restore registered phones.</div>';
  const cards = safeDevices.length
    ? `<div class="card-grid">${safeDevices
        .map((device, index) => deviceCard(account, device, index, canManageDevices))
        .join('')}</div>`
    : emptyState(
        canManageDevices
          ? 'No registered phones were returned by the server for this staff account.'
          : 'Registered phone details are available only with device management permission.',
      );

  return `<div class="section-heading">
    <div><h3>${escapeHtml(name)}</h3><p>${escapeHtml(username)}${username ? ' · ' : ''}${escapeHtml(roleText)}</p></div>
  </div>
  ${permissionNotice}
  ${cards}`;
}
