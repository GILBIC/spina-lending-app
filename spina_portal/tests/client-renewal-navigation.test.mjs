import test from 'node:test';
import assert from 'node:assert/strict';
import {setImmediate} from 'node:timers/promises';
import {Element,fire} from './helpers/dom.mjs';
import {mountClientWorkspace} from '../assets/roles/client.js';
const flush=async()=>{await setImmediate();await setImmediate();};
async function mount(t){
 const prior=Element.prototype.focus;Element.prototype.focus=function(){this.ownerDocument.activeElement=this;};t.after(()=>Element.prototype.focus=prior);
 const root=new Element(),controller=new AbortController(),calls=[];let handle;
 const query=root.querySelectorAll.bind(root);root.querySelectorAll=selector=>{const pair=selector.match(/^(\[[^\]]+\])(\[[^\]]+\])$/);return pair?query(pair[1]).filter(n=>n.getAttribute(pair[2].slice(1,-1))!==null):query(selector);};
 const context={root,signal:controller.signal,setNavigation(){},registerWorkspaceHandle:value=>handle=value,api:{async request(path,options={}){
  calls.push({path,options});assert.notEqual(options.method,'POST');
  if(path==='/api/v1/account')return {profile:{}};if(path==='/api/v1/activity-notifications')return [];if(path==='/api/v1/client/loans')return {loans:[]};
  if(path==='/api/v1/client/renewals')return {loans:[{loan_id:'synthetic-first',loan_number:'SAME',eligible:true},{loan_id:'synthetic-second',loan_number:'SAME',eligible:true}],requests:[{request_id:'synthetic-request',loan_id:'synthetic-second',status:'pending',client_message:'Saved original note'}]};
  if(path.startsWith('/api/v1/client/payment-proofs'))return {proofs:[],capability:{upload_available:true,max_bytes:10485760}};return {requests:[]};
 }}};
 await mountClientWorkspace(context);await handle.activate('client-payment-proofs');await handle.activate('client-renewals');await flush();t.after(()=>controller.abort());
 const form=root.querySelector('#client-renewal-form'),select=form.querySelector('[name="loanId"]'),amount=form.querySelector('[name="requestedAmount"]'),message=form.querySelector('[name="message"]'),support=root.querySelector('#client-support-form').querySelector('[name="message"]'),file=root.querySelector('[name="proofFile"]');
 select.value='synthetic-second';amount.value='5000.00';message.value='Retain renewal message';support.value='Retain Support';file.value='synthetic.png';
 return {root,controller,context,calls,form,select,amount,message,support,file,tab:view=>root.querySelector(`[data-client-renewal-view="${view}"]`)};
}

test('current/eligibility/history keyboard activation keeps logical tab focus and exact unrelated drafts without reads or writes',async t=>{
 const h=await mount(t),before=h.calls.length;
 for(const view of ['eligibility','history','current']){const tab=h.tab(view);tab.focus();fire(tab,'click');assert.ok(h.root.ownerDocument.activeElement===h.tab(view),'focus follows activated tab');assert.equal(h.tab(view).getAttribute('aria-pressed'),'true');}
 assert.equal(h.calls.length,before);assert.equal(h.root.querySelector('#client-renewal-form'),h.form);assert.equal(h.select.value,'synthetic-second');assert.equal(h.amount.value,'5000.00');assert.equal(h.message.value,'Retain renewal message');assert.equal(h.support.value,'Retain Support');assert.equal(h.file.value,'synthetic.png');
});

test('local renewal view changes cannot steal editor focus or revive stale view controls',async t=>{
 const h=await mount(t),old=h.tab('history');h.support.focus();fire(h.tab('eligibility'),'click');assert.ok(h.root.ownerDocument.activeElement===h.support);fire(old,'click');assert.equal(h.tab('eligibility').getAttribute('aria-pressed'),'true');
 const current=h.tab('current');h.controller.abort();h.root.innerHTML='<input name="replacement" />';const replacement=h.root.querySelector('input');replacement.value='New private draft';fire(current,'click');
 assert.equal(h.root.querySelector('input'),replacement);assert.equal(replacement.value,'New private draft');
});
