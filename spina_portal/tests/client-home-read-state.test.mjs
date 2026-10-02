import test from 'node:test';
import assert from 'node:assert/strict';
import {setImmediate} from 'node:timers/promises';
import {Element} from './helpers/dom.mjs';
import {mountClientWorkspace} from '../assets/roles/client.js';

const flush=async()=>{await setImmediate();await setImmediate();};
const deferred=()=>{let resolve;const promise=new Promise(done=>resolve=done);return {promise,resolve};};
const paths={loans:'/api/v1/client/loans',payments:'/api/v1/client/payments',renewals:'/api/v1/client/renewals',renewalWorkflow:'/api/v1/client/renewal-workflow',support:'/api/v1/client/support'};
const failed=()=>Object.assign(Error('Synthetic read failed'),{status:503});
async function mount(t,{loans={loans:[]}}={}){
 const root=new Element(),controller=new AbortController(),calls=[];let handle;
 const values=new Map([[paths.loans,loans],[paths.payments,{payments:[]}],[paths.renewals,{loans:[],requests:[]}],[paths.renewalWorkflow,{requests:[]}],[paths.support,{requests:[]}]]);
 const context={root,signal:controller.signal,setNavigation(){},registerWorkspaceHandle:value=>handle=value,api:{async request(path,options={}){
  calls.push({path,options});assert.notEqual(options.method,'POST');
  if(path==='/api/v1/account')return {profile:{full_name:'Synthetic account'}};
  if(path==='/api/v1/activity-notifications')return [];
  const value=values.get(path);if(value instanceof Error)throw value;return value??{};
 }}};
 await mountClientWorkspace(context);await flush();t.after(()=>controller.abort());
 const overview=root.querySelector('#client-overview'),actions=overview.querySelector('.daily-actions');
 return {root,context,handle,overview,calls,values,
  link:key=>actions.querySelector(`[data-nav-target="client-${key}"]`),
  read:(key,value)=>{values.set(paths[key],value);return context.clientLoad(key,{refresh:true});}};
}

test('Today loading and untouched lazy records never claim a failed read or verified empty result',async t=>{
 const pending=deferred(),h=await mount(t,{loans:pending.promise});
 assert.doesNotMatch(h.overview.textContent,/Some records could not load/);
 assert.match(h.link('loans').textContent,/Loading/i);
 for(const key of ['payments','renewals','support'])assert.doesNotMatch(h.link(key).textContent,/unavailable|No official receipt|\b0\b/i);
 assert.deepEqual(h.calls.map(call=>call.path).sort(),['/api/v1/account','/api/v1/activity-notifications','/api/v1/client/loans'].sort());
 pending.resolve({loans:[]});await flush();
 assert.doesNotMatch(h.link('loans').textContent,/unavailable|Loading/i);
});

test('My loans Today copy follows ready, loading, error and recovery while its button and focus stay put',async t=>{
 const h=await mount(t),link=h.link('loans'),label=link.querySelector('strong'),detail=link.querySelector('span');
 const form=h.root.querySelector('#client-support-form'),draft=form.querySelector('[name="message"]');draft.value='Retained question';
 const doc=link.ownerDocument;doc.activeElement=link;
 assert.doesNotMatch(link.textContent,/unavailable|Loading/i);
 const pending=deferred(),work=h.read('loans',pending.promise);
 assert.match(link.textContent,/Loading/i);pending.resolve({loans:[]});await work;
 await h.read('loans',failed());assert.match(link.textContent,/Loans unavailable/);
 assert.equal(h.overview.querySelector('[data-client-home-read-status]').hidden,false);
 await h.read('loans',{loans:[]});assert.doesNotMatch(link.textContent,/unavailable|Loading/i);
 assert.equal(h.overview.querySelector('[data-client-home-read-status]').hidden,true);
 assert.equal(h.link('loans'),link);assert.equal(link.querySelector('strong'),label);assert.equal(link.querySelector('span'),detail);assert.equal(doc.activeElement,link);
 assert.equal(h.root.querySelector('#client-support-form'),form);assert.equal(draft.value,'Retained question');
});

