import {buildCollectionSubmission} from './collector-contract.js';
import {collectorMutation,collectionResultMatches} from './collector-workflow-contract.js';
import {allocationField,followupFields,readFollowup} from './collector-workflows.js';
import {escapeHtml as h,hasPermission} from './ui.js';
import {formatAuthoritativeMoney as formatMoney} from './client-schedule.js';

const val=(root,name)=>root.querySelector(`[name="${name}"]`)?.value || '';
const available=entry=>entry.can_collect_mobile === true && entry.can_enter_payment === true && !entry.processed_today && Boolean(entry.route_revision);
export function renderOtherAreaEntries(entries) {
  return entries.map((entry,index)=>`<article class="list-item"><h3>${h(entry.client_name)} · ${h(entry.loan_type)}</h3><p>${h(entry.area)} · Assigned Collector: ${h(entry.assigned_collector_name)} · Balance ${formatMoney(entry.remaining_balance)}</p>${available(entry) ? `<form data-other-payment="${index}" class="entry-form"><label>Cash received<input name="amount" inputmode="decimal" required /></label>${allocationField()}${followupFields()}<label>Note<textarea name="note" maxlength="500"></textarea></label><label><input name="recorderConfirmation" type="checkbox" required />I am recording this collection. The assigned Collector remains ${h(entry.assigned_collector_name)}.</label><button type="submit" class="button button-primary">Save cross-area payment</button></form>` : `<p>${h(entry.processed_today ? `Recorded today by ${entry.today_collector_name || 'another collector'}.` : entry.collection_message || 'Collection unavailable.')}</p>`}</article>`).join('') || '<p>No matching other-area client is available.</p>';
}

