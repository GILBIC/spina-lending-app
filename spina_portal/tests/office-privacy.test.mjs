import assert from 'node:assert/strict';
import { setImmediate } from 'node:timers/promises';
import test from 'node:test';
import { createOfficeCaseContext, bindOfficeWriteOwner } from '../assets/office-case-context.js';
import { mountOfficePrivacy } from '../assets/office-privacy.js';
import { Element, fire } from './helpers/dom.mjs';

const CLIENT = '11111111-1111-4111-8111-111111111111';
const CIF = '22222222-2222-4222-8222-222222222222';
const EVIDENCE = '33333333-3333-4333-8333-333333333333';
const ACK = '44444444-4444-4444-8444-444444444444';
const HASH = 'a'.repeat(64);
const PDF = new Blob(['%PDF-1.7\nSynthetic approved privacy document'], { type: 'application/pdf' });
const PDF_HASH = [...new Uint8Array(await crypto.subtle.digest('SHA-256', await PDF.arrayBuffer()))].map((value) => value.toString(16).padStart(2, '0')).join('');
const SOURCE = { version: 'synthetic-1', sha256: PDF_HASH };
const BASE = `/api/v1/management/clients/${CLIENT}`;
const PERMISSION = 'client_onboarding.requirement.review';
function context(optional = false) { return {
  client_id: CLIENT, cif_version_id: CIF, purpose: 'privacy_acknowledgment',
  application_id: null, application_version_id: null, subject_id: CIF,
  snapshot_sha256: HASH, issuable: true, issuance_ready: true, detail: 'Review both approved privacy documents.', acknowledgment: null,
  review_snapshot: { schema_version: 1, scope: 'privacy_acknowledgment', client_id: CLIENT, cif_version_id: CIF,
    cif_information: { full_name: 'Synthetic person', phone_number: '00000000000', present_address: 'Synthetic address', email: null },
    optional_service_communications: optional, notice: { ...SOURCE }, consent: { ...SOURCE } },
}; }
function acknowledgment(optional = false) { return { id: ACK, client_id: CLIENT, cif_version_id: CIF,
  optional_service_communications: optional, notice_version: SOURCE.version, consent_version: SOURCE.version,
  notice_sha256: PDF_HASH, consent_sha256: PDF_HASH, evidence_id: EVIDENCE,
  acknowledged_by_user_id: EVIDENCE, acknowledged_at: '2026-09-19T01:02:03Z' }; }
function captured() { return { evidence_id: EVIDENCE, evidence_reference: `office-evidence:${EVIDENCE}`,
  client_id: CLIENT, cif_version_id: CIF, purpose: 'privacy_acknowledgment', snapshot_sha256: HASH,
  application_id: null, application_version_id: null }; }
function harness(options = {}) {
  const h = { root: new Element(), clientId: CLIENT, cifVersionId: CIF, controller: new AbortController(), calls: [],
    session: { access_token: 'synthetic-private-token', user: { role: options.role ?? 'employee' }, permissions: options.permissions ?? [PERMISSION] }, response: options.response };
  h.signal = h.controller.signal; h.currentSession = h.session;
  h.api = { sessionStore: { load: () => h.currentSession }, async request(path, request = {}) {
    h.calls.push({ path, ...request });
    if (h.response) return h.response(path, request);
    if (path.includes('/privacy/context')) return context(path.includes('optional_service_communications=true'));
    if (path.includes('/privacy/documents/')) return PDF;
    if (path.endsWith('/privacy/acknowledgments')) return acknowledgment(request.body.optional_service_communications);
    return captured();
  } };
  if(options.coordinated){
    h.coordinator=createOfficeCaseContext({getSession:()=>h.currentSession});
    h.api=bindOfficeWriteOwner(h.api,{},h.coordinator);
  }
  h.dispose = mountOfficePrivacy(h);
  h.coordinator?.registerStage('cif',h.dispose);
  return h;
}
function field(h, name) { return h.root.querySelector(`[name="${name}"]`); }
function button(h, name) { return h.root.querySelector(`[data-privacy-${name}]`); }
function choose(h) { field(h, 'signedPrivacyScan').files = [PDF]; field(h, 'signedPrivacyScan').value = 'private-scan.pdf'; field(h, 'witnessedPrivacySignature').checked = true; }
function submit(h) { fire(h.root.querySelector('form'), 'submit'); }

