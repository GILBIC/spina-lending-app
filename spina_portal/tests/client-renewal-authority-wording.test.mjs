import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';

const clientRoleSource = await readFile(
  new URL('../assets/roles/client.js', import.meta.url),
  'utf8',
);

test('Client Web renewal wording keeps assigned Collector recommendation before Management decision', () => {
  assert.match(
    clientRoleSource,
    /permanently assigned Collector must recommend/i,
  );
  assert.match(
    clientRoleSource,
    /before Management reviews and decides/i,
  );
});

test('Client Web renewal wording keeps every other required signer on their own SPINA account', () => {
  assert.match(
    clientRoleSource,
    /other required signer must use their own SPINA account/i,
  );
});
