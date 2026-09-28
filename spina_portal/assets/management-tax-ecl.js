import {escapeHtml, formatMoney, hasPermission, titleCase} from './ui.js';
import {sessionHasRole} from './roles.js';

const BASE='/api/v1/management/financial-accounting';
const mounts=new WeakMap();
const UUID=/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
const DIGEST=/^[0-9a-f]{64}$/i;
const MONEY=/^-?\d{1,16}\.\d{2}$/;
const taxKinds=['documentary_stamp_tax','percentage_tax_lending'];

export const taxEclViews={
 liabilities:{label:'Tax liabilities',path:'/tax/liabilities',status:'accounting_status',id:'evidence_id'},
 settlements:{label:'Tax returns & settlements',path:'/tax/settlements',status:'settlement_status',id:'payment_evidence_id'},
 adjustments:{label:'Tax corrections',path:'/tax/adjustments',status:'adjustment_status',id:'adjustment_evidence_id'},
 additional:{label:'Additional tax',path:'/tax/additional-amendments',status:'amendment_status',id:'amendment_evidence_id'},
 refunds:{label:'Tax refunds',path:'/tax/recoverable-refunds',status:'refund_status',id:'refund_evidence_id'},
 credits:{label:'Tax credits',path:'/tax/recoverable-credits',status:'credit_status',id:'credit_evidence_id'},
 allowance:{label:'Initial ECL allowance',path:'/ecl-allowance-posting',status:'allowance_posting_status',id:'measurement_id'},
 ecl:{label:'ECL remeasurement & recovery',path:'/ecl-a5',status:'a5_status',id:'loan_id'},
};