for (const role of ['employee', 'management']) test(`${role}: exact privacy source and optional false survive one capture and one acknowledgment`, async () => {
  const h = harness({ role }); await setImmediate();
  assert.ok(h.calls[0].path.includes(`cif_version_id=${CIF}&optional_service_communications=false`));
  assert.equal(Boolean(field(h, 'optionalServiceCommunications').checked), false);
  choose(h); submit(h); submit(h); await setImmediate();
  assert.equal(h.calls.length, 3);
  const upload = h.calls[1], query = new URL(upload.path, 'https://office.example').searchParams;
  assert.equal(upload.rawBody, PDF); assert.equal(upload.headers['Content-Type'], 'application/pdf');
  assert.equal(query.get('expected_snapshot_sha256'), HASH);
  assert.equal(query.get('optional_service_communications'), 'false');
  assert.equal(query.get('witnessed_wet_signature'), 'true');
  assert.match(query.get('request_id'), /^[0-9a-f-]{36}$/);
  assert.deepEqual(h.calls[2].body, { cif_version_id: CIF, optional_service_communications: false, evidence_reference: `office-evidence:${EVIDENCE}` });
  assert.match(h.root.textContent, /acknowledgment recorded/);
  assert.equal(field(h, 'signedPrivacyScan').value, '');
  assert.equal(field(h, 'witnessedPrivacySignature').checked, false);
  h.dispose();
});

for (const options of [{ role: 'collector' }, { role: 'client' }, { permissions: [] }, { permissions: [`${PERMISSION}.extra`] }]) {
  test(`unauthorized privacy mount has no capture or reads: ${JSON.stringify(options)}`, async () => {
    const h = harness(options); await setImmediate();
    assert.equal(h.calls.length, 0); assert.equal(h.root.querySelector('form'), null); h.dispose();
  });
}

test('unavailable final templates never offer signing, capture or downloads', async () => {
  const h = harness({ response: () => ({ ...context(), issuable: false, issuance_ready: false, detail: 'Final privacy documents must be configured.' }) });
  await setImmediate(); choose(h); submit(h); await setImmediate();
  assert.equal(h.root.querySelector('form').hidden, true);
  assert.equal(h.root.querySelector('[data-privacy-document]'), null);
  assert.equal(h.calls.length, 1); assert.match(h.root.textContent, /must be configured/); h.dispose();
});

for (const mutate of [
  (value) => { value.review_snapshot.client_id = CIF; },
  (value) => { value.review_snapshot.cif_version_id = CLIENT; },
  (value) => { value.review_snapshot.optional_service_communications = 'false'; },
  (value) => { value.review_snapshot.consent.sha256 = 'bad'; },
  (value) => { value.review_snapshot.notice.version = null; },
]) test(`mismatched privacy snapshot stays closed: ${mutate}`, async () => {
  const value = context(); mutate(value); const h = harness({ response: () => value }); await setImmediate();
  assert.equal(h.root.querySelector('form').hidden, true); assert.equal(h.root.querySelector('[data-privacy-document]'), null);
  assert.match(h.root.textContent, /does not match|invalid/); h.dispose();
});

test('changing optional choice invalidates signature and requires a fresh exact context', async () => {
  const h = harness(); await setImmediate(); choose(h);
  field(h, 'optionalServiceCommunications').checked = true;
  fire(field(h, 'optionalServiceCommunications'), 'change');
  assert.equal(field(h, 'signedPrivacyScan').value, ''); assert.equal(field(h, 'witnessedPrivacySignature').checked, false);
  assert.equal(h.root.querySelector('form').hidden, true);
  submit(h); assert.equal(h.calls.length, 1);
  fire(button(h, 'refresh'), 'click'); await setImmediate(); choose(h); submit(h); await setImmediate();
  assert.equal(h.calls.at(-1).body.optional_service_communications, true); h.dispose();
});

test('uncertain upload remains locked after a generic fresh record load', async () => {
  const h = harness(); await setImmediate();
  h.response = (path) => { if (path.includes('/privacy/context')) return context(); throw Object.assign(new Error('Uncertain upload'), { code: 'network_uncertain' }); };
  choose(h); submit(h); await setImmediate(); submit(h); await setImmediate();
  assert.equal(h.calls.length, 2); assert.equal(h.root.querySelector('button[type="submit"]').disabled, true);
  assert.match(h.root.textContent, /before another attempt/);
  fire(button(h, 'refresh'), 'click'); await setImmediate();
  assert.equal(h.calls.length, 3); assert.equal(field(h, 'signedPrivacyScan').value, 'private-scan.pdf'); assert.equal(h.dispose.isUncertain(),true); h.dispose();
});

