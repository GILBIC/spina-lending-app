import {escapeHtml, formatMoney, hasPermission, titleCase} from './ui.js';
import {sessionHasRole} from './roles.js';

const BASE='/api/v1/management/financial-accounting/tax';
const mounts=new WeakMap();
const UUID=/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
const HASH=/^[0-9a-f]{64}$/i;
const TAX=['documentary_stamp_tax','percentage_tax_lending'];
const CASH=['cash_office','cash_bank_gcash'];
const kinds={
 rule:{label:'Tax rule evidence',path:'',list:'rules',permission:'rule',cap:'rule_evidence_record',post:'/rules'},
 dst:{label:'Documentary stamp evidence',path:'',list:'dst',permission:'dst',cap:'dst_evidence_record',post:'/dst-evidence'},
 percentage:{label:'Lending receipt evidence',path:'',list:'percentage_tax',permission:'percentage',cap:'percentage_evidence_record',post:'/percentage-evidence'},
 return:{label:'Tax return evidence',path:'/settlements',list:'return_liability_candidates',permission:'return',cap:'return_evidence_record',post:'/settlements/returns'},
 payment:{label:'Return payment evidence',path:'/settlements',list:'items',permission:'payment',cap:'payment_evidence_record'},
 adjustment:{label:'Tax correction evidence',path:'/adjustments',list:'adjustment_candidates',permission:'adjustment',cap:'adjustment_evidence_record',post:'/adjustments/evidence'},
 additional:{label:'Additional tax evidence',path:'/additional-amendments',list:'amendment_candidates',permission:'additional_amendment',cap:'amendment_evidence_record',post:'/additional-amendments/evidence'},
 additional_payment:{label:'Additional payment evidence',path:'/additional-amendments',list:'items',permission:'additional_payment',cap:'additional_payment_evidence_record'},
 refund:{label:'Refund evidence',path:'/recoverable-refunds',list:'refund_candidates',permission:'recoverable_refund',cap:'refund_evidence_record',post:'/recoverable-refunds/evidence'},
 credit:{label:'Credit application evidence',path:'/recoverable-credits',list:'credit_candidates',permission:'recoverable_credit',cap:'credit_evidence_record',post:'/recoverable-credits/evidence'},
};

