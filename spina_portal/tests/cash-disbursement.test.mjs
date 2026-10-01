import assert from 'node:assert/strict';
import { setImmediate } from 'node:timers/promises';
import test from 'node:test';

import { Element, fire } from './helpers/dom.mjs';

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
