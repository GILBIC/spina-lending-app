import assert from 'node:assert/strict';
import test from 'node:test';
import * as roles from '../assets/roles.js';

test('combined staff choose only their server-issued Employee and Collector workspaces', () => {
  assert.equal(typeof roles.sessionWorkspaceRoles, 'function');
  assert.deepEqual(roles.sessionWorkspaceRoles({user:{role:'Collector', roles:['Collector', 'Employee', 'collector'], permissions:['employee.review', 'client_onboarding.requirement.review']}}), ['collector', 'employee']);
});

test('capabilities never invent Management membership or accept unknown workspaces', () => {
  assert.equal(typeof roles.sessionWorkspaceRoles, 'function');
  assert.deepEqual(roles.sessionWorkspaceRoles({user:{role:'Employee', roles:['owner', 'unknown'], permissions:['account.manage']}}), ['employee']);
  assert.deepEqual(roles.sessionWorkspaceRoles({}), []);
});
