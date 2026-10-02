import assert from 'node:assert/strict';
import test from 'node:test';
import {Element,fire} from './helpers/dom.mjs';
const tick=()=>new Promise(resolve=>setImmediate(resolve));
const owner='10000000-0000-4000-8000-000000000001';
const row=i=>({notification_id:`20000000-0000-4000-8000-${String(i).padStart(12,'0')}`,recipient_user_id:owner,is_read:false,title:`Update ${i}`,message:'Saved activity'});
test('My updates shows30/60/65 owned distinct rows, then changes only confirmed read row',async()=>{
 const mod=await import('../assets/management-personal-updates.js').catch(()=>({}));assert.ok(mod.mountManagementPersonalUpdates);
 const root=new Element();let wrong=true;
 const h=mod.mountManagementPersonalUpdates({root,getSession:()=>({user:{id:owner}}),api:{async request(path,options){return options?.method?{...row(0),recipient_user_id:wrong?'different':owner,is_read:true,read_at:'2026-10-02T01:00:00Z'}:Array.from({length:65},(_,i)=>row(i));}}});
 await h.refresh();const visible=()=>root.querySelectorAll('[data-my-update]').filter(x=>x.getAttribute('hidden')===null).length;
 assert.equal(visible(),30);fire(root.querySelector('[data-updates-more]'),'click');assert.equal(visible(),60);fire(root.querySelector('[data-updates-more]'),'click');assert.equal(visible(),65);
 const other=root.querySelectorAll('[data-my-update]')[1],button=root.querySelector('[data-update-read]');fire(button,'click');await tick();assert.match(root.textContent,/could not be confirmed/);assert.equal(button.hidden,false);assert.equal(root.querySelector('[data-update-status]').textContent,'Unread');
 wrong=false;fire(button,'click');await tick();assert.equal(button.hidden,true);assert.equal(root.querySelectorAll('[data-my-update]')[1],other);h.dispose();
});
test('wrong-recipient update content is never shown and abort prevents late notification writes',async()=>{
 const mod=await import('../assets/management-personal-updates.js').catch(()=>({}));assert.ok(mod.mountManagementPersonalUpdates);
 const root=new Element();let resolve;const controller=new AbortController();
 const h=mod.mountManagementPersonalUpdates({root,getSession:()=>({user:{id:owner}}),signal:controller.signal,api:{request(){return new Promise(done=>resolve=done);}}});
 const read=h.refresh();resolve([{...row(1),recipient_user_id:'other',title:'Private other person'}]);await read;assert.doesNotMatch(root.textContent,/Private other person/);
 const late=h.refresh();controller.abort();resolve([row(1)]);await late;assert.doesNotMatch(root.textContent,/Update 1/);
});
