import { sessionHasRole, sessionWorkspaceRoles } from './roles.js';
import { escapeHtml as esc, hasPermission, setButtonBusy, clearButtonBusyFocus, sessionPermissions } from './ui.js';

const BASE = '/api/v1/employee-operations';
const mounts = new WeakMap();
// Stable API lifetime spans token rotation. Payloads remain memory-only and are
// discarded explicitly at authentication, identity, device, or authority changes.
const recoveryByApi = new WeakMap();
const localDevice = api => api.sessionStore?.deviceId?.() ?? null;
export function clearCashDisbursementRecovery(api) {
  const previous = recoveryByApi.get(api);
  if (previous) previous.pending = null;
  recoveryByApi.delete(api);
}
export function syncCashDisbursementRecovery(api, session) {
  const scope = JSON.stringify([session?.user?.id, sessionWorkspaceRoles(session).sort(), sessionPermissions(session).sort(), localDevice(api)]);
  let state = recoveryByApi.get(api);
  if (!state || state.scope !== scope) {
    clearCashDisbursementRecovery(api);
    state = {scope, pending:null, device:null, localDevice:localDevice(api)};
    recoveryByApi.set(api,state);
  }
  return state;
}
const expenses = [['5200','Rent'],['5210','Utilities'],['5220','Transportation'],['5230','Professional fees'],['5240','Bank charges'],['5290','Other operating expense']];
const cashAccounts = [['1010','Office Cash'],['1030','Bank / GCash (manual ledger account)']];
const fields = ['as_of','payee','purpose','amount','expense_account_code','cash_account_code','evidence_reference','evidence'];
const uuid = /^[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}$/i;
const matches = (result, command) => result?.request_id === command.request_id && result?.id === command.id && result?.version === 1 && result?.status === 'accepted';
const input = (name,label,type='text') => `<label>${label}<input name="${name}" type="${type}" required maxlength="2000"></label>`;
const select = (name,label,options) => `<label>${label}<select name="${name}" required><option value="">Choose</option>${options.map(([code,text])=>`<option value="${code}">${esc(text)} (${code})</option>`).join('')}</select></label>`;

