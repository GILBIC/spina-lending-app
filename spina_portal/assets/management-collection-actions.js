import {asArray,escapeHtml as h,formatMoney,hasPermission} from './ui.js';
import {createCollectorWriteGuard} from './collector-write-guard.js';
import {collectorMutation} from './collector-workflow-contract.js';
import {mountCollectorOtherArea} from './collector-other-area.js';

const ACTIVATION='/api/v1/management/financial-accounting/contract-collection-activation';
const NO_COLLECTION='/api/v1/management/no-collection';
const value=(root,name)=>String(root.querySelector(`[name="${name}"]`)?.value||'').trim();
const note=(name,label)=>`<label>${label}<textarea name="${name}" maxlength="500" required></textarea></label>`;
const button=(label,extra='')=>`<button class="button button-primary" ${extra}>${label}</button>`;

const readinessLabel=loan=>loan.is_active?'Active':loan.can_activate?'Ready':'Blocked';
const readinessTone=loan=>loan.is_active?'success':loan.can_activate?'warning':'danger';
function plainBlocker(reason) {
  const text=String(reason||'').trim();
  if(text==='Signed-contract schedule has not been registered.')return 'verified signed repayment schedule';
  if(text==='Current schedule is not backed by verified signed-contract evidence.')return 'verified signed-contract evidence';
  if(text.startsWith('Contract schedule/payment allocation is not DPD-ready'))return 'schedule/payment allocation setup';
  if(text==='Loan type is not using direct remaining-balance collection mode.')return 'supported collection mode';
  if(/balance/i.test(text)&&/reconcil/i.test(text))return 'balance reconciliation';
  if(/accounting/i.test(text))return 'accounting readiness';
  return 'another readiness requirement';
}
function blockerSummary(loans) {
  const counts=new Map();
  for(const loan of loans)for(const reason of asArray(loan.blockers)){
    const label=plainBlocker(reason);
    counts.set(label,(counts.get(label)||0)+1);
  }
  const repeated=[...counts.entries()].filter(([,count])=>count>1);
  if(!repeated.length)return '';
  return `<div class="notice-card warning contract-common-blockers" data-contract-common-blockers>
    <strong>Common readiness issues</strong>
    <ul>${repeated.map(([label,count])=>`<li>${count} loans need ${h(label)}.</li>`).join('')}</ul>
  </div>`;
}
function contractReadinessMarkup(result) {
  const loans=asArray(result.loans);
  if(!loans.length)return '<p>No loan readiness is available.</p>';
  const active=loans.filter(loan=>loan.is_active===true).length;
  const ready=loans.filter(loan=>loan.is_active!==true&&loan.can_activate===true).length;
  const blocked=loans.length-active-ready;
  return `<div class="contract-readiness-summary" data-contract-readiness-summary>
      <span><strong>${active}</strong> Active</span>
      <span><strong>${ready}</strong> Ready</span>
      <span><strong>${blocked}</strong> Blocked</span>
    </div>
    ${blockerSummary(loans)}
    <div class="contract-loan-list">${loans.map((loan,index)=>{
      const blockers=asArray(loan.blockers);
      const status=readinessLabel(loan);
      const detail=blockers.length?`<details class="contract-technical-details" data-contract-technical-details>
        <summary>${status==='Blocked'?'Why this loan is blocked':'Readiness details'}</summary>
        <ul>${blockers.map(reason=>`<li>${h(reason)}</li>`).join('')}</ul>
      </details>`:'';
      const action=result.permission===true&&(loan.can_activate===true||loan.can_deactivate===true)
        ?`<form class="entry-form contract-activation-form" data-contract-activate="${index}">${note('activation_note','Evidence / reason')}${button(loan.can_activate?'Activate contract collection':'Deactivate contract collection','type="submit"')}</form>`
        :'';
      return `<article class="contract-loan-row" data-contract-loan="${h(loan.loan_id||index)}">
        <div class="contract-loan-heading">
          <div><strong>${h(loan.client_name||'Client')}</strong><span class="meta">${h(loan.loan_number||'Loan')}${loan.loan_type_name?` · ${h(loan.loan_type_name)}`:''} · ${formatMoney(loan.remaining_balance)}</span></div>
          <span class="badge ${readinessTone(loan)}">${status}</span>
        </div>
        ${detail}
        ${action}
      </article>`;
    }).join('')}</div>`;
}

