import { escapeHtml } from './ui.js';

function requiredText(value, label, minimumLength) {
  const normalized = String(value ?? '').trim();
  if (normalized.length < minimumLength) {
    throw new TypeError(`${label} must contain at least ${minimumLength} characters.`);
  }
  return normalized;
}

export function buildClientAccountCreateRequest(input = {}) {
  const clientId = requiredText(input.clientId, 'Borrower record', 1);
  const email = requiredText(input.email, 'Email', 5).toLowerCase();
  if (!email.includes('@')) {
    throw new TypeError('Enter a valid email address.');
  }
  return {
    client_id: clientId,
    email,
  };
}

export function clientAccountAdminMarkup() {
  return `<div class="list-stack client-account-admin">
    <article class="data-card">
      <div class="section-heading"><div><h3>Create Client account</h3><p>Create sign-in credentials only for an existing active borrower record that is not already linked to a Client account.</p></div></div>
      <form id="management-client-account-search" class="search-bar">
        <input name="query" minlength="2" maxlength="200" required placeholder="Find borrower by name, Client code, phone, or area" />
        <button class="button button-secondary" type="submit">Find borrower</button>
      </form>
      <div id="management-client-account-candidates">Select a borrower record before creating credentials.</div>
    </article>
    <article class="data-card">
      <form id="management-client-account-create" class="entry-form">
        <input name="clientId" type="hidden" />
        <div id="management-client-account-selected" class="empty-state">No borrower selected.</div>
        <label>Email<input name="email" type="email" autocomplete="email" required maxlength="320" /></label>
        <button class="button button-primary" type="submit" disabled>Create Client account</button>
      </form>
      <p class="form-help">SPINA generates the username and password. Management does not type the Client credentials.</p>
    </article>
    <div id="management-client-account-result"></div>
  </div>`;
}

export function renderOneTimeClientCredentials(data = {}) {
  const account = data.account ?? {};
  const credentials = data.credentials ?? {};
  const delivery = data.delivery ?? {};
  const username = escapeHtml(credentials.username || '—');
  const password = escapeHtml(credentials.password || '—');
  const name = escapeHtml(account.full_name || account.username || 'Client');
  const deliveryDetail = escapeHtml(
    delivery.detail || (delivery.sent ? 'Credential email sent.' : 'Credential email was not sent.'),
  );

  return `<article class="data-card one-time-client-credentials">
    <div class="section-heading"><div><h3>Client account created</h3><p>${name}</p></div></div>
    <div class="notice-card warning"><strong>Copy these credentials now.</strong> SPINA shows this password only once and does not keep a readable copy.</div>
    <div class="kv-list">
      <div class="kv-row"><span>Username</span><strong><code>${username}</code></strong></div>
      <div class="kv-row"><span>Password</span><strong><code>${password}</code></strong></div>
      <div class="kv-row"><span>Email delivery</span><strong>${delivery.sent ? 'Sent' : 'Not sent'}</strong></div>
    </div>
    <p class="meta">${deliveryDetail}</p>
  </article>`;
}
