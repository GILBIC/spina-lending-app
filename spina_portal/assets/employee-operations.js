import {asArray, badge, emptyState, errorCard, escapeHtml as esc, loadingPanel, titleCase} from './ui.js';

const BASE = '/api/v1/employee-operations';
const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
const mounts = new WeakMap();
// In-memory, session-bound recovery survives a workspace switch without persisting payroll in browser storage.
const pendingBySession = new WeakMap();
const object = (value) => value !== null && typeof value === 'object' && !Array.isArray(value);
const field = (name, label, type = 'text', options = {}) => ({name, label, type, ...options});
const note = (name, label, optional = false) => field(name, label, 'textarea', {optional});
const date = (name, label) => field(name, label, 'date');
const amount = (name, label, optional = false) => field(name, label, 'money', {optional});
const choice = (name, label, values, optional = false) => field(name, label, 'select', {values, optional});
const reason = note('reason', 'Reason');
const minutes = (name, label, optional = false) => field(name, label, 'integer', {min:0, max:1440, optional});
const timestamp = (name, label) => field(name, `${label} (Asia/Manila)`, 'datetime');
const method = choice('payment_method', 'Payment method', ['cash','gcash','bank']);
const installmentFields = [date('due_date','Due date'), amount('amount','Installment (PHP)')];
const installments = field('installments','Agreed repayment installments','rows',{fields:installmentFields,min:1,max:104});
const scheduleFields = [date('effective_from','Effective from'),field('work_days','Working days','days'),field('start_time','Shift starts (Asia/Manila)','time'),field('end_time','Shift ends (Asia/Manila)','time'),minutes('meal_minutes','Normally unpaid meal minutes'),reason];
const decisionFields = [choice('decision','Decision',['approved','rejected']),reason];
const acknowledgment = note('employee_acknowledgment','Employee acknowledgment / agreement evidence');
const payrollAuthorization = note('payroll_authorization','Agreed payroll repayment authorization');
const paymentFields = [timestamp('occurred_at','Payment time'),method,note('reference','Payment reference'),note('settlement_evidence','Verified settlement evidence'),acknowledgment];

