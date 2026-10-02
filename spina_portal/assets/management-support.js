import {badge,errorCard,escapeHtml,formatDateTime,hasPermission} from './ui.js';

const statuses=['open','answered','resolved','cancelled'];
const validId=value=>typeof value==='string'&&/^[\da-f]{8}-[\da-f]{4}-[\da-f]{4}-[\da-f]{4}-[\da-f]{12}$/i.test(value);
const normalize=value=>String(value||'').trim().replace(/\s+/g,' ');
const fingerprint=row=>JSON.stringify([row.request_id,row.client_id,row.status,row.management_response,row.responded_at,row.resolved_at,row.cancelled_at]);
const matches=(command,row)=>row?.request_id===command.requestId&&row?.client_id===command.clientId&&row?.status===command.action&&normalize(row.management_response)===command.response&&!!row.responded_at&&(command.action!=='resolved'||!!row.resolved_at);

function recordMarkup(item) {
  const editable=['open','answered'].includes(item.status)&&validId(item.request_id)&&validId(item.client_id);
  return `<div class="section-heading"><div><h3>${escapeHtml(item.subject||'Support request')}</h3><p>${escapeHtml(item.client_name||'Client')} · ${escapeHtml(item.client_code||'')}</p></div>${badge(item.status)}</div><p>${escapeHtml(item.message||'')}</p><p class="meta">${escapeHtml(item.reference_text||'')} · Created ${formatDateTime(item.created_at)}</p>${item.management_response?`<p><strong>Saved response:</strong> ${escapeHtml(item.management_response)}</p>`:''}<p class="meta">${item.responded_at?`Answered ${formatDateTime(item.responded_at)}`:''}${item.resolved_at?` · Resolved ${formatDateTime(item.resolved_at)}`:''}${item.cancelled_at?` · Cancelled ${formatDateTime(item.cancelled_at)}`:''}</p><p role="status" data-support-result></p>${editable?`<form class="entry-form" data-support-form><label>Action<select name="action">${item.status==='open'?'<option value="answered">Answer</option>':''}<option value="resolved">Resolve</option></select></label><label>Response<textarea name="response" minlength="3" maxlength="2000" required></textarea></label><button type="submit" class="button button-primary">Save response</button></form>`:''}`;
}

