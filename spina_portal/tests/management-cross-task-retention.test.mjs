import assert from 'node:assert/strict';
import test from 'node:test';
import {setImmediate} from 'node:timers/promises';
import {mountManagementWorkspace} from '../assets/roles/management.js';
import {Element, fire} from './helpers/dom.mjs';
import {id, row, approved, fill, confirm} from './helpers/management-renewal-fixture.mjs';

const ACTOR = id(900), CLIENT = id(901), CIF = id(902), APPLICATION = id(903), VERSION = id(904);
const COLLECTOR = id(910), REMITTANCE = id(911), NOTICE = id(912);
const INTAKE = 'SYNTHETIC-INTAKE', APPLICATION_REFERENCE = 'SYNTHETIC-APPLICATION';
const GROUPS = {
  portfolio: ['management-clients-loans', 'management-loans'],
  office: ['management-clients-loans', 'management-office'],
  support: ['management-operations', 'management-support'],
  terms: ['management-clients-loans', 'management-renewals'],
  invitation: ['management-operations', 'management-staff'],
  remittance: ['management-collections', 'management-remittances'],
};
const supportRecord = number => ({
  request_id: id(920 + number), client_id: id(930 + number), status: 'open',
  subject: `Synthetic question ${number}`, message: 'Synthetic request only.',
  management_response: null, responded_at: null,
});
const applicationReview = () => ({
  client_id: CLIENT, cif_version_id: CIF, application_id: APPLICATION, application_version_id: VERSION,
  application_reference: APPLICATION_REFERENCE, cif_version_number: 1, version_number: 1,
  requested_loan_type_name: null, recorded_at: '2026-10-03T01:00:00Z',
  review_scope: 'loan_application_information_only', missing_fields: [],
  information: {
    request: {requested_loan_type_id: id(905), purpose: 'Synthetic loan', requested_amount: '1000.00',
      requested_payment_arrangement: 'Weekly', requested_term: 'Ten weeks', preferred_first_payment_date: null},
    repayment: {repayment_source: 'Employment', source_details: 'Synthetic details', monthly_gross_income: '10000',
      monthly_net_income: '9000', has_existing_obligations: false, obligations: []},
  },
});
const pendingNotice = () => ({
  notification_id: NOTICE, remittance_id: REMITTANCE, recipient_user_id: ACTOR, sender_user_id: COLLECTOR,
  remittance_number: 'SYNTHETIC-REMITTANCE', collector_name: 'Synthetic Collector',
  collection_date: '2026-10-03', total_amount: '115.00', transaction_count: 2, client_count: 1,
  status: 'pending', is_pending: true,
});
const remittanceRecord = () => ({
  remittance_id: REMITTANCE, remittance_number: 'SYNTHETIC-REMITTANCE',
  recipient_user_id: ACTOR, recipient_name: 'Synthetic Manager', collector_user_id: COLLECTOR,
  collector_name: 'Synthetic Collector', collection_date: '2026-10-03', status: 'submitted',
  transaction_count: 2, payment_count: 2, unable_to_pay_count: 0, covered_payment_count: 0,
  client_count: 1, total_amount: '115.00', note: 'Synthetic cash handover',
  submitted_at: '2026-10-03T01:00:00Z', received_at: null,
  items: ['100.00', '50.00'].map((amount, index) => ({
    transaction_id: id(940 + index), client_id: CLIENT, loan_id: id(950 + index),
    client_name: 'Synthetic Borrower', loan_type: 'Regular', collection_date: '2026-10-03',
    entry_type: 'payment', amount, receipt_number: `SYNTHETIC-RECEIPT-${index}`,
    accepted_at: '2026-10-03T00:30:00Z', note: 'Synthetic payment', covered_dates: [],
  })),
  refund_due_release_count: 1, refund_due_release_total: '35.00',
  refund_due_releases: [{release_id: id(960), approval_id: id(961), adjustment_id: id(962),
    client_id: CLIENT, loan_id: id(950), client_name: 'Synthetic Borrower', loan_type: 'Regular',
    amount: '35.00', released_at: '2026-10-03T00:45:00Z', evidence_reference: 'SYNTHETIC-REFUND',
    evidence_digest: 'a'.repeat(64), cash_effect: 'outflow'}],
});