// Explicit mappings to existing API contracts. Amounts always remain decimal text;
// prepared snapshots are copied from the server, never editable form fields.
const actions={
 liabilities:{
  prepare:{label:'Prepare liability',permission:'accounting.tax.liability.prepare',cap:'liability_prepare',status:'evidence_ready'},
  post:{label:'Post liability',permission:'accounting.tax.liability.post',cap:'liability_post',status:'prepared_not_posted',fields:{evidence_digest:'evidence_digest',tax_due:'tax_due',expense_account_code:'expense_account_code',tax_payable_account_code:'tax_payable_account_code',posting_date:'recognition_date',fiscal_period_id:'fiscal_period_id'}},
 },
 settlements:{
  prepare:{label:'Prepare settlement',permission:'accounting.tax.settlement.prepare',cap:'settlement_prepare',status:'payment_evidence_ready'},
  post:{label:'Post settlement',permission:'accounting.tax.settlement.post',cap:'settlement_post',status:'settlement_prepared',fields:{return_evidence_digest:'return_evidence_digest',payment_evidence_digest:'payment_evidence_digest',payment_amount:'payment_amount',tax_payable_account_code:'tax_payable_account_code',cash_account_code:'cash_account_code',posting_date:'payment_date',fiscal_period_id:'fiscal_period_id'}},
 },
 adjustments:{
  prepare:{label:'Prepare correction',permission:'accounting.tax.adjustment.prepare',cap:'adjustment_prepare',status:'evidence_ready'},
  post:{label:'Post correction',permission:'accounting.tax.adjustment.post',cap:'adjustment_post',status:'prepared_not_posted',fields:{evidence_digest:'evidence_digest',original_tax_due:'original_tax_due',replacement_tax_due:'replacement_tax_due',adjustment_amount:'adjustment_amount',debit_account_code:'debit_account_code',credit_account_code:'credit_account_code',posting_date:'adjustment_date',fiscal_period_id:'fiscal_period_id'}},
 },
 additional:{
  'prepare-liability':{label:'Prepare additional liability',permission:'accounting.tax.additional_amendment.prepare',cap:'additional_liability_prepare',status:'amendment_evidence_ready'},
  'post-liability':{label:'Post additional liability',permission:'accounting.tax.additional_amendment.post',cap:'additional_liability_post',status:'additional_liability_prepared',fields:{evidence_digest:'evidence_digest',original_declared_tax_due:'original_declared_tax_due',revised_declared_tax_due:'revised_declared_tax_due',original_item_tax_due:'original_item_tax_due',replacement_item_tax_due:'replacement_item_tax_due',additional_tax_due:'additional_tax_due',expense_account_code:'expense_account_code',tax_payable_account_code:'tax_payable_account_code',posting_date:'recognition_date',fiscal_period_id:'liability_fiscal_period_id'}},
  'prepare-settlement':{label:'Prepare additional settlement',permission:'accounting.tax.additional_settlement.prepare',cap:'additional_settlement_prepare',status:'additional_payment_evidence_ready'},
  'post-settlement':{label:'Post additional settlement',permission:'accounting.tax.additional_settlement.post',cap:'additional_settlement_post',status:'additional_settlement_prepared',fields:{amendment_evidence_digest:'evidence_digest',additional_liability_confirmation_digest:'liability_confirmation_digest',payment_evidence_digest:'payment_evidence_digest',payment_amount:'payment_amount',tax_payable_account_code:'tax_payable_account_code',cash_account_code:'payment_cash_account_code',posting_date:'payment_date',fiscal_period_id:'settlement_fiscal_period_id'}},
 },
 refunds:{
  prepare:{label:'Prepare refund',permission:'accounting.tax.recoverable_refund.prepare',cap:'refund_prepare',status:'refund_evidence_ready'},
  post:{label:'Post refund',permission:'accounting.tax.recoverable_refund.post',cap:'refund_post',status:'refund_prepared',fields:{evidence_digest:'evidence_digest',refund_amount:'refund_amount',cash_account_code:'cash_account_code',tax_recoverable_account_code:'tax_recoverable_account_code',posting_date:'refund_date',fiscal_period_id:'fiscal_period_id'}},
 },
 credits:{
  prepare:{label:'Prepare credit',permission:'accounting.tax.recoverable_credit.prepare',cap:'credit_prepare',status:'credit_evidence_ready'},
  post:{label:'Post credit',permission:'accounting.tax.recoverable_credit.post',cap:'credit_post',status:'credit_prepared',fields:{evidence_digest:'evidence_digest',credit_amount:'credit_amount',tax_payable_account_code:'tax_payable_account_code',tax_recoverable_account_code:'tax_recoverable_account_code',posting_date:'application_date',fiscal_period_id:'fiscal_period_id'}},
 },
 allowance:{
  prepare:{label:'Prepare allowance',permission:'accounting.ecl.allowance.prepare',cap:'prepare_permission',status:'preparation_required',token:'preparation_review_token',fields:{calculation_digest:'calculation_digest',ecl_amount:'authoritative_ecl_amount',posting_date:'posting_date',fiscal_period_id:'fiscal_period_id',credit_loss_expense_account_id:'credit_loss_expense_account_id',allowance_account_id:'allowance_account_id',prior_allowance_balance:'prior_allowance_balance'}},
  post:{label:'Post allowance',permission:'accounting.ecl.allowance.post',cap:'post_permission',status:'posting_ready',token:'posting_review_token',fields:{measurement_id:'measurement_id',calculation_digest:'calculation_digest',journal_entry_id:'journal_entry_id',source_event_key:'source_event_key',preparation_digest:'preparation_digest',posting_date:'posting_date',fiscal_period_id:'fiscal_period_id',credit_loss_expense_account_id:'credit_loss_expense_account_id',allowance_account_id:'allowance_account_id',allowance_amount:'allowance_amount',prior_allowance_balance:'prior_allowance_balance'}},
 },
 ecl:{
  remeasure:{label:'Post remeasurement',permission:'accounting.ecl.remeasurement.post',cap:'remeasurement_post',status:'remeasurement_required',token:'review_token',fields:{calculation_digest:'calculation_digest',prior_allowance:'current_allowance_balance',target_allowance:'authoritative_ecl_amount',posting_date:'posting_date',fiscal_period_id:'fiscal_period_id',credit_loss_expense_account_id:'credit_loss_expense_account_id',allowance_account_id:'allowance_account_id'}},
  writeoff:{label:'Post full write-off',permission:'accounting.ecl.writeoff.post',cap:'writeoff_post',status:'writeoff_ready',token:'review_token',fields:{credit_risk_review_id:'credit_risk_review_id',measurement_id:'measurement_id',calculation_digest:'calculation_digest',loan_component:'loan_component',accrued_interest_component:'accrued_interest_component',gross_carrying_amount:'gross_carrying_amount',allowance_balance:'current_allowance_balance',loan_receivable_account_id:'loan_receivable_account_id',accrued_interest_account_id:'accrued_interest_account_id',allowance_account_id:'allowance_account_id',posting_date:'posting_date',fiscal_period_id:'fiscal_period_id'}},
  'recovery-review':{label:'Review recovery evidence',permission:'accounting.ecl.recovery.review',cap:'recovery_review',status:'recovery_review_required',token:'review_token',fields:{recovery_transaction_id:'recovery_candidate_transaction_id',recovery_amount:'recovery_candidate_amount'},inputs:['evidence_reference','review_note']},
  recovery:{label:'Post recovery',permission:'accounting.ecl.recovery.post',cap:'recovery_post',status:'post_writeoff_recovery_ready',token:'review_token',fields:{recovery_transaction_id:'recovery_transaction_id',recovery_amount:'recovery_amount',posting_date:'posting_date',fiscal_period_id:'fiscal_period_id',cash_account_id:'cash_account_id',credit_loss_expense_account_id:'credit_loss_expense_account_id'}},
 },
};

