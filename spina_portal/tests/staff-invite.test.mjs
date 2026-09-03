import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';

import {
  staffInviteMarkup,
  submitStaffInvitation,
} from '../assets/staff-invite.js';

test('Invite Staff is available only with account.manage permission', () => {
  assert.equal(
    staffInviteMarkup({ permissions: ['device.manage'] }),
    '',
  );

  const markup = staffInviteMarkup({
    user: { permissions: ['account.manage'] },
  });

  assert.match(markup, /id="management-staff-invite-form"/);
  assert.match(markup, /name="fullName"/);
  assert.match(markup, /name="username"/);
  assert.match(markup, /name="email"/);
  assert.match(markup, /name="role"/);
  assert.match(markup, /value="employee"/);
  assert.match(markup, /value="collector"/);
  assert.match(markup, /value="management"/);
  assert.doesNotMatch(markup, /password/i);
});

test('staff invitation uses the protected endpoint with normalized input', async () => {
  const calls = [];
  const api = {
    async request(path, options) {
      calls.push({ path, options });
      return {
        invitation_sent: true,
        account: { username: 'office.one', roles: ['employee'] },
      };
    },
  };

  const result = await submitStaffInvitation(api, {
    fullName: '  Office   Employee  ',
    username: '  office.one  ',
    email: '  OFFICE.ONE@EXAMPLE.COM ',
    role: ' Employee ',
  });

  assert.equal(result.invitation_sent, true);
  assert.deepEqual(calls, [
    {
      path: '/api/v1/management/accounts/invite',
      options: {
        method: 'POST',
        body: {
          full_name: 'Office Employee',
          username: 'office.one',
          email: 'office.one@example.com',
          role: 'employee',
        },
      },
    },
  ]);
});

test('invalid staff role fails before network access', async () => {
  let calls = 0;
  const api = {
    async request() {
      calls += 1;
      return {};
    },
  };

  await assert.rejects(
    () => submitStaffInvitation(api, {
      fullName: 'Office Employee',
      username: 'office.one',
      email: 'office.one@example.com',
      role: 'client',
    }),
    /Employee, Collector, or Management/i,
  );
  assert.equal(calls, 0);
});

test('user-facing role modules do not display MVP wording', async () => {
  const sources = await Promise.all([
    readFile(new URL('../assets/roles/management.js', import.meta.url), 'utf8'),
    readFile(new URL('../assets/presenters.js', import.meta.url), 'utf8'),
    readFile(new URL('../assets/collector-contract.js', import.meta.url), 'utf8'),
  ]);

  for (const source of sources) {
    assert.doesNotMatch(source, /\bMVP\b/i);
  }
});
