import test from 'node:test';
import assert from 'node:assert/strict';
import {setImmediate} from 'node:timers/promises';
import {Element,fire} from './helpers/dom.mjs';
import {mountClientWorkspace} from '../assets/roles/client.js';
const flush=async()=>{await setImmediate();await setImmediate();};
const uid=index=>`10000000-0000-4000-8000-${String(index).padStart(12,'0')}`;
const owner=uid(900),transaction=uid(901),otherTransaction=uid(902);
const note=index=>({notification_id:uid(index+1),notification_type:'client_payment_posted',recipient_user_id:owner,sender_user_id:uid(903),sender_name:'Test Collector',title:'Payment recorded',message:'Same-looking synthetic update',transaction_id:index===64?otherTransaction:transaction,remittance_id:null,client_id:uid(904),metadata:{receipt_number:'SYNTHETIC',amount:'12.34',covered_dates:['2026-10-01','2026-10-03'],recorder_user_id:uid(903),recorder_name:'Test Collector',collection_origin:'assigned_route',remaining_balance:'2205.00'},is_read:false,created_at:'2026-10-01T09:00:00+08:00',read_at:null});
const deferred=()=>{let resolve,reject;const promise=new Promise((done,fail)=>{resolve=done;reject=fail;});return {promise,resolve,reject};};
async function mount(t,count=65){
 const prior={document:globalThis.document,setTimeout:globalThis.setTimeout,focus:Element.prototype.focus,click:Element.prototype.click};
 const toasts=[];globalThis.document={getElementById:()=>({append:value=>toasts.push(value.textContent)}),createElement:()=>({remove(){}})};globalThis.setTimeout=()=>({unref(){}});
 Element.prototype.focus=function(){this.ownerDocument.activeElement=this;};Element.prototype.click=function(){fire(this,'click');};
 t.after(()=>{Object.assign(globalThis,{document:prior.document,setTimeout:prior.setTimeout});Element.prototype.focus=prior.focus;if(prior.click)Element.prototype.click=prior.click;else delete Element.prototype.click;});
 const root=new Element(),controller=new AbortController(),calls=[],writes=[],navigated=[];
 const query=root.querySelectorAll.bind(root);root.querySelectorAll=selector=>{const pair=selector.match(/^(\[[^\]]+\])(\[[^\]]+\])$/);return pair?query(pair[1]).filter(n=>n.getAttribute(pair[2].slice(1,-1))!==null):query(selector);};
 const session={user:{id:owner,role:'client'},device_id:uid(905),access_token:'original'};
 let notes=Array.from({length:count},(_,i)=>note(i)),handle;
 const context={root,signal:controller.signal,getSession:()=>session,setNavigation(){},navigateTo:id=>navigated.push(id),registerWorkspaceHandle:value=>handle=value,api:{async request(path,options={}){
  calls.push({path,options});if(options.method){const pending=deferred();writes.push({path,options,...pending});return pending.promise;}
  if(path==='/api/v1/activity-notifications')return structuredClone(await notes);
  if(path==='/api/v1/client/payments')return {payments:[{transaction_id:transaction,receipt_number:'SYNTHETIC',amount:'12.34'},{transaction_id:otherTransaction,receipt_number:'SYNTHETIC',amount:'12.34'}]};
  if(path==='/api/v1/account')return {profile:{full_name:'Synthetic'}};
  if(path==='/api/v1/client/loans')return {loans:[]};
  if(path.startsWith('/api/v1/client/payment-proofs'))return {proofs:[],capability:{upload_available:true,max_bytes:10485760}};
  return {requests:[]};
 }}};
 await mountClientWorkspace(context);await handle.activate('client-payment-proofs');await handle.activate('client-updates');await flush();t.after(()=>controller.abort());
 const support=root.querySelector('#client-support-form').querySelector('[name="message"]'),renewal=root.querySelector('#client-renewal-form').querySelector('[name="requestedAmount"]'),file=root.querySelector('[name="proofFile"]');
 support.value='Keep Support';renewal.value='5000.00';file.value='synthetic.png';
 const doc=root.ownerDocument;doc.activeElement=null;
 return {root,context,handle,controller,calls,writes,navigated,toasts,session,support,renewal,file,doc,
  region:()=>root.querySelector('[data-client-region="notifications"]'),
  button:id=>root.querySelector(`[data-client-notification-read="${id}"]`),more:()=>root.querySelector('[data-client-updates-more]'),
  setNotes:value=>notes=value,complete:(index=0,value={...note(0),is_read:true,read_at:'2026-10-03T01:00:00Z'})=>writes[index].resolve(value),
 };
}