function required(row,key){
 const value=row?.[key];
 if(key==='credit_risk_review_id'){
  if(!Number.isSafeInteger(value)||value<1)throw new Error('The review reference needs a fresh server response.');
  return value;
 }
 if(typeof value!=='string'||!value.trim())throw new Error(`The server record is incomplete (${titleCase(key)}). Refresh before continuing.`);
 if(key.endsWith('_id')&&!UUID.test(value))throw new Error('The record reference is invalid.');
 if(key.endsWith('_digest')&&!DIGEST.test(value))throw new Error('The reviewed evidence reference is invalid.');
 if(/amount|balance|tax_due|allowance$|component$/.test(key)&&!MONEY.test(value))throw new Error('The exact amount is unavailable. Refresh before continuing.');
 if(key.endsWith('_date')){
  if(!/^\d{4}-\d{2}-\d{2}$/.test(value)||!Number.isFinite(Date.parse(value))||new Date(`${value}T00:00:00Z`).toISOString().slice(0,10)!==value)throw new Error('The business date is invalid.');
 }
 return value;
}

export function buildTaxEclAction(view,action,data,row,session,input={},token){
 const page=taxEclViews[view], definition=actions[view]?.[action];
 if(!page||!definition||!sessionHasRole(session,'management')||!hasPermission(session,definition.permission))throw new Error('Management permission is required.');
 const capability=view==='allowance'?data?.[definition.cap]:data?.permissions?.[definition.cap];
 if(capability!==true||row?.[page.status]!==definition.status||row.automatic_source_posting!==false||data?.automatic_source_posting===true)throw new Error('This action is unavailable for the current reviewed record.');
 if(view==='allowance'&&(row.protected_allowance_action_ready!==true||required(row,'prior_allowance_balance')!=='0.00'))throw new Error('Initial allowance requires an exact current zero starting balance.');
 if(view==='ecl'&&row.protected_a5_accounting_enabled!==true)throw new Error('Protected ECL accounting is unavailable.');
 const body=definition.token?{}:{confirm:true};
 if(definition.fields){
  if(!DIGEST.test(token||''))throw new Error('A new confirmation identity is required.');
  body[definition.token||'confirmation_token']=token;
  for(const [destination,source] of Object.entries(definition.fields))body[`expected_${destination}`]=required(row,source);
 }
 for(const key of definition.inputs||[]){
  const value=String(input[key]??'').trim();
  if(value.length<(key==='review_note'?20:1)||value.length>(key==='review_note'?4000:500))throw new Error('Enter the retained evidence reference and a review note of at least 20 characters.');
  body[key]=value;
 }
 let path=`${BASE}${page.path}`;
 if(view==='liabilities'){
  if(!taxKinds.includes(row.tax_type))throw new Error('Unsupported tax type.');
  path+=`/${row.tax_type}/${required(row,'evidence_id')}/${action}`;
 }else if(view==='settlements')path+=`/payments/${required(row,'payment_evidence_id')}/${action}`;
 else if(view==='allowance')path+=action==='post'?`/preparations/${required(row,'preparation_id')}/post`:`/${required(row,'measurement_id')}/prepare`;
 else if(view==='ecl')path+=action==='remeasure'?`/measurements/${required(row,'measurement_id')}/remeasure`:action==='recovery'?`/reviews/${required(row,'credit_risk_review_id')}/recovery`:`/loans/${required(row,'loan_id')}/${action}`;
 else path+=`/${required(row,page.id)}/${action}`;
 return {path,body,label:definition.label};
}

