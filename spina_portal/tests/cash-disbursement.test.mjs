import assert from 'node:assert/strict';
import { setImmediate } from 'node:timers/promises';
import test from 'node:test';

import { Element, fire } from './helpers/dom.mjs';

const datasets = new WeakMap();
Object.defineProperty(Element.prototype,'dataset',{get(){if(!datasets.has(this))datasets.set(this,{});return datasets.get(this);}, configurable:true});

const module = await import('../assets/cash-disbursement.js').catch(() => ({}));
const USER='10000000-0000-4000-8000-000000000001';
const DEVICE='20000000-0000-4000-8000-000000000001';

const workspace = {
  contract_version:1,
  actor:{user_id:USER,employee_id:USER,device_id:DEVICE,is_owner:false,is_staff_manager:false},
  capabilities:{can_prepare_cash_disbursement:true},
  accounting_preparations:[],
};

const tick=async()=>{await setImmediate();await setImmediate();};

function session(role, permissions=['cash_disbursement.prepare']) {
  return {user:{id:USER,role,roles:[role]},permissions};
}

test('Employee Cash Disbursement prepares an exact constrained command and never posts', async (t) => {
  assert.equal(typeof module.mountCashDisbursement,'function');
  const root=new Element(),calls=[],controller=new AbortController();
  t.after(()=>controller.abort());
  module.mountCashDisbursement({
    root,
    session:session('employee'),
    signal:controller.signal,
    api:{request:async(path,options={})=>{
      calls.push({path,options});
      if(options.method==='POST'){
        const body=options.body;
        return {request_id:body.request_id,id:body.id,version:1,status:'accepted',message:'Draft prepared'};
      }
      return workspace;
    }},
  });
  await tick();

  const form=root.querySelector('[data-cash-disbursement-form]');
  assert.ok(form);
  form.querySelector('[name="as_of"]').value='2026-10-01';
  form.querySelector('[name="payee"]').value='Electric utility';
  form.querySelector('[name="purpose"]').value='September office electricity';
  form.querySelector('[name="amount"]').value='1250.50';
  form.querySelector('[name="expense_account_code"]').value='5210';
  form.querySelector('[name="cash_account_code"]').value='1010';
  form.querySelector('[name="evidence_reference"]').value='OR-UTIL-1001';
  form.querySelector('[name="evidence"]').value='Reviewed original utility receipt';
  fire(form,'submit');
  await tick();

  const write=calls.find((call)=>call.options.method==='POST');
  assert.ok(write);
  assert.equal(write.path,'/api/v1/employee-operations/actions');
  assert.equal(write.options.body.action,'cash_disbursement_prepare');
  assert.equal(write.options.body.amount,'1250.50');
  assert.equal(write.options.body.expense_account_code,'5210');
  assert.equal(write.options.body.cash_account_code,'1010');
  assert.match(write.options.body.request_id,/^[0-9a-f-]{36}$/);
  assert.match(write.options.body.id,/^[0-9a-f-]{36}$/);
  assert.equal(write.options.body.expected_version,0);

  assert.equal(root.querySelector('[data-cash-disbursement-post]'),null);
  assert.equal(calls.some((call)=>/\/post$/.test(call.path)),false);
});

test('Management can use the same Cash Disbursement preparation surface', async (t) => {
  const root=new Element(),controller=new AbortController();
  t.after(()=>controller.abort());
  module.mountCashDisbursement({
    root,
    session:session('management',['cash_disbursement.prepare','accounting.journal.manage']),
    signal:controller.signal,
    api:{request:async()=>workspace},
  });
  await tick();
  assert.ok(root.querySelector('[data-cash-disbursement-form]'));
  assert.match(root.textContent,/Management reviews and posts the linked draft in General Journal/i);
});

test('Cash Disbursement stays absent without its exact permission', async () => {
  const root=new Element();let requests=0;
  module.mountCashDisbursement({
    root,
    session:session('employee',[]),
    api:{request:async()=>{requests++;return workspace;}},
  });
  await tick();
  assert.equal(requests,0);
  assert.match(root.textContent,/not assigned/i);
});

