import {
  asArray,
  badge,
  emptyState,
  errorCard,
  escapeHtml,
  hasPermission,
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
      <div id="management-client-account-candidates" role="status">Search for an active borrower to create a Client account.</div>
    </article>
    <article class="data-card" data-client-account-create-stage hidden>
      <form id="management-client-account-create" class="entry-form">
        <input name="clientId" type="hidden" />
        <div id="management-client-account-selected"></div>
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
  const stage = context.root.querySelector('[data-client-account-create-stage]');
  if (!searchForm || !candidateRoot || !createForm || !selectedRoot || !resultRoot || !stage) return () => {};

  const clientIdInput = createForm.querySelector('input[name="clientId"]');
  const emailInput = createForm.querySelector('input[name="email"]');
  const queryInput = searchForm.querySelector('input[name="query"]');
  const searchButton = searchForm.querySelector('button[type="submit"]');
  const createButton = createForm.querySelector('button[type="submit"]');
  const controller = new AbortController();
  const listeners = [];
  let candidatesById = new Map();
  let searchVersion = 0;
  let selectedId = '';
  let busy = false;
  let uncertain = false;
  let disposed = false;
  const active = () => !disposed && !context.signal?.aborted;
  const allowed = () => {
    const session = context.session;
    const roles = [...asArray(session?.roles), ...asArray(session?.user?.roles), session?.role, session?.user?.role];
    return roles.includes('management') && !roles.includes('client') && hasPermission(session, 'account.manage');
  };
  const online = context.isOnline || (() => globalThis.navigator?.onLine !== false);

  function on(element, type, handler) {
    element.addEventListener(type, handler);
    listeners.push(() => element.removeEventListener(type, handler));
  }

  function clearSelection() {
    selectedId = '';
    clientIdInput.value = '';
    emailInput.value = '';
    selectedRoot.innerHTML = '';
    stage.setAttribute('hidden', '');
    createButton.disabled = true;
  }

  function invalidateSearch() {
    searchVersion += 1;
    candidatesById = new Map();
    clearSelection();
    candidateRoot.innerHTML = '';
    if (!uncertain) resultRoot.innerHTML = '';
    if (!busy && active()) setButtonBusy(searchButton, false);
  }

  function lockUncertain() {
    uncertain = true;
    invalidateSearch();
    resultRoot.innerHTML = '<div class="notice-card warning" role="alert" data-client-account-uncertain><strong>The creation result is uncertain.</strong> The account may already exist. Search the borrower again to refresh authoritative records before another creation attempt.</div>';
  }

  function cleanup() {
    if (disposed) return;
    disposed = true;
    controller.abort();
    context.signal?.removeEventListener('abort', cleanup);
    for (const remove of listeners) remove();
    invalidateSearch();
    resultRoot.innerHTML = '';
    queryInput.value = '';
    queryInput.disabled = true;
    searchButton.disabled = true;
  }

  context.signal?.addEventListener('abort', cleanup, { once: true });
  if (!active() || !allowed()) {
    cleanup();
    return cleanup;
  }

  on(queryInput, 'input', () => {
    if (active() && !busy) invalidateSearch();
  });

  on(searchForm, 'submit', async (event) => {
    event.preventDefault();
    if (!active() || !allowed() || busy) return;
    invalidateSearch();
    const version = searchVersion;
    const query = String(new FormData(searchForm).get('query') || '').trim();
    if (!online()) {
      candidateRoot.innerHTML = emptyState('Connect to the internet to search authoritative borrower records.');
      return;
    }
    if (query.length < 2) {
      candidateRoot.innerHTML = emptyState('Enter at least two characters to find a borrower.');
      return;
    }
    setButtonBusy(searchButton, true, 'Searching…');
    try {
      const data = await context.api.request(
        `/api/v1/management/client-link-candidates?q=${encodeURIComponent(query)}`,
        { signal: controller.signal },
      );
      if (!active() || version !== searchVersion) return;
      if (!Array.isArray(data?.clients) || data.clients.some((client) => !client || typeof client.id !== 'string' || !client.id || client.status !== 'active')) {
        throw new TypeError('The borrower search response could not be confirmed. Search again.');
      }
      const clients = data.clients;
      candidatesById = new Map(clients.map((client) => [String(client.id || ''), client]));
      uncertain = false;
      resultRoot.innerHTML = '';
      candidateRoot.innerHTML = candidateListMarkup(clients);
      for (const selectButton of candidateRoot.querySelectorAll('.select-client-account-borrower')) {
        on(selectButton, 'click', () => {
          if (!active() || !allowed() || busy || uncertain || version !== searchVersion) return;
          const client = candidatesById.get(String(selectButton.getAttribute('data-client-id') || ''));
          if (!client) {
            showToast('The borrower search result is stale. Search again.', 'error');
            return;
          }
          if (selectedId !== client.id) emailInput.value = '';
          selectedId = client.id;
          clientIdInput.value = selectedId;
          selectedRoot.className = 'data-card';
          selectedRoot.innerHTML = `<strong>${escapeHtml(client.full_name || 'Borrower')}</strong><div class="meta">${escapeHtml(client.client_code || '—')} · ${escapeHtml(client.area || '')}</div>`;
          stage.removeAttribute('hidden');
          createButton.disabled = false;
        });
      }
    } catch (error) {
      if (!active() || version !== searchVersion) return;
      if ([401, 403].includes(error?.status)) { cleanup(); return; }
      candidateRoot.innerHTML = errorCard(error, 'Borrower search is temporarily unavailable.');
    } finally {
      if (active() && version === searchVersion) setButtonBusy(searchButton, false);
    }
  });

  on(createForm, 'submit', async (event) => {
    event.preventDefault();
    if (!active() || !allowed() || busy || uncertain) return;
    if (!online()) { showToast('Connect to the internet to create a Client account.', 'error'); return; }
    if (!selectedId || clientIdInput.value !== selectedId || !candidatesById.has(selectedId)) {
      clearSelection();
      showToast('Search for and select the borrower again before creating an account.', 'error');
      return;
    }
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
    if (!globalThis.confirm?.('Create a Client account for the selected borrower and generate credentials?')) {
      return;
    }

    busy = true;
    queryInput.disabled = true;
    searchButton.disabled = true;
    setButtonBusy(createButton, true, 'Creating…');
    try {
      const result = await context.api.request('/api/v1/management/client-accounts', {
        method: 'POST',
        body,
        signal: controller.signal,
      });
      if (!active()) return;
      if (!result?.account?.username || result.credentials?.username !== result.account.username ||
          typeof result.credentials?.password !== 'string' || !result.credentials.password ||
          typeof result.delivery?.sent !== 'boolean' || typeof result.delivery?.detail !== 'string') {
        lockUncertain();
        return;
      }
      invalidateSearch();
      resultRoot.innerHTML = renderOneTimeClientCredentials(result);
      candidateRoot.innerHTML = emptyState('Account created. Search again to select another borrower.');
      showToast('Client account created. Copy the one-time credentials now.', 'success');
      resultRoot.scrollIntoView?.({ behavior: 'smooth', block: 'start' });
    } catch (error) {
      if (!active()) return;
      if ([401, 403].includes(error?.status)) { cleanup(); return; }
      if (!error?.status || error.status >= 500 || [408, 429].includes(error.status)) lockUncertain();
      else {
        invalidateSearch();
        resultRoot.innerHTML = errorCard(error, 'Client account creation was not accepted. Search the borrower again before retrying.');
      }
      showToast(error.message, 'error');
    } finally {
      busy = false;
      if (active()) {
        setButtonBusy(createButton, false);
        createButton.disabled = uncertain || !selectedId;
        queryInput.disabled = false;
        searchButton.disabled = false;
      }
    }
  });
  return cleanup;
}
