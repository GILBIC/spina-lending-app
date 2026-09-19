import assert from 'node:assert/strict';
import {writeFile} from 'node:fs/promises';
import test, {after} from 'node:test';
import {setImmediate} from 'node:timers/promises';
import {Element,fire} from './helpers/dom.mjs';
import {mountEmployeeOperations} from '../assets/employee-operations.js';

const SELF='10000000-0000-4000-8000-000000000001';
const OTHER='20000000-0000-4000-8000-000000000001';
const DEVICE='30000000-0000-4000-8000-000000000001';
const RECORD='40000000-0000-4000-8000-000000000001';
const UUID=/^[0-9a-f-]{36}$/;
const reason='Synthetic reviewed record';
const payment={occurred_at:'2026-09-20T17:30:00+08:00',payment_method:'cash',reference:'SYNTHETIC-ONLY',settlement_evidence:'Synthetic verified completed payment',employee_acknowledgment:'Synthetic employee receipt acknowledgment'};
const terms={installments:[{due_date:'2026-09-26',amount:'100.15'}],employee_acknowledgment:'Synthetic individually agreed terms',payroll_authorization:'Synthetic agreed payroll authorization'};
const schedule={effective_from:'2026-09-21',work_days:[1,2,3,4,5,6],start_time:'06:00',end_time:'15:00',meal_minutes:60,reason};
// Independent examples of the frozen typed backend commands. Each is built by the real DOM form.
const cases=[
 ['profile_save',{employee_id:OTHER,hire_date:'2025-01-01',effective_from:'2026-09-20',daily_rate:'600.25',payout_method:'bank',staff_manager:true,active:true,premium_pay_covered:true,holiday_pay_covered:true,tax_exempt:false,gp_partial_day_policy:'prorated',ordinary_leave_days_per_year:7,leave_eligible_from:'2025-06-01',classification_basis:reason}],
 ['schedule_save',{employee_id:OTHER,...schedule}],
 ['backup_save',{user_id:OTHER,starts_on:'2026-09-21',ends_on:'2026-09-25',duties:['review_requests','approve_payroll'],reason}],
 ['calendar_save',{work_date:'2026-09-21',day_kind:'ordinary',source:reason}],
 ['statutory_month_save',{employee_id:OTHER,month:'2026-09-01',sss_employee:'100.15',sss_employer:'200.25',philhealth_employee:'50.15',philhealth_employer:'50.15',pagibig_employee:'20.10',pagibig_employer:'20.10',employer_other:'0.00',prior_employee_deductions:'100.25',compensation_basis:reason,source:reason}],
 ['statutory_remittance',{month:'2026-09-01',agency:'sss',amount:'300.40',occurred_at:payment.occurred_at,reference:payment.reference,settlement_evidence:payment.settlement_evidence}],
 ['payroll_history_import',{employee_id:OTHER,year:2026,through_date:'2026-09-19',basic_earned:'10000.15',taxable_earned:'11000.25',tax_withheld:'100.10',thirteenth_paid:'0.00',other_benefits_paid:'1000.10',source:reason}],
 ['correction_request',{employee_id:SELF,work_date:'2026-09-19',clock_in:'2026-09-19T06:00:00+08:00',clock_out:'2026-09-19T15:00:00+08:00',unpaid_break_minutes:60,reason}],
 ['leave_request',{employee_id:SELF,work_date:'2026-09-22',minutes:240,leave_kind:'ordinary',reason,eligibility_evidence:'Synthetic eligibility evidence'}],
 ['shift_request',{employee_id:SELF,...schedule}],
 ['overtime_request',{employee_id:SELF,work_date:'2026-09-20',minutes:90,reason}],
 ['leave_conversion_request',{employee_id:SELF,as_of:'2026-12-31',minutes:2400,reason}],
 ['request_decide',{employee_id:OTHER,decision:'approved',reason,paid_minutes:240},'requests'],
 ['leave_balance_adjust',{employee_id:OTHER,as_of:'2026-09-20',minutes:2400,kind:'opening',reason}],
 ['task_save',{employee_id:OTHER,description:'Synthetic extra office task',due_date:'2026-09-25',notes:reason,related_client_id:RECORD,related_application_id:DEVICE}],
 ['task_progress',{employee_id:SELF,status:'done',reason},'tasks'],
 ['advance_request',{employee_id:SELF,amount:'100.15',reason,...terms}],
 ['advance_terms',{employee_id:SELF,...terms,reason},'advances'],
 ['advance_decide',{employee_id:OTHER,decision:'approved',reason},'advances'],
 ['advance_disburse',{employee_id:OTHER,...payment},'advances'],
 ['advance_repay',{employee_id:OTHER,amount:'100.15',occurred_at:payment.occurred_at,reference:payment.reference,settlement_evidence:payment.settlement_evidence},'advances'],
 ['shortage_report',{employee_id:OTHER,work_date:'2026-09-19',expected_cash:'500.15',accounted_cash:'400.00',evidence:reason}],
 ['shortage_respond',{employee_id:SELF,explanation:'Synthetic employee explanation'},'shortages'],
 ['shortage_decide',{employee_id:OTHER,decision:'dismissed',reason,response_opportunity:'Synthetic documented response opportunity'},'shortages'],
 ['payroll_prepare',{employee_id:OTHER,week_start:'2026-09-20',payroll_kind:'leave_conversion',leave_conversion_request_id:RECORD,withholding_override:'15.10',withholding_basis:reason,unworked_holiday_dates:['2026-09-21'],unworked_holiday_basis:reason,reason}],
 ['payroll_approve',{employee_id:OTHER,decision:'approved',reason},'payroll'],
 ['payroll_payment',{employee_id:OTHER,amount:'100.15',...payment,result:'completed'},'payroll'],
 ['payroll_adjustment',{employee_id:OTHER,original_payroll_id:RECORD,component:'lawful_recovery',amount:'-100.15',reason,lawful_basis:reason,responsibility_evidence:reason,employee_response:reason,maximum_authorized_recovery:'100.15',shortage_id:DEVICE},'payroll'],
 ['accounting_prepare',{preparation_kind:'journal',description:'Synthetic balanced journal draft',as_of:'2026-09-20',evidence:reason,lines:[{account_code:'5000',debit:'100.15',credit:'0.00'},{account_code:'1000',debit:'0.00',credit:'100.15'}],statement_balance:'100.15',ledger_balance:'100.15'}],
];
const captured=[];
function workspace(){
 const data={contract_version:1,actor:{user_id:SELF,employee_id:SELF,device_id:DEVICE,is_owner:true,is_staff_manager:false},capabilities:Object.fromEntries(['can_self_service','can_manage_staff','can_configure','can_prepare_payroll','can_approve_payroll','can_record_payments','can_assign_tasks','can_review_requests','can_review_shortages','can_prepare_accounting','can_view_statutory','can_report_shortage','can_record_advances'].map(key=>[key,true])),setup_missing:[],last_result:null,account_candidates:[{user_id:OTHER,full_name:'Synthetic colleague',username:'synthetic',roles:['collector']}]};
 for(const key of ['profiles','schedules','backups','calendar','statutory_months','statutory_remittances','payroll_history','attendance','attendance_days','requests','leave_balances','leave_ledger','tasks','advances','shortages','payroll','payments','accounting_preparations'])data[key]=[];
 data.profiles=[SELF,OTHER].map(id=>({id,employee_id:id,version:1,status:'active',allowed_actions:[],payload:{full_name:id===SELF?'Synthetic employee':'Synthetic colleague'},created_by:SELF}));return data;
}
function fill(container,values,root){
 for(const [name,value] of Object.entries(values)) {
  if(name==='employee_id'&&!container.querySelector('[name="employee_id"]'))continue;
  if(name==='original_payroll_id')continue;
  if(Array.isArray(value)){
   if(['work_days','duties'].includes(name)){for(const input of container.querySelectorAll(`[name="${name}"]`))input.checked=value.map(String).includes(input.value);continue;}
   const holder=container.querySelector(`[data-employee-rows="${name}"]`);assert.ok(holder,name);
   for(let index=0;index<value.length;index++){
    if(index>0)fire(root.querySelector(`[data-employee-add-row="${name}"]`),'click');
    const row=holder.querySelectorAll('[data-employee-row]')[index];fill(row,typeof value[index]==='string'?{date:value[index]}:value[index],root);
   }
   continue;
  }
  const input=container.querySelector(`[name="${name}"]`);assert.ok(input,name);
  input.value=input.getAttribute('type')==='datetime-local'?String(value).slice(0,16):String(value);
 }
}
for(const [action,expected,domain] of cases)test(`actual ${action} form serializes the strict command contract`,async()=>{
 const data=workspace();if(action==='profile_save')data.profiles=data.profiles.filter(item=>item.employee_id!==OTHER);
 if(domain)data[domain]=[{id:RECORD,employee_id:expected.employee_id,version:3,status:'pending',created_by:OTHER,allowed_actions:[action],payload:{request_kind:'leave'}}];
 const root=new Element();let body;const controller=new AbortController();
 const dispose=mountEmployeeOperations({root,session:{user:{id:SELF}},signal:controller.signal,api:{request:async(path,options={})=>{
  if(options.method==='POST'){body=options.body;return {request_id:body.request_id,id:body.id,version:body.expected_version+1,status:'accepted',message:'Synthetic saved'};}return data;
 }}});await setImmediate();
 fire(root.querySelector(`[${domain?'data-employee-action':'data-employee-create'}="${action}"]`),'click');
 const form=root.querySelector('[data-employee-form]');fill(form,expected,root);fire(form,'submit');await setImmediate();await setImmediate();
 assert.ok(body,root.textContent);assert.equal(body.action,action);assert.match(body.request_id,UUID);assert.match(body.id,UUID);
 assert.equal(body.expected_version,domain&&action!=='payroll_adjustment'?3:0);
 if(action==='profile_save')assert.equal(body.id,OTHER);else if(domain&&action!=='payroll_adjustment')assert.equal(body.id,RECORD);else assert.notEqual(body.id,RECORD);
 const {action:ignoredAction,request_id:ignoredRequest,id:ignoredId,expected_version:ignoredVersion,...actual}=body;
 assert.deepEqual(actual,expected);captured.push(body);dispose();
});

test('actual attendance button serializes the strict event contract',async()=>{
 const data=workspace();const root=new Element();let body;
 const dispose=mountEmployeeOperations({root,session:{user:{id:SELF}},now:()=>new Date('2026-09-20T00:00:00Z'),api:{request:async(path,options={})=>{
  if(options.method==='POST'){body=options.body;return {request_id:body.request_id,id:body.id,version:1,status:'accepted',message:'Synthetic accepted'};}return data;
 }}});await setImmediate();fire(root.querySelector('[data-employee-attendance="clock_in"]'),'click');await setImmediate();await setImmediate();
 const {request_id,id,...actual}=body;assert.match(request_id,UUID);assert.match(id,UUID);assert.deepEqual(actual,{action:'attendance_record',expected_version:0,employee_id:SELF,event_type:'clock_in',captured_at:'2026-09-20T00:00:00.000Z',device_id:DEVICE,previous_event_id:null,sequence:1,offline:false});captured.push(body);dispose();
});

after(async()=>{if(process.env.EMPLOYEE_WEB_CONTRACT_OUTPUT){assert.equal(captured.length,30);await writeFile(process.env.EMPLOYEE_WEB_CONTRACT_OUTPUT,JSON.stringify(captured,null,2));}});
