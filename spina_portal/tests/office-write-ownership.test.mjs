import assert from 'node:assert/strict';
import test from 'node:test';
import {setImmediate} from 'node:timers/promises';
import {Element,fire} from './helpers/dom.mjs';
import {mountEmployeeWorkspace} from '../assets/employee-workspace.js';
import {mountManagementWorkspace} from '../assets/roles/management.js';
const CLIENT='11111111-1111-4111-8111-111111111111',APP='22222222-2222-4222-8222-222222222222',VERSION='33333333-3333-4333-8333-333333333333',LOAN='44444444-4444-4444-8444-444444444444';
const permissions=['client_onboarding.requirement.review','lending.first_loan.approve','lending.first_loan.release'];
function loan(){return {loan_id:LOAN,client_id:CLIENT,packet_id:VERSION,packet_hash:'a'.repeat(64),status:'approved_pending_release',loan_number:'Synthetic loan',packet:{loan_id:LOAN,client_id:CLIENT,packet_id:VERSION,application:{application_id:APP,id:VERSION},borrower:{full_name:'Synthetic applicant'},terms:{principal:'1000.00',schedule_basis_date:'2026-10-04'},net_cash:'1000.00',schedule:[{installment_number:1,due_date:'2026-10-05',contractual_amount:'1000.00',principal_component:'1000.00',interest_component:'0.00'}]},authorization:null,document:{id:CLIENT,content_sha256:'b'.repeat(64)}};}
async function harness(role){
 const h={root:new Element(),calls:[],controller:new AbortController(),record:loan(),fail:true};h.root.dataset={};
 h.context={root:h.root,session:{user:{id:CLIENT,role,roles:[role]},permissions},signal:h.controller.signal,setNavigation(){},activateNavigation(){},registerWorkspaceHandle:handle=>h.handle=handle,sessionStore:{deviceId:()=>CLIENT,nextDeviceSequence:()=>1},api:{async request(path,options={}){
  h.calls.push({path,options});
  if(options.method==='POST'){
   if(h.pendingWrite)return h.pendingWrite;
   if(h.fail)throw Object.assign(Error('Synthetic lost upload'),{status:0,code:'network_uncertain'});
   h.record.evidence={borrower_contract_signed:{evidence_reference:`office-evidence:${APP}`}};
   return {packet_hash:h.record.packet_hash,purpose:'borrower_contract_signed',evidence_reference:`office-evidence:${APP}`};
  }
  if(path.endsWith('/cif-client'))return {client_id:CLIENT,application_reference:'INTAKE-ORIGINAL'};
  if(path.endsWith('/review-summary'))return {client_id:CLIENT,application_id:APP,application_version_id:VERSION,application_reference:'APP-ORIGINAL',version_number:1,missing_fields:[],information:{request:{},repayment:{}}};
  if(path.endsWith('/first-loans/context'))return {products:[],templates:[]};
  if(path.includes('/first-loans/by-application/'))return {loans:[h.record]};
  if(path==='/api/v1/account')return {profile:{full_name:'Synthetic operator'},devices:[]};
  if(path.includes('activity-notifications'))return [];
  return {};
 }}};
 await (role==='management'?mountManagementWorkspace:mountEmployeeWorkspace)(h.context);
 h.activate=async where=>{if(role==='management')assert.equal(await h.handle.activate(where==='office'?'management-clients-loans':'management-account',where==='office'?'management-office':'management-profile'),true);else h.handle.activate(where==='office'?'employee-first-loan':'employee-account');await setImmediate();};
 await h.activate('office');
 if(role==='management'){fire(h.root.querySelector('[data-office-step-target="first-loan"]'),'click');await setImmediate();}
 h.release=h.root.querySelector('[data-office-first-loan]');h.release.querySelector('[name="intakeReference"]').value='INTAKE-ORIGINAL';h.release.querySelector('[name="applicationReference"]').value='APP-ORIGINAL';fire(h.release.querySelector('form'),'submit');await setImmediate();
 return h;
}
for(const role of ['management','employee']){
 test(`${role} shell Refresh reads selected original references and retains dirty File controls`,async t=>{
  const h=await harness(role);t.after(()=>h.controller.abort());const input=h.release.querySelector('[name="applicationReference"]');input.value='EDITED-CANDIDATE';fire(input,'input');
  await h.handle.refreshVisible();await setImmediate();assert.equal(input.value,'APP-ORIGINAL');assert.equal(h.calls.filter(c=>c.path.includes('EDITED-CANDIDATE')).length,0);
  const field=h.release.querySelector('[name="contractFile"]'),file=new File(['signed'],'synthetic.pdf',{type:'application/pdf'});field.files=[file];fire(field,'change');const reads=h.calls.length;
  await h.handle.refreshVisible();assert.equal(h.calls.length,reads);assert.equal(h.release.querySelector('[name="contractFile"]'),field);assert.equal(field.files[0],file);
 });
 test(`${role} delayed Office financial dispatch captures its owner across navigation and resolves Treasury only after exact retry`,async t=>{
  const h=await harness(role);t.after(()=>h.controller.abort());const field=h.release.querySelector('[name="contractFile"]'),file=new File(['signed'],'synthetic.pdf',{type:'application/pdf'});let resolveBytes;file.arrayBuffer=()=>new Promise(resolve=>resolveBytes=resolve);field.files=[file];h.release.querySelector('[name="witnessedSignature"]').checked=true;
  fire(h.release.querySelector('[data-contract]'),'submit');await setImmediate();assert.equal(h.handle.isWritePending(),true);
  await h.activate('account');resolveBytes(new TextEncoder().encode('signed').buffer);await setImmediate();
  assert.equal(h.context.api.canStartTreasuryWrite(),false);assert.equal(field.files[0],file);
  await h.activate('office');fire(h.release.querySelector('[data-action="reload"]'),'click');await setImmediate();assert.equal(h.context.api.canStartTreasuryWrite(),false);
  const first=h.calls.find(c=>c.options.method==='POST');h.fail=false;fire(h.release.querySelector('[data-retry-office-action]'),'click');await setImmediate();
  const writes=h.calls.filter(c=>c.options.method==='POST');assert.equal(writes.length,2);assert.equal(writes[1].path,first.path);assert.equal(writes[1].options.body,first.options.body);assert.equal(h.context.api.canStartTreasuryWrite(),true);assert.equal(h.handle.isWritePending(),false);
 });
}

