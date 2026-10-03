import test from 'node:test';
import assert from 'node:assert/strict';
import {Element,fire} from './helpers/dom.mjs';
const module=await import('../assets/loan-payouts.js').catch(()=>({}));
const id='10000000-0000-4000-8000-000000000001';
test('loan payout page defaults to Collector and refresh preserves receipt File and draft nodes',async t=>{
 assert.equal(typeof module.mountLoanPayouts,'function');
 const root=new Element(),account={id,version:1,kind:'gcash',actions:['loan_payout_prepare']};
 const client={isCurrent:()=>true,state:()=>({status:'idle'}),workspace:async()=>({accounts:[account]}),loanPayoutWorkspace:async()=>({enabled:true,mode:'staff',items:[],has_more:false}),loanPayoutSources:async()=>({items:[]})};
 const handle=module.mountLoanPayouts({root,client,account:()=>account,mode:'staff'});t.after(handle);await handle.ready;
 assert.equal(root.querySelector('[data-payout-destination]').value,'collector');
 const file=root.querySelector('[data-payout-file]'),note=root.querySelector('[data-payout-note]');
 const bytes=new Blob(['receipt'],{type:'image/png'});file.files=[bytes];note.value='Actual receipt review';
 await handle.refreshReadOnly();assert.equal(root.querySelector('[data-payout-file]'),file);assert.equal(file.files[0],bytes);assert.equal(note.value,'Actual receipt review');
});
test('staff workspace exposes a lazy Loan payouts task',async t=>{
 const {mountTreasuryWorkspace}=await import('../assets/treasury-workspace.js');
 const root=new Element(),actor={user_id:id,device_id:id};
 const workspace={contract_version:1,actor,enabled:true,owner_configured:true,capabilities:{},claims:[],blockers:[],accounts:[{id,ledger_context_id:id,version:1,alias:'Test wallet',kind:'gcash',context:'synthetic',actions:['loan_payout_prepare'],balance:null}]};
 const calls=[],api={request:async path=>{calls.push(path);if(path.endsWith('/workspace'))return workspace;if(path.includes('/loan-payout-sources'))return {contract_version:1,actor,account_id:id,account_version:1,items:[]};return {contract_version:1,actor,mode:'staff',account_id:id,enabled:true,items:[],limit:50,offset:0,has_more:false};}};
 const handle=mountTreasuryWorkspace({root,api,getSession:()=>({user:{id,role:'management'},device_id:id,permissions:[]})});t.after(handle);await handle.ready;
 assert.ok(root.querySelector('[data-task="payouts"]'));
 assert.equal(calls.some(path=>path.includes('/loan-payouts')),false);
 await handle.activate('payouts');assert.ok(root.querySelector('[data-payout-destination]'));
});

const tick=()=>new Promise(resolve=>setImmediate(resolve));
test('recipient screen submits its own exact stage without any wallet grant',async t=>{
 const root=new Element(),submitted=[];
 const row={id,account_id:id,ledger_context_id:id,version:3,source_kind:'renewal',destination:'borrower',amount:'1000.00',status:'recipient_confirmed',stages:['borrower'],funding_method:'gcash',acknowledgments:{}};
 const client={isCurrent:()=>true,state:()=>({status:'idle'}),workspace:async()=>({accounts:[]}),loanPayoutWorkspace:async()=>({enabled:true,mode:'own',items:[row],has_more:false}),execute:async body=>{submitted.push(body);return {result:{payout:row}};},dispose(){}};
 const handle=module.mountLoanPayouts({root,client});t.after(handle);await handle.ready;
 root.querySelector('[data-payout-confirmed]').checked=true;root.querySelector('[data-payout-note]').value='I received the full proceeds';root.querySelector('[data-payout-time]').value='2026-10-03T12:00';
 fire(root.querySelector('[data-payout-save]'),'click');await tick();await tick();
 assert.equal(submitted.length,1);assert.equal(submitted[0].action,'loan_payout_acknowledge');assert.equal(submitted[0].stage,'borrower');assert.equal(submitted[0].reviewed_amount,'1000.00');assert.equal(Object.hasOwn(submitted[0],'account_id'),false);assert.equal(Object.hasOwn(submitted[0],'expected_version'),false);
});
test('staff disabled history renders without asking for new payout sources',async t=>{
 const root=new Element(),account={id,version:1,kind:'gcash',actions:[]};let catalogue=0;
 const row={id,version:2,source_kind:'first_loan',destination:'collector',status:'debited',amount:'1000.00',account_id:id,stages:[]};
 const client={isCurrent:()=>true,state:()=>({status:'idle'}),workspace:async()=>({accounts:[account]}),loanPayoutWorkspace:async()=>({enabled:false,items:[row],has_more:false}),loanPayoutSources:async()=>{catalogue++;throw Error('Entry disabled');}};
 const handle=module.mountLoanPayouts({root,client,account:()=>account,mode:'staff'});t.after(handle);await handle.ready;
 assert.equal(catalogue,0);assert.match(root.querySelector('[data-payout-detail]').textContent,/1000.00/);assert.equal(root.querySelector('[data-payout-save]').disabled,true);
});


