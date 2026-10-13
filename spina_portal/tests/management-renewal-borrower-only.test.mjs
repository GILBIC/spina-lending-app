import assert from 'node:assert/strict';
import test from 'node:test';
import { Element, fire } from './helpers/dom.mjs';
import { id, row, tick, setup, fill, confirm, approved } from './helpers/management-renewal-fixture.mjs';

test('new terms offer one borrower and no supporting-party creation controls', async () => {
  const {root, handle} = await setup({async request() { return {requests:[row()]}; }});
  const form = root.querySelector('[data-renewal-terms]');
  assert.equal(form.querySelectorAll('[data-signer]').length, 1);
  assert.equal(form.querySelector('[data-add-signer]'), null);
  assert.equal(form.querySelector('[data-remove-signer]'), null);
  assert.equal(form.querySelector('select[name="party_role"]'), null);
  assert.equal(form.querySelector('[name="party_role"]').value, 'borrower');
  assert.match(form.textContent, /new.*borrower.only/i);
  assert.match(form.textContent, /borrower.*identity evidence/i);
  handle.dispose();
});

test('pending saved supporting or signed signer evidence remains readable and can be rejected without replacement', async () => {
  for (const savedSigner of [
    {party_role:'guarantor', full_name:'Historical Guarantor', signed:false},
    {party_role:'surety', full_name:'Historical Surety', signed:true},
    {party_role:'solidary_co_maker', full_name:'Historical Co-maker', signed:false},
    {party_role:'borrower', full_name:'Already Signed Borrower', signed:true},
  ]) {
    const item = row(1, {signers:[{signer_id:id(401), user_id:id(301), government_id_verified:true, selfie_verified:true, ...savedSigner}]});
    const writes = [];
    const {root, handle, mod} = await setup({async request(path, options) {
      if (options?.method === 'POST') {
        writes.push(options.body);
        return {request:{...item, status:'rejected', review_note:options.body.review_note, reviewed_at:'2026-10-10T02:00:00Z'}};
      }
      return {requests:[item]};
    }});
    const form = root.querySelector('[data-renewal-terms]');
    assert.ok(form, 'Historical pending records retain a rejection form');
    assert.equal(form.querySelector('[name="decision"]').value, 'rejected');
    assert.ok(!form.querySelector('option[value="approved"]'));
    assert.ok(!form.querySelector('[data-signer]'));
    assert.ok(!form.querySelector('[name="approved_principal"]'));
    assert.ok(!form.querySelector('[name="office_processing_required"]'));
    assert.ok(root.textContent.includes(savedSigner.full_name));
    assert.ok(root.textContent.includes(savedSigner.party_role));
    assert.ok(root.textContent.includes(id(301)));
    assert.match(root.textContent, /existing signer records.*review required/i);
    assert.match(mod.renewalActionBlocker(item, 'terms'), /review required/i);
    assert.equal(mod.renewalActionBlocker(item, 'terms', 'rejected'), '');
    fire(form, 'submit');
    await tick();
    assert.ok(!root.querySelector('[data-renewal-confirm-action]'), 'Rejection still requires a reason');
    assert.equal(writes.length, 0);
    form.querySelector('[name="review_note"]').value = 'Historical request withdrawn';
    await confirm(root, form);
    assert.deepEqual(writes, [{decision:'rejected', review_note:'Historical request withdrawn'}]);
    assert.match(root.textContent, /Terms saved/);
    assert.ok(root.textContent.includes(savedSigner.full_name));
    assert.ok(root.textContent.includes(savedSigner.party_role));
    assert.ok(root.textContent.includes(id(301)));
    assert.ok(root.textContent.includes('signature ' + (savedSigner.signed ? 'signed' : 'pending')));
    handle.dispose();
  }
});

test('historical rejection cannot be changed into approval by injected fields or a stale confirmation', async () => {
  const draft = await setup({async request() { return {requests:[row()]}; }});
  const approvalFields = draft.root.querySelector('[data-renewal-terms]').innerHTML;
  draft.handle.dispose();
  for (const savedSigner of [{party_role:'guarantor', signed:false}, {party_role:'borrower', signed:true}]) {
    for (const afterReview of [false, true]) {
      let reads = 0, posts = 0;
      const item = row(1, {signers:[{signer_id:id(401), user_id:id(302), full_name:'Saved Historical Signer', ...savedSigner}]});
      const {root, handle} = await setup({async request(path, options) {
        if (options?.method === 'POST') posts++;
        else reads++;
        return {requests:[item]};
      }});
      const form = root.querySelector('[data-renewal-terms]');
      let staleConfirm;
      if (afterReview) {
        form.querySelector('[name="review_note"]').value = 'Reject this historical request';
        fire(form, 'submit');
        await tick();
        root.querySelector('[data-renewal-confirm-ack]').checked = true;
        staleConfirm = root.querySelector('[data-renewal-confirm-action]');
      }
      form.innerHTML = approvalFields;
      fill(root, 0, {decision:'approved'});
      fire(afterReview ? staleConfirm : form, afterReview ? 'click' : 'submit');
      await tick();
      assert.equal(posts, 0);
      assert.equal(reads, afterReview ? 3 : 1);
      assert.ok(!root.querySelector('[data-renewal-confirm-action]'));
      assert.ok(root.textContent.includes('Saved Historical Signer'));
      assert.equal(handle.isWritePending(), false);
      handle.dispose();
    }
  }
});

