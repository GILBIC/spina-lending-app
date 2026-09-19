import assert from 'node:assert/strict';
import test from 'node:test';
import {setImmediate} from 'node:timers/promises';
import {Element, fire} from './helpers/dom.mjs';

const module = await import('../assets/employee-operations.js').catch(() => ({}));
const SELF='10000000-0000-4000-8000-000000000001';
const OTHER='20000000-0000-4000-8000-000000000001';
const DEVICE='30000000-0000-4000-8000-000000000001';
const ID='40000000-0000-4000-8000-000000000001';
const capabilities={can_self_service:true,can_manage_staff:false,can_configure:false,can_prepare_payroll:false,can_approve_payroll:false,can_record_payments:false,can_assign_tasks:false,can_review_requests:false,can_review_shortages:false,can_prepare_accounting:false,can_view_statutory:false,can_report_shortage:true,can_record_advances:false};
function record(payload={}, allowed_actions=[], employee_id=SELF) {return {id:ID,employee_id,version:3,status:'pending',created_at:'2026-09-20T01:00:00Z',updated_at:'2026-09-20T01:00:00Z',created_by:SELF,allowed_actions,payload};}
function workspace(overrides={}) {return {
  contract_version:1,actor:{user_id:SELF,employee_id:SELF,device_id:DEVICE,is_owner:false,is_staff_manager:false},capabilities:{...capabilities},setup_missing:[],
  profiles:[{...record({full_name:'Synthetic employee',is_self:true,hire_date:'2025-01-01',daily_rate:'500.00',active:true}),id:SELF}],
  schedules:[],backups:[],calendar:[],statutory_months:[],statutory_remittances:[],payroll_history:[],attendance:[],attendance_days:[],requests:[],leave_balances:[],leave_ledger:[],tasks:[],advances:[],shortages:[],payroll:[],payments:[],accounting_preparations:[],account_candidates:[],last_result:null,...overrides,
};}
async function harness(value=workspace(), response) {
  assert.equal(typeof module.mountEmployeeOperations,'function');
  const h={root:new Element(),value,calls:[],controller:new AbortController(),session:{user:{id:SELF,role:'collector',roles:['collector']}}};
  h.api={request:async(path,options={})=>{h.calls.push({path,options});if(response)return response(path,options,h);return h.value;}};
  h.dispose=module.mountEmployeeOperations({root:h.root,api:h.api,session:h.session,signal:h.controller.signal,now:()=>new Date('2026-09-20T03:00:00Z')});await setImmediate();return h;
}
const click=(h,selector)=>{const node=h.root.querySelector(selector);assert.ok(node,selector);fire(node,'click');return node;};
const set=(h,name,value)=>{const node=h.root.querySelector(`[name="${name}"]`);assert.ok(node,name);node.value=value;};
async function open(h,action){click(h,`[data-employee-create="${action}"]`);await setImmediate();}
async function submit(h){fire(h.root.querySelector('[data-employee-form]'),'submit');await setImmediate();await setImmediate();}

test('own Collector workspace renders payslip components and no staff administration',async()=>{
 const h=await harness(workspace({payroll:[record({week_start:'2026-09-13',net_pay:'1200.15',gross_pay:'1400.15',deductions:'200.00',paid_amount:'0.00',balance_due:'1200.15',components:[{code:'basic_pay',label:'Basic pay',amount:'1000.10'},{code:'performance_benefit',label:'Good Performance Benefits',amount:'400.05'},{code:'statutory',label:'Monthly statutory allocation',amount:'-200.00'}]})]}));
 assert.match(h.root.textContent,/Basic pay/);assert.match(h.root.textContent,/1,200\.15/);assert.match(h.root.textContent,/Good Performance Benefits/);
 assert.ok(h.root.querySelector('[data-employee-create="leave_request"]'));
 assert.equal(h.root.querySelector('[data-employee-create="profile_save"]'),null);assert.equal(h.root.querySelector('[data-employee-create="payroll_prepare"]'),null);
});

