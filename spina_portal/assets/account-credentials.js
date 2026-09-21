import { asArray, escapeHtml } from './ui.js';

function accessFor(session = {}) {
  const roles = new Set([
    ...asArray(session.roles), ...asArray(session.user?.roles),
    session.role, session.user?.role,
  ]);
  const permissions = new Set([...asArray(session.permissions), ...asArray(session.user?.permissions)]);
  const staff = !roles.has('client') && ['collector', 'employee', 'management'].some((role) => roles.has(role));
  const anyAccount = staff && roles.has('management') && permissions.has('account.manage');
  const clients = staff && (roles.has('employee') || roles.has('management')) && permissions.has('client.credential.manage');
  return { staff, anyAccount, reset: anyAccount || clients };
}

export function accountCredentialsMarkup({ session } = {}) {
  const access = accessFor(session);
  if (!access.staff) return '';
  return `<div class="list-stack">
    <article class="data-card">
      <h3>Change my password</h3>
      <p>Changes only the password for your signed-in staff account.</p>
      <form class="entry-form" data-credential-own-form>
        <label>New password<input type="password" name="newPassword" autocomplete="new-password" required maxlength="200" /></label>
        <label>Confirm new password<input type="password" name="confirmPassword" autocomplete="new-password" required maxlength="200" /></label>
        <button class="button button-primary" type="submit">Change password</button>
        <button class="button button-secondary" type="button" data-credential-clear-password>Clear password</button>
      </form>
      <div role="status" aria-live="polite" data-credential-own-message></div>
    </article>
    ${access.reset ? `<article class="data-card">
      <h3>${access.anyAccount ? 'Reset account password' : 'Reset Client password'}</h3>
      <p>Find an existing ${access.anyAccount ? 'Client or staff' : 'Client'} account, then confirm whose password will be replaced.</p>
      <form class="search-bar" data-credential-search-form>
        <label>Account search<input name="accountQuery" minlength="2" maxlength="200" required autocomplete="off" placeholder="Name, username, or email" /></label>
        <button class="button button-secondary" type="submit">Find account</button>
      </form>
      <div role="status" aria-live="polite" data-credential-search-message></div>
      <div class="list-stack" data-credential-results></div>
      <div data-credential-selection></div>
      <div data-credential-result></div>
    </article>` : ''}
  </div>`;
}

function validAccount(account, access) {
  return account && /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(account.id)
    && typeof account.username === 'string' && account.username.length > 0
    && Array.isArray(account.roles) && (access.anyAccount || account.roles.includes('client'));
}

function accountIdentity(account) {
  return `<strong>${escapeHtml(account.full_name || account.username)}</strong>
    <div class="meta">Username: ${escapeHtml(account.username)} · ${escapeHtml(account.email || 'No email')}
    · ${escapeHtml(asArray(account.roles).join(', '))} · ${escapeHtml(account.status || 'Unknown status')}</div>`;
}

function confirmedReset(data, target, access) {
  return validAccount(data?.account, access) && data.account.id === target.id
    && data.account.username === target.username
    && data.credentials?.username === target.username
    && typeof data.credentials?.password === 'string' && data.credentials.password.length > 0
    && typeof data.delivery?.sent === 'boolean' && typeof data.delivery.detail === 'string'
    && typeof data.audit_recorded === 'boolean';
}