test('Cash Disbursement uses only approved expense and cash accounts', async (t) => {
  const root=new Element(),controller=new AbortController();
  t.after(()=>controller.abort());
  module.mountCashDisbursement({
    root,
    session:session('employee'),
    signal:controller.signal,
    api:{request:async()=>workspace},
  });
  await tick();
  const expense=root.querySelector('[name="expense_account_code"]');
  const cash=root.querySelector('[name="cash_account_code"]');
  assert.match(expense.innerHTML,/5200/);
  assert.match(expense.innerHTML,/5210/);
  assert.match(expense.innerHTML,/5220/);
  assert.match(expense.innerHTML,/5230/);
  assert.match(expense.innerHTML,/5240/);
  assert.match(expense.innerHTML,/5290/);
  assert.doesNotMatch(expense.innerHTML,/3000/);
  assert.match(cash.innerHTML,/1010/);
  assert.match(cash.innerHTML,/1030/);
  assert.doesNotMatch(cash.innerHTML,/1020/);
});
function fill(root, overrides={}) {
  const form=root.querySelector('[data-cash-disbursement-form]');
  const values={as_of:'2026-10-01',payee:'Synthetic utility',purpose:'Office expense',amount:'1250.50',expense_account_code:'5210',cash_account_code:'1010',evidence_reference:'TEST-1',evidence:'Synthetic receipt',...overrides};
  for(const [name,value] of Object.entries(values))form.querySelector(`[name="${name}"]`).value=value;
  return form;
}

test('confirmed validation rejection preserves entries and permits correction without posting',async(t)=>{
  const root=new Element(),controller=new AbortController();t.after(()=>controller.abort());let writes=0;
  module.mountCashDisbursement({root,session:session('employee'),signal:controller.signal,api:{request:async(path,options={})=>{if(options.method==='POST'){writes++;throw Object.assign(new Error('Validation'),{status:422});}return workspace;}}});
  await tick();const form=fill(root);fire(form,'submit');await tick();
  assert.equal(form.querySelector('[name="amount"]').value,'1250.50');
  assert.equal(form.querySelector('[name="purpose"]').value,'Office expense');
  assert.equal(root.querySelector('[data-cash-feedback]').getAttribute('role'),'alert');
  assert.equal(root.querySelector('[data-cash-submit]').disabled,false);
  form.querySelector('[name="amount"]').value='1251.00';fire(form,'submit');await tick();assert.equal(writes,2);
});

test('duplicate submission and uncertainty cannot create a second command across remount',async(t)=>{
  const root=new Element(),controller=new AbortController(),account=session('employee');t.after(()=>controller.abort());
  let reject, writes=[];
  const api={request:async(path,options={})=>{if(options.method==='POST'){writes.push(options.body);if(writes.length===1)return new Promise((resolve,r)=>{reject=r;});return {request_id:options.body.request_id,id:options.body.id,version:1,status:'accepted'};}return workspace;}};
  module.mountCashDisbursement({root,session:account,signal:controller.signal,api});await tick();const form=fill(root);fire(form,'submit');fire(form,'submit');await tick();assert.equal(writes.length,1);
  reject(new Error('Lost response'));await tick();assert.equal(root.querySelector('[data-cash-disbursement-form]'),null);
  module.mountCashDisbursement({root,session:account,signal:controller.signal,api});await tick();
  assert.equal(root.querySelector('[data-cash-disbursement-form]'),null);
  fire(root.querySelector('[data-cash-retry]'),'click');await tick();assert.equal(writes.length,2);assert.deepEqual(writes[1],writes[0]);
  assert.ok(root.querySelector('[data-cash-disbursement-form]'));
});

test('receipt reconciliation unlocks only the same identity and request',async(t)=>{
  const root=new Element(),controller=new AbortController();t.after(()=>controller.abort());let submitted, receipt;
  const api={request:async(path,options={})=>{if(options.method==='POST'){submitted=options.body;throw new Error('Lost response');}return {...workspace,last_result:receipt};}};
  module.mountCashDisbursement({root,session:session('employee'),signal:controller.signal,api});await tick();fire(fill(root),'submit');await tick();
  receipt={request_id:submitted.request_id,id:'wrong',version:1,status:'accepted'};fire(root.querySelector('[data-cash-refresh]'),'click');await tick();assert.equal(root.querySelector('[data-cash-disbursement-form]'),null);
  receipt={...receipt,id:submitted.id};fire(root.querySelector('[data-cash-refresh]'),'click');await tick();assert.ok(root.querySelector('[data-cash-disbursement-form]'));assert.match(root.textContent,/Draft confirmed/);
});

