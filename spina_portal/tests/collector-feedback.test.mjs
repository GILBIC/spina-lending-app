import assert from 'node:assert/strict';
import test from 'node:test';
import {setImmediate} from 'node:timers/promises';
import {Element, fire} from './helpers/dom.mjs';
import {mountCollectorWorkspace} from '../assets/roles/collector.js';

async function harness(t, kind) {
 const original = globalThis.FormData;
 globalThis.FormData = class { constructor(form) {this.form=form;} get(name) {return this.form.querySelector(`[name="${name}"]`)?.value ?? null;} };
 t.after(()=>{globalThis.FormData=original;});
 const doc=new EventTarget();const listeners=new Map();const add=doc.addEventListener.bind(doc),remove=doc.removeEventListener.bind(doc);doc.addEventListener=(type,handler,...args)=>{if(!listeners.has(type))listeners.set(type,new Set());listeners.get(type).add(handler);add(type,handler,...args);};doc.removeEventListener=(type,handler,...args)=>{listeners.get(type)?.delete(handler);remove(type,handler,...args);};doc.listenerCount=()=>[...listeners.values()].reduce((sum,set)=>sum+set.size,0);doc.body=new Element('body');doc.activeElement=doc.body;
 const root=new Element();root.dataset={};root.ownerDocument=doc;doc.createElement=tag=>{const node=new Element(tag);node.ownerDocument=doc;return node;};const controller=new AbortController();t.after(()=>controller.abort());
 let reject;const writes=[];let handle;
 await mountCollectorWorkspace({root,signal:controller.signal,setNavigation(){},registerWorkspaceHandle:value=>{handle=value;},
  session:{user:{role:'collector',id:'collector'},permissions:['route.view','collection.create','remittance.create']},
  sessionStore:{deviceId:()=> 'synthetic-device',nextDeviceSequence:()=>1},
  api:{async request(path,options={}) {
   if(options.method){writes.push({path,options});return new Promise((_,no)=>{reject=no;});}
   if(path==='/api/v1/collector/routes/today')return {route_date:'2026-10-01',entries:[{route_entry_id:'route-1',client_id:'client-1',loan_id:'loan-1',loan_type:'Regular',route_revision:'v1',can_enter_payment:true,daily_amount:'250.00'}]};
   if(path.endsWith('/remittances/recipients'))return [{user_id:'recipient',full_name:'Synthetic recipient',role_name:'Management'}];
   if(path.includes('/remittances/preview'))return {collector_user_id:'collector',collection_date:'2026-10-01',total_amount:'250.01',transaction_count:1,payment_count:1,unable_to_pay_count:0,covered_payment_count:0,client_count:1,refund_due_release_count:0,refund_due_release_total:'0.00',refund_due_releases:[],items:[{transaction_id:'txn',client_id:'client-1',loan_id:'loan-1',collection_date:'2026-10-01',entry_type:'payment',amount:'250.01',receipt_number:'R',covered_dates:[]}]};
   return {};
  }}});
 if(kind==='remittance')await handle.activate('collector-remittance');
 function decorate(node,parent=null) {
  node.parentElement=parent;node.ownerDocument=doc;let connected=true;Object.defineProperty(node,'isConnected',{get:()=>connected&&parent?.isConnected!==false,set:value=>{connected=value;}});node.hidden=node.getAttribute('hidden')!==null;
  node.dataset=Object.fromEntries(Object.entries(node.attributes).filter(([k])=>k.startsWith('data-')).map(([k,v])=>[k.slice(5).replace(/-([a-z])/g,(_,c)=>c.toUpperCase()),v]));
  node.contains=target=>target===node||node.children.some(child=>typeof child!=='string'&&child.contains(target));
  node.closest=selector=>{let current=node;while(current){if(selector==='[hidden]'&&current.hidden)return current;current=current.parentElement;}return null;};
  node.focus=()=>{doc.activeElement=node;const event=new Event('focusin');Object.defineProperty(event,'target',{value:node});doc.dispatchEvent(event);};
  let disabled=node.disabled;Object.defineProperty(node,'disabled',{get:()=>disabled,set:value=>{disabled=value;if(value&&doc.activeElement===node)doc.activeElement=doc.body;}});
  for(const child of node.children)if(typeof child!=='string')decorate(child,node);
 }
 decorate(root);
 const form=root.querySelector(kind==='remittance'?'#collector-remittance-form':'.collector-entry-form');form.hidden=false;
 const set=(name,value)=>{form.querySelector(`[name="${name}"]`).value=value;};
 set('note','Synthetic retained note');
 if(kind==='remittance'){set('recipientUserId','recipient');set('collectionDate','2026-10-01');form.querySelector('[name="reviewed"]').checked=true;fire(form,'change');}
 else {set('entryType',kind);set('amount','250.01');set('allocation','scheduled');if(kind==='pass')set('reasonCode','no_cash');}
 const button=form.querySelector('button[type="submit"]');button.focus();
 return {root,doc,form,button,writes,controller,start(){fire(form,'submit');},async reject(){assert.equal(typeof reject,'function','must reach actual API write');reject(Object.assign(new Error('Synthetic rejection; review entered values.'),{status:422}));await setImmediate();await setImmediate();}};
}

for(const kind of ['payment','pass','remittance'])test(`${kind} rejection keeps values and focuses persistent form-linked feedback after unlock`,async t=>{
 const h=await harness(t,kind);h.start();assert.equal(h.button.disabled,true);await h.reject();
 const feedback=h.form.querySelector('[data-collection-feedback]');assert.ok(feedback);assert.match(feedback.textContent,/Synthetic rejection/);
 assert.equal(feedback.hidden,false);assert.equal(h.form.getAttribute('aria-describedby'),feedback.getAttribute('id'));
 assert.equal(h.doc.activeElement,feedback);assert.equal(h.button.disabled,false);assert.equal(h.form.querySelector('[name="note"]').value,'Synthetic retained note');
 assert.equal(h.writes.length,1);
});

for(const away of ['another-control','hidden-section','detached','disposed'])test(`late rejection cannot steal focus after ${away}`,async t=>{
 const h=await harness(t,'payment');h.start();
 if(away==='another-control')h.form.querySelector('[name="note"]').focus();
 if(away==='hidden-section')h.root.querySelector('#collector-route').hidden=true;
 if(away==='detached')h.form.isConnected=false;
 if(away==='disposed')h.controller.abort();
 const before=h.doc.activeElement;await h.reject();assert.equal(h.doc.activeElement,before);assert.equal(h.writes.length,1);assert.equal(h.doc.listenerCount(),0);if(away==='disposed')assert.equal(h.button.disabled,true);
});