export function mountCollectorOtherArea({root,api,session,routeDate,guard,identity,onSaved,signal}) {
  if(!/^\d{4}-\d{2}-\d{2}$/.test(routeDate || '')) {
    root.textContent='Refresh today’s route before searching or collecting other-area payments.';
    return ()=>{};
  }
  let disposed=false;let searchVersion=0;let previewVersion=0;let reviewedTarget=null;
  const current=()=>!disposed && guard.current && !signal?.aborted;
  root.innerHTML=`<h2>Other-area collection</h2><p>You remain the recorder. Assigned ownership and cash custody are preserved by SPINA.</p><form data-other-search class="entry-form"><label>Client name, code, phone or area<input name="query" minlength="2" maxlength="120" required /></label><button class="button button-outline" type="submit">Search other-area clients</button></form><div data-other-results></div><div data-cross-remittance></div><div data-other-status role="status"></div>`;
  const status=message=>{if(current()) root.querySelector('[data-other-status]').textContent=message;};
  const run=async operation=>{
    if(!current() || !guard.begin()) return;
    try {await operation();}catch(error){if(current())status(error.message);}finally{guard.finish();}
  };
  const search=root.querySelector('[data-other-search]');
  search.addEventListener('submit',event=>{
    event.preventDefault();
    if(!hasPermission(session,'collection.create'))return;
    run(async()=>{
      const query=val(search,'query').trim();if(query.length<2)throw new Error('Enter at least two characters.');
      const version=++searchVersion;
      const response=await api.request(`/api/v1/collector/other-area-clients/search?q=${encodeURIComponent(query)}&limit=25`);
      if(!current() || version!==searchVersion)return;
      const entries=Array.isArray(response)?response:[];
      const results=root.querySelector('[data-other-results]');results.innerHTML=renderOtherAreaEntries(entries);
      for(const form of results.querySelectorAll('[data-other-payment]'))form.addEventListener('submit',event=>{
        event.preventDefault();run(async()=>{
          const entry=entries[Number(form.getAttribute('data-other-payment'))];
          if(version!==searchVersion || !entry || !available(entry))throw new Error('Search again before recording this payment.');
          if(!form.querySelector('[name="recorderConfirmation"]').checked)throw new Error('Confirm the assigned Collector and your recorder role first.');
          const request=buildCollectionSubmission({...identity(),entry,routeDate,entryType:'payment',amount:val(form,'amount'),note:val(form,'note'),pastDueFollowup:readFollowup(form),paymentAllocationIntent:val(form,'allocation') || 'scheduled'});
          const result=await collectorMutation({api,guard,path:'/api/v1/collector/collections',options:{method:'POST',...request},verify:collectionResultMatches(request)});
          if(current())await onSaved(result);
        });
      });
      guard.sync();status('Review the client and assigned Collector before recording.');
    });
  });
  // Search text edits also invalidate old results; a late response cannot
  // replace the identity the Collector is currently looking for.
  search.querySelector('[name="query"]').addEventListener('input',()=>{searchVersion+=1;root.querySelector('[data-other-results]').innerHTML='';});
  const loadRemittance=async()=>{
    const container=root.querySelector('[data-cross-remittance]');
    try {
      const date=`collection_date=${encodeURIComponent(routeDate)}`;
      const [targets,history]=await Promise.all([
        hasPermission(session,'remittance.create') ? api.request(`/api/v1/collector/cross-remittances/targets?${date}`):[],
        hasPermission(session,'remittance.view') ? api.request(`/api/v1/collector/cross-remittances/history?${date}`):[],
      ]);
      if(!current())return;
      container.innerHTML=`<h3>Other-area cash and remittance</h3>${targets.length ? `<form data-cross-form class="entry-form"><label>Recipient<select name="recipient">${targets.map((item,index)=>`<option value="${index}">${h(item.recipient_name)} · ${h(item.role_name)} · ${formatMoney(item.total_amount)}</option>`).join('')}</select></label><button type="button" class="button button-outline" data-cross-preview>Review remittance</button><div data-cross-summary></div><label>Note<textarea name="note" maxlength="500"></textarea></label><button type="submit" class="button button-primary" data-cross-save disabled>Submit reviewed remittance</button></form>`:'<p>No other-area cash is awaiting remittance.</p>'}${history.map(item=>`<p>${h(item.client_name)} · ${h(item.receipt_number)} · ${formatMoney(item.amount)} · ${h(item.custody_status || item.status || '')} · Assigned: ${h(item.assigned_collector_name || '')}${item.remittance_recipient_name ? ` · Recipient: ${h(item.remittance_recipient_name)}` : ''}</p>`).join('')}`;
      const form=container.querySelector('[data-cross-form]');if(!form)return;
      const invalidate=()=>{previewVersion+=1;reviewedTarget=null;form.querySelector('[data-cross-save]').disabled=true;form.querySelector('[data-cross-summary]').innerHTML='';};
      form.querySelector('[name="recipient"]').addEventListener('change',invalidate);
      form.querySelector('[data-cross-preview]').addEventListener('click',()=>run(async()=>{
        invalidate();const version=previewVersion;const target=targets[Number(val(form,'recipient')) || 0];
        const query=new URLSearchParams({collection_date:routeDate,recipient_user_id:target.recipient_user_id,recipient_capacity:target.recipient_capacity});
        const preview=await api.request(`/api/v1/collector/cross-remittances/preview?${query}`);
        if(!current() || version!==previewVersion)return;
        reviewedTarget=target;
        form.querySelector('[data-cross-summary]').innerHTML=`<p>Total ${formatMoney(preview.total_amount)} · ${h(preview.transaction_count)} transactions · ${h(preview.client_count)} clients</p>${(preview.items || []).map(item=>`<p>${h(item.client_name)} · ${h(item.loan_type)} · ${formatMoney(item.amount)}</p>`).join('')}`;
        form.querySelector('[data-cross-save]').disabled=guard.locked || !preview.transaction_count;
      }));
      form.addEventListener('submit',event=>{event.preventDefault();run(async()=>{
        const target=targets[Number(val(form,'recipient')) || 0];if(!reviewedTarget || reviewedTarget!==target)throw new Error('Review this recipient’s remittance first.');
        const result=await collectorMutation({api,guard,path:'/api/v1/collector/cross-remittances',options:{method:'POST',body:{recipient_user_id:target.recipient_user_id,recipient_capacity:target.recipient_capacity,collection_date:routeDate,note:val(form,'note').trim()}},verify:result=>typeof result.remittance_id==='string' && result.remittance_id.length>0 && result.recipient_user_id===target.recipient_user_id && result.recipient_capacity===target.recipient_capacity && result.collection_date===routeDate});
        if(current())await onSaved(result);
      });});
      guard.sync();
    }catch(error){if(current())container.textContent=error.message;}
  };
  if(routeDate && (hasPermission(session,'remittance.create') || hasPermission(session,'remittance.view')))loadRemittance();
  function dispose(){disposed=true;searchVersion+=1;previewVersion+=1;signal?.removeEventListener('abort',dispose);}
  signal?.addEventListener('abort',dispose,{once:true});if(signal?.aborted)dispose();
  return dispose;
}