async function workspace(t, {action, failReadback = false}) {
  const root = new Element(), abort = new AbortController(), calls = [], unexpected = [];
  const support = [supportRecord(1), supportRecord(2)];
  let renewal = row(), notice = pendingNotice(), remittance = remittanceRecord(), saved = false;
  const api = {async request(path, options = {}) {
    calls.push({path, options});
    const write = options.method === 'POST';
    if (write) {
      if (path === `/api/v1/management/support/${support[0].request_id}/review`) {
        support[0] = {...support[0], status: options.body.action, management_response: options.body.response,
          responded_at: '2026-10-03T02:00:00Z'};
        saved = true;
        return {request: {...support[0]}};
      }
      if (path === `/api/v1/management/renewals/${renewal.request_id}/terms`) {
        renewal = approved(renewal, options.body); saved = true;
        return {request: structuredClone(renewal)};
      }
      if (path === '/api/v1/management/accounts/invite') {
        saved = true;
        return {invitation_sent: true, account: {id: id(970), username: options.body.username,
          email: options.body.email, roles: [options.body.role]}};
      }
      if (path === `/api/v1/notifications/${NOTICE}/accept-remittance`) {
        saved = true; notice = {...notice, status: 'accepted', is_pending: false};
        remittance = {...remittance, status: 'received', received_at: '2026-10-03T02:00:00Z'};
        return {notification: {...notice}, remittance_id: REMITTANCE, remittance_number: remittance.remittance_number,
          status: 'received', received_at: remittance.received_at, custody_user_id: ACTOR,
          custody_message: 'Synthetic confirmed custody.'};
      }
    } else {
      if (failReadback && saved && (
        (['support', 'terms'].includes(action) && path === '/api/v1/management/dashboard-overview') ||
        (action === 'invitation' && path === '/api/v1/management/accounts?staff_only=true') ||
        (action === 'remittance' && path === '/api/v1/notifications')
      )) throw Object.assign(new Error('Synthetic follow-up read unavailable'), {status: 503});
      if (path === '/api/v1/account') return {profile: {full_name: 'Synthetic Manager'}, devices: []};
      if (path === '/api/v1/management/dashboard-overview') return {metrics: []};
      if (path.startsWith('/api/v1/management/loans?')) return {summary: {
        active_client_count: 1, active_loan_count: 1, active_remaining_total: '1000.00', overdue_active_count: 0,
      }, loans: []};
      if (path.startsWith('/api/v1/management/support?')) return {requests: structuredClone(support)};
      if (path.startsWith('/api/v1/management/renewal-workflow?')) return {requests: [structuredClone(renewal)]};
      if (path === '/api/v1/management/accounts?staff_only=true') return {accounts: []};
      if (path === '/api/v1/notifications') return [{...notice}];
      if (path === '/api/v1/remittances') return [structuredClone(remittance)];
      if (path === `/api/v1/treasury/collector-surplus/remittances/${REMITTANCE}/receiving-contract`) {
        // #485's original receiving path is available only when the later server contract explicitly allows it.
        return {collector_surplus_contract_version: 1, remittance_id: REMITTANCE, recipient_user_id: ACTOR,
          count_required: false, legacy_receive_allowed: true};
      }
      if (path === `/api/v1/management/onboarding/applicants/by-reference/${INTAKE}/cif-client`) {
        return {client_id: CLIENT, application_reference: INTAKE};
      }
      if (path === `/api/v1/management/clients/${CLIENT}/loan-applications/by-reference/${APPLICATION_REFERENCE}/review-summary`) {
        return applicationReview();
      }
      if (path.startsWith(`/api/v1/management/clients/${CLIENT}/review-evidence/context?`)) {
        return {client_id: CLIENT, cif_version_id: CIF, application_id: APPLICATION,
          application_version_id: VERSION, purpose: 'application_review', snapshot_sha256: 'a'.repeat(64), issuance_ready: true};
      }
    }
    unexpected.push({path, method: options.method || 'GET'});
    throw new Error('Unexpected synthetic contract request');
  }};
  const session = {user: {id: ACTOR, role: 'management', roles: ['management'], status: 'active'},
    device_id: 'synthetic-device', permissions: ['management.dashboard.view', 'client_onboarding.requirement.review',
      'support.manage', 'renewal.manage', 'account.manage', 'remittance.view', 'remittance.receive']};
  const handle = await mountManagementWorkspace({root, api, session, getSession: () => session,
    signal: abort.signal, setNavigation() {}, activateNavigation() {},
    sessionStore: {deviceId: () => session.device_id, nextDeviceSequence: () => 1}});
  t.after(() => {abort.abort(); assert.deepEqual(unexpected, [], 'All fixture reads/writes use actual supported contracts');});
  const activate = async key => {assert.equal(await handle.activate(...GROUPS[key]), true); await setImmediate();};
  return {root, calls, handle, activate};
}