// This is the finite v1 employee command contract, not an arbitrary payload editor.
const FORMS = {
  profile_save: {label:'Set up employee profile and rate',capability:'can_configure',subject:'account',group:'Setup',fields:[date('hire_date','Service / hire date'),date('effective_from','Rate and classification effective from'),amount('daily_rate','Actual daily rate (PHP)'),choice('payout_method','Preferred payout method',['cash','gcash','bank']),field('staff_manager','Combined staff-manager responsibility','boolean'),field('active','Employee profile active','boolean'),field('premium_pay_covered','Reviewed premium-pay coverage','boolean'),field('holiday_pay_covered','Reviewed holiday-pay coverage','boolean'),field('tax_exempt','Reviewed tax exemption','boolean'),choice('gp_partial_day_policy','Established partial-day performance-benefit policy',['prorated','full_day']),field('ordinary_leave_days_per_year','Better existing annual ordinary leave days (blank uses five)','integer',{min:5,max:365,optional:true}),field('leave_eligible_from','Earlier agreed leave eligibility date (optional)','date',{optional:true}),note('classification_basis','Reviewed classification and existing-benefit basis')]},
  schedule_save: {label:'Set employee work schedule',capability:'can_configure',subject:'employee',group:'Setup',fields:scheduleFields},
  backup_save: {label:'Designate independent backup',capability:'can_configure',group:'Setup',fields:[field('user_id','Backup account','account'),date('starts_on','First authorized date'),date('ends_on','Last authorized date'),field('duties','Explicit backup duties','checks',{values:['review_requests','approve_payroll','approve_advances','assign_tasks','prepare_payroll']}),reason]},
  calendar_save: {label:'Record reviewed calendar day',capability:'can_configure',group:'Setup',fields:[date('work_date','Calendar date'),choice('day_kind','Day classification',['ordinary','special_working','special_nonworking','regular_holiday','double_regular_holiday']),note('source','Effective official calendar source and reviewed coverage')]},
  statutory_month_save: {label:'Set reviewed monthly contributions',capability:'can_configure',subject:'employee',group:'Setup',fields:[date('month','Contribution month (first day)'),...['sss_employee','sss_employer','philhealth_employee','philhealth_employer','pagibig_employee','pagibig_employer','employer_other'].map(name=>amount(name,`${titleCase(name)} (PHP)`)),amount('prior_employee_deductions','Employee contributions already collected outside Spina this month (PHP; enter 0 if none)',true),note('compensation_basis','Reviewed agency compensation bases'),note('source','Effective official schedules and review evidence')]},
  statutory_remittance: {label:'Record actual agency remittance',capability:'can_configure',group:'Setup',fields:[date('month','Contribution month (first day)'),choice('agency','Agency',['sss','philhealth','pagibig','bir']),amount('amount','Amount actually remitted (PHP)'),timestamp('occurred_at','Remittance time'),note('reference','Agency payment reference'),note('settlement_evidence','Verified payment evidence')]},
  payroll_history_import: {label:'Import verified payroll history',capability:'can_configure',subject:'employee',group:'Setup',fields:[field('year','Payroll year','integer',{min:2000,max:2200}),date('through_date','Verified history through date'),...['basic_earned','taxable_earned','tax_withheld','thirteenth_paid','other_benefits_paid'].map(name=>amount(name,`${titleCase(name)} (PHP)`)),note('source','Verified historical payroll records and review evidence')]},
  correction_request: {label:'Request attendance correction',capability:'can_self_service',subject:'self',group:'Time and leave',fields:[date('work_date','Work date'),timestamp('clock_in','Correct clock-in'),timestamp('clock_out','Correct clock-out'),minutes('unpaid_break_minutes','Actual unpaid meal-break minutes'),reason]},
  leave_request: {label:'Request leave',capability:'can_self_service',subject:'self',group:'Time and leave',fields:[date('work_date','Leave date'),minutes('minutes','Scheduled leave minutes'),choice('leave_kind','Leave category',['ordinary','maternity','paternity','solo_parent','vawc','special_women','unpaid']),reason,note('eligibility_evidence','Special-leave eligibility evidence',true)]},
  shift_request: {label:'Request a shift change',capability:'can_self_service',subject:'self',group:'Time and leave',fields:scheduleFields},
  overtime_request: {label:'Request overtime review',capability:'can_self_service',subject:'self',group:'Time and leave',fields:[date('work_date','Work date'),minutes('minutes','Overtime minutes for review'),reason]},
  leave_conversion_request: {label:'Request unused-leave conversion',capability:'can_self_service',subject:'self',group:'Time and leave',fields:[date('as_of','Conversion date'),field('minutes','Eligible unused minutes requested (480 per full day)','integer',{min:1,max:1000000}),reason]},
  request_decide: {label:'Review request',fields:[...decisionFields,minutes('paid_minutes','Reviewed payable minutes (when applicable)',true)]},
  leave_balance_adjust: {label:'Record verified leave opening / correction',capability:'can_configure',subject:'employee',group:'Setup',fields:[date('as_of','Balance date'),field('minutes','Verified minutes (negative for correction)','integer',{min:-1000000,max:1000000}),choice('kind','Ledger entry',['opening','correction']),reason]},
  task_save: {label:'Assign an extra task',capability:'can_assign_tasks',subject:'employee',group:'Tasks',fields:[note('description','Task description'),date('due_date','Due date'),note('notes','Supporting notes',true),field('related_client_id','Related Client ID (optional)','uuid',{optional:true}),field('related_application_id','Related application ID (optional)','uuid',{optional:true})]},
  task_progress: {label:'Update task progress',fields:[choice('status','Task status',['todo','in_progress','done','cancelled']),reason]},
  advance_request: {label:'Request a salary advance',capability:'can_self_service',subject:'self',group:'Advances',fields:[amount('amount','Requested principal (PHP)'),reason,installments,acknowledgment,payrollAuthorization]},
  advance_terms: {label:'Request revised advance terms',fields:[installments,acknowledgment,payrollAuthorization,reason]},
  advance_decide: {label:'Review advance and terms',fields:decisionFields},
  advance_disburse: {label:'Record actual advance disbursement',fields:paymentFields},
  advance_repay: {label:'Record actual advance repayment',fields:[amount('amount','Principal repaid (PHP)'),timestamp('occurred_at','Repayment time'),note('reference','Repayment reference'),note('settlement_evidence','Verified repayment evidence')]},
  shortage_report: {label:'Report a cash discrepancy',capability:'can_report_shortage',subject:'employee',group:'Shortages',fields:[date('work_date','Accountable collection date'),amount('expected_cash','Expected accountable cash (PHP)'),amount('accounted_cash','Counted / remitted cash (PHP)'),note('evidence','Accountable-cash evidence')]},
  shortage_respond: {label:'Submit my shortage explanation',fields:[note('explanation','My explanation and supporting evidence')]},
  shortage_decide: {label:'Decide shortage case',fields:[choice('decision','Decision',['confirmed','dismissed','reversed']),reason,note('response_opportunity','Employee opportunity to respond and evidence considered')]},
  payroll_prepare: {label:'Prepare employee payroll',capability:'can_prepare_payroll',subject:'employee',group:'Payroll',fields:[date('week_start','Payroll week starts (Sunday)'),choice('payroll_kind','Payroll type',['weekly','thirteenth_month','separation','leave_conversion']),field('leave_conversion_request_id','Approved leave-conversion request ID','uuid',{optional:true}),amount('withholding_override','Reviewed withholding override (PHP)',true),note('withholding_basis','Withholding override basis',true),field('unworked_holiday_dates','Eligible unworked holiday dates','rows',{fields:[date('date','Holiday date')],min:0,max:7,scalar:true}),note('unworked_holiday_basis','Unworked-holiday eligibility basis',true),reason]},
  payroll_approve: {label:'Review employee payroll',fields:decisionFields},
  payroll_payment: {label:'Record actual salary payout',fields:[amount('amount','Actual payout amount (PHP)'),timestamp('occurred_at','Payment time'),method,note('reference','Transfer / cash reference',true),note('settlement_evidence','Verified settlement evidence (required for completed transfer)',true),note('employee_acknowledgment','Employee acknowledgment (required for completed cash payout)',true),choice('result','Observed payment result',['completed','pending','failed'])]},
  payroll_adjustment: {label:'Prepare linked payroll adjustment',fields:[choice('component','Component being adjusted',['basic_pay','leave_pay','overtime','premium_pay','performance_benefit','tax','statutory','advance_repayment','lawful_recovery','other']),field('amount','Signed adjustment (PHP)','signed-money'),reason,note('lawful_basis','Lawful payroll-recovery basis (when relevant)',true),note('responsibility_evidence','Individual responsibility evidence',true),note('employee_response','Employee response and fair review',true),amount('maximum_authorized_recovery','Authorized recovery cap (PHP)',true),field('shortage_id','Linked shortage case ID','uuid',{optional:true})]},
  accounting_prepare: {label:'Prepare accounting draft',capability:'can_prepare_accounting',group:'Accounting',fields:[choice('preparation_kind','Preparation type',['journal','reconciliation']),note('description','Draft description'),date('as_of','Accounting date'),note('evidence','Supporting evidence'),field('lines','Journal draft lines','rows',{fields:[field('account_code','Account code'),amount('debit','Debit (PHP)'),amount('credit','Credit (PHP)')],min:0,max:100}),amount('statement_balance','Statement balance (PHP)',true),amount('ledger_balance','Ledger balance (PHP)',true)]},
};