export function mountAccountCredentials({ root, api, session, signal, isOnline = () => globalThis.navigator?.onLine !== false }) {
  if (!root) return () => {};
  const access = accessFor(session);
  const controller = new AbortController();
  const listeners = [];
  let disposed = false;
  let busy = false;
  let locked = false;
  let searchVersion = 0;
  let selectionVersion = 0;
  let selected = null;
  root.innerHTML = signal?.aborted ? '' : accountCredentialsMarkup({ session });

  const ownForm = root.querySelector('[data-credential-own-form]');
  const password = root.querySelector('[name="newPassword"]');
  const confirmation = root.querySelector('[name="confirmPassword"]');
  const ownMessage = root.querySelector('[data-credential-own-message]');
  const searchForm = root.querySelector('[data-credential-search-form]');
  const query = root.querySelector('[name="accountQuery"]');
  const searchMessage = root.querySelector('[data-credential-search-message]');
  const results = root.querySelector('[data-credential-results]');
  const selection = root.querySelector('[data-credential-selection]');
  const result = root.querySelector('[data-credential-result]');
  const active = () => !disposed && !signal?.aborted;

  function on(element, type, handler) {
    if (!element) return;
    element.addEventListener(type, handler);
    listeners.push(() => element.removeEventListener(type, handler));
  }

  function clearPasswords() {
    if (password) password.value = '';
    if (confirmation) confirmation.value = '';
  }

  function clearResult() {
    if (!result) return;
    for (const input of result.querySelectorAll('input')) {
      input.value = '';
      input.removeAttribute('value');
    }
    result.innerHTML = '';
  }

  // Bind outside the request's response scope so event handlers never retain
  // the plaintext response object after the displayed credential is dismissed.
  function bindCredentialResult() {
    on(result.querySelector('[data-credential-reveal]'), 'click', () => {
      if (!active()) return;
      const input = result.querySelector('[data-credential-issued-password]');
      const reveal = result.querySelector('[data-credential-reveal]');
      if (!input || !reveal) return;
      const show = input.getAttribute('type') === 'password';
      input.setAttribute('type', show ? 'text' : 'password');
      reveal.textContent = show ? 'Hide password' : 'Show password';
    });
    on(result.querySelector('[data-credential-dismiss]'), 'click', () => {
      if (active()) clearResult();
    });
  }

  function clearSelection() {
    selected = null;
    selectionVersion += 1;
    if (selection) selection.innerHTML = '';
  }

  function updateDisabled() {
    for (const form of [ownForm, searchForm, selection]) {
      if (!form) continue;
      for (const control of [...form.querySelectorAll('input'), ...form.querySelectorAll('button')]) {
        control.disabled = busy || locked;
      }
    }
  }

  function usable(message) {
    if (!active() || locked || busy) return false;
    if (isOnline()) return true;
    message.textContent = 'Connect to the internet to continue. Password actions require an online connection.';
    return false;
  }

  function uncertain(message) {
    locked = true;
    clearPasswords();
    clearResult();
    clearSelection();
    searchVersion += 1;
    if (results) results.innerHTML = '';
    message.textContent = 'SPINA could not confirm the password change. The password may already have changed. Do not repeat this action. Check the account or credential email with the account holder before using Refresh to reopen these controls. Search and confirm the account again if another reset is necessary.';
    updateDisabled();
  }

  function accessDenied() {
    cleanup();
    root.textContent = 'Credential access is no longer available. Sign in again to refresh your permissions.';
  }

  function handleFailure(error, message, mutation = false) {
    if (!active()) return;
    if ([401, 403].includes(error?.status)) {
      accessDenied();
    } else if (mutation && (!error?.status || error.status >= 500 || [408, 429].includes(error.status))) {
      uncertain(message);
    } else {
      message.textContent = mutation
        ? 'The server did not accept this password change. Check the account and password requirements before trying again.'
        : 'Account search is unavailable. Check your connection and search again.';
    }
  }

  function cleanup() {
    if (disposed) return;
    disposed = true;
    controller.abort();
    signal?.removeEventListener('abort', cleanup);
    for (const remove of listeners) remove();
    listeners.length = 0;
    clearPasswords();
    clearResult();
    clearSelection();
    if (query) query.value = '';
    if (results) results.innerHTML = '';
    searchVersion += 1;
    root.innerHTML = '';
  }

  signal?.addEventListener('abort', cleanup, { once: true });
  if (signal?.aborted || !access.staff) {
    cleanup();
    return cleanup;
  }

  on(root.querySelector('[data-credential-clear-password]'), 'click', () => {
    if (!active()) return;
    clearPasswords();
    if (!locked && !busy) ownMessage.textContent = '';
  });

  on(ownForm, 'submit', async (event) => {
    event.preventDefault();
    let nextPassword = password.value;
    const matches = nextPassword === confirmation.value;
    clearPasswords();
    if (!usable(ownMessage)) return;
    if (!nextPassword || nextPassword.length > 200 || !matches) {
      ownMessage.textContent = !matches ? 'The new passwords must match.' : 'Enter a new password between 1 and 200 characters.';
      return;
    }
    clearResult();
    busy = true;
    updateDisabled();
    ownMessage.textContent = 'Changing password…';
    try {
      const request = api.request('/api/v1/auth/password', {
        method: 'PATCH', body: { password: nextPassword }, signal: controller.signal,
      });
      nextPassword = '';
      const data = await request;
      if (!active()) return;
      if (data?.success !== true) uncertain(ownMessage);
      else ownMessage.textContent = 'Password changed.';
    } catch (error) {
      handleFailure(error, ownMessage, true);
    } finally {
      nextPassword = '';
      busy = false;
      if (active()) updateDisabled();
    }
  });

  function invalidateSearch() {
    searchVersion += 1;
    clearSelection();
    clearResult();
    if (results) results.innerHTML = '';
  }

  on(query, 'input', () => {
    if (!active() || locked || busy) return;
    invalidateSearch();
    searchMessage.textContent = '';
  });

  on(searchForm, 'submit', async (event) => {
    event.preventDefault();
    if (!usable(searchMessage)) return;
    invalidateSearch();
    const text = query.value.trim().replace(/\s+/g, ' ');
    if (text.length < 2 || text.length > 200) {
      searchMessage.textContent = 'Enter 2 to 200 characters to find an account.';
      return;
    }
    const version = searchVersion;
    searchMessage.textContent = 'Searching…';
    const path = access.anyAccount
      ? `/api/v1/management/accounts?q=${encodeURIComponent(text)}&limit=25`
      : `/api/v1/management/client-accounts?q=${encodeURIComponent(text)}`;
    try {
      const data = await api.request(path, { signal: controller.signal });
      if (!active() || locked || version !== searchVersion) return;
      const accounts = asArray(data?.accounts).filter((account) => validAccount(account, access));
      searchMessage.textContent = accounts.length ? 'Select the account whose password needs to be reset.' : 'No matching account was returned.';
      results.innerHTML = accounts.map((account, index) => `<article class="list-item">${accountIdentity(account)}
        <button class="button button-secondary" type="button" data-credential-select="${index}">Select account</button></article>`).join('');
      for (const button of results.querySelectorAll('[data-credential-select]')) {
        on(button, 'click', () => {
          if (!active() || locked || busy || version !== searchVersion) return;
          clearResult();
          clearSelection();
          selected = accounts[Number(button.getAttribute('data-credential-select'))];
          const target = selected;
          const selectedVersion = selectionVersion;
          selection.innerHTML = `<form class="entry-form" data-credential-reset-form>
            <h4>Confirm password reset</h4>${accountIdentity(target)}
            <p>The previous password will stop working. SPINA generates the replacement and may email Client credentials to the account holder.</p>
            <button class="button button-primary" type="submit">Generate new password</button>
            <button class="button button-secondary" type="button" data-credential-cancel>Cancel reset</button>
          </form>`;
          on(selection.querySelector('[data-credential-cancel]'), 'click', () => {
            if (active() && !busy && selectedVersion === selectionVersion) clearSelection();
          });
          on(selection.querySelector('form'), 'submit', async (submit) => {
            submit.preventDefault();
            if (selected !== target || selectedVersion !== selectionVersion || !usable(searchMessage)) return;
            busy = true;
            searchVersion += 1;
            updateDisabled();
            searchMessage.textContent = 'Replacing password…';
            try {
              const data = await api.request(`/api/v1/management/accounts/${target.id}/password/reset`, {
                method: 'POST', signal: controller.signal,
              });
              if (!active()) return;
              clearSelection();
              results.innerHTML = '';
              if (!confirmedReset(data, target, access)) {
                uncertain(searchMessage);
                return;
              }
              searchMessage.textContent = 'Password replaced.';
              result.innerHTML = `<article class="data-card">
                <h4>One-time credentials</h4>
                <p>Copy these credentials now. This password is shown only once; dismissing clears it.</p>
                <p>Username: <code>${escapeHtml(data.credentials.username)}</code></p>
                <label>New password<input data-credential-issued-password type="password" autocomplete="off" readonly value="${escapeHtml(data.credentials.password)}" /></label>
                <button class="button button-secondary" type="button" data-credential-reveal>Show password</button>
                <p>Email delivery: ${data.delivery.sent ? 'Sent' : 'Not sent'}. ${escapeHtml(data.delivery.detail)}</p>
                ${data.audit_recorded ? '' : '<p class="notice-card warning">The password changed, but the completion audit could not be recorded. Ask Management to review the audit; do not reset again for this warning.</p>'}
                <button class="button button-secondary" type="button" data-credential-dismiss>Dismiss credentials</button>
              </article>`;
              bindCredentialResult();
            } catch (error) {
              if (active()) clearSelection();
              handleFailure(error, searchMessage, true);
            } finally {
              busy = false;
              if (active()) updateDisabled();
            }
          });
        });
      }
    } catch (error) {
      if (active() && version === searchVersion) handleFailure(error, searchMessage);
    }
  });

  return cleanup;
}
