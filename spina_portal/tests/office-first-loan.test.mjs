import assert from 'node:assert/strict';
import { existsSync } from 'node:fs';
import { setImmediate } from 'node:timers/promises';
import test from 'node:test';
import { Element, fire } from './helpers/dom.mjs';

const url=new URL('../assets/office-first-loan.js',import.meta.url);
const CLIENT='11111111-1111-4111-8111-111111111111';
const APP='22222222-2222-4222-8222-222222222222';
const VERSION='33333333-3333-4333-8333-333333333333';
const PRODUCT='44444444-4444-4444-8444-444444444444';
const LOAN='55555555-5555-4555-8555-555555555555';
async function mount(){assert.ok(existsSync(url),'First-loan office workflow is not implemented');return (await import(url)).mountOfficeFirstLoan;}
function harness(role='management'){
 const h={root:new Element(),controller:new AbortController(),calls:[],loans:[]};
 h.signal=h.controller.signal;
 h.session={user:{role},permissions:['client_onboarding.requirement.review','lending.first_loan.approve','lending.first_loan.release','client.credential.manage']};
 h.review={client_id:CLIENT,application_id:APP,application_version_id:VERSION,application_reference:'Loan-Mixed',cif_version_id:CLIENT,version_number:1,missing_fields:[],information:{request:{requested_loan_type_id:PRODUCT,requested_amount:'1000.00'},repayment:{}}};
 h.context={server_business_date:'2026-09-19',products:[{id:PRODUCT,code:'regular',name:'Synthetic Regular',calculation_mode:'fixed_daily',daily_interest_per_1000:'0.00'}],templates:[{version:'SYNTHETIC',content_sha256:'a'.repeat(64),approved_for_execution:true}]};
 h.defaultRequest=(path)=>{if(path.endsWith('/cif-client'))return {client_id:CLIENT,application_reference:'Intake-Mixed'};if(path.endsWith('/review-summary'))return h.review;if(path.endsWith('/context'))return h.context;if(path.includes('/by-application/'))return {loans:h.loans};throw new Error('Unexpected request '+path);};
 h.api={async request(path,options={}){h.calls.push({path,options});if(h.request)return h.request(path,options);return h.defaultRequest(path);}};
 return h;
}
function button(h,text){return h.root.querySelectorAll('button').find(x=>x.textContent===text);}
function field(h,name){return h.root.querySelector(`[name="${name}"]`);}
async function open(h){field(h,'intakeReference').value='Intake-Mixed';field(h,'applicationReference').value='Loan-Mixed';fire(h.root.querySelector('form'),'submit');await setImmediate();}

for(const role of ['employee','management'])test(`${role} resolves exact application before first-loan actions`,async()=>{
 const h=harness(role);(await mount())(h);await open(h);
 assert.equal(h.calls.filter(x=>x.options.method==='POST').length,0);
 assert.equal(h.calls.length,4);
 assert.equal(Boolean(button(h,'Approve exact terms')),role==='management');
 assert.match(h.root.textContent,/Loan-Mixed/);
});

for(const role of ['collector','client'])test(`${role} gets no first-loan actions or requests`,async()=>{
 const h=harness(role);(await mount())(h);assert.equal(h.calls.length,0);assert.equal(h.root.querySelector('form'),null);
});

test('combined Collector and Employee memberships allow office work without Management approval',async()=>{
 const h=harness('collector');h.session.user.roles=['collector','employee','employee_manager'];
 (await mount())(h);await open(h);
 assert.equal(h.calls.length,4);assert.equal(button(h,'Approve exact terms'),undefined);
 assert.equal(button(h,'Authorize exact office release'),undefined);
 assert.match(h.root.textContent,/Loan-Mixed/);
});

test('mismatched response fails closed before financial actions',async()=>{
 const h=harness();h.review.client_id=LOAN;(await mount())(h);await open(h);
 assert.equal(button(h,'Approve exact terms'),undefined);assert.match(h.root.textContent,/match|invalid/i);
});

test('clear removes every private editor value and invalidates pending lookup',async()=>{
 const h=harness();let resolve;h.request=()=>new Promise(r=>{resolve=r;});(await mount())(h);
 field(h,'intakeReference').value='Private';field(h,'applicationReference').value='Private';fire(h.root.querySelector('form'),'submit');
 const input=field(h,'intakeReference');fire(button(h,'Clear'),'click');resolve({client_id:CLIENT,application_reference:'Private'});await setImmediate();
 assert.equal(input.value,'');assert.equal(h.calls.length,1);assert.equal(button(h,'Approve exact terms'),undefined);
});