async function retainDrafts(h) {
  await h.activate('portfolio');
  const search = h.root.querySelector('#management-loan-search').querySelector('[name="query"]');
  search.value = 'Keep this borrower search';
  await h.activate('office');
  const workflow = h.root.querySelector('[data-office-workflow]');
  const intake = h.root.querySelector('[data-office-onboarding]').querySelector('[name="applicationReference"]');
  intake.value = INTAKE; fire(intake, 'input');
  fire(workflow.querySelector('[data-office-step-target="application"]'), 'click');await setImmediate();
  const application = h.root.querySelector('[data-office-application-review]');
  // Each stage verifies its candidate; editable intake text is not a case handoff.
  application.querySelector('[name="intakeReference"]').value = INTAKE;
  application.querySelector('[name="applicationReference"]').value = APPLICATION_REFERENCE;
  fire(application.querySelector('form'), 'submit'); await setImmediate();
  assert.ok(application.querySelector('[data-prepare-application-confirmation]'), 'Open the actual authorized application review');
  // Return to intake through actual navigation; only the verified case can refill its cleared candidate lookup.
  fire(workflow.querySelector('[data-office-step-target="intake"]'),'click');await setImmediate();assert.equal(intake.value,INTAKE);
  fire(workflow.querySelector('[data-office-step-target="application"]'),'click');await setImmediate();assert.equal(application.querySelector('[name="applicationReference"]').value,APPLICATION_REFERENCE);
  fire(application.querySelector('[data-prepare-application-confirmation]'), 'click'); await setImmediate();
  const scan = application.querySelector('[name="signedScan"]');
  assert.ok(scan, 'Use the actual Office evidence input, not an injected stand-in file field');
  const file = new File(['%PDF-1.7\nSynthetic unsigned test attachment'], 'synthetic-review.pdf', {type: 'application/pdf'});
  // The shared DOM fixture supplies FileList semantics; file identity and the real production input are asserted below.
  scan.files = [file]; scan.value = 'synthetic-review.pdf'; fire(scan, 'change');
  await h.activate('support');
  const otherResponse = h.root.querySelectorAll('[data-support-form]')[1].querySelector('[name="response"]');
  otherResponse.value = 'Keep this other unfinished support response';
  return {search, intake, application, scan, file, otherResponse};
}

function assertRetained(h, d) {
  assert.equal(h.root.querySelector('#management-loan-search').querySelector('[name="query"]'), d.search);
  assert.equal(d.search.value, 'Keep this borrower search');
  assert.equal(h.root.querySelector('[data-office-onboarding]').querySelector('[name="applicationReference"]'), d.intake);
  assert.equal(d.intake.value, INTAKE);
  assert.equal(h.root.querySelector('[data-office-application-review]'), d.application);
  assert.equal(d.application.querySelector('[name="signedScan"]'), d.scan, 'The file input node must not be rebuilt');
  assert.equal(d.scan.files[0], d.file, 'The exact selected File must survive unrelated work');
  assert.equal(d.scan.value, 'synthetic-review.pdf');
  const response = h.root.querySelectorAll('[data-support-form]').find(form => form.querySelector('[name="response"]') === d.otherResponse);
  assert.ok(response, 'The other Support editor must remain mounted');
  assert.equal(d.otherResponse.value, 'Keep this other unfinished support response');
  assert.equal(h.calls.some(({options}) => options.rawBody), false, 'The retained evidence is never uploaded by unrelated actions');
}

async function save(h, action) {
  await h.activate(action);
  if (action === 'support') {
    const form = h.root.querySelector('[data-support-form]');
    form.querySelector('[name="response"]').value = 'Verified synthetic answer';
    fire(form, 'submit'); await setImmediate();
    assert.match(h.root.querySelector('[data-support-result]').textContent, /Response saved/);
  } else if (action === 'terms') {
    await confirm(h.root, fill(h.root));
    assert.match(h.root.querySelector('[data-renewal-result]').textContent, /Terms saved/);
  } else if (action === 'invitation') {
    const form = h.root.querySelector('#management-staff-invite-form');
    for (const [name, value] of Object.entries({fullName: 'Synthetic Staff', username: 'synthetic.staff',
      email: 'synthetic.staff@example.test', role: 'employee'})) form.querySelector(`[name="${name}"]`).value = value;
    fire(form, 'submit'); await setImmediate();
    assert.match(h.root.querySelector('[data-staff-invite-feedback]').textContent, /Invitation sent/);
  } else {
    fire(h.root.querySelector('[data-review-notification]'), 'click'); await setImmediate();
    const form = h.root.querySelector('[data-remittance-accept-form]');
    assert.ok(form, 'Current receiving compatibility and exact pending evidence must permit this review');
    for (const name of ['reviewedPayments', 'physicallyReceived']) {
      const control = form.querySelector(`[name="${name}"]`); control.checked = true; fire(control, 'change');
    }
    fire(form, 'submit'); await setImmediate();
    assert.match(h.root.querySelector('#management-remittances').textContent, /Remittance accepted/);
  }
  assert.equal(h.calls.filter(({options}) => options.method === 'POST').length, 1, 'Exactly the selected action writes once');
}

for (const action of ['support', 'terms', 'invitation', 'remittance']) {
  for (const failReadback of [false, true]) {
    test(`Management ${action} save retains search, Office references, another response and selected File${failReadback ? ' when its follow-up read fails' : ''}`, async t => {
      const h = await workspace(t, {action, failReadback});
      const drafts = await retainDrafts(h);
      await save(h, action);
      assertRetained(h, drafts);
      assert.equal(h.handle.isWritePending(), false, 'A verified save is not relabeled as an uncertain mutation');
      if (failReadback) {
        const task = h.root.querySelector(`#${GROUPS[action][1]}`);
        assert.match(task.textContent, /refresh failed|could not refresh/i, 'The saved action must disclose its failed follow-up read locally');
      }
      await h.activate('portfolio'); await h.activate('office'); await h.activate('support');
      assertRetained(h, drafts);
      assert.equal(h.calls.filter(({options}) => options.method === 'POST').length, 1, 'Navigation cannot repeat a saved action');
    });
  }
}