for(const count of [0,30,65,100,200])test(`Updates actual Show more reaches all ${count} exact IDs in server order without reading or writing`,async t=>{
 const h=await mount(t,count),before=h.calls.length;let visible=Math.min(count,30);
 while(true){
  assert.deepEqual(h.region().querySelectorAll('[data-client-notification-read]').map(button=>button.dataset.clientNotificationRead),Array.from({length:visible},(_,i)=>uid(i+1)));
  if(!h.more())break;fire(h.more(),'click');visible=Math.min(count,visible+30);
 }
 assert.equal(visible,count);assert.equal(h.calls.length,before);assert.equal(h.writes.length,0);
 assert.equal(h.support.value,'Keep Support');assert.equal(h.renewal.value,'5000.00');assert.equal(h.file.value,'synthetic.png');
 if(count)assert.match(h.region().textContent,new RegExp(`${count} loaded updates`));else assert.match(h.region().textContent,/no new SPINA updates/i);
});

test('keyboard Show more retains logical focus through 30 to60 to65, ending on honest count',async t=>{
 const h=await mount(t);h.more().focus();fire(h.more(),'click');assert.ok(h.doc.activeElement===h.more(),'focus follows replacement Show more');
 h.more().focus();fire(h.more(),'click');const count=h.root.querySelector('[data-client-updates-count]');assert.ok(count);assert.ok(h.doc.activeElement===count);assert.equal(count.getAttribute('tabindex'),'-1');assert.match(count.textContent,/65 loaded updates · 65 unread/);
});

test('programmatic Show more never steals unrelated editor focus or drafts',async t=>{
 const h=await mount(t);h.support.focus();fire(h.more(),'click');assert.ok(h.doc.activeElement===h.support);assert.equal(h.support.value,'Keep Support');assert.equal(h.file.value,'synthetic.png');
});

test('verified Mark as read recomputes loaded unread count locally and focuses only its own status',async t=>{
 const h=await mount(t),button=h.button(uid(1)),before=h.calls.length;button.focus();fire(button,'click');await flush();h.complete();await flush();
 assert.equal(h.context.clientRaw.notifications[0].is_read,true);assert.match(h.region().textContent,/65 loaded updates · 64 unread among loaded updates/);
 assert.equal(button.hidden,true);assert.ok(h.doc.activeElement===button.parentElement.querySelector('[data-client-notification-status]'));
 assert.equal(h.calls.length,before+1);assert.equal(h.region().querySelectorAll('.timeline-item').length,30);assert.equal(h.file.value,'synthetic.png');
});

for(const redraw of ['show-more','payment-read redraw'])test(`pending Mark as read survives ${redraw}, rejects duplicate replacement clicks and reconciles only its exact loaded ID`,async t=>{
 const h=await mount(t),old=h.button(uid(1));fire(old,'click');await flush();
 if(redraw==='show-more'){h.more().focus();fire(h.more(),'click');}else await h.context.clientLoad('payments',{refresh:true});old.isConnected=false;
 const current=h.button(uid(1));assert.notEqual(current,old);current.disabled=false;fire(current,'click');await flush();assert.equal(h.writes.length,1,'the same pending ID must not submit twice after redraw');
 h.support.focus();h.complete();await flush();assert.equal(h.context.clientRaw.notifications[0].is_read,true);assert.equal(current.hidden,true);
 assert.match(current.parentElement.querySelector('[data-client-notification-status]').textContent,/Read/);assert.match(h.region().textContent,/65 loaded updates · 64 unread/);
 assert.ok(h.doc.activeElement===h.support);assert.equal(h.support.value,'Keep Support');assert.equal(h.renewal.value,'5000.00');assert.equal(h.file.value,'synthetic.png');
});

