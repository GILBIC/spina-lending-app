import assert from 'node:assert/strict';
import test from 'node:test';
import {setImmediate} from 'node:timers/promises';
import {fire} from './helpers/dom.mjs';
import {harness,workspace,SELF,DEVICE,ID,click} from './helpers/employee-workspace.mjs';

test('switching a dirty editor requires explicit discard and ordinary reads do not reset that choice',async t=>{
  const h=await harness();t.after(h.dispose);const original=globalThis.confirm;t.after(()=>globalThis.confirm=original);
  let allow=false,confirmations=0;globalThis.confirm=()=>{confirmations++;return allow;};
  click(h,'[data-employee-create="leave_request"]');const form=h.root.querySelector('[data-employee-form]'),reason=form.querySelector('[name="reason"]');reason.value='Keep unfinished leave';
  click(h,'[data-employee-create="leave_request"]');assert.strictEqual(h.root.querySelector('[data-employee-form]'),form);assert.equal(confirmations,0);
  await h.handle.refresh();click(h,'[data-employee-create="advance_request"]');
  assert.equal(confirmations,1);assert.strictEqual(h.root.querySelector('[data-employee-form]'),form);assert.equal(reason.value,'Keep unfinished leave');
  allow=true;click(h,'[data-employee-create="advance_request"]');
  assert.equal(confirmations,2);assert.notStrictEqual(h.root.querySelector('[data-employee-form]'),form);assert.equal(reason.value,'');assert.equal(h.calls.filter(c=>c.options.method==='POST').length,0);
});

test('blank editor switches directly but added advance rows count as unfinished work',async t=>{
  const h=await harness();t.after(h.dispose);const original=globalThis.confirm;t.after(()=>globalThis.confirm=original);let confirmations=0;globalThis.confirm=()=>{confirmations++;return false;};
  click(h,'[data-employee-create="leave_request"]');click(h,'[data-employee-create="advance_request"]');assert.equal(confirmations,0);
  click(h,'[data-employee-add-row="installments"]');const rows=h.root.querySelector('[data-employee-rows="installments"]');
  click(h,'[data-employee-create="leave_request"]');assert.equal(confirmations,1);assert.strictEqual(h.root.querySelector('[data-employee-rows="installments"]'),rows);
});
test('read refresh and unrelated attendance retain the actual leave editor and values',async(t)=>{const h=await harness();t.after(h.dispose);click(h,'[data-employee-create="leave_request"]');const form=h.root.querySelector('[data-employee-form]'),reason=form.querySelector('[name="reason"]');reason.value='Keep this leave draft';assert.ok(h.handle);await h.handle.refresh({recover:false});assert.equal(h.root.querySelector('[data-employee-form]'),form);assert.equal(reason.value,'Keep this leave draft');click(h,'[data-employee-attendance="clock_in"]');await setImmediate();await setImmediate();assert.equal(h.root.querySelector('[data-employee-form]'),form);assert.equal(reason.value,'Keep this leave draft');});
test('changed version retains stale text and original version while blocking submit',async(t)=>{const rec={id:ID,version:3,employee_id:SELF,status:'pending',payload:{description:'Task'},allowed_actions:['task_progress']};const h=await harness(workspace({tasks:[rec]}));t.after(h.dispose);click(h,'[data-employee-action="task_progress"]');const form=h.root.querySelector('[data-employee-form]');form.querySelector('[name="reason"]').value='Keep completed work';h.value={...h.value,tasks:[{...rec,version:4}]};await h.handle.refresh();assert.equal(h.root.querySelector('[data-employee-form]'),form);assert.match(h.root.textContent,/changed.*draft|draft.*changed/i);fire(form,'submit');await setImmediate();assert.equal(h.calls.filter(c=>c.options.method==='POST').length,0);click(h,'[data-employee-cancel]');assert.equal(h.root.querySelector('[data-employee-form]'),null);});
test('advance dynamic row node values survive reads and denied scope erases them',async(t)=>{const h=await harness();t.after(h.dispose);click(h,'[data-employee-create="advance_request"]');click(h,'[data-employee-add-row="installments"]');const rows=h.root.querySelector('[data-employee-rows="installments"]');rows.querySelectorAll('[name="amount"]')[1].value='500.05';await h.handle.refresh();assert.equal(h.root.querySelector('[data-employee-rows="installments"]'),rows);assert.equal(rows.querySelectorAll('[name="amount"]')[1].value,'500.05');h.readError=Object.assign(new Error('Denied'),{status:403});await h.handle.refresh();assert.equal(h.root.querySelector('[data-employee-form]'),null);assert.equal(rows.querySelectorAll('[name="amount"]')[1].value,'');});
