import assert from 'node:assert/strict';
import test from 'node:test';
import {setImmediate} from 'node:timers/promises';
import {Element,fire} from './helpers/dom.mjs';
import {mountEmployeeWorkspace} from '../assets/employee-workspace.js';
import {mountEmployeeOperations} from '../assets/employee-operations.js';
import {workspace,SELF,ID} from './helpers/employee-workspace.mjs';

const payroll={id:ID,employee_id:SELF,version:3,status:'partially_paid',allowed_actions:[],payload:{week_start:'2026-09-27',period_end:'2026-10-03',payroll_kind:'weekly',gross_pay:'12500.00',deductions:'500.00',net_pay:'12000.00',paid_amount:'4000.00',balance_due:'8000.00',issues:[],components:[]}};
const value=()=>workspace({payroll:[payroll],tasks:[{id:ID,employee_id:SELF,version:1,status:'todo',allowed_actions:[],payload:{description:'Synthetic private task'}}]});

for(const status of [401,403])for(const action of ['print','write'])test(`${action} ${status} invalidates the derived private Today snapshot as well as Operations`,async t=>{
  const root=new Element(),controller=new AbortController(),calls=[];let handle,denial=false;
  await mountEmployeeWorkspace({root,signal:controller.signal,session:{user:{id:SELF}},setNavigation(){},registerWorkspaceHandle:h=>handle=h,
    api:{async request(path,options={}){calls.push({path,method:options.method||'GET'});if(denial)throw Object.assign(Error('Synthetic denied employee data'),{status});return value();}}});
  t.after(()=>controller.abort());await setImmediate();
  const today=root.querySelector('[data-employee-today]');assert.match(today.textContent,/2026-09-27.*Partially Paid/);assert.match(today.textContent,/1 loaded/);
  denial=true;
  if(action==='print'){handle.activate('employee-payslips');fire(root.querySelector('[data-employee-print-payroll]'),'click');}
  else{handle.activate('employee-operations');fire(root.querySelector('[data-employee-attendance="clock_in"]'),'click');}
  await setImmediate();
  assert.match(today.textContent,/access is unavailable/);assert.doesNotMatch(today.textContent,/2026-09-27|Partially Paid|1 loaded/);
  assert.equal(root.querySelector('[data-employee-form]'),null);assert.equal(root.querySelector('[data-employee-print-region]'),null);
  assert.equal(calls.length,2);assert.equal(calls.filter(call=>call.method==='POST').length,action==='write'?1:0);
});

for(const status of [401,403,503])test(`late print ${status} cannot mutate a replacement mount or its privacy callbacks`,async t=>{
  const root=new Element(),session={user:{id:SELF}};let reject,reads=0,oldAfter=0,oldDenied=0;
  const dispose=mountEmployeeOperations({root,session,presentation:'employee',api:{request(){return ++reads===1?Promise.resolve(value()):new Promise((resolve,fail)=>reject=fail);}},afterTaskChange:()=>oldAfter++,onReadState:state=>{if(state.status==='denied')oldDenied++;}});
  await setImmediate();fire(root.querySelector('[data-employee-print-payroll]'),'click');await setImmediate();assert.equal(reads,2);dispose();const afterAtDispose=oldAfter;
  const replacement=mountEmployeeOperations({root,session,presentation:'employee',api:{request:async()=>value()}});t.after(replacement);await setImmediate();
  fire(root.querySelector('[data-employee-create="leave_request"]'),'click');const form=root.querySelector('[data-employee-form]'),reason=form.querySelector('[name="reason"]');reason.value='Replacement mount private draft';
  reject(Object.assign(Error('Synthetic late print rejection'),{status}));await setImmediate();
  assert.strictEqual(root.querySelector('[data-employee-form]'),form);assert.equal(reason.value,'Replacement mount private draft');assert.equal(reason.disabled,false);assert.doesNotMatch(root.textContent,/Synthetic late print rejection/);assert.equal(oldAfter,afterAtDispose);assert.equal(oldDenied,0);
});
