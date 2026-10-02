import assert from 'node:assert/strict';
import test from 'node:test';
import {setImmediate} from 'node:timers/promises';
import {mountEmployeeAt} from './helpers/employee-activation.mjs';
const mountEmployeeWorkspace=context=>mountEmployeeAt(context,['employee-cash-disbursement']);
import {Element} from './helpers/dom.mjs';

test('Employee workspace exposes Cash Disbursement only with its exact permission', async () => {
  for (const permitted of [false, true]) {
    const root = new Element();
    root.dataset = {};
    const controller = new AbortController();
    let navigation;
    const context = {root, signal: controller.signal,
      session: {user: {id: 'employee', role: 'employee', roles: ['employee']},
        permissions: [permitted ? 'cash_disbursement.prepare' : 'cash_disbursement.prepare.extra']},
      api: {request: async () => ({contract_version: 1, actor: {},
        capabilities: {can_prepare_cash_disbursement: permitted}, accounting_preparations: []})},
      setNavigation(items) { navigation = items; }};
    try {
      await mountEmployeeWorkspace(context);
      await setImmediate();
      assert.equal(Boolean(root.querySelector('[data-cash-disbursement]')), permitted);
      assert.equal(navigation.some(item => item.id === 'employee-cash-disbursement'), permitted);
      if (permitted) {
        assert.equal(typeof context.cashDisbursementCleanup, 'function');
        const oldRoot = root.querySelector('[data-cash-disbursement]');
        await mountEmployeeWorkspace(context);
        assert.equal(oldRoot.innerHTML, '', 'remount erases the old private preparation surface');
      }
    } finally { controller.abort(); }
  }
});
