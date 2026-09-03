import { escapeHtml, sessionPermissions } from './ui.js';

const STAFF_ROLES = new Set(['employee', 'collector', 'management']);

function requiredText(value, label, minimumLength) {
  const normalized = String(value ?? '').trim();
  if (normalized.length < minimumLength) {
    throw new TypeError(`${label} must contain at least ${minimumLength} characters.`);
  }
  return normalized;
}

export function normalizeStaffInvitation(input = {}) {
  const fullName = requiredText(input.fullName, 'Full name', 2)
    .split(/\s+/)
    .join(' ');
  const username = requiredText(input.username, 'Username', 3);
  if (/\s/.test(username)) {
    throw new TypeError('Username cannot contain spaces.');
  }

  const email = requiredText(input.email, 'Email', 5).toLowerCase();
  if (!email.includes('@')) {
    throw new TypeError('Enter a valid email address.');
  }

  const role = String(input.role ?? '').trim().toLowerCase();
  if (!STAFF_ROLES.has(role)) {
    throw new TypeError('Role must be Employee, Collector, or Management.');
  }

  return {
    full_name: fullName,
    username,
    email,
    role,
  };
}

export function staffInviteMarkup(session = {}) {
  if (!sessionPermissions(session).includes('account.manage')) {
    return '';
  }

  return `<details class="data-card staff-invite-card">
    <summary>Invite staff</summary>
    <p class="meta">Create a protected Spina staff invitation. The invited person completes account setup through the email sent by Spina.</p>
    <form id="management-staff-invite-form" class="entry-form">
      <label>Full name<input name="fullName" autocomplete="name" required minlength="2" maxlength="200" /></label>
      <label>Username<input name="username" autocomplete="off" required minlength="3" maxlength="80" /></label>
      <label>Email<input name="email" type="email" autocomplete="email" required maxlength="320" /></label>
      <label>Role<select name="role" required>
        <option value="employee">Employee</option>
        <option value="collector">Collector</option>
        <option value="management">Management</option>
      </select></label>
      <button class="button button-primary" type="submit">Send invitation</button>
    </form>
    <p class="form-help">Access remains controlled by the selected role, server permissions, and device rules.</p>
  </details>`;
}

export async function submitStaffInvitation(api, input) {
  if (api == null || typeof api.request !== 'function') {
    throw new TypeError('A Spina API client is required.');
  }
  const body = normalizeStaffInvitation(input);
  return api.request('/api/v1/management/accounts/invite', {
    method: 'POST',
    body,
  });
}
