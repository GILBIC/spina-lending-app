import assert from 'node:assert/strict';
import { existsSync } from 'node:fs';
import { setImmediate } from 'node:timers/promises';
import test from 'node:test';

import { ApiError } from '../assets/api.js';
import { Element, fire } from './helpers/dom.mjs';

const moduleUrl = new URL('../assets/office-cif-correction.js', import.meta.url);
const CLIENT_ID = '11111111-1111-4111-8111-111111111111';
const CIF_ID = '22222222-2222-4222-8222-222222222222';
const OTHER_ID = '33333333-3333-4333-8333-333333333333';
const PERMISSION = 'client_onboarding.requirement.review';
const GET = `/api/v1/management/clients/${CLIENT_ID}/cif/review-summary?include_correction_availability=true`;
const PATCH = `/api/v1/management/clients/${CLIENT_ID}/cif/draft-information`;

async function loadMount() {
  assert.equal(existsSync(moduleUrl), true, 'Office CIF correction is not implemented');
  const { mountOfficeCifCorrection } = await import(moduleUrl.href);
  assert.equal(typeof mountOfficeCifCorrection, 'function');
  return mountOfficeCifCorrection;
}

function review(changes = {}) {
  return {
    client_id: CLIENT_ID, cif_version_id: CIF_ID, version_number: 7,
    status: 'draft', review_scope: 'cif_information_only', can_correct_information: true,
    full_name: '  Synthetic   Applicant  ', phone_number: '0917-123-4567',
    email: null, present_address: '  Synthetic   Original Address  ',
    ...changes,
  };
}

function deferred() {
  let resolve;
  let reject;
  const promise = new Promise((yes, no) => { resolve = yes; reject = no; });
  return { promise, resolve, reject };
}

function harness({ role = 'employee', permissions = [PERMISSION] } = {}) {
  const h = {
    root: new Element(), calls: [], callbacks: [], current: review(),
    controller: new AbortController(), getResult: null, patchResult: null,
  };
  h.options = {
    root: h.root, clientId: CLIENT_ID, signal: h.controller.signal,
    session: { user: { role, roles: [role] }, permissions },
    api: {
      async request(path, options = {}) {
        h.calls.push({ path, options });
        if ((options.method ?? 'GET') === 'GET') return h.getResult ? h.getResult() : h.current;
        return h.patchResult ? h.patchResult(options.body) : h.current;
      },
    },
    onEditing: () => h.callbacks.push('editing'),
    onClosed: () => h.callbacks.push('closed'),
    onSaved: () => h.callbacks.push('saved'),
    onAccessDenied: () => h.callbacks.push('denied'),
  };
  return h;
}

function button(h, text) {
  return h.root.querySelectorAll('button').find((element) => element.textContent.trim() === text);
}

function field(h, name) {
  return h.root.querySelector(`[name="${name}"]`);
}

async function open(h) {
  fire(button(h, 'Correct information'), 'click');
  await setImmediate();
}

function submit(h) {
  const event = fire(h.root.querySelector('form'), 'submit');
  assert.equal(event.defaultPrevented, true);
}

function edit(h, changes = {}) {
  const values = {
    full_name: 'Corrected Applicant', phone_number: '09170000009',
    email: '', present_address: 'Corrected office address', reason: 'Applicant corrected the record',
    ...changes,
  };
  for (const [name, value] of Object.entries(values)) field(h, name).value = value;
  return values;
}

for (const role of ['employee', ' Management ']) {
  test(`${role}: correction loads on demand and saves the exact original nullable snapshot`, async () => {
    const mount = await loadMount();
    const h = harness({ role });
    const dispose = mount(h.options);
    assert.equal(typeof dispose, 'function');
    assert.equal(h.calls.length, 0);
    assert.equal(h.root.querySelector('form'), null);
    assert.ok(button(h, 'Correct information'));
    await open(h);
    assert.deepEqual(h.calls.map(({ path }) => path), [GET]);
    assert.deepEqual(h.callbacks, ['editing']);
    assert.equal(field(h, 'full_name').value, h.current.full_name);
    assert.equal(field(h, 'email').value, '');
    const values = edit(h, { reason: '  Applicant corrected the record  ' });
    const oldFields = h.root.querySelectorAll('input').concat(h.root.querySelectorAll('textarea'));
    submit(h);
    await setImmediate();

    assert.equal(h.calls.length, 2);
    assert.equal(h.calls[1].path, PATCH);
    assert.equal(h.calls[1].options.method, 'PATCH');
    assert.deepEqual(h.calls[1].options.body, {
      cif_version_id: CIF_ID,
      expected_information: {
        full_name: h.current.full_name, phone_number: h.current.phone_number,
        email: null, present_address: h.current.present_address,
      },
      corrected_information: {
        full_name: values.full_name, phone_number: values.phone_number,
        email: null, present_address: values.present_address,
      },
      reason: values.reason,
    });
    assert.deepEqual(h.callbacks, ['editing', 'saved']);
    assert.ok(oldFields.every((element) => element.value === ''));
    dispose();
    assert.equal(h.root.innerHTML, '');
  });
}