const COLLECTIONS = {
  profiles:'Employee profiles',schedules:'Effective work schedules',backups:'Independent backup grants',calendar:'Reviewed calendar',statutory_months:'Monthly statutory review',statutory_remittances:'Agency remittance evidence',payroll_history:'Verified payroll history',attendance:'Original attendance events',requests:'Requests and decisions',leave_ledger:'Leave ledger',tasks:'Extra tasks',advances:'Advances and repayments',shortages:'Shortage cases',payroll:'Payslips and payroll',payments:'Actual payment evidence',accounting_preparations:'Accounting preparations',
};
const CAPABILITIES = ['can_self_service','can_manage_staff','can_configure','can_prepare_payroll','can_approve_payroll','can_record_payments','can_assign_tasks','can_review_requests','can_review_shortages','can_prepare_accounting','can_view_statutory','can_report_shortage','can_record_advances'];
const MONEY_FIELDS = new Set(['daily_rate','amount','expected_cash','accounted_cash','shortage_amount','disbursed_amount','repaid_amount','outstanding_amount','gross_pay','deductions','net_pay','paid_amount','balance_due','statement_balance','ledger_balance','sss_employee','sss_employer','philhealth_employee','philhealth_employer','pagibig_employee','pagibig_employer','employer_other','maximum_authorized_recovery','basic_earned','taxable_earned','tax_withheld','thirteenth_paid','other_benefits_paid','debit','credit']);
const LABELS = Object.fromEntries(Object.values(FORMS).flatMap(form=>form.fields.map(item=>[item.name,item.label])));
Object.assign(LABELS,{full_name:'Employee',status:'Status',working_minutes:'Accepted working minutes',unpaid_break_minutes:'Unpaid break minutes',event_type:'Event',captured_at:'Captured at',received_at:'Received by server',decision_reason:'Review decision reason',request_kind:'Request category',disbursed_amount:'Principal disbursed',repaid_amount:'Principal repaid',outstanding_amount:'Outstanding principal',shortage_amount:'Recorded shortage',gross_pay:'Gross pay',deductions:'Deductions',net_pay:'Net pay',paid_amount:'Completed payments',balance_due:'Still due',period_end:'Period ends',journal_entry_id:'General Journal draft reference',explanation:'Employee explanation',approved_by:'Approved by',decided_by:'Decision by',recorded_by:'Payment recorded by',disbursed_at:'Disbursed at',original_payroll_id:'Original payroll reference',approval_reason:'Approval reason'});
Object.assign(LABELS,{minutes:'Minutes',amount:'Amount (PHP)',work_date:'Work date',as_of:'As of',description:'Description',reason:'Reason',source:'Reviewed source',reference:'Reference',evidence:'Supporting evidence',employee_acknowledgment:'Employee acknowledgment',settlement_evidence:'Verified settlement evidence',paid_minutes:'Reviewed payable minutes'});