for(const result of ['wrong-ID','wrong-recipient','unread','failed'])test(`${result} Mark as read result leaves counts and current rows unchanged after Show more`,async t=>{
 const h=await mount(t);fire(h.button(uid(1)),'click');await flush();fire(h.more(),'click');
 if(result==='failed')h.writes[0].reject(Object.assign(Error('Synthetic temporary failure'),{status:503}));else h.complete(0,{...note(0),is_read:result!=='unread',notification_id:result==='wrong-ID'?uid(999):uid(1),recipient_user_id:result==='wrong-recipient'?uid(998):owner});
 await flush();assert.equal(h.context.clientRaw.notifications[0].is_read,false);assert.match(h.region().textContent,/65 loaded updates · 65 unread/);assert.equal(h.button(uid(1)).hidden,false);assert.equal(h.button(uid(1)).disabled,false);assert.equal(h.file.value,'synthetic.png');
});

test('a verified late result cannot resurrect an ID absent from the current loaded array',async t=>{
 const h=await mount(t),old=h.button(uid(1));fire(old,'click');await flush();h.context.clientRaw.notifications=[note(1)];await h.context.clientLoad('payments',{refresh:true});old.isConnected=false;h.complete();await flush();
 assert.deepEqual(h.context.clientRaw.notifications.map(item=>item.notification_id),[uid(2)]);assert.match(h.region().textContent,/1 loaded updates · 1 unread/);assert.equal(h.button(uid(1)),null);assert.equal(h.toasts.length,0);
});

test('owned payment beyond first group navigates exact transaction with no implicit write; stale membership blocks it',async t=>{
 const h=await mount(t);fire(h.more(),'click');fire(h.more(),'click');
 const link=h.root.querySelector(`[data-client-notification-payment="${otherTransaction}"]`);assert.ok(link);fire(link,'click');await flush();
 assert.deepEqual(h.navigated,['client-payments']);assert.equal(h.root.querySelector(`[data-payment-record-copy="${otherTransaction}"]`).getAttribute('data-payment-record-copy'),otherTransaction);assert.equal(h.writes.length,0);
 h.context.clientRaw.payments.payments=[];fire(link,'click');await flush();assert.deepEqual(h.navigated,['client-payments']);assert.equal(h.writes.length,0);
});

test('unsupported/hostile/deleted targets stay text and a mismatched recipient read makes Updates unavailable',async t=>{
 const h=await mount(t);h.setNotes([{...note(0),notification_type:'unknown',message:`javascript:alert(1) ${otherTransaction}`,metadata:{url:'https://untrusted.invalid',proof_id:otherTransaction}},{...note(1),transaction_id:uid(999)}]);
 await h.context.clientLoad('notifications',{refresh:true});assert.equal(h.region().querySelector('[data-client-notification-payment]'),null);assert.equal(h.writes.length,0);
 h.setNotes([{...note(0),recipient_user_id:uid(999)}]);await h.context.clientLoad('notifications',{refresh:true});assert.match(h.region().textContent,/do not match this account/);assert.equal(h.region().querySelector('[data-client-notification-read]'),null);assert.equal(h.writes.length,0);
});


test('verified pending result after Show more updates its replacement row and counts without stealing paging focus',async t=>{
 const h=await mount(t),old=h.button(uid(1));fire(old,'click');await flush();h.more().focus();fire(h.more(),'click');old.isConnected=false;
 const paging=h.more();paging.focus();h.complete();await flush();
 assert.equal(h.context.clientRaw.notifications[0].is_read,true);assert.equal(h.button(uid(1)).hidden,true);assert.match(h.region().textContent,/65 loaded updates · 64 unread/);assert.ok(h.doc.activeElement===paging);
});


for(const status of [401,403])test(`pending Mark as read ${status} after Show more still clears private current mount and detached controls stay inert`,async t=>{
 const h=await mount(t),old=h.button(uid(1));fire(old,'click');await flush();fire(h.more(),'click');old.isConnected=false;
 const replacement=h.button(uid(1));h.writes[0].reject(Object.assign(Error('Synthetic denied update'),{status}));await flush();
 assert.equal(h.root.innerHTML,'');assert.equal(h.support.value,'');assert.equal(h.renewal.value,'');assert.equal(h.file.value,'');
 for(const button of [old,replacement]){button.disabled=false;fire(button,'click');}await flush();assert.equal(h.writes.length,1);
});