for (const [role, permissions] of [
  ['collector', [PERMISSION]], ['client', [PERMISSION]],
  ['employee', []], ['management', [`${PERMISSION}.extra`]],
]) {
  test(`${role}/${permissions.join(',')}: insufficient authority exposes no correction`, async () => {
    const mount = await loadMount();
    const h = harness({ role, permissions });
    mount(h.options);
    assert.equal(h.root.querySelector('button'), null);
    assert.equal(h.calls.length, 0);
    assert.deepEqual(h.callbacks, []);
  });
}

test('an invalid Client and an already aborted mount never fetch or expose a correction action', async () => {
  const mount = await loadMount();
  for (const reason of ['client', 'aborted']) {
    const h = harness();
    if (reason === 'client') h.options.clientId = '../private';
    else h.controller.abort();
    mount(h.options);
    assert.equal(h.root.querySelector('button'), null);
    assert.equal(h.calls.length, 0);
  }
});

test('unavailable correction remains read-only and can close without saving', async () => {
  const mount = await loadMount();
  const h = harness();
  h.current.can_correct_information = false;
  mount(h.options);
  await open(h);
  assert.equal(h.root.querySelector('form'), null);
  assert.match(h.root.textContent, /read.only|unavailable/i);
  assert.match(h.root.textContent, /Synthetic.*Applicant/);
  fire(button(h, 'Cancel'), 'click');
  assert.deepEqual(h.callbacks, ['editing', 'closed']);
  assert.equal(h.calls.length, 1);
  assert.doesNotMatch(h.root.textContent, /Synthetic.*Applicant/);
});

for (const [reason, changes] of [
  ['wrong Client', { client_id: OTHER_ID }],
  ['wrong scope', { review_scope: 'loan_application_information_only' }],
  ['missing CIF', { cif_version_id: null }],
  ['invalid version', { version_number: 0 }],
  ['missing email', { email: undefined }],
  ['wrong address type', { present_address: 45 }],
  ['nonliteral permission', { can_correct_information: 'true' }],
]) {
  test(`opening with ${reason} never exposes editable information`, async () => {
    const mount = await loadMount();
    const h = harness();
    h.current = review(changes);
    mount(h.options);
    await open(h);
    assert.equal(h.root.querySelector('form'), null);
    assert.ok(h.root.querySelector('[role="alert"]'));
    assert.doesNotMatch(h.root.textContent, /Synthetic.*Applicant/);
    assert.equal(h.calls.length, 1);
  });
}

test('untrusted information and server errors stay escaped text', async () => {
  const mount = await loadMount();
  const h = harness();
  h.current = review({ full_name: '<img src=x onerror=alert(1)>', can_correct_information: false });
  mount(h.options);
  await open(h);
  assert.doesNotMatch(h.root.innerHTML, /<img\b/i);
  assert.match(h.root.innerHTML, /&lt;img/);
});

test('field limits are accessible and invalid edits never send a PATCH', async () => {
  const mount = await loadMount();
  const h = harness();
  mount(h.options);
  await open(h);
  for (const [name, minimum, maximum] of [
    ['full_name', 2, 200], ['phone_number', 7, 40],
    ['present_address', 5, 500], ['reason', 3, 500],
  ]) {
    assert.equal(field(h, name).getAttribute('minlength'), String(minimum));
    assert.equal(field(h, name).getAttribute('maxlength'), String(maximum));
  }
  assert.equal(field(h, 'email').getAttribute('maxlength'), '320');
  for (const invalid of [
    { full_name: ' ' }, { full_name: 'x'.repeat(201) }, { phone_number: 'abcdefgh' },
    { phone_number: '9'.repeat(41) }, { email: 'x'.repeat(321) },
    { present_address: '    ' }, { present_address: 'x'.repeat(501) },
    { reason: '  ' }, { reason: 'x'.repeat(501) },
  ]) {
    edit(h, invalid);
    submit(h);
    await setImmediate();
    assert.equal(h.calls.length, 1);
    assert.ok(h.root.querySelector('[role="alert"]'));
  }
});

test('a pending save sends only one PATCH despite repeated submit events', async () => {
  const mount = await loadMount();
  const h = harness();
  const pending = deferred();
  h.patchResult = () => pending.promise;
  mount(h.options);
  await open(h);
  edit(h);
  submit(h);
  submit(h);
  assert.equal(button(h, 'Save correction').disabled, true);
  assert.equal(h.calls.length, 2);
  pending.resolve(h.current);
  await setImmediate();
  assert.deepEqual(h.callbacks, ['editing', 'saved']);
});