for(const [key,ready,readyText,empty,emptyText]of [
 ['payments',{payments:[{transaction_id:'synthetic-payment',receipt_number:'SYNTHETIC-RECEIPT'}]},/Review your payment history/,{payments:[]},/No official receipt yet/],
 ['support',{requests:[{request_id:'synthetic-question',status:'open'}]},/1 open request/,{requests:[]},/Send a question/],
])test(`${key} alone updates Today through loading/error/ready/empty without replacing task buttons or loan cards`,async t=>{
 const h=await mount(t),link=h.link(key),homeLoans=h.root.querySelector('[data-client-home-loans]'),loanContent=homeLoans.children[0];
 const form=h.root.querySelector('#client-renewal-form'),draft=form.querySelector('[name="message"]');draft.value='Retained renewal';
 const pending=deferred(),work=h.read(key,pending.promise);assert.match(link.textContent,/Loading/i);
 pending.resolve(ready);await work;assert.match(link.textContent,readyText);
 await h.read(key,failed());assert.match(link.textContent,/unavailable/i);assert.equal(h.overview.querySelector('[data-client-home-read-status]').hidden,false);
 await h.read(key,ready);assert.match(link.textContent,readyText);assert.equal(h.overview.querySelector('[data-client-home-read-status]').hidden,true);
 await h.read(key,empty);assert.match(link.textContent,emptyText);
 assert.equal(h.link(key),link);assert.equal(homeLoans.children[0],loanContent,'unrelated copy updates must not redraw loan content');
 assert.equal(h.root.querySelector('#client-renewal-form'),form);assert.equal(draft.value,'Retained renewal');
 assert.equal(h.calls.filter(call=>call.path===paths[key]).length,4);
});

test('renewal Today link clears old action counts on empty, error and recovery and keeps the same button',async t=>{
 const h=await mount(t),link=h.link('renewals'),record={request_id:'synthetic-request',loan_id:'synthetic-loan',status:'approved'};
 await h.read('renewals',{loans:[],requests:[record]});
 assert.doesNotMatch(link.textContent,/\d+ actions? for you|unavailable/i,'unread workflow is not a failed read or an available action');
 await h.read('renewalWorkflow',{requests:[record]});assert.match(link.textContent,/1 action for you/);
 await h.read('renewalWorkflow',{requests:[]});assert.doesNotMatch(link.textContent,/1 action for you/);
 await h.read('renewalWorkflow',failed());assert.match(link.textContent,/Renewals unavailable/);
 await h.read('renewalWorkflow',{requests:[]});assert.doesNotMatch(link.textContent,/unavailable|1 action for you/i);
 await h.read('renewals',{loans:[],requests:[{...record,status:'pending'}]});assert.match(link.textContent,/1 pending/);
 await h.read('renewals',{loans:[],requests:[]});assert.doesNotMatch(link.textContent,/1 pending|1 action for you/);
 assert.equal(h.link('renewals'),link);
});

test('Today warning clears only when its actual failed reads recover, not while another remains failed',async t=>{
 const h=await mount(t);await h.read('payments',failed());await h.read('support',failed());
 const notice=h.overview.querySelector('[data-client-home-read-status]');assert.ok(notice);assert.equal(notice.hidden,false);
 await h.read('payments',{payments:[]});assert.equal(notice.hidden,false);
 await h.read('support',{requests:[]});assert.equal(notice.hidden,true);
 const pending=deferred(),work=h.read('payments',pending.promise);assert.equal(notice.hidden,true,'loading is not a failed read');
 pending.resolve({payments:[]});await work;
 assert.equal(h.calls.filter(call=>[paths.renewals,paths.renewalWorkflow].includes(call.path)).length,0);
});
