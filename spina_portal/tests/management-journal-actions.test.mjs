import test from 'node:test';
import assert from 'node:assert/strict';
import {setImmediate} from 'node:timers/promises';
import {Element,fire} from './helpers/dom.mjs';
const module=await import('../assets/management-journal-actions.js').catch(()=>({}));
const PATH='/api/v1/management/financial-accounting/journals';
const tick=async()=>{await setImmediate();await setImmediate();};
const set=(root,name,value)=>{const input=root.querySelector(`[name="${name}"]`);assert.ok(input,name);input.value=value;};
const click=async(root,selector)=>{const node=root.querySelector(selector);assert.ok(node,selector);fire(node,'click');await tick();};
const submit=async(root)=>{fire(root.querySelector('[data-journal-form]'),'submit');await tick();};
const lines=[{account_code:'1100',description:'Cash',debit:'1234567890123456.78',credit:'0.00'},{account_code:'3100',description:'Capital',debit:'0.00',credit:'1234567890123456.78'}];
const entry={entry_id:'entry-1',entry_number:'GJ-1',posting_date:'2026-09-29',description:'Owner capital',status:'draft',source_type:'manual',lines};
async function harness(t,request,permissions=['accounting.view','accounting.journal.manage']) {
 assert.equal(typeof module.mountManagementJournalActions,'function');
 const root=new Element(),calls=[],controller=new AbortController();
 const dispose=module.mountManagementJournalActions({root,session:{user:{role:'management'},permissions},signal:controller.signal,confirm:()=>true,api:{request:async(path,options={})=>{calls.push({path,options});return request(path,options);}}});
 t.after(dispose);await tick();return {root,calls,controller};
}
function fill(root){set(root,'posting_date','2026-09-29');set(root,'description','Owner capital');for(let i=0;i<2;i++)for(const key of ['account_code','description','debit','credit'])set(root,`${key}_${i}`,lines[i][key]);}
for(const removed of [1,2])test(`removing journal line ${removed+1} focuses a surviving field and preserves the draft`,async t=>{
 const h=await harness(t,()=>({entries:[],can_manage:true}));
 await click(h.root,'[data-journal-create]');fill(h.root);
 await click(h.root,'[data-journal-add-line]');
 for(const [key,value] of Object.entries({account_code:'5100',description:'Third line',debit:'0.00',credit:'12.34'}))set(h.root,`${key}_2`,value);
 const remove=h.root.querySelector(`[data-journal-remove-line="${removed}"]`);remove.focus();
 await click(h.root,`[data-journal-remove-line="${removed}"]`);
 assert.equal(h.root.querySelector('[name="account_code_1"]').focused,true);
 assert.equal(h.root.querySelector(`[data-journal-remove-line="${removed}"]`),null);
 assert.equal(h.root.querySelector('[name="posting_date"]').value,'2026-09-29');
 assert.equal(h.root.querySelector('[name="description"]').value,'Owner capital');
 assert.equal(h.root.querySelector('[name="debit_0"]').value,'1234567890123456.78');
 assert.equal(h.root.querySelector('[name="account_code_1"]').value,removed===1?'5100':'3100');
 assert.equal(h.root.querySelector('[name="credit_1"]').value,removed===1?'12.34':'1234567890123456.78');
 assert.equal(h.calls.filter(call=>call.options.method).length,0);
});
test('manual journal creation preserves exact amounts and saves an unposted draft',async t=>{
 const h=await harness(t,(_path,options)=>options.method?{entry}:{entries:[],can_manage:true});
 await click(h.root,'[data-journal-create]');fill(h.root);await submit(h.root);
 const post=h.calls.find(call=>call.options.method==='POST');assert.equal(post.path,PATH);assert.equal(post.options.financial,true);assert.deepEqual(post.options.body,{posting_date:'2026-09-29',description:'Owner capital',lines});
 assert.equal(h.calls.some(call=>call.path.endsWith('/post')),false);assert.match(h.root.textContent,/draft saved|draft created/i);
});
test('manual draft edit, cancel and post send the reviewed entry identity',async t=>{
 const h=await harness(t,(path,options)=>options.method==='DELETE'?{cancelled:true}:options.method?{entry:{...entry,status:path.endsWith('/post')?'posted':'draft'}}:{entries:[entry],can_manage:true});
 await click(h.root,'[data-journal-edit]');fill(h.root);set(h.root,'description','Reviewed capital');await submit(h.root);
 const edit=h.calls.find(call=>call.options.method==='PUT');assert.equal(edit.path,`${PATH}/entry-1`);assert.equal(edit.options.body.description,'Reviewed capital');assert.equal(edit.options.body.lines[0].debit,'1234567890123456.78');
 await click(h.root,'[data-journal-post]');await click(h.root,'[data-journal-cancel]');
 assert.deepEqual(h.calls.find(call=>call.path.endsWith('/post')).options.body,{confirm:true});assert.deepEqual(h.calls.find(call=>call.options.method==='DELETE').options.body,{confirm:true});
});
test('posted entry reversal creates a separately reviewed draft without editing or reposting original',async t=>{
 const posted={...entry,status:'posted'};
 const h=await harness(t,(_path,options)=>options.method?{entry:{...entry,entry_id:'reversal-1',source_type:'reversal',reversal_of_entry_id:entry.entry_id}}:{entries:[posted],can_manage:true});
 assert.equal(h.root.querySelector('[data-journal-edit]'),null);assert.equal(h.root.querySelector('[data-journal-post]'),null);
 await click(h.root,'[data-journal-reverse]');set(h.root,'posting_date','2026-09-30');set(h.root,'description','Correct entry with reversal');await submit(h.root);
 const mutation=h.calls.find(call=>call.options.method);assert.equal(mutation.path,`${PATH}/entry-1/reverse`);assert.deepEqual(mutation.options.body,{posting_date:'2026-09-30',description:'Correct entry with reversal'});assert.match(h.root.textContent,/post it separately/i);
});
test('permissions and protected source types suppress unsupported write controls',async t=>{
 const h=await harness(t,()=>({entries:[{...entry,source_type:'opening_balance'}],can_manage:true}));assert.equal(h.root.querySelector('[data-journal-post]'),null);assert.equal(h.root.querySelector('[data-journal-edit]'),null);
 const denied=await harness(t,()=>({entries:[entry],can_manage:false}));assert.equal(denied.root.querySelector('[data-journal-create]'),null);
 const viewer=await harness(t,()=>({entries:[entry],can_manage:true}),['accounting.view']);assert.equal(viewer.root.querySelector('[data-journal-create]'),null);
});
test('unbalanced drafts fail locally and an uncertain save cannot be retried without refresh',async t=>{
 const h=await harness(t,(_path,options)=>{if(options.method)throw Object.assign(new Error('Timeout'),{status:503});return {entries:[],can_manage:true};});
 await click(h.root,'[data-journal-create]');fill(h.root);set(h.root,'credit_1','1.00');await submit(h.root);assert.equal(h.calls.filter(call=>call.options.method).length,0);assert.match(h.root.textContent,/balance/i);
 set(h.root,'credit_1',lines[1].credit);await submit(h.root);await submit(h.root);assert.equal(h.calls.filter(call=>call.options.method).length,1);assert.match(h.root.textContent,/refresh/i);
 h.controller.abort();assert.equal(h.root.innerHTML,'');
});
for(const code of [401,403,426])test(`journal denial ${code} erases private evidence and leaves a terminal explanation`,async t=>{
 const h=await harness(t,(_path,options)=>{if(options.method)throw Object.assign(new Error('Private backend detail'),{status:code});return {entries:[entry],can_manage:true};});
 const post=h.root.querySelector('[data-journal-post]');fire(post,'click');await tick();assert.doesNotMatch(h.root.textContent,/Owner capital|Private backend detail/);assert.match(h.root.textContent,/sign in|update/i);assert.equal(h.root.querySelector('[data-journal-post]'),null);fire(post,'click');await tick();assert.equal(h.calls.filter(call=>call.options.method).length,1);
});
test('linked reversal draft can post separately while protected generated drafts remain unavailable',async t=>{
 const reversal={...entry,entry_id:'reversal-1',source_type:'reversal',reversal_of_entry_id:'original-1'};
 const h=await harness(t,(_path,options)=>options.method?{entry:{...reversal,status:'posted'}}:{entries:[reversal],can_manage:true});
 assert.equal(h.root.querySelector('[data-journal-edit]'),null);assert.equal(h.root.querySelector('[data-journal-cancel]'),null);await click(h.root,'[data-journal-post]');assert.equal(h.calls.find(call=>call.options.method).path,`${PATH}/reversal-1/post`);
});
test('period close, reversals and already reversed originals cannot create another reversal',async t=>{
 const h=await harness(t,()=>({entries:[{...entry,status:'posted'},{...entry,entry_id:'reversal-1',source_type:'reversal',status:'posted',reversal_of_entry_id:entry.entry_id},{...entry,entry_id:'period-close',source_type:'period_close',status:'posted'}],can_manage:true}));
 assert.equal(h.root.querySelector('[data-journal-reverse]'),null);
});