test('logout removes all values and cannot be undone by late responses',async()=>{
 const h=harness();let resolve;h.request=()=>new Promise(r=>{resolve=r;});(await mount())(h);field(h,'intakeReference').value='Private';field(h,'applicationReference').value='Private';fire(h.root.querySelector('form'),'submit');
 const input=field(h,'applicationReference');h.controller.abort();resolve({client_id:CLIENT,application_reference:'Private'});await setImmediate();assert.equal(input.value,'');assert.equal(h.root.innerHTML,'');
});

function approved(status='approved_pending_release') {
 return {loan_id:LOAN,client_id:CLIENT,packet_id:VERSION,packet_hash:'a'.repeat(64),loan_number:'SYNTHETIC-ONLY',status,
  packet:{loan_id:LOAN,client_id:CLIENT,packet_id:VERSION,application:{application_id:APP},borrower:{full_name:'Synthetic Borrower'},terms:{principal:'1000.00',schedule_basis_date:'2026-09-19'},net_cash:'1000.00',schedule:[{installment_number:1,due_date:'2026-09-20',contractual_amount:'1100.00',principal_component:'1000.00',interest_component:'100.00'}]},authorization:null,document:null,
  release:status==='released'?{released_at:'2026-09-19T02:00:00Z',receipt:{receipt_reference:'SYNTHETIC-RECEIPT',actual_cash_received:'1000.00'}}:null,credential_intent:status==='released'?{status:'pending'}:null};
}

test('document issuance sends only exact packet hash and blocks authorization until issued',async()=>{
 const h=harness();h.loans=[approved()];h.request=(path,options)=>options.method==='POST'?{id:VERSION,content_sha256:'b'.repeat(64),byte_count:50}:h.defaultRequest(path);
 (await mount())(h);await open(h);assert.equal(button(h,'Authorize exact office release'),undefined);
 fire(button(h,'Generate locked PDF packet'),'click');await setImmediate();
 assert.deepEqual(h.calls.find(x=>x.options.method==='POST').options.body,{packet_hash:'a'.repeat(64)});
});

test('one-time credentials remain visible after success and detached password is erased on clear',async()=>{
 const h=harness();h.loans=[approved('released')];h.request=(path,options)=>options.method==='POST'?{status:'completed',credentials:{username:'SYNTHETIC-USER',password:'Synthetic-Only-Password'}}:h.defaultRequest(path);
 (await mount())(h);await open(h);fire(button(h,'Retry account setup'),'click');await setImmediate();
 const password=field(h,'issuedPassword');assert.ok(password);assert.equal(password.value,'Synthetic-Only-Password');
 fire(button(h,'Clear'),'click');assert.equal(password.value,'');assert.equal(field(h,'issuedPassword'),null);
});

test('pending credential result cannot restore credentials after logout',async()=>{
 const h=harness();h.loans=[approved('released')];let resolve;h.request=(path,options)=>options.method==='POST'?new Promise(r=>{resolve=r;}):h.defaultRequest(path);
 (await mount())(h);await open(h);fire(button(h,'Retry account setup'),'click');h.controller.abort();
 resolve({status:'completed',credentials:{username:'SYNTHETIC-USER',password:'Synthetic-Only-Password'}});await setImmediate();assert.equal(h.root.innerHTML,'');
});

test('uncertain mutation prevents duplicate actions until authoritative reload',async()=>{
 const h=harness();h.loans=[approved()];let resolve;h.request=(path,options)=>options.method==='POST'?new Promise(r=>{resolve=r;}):h.defaultRequest(path);
 (await mount())(h);await open(h);const generate=button(h,'Generate locked PDF packet');fire(generate,'click');fire(generate,'click');await setImmediate();
 assert.equal(h.calls.filter(x=>x.options.method==='POST').length,1);resolve({unverified:true});await setImmediate();
 assert.equal(button(h,'Generate locked PDF packet').disabled,true);assert.equal(button(h,'Reload saved record').disabled,false);
});

test('approval sends exact decimals and selected source version without creating a schedule in the browser',async()=>{
 const h=harness();h.request=(path,options)=>{if(options.method==='POST'){h.loans=[approved()];return h.loans[0];}return h.defaultRequest(path);};
 (await mount())(h);await open(h);
 for(const [name,value] of Object.entries({product:PRODUCT,principal:'1234.56',interest:'123.46',interestRate:'10.0000',installment:'113.17',count:'12',frequency:'daily',basisDate:'2026-09-19',firstDate:'2026-09-25',semiDays:'15,30',pricingReference:'SYNTHETIC-APPROVAL',accountEmail:'synthetic@example.invalid',template:'SYNTHETIC',deductions:'fee | 10.25 | SYNTHETIC-FEE'}))field(h,name).value=value;
 fire(h.root.querySelector('[data-approval]'),'submit');await setImmediate();
 const body=h.calls.find(x=>x.options.method==='POST').options.body;
 assert.equal(body.application_version_id,VERSION);assert.equal(body.terms.principal,'1234.56');assert.equal(body.terms.interest_rate_percent,'10.0000');assert.equal(body.terms.installment_count,12);assert.equal(body.terms.deductions[0].amount,'10.25');assert.equal(Object.hasOwn(body,'schedule'),false);
 assert.equal(button(h,'Approve exact terms'),undefined);
});