export function mountManagementSupport({root,api,signal,getSession,onSaved}) {
  const owner=getSession()?.user?.id;
  let disposed=false,generation=0,status='open',offset=0,returned=0,busy=false,uncertain=null;
  const alive=()=>!disposed&&!signal?.aborted&&getSession()?.user?.id===owner&&hasPermission(getSession(),'support.manage');
  root.innerHTML=`<label>Support status<select data-support-status>${statuses.map(value=>`<option value="${value}">${value[0].toUpperCase()+value.slice(1)}</option>`).join('')}</select></label><div class="inline-actions"><button type="button" class="button button-outline" data-support-refresh>Refresh support</button><button type="button" class="button button-outline" data-support-reconcile hidden>Check uncertain saved response</button></div><p role="status" data-support-feedback></p><div class="list-stack" data-support-list></div><div class="inline-actions"><button type="button" class="button button-outline" data-support-previous disabled>Previous page</button><span class="meta" data-support-page></span><button type="button" class="button button-outline" data-support-next disabled>Next page</button></div>`;
  const select=root.querySelector('[data-support-status]'),list=root.querySelector('[data-support-list]'),feedback=root.querySelector('[data-support-feedback]'),refreshButton=root.querySelector('[data-support-refresh]'),reconcileButton=root.querySelector('[data-support-reconcile]'),previous=root.querySelector('[data-support-previous]'),next=root.querySelector('[data-support-next]'),page=root.querySelector('[data-support-page]');select.value=status;
  const dirty=()=>Array.from(list.querySelectorAll('[name="response"]')).some(input=>String(input.value||'').length>0);
  const path=(selected=status,start=offset)=>`/api/v1/management/support?status=${selected}&limit=100&offset=${start}`;
  function controls(){select.disabled=busy||!!uncertain;refreshButton.disabled=busy||!!uncertain;previous.disabled=busy||!!uncertain||offset===0;next.disabled=busy||!!uncertain||returned<100;reconcileButton.hidden=!uncertain;reconcileButton.disabled=busy;page.textContent=`Page ${offset/100+1} · ${returned} returned requests`;}
  function bindRow(node,item) {
    const form=node.querySelector('[data-support-form]');
    form?.addEventListener('submit',async event=>{
      event.preventDefault();if(!alive()||busy||uncertain)return;
      const action=form.querySelector('[name="action"]').value||(item.status==='open'?'answered':'resolved');
      const response=normalize(form.querySelector('[name="response"]').value);
      const resultNode=node.querySelector('[data-support-result]');
      if(response.length<3||response.length>2000||!['answered','resolved'].includes(action)||(item.status==='answered'&&action!=='resolved')){resultNode.textContent='Choose a valid action and enter a response of 3–2000 characters.';return;}
      const command={requestId:item.request_id,clientId:item.client_id,action,response};
      busy=true;controls();let attempted=false;
      try {
        const fresh=await api.request(path());if(!alive())return;
        const current=Array.isArray(fresh?.requests)?fresh.requests.find(row=>row.request_id===item.request_id):null;
        if(!current||fingerprint(current)!==fingerprint(item))throw new Error('This support request changed. Refresh and deliberately review the current record before saving.');
        if(!alive())return;attempted=true;
        const data=await api.request(`/api/v1/management/support/${encodeURIComponent(item.request_id)}/review`,{method:'POST',body:{action,response}});
        if(!alive())return;
        if(!matches(command,data?.request))throw new Error('The saved response could not be confirmed.');
        node.innerHTML=recordMarkup(data.request);bindRow(node,data.request);node.querySelector('[data-support-result]').textContent='Response saved.';
        try{if(await onSaved?.()===false)throw new Error('Overview refresh failed.');}catch{if(alive())node.querySelector('[data-support-result]').textContent='Response saved; overview refresh failed. Refresh Today for current counts.';}
      }catch(error){if(alive()){
        if(attempted&&(!error.status||error.status>=500)){uncertain={command,node};resultNode.textContent='The save outcome is uncertain. Do not submit again; check the saved response.';}
        else resultNode.textContent=error.message;
      }}finally{busy=false;if(alive())controls();}
    });
  }
  async function refresh({nextStatus=status,nextOffset=offset}={}) {
    if(!alive()||busy||uncertain){select.value=status;return false;}
    if(dirty()&&!globalThis.confirm?.('Discard the unsent Support responses on this page and load current records?')){select.value=status;return false;}
    if(!statuses.includes(nextStatus))return false;
    status=nextStatus;offset=nextOffset;select.value=status;
    const version=++generation;busy=true;controls();feedback.textContent='Loading Support…';
    try {
      const data=await api.request(path());if(!alive()||version!==generation)return false;
      if(!Array.isArray(data?.requests))throw new Error('Support records are unavailable. Retry this read.');
      if(data.requests.some(item=>!item||item.status!==status||!validId(item.request_id)||!validId(item.client_id)))throw new Error('Some Support records could not be verified. Refresh before reviewing.');
      returned=data.requests.length;
      list.innerHTML=returned?data.requests.map(item=>`<article class="data-card" data-support-record="${escapeHtml(item.request_id)}">${recordMarkup(item)}</article>`).join(''):`<p class="meta" role="status" data-management-queue-empty="support">No ${escapeHtml(status)} support requests were returned.</p>`;
      for(const node of list.querySelectorAll('[data-support-record]'))bindRow(node,data.requests.find(item=>item.request_id===node.getAttribute('data-support-record')));
      feedback.textContent='';return true;
    }catch(error){if(alive()&&version===generation){list.innerHTML=errorCard(error);feedback.textContent='Support could not be loaded. Use Refresh support to retry.';returned=0;}return false;}
    finally{busy=false;if(alive())controls();}
  }
  async function reconcile(){
    if(!alive()||busy||!uncertain)return;
    busy=true;controls();const pending=uncertain;
    try{
      const data=await api.request(path(pending.command.action,0));if(!alive())return;
      const found=data?.requests?.find(item=>item.request_id===pending.command.requestId);
      if(!matches(pending.command,found)){feedback.textContent='The saved response remains unconfirmed. Further submissions remain blocked.';return;}
      pending.node.innerHTML=recordMarkup(found);bindRow(pending.node,found);pending.node.querySelector('[data-support-result]').textContent='Saved response verified from current records.';uncertain=null;feedback.textContent='';
    }catch{if(alive())feedback.textContent='Could not check the saved response. Further submissions remain blocked.';}
    finally{busy=false;if(alive())controls();}
  }
  const listeners=[[select,'change',()=>void refresh({nextStatus:select.value,nextOffset:0})],[refreshButton,'click',()=>void refresh()],[previous,'click',()=>{if(offset&&!busy&&!uncertain)void refresh({nextOffset:offset-100});}],[next,'click',()=>{if(returned===100&&!busy&&!uncertain)void refresh({nextOffset:offset+100});}],[reconcileButton,'click',()=>void reconcile()]];
  for(const [element,event,handler]of listeners)element.addEventListener(event,handler);
  function dispose(){if(disposed)return;disposed=true;generation++;for(const [element,event,handler]of listeners)element.removeEventListener(event,handler);signal?.removeEventListener('abort',dispose);}
  signal?.addEventListener('abort',dispose,{once:true});
  return{refresh,dispose,isWritePending:()=>busy||!!uncertain};
}