function currency(value) {
  if(typeof value!=='string'||!/^[-+]?\d+(?:\.\d+)?$/.test(value))return esc(value??'Not recorded');
  const [whole,fraction]=value.split('.');
  return `PHP ${esc(whole.replace(/\B(?=(\d{3})+(?!\d))/g,','))}${fraction===undefined?'':`.${esc(fraction)}`}`;
}
function display(name,value) {
  if(MONEY_FIELDS.has(name))return currency(value);
  if(typeof value==='boolean')return value?'Yes':'No';
  if(value===null||value===undefined||value==='')return 'Not recorded';
  return esc(value);
}
function manilaDate(value) {
  const instant=new Date(value);
  return Number.isNaN(instant.getTime())?null:new Intl.DateTimeFormat('en-CA',{timeZone:'Asia/Manila'}).format(instant);
}
function validateWorkspace(value,session) {
  if(!object(value)||value.contract_version!==1||!object(value.actor)||!UUID.test(value.actor.user_id)
    ||value.actor.user_id!==session?.user?.id||!object(value.capabilities)
    ||!CAPABILITIES.every(key=>typeof value.capabilities[key]==='boolean')
    ||!Array.isArray(value.setup_missing)||!value.setup_missing.every(item=>typeof item==='string')
    ||![...Object.keys(COLLECTIONS),'attendance_days','leave_balances','account_candidates'].every(key=>Array.isArray(value[key]))) {
    throw new Error('Employee records could not be verified for this account. Refresh to try again.');
  }
  for(const key of Object.keys(COLLECTIONS))for(const record of value[key]) {
    if(!object(record)||!UUID.test(record.id)||!Number.isSafeInteger(record.version)||record.version<1
      ||!(record.employee_id===null||UUID.test(record.employee_id))||!object(record.payload)
      ||!Array.isArray(record.allowed_actions)||!record.allowed_actions.every(action=>typeof action==='string')) {
      throw new Error('The server returned incomplete employee records. Refresh to try again.');
    }
  }
  return value;
}
function matchesResult(result,command) {
  return object(result)&&result.request_id===command.request_id&&result.id===command.id
    &&Number.isSafeInteger(result.version)&&result.version>command.expected_version
    &&['accepted','pending_review'].includes(result.status)&&typeof result.message==='string';
}
function createAllowed(workspace,action) {
  const form=FORMS[action];return Boolean(form?.capability&&workspace.capabilities[form.capability]===true
    &&(form.subject!=='self'||UUID.test(workspace.actor.employee_id)));
}
function recordAllowed(workspace,record,action) {
  if(!FORMS[action]||!record.allowed_actions.includes(action))return false;
  const self=record.employee_id===workspace.actor.user_id;
  if(self&&['payroll_approve','advance_decide','shortage_decide'].includes(action))return false;
  if(['advance_disburse','advance_repay'].includes(action)&&!workspace.capabilities.can_record_advances)return false;
  if(action==='payroll_payment'&&!workspace.capabilities.can_record_payments)return false;
  return true;
}
function employeeName(workspace,id) {
  return workspace.profiles.find(record=>record.employee_id===id)?.payload.full_name
    ||workspace.account_candidates.find(record=>record.user_id===id)?.full_name||'Employee';
}
function repeatMarkup(spec,values=[]) {
  const rows=values.length?values:[spec.scalar?'':{}];
  return `<div data-employee-rows="${spec.name}">${rows.map(value=>`<div class="employee-form-row" data-employee-row>${spec.fields.map(item=>inputMarkup({...item,optional:true},spec.scalar?{date:value}:value,[])).join('')}</div>`).join('')}</div><button type="button" class="button button-outline" data-employee-add-row="${spec.name}">Add ${spec.name==='installments'?'installment':spec.scalar?'date':'line'}</button><p class="meta">Empty rows are ignored.</p>`;
}
function inputMarkup(spec,values={},accounts=[]) {
  const value=values[spec.name]??'';
  const required=spec.optional?'':' required';
  const attrs=`name="${spec.name}"${required}`;
  if(spec.type==='rows')return `<fieldset><legend>${esc(spec.label)}</legend>${repeatMarkup(spec,asArray(value))}</fieldset>`;
  if(spec.type==='days'||spec.type==='checks') {
    const options=spec.type==='days'?[[1,'Monday'],[2,'Tuesday'],[3,'Wednesday'],[4,'Thursday'],[5,'Friday'],[6,'Saturday'],[7,'Sunday']]:spec.values.map(item=>[item,titleCase(item)]);
    return `<fieldset><legend>${esc(spec.label)}</legend>${options.map(([key,label])=>`<label class="employee-checkbox"><input type="checkbox" name="${spec.name}" value="${esc(key)}"${asArray(value).includes(key)?' checked':''}>${esc(label)}</label>`).join('')}</fieldset>`;
  }
  if(['select','boolean','account'].includes(spec.type)) {
    const options=spec.type==='boolean'?[[true,'Yes'],[false,'No']]:spec.type==='account'?accounts.map(item=>[item.user_id,`${item.full_name} (${item.username||'account'})`]):spec.values.map(item=>[item,titleCase(item)]);
    return `<label>${esc(spec.label)}<select ${attrs}><option value="">Choose…</option>${options.map(([key,label])=>`<option value="${esc(key)}"${String(value)===String(key)?' selected':''}>${esc(label)}</option>`).join('')}</select></label>`;
  }
  if(spec.type==='textarea')return `<label>${esc(spec.label)}<textarea ${attrs} maxlength="2000">${esc(value)}</textarea></label>`;
  const type=spec.type==='datetime'?'datetime-local':spec.type==='integer'?'number':['date','time'].includes(spec.type)?spec.type:'text';
  let shown=value;
  if(spec.type==='datetime'&&value) {
    const instant=new Date(value);if(!Number.isNaN(instant.getTime()))shown=new Date(instant.getTime()+8*60*60*1000).toISOString().slice(0,16);
  }
  return `<label>${esc(spec.label)}<input ${attrs} type="${type}" value="${esc(shown)}"${spec.type==='integer'?` min="${spec.min}" max="${spec.max}" step="1"`:''}${['money','signed-money'].includes(spec.type)?' inputmode="decimal"':''} autocomplete="off"></label>`;
}
function readFields(container,fields,validate=true) {
  const result={};
  for(const spec of fields) {
    if(spec.type==='rows') {
      const parent=container.querySelector(`[data-employee-rows="${spec.name}"]`);
      const entries=[...parent.querySelectorAll('[data-employee-row]')].filter(row=>spec.fields.some(item=>row.querySelector(`[name="${item.name}"]`).value.trim()));
      if(validate&&(entries.length<spec.min||entries.length>spec.max))throw new Error(`${spec.label}: enter ${spec.min}–${spec.max} complete rows.`);
      result[spec.name]=entries.map(row=>{const value=readFields(row,spec.fields,validate);return spec.scalar?value.date:value;});continue;
    }
    if(spec.type==='days'||spec.type==='checks') {
      result[spec.name]=[...container.querySelectorAll(`[name="${spec.name}"]`)].filter(input=>input.checked).map(input=>spec.type==='days'?Number(input.value):input.value);
      if(validate&&spec.type==='days'&&(result[spec.name].length<1||result[spec.name].length>6))throw new Error('Choose one to six working days and preserve the weekly rest day.');
      continue;
    }
    const raw=String(container.querySelector(`[name="${spec.name}"]`)?.value??'').trim();
    if(!raw&&spec.optional)continue;
    if(validate&&!raw)throw new Error(`${spec.label} is required.`);
    let value=raw;
    if(spec.type==='integer') {value=raw===''?'':Number(raw);if(validate&&(!Number.isSafeInteger(value)||value<spec.min||value>spec.max))throw new Error(`${spec.label} must be a whole number from ${spec.min} to ${spec.max}.`);}
    if(spec.type==='money'||spec.type==='signed-money') {
      const pattern=spec.type==='money'?/^\d{1,12}(?:\.\d{1,2})?$/:/^-?\d{1,12}(?:\.\d{1,2})?$/;
      if(validate&&!pattern.test(raw))throw new Error(`${spec.label} must be an exact amount with at most two decimal places.`);
    }
    if(spec.type==='boolean') {if(validate&&!['true','false'].includes(raw))throw new Error(`Choose Yes or No for ${spec.label}.`);value=raw==='true';}
    if(spec.type==='select'&&validate&&!spec.values.includes(raw))throw new Error(`Choose a valid ${spec.label.toLowerCase()}.`);
    if((spec.type==='uuid'||spec.type==='account')&&validate&&!UUID.test(raw))throw new Error(`Select a valid ${spec.label.toLowerCase()}.`);
    if(spec.type==='date'&&validate&&!/^\d{4}-\d{2}-\d{2}$/.test(raw))throw new Error(`Enter ${spec.label.toLowerCase()}.`);
    if(spec.type==='time'&&validate&&!/^([01]\d|2[0-3]):[0-5]\d$/.test(raw))throw new Error(`Enter ${spec.label.toLowerCase()}.`);
    if(spec.type==='datetime') {if(validate&&!/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(?::\d{2})?$/.test(raw))throw new Error(`Enter ${spec.label.toLowerCase()}.`);value=raw?`${raw.length===16?`${raw}:00`:raw}+08:00`:'';}
    if(validate&&raw.length>2000)throw new Error(`${spec.label} must contain at most 2,000 characters.`);
    result[spec.name]=value;
  }
  return result;
}