function text(value,label,max=500,min=1){
 const result=String(value??'').trim().replace(/\s+/g,' ');
 if(result.length<min||result.length>max)throw new Error(`${label} needs ${min} to ${max} characters.`);
 return result;
}
function uuid(value){if(typeof value!=='string'||!UUID.test(value))throw new Error('Select a current server record.');return value;}
function digest(value){if(typeof value!=='string'||!HASH.test(value))throw new Error('Choose the retained document or enter its 64-character SHA-256 checksum.');return value.toLowerCase();}
function date(value,label='Date'){
 if(typeof value!=='string'||!/^\d{4}-\d{2}-\d{2}$/.test(value)||!Number.isFinite(Date.parse(value))||new Date(`${value}T00:00:00Z`).toISOString().slice(0,10)!==value)throw new Error(`${label} must be a valid date.`);
 return value;
}
function choice(value,values,label){if(!values.includes(value))throw new Error(`Select ${label}.`);return value;}
function money(value,positive=false){
 if(typeof value!=='string'||!/^\d{1,16}\.\d{2}$/.test(value)||(positive&&cents(value)===0n))throw new Error('Enter an exact nonnegative amount with two decimal places.');
 return value;
}
function cents(value){return BigInt(value.replace('.',''));}
function moneyFromCents(value){return money(`${value/100n}.${String(value%100n).padStart(2,'0')}`);}
function minimum(value,lower,label){const result=date(value,label);if(result<date(lower))throw new Error(`${label} cannot precede ${lower}.`);return result;}
function allowed(kind,data,session){const config=kinds[kind];return config&&sessionHasRole(session,'management')&&hasPermission(session,`accounting.tax.${config.permission}_evidence.record`)&&data?.permissions?.[config.cap]===true&&data.automatic_source_posting===false;}
function eligible(kind,row){
 if(!row||row.automatic_source_posting===true)return false;
 if(kind==='payment')return row.automatic_source_posting===false&&row.settlement_status==='return_recorded_awaiting_payment'&&row.payment_evidence_id==null;
 if(kind==='additional_payment')return row.automatic_source_posting===false&&row.amendment_status==='additional_liability_posted_awaiting_payment'&&UUID.test(row.additional_liability_posting_id||'')&&HASH.test(row.liability_confirmation_digest||'')&&row.additional_payment_evidence_id==null;
 if(kind==='percentage')return row.is_voided===false&&row.automatic_source_posting===false&&row.tax_posting_enabled===false;
 if(kind==='dst')return row.automatic_source_posting===false&&row.tax_posting_enabled===false;
 return true;
}
function selectedRule(kind,data,input,row){
 const rule=data.rules?.find(item=>item.id===input.rule_evidence_id);
 const day=date(kind==='dst'?row.issue_date:row.collection_date);
 if(!rule||rule.tax_type!==(kind==='dst'?TAX[0]:TAX[1])||day<date(rule.effective_from)||(rule.effective_to&&day>date(rule.effective_to)))throw new Error('Select a retained rule for this tax type and source date.');
 return uuid(rule.id);
}
function receiptMatches(kind,row,body,result){
 if(!result||typeof result!=='object')return false;
 if(['rule','dst','percentage'].includes(kind))return result.automatic_source_posting===false&&result.tax_posting_enabled===false&&UUID.test(result[{rule:'rule_evidence_id',dst:'dst_evidence_id',percentage:'percentage_tax_evidence_id'}[kind]]||'');
 const item=result.item;if(!item||item.automatic_source_posting!==false)return false;
 const key={return:'tax_return_id',payment:'payment_evidence_id',adjustment:'adjustment_evidence_id',additional:'amendment_evidence_id',additional_payment:'additional_payment_evidence_id',refund:'refund_evidence_id',credit:'credit_evidence_id'}[kind];
 if(!UUID.test(item[key]||''))return false;
 if(kind==='return')return item.return_evidence_digest===body.evidence_digest&&item.return_reference===body.return_reference&&item.declared_tax_due===body.declared_tax_due;
 if(kind==='payment'||kind==='additional_payment')return item[kind==='payment'?'tax_return_id':'amendment_evidence_id']===row[kind==='payment'?'tax_return_id':'amendment_evidence_id']&&item.payment_evidence_digest===body.evidence_digest&&item.payment_amount===body.payment_amount;
 return item.evidence_digest===body.evidence_digest&&Object.entries(body).filter(([name])=>name.endsWith('_id')).every(([name,value])=>item[name]===value);
}

