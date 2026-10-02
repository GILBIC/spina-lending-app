import assert from 'node:assert/strict';
import test from 'node:test';

import { mountManagementWorkspace } from '../assets/roles/management.js';
import { Element, fire } from './helpers/dom.mjs';

class ManagementElement extends Element {
  querySelectorAll(selector) {
    if (/^\[[^\]]+\]\[[^\]]+\]$/.test(selector)) return [];
    return super.querySelectorAll(selector);
  }
}

function response(path) {
  if (path === '/api/v1/account') return { profile: { full_name: 'Management User' }, devices: [] };
  if (path === '/api/v1/management/dashboard-overview') return { metrics: [] };
  if (path.startsWith('/api/v1/management/loans')) return { summary: {}, loans: [] };
  if (path.startsWith('/api/v1/management/loan-operations')) return { summary: {}, entries: [], audits: [], notice: '' };
  if (path.startsWith('/api/v1/activity-notifications')) return [];
  return {};
}

test('Management office workflow shows one stage at a time and carries references forward safely', async () => {
  const root = new ManagementElement();
  root.dataset = {};
  const calls = [];
  const controller = new AbortController();
  try {
    const tasks = await mountManagementWorkspace({
      root,
      api: { async request(path, options = {}) { calls.push({ path, options }); return response(path); } },
      session: {
        user: { role: 'management', roles: ['management'] },
        permissions: ['client_onboarding.requirement.review'],
      },
      signal: controller.signal,
      setNavigation() {},
      activateNavigation() {},
      sessionStore: {
        deviceId: () => 'synthetic-device',
        nextDeviceSequence: () => 1,
      },
    });

    await tasks.activate('management-clients-loans', 'management-office');
    const hub = root.querySelector('#management-clients-loans');
    const workflow = hub.querySelector('[data-office-workflow]');
    assert.ok(workflow);

    const buttons = workflow.querySelectorAll('[data-office-step-target]');
    assert.deepEqual(
      buttons.map((button) => button.attributes['data-office-step-target']),
      ['intake', 'cif', 'application', 'first-loan'],
    );

    const panels = workflow.querySelectorAll('[data-office-step]');
    assert.equal(panels.length, 4);
    assert.equal(panels[0].getAttribute('hidden'), null);
    for (const panel of panels.slice(1)) assert.equal(panel.getAttribute('hidden'), '');

    const intakeInput = panels[0].querySelector('[name="applicationReference"]');
    intakeInput.value = 'INTAKE-123';

    const baselineCalls = calls.length;
    fire(buttons[1], 'click');
    assert.equal(calls.length, baselineCalls, 'step navigation does not invent API authority');
    assert.equal(panels[0].getAttribute('hidden'), '');
    assert.equal(panels[1].getAttribute('hidden'), null);
    assert.equal(panels[1].querySelector('[name="applicationReference"]').value, 'INTAKE-123');

    fire(buttons[2], 'click');
    assert.equal(panels[2].querySelector('[name="intakeReference"]').value, 'INTAKE-123');
    panels[2].querySelector('[name="applicationReference"]').value = 'APP-456';

    fire(buttons[3], 'click');
    assert.equal(panels[3].querySelector('[name="intakeReference"]').value, 'INTAKE-123');
    assert.equal(panels[3].querySelector('[name="applicationReference"]').value, 'APP-456');
    assert.equal(buttons[3].getAttribute('aria-current'), 'step');
    assert.equal(buttons[0].getAttribute('aria-current'), null);

    fire(buttons[0], 'click');
    intakeInput.value = 'INTAKE-OTHER';
    const firstLoanIntake=panels[3].querySelector('[name="intakeReference"]');
    fire(buttons[1], 'click');
    assert.equal(buttons[0].getAttribute('aria-current'), 'step', 'A conflicting case must not silently open the old CIF');
    assert.match(workflow.querySelector('[data-office-case-feedback]').textContent,/different case/i);
    assert.equal(firstLoanIntake.value,'INTAKE-123');
    assert.equal(calls.length,baselineCalls);
    fire(workflow.querySelector('[data-office-show-existing]'),'click');
    assert.equal(buttons[1].getAttribute('aria-current'),'step');
    assert.equal(panels[1].querySelector('[name="applicationReference"]').value,'INTAKE-123');

    fire(buttons[2],'click');
    firstLoanIntake.value='';
    panels[3].querySelector('[name="applicationReference"]').value='OTHER-APPLICATION';
    fire(buttons[3],'click');
    assert.equal(firstLoanIntake.value,'','A conflicting pair must be checked before either reference is filled');
    assert.equal(buttons[2].getAttribute('aria-current'),'step');
    assert.equal(panels[3].querySelector('[name="applicationReference"]').value,'OTHER-APPLICATION');
    const staleConflict=workflow.querySelector('[data-office-show-existing]');
    fire(buttons[0],'click');
    fire(staleConflict,'click');
    assert.equal(buttons[0].getAttribute('aria-current'),'step','A superseded conflict control cannot change the current stage');
  } finally {
    controller.abort();
  }
});