test('a detached old Mark as read control cannot write after redraw and verified count is not decremented twice',async t=>{
 const h=await mount(t),old=h.button(uid(1));fire(h.more(),'click');old.isConnected=false;fire(old,'click');await flush();assert.equal(h.writes.length,0);
 const current=h.button(uid(1));fire(current,'click');await flush();h.complete();await flush();current.disabled=false;current.hidden=false;fire(current,'click');await flush();
 assert.equal(h.writes.length,1);assert.match(h.region().textContent,/65 loaded updates · 64 unread/);
});

for(const loss of ['owner','abort'])test(`a pending verified update cannot alter a replacement mount after ${loss}`,async t=>{
 const h=await mount(t);fire(h.button(uid(1)),'click');await flush();
 if(loss==='owner'){h.session.user.id=uid(999);h.context.clientIsCurrent();}else h.controller.abort();
 h.root.innerHTML='<input name="replacement" />';const replacement=h.root.querySelector('input');replacement.value='Replacement draft';h.complete();await flush();
 assert.equal(h.root.querySelector('input'),replacement);assert.equal(replacement.value,'Replacement draft');assert.equal(h.toasts.length,0);
});


for(const outcome of ['saved','failed'])test(`pending Mark as read blocks overlapping notification reads and allows explicit refresh after ${outcome}`,async t=>{
 const h=await mount(t),button=h.button(uid(1)),before=h.calls.filter(call=>call.path==='/api/v1/activity-notifications').length;
 fire(button,'click');await flush();const snapshot=deferred();h.setNotes(snapshot.promise);
 const read=h.context.clientLoad('notifications',{refresh:true});await flush();
 assert.equal(h.calls.filter(call=>call.path==='/api/v1/activity-notifications').length,before,'an overlapping old notification GET must not start');
 assert.equal(h.button(uid(1)),button);assert.equal(h.context.clientReads.state('notifications').status,'ready');await read;
 assert.equal(await h.handle.refreshVisible(),false);assert.match(h.toasts.at(-1),/update.*marked.*read.*Refresh after/i);
 // Paging and an independent payment read still work and retain the pending exact ID.
 fire(h.more(),'click');await h.context.clientLoad('payments',{refresh:true});assert.equal(h.button(uid(1)).disabled,true);
 if(outcome==='saved')h.complete();else h.writes[0].reject(Object.assign(Error('Synthetic temporary failure'),{status:503}));await flush();
 assert.equal(h.context.clientRaw.notifications[0].is_read,outcome==='saved');assert.match(h.region().textContent,outcome==='saved'?/65 loaded updates · 64 unread/:/65 loaded updates · 65 unread/);
 const currentNotes=Array.from({length:65},(_,i)=>({...note(i),is_read:outcome==='saved'&&i===0}));h.setNotes(currentNotes);snapshot.resolve(Array.from({length:65},(_,i)=>note(i)));
 await h.context.clientLoad('notifications',{refresh:true});assert.equal(h.calls.filter(call=>call.path==='/api/v1/activity-notifications').length,before+1);
 assert.equal(h.context.clientRaw.notifications[0].is_read,outcome==='saved');assert.equal(h.writes.length,1);assert.equal(h.file.value,'synthetic.png');assert.equal(h.support.value,'Keep Support');
});

test('a notification GET already loading makes retained Mark as read controls inert until current rows return',async t=>{
 const h=await mount(t),old=h.button(uid(1)),snapshot=deferred();h.setNotes(snapshot.promise);const read=h.context.clientLoad('notifications',{refresh:true});
 fire(old,'click');await flush();assert.equal(h.writes.length,0);snapshot.resolve([note(0)]);await read;
 fire(h.button(uid(1)),'click');await flush();assert.equal(h.writes.length,1);h.complete();await flush();assert.equal(h.context.clientRaw.notifications[0].is_read,true);
});


test('the pending notification read guard rechecks authority before returning any retained private state',async t=>{
 const h=await mount(t);fire(h.button(uid(1)),'click');await flush();h.session.user.id=uid(999);
 const state=await h.context.clientLoad('notifications',{refresh:true});assert.equal(state.status,'idle');assert.equal(state.data,null);assert.equal(h.root.innerHTML,'');assert.equal(h.file.value,'');
 h.complete();await flush();assert.equal(h.root.innerHTML,'');
});