async function showExistingRelease(h) {
  const candidate = h.release.querySelector('[name="applicationReference"]');
  candidate.value = 'EDITED-CANDIDATE'; fire(candidate, 'input');
  fire(h.root.querySelector('[data-office-step-target="intake"]'), 'click'); await setImmediate();
  fire(h.root.querySelector('[data-office-step-target="first-loan"]'), 'click'); await setImmediate();
  const showExisting = h.root.querySelector('[data-office-show-existing]');
  assert.ok(showExisting);
  fire(showExisting, 'click'); await setImmediate();
  assert.equal(candidate.value, 'EDITED-CANDIDATE');
  assert.equal(h.root.querySelector('[data-office-step="first-loan"]').getAttribute('hidden'), null);
  assert.equal(h.root.querySelector('[data-office-step-target="first-loan"]').getAttribute('aria-current'), 'step');
  return candidate;
}

test('Management Show existing case routes shell Refresh to visible original verified release owner', async t => {
  const h = await harness('management'); t.after(() => h.controller.abort());
  const candidate = await showExistingRelease(h), before = h.calls.length;
  assert.equal(await h.handle.refreshVisible(), true); await setImmediate();
  assert.deepEqual(h.calls.slice(before).map(call => call.path), [
    `/api/v1/management/onboarding/applicants/by-reference/INTAKE-ORIGINAL/cif-client`,
    `/api/v1/management/clients/${CLIENT}/loan-applications/by-reference/APP-ORIGINAL/review-summary`,
    '/api/v1/management/first-loans/context',
    `/api/v1/management/first-loans/by-application/${APP}`,
  ]);
  assert.equal(candidate.value, 'APP-ORIGINAL');
  assert.match(h.root.querySelector('[data-office-context-banner]').textContent, /Approval & release/);
  assert.equal(h.calls.filter(call => call.options.method === 'POST').length, 0);
});