test('new remote and office terms reject tampered supporting roles and duplicate borrower additions locally', async () => {
  for (const office of [false, true]) for (const role of ['guarantor', 'surety', 'solidary_co_maker', 'borrower', '']) {
    let reads = 0, posts = 0;
    const {root, handle} = await setup({async request(path, options) {
      if (options?.method === 'POST') posts++;
      else reads++;
      return {requests:[row()]};
    }});
    const form = fill(root, 0, {office_processing_required:office});
    if (role === 'borrower') {
      const extra = new Element();
      extra.innerHTML = form.querySelector('[data-signer]').outerHTML;
      const signer = extra.querySelector('[data-signer]');
      signer.querySelector('[name="full_name"]').value = 'Injected Borrower';
      signer.querySelector('[name="user_id"]').value = id(302);
      signer.querySelector('[name="identity_reviewed"]').checked = true;
      form.querySelector('[data-signers]').appendChild(signer);
    } else form.querySelector('[name="party_role"]').value = role;
    fire(form, 'submit');
    await tick();
    assert.equal(posts, 0);
    assert.equal(reads, 1, `${office ? 'office' : 'remote'} ${role || 'empty'} is rejected before preflight`);
    assert.ok(!root.querySelector('[data-renewal-confirm-action]'));
    assert.match(root.textContent, /one borrower|borrower.only/i);
    handle.dispose();
  }
});

test('borrower-only terms preserve the exact remote and office request contracts and unchecked evidence', async () => {
  for (const office of [false, true]) {
    const writes = [];
    const {root, handle} = await setup({async request(path, options) {
      if (options?.method === 'POST') {
        writes.push({path, body:options.body, financial:options.financial});
        return {request:approved(row(), options.body)};
      }
      return {requests:[row()]};
    }});
    const form = fill(root, 0, {office_processing_required:office});
    if (office) form.querySelector('[name="user_id"]').value = '';
    await confirm(root, form);
    assert.deepEqual(writes, [{
      path:`/api/v1/management/renewals/${id(1)}/terms`, financial:true,
      body:{decision:'approved', approved_principal:'10000.00', review_note:'Approved after review', override_reason:'', office_processing_required:office,
        signers:[{party_role:'borrower', full_name:'Verified Borrower', user_id:office ? null : id(301), government_id_verified:false, selfie_verified:false}]},
    }]);
    assert.match(root.textContent, /Terms saved/);
    assert.match(root.textContent, /signature pending/);
    assert.equal(handle.isWritePending(), false);
    handle.dispose();
  }
});

test('changing borrower role after review cannot submit stale confirmed terms', async () => {
  let posts = 0;
  const {root, handle} = await setup({async request(path, options) {
    if (options?.method === 'POST') posts++;
    return {requests:[row()]};
  }});
  const form = fill(root);
  fire(form, 'submit');
  await tick();
  root.querySelector('[data-renewal-confirm-ack]').checked = true;
  form.querySelector('[name="party_role"]').value = 'surety';
  fire(root.querySelector('[data-renewal-confirm-action]'), 'click');
  await tick();
  assert.equal(posts, 0);
  assert.ok(!root.querySelector('[data-renewal-confirm-action]'));
  assert.equal(handle.isWritePending(), false);
  handle.dispose();
});

test('newly discovered saved signers invalidate an already reviewed borrower-only draft', async () => {
  let posts = 0, changed = false;
  const {root, handle} = await setup({async request(path, options) {
    if (options?.method === 'POST') posts++;
    return {requests:[row(1, {signers:changed ? [{signer_id:id(401), party_role:'guarantor', full_name:'Saved Historical Guarantor', user_id:id(302), signed:true}] : []})]};
  }});
  const form = fill(root);
  fire(form, 'submit');
  await tick();
  root.querySelector('[data-renewal-confirm-ack]').checked = true;
  changed = true;
  fire(root.querySelector('[data-renewal-confirm-action]'), 'click');
  await tick();
  assert.equal(posts, 0);
  assert.match(root.textContent, /changed/);
  assert.equal(handle.isWritePending(), false);
  handle.dispose();
});

test('server review-required response preserves a failed save and reports existing signer protection', async () => {
  let posts = 0;
  const {root, handle} = await setup({async request(path, options) {
    if (options?.method === 'POST') {
      posts++;
      throw Object.assign(new Error('synthetic protected record'), {status:409, code:'renewal_existing_signers_review_required'});
    }
    return {requests:[row()]};
  }});
  await confirm(root, fill(root));
  assert.equal(posts, 1);
  assert.match(root.textContent, /Existing signer records: review required/);
  assert.doesNotMatch(root.textContent, /Terms saved/);
  assert.equal(handle.isWritePending(), false);
  handle.dispose();
});
