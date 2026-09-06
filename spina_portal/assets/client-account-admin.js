import {
  asArray,
  badge,
  emptyState,
  errorCard,
  escapeHtml,
  setButtonBusy,
  showToast,
} from './ui.js';

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

function candidateListMarkup(clients) {
  if (!clients.length) {
    return emptyState('No active unlinked borrower record matched that search.');
  }
  return `<div class="list-stack">${clients.map((client) => `<article class="list-item">
    <div class="section-heading"><div><strong>${escapeHtml(client.full_name || 'Borrower')}</strong><div class="meta">${escapeHtml(client.client_code || '—')} · ${escapeHtml(client.area || '')}${client.phone_number ? ` · ${escapeHtml(client.phone_number)}` : ''}</div></div>${badge(client.status || 'active')}</div>
    <button class="button button-primary button-small select-client-account-borrower" type="button" data-client-id="${escapeHtml(client.id || '')}">Select borrower</button>
  </article>`).join('')}</div>`;
}

export function bindClientAccountAdmin(context) {
  const searchForm = context.root.querySelector('#management-client-account-search');
  const candidateRoot = context.root.querySelector('#management-client-account-candidates');
  const createForm = context.root.querySelector('#management-client-account-create');
  const selectedRoot = context.root.querySelector('#management-client-account-selected');
  const resultRoot = context.root.querySelector('#management-client-account-result');
  if (!searchForm || !candidateRoot || !createForm || !selectedRoot || !resultRoot) return;

  const clientIdInput = createForm.querySelector('input[name="clientId"]');
  const createButton = createForm.querySelector('button[type="submit"]');
  let candidatesById = new Map();

  searchForm.addEventListener('submit', async (event) => {
    event.preventDefault();
    const query = String(new FormData(searchForm).get('query') || '').trim();
    if (query.length < 2) {
      candidateRoot.innerHTML = emptyState('Enter at least two characters to find a borrower.');
      return;
    }
    const button = searchForm.querySelector('button[type="submit"]');
    setButtonBusy(button, true, 'Searching…');
    try {
      const data = await context.api.request(
        `/api/v1/management/client-link-candidates?q=${encodeURIComponent(query)}`,
      );
      const clients = asArray(data.clients);
      candidatesById = new Map(clients.map((client) => [String(client.id || ''), client]));
      candidateRoot.innerHTML = candidateListMarkup(clients);
      for (const selectButton of candidateRoot.querySelectorAll('.select-client-account-borrower')) {
        selectButton.addEventListener('click', () => {
          const client = candidatesById.get(String(selectButton.dataset.clientId || ''));
          if (!client) {
            showToast('The borrower search result is stale. Search again.', 'error');
            return;
          }
          clientIdInput.value = String(client.id || '');
          selectedRoot.className = 'data-card';
          selectedRoot.innerHTML = `<strong>${escapeHtml(client.full_name || 'Borrower')}</strong><div class="meta">${escapeHtml(client.client_code || '—')} · ${escapeHtml(client.area || '')}</div>`;
          createButton.disabled = false;
        });
      }
    } catch (error) {
      candidateRoot.innerHTML = errorCard(error, 'Borrower search is temporarily unavailable.');
    } finally {
      setButtonBusy(button, false);
    }
  });

  createForm.addEventListener('submit', async (event) => {
    event.preventDefault();
    const data = new FormData(createForm);
    let body;
    try {
      body = buildClientAccountCreateRequest({
        clientId: data.get('clientId'),
        email: data.get('email'),
      });
    } catch (error) {
      showToast(error.message, 'error');
      return;
    }
    if (
      typeof globalThis.confirm === 'function' &&
      !globalThis.confirm('Create a Client account for the selected borrower and generate credentials?')
    ) {
      return;
    }

    setButtonBusy(createButton, true, 'Creating…');
    try {
      const result = await context.api.request('/api/v1/management/client-accounts', {
        method: 'POST',
        body,
      });
      resultRoot.innerHTML = renderOneTimeClientCredentials(result);
      createForm.reset();
      clientIdInput.value = '';
      selectedRoot.className = 'empty-state';
      selectedRoot.textContent = 'No borrower selected.';
      createButton.disabled = true;
      candidateRoot.innerHTML = emptyState('Account created. Search again to select another borrower.');
      candidatesById = new Map();
      showToast('Client account created. Copy the one-time credentials now.', 'success');
      resultRoot.scrollIntoView?.({ behavior: 'smooth', block: 'start' });
    } catch (error) {
      resultRoot.innerHTML = errorCard(
        error,
        'SPINA could not confirm Client account creation. Refresh authoritative records before retrying.',
      );
      showToast(error.message, 'error');
      setButtonBusy(createButton, false);
    }
  });
}