// All source coordinates come from the current queue. Tax rates and evidence
// amounts are reviewed inputs; this client does not derive tax policy.
export function buildTaxEvidenceAction(kind,data,row,session,input={},identity){
 const config=kinds[kind];
 if(!allowed(kind,data,session))throw new Error('Current Management permission is required. Refresh the records.');
 if(kind!=='return'&&!(kind==='rule'&&row===null)&&(!data[config.list]?.includes(row)||!eligible(kind,row)))throw new Error('Select an available record from the current server response.');
 const body={idempotency_key:uuid(identity)};
 let path=config.post;
 const putText=(key,max=500,min=1)=>body[key]=text(input[key],titleCase(key),max,min);
 const putDigest=key=>body[key]=digest(input[key]);
 const copyIds=(...keys)=>{for(const key of keys)body[key]=uuid(row[key]);};
 if(['rule','dst','percentage'].includes(kind)){
  if(data.tax_posting_enabled!==false)throw new Error('The evidence-only contract is unavailable.');
  body.confirm=true;putText('management_rationale',4000,20);
 }else{putText('evidence_note',4000,20);putDigest('evidence_digest');}
 if(kind==='rule'){
  body.tax_type=choice(input.tax_type,TAX,'tax type');putText('rule_key',120);
  body.effective_from=date(input.effective_from);body.effective_to=input.effective_to?minimum(input.effective_to,body.effective_from,'Effective end date'):null;
  body.treatment=choice(input.treatment,['taxable','exempt'],'treatment');
  if(typeof input.rate!=='string'||!/^(?:0(?:\.\d{1,10})?|1(?:\.0{1,10})?)$/.test(input.rate)||((!/[1-9]/.test(input.rate))!==(body.treatment==='exempt')))throw new Error('Use a reviewed rate from 0 to 1, up to 10 decimals; exempt rules require zero.');
  body.rate=input.rate;
  const days=String(input.maturity_max_days??'').trim();
  if(days&&(!/^\d+$/.test(days)||!Number.isSafeInteger(Number(days))||Number(days)<1))throw new Error('Maturity limit must be a positive whole number of days.');
  body.maturity_max_days=days?Number(days):null;
  putText('legal_source',240);putText('legal_reference');putText('retained_source_reference');putDigest('evidence_digest');
  body.supersedes_rule_id=row?uuid(row.id):null;
  if(row&&(row.tax_type!==body.tax_type||row.rule_key!==body.rule_key))throw new Error('A replacement must retain the selected rule key and tax type.');
 }else if(kind==='dst'||kind==='percentage'){
  body.rule_evidence_id=selectedRule(kind,data,input,row);body.expected_tax_due=money(input.expected_tax_due);
  body.supersedes_evidence_id=row.evidence_id?uuid(row.evidence_id):null;
  if(kind==='dst'){
   copyIds('loan_id','disbursement_event_id');body.expected_issue_price=money(row.protected_issue_price,true);
   if(!Number.isSafeInteger(row.protected_term_days)||row.protected_term_days<1)throw new Error('Refresh the protected term days.');
   body.expected_term_days=row.protected_term_days;
   for(const name of ['instrument','calculation']){putText(`${name}_reference`);putDigest(`${name}_digest`);}
  }else{
   copyIds('transaction_id');body.expected_source_cash_amount=money(row.source_cash_amount,true);
   body.taxable_lending_receipt_amount=money(input.taxable_lending_receipt_amount);body.principal_receipt_amount=money(input.principal_receipt_amount);
   if(cents(body.taxable_lending_receipt_amount)+cents(body.principal_receipt_amount)!==cents(body.expected_source_cash_amount))throw new Error('Taxable receipt plus principal must exactly equal the protected source cash.');
   putText('allocation_reference');putDigest('allocation_digest');
  }
 }else if(kind==='return'){
  body.tax_type=choice(input.tax_type,TAX,'tax type');body.return_period_start=date(input.return_period_start);body.return_period_end=minimum(input.return_period_end,body.return_period_start,'Return period end');body.filing_date=minimum(input.filing_date,body.return_period_end,'Filing date');
  const ids=input.liability_posting_ids;
  if(!Array.isArray(ids)||ids.length<1||ids.length>500||new Set(ids).size!==ids.length)throw new Error('Select 1 to 500 distinct posted liabilities.');
  let total=0n;
  for(const id of ids){const item=data.return_liability_candidates?.find(candidate=>candidate.posting_id===uuid(id));if(!item||item.tax_type!==body.tax_type||date(item.recognition_date)<body.return_period_start||item.recognition_date>body.return_period_end)throw new Error('Every selected liability must match the tax type and return period.');total+=cents(money(item.tax_due,true));}
  body.liability_posting_ids=[...ids];body.declared_tax_due=money(moneyFromCents(total),true);putText('return_reference',240);putText('evidence_reference');
 }else if(kind==='payment'||kind==='additional_payment'){
  body.payment_date=minimum(input.payment_date,kind==='payment'?row.filing_date:row.amendment_date,'Payment date');
  body.payment_amount=money(kind==='payment'?row.declared_tax_due:row.payment_required_amount,true);
  body.cash_account_system_key=choice(input.cash_account_system_key,CASH,'the actual payment account');putText('payment_reference',240);putText('evidence_reference');
  path=kind==='payment'?`/settlements/returns/${uuid(row.tax_return_id)}/payments`:`/additional-amendments/${uuid(row.amendment_evidence_id)}/payment-evidence`;
 }else if(kind==='adjustment'){
  copyIds('tax_liability_posting_id','replacement_evidence_id');body.adjustment_kind=choice(row.adjustment_kind,['reverse_unsettled_liability','recognize_settled_tax_recoverable'],'supported correction');body.adjustment_date=date(input.adjustment_date);
  if(body.adjustment_date<date(row.fiscal_period_start)||body.adjustment_date>date(row.fiscal_period_end))throw new Error('The correction date must fall within the displayed open fiscal period.');
  putText('adjustment_reference',240);putText('evidence_reference');
 }else if(kind==='additional'){
  copyIds('tax_return_id','tax_liability_posting_id','replacement_evidence_id');body.amendment_basis=choice(input.amendment_basis,['amended_return','additional_assessment'],'amendment basis');body.amendment_date=minimum(input.amendment_date,row.filing_date,'Amendment date');body.recognition_date=date(row.recognition_date);putText('amendment_reference',240);putText('evidence_reference');
 }else if(kind==='refund'){
  copyIds('adjustment_posting_id');body.refund_date=minimum(input.refund_date,row.minimum_refund_date,'Refund date');body.cash_account_code=choice(input.cash_account_code,['1010','1030'],'the actual receiving account');putText('refund_reference',240);putText('authority_reference');
 }else if(kind==='credit'){
  copyIds('adjustment_posting_id','target_tax_return_id');body.application_date=minimum(input.application_date,row.minimum_application_date,'Application date');putText('application_reference',240);putText('authority_reference');
 }
 return {path:BASE+path,body,label:config.label};
}

