import assert from 'node:assert/strict';
import { existsSync, readFileSync } from 'node:fs';
import test from 'node:test';

const moduleUrl = new URL('../assets/client-account-admin.js', import.meta.url);
const managementWorkspaceUrl = new URL('../assets/roles/management.js', import.meta.url);

async function loadClientAccountAdmin() {
  assert.equal(
    existsSync(moduleUrl),
    true,
    'Client account administration module must exist',
  );
  return import(moduleUrl.href);
}

test('Client account request normalizes borrower id and email without accepting credentials', async () => {
  const { buildClientAccountCreateRequest } = await loadClientAccountAdmin();

  const request = buildClientAccountCreateRequest({
    clientId: ' 77777777-7777-4777-8777-777777777777 ',
    email: ' Client@Example.COM ',
    username: 'caller.chosen',
    password: 'caller-chosen-password',
  });

  assert.deepEqual(request, {
    client_id: '77777777-7777-4777-8777-777777777777',
    email: 'client@example.com',
  });
  assert.equal(Object.hasOwn(request, 'username'), false);
  assert.equal(Object.hasOwn(request, 'password'), false);
});

test('Client account creation form contains borrower search and email but no credential inputs', async () => {
  const { clientAccountAdminMarkup } = await loadClientAccountAdmin();

  const markup = clientAccountAdminMarkup();

  assert.match(markup, /Find borrower/i);
  assert.match(markup, /name="email"/i);
  assert.doesNotMatch(markup, /name="username"/i);
  assert.doesNotMatch(markup, /name="password"/i);
});

test('Generated Client credentials render once with delivery status and an explicit copy-now warning', async () => {
  const { renderOneTimeClientCredentials } = await loadClientAccountAdmin();

  const markup = renderOneTimeClientCredentials({
    account: {
      id: '33333333-3333-4333-8333-333333333333',
      full_name: 'Maria Santos',
      status: 'active',
      roles: ['client'],
    },
    credentials: {
      username: 'spina.c.001',
      password: 'Abcdef12@Ghijklm',
    },
    delivery: {
      sent: true,
      detail: 'SPINA account credentials were sent by email.',
    },
  });

  assert.match(markup, /spina\.c\.001/);
  assert.match(markup, /Abcdef12@Ghijklm/);
  assert.match(markup, /copy/i);
  assert.match(markup, /only once|one-time/i);
  assert.match(markup, /sent by email/i);
});

test('Management workspace mounts Client Accounts and retires the active registration queue', () => {
  const source = readFileSync(managementWorkspaceUrl, 'utf8');

  assert.match(source, /clientAccountAdminMarkup/);
  assert.match(source, /bindClientAccountAdmin/);
  assert.match(source, /management-client-accounts/);
  assert.doesNotMatch(source, /\/api\/v1\/management\/client-registrations/);
  assert.doesNotMatch(source, /bindRegistrations/);
});
