import {escapeHtml as h,hasPermission} from './ui.js';
import {formatAuthoritativeMoney as formatMoney} from './client-schedule.js';
import {collectorMutation} from './collector-workflow-contract.js';

export function collectorRenewalActions(item,session) {
  const actions=[];
  if(item.status === 'pending' && !item.collector_recommendation && hasPermission(session,'renewal.recommend.assigned')) actions.push('recommendation');
  if(item.status === 'approved' && item.client_decision !== 'declined' && hasPermission(session,'renewal.cash_custody.assigned')) {
    if(item.cash_released_to_collector_at && !item.collector_cash_received_at) actions.push('cash-received');
    else if(item.collector_cash_received_at && !item.cash_given_to_client_at) actions.push('cash-given');
    else if(item.cash_given_to_client_at && !['approved','under_review'].includes(item.handover_proof_status)) actions.push('handover-photo');
  }
  return actions;
}

export function renderCollectorRenewals(items,session) {
  if(!items.length) return '<p>No assigned renewal request is available.</p>';
  return items.map(item=>`<article class="list-item"><h3>${h(item.client_name)} · ${h(item.loan_number || '')}</h3><p>${h(item.status)} · Cash to client ${item.net_release_amount == null ? 'Unavailable' : formatMoney(item.net_release_amount)} · Handover proof ${h(item.handover_proof_status || 'not submitted')}</p><p>${item.client_cash_confirmed_at ? 'Client cash receipt confirmed.' : 'Client confirmation remains a separate step.'}</p>${collectorRenewalActions(item,session).map(action=>`<form class="entry-form" data-renewal-id="${h(item.request_id)}" data-renewal-action="${action}">${action === 'recommendation' ? '<label>Recommendation<select name="recommendation"><option value="recommend">Recommend</option><option value="do_not_recommend">Do not recommend</option></select></label><label>Reason<select name="reasonCode"><option value="Good payment history">Good payment history</option><option value="Near or fully completed term">Near or fully completed term</option><option value="Stable field collection pattern">Stable field collection pattern</option><option value="Good client history">Good client history</option><option value="Frequent missed payments">Frequent missed payments</option><option value="Payment capacity concern">Payment capacity concern</option><option value="Field verification concern">Field verification concern</option><option value="Client conduct concern">Client conduct concern</option><option value="Other">Other</option></select></label><label>Comment<textarea name="comment" maxlength="1000"></textarea></label>' : action === 'handover-photo' ? '<label>Handover photo<input name="photo" type="file" accept="image/jpeg,image/png,image/webp" capture="environment" required /></label><p>JPEG, PNG or WebP, up to 8 MB. Management reviews the photo.</p>' : `<label><input name="physicalConfirmation" type="checkbox" required />I physically ${action === 'cash-received' ? 'received this cash from Management' : 'gave this cash to the client'}.</label>`}<button type="submit" class="button button-primary">${{'recommendation':'Send recommendation','cash-received':'Confirm cash received','cash-given':'Confirm cash given','handover-photo':'Submit handover photo'}[action]}</button></form>`).join('')}</article>`).join('');
}

export function mountCollectorRenewals({root,api,session,guard,onSaved,signal}) {
  let disposed=false;
  const current=()=>!disposed && guard.current && !signal?.aborted;
  root.innerHTML='<p>Loading assigned renewals…</p>';
  const load=async()=>{
    try {
      const data=await api.request('/api/v1/collector/renewals');
      if(!current()) return;
      const items=Array.isArray(data?.requests) ? data.requests : [];
      root.innerHTML=renderCollectorRenewals(items,session)+'<div data-renewal-status role="status"></div>';
      const status=message=>{if(current()) root.querySelector('[data-renewal-status]').textContent=message;};
      for(const form of root.querySelectorAll('[data-renewal-action]')) form.addEventListener('submit',async event=>{
        event.preventDefault();if(!current() || !guard.begin()) return;
        try {
          const id=form.getAttribute('data-renewal-id');const action=form.getAttribute('data-renewal-action');
          const item=items.find(item=>item.request_id===id);
          if(!item || !collectorRenewalActions(item,session).includes(action)) throw new Error('Refresh the renewal before acting.');
          const options={method:'POST',financial:true};
          if(action === 'recommendation') {
            const recommendation=form.querySelector('[name="recommendation"]').value;
            const reason=form.querySelector('[name="reasonCode"]').value;
            const comment=form.querySelector('[name="comment"]').value.trim();
            if((recommendation === 'do_not_recommend' || reason.toLowerCase() === 'other') && comment.length<3) throw new Error('Explain this recommendation in the comment.');
            options.body={recommendation,reason_code:reason,comment};
          } else if(action === 'handover-photo') {
            const file=form.querySelector('[name="photo"]').files?.[0];
            if(!file || !['image/jpeg','image/png','image/webp'].includes(file.type) || !file.size || file.size>8*1024*1024) throw new Error('Choose a JPEG, PNG or WebP photo up to 8 MB.');
            options.rawBody=file;options.headers={'Content-Type':file.type,'X-File-Name':encodeURIComponent(file.name)};
          } else {
            if(!form.querySelector('[name="physicalConfirmation"]').checked) throw new Error('Confirm the physical cash handover first.');
            options.body={};
          }
          const result=await collectorMutation({api,guard,path:`/api/v1/collector/renewals/${encodeURIComponent(id)}/${action}`,options,verify:result=>action==='handover-photo' ? result.status==='under_review' : result.request?.request_id===id});
          if(current()) await onSaved(result);
        } catch(error) {if(current())status(error.message);}
        finally {guard.finish();}
      });
      guard.sync();
    } catch(error) {if(current()) root.textContent=error.message;}
  };
  if(hasPermission(session,'renewal.recommend.assigned')) load();else root.textContent='Assigned renewal permission is required.';
  function dispose(){disposed=true;signal?.removeEventListener('abort',dispose);}
  signal?.addEventListener('abort',dispose,{once:true});
  if(signal?.aborted) dispose();
  return dispose;
}