test('prepared payout becomes a movement source without discarding other drafts',async t=>{
 const {mountTreasuryWorkspace}=await import('../assets/treasury-workspace.js');
 const root=new Element(),actor={user_id:id,device_id:id},payoutId='20000000-0000-4000-8000-000000000001';
 const account={id,ledger_context_id:id,version:1,alias:'Funding wallet',kind:'gcash',context:'synthetic',actions:['loan_payout_prepare','disbursement_record'],balance:null};
 const source={source_kind:'first_loan',source_id:id,amount:'1000.00',label:'Approved loan',authorization_id:id,packet_hash:'b'.repeat(64),contract_evidence_reference:'office-evidence:'+id};
 let prepared=null;
 const api={request:async(path,options={})=>{
  if(path.endsWith('/workspace'))return {contract_version:1,actor,enabled:true,owner_configured:true,capabilities:{disbursement_record:true},claims:[],blockers:[],accounts:[{...account}],source_choices:prepared?[{purpose:'loan_release',id:payoutId,version:1,label:'Prepared approved loan',account_id:id,payee_id:id,amount:'1000.00',provider:'gcash'}]:[]};
  if(path.includes('/loan-payout-sources'))return {contract_version:1,actor,account_id:id,account_version:account.version,items:prepared?[]:[source]};
  if(path.endsWith('/loan-payout-preview'))return {...options.body,contract_version:1,actor,ledger_context_id:id,account_version:account.version,amount:'1000.00',payee_id:id,payee_name:'Assigned Collector',client_id:id,source_digest:'a'.repeat(64)};
  if(path.endsWith('/actions')){const b=options.body;prepared={...b,id:payoutId,version:1,status:'prepared',amount:'1000.00',ledger_context_id:id,stages:[]};account.version=2;return {contract_version:1,action:b.action,request_id:b.request_id,target_id:payoutId,version:1,status:'saved',result:{actor_user_id:id,device_id:id,account_id:id,ledger_context_id:id,payout:prepared}};}
  if(path.includes('/loan-payouts?'))return {contract_version:1,actor,mode:'staff',account_id:id,enabled:true,items:prepared?[prepared]:[],limit:50,offset:0,has_more:false};
  return {items:[],total_count:0,limit:50,offset:0,has_more:false,totals:null};
 }};
 const handle=mountTreasuryWorkspace({root,api,getSession:()=>({user:{id,role:'management',status:'active'},device_id:id,permissions:[]})});t.after(handle);await handle.ready;
 const file=root.querySelector('[data-treasury-evidence-file]'),bytes=new Blob(['reviewed proof'],{type:'image/png'});file.files=[bytes];
 await handle.activate('payouts');root.querySelector('[data-payout-source]').value=id;root.querySelector('[data-payout-recipient]').value='Reviewed Collector wallet';
 fire(root.querySelector('[data-payout-preview]'),'click');for(let i=0;i<5;i++)await tick();
 fire(root.querySelector('[data-payout-prepare]'),'click');for(let i=0;i<5;i++)await tick();
 assert.ok(prepared,'actual prepare command saved');
 fire(root.querySelector('[data-payout-movement]'),'click');for(let i=0;i<5;i++)await tick();
 const movement=root.querySelector('[data-treasury-action="disbursement_record"]');
 assert.match(movement.querySelector('[name="source_id"]').innerHTML,new RegExp(payoutId));
 assert.equal(root.querySelector('[data-treasury-evidence-file]'),file);assert.equal(file.files[0],bytes);
});