for (const mutate of [(saved) => { saved.optional_service_communications = true; }, (saved) => { saved.consent_sha256 = 'b'.repeat(64); }]) {
  test(`a mismatched successful acknowledgment requires reconciliation: ${mutate}`, async () => {
    const h = harness(); await setImmediate(); h.response = (path) => {
      if (!path.endsWith('/privacy/acknowledgments')) return captured(); const saved = acknowledgment(); mutate(saved); return saved;
    };
    choose(h); submit(h); await setImmediate();
    assert.doesNotMatch(h.root.textContent, /acknowledgment recorded/);
    assert.match(h.root.textContent, /before another attempt/); h.dispose();
  });
}

for (const close of ['abort', 'dispose', 'logout']) test(`${close} during upload suppresses late acknowledgment and clears file input`, async () => {
  const h = harness(); await setImmediate(); let resolve; h.response = () => new Promise((done) => { resolve = done; });
  choose(h); const scan = field(h, 'signedPrivacyScan'); submit(h);
  if (close === 'abort') h.controller.abort(); else if (close === 'dispose') h.dispose(); else h.currentSession = null;
  resolve(captured()); await setImmediate();
  assert.equal(h.calls.length, 2); assert.equal(h.root.innerHTML, ''); assert.equal(scan.value, '');
});

test('protected document download checks the displayed hash and only puts a blob URL on an anchor', async (t) => {
  async function downloadCompleted(button) {
    const deadline = Date.now() + 2000;
    while (button.disabled) {
      assert.ok(Date.now() < deadline, 'The protected download must complete its digest check');
      await setImmediate();
    }
  }
  const originalDocument = globalThis.document, originalCreate = URL.createObjectURL, originalRevoke = URL.revokeObjectURL;
  const anchors = [], blobs = [];
  globalThis.document = { createElement(tag) { assert.equal(tag, 'a'); const anchor = { click() { anchors.push(this); } }; return anchor; } };
  URL.createObjectURL = (blob) => { blobs.push(blob); return 'blob:synthetic-private-document'; }; URL.revokeObjectURL = () => {};
  t.after(() => { globalThis.document = originalDocument; URL.createObjectURL = originalCreate; URL.revokeObjectURL = originalRevoke; });
  const h = harness(); await setImmediate();
  const consent = h.root.querySelector('[data-privacy-document="consent"]');
  fire(consent, 'click'); await downloadCompleted(consent);
  assert.equal(anchors.length, 1); assert.equal(anchors[0].href, 'blob:synthetic-private-document'); assert.equal(anchors[0].download, 'privacy-consent.pdf');
  assert.equal(blobs[0], PDF); assert.ok(h.calls[1].path.includes(`expected_sha256=${PDF_HASH}`));
  assert.equal(h.calls[1].responseType, 'blob'); assert.doesNotMatch(anchors[0].href, /token|Bearer/);
  h.response = () => new Blob(['%PDF-1.7\nChanged'], { type: 'application/pdf' });
  const notice = h.root.querySelector('[data-privacy-document="notice"]');
  fire(notice, 'click'); await downloadCompleted(notice);
  assert.equal(anchors.length, 1); assert.match(h.root.textContent, /changed|match/); h.dispose();
});

test('access denial after capture begins clears sensitive state and prevents further requests', async () => {
  const h = harness(); await setImmediate(); const oldForm = h.root.querySelector('form');
  h.response = () => { throw Object.assign(new Error('No access'), { status: 403 }); }; choose(h); submit(h); await setImmediate();
  assert.equal(h.root.innerHTML, ''); fire(oldForm, 'submit'); await setImmediate(); assert.equal(h.calls.length, 2);
});

test('same-owner compatible token refresh retains native privacy File during upload and acknowledgment', async () => {
  let resolve; const hold=new Promise(r=>resolve=r);
  const h=harness(); await setImmediate();
  const nativeFile=new File(['signed'],'synthetic.pdf',{type:'application/pdf'});
  choose(h); field(h,'signedPrivacyScan').files=[nativeFile];
  h.response=(path,request)=>path.includes('/review-evidence?')?hold:path.endsWith('/privacy/acknowledgments')?acknowledgment():context();
  const original=field(h,'signedPrivacyScan'); submit(h); await setImmediate();
  h.currentSession={...h.session,access_token:'rotated-compatible-token'};
  resolve(captured()); await setImmediate();
  assert.equal(h.calls.filter(call=>call.method==='POST').length,2);
  assert.equal(h.calls[1].rawBody,nativeFile);
  assert.equal(field(h,'signedPrivacyScan'),original);
  assert.match(h.root.textContent,/acknowledgment recorded/); h.dispose();
});