function recordMarkup(workspace,record,index) {
  const data=record.payload;
  const history=asArray(workspace.history).filter(item=>object(item)&&item.record_id===record.id&&item.domain===index.split(':')[0]);
  const scalar=Object.entries(data).filter(([key,value])=>LABELS[key]&&['string','number','boolean'].includes(typeof value));
  const actions=record.allowed_actions.filter(action=>recordAllowed(workspace,record,action));
  const components=asArray(data.components);
  const rows=(name,label,fields)=>asArray(data[name]).length?`<h4>${label}</h4><div class="table-wrap"><table><thead><tr>${fields.map(key=>`<th>${esc(key==='due_date'?'Due date':titleCase(key))}</th>`).join('')}</tr></thead><tbody>${data[name].map(row=>`<tr>${fields.map(key=>`<td>${display(key,row[key])}</td>`).join('')}</tr>`).join('')}</tbody></table></div>`:'';
  const original=data.request_kind==='correction'?`<h4>Original recorded events for the requested date</h4>${workspace.attendance.filter(event=>event.employee_id===record.employee_id&&manilaDate(event.payload.captured_at)===data.work_date).map(event=>`<p>${esc(titleCase(event.payload.event_type))} · ${esc(event.payload.captured_at)} · ${esc(titleCase(event.status))}</p>`).join('')||'<p>No original events recorded.</p>'}`:'';
  const proposed=object(data.proposed_terms)?`<div class="notice-card"><h4>Proposed advance terms awaiting review</h4><p>${esc(data.proposed_terms.reason)}</p><p>Employee agreement: ${esc(data.proposed_terms.employee_acknowledgment)}</p><p>Payroll authorization: ${esc(data.proposed_terms.payroll_authorization)}</p><table><thead><tr><th>Proposed due date</th><th>Proposed installment</th></tr></thead><tbody>${asArray(data.proposed_terms.installments).map(item=>`<tr><td>${esc(item.due_date)}</td><td>${currency(item.amount)}</td></tr>`).join('')}</tbody></table></div>`:'';
  return `<article class="data-card employee-record"><div class="section-heading"><h3>${esc(record.employee_id?employeeName(workspace,record.employee_id):COLLECTIONS[index.split(':')[0]])}</h3>${badge(record.status)}</div>
    <p class="meta">Updated ${esc(record.updated_at||'')}</p><p class="meta">Record reference: ${esc(record.id)}</p>
    <dl class="employee-details">${scalar.map(([key,value])=>`<div><dt>${esc(LABELS[key])}</dt><dd>${display(key,value)}</dd></div>`).join('')}</dl>
    ${Array.isArray(data.work_days)?`<p>Working days: ${data.work_days.map(day=>['','Monday','Tuesday','Wednesday','Thursday','Friday','Saturday','Sunday'][day]||'Unknown').map(esc).join(', ')}</p>`:''}
    ${Array.isArray(data.duties)?`<p>Authorized duties: ${data.duties.map(value=>esc(titleCase(value))).join(', ')}</p>`:''}
    ${components.length?`<h4>Server-calculated salary components</h4><table><tbody>${components.map(component=>`<tr><th>${esc(component.label)}</th><td>${currency(component.amount)}</td></tr>`).join('')}</tbody></table>`:''}
    ${original}${rows('installments','Current agreed principal repayment schedule',['due_date','amount'])}${proposed}${rows('repayment_history','Recorded repayments',['amount','occurred_at','reference','source'])}${rows('lines','Journal draft lines',['account_code','debit','credit'])}
    ${history.length?`<details><summary>Record history (${history.length})</summary>${history.map(item=>`<article><p>${esc(item.created_at)} · ${esc(titleCase(item.action))} · ${esc(titleCase(item.status))} · Revision ${esc(item.version)}</p><dl class="employee-details">${Object.entries(object(item.payload)?item.payload:{}).filter(([key,value])=>LABELS[key]&&['string','number','boolean'].includes(typeof value)).map(([key,value])=>`<div><dt>${esc(LABELS[key])}</dt><dd>${display(key,value)}</dd></div>`).join('')}</dl></article>`).join('')}</details>`:''}
    ${asArray(data.issues).length?`<div class="notice-card warning"><strong>Review required</strong><ul>${data.issues.map(issue=>`<li>${esc(issue)}</li>`).join('')}</ul></div>`:''}
    ${actions.length?`<div class="inline-actions">${actions.map(action=>`<button type="button" class="button button-secondary" data-employee-action="${action}" data-employee-record="${index}">${esc(FORMS[action].label)}</button>`).join('')}</div>`:''}
  </article>`;
}

