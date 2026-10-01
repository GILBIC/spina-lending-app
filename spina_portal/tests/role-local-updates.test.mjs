import assert from 'node:assert/strict';
import test from 'node:test';
import {setImmediate} from 'node:timers/promises';
import {Element,fire} from './helpers/dom.mjs';
import {mountClientWorkspace} from '../assets/roles/client.js';
import {mountEmployeeWorkspace} from '../assets/roles/employee.js';

function decorate(node,parent=null,doc=Object.assign(new EventTarget(),{body:{}})){node.parentElement=parent;node.isConnected=true;node.ownerDocument=doc;node.dataset=Object.fromEntries(Object.entries(node.attributes).filter(([k])=>k.startsWith('data-')).map(([k,v])=>[k.slice(5).replace(/-([a-z])/g,(_,c)=>c.toUpperCase()),v]));node.focus=()=>{doc.activeElement=node;};for(const child of node.children)if(typeof child!=='string')decorate(child,node,doc);return doc;}
async function setup(t,role){
 const root=new Element();root.dataset={};const query=root.querySelectorAll.bind(root);root.querySelectorAll=selector=>{const pair=selector.match(/^(\[[^\]]+\])(\[[^\]]+\])$/);return pair?query(pair[1]).filter(node=>node.getAttribute(pair[2].slice(1,-1))!==null):query(selector);};const controller=new AbortController();t.after(()=>controller.abort());const calls=[];let finish;
 const rows=[1,2].map(i=>({request_id:`support-${i}`,client_name:`Synthetic Client ${i}`,message:'Synthetic question',status:'open'}));
 const api={async request(path,options={}){calls.push({path,options});if(options.method)return new Promise(resolve=>{finish=resolve;});
  if(path==='/api/v1/activity-notifications')return [{notification_id:'note-1',title:'Synthetic update',is_read:false}];
  if(path==='/api/v1/management/support?status=open')return {requests:rows};
  return {};
 }};
 const context={root,api,signal:controller.signal,setNavigation(){},session:{user:{role},permissions:['support.manage']}};
 await (role==='client'?mountClientWorkspace:mountEmployeeWorkspace)(context);await setImmediate();
 const doc=decorate(root);return {root,doc,calls,controller,finish:async result=>{finish(result);await setImmediate();await setImmediate();}};
}

test('marking one Client update read preserves unrelated support and renewal drafts and focus',async t=>{
 const h=await setup(t,'client');const support=h.root.querySelector('#client-support-form');const renewal=h.root.querySelector('#client-renewal-form');
 support.querySelector('[name="message"]').value='Unsent support draft';renewal.querySelector('[name="message"]').value='Unsent renewal draft';
 const button=h.root.querySelector('[data-client-notification-read]');fire(button,'click');support.querySelector('[name="message"]').focus();const focused=h.doc.activeElement;
 await h.finish({notification_id:'note-1',is_read:true});
 assert.equal(h.root.querySelector('#client-support-form'),support);assert.equal(h.root.querySelector('#client-renewal-form'),renewal);
 assert.equal(support.querySelector('[name="message"]').value,'Unsent support draft');assert.equal(renewal.querySelector('[name="message"]').value,'Unsent renewal draft');assert.equal(h.doc.activeElement,focused);
 assert.equal(button.hidden,true);assert.match(button.parentElement.textContent,/Read/);
 assert.equal(h.calls.filter(c=>c.path==='/api/v1/account').length,1);
});

for(const changed of [false,true])test(`successful Employee reply updates only its record; later same-form draft ${changed?'preserved':'cleared'}`,async t=>{
 const previous=globalThis.FormData;globalThis.FormData=class{constructor(form){this.form=form;}get(name){return this.form.querySelector(`[name="${name}"]`)?.value;}};t.after(()=>{globalThis.FormData=previous;});
 const h=await setup(t,'employee');const [first,second]=h.root.querySelectorAll('.employee-support-review');
 first.querySelector('[name="action"]').value='answered';first.querySelector('[name="response"]').value='Submitted response';second.querySelector('[name="response"]').value='Other unsent reply';
 fire(first,'submit');second.querySelector('[name="response"]').focus();const focused=h.doc.activeElement;
 if(changed)first.querySelector('[name="response"]').value='A later unsent reply';
 await h.finish({request:{request_id:'support-1',status:'answered',management_response:'Submitted response'}});
 assert.equal(h.root.querySelectorAll('.employee-support-review')[1],second);assert.equal(second.querySelector('[name="response"]').value,'Other unsent reply');assert.equal(h.doc.activeElement,focused);
 assert.equal(first.querySelector('[name="response"]').value,changed?'A later unsent reply':'');assert.equal(first.hidden,true);for(const count of h.root.querySelectorAll('[data-support-count]'))assert.equal(count.textContent,'1');assert.match(first.parentElement.textContent,/Submitted response/);assert.match(first.parentElement.textContent,/Answered/);
 assert.equal(h.calls.filter(c=>c.path==='/api/v1/account').length,1);assert.equal(first.querySelector('button[type="submit"]').disabled,false);
});

test('resolved Employee reply updates open-work counts without removing another draft',async t=>{
 const previous=globalThis.FormData;globalThis.FormData=class{constructor(form){this.form=form;}get(name){return this.form.querySelector(`[name="${name}"]`)?.value;}};t.after(()=>{globalThis.FormData=previous;});
 const h=await setup(t,'employee');const [first,second]=h.root.querySelectorAll('.employee-support-review');
 first.querySelector('[name="action"]').value='resolved';first.querySelector('[name="response"]').value='Resolved synthetic request';second.querySelector('[name="response"]').value='Other draft';
 fire(first,'submit');await h.finish({request:{request_id:'support-1',status:'resolved',management_response:'Resolved synthetic request'}});
 assert.equal(first.hidden,true);assert.equal(second.querySelector('[name="response"]').value,'Other draft');
 for(const count of h.root.querySelectorAll('[data-support-count]'))assert.equal(count.textContent,'1');
});

for(const state of ['aborted','detached','wrong-record'])test(`Client notification ${state} response cannot update the current card`,async t=>{
 const h=await setup(t,'client');const button=h.root.querySelector('[data-client-notification-read]');fire(button,'click');
 if(state==='aborted')h.controller.abort();if(state==='detached')button.isConnected=false;
 await h.finish({notification_id:state==='wrong-record'?'other-note':'note-1',is_read:true});
 assert.notEqual(button.hidden,true);assert.match(button.parentElement.textContent,/Unread/);assert.equal(h.calls.filter(c=>c.path==='/api/v1/account').length,1);
});