test('nonstaff permission, invalid exact amounts, and stale disposed forms cannot write',async(t)=>{
  const denied=new Element();let reads=0;
  module.mountCashDisbursement({root:denied,session:session('client'),api:{request:async()=>{reads++;return workspace;}}});await tick();assert.equal(reads,0);
  const root=new Element(),controller=new AbortController();t.after(()=>controller.abort());let writes=0;
  module.mountCashDisbursement({root,session:session('employee'),signal:controller.signal,api:{request:async(path,options={})=>{if(options.method==='POST')writes++;return workspace;}}});await tick();
  for(const amount of ['0.00','-1.00','1.001','1e3','1000000000000.00']){fire(fill(root,{amount}),'submit');await tick();}
  assert.equal(writes,0);const old=fill(root);controller.abort();fire(old,'submit');await tick();assert.equal(writes,0);assert.equal(root.textContent,'');
});
test('an omitted permission-gated mount root is a harmless no-op',()=>{
  let calls=0;
  const dispose=module.mountCashDisbursement({root:null,session:session('employee',[]),api:{request:()=>{calls++;}}});
  assert.equal(typeof dispose,'function');dispose();assert.equal(calls,0);
});
test('token refresh replaces the session object without losing a committed uncertain request',async(t)=>{
  const root=new Element(),controller=new AbortController();t.after(()=>controller.abort());const writes=[];let committed;
  const api={request:async(path,options={})=>{if(options.method==='POST'){writes.push(options.body);committed||={...options.body};if(writes.length===1)throw new Error('Committed but response lost');return {request_id:committed.request_id,id:committed.id,version:1,status:'accepted'};}return workspace;}};
  module.mountCashDisbursement({root,api,session:{...session('employee'),access_token:'old'},signal:controller.signal});await tick();fire(fill(root),'submit');await tick();
  module.mountCashDisbursement({root,api,session:{...session('employee'),access_token:'new'},signal:controller.signal});await tick();
  fire(root.querySelector('[data-cash-refresh]'),'click');await tick();
  assert.equal(root.querySelector('[data-cash-disbursement-form]'),null,'uncertain command must still block a new draft after refreshed session identity');
  fire(root.querySelector('[data-cash-retry]'),'click');await tick();assert.deepEqual(writes,[committed,committed]);
});
for(const boundary of ['logout','account','permission','role','local-device','registered-device'])test(`cash recovery clears at ${boundary} boundary and cannot be resurrected by late work`,async(t)=>{
  const root=new Element(),controller=new AbortController();t.after(()=>controller.abort());let local='browser-one',registered=DEVICE,write;
  const api={sessionStore:{deviceId:()=>local},request:async(path,options={})=>{if(options.method==='POST'){write=options.body;throw new Error('Uncertain');}return {...workspace,actor:{...workspace.actor,device_id:registered}};}};
  const original=session('employee');module.mountCashDisbursement({root,api,session:original,signal:controller.signal});await tick();fire(fill(root),'submit');await tick();assert.ok(root.querySelector('[data-cash-retry]'));
  let next={...session('employee')};
  if(boundary==='logout')module.clearCashDisbursementRecovery(api);
  if(boundary==='account'){module.syncCashDisbursementRecovery(api,{...next,user:{...next.user,id:'other'}});}
  if(boundary==='permission'){module.syncCashDisbursementRecovery(api,session('employee',[]));}
  if(boundary==='role'){module.syncCashDisbursementRecovery(api,session('management'));}
  if(boundary==='local-device')local='browser-two';
  if(boundary==='registered-device')registered='30000000-0000-4000-8000-000000000001';
  module.mountCashDisbursement({root,api,session:next,signal:controller.signal});await tick();
  assert.ok(root.querySelector('[data-cash-disbursement-form]'));assert.equal(root.querySelector('[data-cash-retry]'),null);
  assert.ok(write.request_id);
});

test('logout invalidates an in-flight completion before a same-account login',async(t)=>{
  const root=new Element(),controller=new AbortController();t.after(()=>controller.abort());let finish,write;
  const api={request:async(path,options={})=>{if(options.method==='POST'){write=options.body;return new Promise(resolve=>{finish=resolve;});}return workspace;}};
  module.mountCashDisbursement({root,api,session:session('employee'),signal:controller.signal});await tick();fire(fill(root),'submit');await tick();
  module.clearCashDisbursementRecovery(api);module.mountCashDisbursement({root,api,session:session('employee'),signal:controller.signal});await tick();
  fill(root,{payee:'New login draft'});finish({request_id:write.request_id,id:write.id,version:1,status:'accepted'});await tick();
  assert.equal(root.querySelector('[name="payee"]').value,'New login draft');assert.doesNotMatch(root.textContent,/Draft prepared/);
});