test('record references and scoped history support linked corrections without mixing domains',async()=>{
 const h=await harness(workspace({requests:[record({request_kind:'leave_conversion',minutes:480})],history:[
  {record_id:ID,domain:'requests',version:2,action:'request_decide',created_at:'2026-09-20T02:00:00Z',status:'approved',payload:{reason:'Reviewed conversion evidence'}},
  {record_id:ID,domain:'profiles',version:1,action:'profile_save',created_at:'2026-09-20T02:00:00Z',status:'active',payload:{reason:'Other domain private history'}},
 ]}));
 assert.match(h.root.textContent,new RegExp(`Record reference: ${ID}`));
 assert.match(h.root.textContent,/Reviewed conversion evidence/);
 assert.doesNotMatch(h.root.textContent,/Other domain private history/);
 h.controller.abort();assert.equal(h.root.textContent,'');
});

test('missing setup is explicit and owner gets named setup forms without seeded staff values',async()=>{
 const h=await harness(workspace({setup_missing:['Actual daily rate is required.'],capabilities:{...capabilities,can_configure:true},account_candidates:[{user_id:OTHER,full_name:'Other synthetic employee',username:'synthetic',roles:['collector']}]}));
 assert.match(h.root.textContent,/Actual daily rate is required/);await open(h,'profile_save');
 assert.ok(h.root.querySelector('[name="hire_date"]'));assert.equal(h.root.querySelector('[name="daily_rate"]').value,'');
 assert.ok(h.root.querySelector('[name="premium_pay_covered"]'));assert.doesNotMatch(h.root.innerHTML,/JSON editor|name="payload"/);
});

test('only server allowed actions expose scoped reviewer controls and self approval is absent',async()=>{
 const h=await harness(workspace({capabilities:{...capabilities,can_review_requests:true},requests:[record({request_kind:'leave',work_date:'2026-09-21',minutes:240,reason:'Private <reason>'},['request_decide'],OTHER)]}));
 click(h,'[data-employee-action="request_decide"]');await setImmediate();
 assert.match(h.root.innerHTML,/Private &lt;reason&gt;/);assert.match(h.root.querySelector('[name="decision"]').innerHTML,/approved/);
 const own=await harness(workspace({requests:[record({request_kind:'leave'},['request_decide'])]}));
 click(own,'[data-employee-action="request_decide"]');await setImmediate();
 assert.doesNotMatch(own.root.querySelector('[name="decision"]').innerHTML,/value="approved"/);
});

test('review sends exact record version and rejected server feedback never claims success',async()=>{
 const h=await harness(workspace({capabilities:{...capabilities,can_review_requests:true},requests:[record({request_kind:'leave'},['request_decide'],OTHER)]}),async(path,options,h)=>{
  if(options.method==='POST')throw Object.assign(new Error('This request needs an independent reviewer.'),{status:403});return h.value;
 });
 click(h,'[data-employee-action="request_decide"]');set(h,'decision','approved');set(h,'reason','Reviewed supporting records');await submit(h);
 const post=h.calls.find(x=>x.options.method==='POST');assert.equal(post.options.body.expected_version,3);assert.equal(post.options.body.employee_id,OTHER);
 assert.match(h.root.textContent,/independent reviewer/);assert.equal(h.root.querySelector('[data-employee-form]'),null);assert.doesNotMatch(h.root.textContent,/Saved successfully/);
});

test('timeout reads back the same request before confirming and never repeats the POST',async()=>{
 let body;
 const h=await harness(workspace(),async(path,options,h)=>{
  if(options.method==='POST'){body=options.body;throw Object.assign(new Error('Timeout'),{code:'network_uncertain',status:0});}
  if(path.includes('request_id='))return {...h.value,last_result:{request_id:body.request_id,id:body.id,version:1,status:'pending_review',replayed:true,message:'Saved for review'}};
  return h.value;
 });
 await open(h,'leave_request');for(const [name,value] of Object.entries({work_date:'2026-09-21',minutes:'240',leave_kind:'ordinary',reason:'Synthetic reason'}))set(h,name,value);
 await submit(h);assert.equal(h.calls.filter(x=>x.options.method==='POST').length,1);assert.ok(h.calls.some(x=>x.path.includes(`request_id=${body.request_id}`)));assert.match(h.root.textContent,/Saved for review/);
});