test('uncertain privacy upload cannot be cleared by choice edit or generic context Reload', async () => {
  const h=harness(); await setImmediate(); choose(h);
  const original=field(h,'signedPrivacyScan'), nativeFile=new File(['signed'],'retained.pdf',{type:'application/pdf'});
  original.files=[nativeFile];
  h.response=(path,request)=>request.method?Promise.reject(Error('Lost upload')):context();
  submit(h); await setImmediate();
  field(h,'optionalServiceCommunications').checked=true;
  fire(field(h,'optionalServiceCommunications'),'change');
  fire(button(h,'refresh'),'click'); await setImmediate();
  assert.equal(h.dispose.isUncertain(),true);
  assert.equal(original.files[0],nativeFile);
  assert.equal(field(h,'optionalServiceCommunications').checked,false);
  assert.equal(h.calls.filter(call=>call.method==='POST').length,1); h.dispose();
});

test('privacy exact retry retains original File request snapshot choice and acknowledgment identity',async()=>{
 const h=harness();await setImmediate();choose(h);const file=new File(['original'],'original.pdf',{type:'application/pdf'});field(h,'signedPrivacyScan').files=[file];
 let lost=true;h.response=(path,request)=>path.includes('/review-evidence?')?(lost?Promise.reject(Error('Lost upload')):captured()):path.endsWith('/privacy/acknowledgments')?acknowledgment():context();
 submit(h);await setImmediate();const first=h.calls.find(c=>c.method==='POST');
 field(h,'signedPrivacyScan').files=[new File(['different'],'different.pdf',{type:'application/pdf'})];field(h,'optionalServiceCommunications').checked=true;fire(field(h,'optionalServiceCommunications'),'change');
 lost=false;fire(button(h,'retry'),'click');await setImmediate();
 const writes=h.calls.filter(c=>c.method==='POST');assert.equal(writes.length,3);assert.equal(writes[1].path,first.path);assert.equal(writes[1].rawBody,file);assert.equal(writes[2].body.optional_service_communications,false);assert.equal(h.dispose.isUncertain(),false);h.dispose();
});