export function mountEmployeeOperations({root,api,session,signal,now=()=>new Date()}) {
  if(!root)return ()=>{};
  mounts.get(root)?.();
  const controller=new AbortController();let disposed=false;let busy=false;let stale=false;let workspace=null;let selected=null;let removers=[];let pending=pendingBySession.get(session)||null;
  const listen=(element,event,handler)=>{if(element){element.addEventListener(event,handler);removers.push(()=>element.removeEventListener(event,handler));}};
  function clear(){for(const remove of removers)remove();removers=[];for(const input of [...root.querySelectorAll('input'),...root.querySelectorAll('textarea'),...root.querySelectorAll('select')])input.value='';root.innerHTML='';}
  function dispose(){if(disposed)return;disposed=true;controller.abort();workspace=null;selected=null;clear();signal?.removeEventListener('abort',dispose);globalThis.removeEventListener?.('online',connection);globalThis.removeEventListener?.('offline',connection);if(mounts.get(root)===dispose)mounts.delete(root);}
  function message(text,error=false){const element=root.querySelector('[data-employee-status]');if(element){if(error)element.innerHTML=errorCard(text);else element.textContent=text;}}
  function denied(error){if([401,403].includes(error?.status)){pending=null;pendingBySession.delete(session);workspace=null;selected=null;clear();root.innerHTML=errorCard(error);return true;}return false;}
  function connection(){if(disposed)return;lock();const notice=root.querySelector('[data-employee-connection]');if(notice)notice.textContent=globalThis.navigator?.onLine===false?'Offline: Web changes are unavailable. Reconnect and refresh.':'Web changes are submitted online. Android can capture attendance offline.';}
  function lock(){
    const offline=globalThis.navigator?.onLine===false;
    for(const node of [...root.querySelectorAll('button'),...root.querySelectorAll('input'),...root.querySelectorAll('select'),...root.querySelectorAll('textarea')]) {
      const recovery=node.getAttribute('data-employee-check')!==null||node.getAttribute('data-employee-retry')!==null;
      node.disabled=busy||offline||Boolean(pending&&!recovery)||Boolean(stale&&!recovery&&node.getAttribute('data-employee-refresh')===null);
    }
  }
  function setPending(value){pending=value;if(value)pendingBySession.set(session,value);else pendingBySession.delete(session);}
  async function load({recover=Boolean(pending),successMessage=''}={}) {
    if(disposed||busy)return;busy=true;lock();
    try {
      const value=await api.request(`${BASE}/workspace${recover&&pending?`?request_id=${encodeURIComponent(pending.request_id)}`:''}`,{signal:controller.signal});
      if(disposed)return;workspace=validateWorkspace(value,session);stale=false;
      if(recover&&pending&&matchesResult(workspace.last_result,pending)) {successMessage=workspace.last_result.message;setPending(null);selected=null;}
      render();if(successMessage)message(successMessage);
      else if(pending)message('The result is not confirmed. Check the saved result, or retry the same unchanged request. Do not start another payment.');
    } catch(error){if(disposed)return;stale=true;if(!denied(error)){if(!workspace){clear();root.innerHTML=`${errorCard(error)}<button type="button" data-employee-refresh>Refresh employee records</button>`;listen(root.querySelector('[data-employee-refresh]'),'click',()=>load());}else message(error,true);}}
    finally{busy=false;if(!disposed)lock();}
  }
  async function execute(command) {
    if(disposed||busy||globalThis.navigator?.onLine===false)return;
    setPending(command);busy=true;lock();message('Saving employee record…');let accepted='';let uncertain=false;
    try {
      const result=await api.request(`${BASE}/actions`,{method:'POST',body:command,financial:true,signal:controller.signal});
      if(disposed)return;if(!matchesResult(result,command))throw Object.assign(new Error('The saved response could not be confirmed.'),{code:'network_uncertain'});
      accepted=result.message;setPending(null);selected=null;
    } catch(error){
      if(disposed)return;if(denied(error))return;
      uncertain=error?.code==='network_uncertain'||!error?.status||error.status>=500;
      if(!uncertain){setPending(null);if(error.status===409){selected=null;stale=true;}render();message(error,true);}
    } finally{busy=false;if(!disposed)lock();}
    if(disposed||!workspace)return;
    if(accepted){render();await load({recover:false,successMessage:accepted});}
    else if(uncertain){render();await load({recover:true});}
  }
  function editor(action,record=null) {
    if(busy||pending||stale||disposed||!(record?recordAllowed(workspace,record,action):createAllowed(workspace,action)))return;
    selected={action,record};render();root.querySelector('[data-employee-editor]')?.scrollIntoView?.({block:'nearest'});
  }
  function editorMarkup(){
    if(!selected)return '';
    const {action,record}=selected;const form=FORMS[action];let fields=form.fields;
    if(action==='request_decide')fields=[choice('decision','Decision',record.employee_id===workspace.actor.user_id?['cancelled']:['approved','rejected','cancelled']),reason,minutes('paid_minutes','Reviewed payable minutes (when applicable)',true)];
    const profiles=workspace.profiles.filter(item=>action!=='shortage_report'||workspace.capabilities.can_manage_staff||item.employee_id===workspace.actor.user_id);
    const target=record?`<p>Employee: ${esc(employeeName(workspace,record.employee_id))}</p>`:form.subject==='self'?`<p>For: ${esc(employeeName(workspace,workspace.actor.employee_id))}</p>`:form.subject?inputMarkup(field('employee_id','Employee account', 'account'),{},form.subject==='account'?workspace.account_candidates:profiles.map(item=>({user_id:item.employee_id,full_name:item.payload.full_name} ))):'';
    const values=action==='advance_terms'&&object(record?.payload.proposed_terms)?record.payload.proposed_terms:record?.payload??{};
    return `<section class="employee-editor" data-employee-editor><h3>${esc(form.label)}</h3>${record||form.subject==='self'?target:''}
      ${action==='payroll_payment'?'<p>Record a payment that actually occurred. This form does not initiate a transfer. A reference alone is insufficient evidence of completion.</p>':''}
      ${action==='payroll_adjustment'?'<p>This creates a linked adjustment. Shortage recovery requires a lawful basis, individual responsibility, employee response and an authorized cap; it is never automatic.</p>':''}
      ${action==='accounting_prepare'?'<p>Preparation creates a draft for authorized review. It does not post a journal or confirm settlement.</p>':''}
      ${fields.some(spec=>spec.type==='integer'&&/minutes/.test(spec.name))?'<p class="meta">For an eight-hour schedule, a full day is 480 minutes and half a day is 240 minutes. Enter the actual applicable time.</p>':''}
      <form class="entry-form" data-employee-form="${action}">${!record&&form.subject&&form.subject!=='self'?target:''}${fields.map(spec=>inputMarkup(spec,values,workspace.account_candidates)).join('')}<div class="inline-actions"><button type="submit" class="button button-primary">${esc(form.label)}</button><button type="button" class="button button-outline" data-employee-cancel>Cancel editing</button></div></form></section>`;
  }
  function buildCommand(form){
    const {action,record}=selected;const definition=FORMS[action];
    let fields=definition.fields;
    if(action==='request_decide')fields=[choice('decision','Decision',record.employee_id===workspace.actor.user_id?['cancelled']:['approved','rejected','cancelled']),reason,minutes('paid_minutes','Reviewed payable minutes',true)];
    const body=readFields(form,fields);
    let employeeId=record?.employee_id;
    if(!record&&definition.subject==='self')employeeId=workspace.actor.employee_id;
    else if(!record&&definition.subject)employeeId=form.querySelector('[name="employee_id"]')?.value;
    if(definition.subject||record?.employee_id){if(!UUID.test(employeeId))throw new Error('Select the employee account.');body.employee_id=employeeId;}
    const adjustment=action==='payroll_adjustment';
    const command={action,request_id:crypto.randomUUID(),id:adjustment?crypto.randomUUID():record?.id||(action==='profile_save'?employeeId:crypto.randomUUID()),expected_version:adjustment?0:record?.version??0,...body};
    if(adjustment)command.original_payroll_id=record.id;
    return command;
  }
  async function attendance(eventType){
    if(disposed||busy||pending||stale||!workspace?.capabilities.can_self_service||globalThis.navigator?.onLine===false)return;
    if(!UUID.test(workspace.actor.device_id)||!UUID.test(workspace.actor.employee_id)){message(new Error('The current registered employee device could not be verified. Refresh before recording attendance.'),true);return;}
    const capturedAt=now().toISOString();
    const today=workspace.attendance.filter(item=>item.employee_id===workspace.actor.employee_id&&manilaDate(item.payload.captured_at)===manilaDate(capturedAt));
    const prior=[...today].sort((a,b)=>Date.parse(b.payload.captured_at)-Date.parse(a.payload.captured_at)||b.id.localeCompare(a.id))[0];
    const deviceEvents=today.filter(item=>item.payload.device_id===workspace.actor.device_id);
    const sequence=deviceEvents.length?Math.max(...deviceEvents.map(item=>item.payload.sequence))+1:1;
    if(!Number.isSafeInteger(sequence)||sequence<1){message(new Error('Attendance order could not be verified. Refresh the record.'),true);return;}
    await execute({action:'attendance_record',request_id:crypto.randomUUID(),id:crypto.randomUUID(),expected_version:0,employee_id:workspace.actor.employee_id,event_type:eventType,captured_at:capturedAt,device_id:workspace.actor.device_id,previous_event_id:prior?.id??null,sequence,offline:false});
  }
  function render(){
    clear();if(!workspace)return;
    const available=Object.entries(FORMS).filter(([action])=>createAllowed(workspace,action));
    const groups=[...new Set(available.map(([,form])=>form.group))];
    root.innerHTML=`<div class="section-heading"><div><h2>Employee work and pay</h2><p>Private records and actions authorized for this account. Salary figures are calculated by the server.</p></div><button type="button" class="button button-outline" data-employee-refresh>Refresh employee records</button></div>
      <p class="meta" data-employee-connection></p>
      ${workspace.setup_missing.length?`<div class="notice-card warning"><h3>Setup or review needed</h3><ul>${workspace.setup_missing.map(item=>`<li>${esc(item)}</li>`).join('')}</ul><p>Missing inputs do not mean zero pay.</p></div>`:''}
      ${workspace.capabilities.can_self_service?`<section class="employee-time"><h3>My attendance</h3><div class="inline-actions">${[['clock_in','Clock in'],['break_start','Start break'],['break_end','End break'],['clock_out','Clock out']].map(([value,label])=>`<button class="button button-secondary" type="button" data-employee-attendance="${value}">${label}</button>`).join('')}</div><p>Record actual time. Paid or interrupted-break exceptions can be submitted for review.</p></section>`:''}
      <div class="employee-command-groups">${groups.map(group=>`<section><h3>${esc(group)}</h3><div class="inline-actions">${available.filter(([,form])=>form.group===group).map(([action,form])=>`<button type="button" class="button button-outline" data-employee-create="${action}">${esc(form.label)}</button>`).join('')}</div></section>`).join('')}</div>
      <div data-employee-status role="status" aria-live="polite"></div>
      ${pending?'<div class="notice-card warning"><h3>Confirm previous submission</h3><p>The same request identity is retained. Check its result before creating any other change.</p><button type="button" class="button button-secondary" data-employee-check>Check saved result</button><button type="button" class="button button-outline" data-employee-retry>Retry same unchanged request</button></div>':''}
      ${editorMarkup()}
      <section><h3>Attendance day review</h3>${workspace.attendance_days.length?workspace.attendance_days.map(day=>`<article class="data-card"><strong>${esc(employeeName(workspace,day.employee_id))} · ${esc(day.work_date)}</strong>${badge(day.status)}<p>Working minutes: ${esc(day.working_minutes)} · Unpaid break minutes: ${esc(day.unpaid_break_minutes)}</p>${asArray(day.issues).map(issue=>`<p>${esc(issue)}</p>`).join('')}</article>`).join(''):emptyState('No attendance day has been recorded.')}</section>
      <section><h3>Leave balances</h3>${workspace.leave_balances.length?workspace.leave_balances.map(balance=>`<article class="data-card"><strong>${esc(employeeName(workspace,balance.employee_id))}</strong><p>As of ${esc(balance.as_of)} · ${balance.eligible?'Eligible':'Not yet eligible'}</p><p>Available: ${esc(balance.available_minutes)} minutes · Used: ${esc(balance.used_minutes)} · Reserved: ${esc(balance.reserved_minutes)} · Accrued: ${esc(balance.accrued_minutes)} · Verified opening: ${esc(balance.opening_minutes)}</p></article>`).join(''):emptyState('No verified leave balance is available.')}</section>
      ${Object.entries(COLLECTIONS).filter(([key])=>workspace[key].length||['requests','tasks','advances','shortages','payroll'].includes(key)).map(([key,label])=>`<details class="employee-record-section" open><summary>${esc(label)} (${workspace[key].length})</summary><div class="employee-record-grid">${workspace[key].length?workspace[key].map((record,index)=>recordMarkup(workspace,record,`${key}:${index}`)).join(''):emptyState(`No ${label.toLowerCase()} are available in your authorized scope.`)}</div></details>`).join('')}`;
    listen(root.querySelector('[data-employee-refresh]'),'click',()=>load());
    listen(root.querySelector('[data-employee-check]'),'click',()=>load({recover:true}));
    listen(root.querySelector('[data-employee-retry]'),'click',()=>{if(pending)void execute(pending);});
    for(const button of root.querySelectorAll('[data-employee-create]'))listen(button,'click',()=>editor(button.getAttribute('data-employee-create')));
    for(const button of root.querySelectorAll('[data-employee-action]'))listen(button,'click',()=>{const [key,index]=button.getAttribute('data-employee-record').split(':');editor(button.getAttribute('data-employee-action'),workspace[key][Number(index)]);});
    for(const button of root.querySelectorAll('[data-employee-attendance]'))listen(button,'click',()=>attendance(button.getAttribute('data-employee-attendance')));
    listen(root.querySelector('[data-employee-cancel]'),'click',()=>{if(busy||pending)return;selected=null;render();});
    const form=root.querySelector('[data-employee-form]');
    listen(form,'submit',event=>{event.preventDefault();if(busy||pending||stale||disposed)return;try{void execute(buildCommand(form));}catch(error){message(error,true);}});
    if(selected)for(const button of root.querySelectorAll('[data-employee-add-row]'))listen(button,'click',()=>{
      if(busy||pending)return;const spec=FORMS[selected.action].fields.find(item=>item.name===button.getAttribute('data-employee-add-row'));
      const parent=form.querySelector(`[data-employee-rows="${spec.name}"]`);const rows=[...parent.querySelectorAll('[data-employee-row]')].map(row=>readFields(row,spec.fields,false));
      if(rows.length>=spec.max)return;rows.push({});parent.innerHTML=rows.map(value=>`<div class="employee-form-row" data-employee-row>${spec.fields.map(item=>inputMarkup({...item,optional:true},value)).join('')}</div>`).join('');
    });
    connection();
  }
  mounts.set(root,dispose);signal?.addEventListener('abort',dispose,{once:true});globalThis.addEventListener?.('online',connection);globalThis.addEventListener?.('offline',connection);
  if(signal?.aborted){dispose();return dispose;}
  root.innerHTML=loadingPanel('Loading private employee records…');void load();return dispose;
}