export function mountManagementCollectionActions(options) {
  const {root,api,session,sessionStore,signal,confirm=message=>globalThis.confirm?.(message),now=()=>new Date()}=options;
  if(!root)return ()=>{};
  let disposed=false,busy=false,directCleanup=()=>{},replacementCleanup=null;
  const controller=new AbortController();
  const can=permission=>hasPermission(session,permission);
  const current=()=>!disposed&&!signal?.aborted;
  const read=path=>api.request(path,{signal:controller.signal});
  const status=message=>{const node=root.querySelector('[data-management-collection-status]');if(current()&&node)node.textContent=message;};
  const lock=()=>{
    if(!current())return;
    for(const node of [...root.querySelectorAll('button'),...root.querySelectorAll('input'),...root.querySelectorAll('textarea')])node.disabled=busy||(guard.locked&&node.getAttribute('data-management-collection-refresh')===null);
  };
  let guard;
  guard=createCollectorWriteGuard({signal:controller.signal,onLock:message=>{status(message);if(guard)lock();}});
  const run=async operation=>{
    if(!current()||!guard.begin())return;busy=true;lock();
    try{await operation();}catch(error){if(current()){status(error.message);if([401,403,426].includes(error.status)){dispose();root.textContent=error.status===426?'Update SPINA before continuing.':'Access is unavailable. Sign in again before continuing.';}else if(error.status===409)guard.lock('The record changed. Refresh the authoritative record before another action.');}}
    finally{busy=false;guard.finish();lock();}
  };
  const save=async(path,body,verify)=>collectorMutation({api,path,options:{method:'POST',body},guard,verify});
  const workflows=[
    can('lending.contract_collection.activate')&&['contract','Contract collection'],
    can('lending.no_collection.manage')&&['no-collection','No Collection'],
    can('collection.void.unremitted')&&['void','Void payment'],
    can('collection.create')&&['direct','Record payment'],
  ].filter(Boolean);
  const initialWorkflow=workflows[0]?.[0]||'';
  root.innerHTML=`<div class="section-heading collection-actions-heading"><div><h2>Collection actions</h2><p>Choose one protected workflow. Review the borrower and server evidence before confirming a change.</p></div><button class="button button-outline" type="button" data-management-collection-refresh>Refresh</button></div>
    <div class="collection-action-tabs" role="tablist" aria-label="Collection actions">
      ${workflows.map(([id,label],index)=>`<button class="collection-action-tab" type="button" role="tab" data-management-collection-tab="${id}" aria-selected="${index===0?'true':'false'}">${label}</button>`).join('')}
    </div>
    <p data-management-collection-status role="status" aria-live="polite"></p>
    ${can('lending.contract_collection.activate')?`<section class="data-card collection-action-panel" data-management-collection-panel="contract"${initialWorkflow==='contract'?'':' hidden'}><div class="section-heading"><div><h3>Contract collection</h3><p>Activate only loans whose verified contract, schedule, balance and accounting checks are ready.</p></div></div><div data-contract-collection>Loading readiness…</div></section>`:''}
    ${can('lending.no_collection.manage')?`<section class="data-card collection-action-panel" data-management-collection-panel="no-collection"${initialWorkflow==='no-collection'?'':' hidden'}><h3>No Collection</h3><form class="entry-form" data-no-collection-search><label>Client, loan number or area<input name="query" minlength="2" required></label>${button('Find loan','type="submit"')}</form><div data-no-collection-results></div><div data-no-collection-detail></div></section>`:''}
    ${can('collection.void.unremitted')?`<section class="data-card collection-action-panel danger-panel" data-management-collection-panel="void"${initialWorkflow==='void'?'':' hidden'}><h3>Void incorrect payment</h3><p class="meta">Use only for an incorrect unremitted payment. The reversal is permanently recorded.</p><form class="entry-form" data-void-search><label>Receipt number<input name="receipt_number" maxlength="120" required></label>${button('Find receipt','type="submit"')}</form><div data-void-detail></div></section>`:''}
    ${can('collection.create')?`<section class="data-card collection-action-panel" data-management-collection-panel="direct"${initialWorkflow==='direct'?'':' hidden'} data-management-direct-payment></section>`:''}`;
  const activateWorkflow=id=>{
    for(const panel of root.querySelectorAll('[data-management-collection-panel]')){
      if(panel.getAttribute('data-management-collection-panel')===id)panel.removeAttribute('hidden');
      else panel.setAttribute('hidden','');
    }
    for(const tab of root.querySelectorAll('[data-management-collection-tab]')){
      tab.setAttribute('aria-selected',tab.getAttribute('data-management-collection-tab')===id?'true':'false');
    }
  };
  for(const tab of root.querySelectorAll('[data-management-collection-tab]'))tab.addEventListener('click',()=>activateWorkflow(tab.getAttribute('data-management-collection-tab')));
  root.querySelector('[data-management-collection-refresh]').addEventListener('click',()=>{if(busy||disposed)return;dispose();replacementCleanup=mountManagementCollectionActions(options);});

  async function loadActivations(){
    const result=await read(ACTIVATION);if(!current())return;
    const target=root.querySelector('[data-contract-collection]');
    target.innerHTML=contractReadinessMarkup(result);
    for(const form of target.querySelectorAll('[data-contract-activate]'))form.addEventListener('submit',event=>{event.preventDefault();run(async()=>{
      const loan=result.loans[Number(form.getAttribute('data-contract-activate'))];
      const activationNote=value(form,'activation_note');if(!activationNote)throw new Error('Enter the evidence or reason.');
      const action=loan.can_activate?'activate':'deactivate';
      if(!confirm(`${action==='activate'?'Activate':'Deactivate'} contract collection for ${loan.client_name} (${loan.loan_number})?`))return;
      await save(`${ACTIVATION}/${encodeURIComponent(loan.loan_id)}/${action}`,{activation_note:activationNote,confirm_action:true},saved=>saved.loan_id===loan.loan_id&&saved.is_active===(action==='activate'));
      if(current()){await loadActivations();status('Contract collection change confirmed by the server.');}
    });});
  }

  async function loadSchedule(loanId){
    const state=await read(`${NO_COLLECTION}/loans/${encodeURIComponent(loanId)}`);if(!current())return;
    if(state.loan_id!==loanId||!Number.isSafeInteger(state.operational_version))throw new Error('The loan schedule could not be verified. Refresh before continuing.');
    let preview=null;let generation=0;
    const target=root.querySelector('[data-no-collection-detail]');
    target.innerHTML=`<h4>${h(state.client_name)} · ${h(state.loan_number||'')}</h4><form class="entry-form" data-no-collection-declare><label>No Collection date<input type="date" name="no_collection_date" required></label>${note('reason','Reason')}${button('Preview schedule shift','type="button" data-no-collection-preview')}<div data-no-collection-shifts></div>${button('Declare No Collection','type="submit"')}</form>${asArray(state.active_no_collection).map((item,index)=>`<form class="entry-form" data-no-collection-reverse="${index}"><p>Active No Collection: ${h(item.no_collection_date)} · ${h(item.reason)}</p>${note('reversal_reason','Reversal reason')}${button('Reverse No Collection','type="submit"')}</form>`).join('')}`;
    const form=target.querySelector('[data-no-collection-declare]');
    const invalidate=()=>{preview=null;generation++;form.querySelector('[data-no-collection-shifts]').innerHTML='';};
    form.querySelector('[name="no_collection_date"]').addEventListener('input',invalidate);
    form.querySelector('[data-no-collection-preview]').addEventListener('click',()=>run(async()=>{
      invalidate();const version=generation;const date=value(form,'no_collection_date');if(!/^\d{4}-\d{2}-\d{2}$/.test(date))throw new Error('Choose the No Collection date.');
      const result=await api.request(`${NO_COLLECTION}/preview`,{method:'POST',body:{loan_id:loanId,expected_operational_version:state.operational_version,no_collection_date:date},signal:controller.signal});
      if(!current()||version!==generation||value(form,'no_collection_date')!==date)return;
      if(result.loan_id!==loanId||result.operational_version!==state.operational_version||result.no_collection_date!==date||!asArray(result.shifts).length)throw new Error('The preview does not match this schedule. Refresh before continuing.');
      preview=result;
      form.querySelector('[data-no-collection-shifts]').innerHTML=`<p>Review ${result.shifts.length} schedule shifts:</p><ul>${result.shifts.map(shift=>`<li>Installment ${h(shift.installment_number)}: ${h(shift.prior_effective_due_date)} → ${h(shift.new_effective_due_date)}</li>`).join('')}</ul>`;
    }));
    form.addEventListener('submit',event=>{event.preventDefault();run(async()=>{
      if(!preview||preview.no_collection_date!==value(form,'no_collection_date'))throw new Error('Preview this date and review the schedule changes first.');
      const reason=value(form,'reason');if(!reason)throw new Error('Enter the reason.');
      if(!confirm(`Declare No Collection on ${preview.no_collection_date} for ${state.client_name}?`))return;
      await save(NO_COLLECTION,{no_collection_date:preview.no_collection_date,reason,loans:[{loan_id:loanId,expected_operational_version:state.operational_version}]},saved=>asArray(saved.loans).length===1&&saved.loans[0].loan_id===loanId&&saved.loans[0].resulting_operational_version>state.operational_version);
      if(current()){await loadSchedule(loanId);status('No Collection declaration confirmed.');}
    });});
    for(const reverse of target.querySelectorAll('[data-no-collection-reverse]'))reverse.addEventListener('submit',event=>{event.preventDefault();run(async()=>{
      const item=state.active_no_collection[Number(reverse.getAttribute('data-no-collection-reverse'))];const reason=value(reverse,'reversal_reason');if(!reason)throw new Error('Enter the reversal reason.');
      if(!confirm(`Reverse No Collection for ${state.client_name} on ${item.no_collection_date}?`))return;
      await save(`${NO_COLLECTION}/${encodeURIComponent(item.adjustment_id)}/reverse`,{expected_operational_version:state.operational_version,reason},saved=>saved.loan_id===loanId&&saved.reverses_adjustment_id===item.adjustment_id&&saved.resulting_operational_version>state.operational_version);
      if(current()){await loadSchedule(loanId);status('No Collection reversal confirmed.');}
    });});
  }
  const search=root.querySelector('[data-no-collection-search]');
  search?.addEventListener('submit',event=>{event.preventDefault();run(async()=>{
    const query=value(search,'query');if(query.length<2)throw new Error('Enter at least two characters.');
    root.querySelector('[data-no-collection-detail]').innerHTML='';
    const result=await read(`/api/v1/management/loans?q=${encodeURIComponent(query)}&status=active`);if(!current())return;
    const target=root.querySelector('[data-no-collection-results]');
    target.innerHTML=asArray(result.loans).map((loan,index)=>button(`${h(loan.client_name)} · ${h(loan.loan_number)}`,`type="button" data-no-collection-loan="${index}"`)).join('')||'<p>No matching active loan.</p>';
    for(const item of target.querySelectorAll('[data-no-collection-loan]'))item.addEventListener('click',()=>run(()=>loadSchedule(result.loans[Number(item.getAttribute('data-no-collection-loan'))].loan_id)));
  });});

  async function loadReceipt(receipt){
    const candidate=await read(`/api/v1/management/collections/by-receipt/${encodeURIComponent(receipt)}`);if(!current())return;
    if(candidate.receipt_number!==receipt||!candidate.transaction_id)throw new Error('The receipt identity could not be verified. Search again.');
    const target=root.querySelector('[data-void-detail]');
    target.innerHTML=`<p>${h(candidate.client_name)} · ${h(candidate.receipt_number)} · ${formatMoney(candidate.amount)} · ${h(candidate.collection_date||'')}</p>${candidate.is_locked===false&&candidate.is_voided===false?`<form class="entry-form" data-void-save>${note('void_reason','Permanent reason for voiding')}${button('Void incorrect payment','type="submit"')}</form>`:'<p>This payment is locked or already voided.</p>'}`;
    target.querySelector('[data-void-save]')?.addEventListener('submit',event=>{event.preventDefault();run(async()=>{
      const reason=value(event.currentTarget,'void_reason');if(reason.length<3)throw new Error('Enter a clear void reason.');
      if(!confirm(`Void ${receipt} for ${candidate.client_name}, ${formatMoney(candidate.amount)}? This records a permanent reversal.`))return;
      const body={reason};if(can('lending.extra_principal.reverse'))body.idempotency_key=crypto.randomUUID();
      await save(`/api/v1/management/collections/${encodeURIComponent(candidate.transaction_id)}/void`,body,saved=>saved.transaction_id===candidate.transaction_id&&saved.receipt_number===receipt);
      if(current()){await loadReceipt(receipt);status('Payment void confirmed. Review the restored official balance.');}
    });});
  }
  const voidSearch=root.querySelector('[data-void-search]');
  voidSearch?.addEventListener('submit',event=>{event.preventDefault();const receipt=value(voidSearch,'receipt_number').toUpperCase();if(receipt)run(()=>loadReceipt(receipt));});
  if(can('collection.create')){
    const date=new Intl.DateTimeFormat('en-CA',{timeZone:'Asia/Manila',year:'numeric',month:'2-digit',day:'2-digit'}).format(now());
    directCleanup=mountCollectorOtherArea({root:root.querySelector('[data-management-direct-payment]'),api,session,mode:'management',routeDate:date,guard,signal:controller.signal,identity:()=>({deviceId:sessionStore.deviceId(),deviceSequence:sessionStore.nextDeviceSequence(),clientTransactionId:crypto.randomUUID(),recordedAt:now().toISOString()}),onSaved:async result=>{if(current()){root.querySelector('[data-other-results]').innerHTML='';status(`Direct payment confirmed: ${result.receipt_number}. Search again before another payment.`);}}});
  }
  guard.sync();
  if(can('lending.contract_collection.activate'))run(loadActivations);
  function dispose(){if(replacementCleanup){replacementCleanup();replacementCleanup=null;}if(disposed)return;disposed=true;controller.abort();guard.dispose();directCleanup();root.innerHTML='';signal?.removeEventListener('abort',dispose);}
  signal?.addEventListener('abort',dispose,{once:true});if(signal?.aborted)dispose();
  return dispose;
}
