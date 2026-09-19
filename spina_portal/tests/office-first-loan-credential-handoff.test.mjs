import assert from 'node:assert/strict';
import test from 'node:test';
import { setImmediate } from 'node:timers/promises';
import { mountOfficeFirstLoan } from '../assets/office-first-loan.js';
import { Element, fire } from './helpers/dom.mjs';

const CLIENT='11111111-1111-4111-8111-111111111111';
const APP='22222222-2222-4222-8222-222222222222';
const VERSION='33333333-3333-4333-8333-333333333333';
const LOAN='44444444-4444-4444-8444-444444444444';
const button=(root,text)=>root.querySelectorAll('button').find(item=>item.textContent===text);
async function opened({role='employee',permissions=['lending.first_loan.release','client.credential.manage'],setup=true,deniedStatus=null,pending=false}={}) {
 const root=new Element(),controller=new AbortController();
 const review={client_id:CLIENT,application_id:APP,application_version_id:VERSION,application_reference:'Synthetic-Loan',version_number:1,information:{},missing_fields:[]};
 const loan={loan_id:LOAN,client_id:CLIENT,packet_id:VERSION,packet_hash:'a'.repeat(64),loan_number:'SYNTHETIC',status:'released',authorization:null,document:null,
  packet:{loan_id:LOAN,client_id:CLIENT,packet_id:VERSION,application:{application_id:APP},terms:{principal:'100.00'},net_cash:'100.00',borrower:{full_name:'Synthetic borrower'},schedule:[{installment_number:1,due_date:'2026-09-20',contractual_amount:'100.00',principal_component:'100.00',interest_component:'0.00'}]}};
 const api={async request(path,options={}) {
  if(path.endsWith('/documents'))throw Object.assign(new Error('Access denied'),{status:deniedStatus});
  if(options.method==='POST')return {status:'completed',credentials:{username:'synthetic-user',password:'Synthetic-Test-Only'}};
  if(path.endsWith('/cif-client'))return {client_id:CLIENT,application_reference:'Synthetic-Intake'};
  if(path.endsWith('/review-summary'))return review;
  if(path.endsWith('/context'))return {products:[{id:APP,name:'Synthetic product',calculation_mode:'fixed_total',daily_interest_per_1000:'0.00'}],templates:[]};
  if(path.includes('/by-application/'))return {loans:[loan]};
  throw new Error('Unexpected request '+path);
 }};
 if(deniedStatus)loan.document={id:VERSION,content_sha256:'b'.repeat(64)};
 if(pending){loan.status='approved_pending_release';loan.document={id:VERSION,content_sha256:'b'.repeat(64)};}
 mountOfficeFirstLoan({root,api,session:{user:{role},permissions:['client_onboarding.requirement.review',...permissions]},signal:controller.signal});
 root.querySelector('[name="intakeReference"]').value='Synthetic-Intake';
 root.querySelector('[name="applicationReference"]').value='Synthetic-Loan';
 fire(root.querySelector('form'),'submit');await setImmediate();
 if(setup){fire(button(root,'Retry account setup'),'click');await setImmediate();}
 return {root,controller,api,loan};
}

test('one-time password is readonly and explicitly revealed then hidden without another request',async()=>{
 const {root,controller}=await opened();const input=root.querySelector('[name="issuedPassword"]');
 assert.equal(input.getAttribute('readonly'),'');
 assert.equal(input.getAttribute('type'),'password');
 const toggle=button(root,'Show password');assert.ok(toggle,'Office credential handoff needs an explicit reveal control');
 fire(toggle,'click');assert.equal(input.getAttribute('type'),'text');assert.equal(toggle.textContent,'Hide password');
 fire(toggle,'click');assert.equal(input.getAttribute('type'),'password');assert.equal(toggle.textContent,'Show password');
 controller.abort();assert.equal(input.value,'');assert.equal(root.innerHTML,'');
 fire(toggle,'click');assert.equal(input.getAttribute('type'),'password');assert.equal(input.value,'');
});

test('Clear erases a revealed one-time password and removes its detached reveal listener',async()=>{
 const {root}=await opened();const input=root.querySelector('[name="issuedPassword"]'),toggle=button(root,'Show password');
 assert.ok(toggle);fire(toggle,'click');fire(button(root,'Clear'),'click');
 assert.equal(input.value,'');assert.equal(root.querySelector('[name="issuedPassword"]'),null);
 const type=input.getAttribute('type');fire(toggle,'click');assert.equal(input.getAttribute('type'),type);
});

for(const role of ['employee','management'])test(`${role}: account setup needs exact credential permission independently of release permission`,async()=>{
 const allowed=await opened({role,permissions:['client.credential.manage'],setup:false});
 assert.ok(button(allowed.root,'Retry account setup'));allowed.controller.abort();
 const denied=await opened({role,permissions:['lending.first_loan.release','client.credential.manage.extra'],setup:false});
 assert.equal(button(denied.root,'Retry account setup'),undefined);
 assert.match(denied.root.textContent,/Synthetic borrower/);denied.controller.abort();
});

for(const deniedStatus of [401,403])test(`document download ${deniedStatus} clears borrower facts, references and detached credentials`,async()=>{
 const {root,controller}=await opened({deniedStatus});
 const password=root.querySelector('[name="issuedPassword"]');
 fire(button(root,'Download locked PDF packet'),'click');await setImmediate();
 assert.equal(password.value,'');assert.doesNotMatch(root.textContent,/Synthetic borrower|synthetic-user/);
 assert.equal(root.querySelector('[name="intakeReference"]').value,'');
 assert.equal(root.querySelector('[name="applicationReference"]').value,'');
 assert.equal(button(root,'Retry account setup'),undefined);controller.abort();
});

test('a pending old PDF is discarded when cancellation and a new approval replace the packet',async(t)=>{
 const h=await opened({role:'management',permissions:['lending.first_loan.approve'],setup:false,pending:true});
 const originalCreate=URL.createObjectURL,originalDocument=globalThis.document;let downloads=0;
 URL.createObjectURL=()=>{downloads+=1;return 'blob:synthetic';};
 globalThis.document={createElement(){return {click(){}};}};
 t.after(()=>{URL.createObjectURL=originalCreate;globalThis.document=originalDocument;h.controller.abort();});
 const originalRequest=h.api.request;let resolve;
 h.api.request=async(path,options={})=>{
  if(path.endsWith('/documents'))return new Promise(done=>{resolve=done;});
  if(path.endsWith('/cancel-approval')){h.loan.status='cancelled';return h.loan;}
  if(path.endsWith('/approve')){
   h.loan.status='approved_pending_release';h.loan.loan_id=APP;h.loan.packet_id=CLIENT;h.loan.packet_hash='c'.repeat(64);h.loan.loan_number='SYNTHETIC-NEW';
   h.loan.packet={...h.loan.packet,loan_id:APP,packet_id:CLIENT};h.loan.document={id:CLIENT,content_sha256:'d'.repeat(64)};return h.loan;
  }
  return originalRequest(path,options);
 };
 fire(button(h.root,'Download locked PDF packet'),'click');
 h.root.querySelector('[name="revokeReason"]').value='Synthetic correction';fire(button(h.root,'Cancel unreleased approval'),'click');await setImmediate();
 h.root.querySelector('[name="product"]').value=APP;fire(h.root.querySelector('[data-approval]'),'submit');await setImmediate();
 assert.match(h.root.textContent,/SYNTHETIC-NEW/);
 resolve(new Blob(['old signed packet'],{type:'application/pdf'}));await setImmediate();
 assert.equal(downloads,0,'An old document must never download under a replacement loan filename');
});