test('contract upload requires witnessed signature and never implies borrower cash confirmation',async()=>{
 const h=harness('employee');h.loans=[{...approved(),document:{id:PRODUCT,content_sha256:'b'.repeat(64),byte_count:8}}];
 h.request=(path,options)=>options.method==='POST'?{packet_hash:'a'.repeat(64),purpose:'borrower_contract_signed',evidence_reference:`office-evidence:${CLIENT}`} :h.defaultRequest(path);
 (await mount())(h);await open(h);field(h,'contractFile').files=[{size:8,type:'application/pdf',arrayBuffer:async()=>new TextEncoder().encode('%PDF-1.4').buffer}];
 fire(h.root.querySelector('[data-contract]'),'submit');await setImmediate();assert.equal(h.calls.filter(x=>x.options.method==='POST').length,0);
 field(h,'witnessedSignature').checked=true;fire(h.root.querySelector('[data-contract]'),'submit');await setImmediate();
 const posts=h.calls.filter(x=>x.options.method==='POST');assert.equal(posts.length,1);assert.ok(posts[0].path.endsWith('/evidence'));assert.equal(posts[0].options.body.witnessed_wet_signature,true);assert.equal(Object.hasOwn(posts[0].options.body,'borrower_confirmed'),false);
});

test('resumed exact contract and cash evidence can record one explicit confirmed release',async()=>{
 const h=harness('employee');h.loans=[{...approved(),document:{id:PRODUCT,content_sha256:'b'.repeat(64),byte_count:8},authorization:{id:APP,revoked:false},evidence:{borrower_contract_signed:{evidence_reference:`office-evidence:${CLIENT}`},borrower_cash_received:{evidence_reference:`office-evidence:${VERSION}`}}}];
 h.request=(path,options)=>{if(options.method==='POST'){h.loans=[approved('released')];return {...h.loans[0],credentials:{status:'pending',detail:'Synthetic setup pending'}};}return h.defaultRequest(path);};
 (await mount())(h);await open(h);field(h,'cashAmount').value='1000.00';field(h,'borrowerConfirmed').checked=true;fire(h.root.querySelector('[data-release]'),'submit');await setImmediate();
 const post=h.calls.find(x=>x.options.method==='POST');assert.ok(post.path.endsWith('/release'));assert.equal(post.options.body.cash_amount,'1000.00');assert.equal(post.options.body.borrower_confirmed,true);assert.equal(post.options.body.contract_evidence_reference,`office-evidence:${CLIENT}`);assert.match(h.root.textContent,/SYNTHETIC-RECEIPT/);
});

test('7x7 compliance uses existing endpoint and immutable packet terms',async()=>{
 const h=harness();h.session.permissions.push('lending.contract_schedule.manage');const loan=approved();loan.packet.contract_reference=VERSION;Object.assign(loan.packet.terms,{product_code:'seven_by_seven',payment_frequency:'daily',first_due_date:'2026-09-25',installment_amount:'100.00',grace_days:0});h.loans=[loan];
 h.request=(path,options)=>options.method==='POST'?{loan_id:LOAN,terms_fingerprint:'c'.repeat(64)}:h.defaultRequest(path);
 (await mount())(h);await open(h);for(const name of ['applicability_review_ready','pricing_cap_review_ready','disclosure_ready','total_cost_cap_review_ready'])field(h,name).checked=true;
 for(const [name,value] of Object.entries({policyVersion:'SYNTHETIC-POLICY',rateCeiling:'0.050000',lifetimeCeiling:'1000.00',countedCost:'100.00',complianceEvidence:'SYNTHETIC-REVIEW',complianceNote:'Synthetic exact review'}))field(h,name).value=value;
 fire(h.root.querySelector('[data-compliance]'),'submit');await setImmediate();
 const post=h.calls.find(x=>x.options.method==='POST');assert.ok(post.path.endsWith('/contract-schedules/7x7-pricing-compliance/review'));assert.equal(post.options.body.contract_reference,VERSION);assert.equal(post.options.body.first_due_date,'2026-09-25');assert.equal(post.options.body.agreed_daily_payment,'100.00');assert.equal(post.options.body.penalty_rate_ceiling,'0.050000');assert.equal(button(h,'Generate locked PDF packet').disabled,false);
});