const deferred = () => {
  let resolve, reject;
  const promise = new Promise((yes, no) => { resolve = yes; reject = no; });
  return {promise, resolve, reject};
};
for (const role of ['employee', 'management']) {
  for (const editTiming of ['before read', 'during read']) test(`${role}: recoverable privacy download failure retains unsubmitted draft edited ${editTiming}`, async t => {
    const h = harness({role, coordinated:true});
    t.after(() => h.coordinator.dispose());
    await setImmediate();
    const read = deferred(), scan = field(h, 'signedPrivacyScan');
    const file = new File(['signed'], 'retained.pdf', {type:'application/pdf'});
    const source = h.dispose.getContext();
    const edit = () => { choose(h); scan.files = [file]; fire(scan, 'change'); };
    h.response = () => read.promise;
    if (editTiming === 'before read') edit();
    fire(h.root.querySelector('[data-privacy-document="notice"]'), 'click');
    if (editTiming === 'during read') edit();
    read.reject(Object.assign(Error('Recoverable document outage'), {status:503}));
    await setImmediate();
    assert.equal(field(h, 'signedPrivacyScan'), scan);
    assert.equal(scan.value, 'private-scan.pdf');
    assert.equal(scan.files[0], file);
    assert.equal(field(h, 'witnessedPrivacySignature').checked, true);
    assert.equal(h.root.querySelector('form').hidden, false);
    assert.deepEqual(h.dispose.getContext(), source);
    assert.equal(h.dispose.isDirty(), true);
    assert.equal(h.calls.filter(call => call.method === 'POST').length, 0);
    assert.match(h.root.textContent, /Recoverable document outage/);
  });
  for (const failure of ['invalid media', 'hash mismatch', 'server source conflict']) test(`${role}: ${failure} blocks privacy signing without clearing draft until exact document recovery`, async t => {
    const h = harness({role, coordinated:true});
    t.after(() => h.coordinator.dispose());
    await setImmediate(); choose(h);
    const scan = field(h, 'signedPrivacyScan'), file = new File(['signed'], 'retained.pdf', {type:'application/pdf'});
    scan.files = [file];
    const notice = h.root.querySelector('[data-privacy-document="notice"]');
    h.response = () => {
      if (failure === 'server source conflict') throw Object.assign(Error('Privacy document changed'), {status:409});
      return failure === 'invalid media' ? new Blob(['invalid'], {type:'text/plain'}) : new Blob(['changed'], {type:'application/pdf'});
    };
    fire(notice, 'click');
    while (notice.disabled) await setImmediate();
    assert.equal(scan.value, 'private-scan.pdf');
    assert.equal(scan.files[0], file);
    assert.equal(field(h, 'witnessedPrivacySignature').checked, true);
    assert.equal(h.root.querySelector('form').hidden, false);
    assert.equal(h.root.querySelector('button[type="submit"]').disabled, true);
    assert.match(h.root.textContent, /signing.*blocked/i);
    submit(h); fire(button(h, 'refresh'), 'click'); await setImmediate();
    assert.equal(h.calls.length, 2, 'blocked draft cannot write or be erased by a generic load');
    const originalDocument = globalThis.document;
    globalThis.document = {createElement:() => ({click(){}})};
    t.after(() => { globalThis.document = originalDocument; });
    h.response = () => PDF;
    fire(notice, 'click');
    while (notice.disabled) await setImmediate();
    assert.equal(field(h, 'signedPrivacyScan'), scan);
    assert.equal(scan.files[0], file);
    assert.equal(field(h, 'witnessedPrivacySignature').checked, true);
    assert.equal(h.root.querySelector('button[type="submit"]').disabled, false);
    h.response = path => path.includes('/review-evidence?') ? captured() : acknowledgment();
    submit(h); await setImmediate();
    assert.equal(h.calls.filter(call => call.method === 'POST').length, 2);
    assert.equal(h.calls.find(call => call.method === 'POST').rawBody, file);
    assert.match(h.root.textContent, /acknowledgment recorded/);
  });
}
async function downloadingPrivacyWrite(phase) {
  const h = harness({coordinated:true});
  await setImmediate();
  h.documentRead = deferred(); h.upload = deferred(); h.ack = deferred();
  h.response = path => path.includes('/privacy/documents/') ? h.documentRead.promise
    : path.includes('/review-evidence?') ? h.upload.promise : h.ack.promise;
  fire(h.root.querySelector('[data-privacy-document="notice"]'), 'click');
  choose(h);
  h.scan = field(h, 'signedPrivacyScan');
  h.file = new File(['signed'], 'original-privacy.pdf', {type:'application/pdf'});
  h.scan.files = [h.file];
  submit(h); await setImmediate();
  if (phase === 'acknowledgment') { h.upload.resolve(captured()); await setImmediate(); }
  assert.equal(h.coordinator.isWritePending(), true);
  return h;
}
for (const phase of ['upload','acknowledgment']) {
  for (const readFailure of ['network','invalid document']) {
    test(`in-flight document ${readFailure} during privacy ${phase} preserves original command and exact recovery`, async t => {
      const h = await downloadingPrivacyWrite(phase); t.after(() => h.coordinator.dispose());
      const first = h.calls.find(call => call.method === 'POST');
      if (readFailure === 'network') h.documentRead.reject(Error('Document unavailable'));
      else h.documentRead.resolve(new Blob(['wrong media'], {type:'text/plain'}));
      await setImmediate();
      assert.equal(field(h, 'signedPrivacyScan'), h.scan);
      assert.equal(h.scan.value, 'private-scan.pdf'); assert.equal(h.scan.files[0], h.file);
      assert.equal(field(h, 'witnessedPrivacySignature').checked, true);
      assert.equal(await h.coordinator.requestTransition({kind:'close'}), false);
      if (phase === 'upload') { h.upload.resolve(captured()); await setImmediate(); }
      assert.equal(h.calls.filter(call => call.method === 'POST').length, 2);
      h.ack.reject(Error('Acknowledgment response lost')); await setImmediate();
      assert.equal(h.dispose.isUncertain(), true); assert.equal(h.coordinator.isWritePending(), true);
      assert.equal(h.scan.files[0], h.file); assert.ok(button(h, 'retry'));
      const originalAck = h.calls.find(call => call.path.endsWith('/privacy/acknowledgments'));
      h.response = () => acknowledgment(); fire(button(h, 'retry'), 'click'); await setImmediate();
      const writes = h.calls.filter(call => call.method === 'POST');
      assert.equal(writes.length, 3); assert.equal(writes[0].rawBody, h.file);
      assert.equal(writes[0].path, first.path); assert.deepEqual(writes[2].body, originalAck.body);
      assert.equal(writes[2].path, originalAck.path); assert.equal(h.coordinator.isWritePending(), false);
      assert.equal(h.scan.value, ''); assert.match(h.root.textContent, /acknowledgment recorded/);
    });
  }
  test(`late document network failure preserves uncertain privacy ${phase} and its recovery control`, async t => {
    const h = await downloadingPrivacyWrite(phase); t.after(() => h.coordinator.dispose());
    (phase === 'upload' ? h.upload : h.ack).reject(Error('Write response lost')); await setImmediate();
    assert.equal(h.dispose.isUncertain(), true);
    const retry = button(h, 'retry'); h.documentRead.reject(Error('Late document failure')); await setImmediate();
    assert.equal(button(h, 'retry'), retry); assert.equal(h.scan.value, 'private-scan.pdf');
    assert.equal(h.scan.files[0], h.file); assert.equal(h.coordinator.isWritePending(), true);
    assert.equal(await h.coordinator.requestTransition({kind:'new-intake'}), false);
  });
  for (const status of [401,403]) test(`in-flight document ${status} during privacy ${phase} tears down all private owners`, async t => {
    const h = await downloadingPrivacyWrite(phase); t.after(() => h.coordinator.dispose());
    let siblingDisposed = false;
    h.coordinator.registerStage('application', {dispose(){siblingDisposed=true;}});
    h.documentRead.reject(Object.assign(Error('Access unavailable'), {status})); await setImmediate();
    assert.equal(siblingDisposed, true); assert.equal(h.root.innerHTML, ''); assert.equal(h.scan.value, '');
    const count = h.calls.length;
    h.upload.resolve(captured()); h.ack.resolve(acknowledgment()); await setImmediate();
    assert.equal(h.calls.length, count); assert.equal(h.root.innerHTML, '');
  });
}

