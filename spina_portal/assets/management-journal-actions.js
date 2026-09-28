import {asArray,escapeHtml as h,hasPermission,formatMoney} from './ui.js';
import {createCollectorWriteGuard} from './collector-write-guard.js';
import {collectorMutation} from './collector-workflow-contract.js';

const PATH='/api/v1/management/financial-accounting/journals';
const value=(root,name)=>String(root.querySelector(`[name="${name}"]`)?.value||'').trim();
const button=(label,attribute)=>`<button type="button" class="button button-outline" ${attribute}>${label}</button>`;
const input=(name,label,type='text',initial='',extra='')=>`<label>${label}<input name="${name}" type="${type}" value="${h(initial)}" ${extra}></label>`;
function money(text){
  if(!/^(0|[1-9]\d{0,15})(\.\d{1,2})?$/.test(text))throw new Error('Use non-negative amounts with at most two decimal places.');
  const [whole,fraction='']=text.split('.');return `${whole}.${fraction.padEnd(2,'0')}`;
}
const cents=text=>BigInt(text.replace('.',''));

export function mountManagementJournalActions(options){
  const {root,api,session,signal,confirm=message=>globalThis.confirm?.(message),onSaved}=options;
  if(!root||!hasPermission(session,'accounting.view'))return ()=>{};
  let disposed=false,busy=false,guard,replacementCleanup;
  const controller=new AbortController();
  const current=()=>!disposed&&!signal?.aborted;
  const status=message=>{const node=root.querySelector('[data-journal-status]');if(current()&&node)node.textContent=message;};
  const lock=()=>{if(current())for(const tag of ['button','input'])for(const node of root.querySelectorAll(tag))node.disabled=busy||(guard.locked&&node.getAttribute('data-journal-refresh')===null);};
  root.innerHTML=`<h3>Journal actions</h3><p>Review manual drafts before posting. Posted records remain immutable; corrections create a separate reversal draft.</p>${button('Refresh journals','data-journal-refresh')}<p data-journal-status role="status" aria-live="polite"></p><div data-journal-records></div><div data-journal-editor></div>`;
  guard=createCollectorWriteGuard({signal:controller.signal,onLock:message=>{status(message);if(guard)lock();}});
  const run=async operation=>{
    if(!current()||!guard.begin())return;busy=true;lock();
    try{await operation();}catch(error){if(current()){status(error.message);if([401,403,426].includes(error.status)){dispose();root.textContent=error.status===426?'Update SPINA before continuing.':'Access is unavailable. Sign in again before continuing.';}else if(error.status===409)guard.lock('The journal changed. Refresh the journals and review the current evidence before another action.');}}
    finally{busy=false;guard.finish();lock();}
  };
  const save=(path,method,body,verify)=>collectorMutation({api,path,options:{method,body},guard,verify});
  async function saved(message){if(!current())return;root.querySelector('[data-journal-editor]').innerHTML='';await load();if(current()){status(message);await onSaved?.();}}
  root.querySelector('[data-journal-refresh]').addEventListener('click',()=>{if(busy||disposed)return;dispose();replacementCleanup=mountManagementJournalActions(options);});
  function editor(entry=null,reversal=false){
    if(guard.locked||busy||!current())return;
    const target=root.querySelector('[data-journal-editor]');
    let lines=entry&&!reversal?asArray(entry.lines).map(line=>({...line})):[{},{}];
    target.innerHTML=`<form class="entry-form" data-journal-form><h4>${reversal?'Create reversal draft':entry?'Edit manual draft':'Create manual draft'}</h4>${entry?`<p>Selected journal: ${h(entry.entry_number||entry.entry_id)} · ${h(entry.description)}</p>`:''}${input('posting_date','Posting date','date',reversal?'':entry?.posting_date||'','required')}${input('description',reversal?'Reversal reason':'Description','text',reversal?'':entry?.description||'','minlength="3" maxlength="240" required')}${reversal?'<p>The server will reverse the original lines. Review and post the resulting draft separately.</p>':'<div data-journal-lines></div>'+button('Add line','data-journal-add-line')}<button type="submit" class="button button-primary">${reversal?'Create reversal draft':'Save unposted draft'}</button></form>`;
    const form=target.querySelector('[data-journal-form]');
    const capture=()=>lines.map((_,index)=>Object.fromEntries(['account_code','description','debit','credit'].map(key=>[key,value(form,`${key}_${index}`)])));
    const renderLines=()=>{
      form.querySelector('[data-journal-lines]').innerHTML=lines.map((line,index)=>`<fieldset><legend>Line ${index+1}</legend>${input(`account_code_${index}`,'Account code','text',line.account_code||'','maxlength="20" required')}${input(`description_${index}`,'Line description','text',line.description||'','maxlength="240"')}${input(`debit_${index}`,'Debit','text',line.debit||'0.00','inputmode="decimal" required')}${input(`credit_${index}`,'Credit','text',line.credit||'0.00','inputmode="decimal" required')}${lines.length>2?button('Remove line',`data-journal-remove-line="${index}"`):''}</fieldset>`).join('');
      for(const item of form.querySelectorAll('[data-journal-remove-line]'))item.addEventListener('click',()=>{if(busy||guard.locked)return;lines=capture();lines.splice(Number(item.getAttribute('data-journal-remove-line')),1);renderLines();});
    };
    if(!reversal){renderLines();form.querySelector('[data-journal-add-line]').addEventListener('click',()=>{if(busy||guard.locked)return;if(lines.length>=30){status('A draft supports at most 30 lines.');return;}lines=capture();lines.push({});renderLines();});}
    form.addEventListener('submit',event=>{event.preventDefault();run(async()=>{
      const body={posting_date:value(form,'posting_date'),description:value(form,'description')};
      if(!/^\d{4}-\d{2}-\d{2}$/.test(body.posting_date)||body.description.length<3)throw new Error('Choose a posting date and enter a clear description.');
      if(!reversal){
        body.lines=capture().map(line=>({...line,debit:money(line.debit),credit:money(line.credit)}));
        let debit=0n,credit=0n;
        for(const line of body.lines){if(!line.account_code||!((cents(line.debit)>0n&&cents(line.credit)===0n)||(cents(line.credit)>0n&&cents(line.debit)===0n)))throw new Error('Each line needs an account and one positive debit or credit.');debit+=cents(line.debit);credit+=cents(line.credit);}
        if(!debit||debit!==credit)throw new Error('The draft must balance before it can be saved.');
      }
      const summary=reversal?`Create an unposted reversal of ${entry.entry_number||entry.entry_id} on ${body.posting_date}?\n${body.description}`:`Save this unposted manual draft on ${body.posting_date}?\n${body.description}\n${body.lines.map(line=>`${line.account_code}: debit ${line.debit}, credit ${line.credit}`).join('\n')}`;
      if(!confirm(summary))return;
      const path=entry?`${PATH}/${encodeURIComponent(entry.entry_id)}${reversal?'/reverse':''}`:PATH;
      await save(path,entry&&!reversal?'PUT':'POST',body,result=>Boolean(result.entry?.entry_id)&&result.entry.status==='draft'&&(!entry||(reversal?result.entry.source_type==='reversal'&&result.entry.reversal_of_entry_id===entry.entry_id:result.entry.entry_id===entry.entry_id)));
      await saved(reversal?'Reversal draft created. Review and post it separately.':'Manual draft saved. Review it before posting.');
    });});
  }
  async function load(){
    const result=await api.request(PATH,{signal:controller.signal});if(!current())return;
    const canManage=hasPermission(session,'accounting.journal.manage')&&result.can_manage===true;
    const target=root.querySelector('[data-journal-records]');
    const reversedIds=new Set(asArray(result.entries).map(entry=>entry.reversal_of_entry_id).filter(Boolean));
    target.innerHTML=`${canManage?button('Create manual draft','data-journal-create'):'<p>Journal changes are unavailable for this account.</p>'}${asArray(result.entries).map((entry,index)=>`<article class="list-item"><h4>${h(entry.entry_number||entry.entry_id)} · ${h(entry.status)}</h4><p>${h(entry.posting_date)} · ${h(entry.description)} · ${h(entry.source_type)} · Debit ${formatMoney(entry.total_debit)} / Credit ${formatMoney(entry.total_credit)}</p><ul>${asArray(entry.lines).map(line=>`<li>${h(line.account_code)} · ${h(line.description)} · Debit ${formatMoney(line.debit)} / Credit ${formatMoney(line.credit)}</li>`).join('')}</ul>${canManage&&entry.status==='draft'&&entry.source_type==='manual'?button('Edit',`data-journal-edit="${index}"`)+button('Cancel draft',`data-journal-cancel="${index}"`):''}${canManage&&entry.status==='draft'&&(entry.source_type==='manual'||(entry.source_type==='reversal'&&entry.reversal_of_entry_id))?button('Post',`data-journal-post="${index}"`):''}${canManage&&entry.status==='posted'&&!entry.reversal_of_entry_id&&!['period_close','reversal'].includes(entry.source_type)&&!reversedIds.has(entry.entry_id)?button('Create reversal',`data-journal-reverse="${index}"`):''}</article>`).join('')}`;
    target.querySelector('[data-journal-create]')?.addEventListener('click',()=>editor());
    for(const action of ['edit','reverse','post','cancel'])for(const item of target.querySelectorAll(`[data-journal-${action}]`))item.addEventListener('click',()=>{
      const entry=result.entries[Number(item.getAttribute(`data-journal-${action}`))];
      if(action==='edit'||action==='reverse'){editor(entry,action==='reverse');return;}
      run(async()=>{
        if(!confirm(`${action==='post'?'Post permanently':'Cancel'} journal ${entry.entry_number||entry.entry_id}?\n${entry.description}\nDebit ${entry.total_debit} / Credit ${entry.total_credit}\n${action==='post'?'Posted entries are immutable. Corrections require a separate reversal.':'The audit record will be retained.'}`))return;
        const path=`${PATH}/${encodeURIComponent(entry.entry_id)}${action==='post'?'/post':''}`;
        await save(path,action==='post'?'POST':'DELETE',{confirm:true},response=>action==='post'?response.entry?.entry_id===entry.entry_id&&response.entry.status==='posted':response.cancelled===true);
        await saved(action==='post'?'Journal posting confirmed.':'Draft cancellation confirmed.');
      });
    });
  }
  function dispose(){if(replacementCleanup){replacementCleanup();replacementCleanup=null;}if(disposed)return;disposed=true;controller.abort();guard.dispose();root.innerHTML='';signal?.removeEventListener('abort',dispose);}
  signal?.addEventListener('abort',dispose,{once:true});if(signal?.aborted)dispose();else run(load);
  return dispose;
}