function newToken(){return Array.from(crypto.getRandomValues(new Uint8Array(32)),byte=>byte.toString(16).padStart(2,'0')).join('');}
function savedResultMatches(view,action,row,result){
 if(!result||typeof result!=='object')return false;
 if(view==='allowance')return UUID.test(result.id||'')&&result.loan_id===row.loan_id&&result.measurement_id===row.measurement_id&&result.calculation_digest===row.calculation_digest&&result.automatic_source_posting===false;
 if(view==='ecl'){
  const key={remeasure:'remeasurement_id',writeoff:'writeoff_id',recovery:'recovery_id','recovery-review':'credit_risk_review_id'}[action];
  return result.automatic_source_posting===false&&(action==='recovery-review'?(Number.isSafeInteger(result[key])&&result[key]>0&&result.recovery_transaction_id===row.recovery_candidate_transaction_id):UUID.test(result[key]||''));
 }
 const item=result.item,key=taxEclViews[view].id;
 return item&&item[key]===row[key]&&item.automatic_source_posting===false;
}
function facts(row){
 const names=['loan_number','loan_id','client_id','evidence_id','measurement_id','payment_evidence_id','adjustment_evidence_id','amendment_evidence_id','refund_evidence_id','credit_evidence_id','return_reference','tax_type','recognition_date','posting_date','payment_date','tax_due','declared_tax_due','original_tax_due','replacement_tax_due','adjustment_amount','additional_tax_due','payment_amount','refund_amount','credit_amount','authoritative_ecl_amount','current_allowance_balance','loan_component','accrued_interest_component','gross_carrying_amount','recovery_candidate_amount','recovery_amount','expense_account_code','tax_payable_account_code','cash_account_code','debit_account_code','credit_account_code'];
 return names.filter(key=>row[key]!==null&&row[key]!==undefined).map(key=>[titleCase(key),/amount|balance|tax_due|component/.test(key)?formatMoney(row[key]):String(row[key])]);
}
function factsMarkup(row){return `<dl class="detail-grid accounting-details">${facts(row).map(([label,value])=>`<div><dt>${escapeHtml(label)}</dt><dd>${escapeHtml(value)}</dd></div>`).join('')}</dl>`;}
function available(view,data,row,session){return Object.entries(actions[view]).filter(([name,def])=>{try{buildTaxEclAction(view,name,data,row,session,{evidence_reference:'Retained reference',review_note:'Placeholder only for capability validation'},'a'.repeat(64));return true;}catch{return false;}});}

