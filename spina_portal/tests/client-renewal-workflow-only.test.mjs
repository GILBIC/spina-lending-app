import test from 'node:test';
import assert from 'node:assert/strict';
import {setImmediate} from 'node:timers/promises';
import {Element,fire} from './helpers/dom.mjs';
import {mountClientWorkspace,clientRenewalPresentation} from '../assets/roles/client.js';
const flush=async()=>{await setImmediate();await setImmediate();};
const uid=n=>`10000000-0000-4000-8000-${String(n).padStart(12,'0')}`;
const own={signer_id:uid(20),party_role:'borrower',has_app:true,government_id_verified:true,selfie_verified:true,signed:false,ready:false};
const base={request_id:uid(1),client_id:uid(2),loan_id:uid(3),loan_number:'SAME',status:'approved',requested_amount:'5000.00',approved_principal:'5000.00',renewal_offset_amount:'100.00',net_release_amount:'4900.00',client_decision:null,office_processing_required:false,signer_readiness_status:'pending',signers:[own],handover_proof_status:'not_submitted',activation_status:'not_released'};
const actions=[
 ['decision',base,'data-client-renewal-decision-request'],
 ['sign',{...base,client_decision:'accepted'},'data-client-renewal-sign-request'],
 ['cash',{...base,client_decision:'accepted',signer_readiness_status:'ready',signers:[{...own,signed:true,ready:true}],amount_locked_at:'2026-10-02T08:00:00+08:00',cash_given_to_client_at:'2026-10-02T09:00:00+08:00'},'data-client-renewal-cash-confirm'],
];
async function mount(t,{requests=[],workflow=[base]}={}){
 const root=new Element(),controller=new AbortController(),calls=[];let handle;
 const query=root.querySelectorAll.bind(root);root.querySelectorAll=selector=>{const pair=selector.match(/^(\[[^\]]+\])(\[[^\]]+\])$/);return pair?query(pair[1]).filter(n=>n.getAttribute(pair[2].slice(1,-1))!==null):query(selector);};
 const context={root,signal:controller.signal,setNavigation(){},registerWorkspaceHandle:value=>handle=value,
  activateNavigation(){for(const button of root.querySelectorAll('[data-nav-target]'))button.addEventListener('click',()=>{void handle.activate(button.dataset.navTarget);});},
  api:{async request(path,options={}){calls.push({path,options});assert.notEqual(options.method,'POST');
   if(path==='/api/v1/account')return {profile:{}};if(path==='/api/v1/activity-notifications')return [];if(path==='/api/v1/client/loans')return {loans:[]};
   if(path==='/api/v1/client/renewals'){if(requests instanceof Error)throw requests;return {loans:[],requests:structuredClone(requests)};}
   if(path==='/api/v1/client/renewal-workflow'){if(workflow instanceof Error)throw workflow;return {requests:structuredClone(workflow)};}
   if(path.startsWith('/api/v1/client/payment-proofs'))return {proofs:[],capability:{upload_available:true,max_bytes:10485760}};return {requests:[]};
  }}};
 await mountClientWorkspace(context);await handle.activate('client-payment-proofs');await handle.activate('client-renewals');await handle.activate('client-overview');await flush();t.after(()=>controller.abort());
 const overview=root.querySelector('#client-overview'),link=overview.querySelector('[data-nav-target="client-renewals"]'),label=link.querySelector('strong'),detail=link.querySelector('span');
 const support=root.querySelector('#client-support-form').querySelector('[name="message"]'),file=root.querySelector('[name="proofFile"]');support.value='Retained Support';file.value='synthetic.png';
 return {root,context,handle,calls,overview,link,label,detail,support,file};
}

for(const [name,workflow,attribute]of actions)test(`Today retains protected workflow-only ${name} and opens its exact usable renewal card without writes`,async t=>{
 const h=await mount(t,{workflow:[workflow]});assert.match(h.link.textContent,/1 action for you/);assert.match(h.overview.textContent,/Pending renewals 0/);
 const before=h.calls.length;h.link.ownerDocument.activeElement=h.link;fire(h.link,'click');await flush();
 const card=h.root.querySelector(`[data-client-renewal-record="${base.request_id}"]`);assert.ok(card);assert.ok(card.querySelector(`[${attribute}="${base.request_id}"]`));assert.doesNotMatch(h.root.querySelector('[data-client-region="renewals"]').textContent,/No current renewal request/);
 assert.equal(h.calls.length,before);assert.equal(h.overview.querySelector('[data-nav-target="client-renewals"]'),h.link);assert.equal(h.link.querySelector('strong'),h.label);assert.equal(h.link.querySelector('span'),h.detail);assert.equal(h.link.ownerDocument.activeElement,h.link);assert.equal(h.support.value,'Retained Support');assert.equal(h.file.value,'synthetic.png');
});

test('Today can report pending requests and separate verified actions together without replacing its link',async t=>{
 const pending={...base,request_id:uid(4),status:'pending',loan_id:uid(5),client_message:'Saved pending note'};
 const h=await mount(t,{requests:[pending],workflow:[base]});assert.match(h.link.textContent,/1 action for you/);assert.match(h.link.textContent,/1 pending/);assert.match(h.overview.textContent,/Pending renewals 1/);
 assert.equal(h.root.querySelectorAll('[data-client-renewal-record]').length,2);
});

for(const source of ['requests','workflow'])test(`${source} failed cannot expose workflow-only continuation or stale Today actions`,async t=>{
 const error=Object.assign(Error('Synthetic read unavailable'),{status:503});const h=await mount(t,source==='requests'?{requests:error,workflow:[base]}:{requests:[],workflow:error});
 assert.match(h.link.textContent,/Renewals unavailable/);assert.doesNotMatch(h.link.textContent,/1 action for you/);assert.equal(h.root.querySelector('[data-client-renewal-decision-request]'),null);
});

test('exact conflicting request ID stays neutral while distinct same-name workflow-only records retain their own identity',()=>{
 const second={...base,request_id:uid(6),loan_id:uid(7)};
 const requests=[{...base,loan_id:uid(99)}],workflow=[base,second],snapshot=JSON.stringify({requests,workflow});
 const result=clientRenewalPresentation({requestsState:{status:'ready',data:{requests}},workflowState:{status:'ready',data:{requests:workflow}}});
 assert.equal(result.cards.length,2);assert.equal(result.cards[0].conflict,true);assert.equal(result.cards[0].workflow,null);assert.equal(result.cards[1].request.request_id,second.request_id);assert.equal(result.cards[1].workflow.loan_id,second.loan_id);assert.equal(JSON.stringify({requests,workflow}),snapshot);
});