test('missing readback preserves immutable payload and safe same-key retry',async()=>{
 const posts=[];
 const h=await harness(workspace(),async(path,options,h)=>{
  if(options.method==='POST'){posts.push(options.body);throw Object.assign(new Error('Timeout'),{status:503});}return h.value;
 });
 await open(h,'overtime_request');set(h,'work_date','2026-09-20');set(h,'minutes','90');set(h,'reason','Actual permitted work');await submit(h);
 assert.match(h.root.textContent,/not confirmed|unconfirmed/i);assert.equal(h.root.querySelector('[data-employee-create="leave_request"]').disabled,true);
 click(h,'[data-employee-retry]');await setImmediate();await setImmediate();assert.equal(posts.length,2);assert.deepEqual(posts[0],posts[1]);
});

test('attendance captures current time and registered device without local pay calculation',async()=>{
 let body;
 const h=await harness(workspace({attendance:[record({event_type:'clock_in',captured_at:'2026-09-20T00:00:00Z',sequence:6,device_id:DEVICE})]}),async(path,options,h)=>{
  if(options.method==='POST'){body=options.body;return {request_id:body.request_id,id:body.id,version:1,status:'accepted',replayed:false,message:'Attendance accepted'};}return h.value;
 });
 click(h,'[data-employee-attendance="break_start"]');await setImmediate();await setImmediate();
 assert.equal(body.device_id,DEVICE);assert.equal(body.employee_id,SELF);assert.equal(body.sequence,7);assert.equal(body.previous_event_id,ID);assert.equal(body.offline,false);assert.equal(body.expected_version,0);assert.ok(Date.parse(body.captured_at));
});

test('first attendance on the next Manila day resets predecessor and device sequence',async()=>{
 let body;const h=await harness(workspace({attendance:[record({event_type:'clock_out',captured_at:'2026-09-19T10:00:00Z',sequence:4,device_id:DEVICE})]}),async(path,options,h)=>{if(options.method==='POST'){body=options.body;return {request_id:body.request_id,id:body.id,version:1,status:'accepted',message:'Accepted'};}return h.value;});
 click(h,'[data-employee-attendance="clock_in"]');await setImmediate();await setImmediate();assert.equal(body.previous_event_id,null);assert.equal(body.sequence,1);
});

test('a device change uses the employee same-day predecessor across Manila midnight in UTC',async()=>{
 let body;const h=await harness(workspace({attendance:[record({event_type:'clock_in',captured_at:'2026-09-19T22:00:00Z',sequence:1,device_id:OTHER})]}),async(path,options,h)=>{if(options.method==='POST'){body=options.body;return {request_id:body.request_id,id:body.id,version:1,status:'accepted',message:'Accepted'};}return h.value;});
 click(h,'[data-employee-attendance="break_start"]');await setImmediate();await setImmediate();assert.equal(body.previous_event_id,ID);assert.equal(body.sequence,1);assert.equal(body.device_id,DEVICE);
});

test('malformed workspace or actor mismatch fails closed without rendering private data',async()=>{
 const h=await harness(workspace({actor:{user_id:OTHER},profiles:[record({full_name:'Other private person'})]}));
 assert.doesNotMatch(h.root.textContent,/Other private person/);assert.equal(h.root.querySelector('[data-employee-create="leave_request"]'),null);
});

test('dispose erases private fields and ignores a late workspace response',async()=>{
 let resolve;const h=await harness(workspace(),()=>new Promise(done=>{resolve=done;}));
 h.controller.abort();resolve(workspace({setup_missing:['Late private record']}));await setImmediate();assert.equal(h.root.innerHTML,'');
});

