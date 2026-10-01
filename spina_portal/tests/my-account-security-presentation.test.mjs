import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';

import {
  accountCredentialsMarkup,
} from '../assets/account-credentials.js';

const managementSource = await readFile(
  new URL('../assets/roles/management.js', import.meta.url),
  'utf8',
);
const appSource = await readFile(
  new URL('../assets/app.js', import.meta.url),
  'utf8',
);

const managementSession = {
  user: {
    roles: ['collector', 'management'],
    role: 'management',
  },
  permissions: ['account.manage', 'client.credential.manage'],
};

test('Management My account presents active workspace separately from additional access', () => {
  assert.match(managementSource, /<span>Workspace<\/span><strong>Management<\/strong>/);
  assert.match(managementSource, /<span>Additional access<\/span>/);
  assert.match(managementSource, /titleCase\(String\(role/);
  assert.doesNotMatch(
    managementSource,
    /<span>Roles<\/span><strong>\$\{escapeHtml\(asArray\(profile\.roles\)\.join/,
  );
});

test('Management membership still pins one Management workspace and hides workspace switching', () => {
  assert.match(appSource, /const hasManagementWorkspace = roles\.includes\('management'\)/);
  assert.match(appSource, /hasManagementWorkspace\s*\? 'management'/);
  assert.match(appSource, /workspaceChoiceLabel\.hidden = hasManagementWorkspace \|\| roles\.length < 2/);
});

test('Management password controls separate own-password and administrator reset work', () => {
  const markup = accountCredentialsMarkup({ session: managementSession });

  assert.match(markup, />My password</);
  assert.match(markup, /Changes only the password for your signed-in staff account\./);
  assert.match(markup, />Reset another account's password</);
  assert.match(markup, /higher-risk administrator action/i);
  assert.match(markup, /Find an existing Client or staff account/i);
  assert.match(
    markup,
    /class="button button-quiet"[^>]*data-credential-clear-password>Clear password</,
  );
});

test('Employee reset wording remains Client-only while Collector gets no reset surface', () => {
  const employee = accountCredentialsMarkup({
    session: {
      user: { roles: ['employee'] },
      permissions: ['client.credential.manage'],
    },
  });
  assert.match(employee, />My password</);
  assert.match(employee, />Reset Client password</);
  assert.doesNotMatch(employee, /another account's password/i);

  const collector = accountCredentialsMarkup({
    session: {
      user: { roles: ['collector'] },
      permissions: [],
    },
  });
  assert.match(collector, />My password</);
  assert.doesNotMatch(collector, /Reset .*password/);
});

test('password guidance stays concise without weakening server validation', () => {
  const markup = accountCredentialsMarkup({ session: managementSession });

  assert.match(markup, /Both entries must match/i);
  assert.doesNotMatch(markup, /minimum of \d+|must contain an uppercase|special character/i);
  assert.match(markup, /autocomplete="new-password"/);
  assert.match(markup, /maxlength="200"/);
});