for (const status of [400, 422]) {
  test(`${status} preserves all edited values and permits an intentional corrected save`, async () => {
    const mount = await loadMount();
    const h = harness();
    h.patchResult = () => { throw new ApiError('<img src=x> Invalid information', { status }); };
    mount(h.options);
    await open(h);
    const values = edit(h, { email: ' MiXeD@Example.TEST ' });
    submit(h);
    await setImmediate();
    for (const [name, value] of Object.entries(values)) assert.equal(field(h, name).value, value);
    assert.equal(button(h, 'Save correction').disabled, false);
    assert.doesNotMatch(h.root.innerHTML, /<img\b/i);
    assert.match(h.root.innerHTML, /&lt;img/);
    assert.deepEqual(h.callbacks, ['editing']);
    h.patchResult = null;
    submit(h);
    await setImmediate();
    assert.equal(h.calls.length, 3);
    assert.deepEqual(h.callbacks, ['editing', 'saved']);
  });
}

for (const outcome of ['conflict', 'network_uncertain', 'server', 'malformed', 'wrong-version']) {
  test(`${outcome} blocks blind retry and requires a fresh review before another save`, async () => {
    const mount = await loadMount();
    const h = harness();
    h.patchResult = () => {
      if (outcome === 'malformed') return { saved: true };
      if (outcome === 'wrong-version') return review({ cif_version_id: OTHER_ID, version_number: 8 });
      throw new ApiError('Synthetic save failure', {
        status: outcome === 'conflict' ? 409 : outcome === 'server' ? 503 : 0,
        code: outcome,
      });
    };
    mount(h.options);
    await open(h);
    edit(h);
    submit(h);
    await setImmediate();
    assert.equal(button(h, 'Save correction').disabled, true);
    assert.ok(button(h, 'Reload current CIF'));
    submit(h);
    assert.equal(h.calls.length, 2);
    assert.deepEqual(h.callbacks, ['editing']);
    h.current = review({ cif_version_id: OTHER_ID, version_number: 8, full_name: 'Fresh server snapshot' });
    fire(button(h, 'Reload current CIF'), 'click');
    await setImmediate();
    assert.equal(h.calls[2].path, GET);
    assert.equal(field(h, 'full_name').value, 'Fresh server snapshot');
    h.patchResult = null;
    edit(h);
    submit(h);
    await setImmediate();
    assert.equal(h.calls[3].options.body.cif_version_id, OTHER_ID);
    assert.equal(h.calls[3].options.body.expected_information.full_name, 'Fresh server snapshot');
    assert.equal(h.callbacks.filter((name) => name === 'saved').length, 1);
  });
}

for (const stage of ['GET', 'PATCH']) {
  for (const status of [401, 403]) {
    test(`${status} during ${stage} clears values and permanently blocks this correction mount`, async () => {
      const mount = await loadMount();
      const h = harness();
      const denied = () => { throw new ApiError('Office access denied', { status }); };
      if (stage === 'GET') h.getResult = denied;
      else h.patchResult = denied;
      mount(h.options);
      await open(h);
      let oldForm;
      let oldFields = [];
      if (stage === 'PATCH') {
        edit(h);
        oldForm = h.root.querySelector('form');
        oldFields = h.root.querySelectorAll('input').concat(h.root.querySelectorAll('textarea'));
        submit(h);
        await setImmediate();
      }
      assert.ok(oldFields.every((element) => element.value === ''));
      assert.equal(h.root.querySelector('button'), null);
      assert.equal(h.root.querySelector('form'), null);
      assert.deepEqual(h.callbacks, ['editing', 'denied']);
      const count = h.calls.length;
      if (oldForm) fire(oldForm, 'submit');
      await setImmediate();
      assert.equal(h.calls.length, count);
    });
  }

  for (const action of ['Cancel', 'dispose', 'abort', 'remount']) {
    test(`${action} invalidates pending ${stage} and suppresses late data and callbacks`, async () => {
      const mount = await loadMount();
      const h = harness();
      const pending = deferred();
      if (stage === 'GET') h.getResult = () => pending.promise;
      else h.patchResult = () => pending.promise;
      const dispose = mount(h.options);
      fire(button(h, 'Correct information'), 'click');
      await setImmediate();
      let oldForm;
      let oldFields = [];
      if (stage === 'PATCH') {
        edit(h);
        oldForm = h.root.querySelector('form');
        oldFields = h.root.querySelectorAll('input').concat(h.root.querySelectorAll('textarea'));
        submit(h);
      }
      if (action === 'Cancel') fire(button(h, 'Cancel'), 'click');
      else if (action === 'dispose') dispose();
      else if (action === 'abort') h.controller.abort();
      else mount(h.options);
      const cleared = h.root.innerHTML;
      const callbacks = [...h.callbacks];
      const count = h.calls.length;
      assert.ok(oldFields.every((element) => element.value === ''));
      if (oldForm) fire(oldForm, 'submit');
      pending.resolve(h.current);
      await setImmediate();
      assert.equal(h.root.innerHTML, cleared);
      assert.deepEqual(h.callbacks, callbacks);
      assert.equal(h.calls.length, count);
      assert.equal(h.callbacks.includes('saved'), false);
      assert.equal(h.callbacks.includes('closed'), action === 'Cancel');
    });
  }
}