for (const phase of ['upload','acknowledgment']) test(`in-flight document success during privacy ${phase} keeps the command until acknowledgment`, async t => {
  const h = await downloadingPrivacyWrite(phase); t.after(() => h.coordinator.dispose());
  h.documentRead.resolve(PDF); await setImmediate();
  assert.equal(h.scan.value, 'private-scan.pdf'); assert.equal(h.scan.files[0], h.file);
  assert.equal(h.coordinator.isWritePending(), true);
  assert.equal(h.root.querySelector('[data-privacy-document="notice"]').disabled, true);
  h.upload.resolve(captured()); await setImmediate(); h.ack.resolve(acknowledgment()); await setImmediate();
  assert.equal(h.calls.filter(call => call.method === 'POST').length, 2);
  assert.equal(h.coordinator.isWritePending(), false); assert.equal(h.scan.value, '');
  assert.match(h.root.textContent, /acknowledgment recorded/);
});
test('document failure followed by privacy upload rejection retains the exact raw upload retry', async t => {
  const h = await downloadingPrivacyWrite('upload'); t.after(() => h.coordinator.dispose());
  const original = h.calls.find(call => call.method === 'POST');
  h.documentRead.reject(Error('Document unavailable')); await setImmediate();
  h.upload.reject(Error('Upload response lost')); await setImmediate();
  assert.equal(h.dispose.isUncertain(), true); assert.equal(h.coordinator.isWritePending(), true);
  assert.equal(h.scan.files[0], h.file); assert.equal(h.scan.value, 'private-scan.pdf');
  h.response = path => path.includes('/review-evidence?') ? captured() : acknowledgment();
  fire(button(h, 'retry'), 'click'); await setImmediate();
  const writes = h.calls.filter(call => call.method === 'POST');
  assert.equal(writes.length, 3); assert.equal(writes[1].path, original.path);
  assert.equal(writes[1].rawBody, original.rawBody); assert.equal(writes[1].rawBody, h.file);
  assert.equal(h.coordinator.isWritePending(), false); assert.match(h.root.textContent, /acknowledgment recorded/);
});