export function mountCashDisbursement({root, api, session, signal}) {
  if (!root) return () => {};
  mounts.get(root)?.();
  const recovery=syncCashDisbursementRecovery(api,session);
  let disposed=false, busy=false, workspace=null, pending=recovery.pending, stale=false;
  const controller=new AbortController();
  const current=()=>{
    if (localDevice(api)!==recovery.localDevice && recoveryByApi.get(api)===recovery) clearCashDisbursementRecovery(api);
    return !disposed && !signal?.aborted && recoveryByApi.get(api)===recovery;
  };
  const permitted=()=>hasPermission(session,'cash_disbursement.prepare') && (sessionHasRole(session,'employee') || sessionHasRole(session,'management'));
  const online=()=>globalThis.navigator?.onLine!==false;
  function dispose(){if(disposed)return;disposed=true;controller.abort();signal?.removeEventListener('abort',dispose);globalThis.removeEventListener?.('offline',offline);root.querySelectorAll('button').forEach(clearButtonBusyFocus);root.innerHTML='';}
  mounts.set(root,dispose);signal?.addEventListener('abort',dispose,{once:true});
  function message(text,error=false){const node=root.querySelector('[data-cash-feedback]');if(node){node.textContent=text;node.setAttribute('role',error?'alert':'status');}}
  function remember(command){pending=command;if(recoveryByApi.get(api)===recovery)recovery.pending=command;}
  function lock(){for(const node of root.querySelectorAll('input'))node.disabled=busy||Boolean(pending)||stale||!online();for(const node of root.querySelectorAll('select'))node.disabled=busy||Boolean(pending)||stale||!online();const submit=root.querySelector('[data-cash-submit]');if(submit)submit.disabled=busy||Boolean(pending)||stale||!online();for(const name of ['refresh','retry']){const node=root.querySelector(`[data-cash-${name}]`);if(node)node.disabled=busy||!online();}}
  function offline(){if(current()){stale=true;lock();message('Offline. Reconnect and refresh before preparing a draft.',true);}}
  globalThis.addEventListener?.('offline',offline);
  function render(){
    root.innerHTML=`<section class="card"><h3>Cash Disbursement</h3><p>Prepare an expense draft with its supporting receipt. Management reviews and posts the linked draft in General Journal. This does not send money.</p><p data-cash-feedback role="status" tabindex="-1"></p><button type="button" class="button button-outline" data-cash-refresh>Refresh / check saved result</button>${pending?'<button type="button" class="button button-outline" data-cash-retry>Retry the same unchanged request</button>':`<form class="entry-form" data-cash-disbursement-form>${input('as_of','Accounting date','date')}${input('payee','Payee')}${input('purpose','Purpose')}${input('amount','Amount (PHP)')}${select('expense_account_code','Expense',expenses)}${select('cash_account_code','Paid from',cashAccounts)}${input('evidence_reference','Receipt / reference')}${input('evidence','Supporting evidence')}<button class="button button-primary" type="submit" data-cash-submit>Prepare draft</button></form>`}</section>`;
    root.querySelector('[data-cash-refresh]')?.addEventListener('click',()=>load());
    root.querySelector('[data-cash-retry]')?.addEventListener('click',()=>{if(pending)save(pending);});
    root.querySelector('[data-cash-disbursement-form]')?.addEventListener('submit',event=>{event.preventDefault();if(!current()||busy||pending||stale||!online())return;try{save(command());}catch(error){message(error.message,true);}});
    lock();
  }
  function command(){
    const form=root.querySelector('[data-cash-disbursement-form]');
    const value=Object.fromEntries(fields.map(name=>[name,form.querySelector(`[name="${name}"]`).value.trim()]));
    if(fields.some(name=>!value[name]||value[name].length>2000))throw new Error('Complete every field before preparing the draft.');
    if(!/^(0|[1-9]\d{0,11})(?:\.\d{1,2})?$/.test(value.amount)||!/[1-9]/.test(value.amount))throw new Error('Enter a positive amount with at most two decimal places.');
    if(!expenses.some(([code])=>code===value.expense_account_code)||!cashAccounts.some(([code])=>code===value.cash_account_code))throw new Error('Choose an approved expense and cash account.');
    if(!/^\d{4}-\d{2}-\d{2}$/.test(value.as_of)||new Date(`${value.as_of}T00:00:00Z`).toISOString().slice(0,10)!==value.as_of)throw new Error('Enter a valid accounting date.');
    const [whole,cents='']=value.amount.split('.');value.amount=`${whole}.${cents.padEnd(2,'0')}`;
    return {...value,action:'cash_disbursement_prepare',request_id:crypto.randomUUID(),id:crypto.randomUUID(),expected_version:0};
  }
  async function load(){
    if(!current()||busy||!online())return;busy=true;lock();
    try{
      const result=await api.request(`${BASE}/workspace${pending?`?request_id=${encodeURIComponent(pending.request_id)}`:''}`,{signal:controller.signal});
      if(!current())return;
      if(result?.contract_version!==1||result?.actor?.user_id!==session?.user?.id||!uuid.test(result?.actor?.device_id||'')||result?.capabilities?.can_prepare_cash_disbursement!==true)throw Object.assign(new Error('Cash Disbursement preparation is not assigned or could not be verified.'),{status:403});
      if(recovery.device && recovery.device!==result.actor.device_id){remember(null);root.innerHTML='';}
      recovery.device=result.actor.device_id;
      workspace=result;stale=false;
      const recovered=pending&&matches(result.last_result,pending);
      if(recovered)remember(null);
      if(!root.querySelector('[data-cash-disbursement-form]')||recovered)render();
      message(recovered?'Draft confirmed. Management can review it in General Journal.':pending?'The outcome is not confirmed. Check again or retry only the same unchanged request.':'Ready to prepare a draft.');
    }catch(error){if(!current())return;stale=true;if([401,403].includes(error.status)){remember(null);root.innerHTML='<p role="alert">Cash Disbursement access is not available. Sign in again or ask Management.</p>';}else message('Could not verify the workspace. Refresh before preparing a draft.',true);}
    finally{busy=false;if(current())lock();}
  }
  async function save(value){
    if(!current()||busy||!permitted()||!online()||!workspace)return;
    remember(value);busy=true;const button=root.querySelector('[data-cash-submit]')||root.querySelector('[data-cash-retry]');if(button)setButtonBusy(button,true,'Preparing…');lock();message('Preparing draft…');
    try{
      const result=await api.request(`${BASE}/actions`,{method:'POST',body:value,financial:true,signal:controller.signal});
      if(!current())return;
      if(!matches(result,value))throw new Error('Unconfirmed response');
      remember(null);render();message('Draft prepared. Management reviews and posts it in General Journal.');
    }catch(error){if(!current())return;
      if([401,403].includes(error.status)){remember(null);root.innerHTML='<p role="alert">Cash Disbursement access is no longer available.</p>';workspace=null;}
      else if(error.status && error.status<500 && error.code!=='network_uncertain'){remember(null);stale=error.status!==422;message(stale?'The request was rejected. Refresh and review before trying again.':'Check the entered values. The draft was not saved; your entries are preserved.',true);}
      else{render();message('The outcome is uncertain. Check the saved result or retry only the same unchanged request.',true);}
    }finally{busy=false;if(current()){if(button)setButtonBusy(button,false);lock();}else if(button)clearButtonBusyFocus(button);}
  }
  if(!current()){dispose();return dispose;}
  if(!permitted()){root.innerHTML='<p>Cash Disbursement preparation is not assigned to this account.</p>';return dispose;}
  render();load();return dispose;
}