test('profile setup sends actual decimal text and explicit classifications for the selected account',async()=>{
 let body;const h=await harness(workspace({capabilities:{...capabilities,can_configure:true},account_candidates:[{user_id:OTHER,full_name:'Synthetic colleague',username:'synthetic',roles:['collector']}]}),async(path,options,h)=>{
  if(options.method==='POST'){body=options.body;return {request_id:body.request_id,id:body.id,version:1,status:'accepted',message:'Profile saved'};}return h.value;
 });
 await open(h,'profile_save');for(const [name,value] of Object.entries({employee_id:OTHER,hire_date:'2025-01-01',effective_from:'2026-09-20',daily_rate:'500.15',payout_method:'cash',staff_manager:'false',active:'true',premium_pay_covered:'true',holiday_pay_covered:'true',tax_exempt:'false',gp_partial_day_policy:'prorated',classification_basis:'Verified synthetic classification'}))set(h,name,value);
 await submit(h);assert.equal(body.id,OTHER);assert.equal(body.employee_id,OTHER);assert.equal(body.expected_version,0);assert.equal(body.daily_rate,'500.15');assert.equal(body.staff_manager,false);assert.equal(body.tax_exempt,false);assert.equal(Object.hasOwn(body,'role'),false);
});

test('advance request uses named installment rows, exact principal and employee agreement',async()=>{
 let body;const h=await harness(workspace(),async(path,options,h)=>{if(options.method==='POST'){body=options.body;return {request_id:body.request_id,id:body.id,version:1,status:'pending_review',message:'Advance requested'};}return h.value;});
 await open(h,'advance_request');set(h,'amount','1000.10');set(h,'reason','Synthetic request');set(h,'employee_acknowledgment','I agree to the individual installments');set(h,'payroll_authorization','Recorded employee payroll authorization');
 let rows=h.root.querySelector('[data-employee-rows="installments"]').querySelectorAll('[data-employee-row]');rows[0].querySelector('[name="due_date"]').value='2026-09-26';rows[0].querySelector('[name="amount"]').value='500.05';
 click(h,'[data-employee-add-row="installments"]');rows=h.root.querySelector('[data-employee-rows="installments"]').querySelectorAll('[data-employee-row]');assert.equal(rows[0].querySelector('[name="amount"]').value,'500.05');rows[1].querySelector('[name="due_date"]').value='2026-10-03';rows[1].querySelector('[name="amount"]').value='500.05';
 await submit(h);assert.equal(body.amount,'1000.10');assert.deepEqual(body.installments,[{due_date:'2026-09-26',amount:'500.05'},{due_date:'2026-10-03',amount:'500.05'}]);assert.equal(Object.hasOwn(body,'interest'),false);
});

test('salary payout records explicit observed result and Manila time without initiating transfers',async()=>{
 let body;const h=await harness(workspace({capabilities:{...capabilities,can_record_payments:true},payroll:[record({balance_due:'1500.00'},['payroll_payment'],OTHER)]}),async(path,options,h)=>{if(options.method==='POST'){body=options.body;return {request_id:body.request_id,id:body.id,version:4,status:'accepted',message:'Payment evidence saved'};}return h.value;});
 click(h,'[data-employee-action="payroll_payment"]');for(const [name,value] of Object.entries({amount:'500.10',occurred_at:'2026-09-26T17:30',payment_method:'gcash',reference:'Synthetic transfer',settlement_evidence:'Verified actual settlement',result:'completed'}))set(h,name,value);
 await submit(h);assert.equal(body.occurred_at,'2026-09-26T17:30:00+08:00');assert.equal(body.amount,'500.10');assert.equal(body.expected_version,3);assert.equal(body.result,'completed');assert.equal(h.calls.filter(x=>x.options.method==='POST').every(x=>x.path==='/api/v1/employee-operations/actions'),true);
});

