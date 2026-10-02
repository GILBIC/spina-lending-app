import {badge,emptyState,errorCard,escapeHtml,formatDateTime} from './ui.js';

const validId=value=>typeof value==='string'&&/^[\da-f]{8}-[\da-f]{4}-[\da-f]{4}-[\da-f]{4}-[\da-f]{12}$/i.test(value);

export function mountManagementPersonalUpdates({root,api,signal,getSession,onRead}) {
  const owner=getSession()?.user?.id;
  let disposed=false,generation=0,cap=30,records=[];
  const busy=new Set();
  const focusCleanups=new Set();
  const alive=()=>!disposed&&!signal?.aborted&&getSession()?.user?.id===owner;
  root.innerHTML='<p>Personal updates for this account. Marking an update read does not alter permanent audit history.</p><button type="button" class="button button-outline" data-updates-refresh>Refresh updates</button><p role="status" data-updates-feedback></p><p class="meta" data-updates-count></p><div class="list-stack" data-updates-list></div><button type="button" class="button button-outline" data-updates-more hidden>Show 30 more updates</button>';
  const list=root.querySelector('[data-updates-list]'),feedback=root.querySelector('[data-updates-feedback]'),count=root.querySelector('[data-updates-count]'),more=root.querySelector('[data-updates-more]'),refreshButton=root.querySelector('[data-updates-refresh]');
  function reveal() {
    for(const [index,row] of Array.from(list.querySelectorAll('[data-my-update]')).entries()){
      if(index<cap)row.removeAttribute('hidden');else row.setAttribute('hidden','');
    }
    count.textContent=`${Math.min(cap,records.length)} visible · ${records.length} loaded · ${records.filter(item=>!item.is_read).length} unread among loaded. Up to 100 recent records; this is not a lifetime total.`;
    more.hidden=cap>=records.length;
  }
  function render() {
    list.innerHTML=records.length?records.map(item=>`<article class="data-card" data-my-update="${escapeHtml(item.notification_id)}"><div class="section-heading"><h3>${escapeHtml(item.title||'Activity update')}</h3><span data-update-status>${badge(item.is_read?'Read':'Unread')}</span></div><p>${escapeHtml(item.message||'')}</p><p class="meta">${formatDateTime(item.created_at)}</p>${item.is_read?'':`<button type="button" class="button button-outline" data-update-read="${escapeHtml(item.notification_id)}">Mark as read</button>`}</article>`).join(''):emptyState('No personal updates were returned for this account.');
    for(const row of list.querySelectorAll('[data-my-update]')) {
      const button=row.querySelector('[data-update-read]');
      button?.addEventListener('click',async()=>{
        const id=button.getAttribute('data-update-read'),item=records.find(record=>record.notification_id===id);
        if(!alive()||busy.has(id)||!item||item.is_read)return;
        const document=root.ownerDocument;
        let restoreFocus=document?.activeElement===button;
        const moved=event=>{if(event.type!=='focusin'||event.target!==button)restoreFocus=false;};
        const stopFocus=()=>{for(const type of ['focusin','pointerdown','keydown'])document?.removeEventListener(type,moved,true);focusCleanups.delete(stopFocus);};
        if(restoreFocus){for(const type of ['focusin','pointerdown','keydown'])document.addEventListener(type,moved,true);focusCleanups.add(stopFocus);}
        const version=generation;busy.add(id);button.disabled=true;feedback.textContent='';
        try {
          const result=await api.request(`/api/v1/activity-notifications/${encodeURIComponent(id)}/read`,{method:'POST'});
          if(!alive()||generation!==version)return;
          if(result?.notification_id!==id||result?.recipient_user_id!==owner||result.is_read!==true||!result.read_at)throw new Error('This update could not be confirmed as read. Refresh Updates or try again.');
          item.is_read=true;item.read_at=result.read_at;
          const status=row.querySelector('[data-update-status]');status.innerHTML=badge('Read');status.setAttribute('tabindex','-1');button.hidden=true;reveal();
          if(restoreFocus&&(document.activeElement===button||document.activeElement===document.body))status.focus();
          feedback.textContent='Update marked read.';
          try{if(await onRead?.()===false)throw new Error('Overview refresh failed.');}catch{if(alive())feedback.textContent='Update marked read; overview refresh failed. Refresh Today for current totals.';}
        }catch(error){if(alive()&&generation===version)feedback.textContent=error.message;}
        finally{stopFocus();busy.delete(id);if(alive())button.disabled=false;}
      });
    }
    reveal();
  }
  async function refresh() {
    if(!alive()||busy.size)return false;
    const version=++generation;feedback.textContent='Loading your updates…';
    try {
      const data=await api.request('/api/v1/activity-notifications?limit=100');
      if(!alive()||version!==generation)return false;
      if(!Array.isArray(data))throw new Error('Personal updates are unavailable. Retry this read.');
      const seen=new Set();records=data.filter(item=>{if(!item||item.recipient_user_id!==owner||!validId(item.notification_id)||typeof item.is_read!=='boolean'||seen.has(item.notification_id))return false;seen.add(item.notification_id);return true;});
      cap=30;feedback.textContent=records.length!==data.length?'Some returned updates could not be verified for this account and were not displayed.':'';render();return true;
    }catch(error){if(alive()&&version===generation){list.innerHTML=errorCard(error);feedback.textContent='Could not refresh personal updates. Use Refresh updates to retry.';count.textContent='';more.hidden=true;}return false;}
  }
  const read=()=>void refresh(),showMore=()=>{if(alive()){cap+=30;reveal();}};
  refreshButton.addEventListener('click',read);more.addEventListener('click',showMore);
  function dispose(){if(disposed)return;disposed=true;generation++;for(const stop of focusCleanups)stop();refreshButton.removeEventListener('click',read);more.removeEventListener('click',showMore);signal?.removeEventListener('abort',dispose);}
  signal?.addEventListener('abort',dispose,{once:true});
  return{refresh,dispose,isWritePending:()=>busy.size>0};
}