export async function mountManagementTaxEcl({root,api,session,signal,initialView='liabilities',confirm=message=>globalThis.confirm?.(message)===true}){
 mounts.get(root)?.();
 const controller=new AbortController();let disposed=false,busy=false,locked=false,generation=0,offset=0,view=initialView,data=null,evidenceCleanup=null,evidenceController=null;
 function closeEvidence(){evidenceController?.abort();evidenceCleanup?.();evidenceController=null;evidenceCleanup=null;}
 function dispose(){if(disposed)return;disposed=true;generation++;closeEvidence();controller.abort();signal?.removeEventListener('abort',dispose);root.innerHTML='';if(mounts.get(root)===dispose)mounts.delete(root);}
 mounts.set(root,dispose);signal?.addEventListener('abort',dispose,{once:true});
 if(signal?.aborted){dispose();return dispose;}
 if(!sessionHasRole(session,'management')){root.textContent='Management access is required.';return dispose;}
 function rejectAccess(){data=null;locked=true;dispose();root.innerHTML='<p role="alert">Accounting access is no longer available. Sign in again before reopening this section.</p>';}
 function status(message){if(!disposed){const target=root.querySelector('[data-tax-status]');if(target)target.textContent=message;}}
 function disable(){for(const button of root.querySelectorAll('button'))button.disabled=busy||((locked||globalThis.navigator?.onLine===false)&&button.getAttribute('data-tax-action')!==null);}
 async function load(){
  if(disposed||busy)return;
  closeEvidence();
  const revision=++generation;data=null;locked=true;
  root.innerHTML='<div class="loading-panel" role="status">Loading protected accounting records...</div>';
  try{
   const result=await api.request(`${BASE}${taxEclViews[view].path}?limit=100&offset=${offset}`,{signal:controller.signal});
   if(disposed||revision!==generation)return;
   if(!result||!Array.isArray(result.items))throw new Error('The server did not return the accounting records.');
   data=structuredClone(result);locked=false;render();
  }catch(error){if(!disposed&&revision===generation){if([401,403,426].includes(error.status)){rejectAccess();return;}root.innerHTML=`<p role="alert">${escapeHtml(error.message||'Accounting records could not be loaded.')}</p><button class="button button-outline" type="button" data-tax-reload>Refresh records</button>`;root.querySelector('[data-tax-reload]')?.addEventListener('click',load);}}
 }
 function render(){
  const renderedGeneration=generation;
  root.innerHTML=`<div class="list-stack"><div class="inline-actions accounting-actions">${Object.entries(taxEclViews).map(([key,item])=>`<button class="button button-outline" type="button" data-tax-view="${key}" aria-pressed="${key===view}">${escapeHtml(item.label)}</button>`).join('')}<button class="button button-outline" type="button" data-tax-evidence>Record tax evidence</button></div><h3>${escapeHtml(taxEclViews[view].label)}</h3><p>Review the exact retained facts before each action. Preparing a draft does not post it. Posted records keep their history.</p><div role="status" aria-live="polite" data-tax-status></div><div class="inline-actions accounting-actions"><button class="button button-outline" type="button" data-tax-reload>Refresh records</button>${offset?'<button class="button button-outline" type="button" data-tax-previous>Previous</button>':''}${data.items.length===100?'<button class="button button-outline" type="button" data-tax-next>Next</button>':''}</div>${data.items.length?data.items.map((row,index)=>`<article class="data-card"><h4>${escapeHtml(row.loan_number||row.return_reference||row.adjustment_reference||row.application_reference||row.refund_reference||'Retained accounting record')}</h4><p>${escapeHtml(titleCase(row[taxEclViews[view].status]||'Unavailable'))}</p>${factsMarkup(row)}${row.accounting_blocker||row.settlement_blocker||row.adjustment_blocker||row.refund_blocker||row.credit_blocker?`<p>${escapeHtml(row.accounting_blocker||row.settlement_blocker||row.adjustment_blocker||row.refund_blocker||row.credit_blocker)}</p>`:''}${available(view,data,row,session).map(([name,def])=>`<button class="button button-outline" type="button" data-tax-action="${name}" data-tax-index="${index}">${escapeHtml(def.label)}</button>`).join('')}</article>`).join(''):'<p>No records in this part of the queue.</p>'}</div>`;
  for(const button of root.querySelectorAll('[data-tax-view]'))button.addEventListener('click',()=>{if(busy||disposed)return;view=button.getAttribute('data-tax-view');offset=0;void load();});
  root.querySelector('[data-tax-reload]')?.addEventListener('click',load);
  root.querySelector('[data-tax-evidence]')?.addEventListener('click',showEvidence);
  root.querySelector('[data-tax-previous]')?.addEventListener('click',()=>{if(!busy){offset=Math.max(0,offset-100);void load();}});
  root.querySelector('[data-tax-next]')?.addEventListener('click',()=>{if(!busy){offset+=100;void load();}});
  for(const button of root.querySelectorAll('[data-tax-action]'))button.addEventListener('click',()=>{if(renderedGeneration===generation)void act(button.getAttribute('data-tax-action'),Number(button.getAttribute('data-tax-index')));});
  disable();
 }
 async function showEvidence(){
  if(disposed||busy)return;
  const revision=++generation;data=null;locked=true;closeEvidence();
  evidenceController=new AbortController();const childSignal=evidenceController.signal;
  root.innerHTML='<button class="button button-outline" type="button" data-tax-back>Back to accounting records</button><div data-tax-evidence-root></div>';
  root.querySelector('[data-tax-back]').addEventListener('click',load);
  try{
   const {mountTaxEvidence}=await import('./management-tax-evidence.js');
   if(disposed||revision!==generation)return;
   const cleanup=await mountTaxEvidence({root:root.querySelector('[data-tax-evidence-root]'),api,session,signal:childSignal,confirm});
   if(disposed||revision!==generation)cleanup?.();else evidenceCleanup=cleanup;
  }catch(error){if(!disposed&&revision===generation)root.querySelector('[data-tax-evidence-root]').textContent=error.message||'Tax evidence could not be loaded.';}
 }
 async function act(action,index){
  if(disposed||busy||locked||globalThis.navigator?.onLine===false)return;
  const row=data?.items[index],reviewedGeneration=generation;if(!row)return;
  let input={};
  if(action==='recovery-review'){
   // Evidence entry is scoped to the selected immutable server candidate.
   const article=root.querySelectorAll('article')[index];
   if(!article.querySelector('[data-recovery-review]')){
    const current=article.innerHTML;
    article.innerHTML=current+'<form data-recovery-review><label>Retained evidence reference<input name="evidence_reference" required maxlength="500"></label><label>Management review note<textarea name="review_note" required minlength="20" maxlength="4000"></textarea></label><button class="button button-primary" type="submit">Review recovery evidence</button></form>';
    article.querySelector('[data-recovery-review]').addEventListener('submit',event=>{event.preventDefault();void act(action,index);});return;
   }
   input={evidence_reference:article.querySelector('[name="evidence_reference"]').value,review_note:article.querySelector('[name="review_note"]').value};
  }
  let request;const token=newToken();
  try{request=buildTaxEclAction(view,action,data,row,session,input,token);}catch(error){status(error.message);return;}
  const consequence=action.startsWith('prepare')?'Prepare a draft only; no ledger balance changes.':action==='recovery-review'?'Record this review against the selected recovery evidence.':'Post this exact reviewed action. Posted history is immutable.';
  if(!await confirm(`${request.label}\n\n${facts(row).map(([label,value])=>`${label}: ${value}`).join('\n')}\n\n${consequence}`)||disposed||busy||locked||reviewedGeneration!==generation)return;
  try{request=buildTaxEclAction(view,action,data,row,session,input,token);}catch(error){status(error.message);return;}
  busy=true;disable();status('Saving the reviewed action...');
  try{
   const result=await api.request(request.path,{method:'POST',body:request.body,financial:true,signal:controller.signal});
   if(disposed)return;
   if(!savedResultMatches(view,action,row,result))throw new Error('The result is uncertain. Refresh authoritative records before continuing.');
   locked=true;busy=false;await load();
  }catch(error){if(!disposed){if([401,403,426].includes(error.status)){rejectAccess();return;}locked=true;status(`${error.message||'The result is uncertain.'} Refresh authoritative records before another action.`);}}
  finally{busy=false;if(!disposed)disable();}
 }
 await load();return dispose;
}