test('linked payroll adjustment uses a new record while preserving original payroll and legal evidence',async()=>{
 let body;const h=await harness(workspace({payroll:[record({net_pay:'1500.00'},['payroll_adjustment'],OTHER)]}),async(path,options,h)=>{if(options.method==='POST'){body=options.body;return {request_id:body.request_id,id:body.id,version:1,status:'accepted',message:'Adjustment saved'};}return h.value;});
 click(h,'[data-employee-action="payroll_adjustment"]');for(const [name,value] of Object.entries({component:'lawful_recovery',amount:'-25.15',reason:'Synthetic lawful adjustment',lawful_basis:'Reviewed lawful basis',responsibility_evidence:'Individual responsibility evidence',employee_response:'Employee response reviewed',maximum_authorized_recovery:'25.15',shortage_id:ID}))set(h,name,value);
 await submit(h);assert.notEqual(body.id,ID);assert.equal(body.original_payroll_id,ID);assert.equal(body.expected_version,0);assert.equal(body.amount,'-25.15');assert.equal(body.maximum_authorized_recovery,'25.15');assert.equal(body.employee_id,OTHER);
});

test('accounting form sends structured journal lines to preparation and never to a posting endpoint',async()=>{
 let body;const h=await harness(workspace({capabilities:{...capabilities,can_prepare_accounting:true}}),async(path,options,h)=>{if(options.method==='POST'){body=options.body;return {request_id:body.request_id,id:body.id,version:1,status:'accepted',message:'Draft prepared'};}return h.value;});
 await open(h,'accounting_prepare');set(h,'preparation_kind','journal');set(h,'description','Synthetic adjustment draft');set(h,'as_of','2026-09-20');set(h,'evidence','Reviewed synthetic supporting record');
 let rows=h.root.querySelector('[data-employee-rows="lines"]').querySelectorAll('[data-employee-row]');for(const [name,value] of Object.entries({account_code:'5000',debit:'25.15',credit:'0.00'}))rows[0].querySelector(`[name="${name}"]`).value=value;
 click(h,'[data-employee-add-row="lines"]');rows=h.root.querySelector('[data-employee-rows="lines"]').querySelectorAll('[data-employee-row]');for(const [name,value] of Object.entries({account_code:'1000',debit:'0.00',credit:'25.15'}))rows[1].querySelector(`[name="${name}"]`).value=value;
 await submit(h);assert.deepEqual(body.lines,[{account_code:'5000',debit:'25.15',credit:'0.00'},{account_code:'1000',debit:'0.00',credit:'25.15'}]);assert.equal(Object.hasOwn(body,'employee_id'),false);assert.equal(body.action,'accounting_prepare');
});

test('advance reviewer sees current and proposed terms with employee agreement before deciding',async()=>{
 const h=await harness(workspace({advances:[record({installments:[{due_date:'2026-09-26',amount:'500.00'}],proposed_terms:{reason:'Requested later payment',employee_acknowledgment:'Agreed revised due date',payroll_authorization:'Revised written authorization',installments:[{due_date:'2026-10-03',amount:'500.00'}]}},['advance_decide'],OTHER)]}));
 assert.match(h.root.textContent,/Current agreed principal repayment schedule/);assert.match(h.root.textContent,/Proposed advance terms awaiting review/);assert.match(h.root.textContent,/2026-09-26/);assert.match(h.root.textContent,/2026-10-03/);assert.match(h.root.textContent,/Agreed revised due date/);
});

test('wrong successful response identity remains uncertain until matching request readback',async()=>{
 const h=await harness(workspace(),async(path,options,h)=>{if(options.method==='POST')return {request_id:OTHER,id:ID,version:1,status:'accepted',message:'Wrong result'};return h.value;});
 await open(h,'overtime_request');set(h,'work_date','2026-09-20');set(h,'minutes','30');set(h,'reason','Actual permitted work');await submit(h);
 assert.match(h.root.textContent,/not confirmed/);assert.doesNotMatch(h.root.textContent,/Wrong result/);assert.ok(h.root.querySelector('[data-employee-check]'));
});

