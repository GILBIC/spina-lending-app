import {asArray,escapeHtml,formatDate,formatDateTime} from './ui.js';
import {formatAuthoritativeMoney} from './client-schedule.js';
const recorded=value=>value==null||value===''?'Not recorded':escapeHtml(value);
export function renderClientPaymentDetails(payment={}) {
 const fields=[['Transaction',recorded(payment.transaction_id)],['Receipt',recorded(payment.receipt_number)],['Loan',recorded(payment.loan_number)],['Collector',recorded(payment.collector_name)],['Collection date',payment.collection_date?formatDate(payment.collection_date):'Not recorded'],['Recorded',payment.recorded_at?formatDateTime(payment.recorded_at):'Not recorded'],['Amount',formatAuthoritativeMoney(payment.amount)],['Covered dates',asArray(payment.covered_dates).length?asArray(payment.covered_dates).map(escapeHtml).join(', '):'Not recorded'],['Previous balance',formatAuthoritativeMoney(payment.previous_balance)],['Official balance',formatAuthoritativeMoney(payment.official_balance)],['Origin',recorded(payment.collection_origin)],['Status',payment.is_voided?'Voided':recorded(payment.status)],['Void date',payment.voided_at?formatDateTime(payment.voided_at):'Not recorded'],['Void reason',recorded(payment.void_reason)],['Record version',recorded(payment.edit_version)],['Note',recorded(payment.note)],['Remittance reference',recorded(payment.remittance_number)],['Remittance status',recorded(payment.remittance_status)],['Remittance submitted',payment.remittance_submitted_at?formatDateTime(payment.remittance_submitted_at):'Not recorded'],['Remittance received',payment.remittance_received_at?formatDateTime(payment.remittance_received_at):'Not recorded']];
 return `<article class="notice-card client-payment-details" tabindex="-1"><h3>Payment record ${payment.is_voided?'· Voided':''}</h3><div class="loan-meta">${fields.map(([label,value])=>`<div class="detail-item"><span>${label}</span><strong>${value==='—'?'Not recorded':value}</strong></div>`).join('')}</div><p class="meta">Current record copies reflect corrections and voids. Internal remittance is separate from your official payment record.</p><button class="button button-secondary" type="button" data-payment-record-copy="${escapeHtml(payment.transaction_id)}">Download ${payment.is_voided?'voided ':''}payment record copy (PDF)</button><button class="button button-secondary" type="button" data-payment-detail-close>Close details</button><div data-payment-download-status role="status"></div></article>`;
}
export function bindClientPaymentDetails({root,paymentsState,onDownload,signal,isCurrent=()=>true,beforeTaskChange,afterTaskChange}) {
 let disposed=false;const removers=[],disclosures=new Set();
 for(const button of root.querySelectorAll('[data-payment-details]')){
  let closeDisclosure=()=>{};
  const open=()=>{
   if(disposed||signal?.aborted||!isCurrent())return;
   const id=button.getAttribute('data-payment-details');const state=typeof paymentsState==='function'?paymentsState():paymentsState;
   const record=state?.status==='ready'?asArray(state.data?.payments).find(payment=>payment.transaction_id===id):null;if(!record)return;
   const panel=root.querySelector(`[data-payment-detail-panel="${id}"]`);if(!panel)return;
   closeDisclosure();
   const controller=new AbortController();let active=true,downloading=false;
   const current=()=>!disposed&&active&&!signal?.aborted&&isCurrent();
   beforeTaskChange?.();panel.hidden=false;panel.innerHTML=renderClientPaymentDetails(record);afterTaskChange?.();panel.querySelector('.client-payment-details')?.focus?.();
   const close=panel.querySelector('[data-payment-detail-close]'),copy=panel.querySelector('[data-payment-record-copy]'),status=panel.querySelector('[data-payment-download-status]');
   const onClose=()=>{if(!current())return;closeDisclosure();beforeTaskChange?.();panel.hidden=true;panel.innerHTML='';button.focus?.();afterTaskChange?.();};
   const download=async()=>{
    const state=typeof paymentsState==='function'?paymentsState():paymentsState;
    if(!current()||downloading||state?.status!=='ready'||!asArray(state.data?.payments).some(payment=>payment.transaction_id===id))return;
    downloading=true;copy.disabled=true;status.textContent='';
    try{await onDownload?.(id,{signal:controller.signal});}
    catch(error){if(current())status.textContent=error?.message||'Download unavailable.';}
    finally{if(current()){downloading=false;copy.disabled=false;}}
   };
   closeDisclosure=()=>{if(!active)return;active=false;controller.abort();copy.disabled=true;close.removeEventListener('click',onClose);copy.removeEventListener('click',download);disclosures.delete(closeDisclosure);};
   disclosures.add(closeDisclosure);close.addEventListener('click',onClose);copy.addEventListener('click',download);
  };
  button.addEventListener('click',open);removers.push(()=>button.removeEventListener('click',open));
 }
 const dispose=()=>{if(disposed)return;disposed=true;for(const close of disclosures)close();for(const remove of removers)remove();signal?.removeEventListener('abort',dispose);};
 signal?.addEventListener('abort',dispose,{once:true});if(signal?.aborted)dispose();return dispose;
}
