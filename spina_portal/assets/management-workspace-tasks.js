import {escapeHtml, errorCard, showToast} from './ui.js';

// A mounted Management task owns its existing editor and cleanup. Switching tasks
// hides it; it never serializes fields or recreates a financial workflow.
export function createManagementTaskController({root, signal, getSession, tasks, beforeTaskChange=()=>{}, afterTaskChange=()=>{}}) {
  let disposed=false, current=null, activation=0;
  const owner=getSession()?.user?.id;
  const states=new Map(tasks.map(task=>[task.id,{task,handle:null,promise:null,loaded:false}]));
  const selections=new Map();
  const removers=[];
  const alive=()=>!disposed && !signal?.aborted && getSession()?.user?.id===owner;
  const allowed=task=>alive() && (!task.allowed || task.allowed(getSession()));
  const panel=task=>root.querySelector(`#${task.id}`);
  for(const group of new Set(tasks.map(task=>task.group))) {
    const nav=root.querySelector(`#${group}`)?.querySelector('[data-management-task-navigation]');
    if(!nav)continue;
    nav.innerHTML=tasks.filter(task=>task.group===group && allowed(task)).map(task=>`<button class="button button-outline" type="button" data-management-task="${escapeHtml(task.id)}" aria-pressed="false">${escapeHtml(task.label)}</button>`).join('');
    for(const button of nav.querySelectorAll('[data-management-task]')) {
      const onClick=()=>{void activate(group,button.getAttribute('data-management-task'));};
      button.addEventListener('click',onClick);removers.push(()=>button.removeEventListener('click',onClick));
    }
  }
  async function load(state) {
    if(state.loaded)return state.handle;
    if(state.promise)return state.promise;
    state.promise=(async()=>{
      const handle=await state.task.mount?.();
      if(!allowed(state.task)) { typeof handle==='function'?handle():handle?.dispose?.(); return null; }
      state.handle=typeof handle==='function'?{dispose:handle}:handle||{};
      state.loaded=true;
      return state.handle;
    })();
    try{return await state.promise;}
    catch(error){
      if(allowed(state.task)) {
        const target=panel(state.task);
        if(target) {
          target.innerHTML=`${errorCard(error)}<button type="button" class="button button-outline" data-task-retry>Retry ${escapeHtml(state.task.label)}</button>`;
          target.querySelector('[data-task-retry]')?.addEventListener('click',()=>void activate(state.task.group,state.task.id),{once:true});
        }
      }
      return null;
    }finally{state.promise=null;}
  }
  async function activate(group,id=selections.get(group)) {
    if(!alive())return false;
    const available=tasks.filter(task=>task.group===group && allowed(task));
    const task=available.find(item=>item.id===id) || (!id ? available[0] : null);
    if(!task)return false;
    const version=++activation;
    if(current!==task.id)beforeTaskChange();
    for(const item of tasks.filter(item=>item.group===group)) {
      const target=panel(item);if(target)target.hidden=item.id!==task.id;
    }
    for(const button of root.querySelector(`#${group}`)?.querySelectorAll('[data-management-task]')||[])button.setAttribute('aria-pressed',String(button.getAttribute('data-management-task')===task.id));
    current=task.id;selections.set(group,current);
    await load(states.get(current));
    if(alive() && activation===version)afterTaskChange();
    return alive();
  }
  const isWritePending=(excludeId)=>[...states.values()].some(state=>state.task.id!==excludeId&&state.handle?.isWritePending?.());
  async function refreshVisible() {
    if(!alive())return false;
    if(isWritePending()) {showToast('Finish or reconcile the current action before refreshing.','error');return false;}
    const state=states.get(current);
    if(!state || !allowed(state.task))return false;
    const handle=await load(state);
    if(!alive())return false;
    if(handle?.refresh||state.task.refresh){
      beforeTaskChange();
      try{return await (handle?.refresh?handle.refresh():state.task.refresh(handle));}
      finally{if(alive())afterTaskChange();}
    }
    showToast('Your work is retained. Use the task’s refresh or search controls.');
    return false;
  }
  function dispose() {
    if(disposed)return;disposed=true;activation++;
    for(const remove of removers)remove();
    for(const state of states.values())state.handle?.dispose?.();
    signal?.removeEventListener('abort',dispose);
  }
  signal?.addEventListener('abort',dispose,{once:true});
  return {activate,refreshVisible,isWritePending,writeOwner:()=>states.get(current)?.handle??null,dispose};
}