test('Management denied Show existing case cannot display or refresh its retained private owner', async t => {
  const h = await harness('management'); t.after(() => h.controller.abort());
  const candidate = h.release.querySelector('[name="applicationReference"]');
  candidate.value = 'EDITED-CANDIDATE'; fire(candidate, 'input');
  fire(h.root.querySelector('[data-office-step-target="intake"]'), 'click'); await setImmediate();
  fire(h.root.querySelector('[data-office-step-target="first-loan"]'), 'click'); await setImmediate();
  const control = h.root.querySelector('[data-office-show-existing]'), before = h.calls.length;
  h.context.session.permissions = [];
  fire(control, 'click'); await setImmediate();
  assert.match(h.root.querySelector('[data-office-context-banner]').textContent, /Office access is unavailable/);
  assert.equal(h.release.querySelector('[name="contractFile"]'), null);
  await h.handle.refreshVisible(); await setImmediate();
  assert.equal(h.calls.length, before);
});

for (const work of ['dirty', 'pending', 'uncertain']) test(`Management Show existing case retains ${work} release File and global locks`, async t => {
  const h = await harness('management'); t.after(() => h.controller.abort());
  const scan = h.release.querySelector('[name="contractFile"]');
  const file = new File(['signed'], 'retained.pdf', {type:'application/pdf'});
  scan.files = [file]; fire(scan, 'change');
  let rejectWrite;
  if (work !== 'dirty') {
    if (work === 'pending') h.pendingWrite = new Promise((resolve, reject) => { rejectWrite = reject; });
    h.release.querySelector('[name="witnessedSignature"]').checked = true;
    fire(h.release.querySelector('[data-contract]'), 'submit'); await setImmediate();
    assert.equal(h.handle.isWritePending(), true);
    assert.equal(h.calls.filter(call => call.options.method === 'POST').length, 1);
  }
  const candidate = await showExistingRelease(h), before = h.calls.length;
  await h.handle.refreshVisible(); await setImmediate();
  assert.equal(h.calls.length, before);
  assert.equal(h.release.querySelector('[name="contractFile"]'), scan);
  assert.equal(scan.files[0], file); assert.equal(candidate.value, 'EDITED-CANDIDATE');
  assert.match(h.root.querySelector('[data-office-context-banner]').textContent, /Approval & release/);
  assert.equal(h.handle.isWritePending(), work !== 'dirty');
  if (work !== 'dirty') assert.equal(h.context.api.canStartTreasuryWrite(), false);
  if (rejectWrite) { rejectWrite(Error('Synthetic lost dispatch')); await setImmediate(); }
});

for(const role of ['management','employee']){
 test(`${role} Office authority loss clears private data and explains access loss at its boundary`,async t=>{
  const h=await harness(role);t.after(()=>h.controller.abort());
  h.context.session.permissions=[];
  await h.handle.refreshVisible();await setImmediate();
  const boundary=h.root.querySelector(role==='management'?'[data-office-context-banner]':'[data-office-case-strip]');
  assert.match(boundary?.textContent??'',/Office access is unavailable.*Sign in again/);
  assert.equal(h.release.querySelector('[name="contractFile"]'),null);
 });
}

for(const role of ['management','employee'])test(`${role} ordinary workspace disposal does not announce an access failure`,async()=>{
 const h=await harness(role);h.controller.abort();await setImmediate();
 assert.doesNotMatch(h.root.textContent,/Office access is unavailable|Sign in again/);
});