const labels={tax_type:'Tax type',rate:'Reviewed rate (decimal, for example 0.01)',rule_key:'Rule name',maturity_max_days:'Maximum maturity days (optional)',effective_to:'Effective until (optional)',expected_tax_due:'Reviewed tax due',taxable_lending_receipt_amount:'Taxable lending receipt',principal_receipt_amount:'Principal receipt',management_rationale:'Management rationale',evidence_note:'Management evidence review',evidence_reference:'Retained document reference',retained_source_reference:'Retained legal source reference',cash_account_system_key:'Cash account',cash_account_code:'Cash account',rule_evidence_id:'Retained rule'};
const selectValues={tax_type:TAX.map(value=>[value,titleCase(value)]),treatment:[['taxable','Taxable'],['exempt','Exempt']],cash_account_system_key:[['cash_office','Cash — Office'],['cash_bank_gcash','Cash — Bank / GCash']],cash_account_code:[['1010','Cash — Office (1010)'],['1030','Cash — Bank / GCash (1030)']],amendment_basis:[['amended_return','Amended return'],['additional_assessment','Additional assessment']]};
const fields={
 rule:['tax_type','rule_key','effective_from','effective_to','treatment','rate','maturity_max_days','legal_source','legal_reference','retained_source_reference','evidence_digest','management_rationale'],
 dst:['rule_evidence_id','expected_tax_due','instrument_reference','instrument_digest','calculation_reference','calculation_digest','management_rationale'],
 percentage:['rule_evidence_id','taxable_lending_receipt_amount','principal_receipt_amount','expected_tax_due','allocation_reference','allocation_digest','management_rationale'],
 return:['tax_type','return_period_start','return_period_end','filing_date','return_reference','evidence_reference','evidence_digest','evidence_note'],
 payment:['payment_date','cash_account_system_key','payment_reference','evidence_reference','evidence_digest','evidence_note'],
 adjustment:['adjustment_date','adjustment_reference','evidence_reference','evidence_digest','evidence_note'],
 additional:['amendment_basis','amendment_date','amendment_reference','evidence_reference','evidence_digest','evidence_note'],
 additional_payment:['payment_date','cash_account_system_key','payment_reference','evidence_reference','evidence_digest','evidence_note'],
 refund:['refund_date','cash_account_code','refund_reference','authority_reference','evidence_digest','evidence_note'],
 credit:['application_date','application_reference','authority_reference','evidence_digest','evidence_note'],
};
const factsKeys=['rule_key','rule_version','tax_type','loan_number','loan_id','client_id','transaction_id','disbursement_event_id','tax_return_id','target_tax_return_id','tax_liability_posting_id','adjustment_posting_id','evidence_id','evidence_version','original_evidence_version','replacement_evidence_version','amendment_evidence_id','entry_number','return_reference','target_return_reference','issue_date','collection_date','recognition_date','protected_issue_price','protected_term_days','source_cash_amount','tax_due','declared_tax_due','return_period_start','return_period_end','filing_date','original_tax_due','replacement_tax_due','adjustment_amount','adjustment_kind','fiscal_period_start','fiscal_period_end','original_declared_tax_due','revised_declared_tax_due','original_item_tax_due','replacement_item_tax_due','additional_tax_due','payment_basis','payment_required_amount','recoverable_amount','credit_amount','target_return_period_start','target_return_period_end','target_declared_tax_due','minimum_refund_date','minimum_application_date','effective_from','effective_to','treatment','rate','legal_source','legal_reference'];
function display(key,value){if(/amount|tax_due|issue_price/.test(key))return formatMoney(value);if(selectValues[key])return selectValues[key].find(([id])=>id===value)?.[1]||String(value);return String(value);}
function facts(row){return factsKeys.filter(key=>row?.[key]!=null).map(key=>[titleCase(key),display(key,row[key])]);}
function factsMarkup(row){const entries=facts(row);return entries.length?`<dl class="detail-grid accounting-details">${entries.map(([key,value])=>`<div><dt>${escapeHtml(key)}</dt><dd>${escapeHtml(value)}</dd></div>`).join('')}</dl>`:'';}
function sourceName(row){return row.rule_key||row.return_reference||row.target_return_reference||row.entry_number||row.loan_number||`${titleCase(row.tax_type||'Source')} · ${row.issue_date||row.collection_date||row.recognition_date||row.adjustment_kind||row.minimum_refund_date||row.minimum_application_date||''}`;}
function fieldMarkup(key,kind,data,row){
 const label=labels[key]||titleCase(key),value=kind==='rule'&&row?row[key]??'':'';
 let options=selectValues[key];
 if(key==='rule_evidence_id')options=(data.rules||[]).filter(rule=>rule.tax_type===(kind==='dst'?TAX[0]:TAX[1])).map(rule=>[rule.id,`${rule.rule_key} · version ${rule.rule_version} · ${rule.effective_from} · ${rule.treatment}, rate ${rule.rate} · ${rule.legal_reference}`]);
 if(options)return `<label>${escapeHtml(label)}<select name="${key}" required><option value="">Select…</option>${options.map(([id,title])=>`<option value="${escapeHtml(id)}"${id===value?' selected':''}>${escapeHtml(title)}</option>`).join('')}</select></label>`;
 if(key==='management_rationale'||key==='evidence_note')return `<label>${escapeHtml(label)}<textarea name="${key}" required minlength="20" maxlength="4000">${escapeHtml(value)}</textarea></label>`;
 if(key.endsWith('_digest'))return `<fieldset><legend>${escapeHtml(label.replace('Digest','document checksum'))}</legend><p>Choose the retained file to calculate its checksum locally. The file stays on this device; keep it at the reference entered above.</p><label>Retained document<input type="file" data-evidence-file="${key}"></label><label>SHA-256 checksum<input name="${key}" value="" required pattern="[0-9a-fA-F]{64}" maxlength="64" spellcheck="false"></label></fieldset>`;
 const type=key.endsWith('_date')||['effective_from','effective_to','return_period_start','return_period_end'].includes(key)?'date':'text';
 return `<label>${escapeHtml(label)}<input name="${key}" type="${type}" value="${escapeHtml(value)}"${['effective_to','maturity_max_days'].includes(key)?'':' required'} maxlength="${key==='rule_key'?120:key==='legal_source'||key==='return_reference'||key==='payment_reference'||key==='adjustment_reference'||key==='amendment_reference'||key==='refund_reference'||key==='application_reference'?240:500}"${/amount|tax_due|rate|days/.test(key)?' inputmode="decimal"':''}></label>`;
}