test('Web attendance and financial forms never submit or queue while offline',async(t)=>{
 const previous=Object.getOwnPropertyDescriptor(globalThis,'navigator');Object.defineProperty(globalThis,'navigator',{configurable:true,value:{onLine:false}});
 t.after(()=>{if(previous)Object.defineProperty(globalThis,'navigator',previous);else delete globalThis.navigator;});
 const h=await harness();click(h,'[data-employee-attendance="clock_in"]');await setImmediate();assert.equal(h.calls.some(x=>x.options.method==='POST'),false);assert.match(h.root.textContent,/Offline/);
});

test('a stale refresh locks changes until authoritative employee data is available again',async()=>{
 let fail=false;const h=await harness(workspace(),async(path,options,h)=>{if(fail)throw Object.assign(new Error('Server unavailable'),{status:503});return h.value;});
 fail=true;click(h,'[data-employee-refresh]');await setImmediate();assert.equal(h.root.querySelector('[data-employee-attendance="clock_in"]').disabled,true);assert.equal(h.root.querySelector('[data-employee-refresh]').disabled,false);
 fail=false;click(h,'[data-employee-refresh]');await setImmediate();assert.equal(h.root.querySelector('[data-employee-attendance="clock_in"]').disabled,false);
});

test('empty optional holiday and reconciliation rows do not block native form validation',async()=>{
 const h=await harness(workspace({capabilities:{...capabilities,can_prepare_payroll:true,can_prepare_accounting:true}}));
 await open(h,'payroll_prepare');assert.equal(h.root.querySelector('[data-employee-rows="unworked_holiday_dates"]').querySelector('input').getAttribute('required'),null);
 click(h,'[data-employee-cancel]');await open(h,'accounting_prepare');for(const input of h.root.querySelector('[data-employee-rows="lines"]').querySelectorAll('input'))assert.equal(input.getAttribute('required'),null);
});

test('a version conflict requires authoritative refresh before another mutation',async()=>{
 const h=await harness(workspace({tasks:[record({description:'Synthetic task'},['task_progress'])]}),async(path,options,h)=>{if(options.method==='POST')throw Object.assign(new Error('The task has changed. Refresh its saved state.'),{status:409});return h.value;});
 click(h,'[data-employee-action="task_progress"]');set(h,'status','done');set(h,'reason','Synthetic completed task');await submit(h);
 assert.match(h.root.textContent,/task has changed/);assert.equal(h.root.querySelector('[data-employee-action="task_progress"]').disabled,true);assert.equal(h.root.querySelector('[data-employee-refresh]').disabled,false);
});

for(const role of ['employee','collector','management'])test(`${role} mounts private employee panel through server capabilities`,async()=>{
 const names={employee:'mountEmployeeWorkspace',collector:'mountCollectorWorkspace',management:'mountManagementWorkspace'};
 const roleModule=await import(`../assets/roles/${role}.js`);const root=new Element();root.dataset={};let navigation;const calls=[];const controller=new AbortController();
 const api={request:async(path)=>{calls.push(path);if(path==='/api/v1/employee-operations/workspace')return workspace();if(path==='/api/v1/account')return {profile:{full_name:'Synthetic employee'}};return {};}};
 await roleModule[names[role]]({root,api,session:{user:{id:SELF,role,roles:[role],permissions:[]}},signal:controller.signal,setNavigation:items=>{navigation=items;}});await setImmediate();
 assert.ok(calls.includes('/api/v1/employee-operations/workspace'));assert.ok(navigation.some(item=>item.id.includes('employee-operations')||item.id==='employee-operations'));assert.match(root.textContent,/My attendance/);
 controller.abort();assert.equal(root.querySelector('[data-employee-operations]').innerHTML,'');
});
