import {escapeHtml as h,hasPermission,formatDateTime} from './ui.js';
const userId=session=>session?.user?.user_id || session?.user?.id || session?.user_id;
// Executable producers: SQL 0013/0015 and collection_void_repository.
// No current producer supplies a renewal request destination.
const receiptKinds=new Set(['cross_collection_posted','cross_collection_remitted','cross_collection_accepted','collector_payment_voided']);
export function collectorNotificationTarget(notice,{route,remittances=[],session}={}) {
  if(!notice || notice.recipient_user_id!==userId(session) || !receiptKinds.has(notice.notification_type))return null;
  if(hasPermission(session,'route.view') && typeof notice.transaction_id==='string'){const entry=route?.entries?.find(entry=>entry.today_receipts?.some(receipt=>receipt.transaction_id===notice.transaction_id));if(entry)return {sectionId:'collector-route',routeEntryId:entry.route_entry_id,recordId:notice.transaction_id};}
  if(hasPermission(session,'remittance.view') && notice.remittance_id && remittances.some(record=>record.remittance_id===notice.remittance_id))return {sectionId:'collector-remittance',recordId:notice.remittance_id};
  return null;
}
export function mountCollectorActivity({root,api,getSession,getTargets,navigate=()=>{},openTarget=()=>{},signal,beforeTaskChange=()=>{},afterTaskChange=()=>{}}) {
  let disposed=false,version=0,inflight=null,items=[],limit=30,readState='idle',message='';
  const pending=new Set(),rows=new Map(),owner=userId(getSession());
  function current(){if(disposed||signal?.aborted)return false;if(!getSession()||userId(getSession())!==owner){dispose();return false;}return true;}
  function feedback(){const target=root.querySelector('[data-update-status]');if(target)target.textContent=message;}
  function reveal(){
    for(const [index,item] of items.entries()){const row=rows.get(item.notification_id);if(row)row.hidden=index>=limit;}
    const count=root.querySelector('[data-updates-count]');if(count)count.textContent=`Showing ${Math.min(limit,items.length)} of ${items.length} loaded updates · ${items.filter(item=>!item.is_read).length} unread among loaded`;
    const more=root.querySelector('[data-more-updates]');if(more)more.hidden=limit>=items.length;
  }
  function deny(error){if(![401,403].includes(error?.status))return false;beforeTaskChange();dispose();root.innerHTML='<h2>Updates</h2><p>Updates access is unavailable. Reopen the workspace after your access is restored.</p>';afterTaskChange();return true;}
  function render(){
    if(!current())return;beforeTaskChange();rows.clear();
    root.innerHTML='<h2>Updates</h2><p>Activity intended for this signed-in account.</p>'+(['idle','loading'].includes(readState)?'<p>Loading updates…</p>':readState==='error'?'<p>Updates unavailable.</p><button class="button button-outline" type="button" data-retry-updates>Retry updates</button>':`<p data-updates-count role="status"></p><div class="timeline">${items.map(item=>{
      const target=collectorNotificationTarget(item,{...getTargets(),session:getSession()});
      return `<article class="timeline-item" data-notice-id="${h(item.notification_id)}"><strong>${h(item.title || 'Update')}</strong><span>${h(item.message || '')}</span><span>${formatDateTime(item.created_at)} · <span data-read-state tabindex="-1">${item.is_read?'Read':'Unread'}</span></span><div class="action-row">${!item.is_read?`<button class="button button-quiet" type="button" data-mark-read="${h(item.notification_id)}" ${pending.has(item.notification_id)?'disabled':''}>Mark as read</button>`:''}${target?`<button class="button button-outline" type="button" data-update-target="${h(item.notification_id)}">Open related record</button>`:'<span class="meta">Related detail is unavailable in the current loaded records.</span>'}</div></article>`;
    }).join('') || '<p>No Collector update is available.</p>'}</div><button class="button button-secondary" type="button" data-more-updates>Show more</button>`)+`<p data-update-status role="status">${h(message)}</p>`;
    for(const row of root.querySelectorAll('[data-notice-id]'))rows.set(row.getAttribute('data-notice-id'),row);
    root.querySelector('[data-retry-updates]')?.addEventListener('click',refresh);
    root.querySelector('[data-more-updates]')?.addEventListener('click',event=>{if(!current())return;beforeTaskChange();limit+=30;reveal();if(event.target.hidden)root.querySelector('[data-updates-count]')?.setAttribute('tabindex','-1');if(event.target.hidden)root.querySelector('[data-updates-count]')?.focus({preventScroll:true});afterTaskChange();});
    for(const button of root.querySelectorAll('[data-mark-read]'))button.addEventListener('click',()=>markRead(button.getAttribute('data-mark-read'),button));
    for(const button of root.querySelectorAll('[data-update-target]'))button.addEventListener('click',()=>{if(!current())return;const item=items.find(item=>item.notification_id===button.getAttribute('data-update-target'));const target=collectorNotificationTarget(item,{...getTargets(),session:getSession()});if(!target){message='This related record is no longer available. Refresh the permitted task.';feedback();return;}navigate(target.sectionId);openTarget(target);});
    reveal();afterTaskChange();
  }
  async function refresh(){
    if(!current())return;if(inflight)return inflight;if(pending.size){message='Read confirmation is in progress. Refresh after it finishes.';feedback();return false;}const generation=++version,recipient=userId(getSession());readState='loading';render();
    inflight=(async()=>{try{
      const data=await api.request('/api/v1/activity-notifications',{signal});if(!current()||generation!==version||recipient!==userId(getSession()))return;
      if(!Array.isArray(data)||data.some(item=>typeof item?.notification_id!=='string'||!item.notification_id||item.recipient_user_id!==recipient||typeof item.is_read!=='boolean')||new Set(data.map(item=>item.notification_id)).size!==data.length)throw new Error('Updates did not match this account.');
      items=data;readState='ready';message='';
    }catch(error){if(current()&&generation===version){if(deny(error))return;readState='error';message=error.message;}}
    if(current()&&generation===version)render();})().finally(()=>{inflight=null;});return inflight;
  }
  async function markRead(notificationId,button){
    if(!current()||pending.has(notificationId))return;
    const item=items.find(item=>item.notification_id===notificationId),recipient=userId(getSession()),generation=version,row=rows.get(notificationId),doc=button.ownerDocument;
    if(!item||item.is_read||item.recipient_user_id!==recipient||!row)return;
    let keepFocus=doc?.activeElement===button;const moved=event=>{if(event.target!==button)keepFocus=false;};
    for(const event of ['focusin','pointerdown','keydown'])doc?.addEventListener(event,moved);
    pending.add(notificationId);button.disabled=true;
    try{
      const result=await api.request(`/api/v1/activity-notifications/${encodeURIComponent(notificationId)}/read`,{method:'POST',signal});
      if(!current()||generation!==version||recipient!==userId(getSession()))return;
      if(result?.notification_id!==notificationId||result.recipient_user_id!==recipient||result.is_read!==true)throw new Error('Read status could not be confirmed. Retry this update.');
      items=items.map(notice=>notice.notification_id===notificationId?{...notice,is_read:true,read_at:result.read_at}:notice);
      const focusAllowed=keepFocus&&(!doc?.activeElement||doc.activeElement===doc.body||doc.activeElement===button);
      beforeTaskChange();const status=row.querySelector('[data-read-state]');status.textContent='Read';button.remove();message='Update marked as read.';reveal();feedback();afterTaskChange();
      if(focusAllowed&&row.isConnected!==false&&!row.closest?.('[hidden]'))status.focus({preventScroll:true});
    }catch(error){if(current()&&generation===version){if(deny(error))return;message=error.message;feedback();}}
    finally{for(const event of ['focusin','pointerdown','keydown'])doc?.removeEventListener(event,moved);pending.delete(notificationId);if(current()&&generation===version)button.disabled=false;}
  }
  function dispose(){disposed=true;version++;items=[];message='';pending.clear();rows.clear();root.innerHTML='';signal?.removeEventListener('abort',dispose);}
  signal?.addEventListener('abort',dispose,{once:true});if(signal?.aborted)dispose();return {refresh,dispose};
}