export async function mountTaxEvidence({root,api,session,signal,initialView='rule',confirm=message=>globalThis.confirm?.(message)===true}){
 mounts.get(root)?.();
 const controller=new AbortController();let disposed=false,busy=false,locked=true,generation=0,formRevision=0,offset=0,view=Object.hasOwn(kinds,initialView)?initialView:'rule',data=null,hashing=0,returnHasMore=false,returnNextOffset=200;
 function dispose(){if(disposed)return;disposed=true;generation++;formRevision++;controller.abort();signal?.removeEventListener('abort',dispose);root.innerHTML='';if(mounts.get(root)===dispose)mounts.delete(root);}
 mounts.set(root,dispose);signal?.addEventListener('abort',dispose,{once:true});
 if(signal?.aborted){dispose();return dispose;}
 if(!sessionHasRole(session,'management')){root.textContent='Management access is required.';return dispose;}
 function rejectAccess(){data=null;locked=true;dispose();root.innerHTML='<p role="alert">Tax evidence access is no longer available. Sign in again before reopening this section.</p>';}
 function status(message){if(!disposed){const node=root.querySelector('[data-evidence-status]');if(node)node.textContent=message;}}
 function disable(){
  for(const button of root.querySelectorAll('button'))button.disabled=busy||hashing>0||((locked||globalThis.navigator?.onLine===false)&&(button.getAttribute('data-evidence-save')!==null||button.getAttribute('data-evidence-more')!==null));
  for(const tag of ['input','select','textarea'])for(const field of root.querySelectorAll(tag))field.disabled=busy||hashing>0||locked;
 }
 async function load(){
  if(disposed||busy||hashing)return;
  const revision=++generation;formRevision++;data=null;locked=true;const requestedView=view;
  root.innerHTML='<p role="status">Loading retained tax evidence…</p>';
  try{
   const result=await api.request(`${BASE}${kinds[view].path}?limit=200&offset=${offset}`,{signal:controller.signal});
   if(disposed||revision!==generation)return;
   if(!result||!Array.isArray(result[kinds[view].list])||result.automatic_source_posting!==false)throw new Error('The server did not return the current evidence records.');
   const loaded=structuredClone(result);
   // Rules have independent pagination in the readiness response. Read their
   // complete catalog so a source page never silently loses an applicable rule.
   if(['dst','percentage'].includes(requestedView)){
    const rules=[];
    for(let ruleOffset=0;ruleOffset<10000;ruleOffset+=200){
     const page=ruleOffset===offset?loaded:await api.request(`${BASE}?limit=200&offset=${ruleOffset}`,{signal:controller.signal});
     if(disposed||revision!==generation)return;
     if(!Array.isArray(page?.rules)||page.automatic_source_posting!==false)throw new Error('The retained rule catalog could not be verified.');
     rules.push(...page.rules);
     if(page.rules.length<200){loaded.rules=structuredClone(rules);break;}
     if(ruleOffset===9800)throw new Error('The retained rule catalog is too large to review here. Narrow it with management before continuing.');
    }
   }
   data=loaded;returnHasMore=view==='return'&&loaded.return_liability_candidates.length===200;returnNextOffset=offset+200;locked=false;render();
  }catch(error){if(!disposed&&revision===generation){if([401,403,426].includes(error.status)){rejectAccess();return;}root.innerHTML=`<p role="alert">${escapeHtml(error.message||'Evidence records could not be loaded.')}</p><button type="button" class="button button-outline" data-evidence-reload>Refresh records</button>`;root.querySelector('[data-evidence-reload]')?.addEventListener('click',load);}}
 }
 async function loadMoreLiabilities(){
  if(disposed||busy||hashing||locked||view!=='return'||!returnHasMore)return;
  const revision=generation;busy=true;disable();status('Loading more posted liabilities…');
  try{
   const page=await api.request(`${BASE}/settlements?limit=200&offset=${returnNextOffset}`,{signal:controller.signal});
   if(disposed||revision!==generation)return;
   if(!Array.isArray(page?.return_liability_candidates)||page.automatic_source_posting!==false)throw new Error('The additional liabilities could not be verified.');
   const draft={};for(const field of root.querySelectorAll('[name]'))draft[field.getAttribute('name')]=field.value;
   const checked=new Set(Array.from(root.querySelectorAll('[data-liability]')).filter(box=>box.checked).map(box=>data.return_liability_candidates[Number(box.getAttribute('data-liability'))].posting_id));
   const combined=new Map(data.return_liability_candidates.map(row=>[uuid(row.posting_id),row]));
   for(const row of page.return_liability_candidates)combined.set(uuid(row.posting_id),structuredClone(row));
   data.return_liability_candidates=[...combined.values()];data.permissions=structuredClone(page.permissions);returnHasMore=page.return_liability_candidates.length===200;returnNextOffset+=200;
   render();
   for(const field of root.querySelectorAll('[name]'))if(Object.hasOwn(draft,field.getAttribute('name')))field.value=draft[field.getAttribute('name')];
   for(const box of root.querySelectorAll('[data-liability]'))box.checked=checked.has(data.return_liability_candidates[Number(box.getAttribute('data-liability'))].posting_id);
   updateReturnTotal();status('Additional liabilities loaded. Your selected liabilities and entered return facts are retained. Newly loaded liabilities are unselected.');
  }catch(error){if(!disposed&&revision===generation){if([401,403,426].includes(error.status)){rejectAccess();return;}locked=true;status(`${error.message||'Liabilities could not be loaded.'} Refresh authoritative records before continuing.`);}}
  finally{busy=false;if(!disposed)disable();}
 }
 function updateReturnTotal(){
  const totalNode=root.querySelector('[data-return-total]');if(!totalNode)return;
  try{let total=0n,count=0;for(const box of root.querySelectorAll('[data-liability]'))if(box.checked){total+=cents(money(data.return_liability_candidates[Number(box.getAttribute('data-liability'))].tax_due,true));count++;}totalNode.textContent=`${count} selected (maximum 500) · Declared tax due ${formatMoney(moneyFromCents(total))}`;}catch(error){status(error.message);}
 }
 function render(){
  const revision=generation,rows=data[kinds[view].list],canWrite=allowed(view,data,session);formRevision++;hashing=0;
  root.innerHTML=`<div class="list-stack"><div class="inline-actions accounting-actions">${Object.entries(kinds).map(([key,item])=>`<button type="button" class="button button-outline" data-evidence-view="${key}" aria-pressed="${key===view}">${escapeHtml(item.label)}</button>`).join('')}</div><h3>${escapeHtml(kinds[view].label)}</h3><p>Record reviewed evidence with its retained document reference. Tax amounts come from the reviewed documents and protected source facts. Recording evidence does not post a journal.</p><div role="status" aria-live="polite" data-evidence-status></div><div class="inline-actions accounting-actions"><button type="button" class="button button-outline" data-evidence-reload>Refresh records</button>${offset?'<button type="button" class="button button-outline" data-evidence-previous>Previous records</button>':''}${view==='return'&&returnHasMore?'<button type="button" class="button button-outline" data-evidence-more>Load more liabilities</button>':''}${view!=='return'&&rows.length===200?'<button type="button" class="button button-outline" data-evidence-next>Next records</button>':''}</div><p>${rows.length?`Showing ${view==='return'?'loaded ':''}records ${offset+1}–${offset+rows.length}.`:'0 records.'} ${view==='return'?'Load more to review additional liabilities; selections remain explicit.':'Changing pages clears your selection.'}</p>${!canWrite?'<p>You can review these records. Evidence entry requires the matching Management permission.</p>':''}${view==='rule'&&canWrite?'<button type="button" class="button button-outline" data-evidence-new>New rule evidence</button>':''}<div data-evidence-editor></div>${view==='return'?'':rows.map((row,index)=>`<article class="data-card"><h4>${escapeHtml(sourceName(row))}</h4>${factsMarkup(row)}${row.tax_blocker||row.settlement_blocker?`<p>${escapeHtml(row.tax_blocker||row.settlement_blocker)}</p>`:''}${canWrite&&eligible(view,row)?`<button type="button" class="button button-outline" data-evidence-select="${index}">${view==='rule'?'Record replacement rule':'Record evidence for this source'}</button>`:''}</article>`).join('')}${!rows.length?'<p>No source records on this page.</p>':''}</div>`;
  for(const button of root.querySelectorAll('[data-evidence-view]'))button.addEventListener('click',()=>{if(disposed||busy||hashing||revision!==generation)return;view=button.getAttribute('data-evidence-view');offset=0;void load();});
  root.querySelector('[data-evidence-reload]')?.addEventListener('click',load);
  root.querySelector('[data-evidence-more]')?.addEventListener('click',()=>{if(revision===generation)void loadMoreLiabilities();});
  for(const [selector,delta] of [['data-evidence-previous',-200],['data-evidence-next',200]])root.querySelector(`[${selector}]`)?.addEventListener('click',()=>{if(disposed||busy||hashing||revision!==generation)return;offset=Math.max(0,offset+delta);void load();});
  root.querySelector('[data-evidence-new]')?.addEventListener('click',()=>{if(!disposed&&!busy&&!locked&&!hashing&&revision===generation)showForm(null);});
  for(const button of root.querySelectorAll('[data-evidence-select]'))button.addEventListener('click',()=>{if(disposed||busy||locked||hashing||revision!==generation)return;showForm(rows[Number(button.getAttribute('data-evidence-select'))]);});
  if(view==='return'&&canWrite)showForm(null);
  disable();
 }
 function showForm(row){
  const editor=root.querySelector('[data-evidence-editor]');if(!editor)return;
  const revision=++formRevision,loadedGeneration=generation;hashing=0;
  editor.innerHTML=`<form data-evidence-form class="form-grid"><h4>${row?`Review ${escapeHtml(sourceName(row))}`:view==='rule'?'New retained rule':'Select posted liabilities for this return'}</h4>${factsMarkup(row)}${fields[view].map(key=>fieldMarkup(key,view,data,row)).join('')}${view==='return'?`<fieldset><legend>Loaded posted liabilities (select at most 500)</legend><p>Select the exact liabilities included in the retained return. The declared tax due is their exact total. Every selected item must match the tax type and dates above.</p>${data.return_liability_candidates.map((item,index)=>`<label><input type="checkbox" data-liability="${index}">${escapeHtml(sourceName(item))} · ${escapeHtml(titleCase(item.tax_type))} · ${escapeHtml(item.recognition_date)} · ${escapeHtml(formatMoney(item.tax_due))} · Loan ${escapeHtml(item.loan_id||'—')} · Posting ${escapeHtml(item.posting_id)}</label>`).join('')}<p data-return-total>No liabilities selected.</p></fieldset>`:''}<button type="submit" class="button button-primary" data-evidence-save>Review and record evidence</button></form>`;
  const form=editor.querySelector('[data-evidence-form]');
  const valid=()=>!disposed&&loadedGeneration===generation&&revision===formRevision;
  for(const fileInput of form.querySelectorAll('[data-evidence-file]')){
   let fileRevision=0;
   fileInput.addEventListener('change',async()=>{
    if(!valid()||busy||locked)return;
    const requestRevision=++fileRevision,field=form.querySelector(`[name="${fileInput.getAttribute('data-evidence-file')}"]`),file=fileInput.files?.[0];field.value='';
    if(!file)return;
    if(file.size>50*1024*1024){status('Choose a retained file of at most 50 MB, or enter its verified SHA-256 checksum.');return;}
    hashing++;disable();status('Calculating the retained document checksum locally…');
    try{
     const checksum=await crypto.subtle.digest('SHA-256',await file.arrayBuffer());
     if(valid()&&requestRevision===fileRevision){field.value=Array.from(new Uint8Array(checksum),byte=>byte.toString(16).padStart(2,'0')).join('');status(`Checksum ready for ${file.name}. Keep the file at the retained reference entered above.`);}
    }catch{if(valid()&&requestRevision===fileRevision)status('The checksum could not be calculated. Retry the file or enter its verified SHA-256 checksum.');}
    finally{if(valid()){hashing--;disable();}}
   });
  }
  for(const checkbox of form.querySelectorAll('[data-liability]'))checkbox.addEventListener('change',()=>{
   if(!valid())return;
   updateReturnTotal();
  });
  form.addEventListener('submit',event=>{event.preventDefault();if(valid())void submit(form,row,valid);});
  disable();
 }
 async function submit(form,row,valid){
  if(!valid()||busy||locked||hashing||globalThis.navigator?.onLine===false)return;
  const input={};for(const node of form.querySelectorAll('[name]'))input[node.getAttribute('name')]=node.value;
  if(view==='return')input.liability_posting_ids=Array.from(form.querySelectorAll('[data-liability]')).filter(box=>box.checked).map(box=>data.return_liability_candidates[Number(box.getAttribute('data-liability'))].posting_id);
  let action;
  try{action=buildTaxEvidenceAction(view,data,row,session,input,crypto.randomUUID());}catch(error){status(error.message);return;}
  const review=[action.label,...facts(row).map(([key,value])=>`${key}: ${value}`)];
  if(view==='return')for(const id of action.body.liability_posting_ids){const candidate=data.return_liability_candidates.find(item=>item.posting_id===id);review.push(`${sourceName(candidate)} · ${candidate.recognition_date} · ${formatMoney(candidate.tax_due)} · Loan ${candidate.loan_id||'—'} · Posting ${candidate.posting_id}`);}
  if(input.rule_evidence_id){const rule=data.rules.find(item=>item.id===input.rule_evidence_id);review.push(...facts(rule).map(([key,value])=>`${key}: ${value}`));}
  for(const [key,value] of Object.entries(action.body))if(value!==null&&!['confirm','idempotency_key','liability_posting_ids'].includes(key)&&!key.endsWith('_id'))review.push(`${labels[key]||titleCase(key)}: ${display(key,value)}`);
  review.push('Record this retained evidence. Existing history remains available. No journal will be posted by this action.');
  // Latch before the asynchronous confirmation to prevent two submissions from
  // creating different idempotency identities for one review.
  busy=true;disable();let sent=false;
  try{
   if(!await confirm(review.join('\n'))||!valid()||locked)return;
   if(!allowed(view,data,session)){rejectAccess();return;}
   sent=true;status('Recording reviewed evidence…');
   const result=await api.request(action.path,{method:'POST',body:action.body,financial:true,signal:controller.signal});
   if(!valid())return;
   if(!receiptMatches(view,row,action.body,result))throw new Error('The server receipt is uncertain.');
   // A POST acknowledgement alone never unlocks another write. An authoritative
   // reread is required even if the response body is missing or malformed.
   locked=true;status('Evidence recorded. Refresh authoritative records before another action.');
  }catch(error){if(valid()){if([401,403,426].includes(error.status)){rejectAccess();return;}if(sent)locked=true;status(`${error.message||'The result is uncertain.'}${sent?' The result may be uncertain. Refresh authoritative records before another action.':''}`);}}
  finally{busy=false;if(valid())disable();}
 }
 await load();return dispose;
}
