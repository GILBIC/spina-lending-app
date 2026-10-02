import test from 'node:test';import assert from 'node:assert/strict';import * as client from '../assets/roles/client.js';
const ready=data=>({status:'ready',data});
test('one request one current card, exact join and workflow error is neutral',()=>{
 assert.equal(typeof client.clientRenewalPresentation,'function');const requestsState=ready({requests:[{request_id:'one',status:'approved',requested_amount:'5000.00'}]});const workflowState=ready({requests:[{request_id:'one',status:'approved',client_cash_confirmed_at:'2026-10-02',activation_status:'pending'}]});let view=client.clientRenewalPresentation({requestsState,workflowState,view:'current'});assert.equal(view.cards.length,1);assert.match(view.cards[0].nextStep,/Management verification/);view=client.clientRenewalPresentation({requestsState,workflowState:{status:'error'},view:'current'});assert.equal(view.cards[0].workflow,null);assert.match(view.cards[0].nextStep,/unavailable/);
});
test('unknown readiness cannot offer signing and cash confirmed is not active',()=>{const html=client.clientRenewalWorkflowRows([{request_id:'one',status:'approved',client_decision:'accepted',signer_readiness_status:'invented',signers:[{signer_id:'own',party_role:'borrower',signed:false,government_id_verified:true,selfie_verified:true}],client_cash_confirmed_at:'date',activation_status:'pending'}]);assert.doesNotMatch(html,/data-client-renewal-sign-request/);assert.match(html,/not collectible yet/);});

test('pending renewal joined to workflow retains cancellation and original client note',()=>{const html=client.clientRenewalWorkflowRows([{request_id:'pending',status:'pending',client_message:'Original request note'}]);assert.match(html,/data-client-renewal-cancel="pending"/);assert.match(html,/Original request note/);});


const own={signer_id:'10000000-0000-4000-8000-000000000101',party_role:'borrower',has_app:true,government_id_verified:true,selfie_verified:true,signed:false,ready:false};
const other={...own,signer_id:'10000000-0000-4000-8000-000000000102',party_role:'guarantor'};
const record={request_id:'10000000-0000-4000-8000-000000000001',client_id:'10000000-0000-4000-8000-000000000002',loan_id:'10000000-0000-4000-8000-000000000003',loan_number:'SYNTHETIC',status:'approved',requested_amount:'5000.00',approved_principal:'5000.00',renewal_offset_amount:'100.00',net_release_amount:'4900.00',client_decision:'accepted',office_processing_required:false,signer_readiness_status:'pending',signers:[own,other],handover_proof_status:'not_submitted',activation_status:'not_released'};
const presentation=value=>client.clientRenewalPresentation({requestsState:ready({requests:[{request_id:value.request_id,client_id:value.client_id,loan_id:value.loan_id,status:value.status,requested_amount:value.requested_amount}]}),workflowState:ready({requests:[value]})});

test('already-signed borrower gets other-account next step while existing own-action guards remain unchanged',()=>{
 const supplied={...record,signers:[{...own,signed:true},other]};const card=presentation(supplied).cards[0];
 assert.match(card.nextStep,/your signer step.*complete/i);assert.match(card.nextStep,/other.*own.*account/i);assert.doesNotMatch(card.nextStep,/Complete your own signer step/);
 const html=client.clientRenewalWorkflowRows([supplied]);assert.doesNotMatch(html,/data-client-renewal-sign-request/);
});

for(const readiness of [null,'future_token'])test(`accepted ${readiness} readiness stays neutral and refreshable without sign actions`,()=>{
 const value={...record,signer_readiness_status:readiness};assert.match(presentation(value).cards[0].nextStep,/unavailable|unknown/i);assert.match(presentation(value).cards[0].nextStep,/Refresh/);
 assert.doesNotMatch(presentation(value).cards[0].nextStep,/Complete your own signer step/);assert.doesNotMatch(client.clientRenewalWorkflowRows([value]),/data-client-renewal-sign-request/);
});

test('renewal display preserves actual collector reason/comment and Management override notes with escaping',()=>{
 const html=client.clientRenewalWorkflowRows([{...record,client_message:'Client <message>',review_note:'Manager <review>',collector_comment:'Collector <comment>',collector_reason_code:'saved_reason_<code>',management_override_reason:'Override <reason>'}]);
 for(const value of ['Client &lt;message&gt;','Manager &lt;review&gt;','Collector &lt;comment&gt;','saved_reason_&lt;code&gt;','Override &lt;reason&gt;'])assert.ok(html.includes(value),value);
 for(const label of ['Collector note:','Collector reason:','Management override reason:'])assert.ok(html.includes(label),label);
 assert.doesNotMatch(html,/<message>|<review>|<comment>|<code>|<reason>/);
});

for(const [field,value,label]of [
 ['signer_readiness_status','pending','Verification or signatures pending'],['signer_readiness_status','ready','Signers ready'],['signer_readiness_status','office_required','Office processing required'],
 ['handover_proof_status','not_submitted','Not submitted'],['handover_proof_status','under_review','Under review'],['handover_proof_status','approved','Approved'],['handover_proof_status','correction_required','Correction required'],['handover_proof_status','flagged','Flagged for review'],
 ['activation_status','not_released','Not released'],['activation_status','released_pending_management','Released; awaiting Management verification'],['activation_status','active','Active'],
])test(`display-only ${field} ${value} uses a readable known label`,()=>{
 const html=client.clientRenewalWorkflowRows([{...record,[field]:value,...(field==='signer_readiness_status'?{}:{client_cash_confirmed_at:'2026-10-02T09:00:00+08:00'})}]);assert.ok(html.includes(field==='signer_readiness_status'?`<span>Signer status</span><strong>${label}</strong>`:field==='handover_proof_status'?`Handover proof: ${label} · Activation:`:`Activation: ${label}</p>`),label);
});

test('unknown returned stage tokens stay escaped details rather than a known or complete status',()=>{
 const html=client.clientRenewalWorkflowRows([{...record,signer_readiness_status:'future_<signer>',client_cash_confirmed_at:'2026-10-02T09:00:00+08:00',handover_proof_status:'future_<proof>',activation_status:'future_<activation>'}]);
 for(const value of ['future_&lt;signer&gt;','future_&lt;proof&gt;','future_&lt;activation&gt;'])assert.ok(html.includes(value));
 assert.match(html,/Status unavailable/);assert.match(html,/not collectible yet/);assert.doesNotMatch(html,/<signer>|<proof>|<activation>/);
});

test('saved exact principal/offset/net are formatted independently without arithmetic',()=>{
 const html=client.clientRenewalWorkflowRows([{...record,approved_principal:'90071992547409.93',renewal_offset_amount:'100.01',net_release_amount:'4900.02'}]);
 assert.match(html,/90,071,992,547,409\.93/);assert.match(html,/100\.01/);assert.match(html,/4,900\.02/);
});

test('actual renewal lifecycle preserves permitted own actions and separates cash confirmation from activation',()=>{
 const cases=[
  [{...record,status:'pending',client_decision:null},'current',/assigned Collector/,['cancel']],
  [{...record,status:'cancelled'},'history',/No further action/,[]],
  [{...record,status:'rejected'},'history',/No further action/,[]],
  [{...record,client_decision:null},'current',/Review approved terms/,['decision']],
  [{...record,client_decision:'declined'},'history',/No further action/,[]],
  [{...record,signers:[{...own,government_id_verified:false},other]},'current',/signer/,[]],
  [record,'current',/signer/,['sign']],
  [{...record,office_processing_required:true,signer_readiness_status:'office_required'},'current',/office/,[]],
  [{...record,signer_readiness_status:'ready',signers:[{...own,signed:true,ready:true},{...other,signed:true,ready:true}],amount_locked_at:'2026-10-02T08:00:00+08:00',cash_given_to_client_at:'2026-10-02T09:00:00+08:00'},'current',/personally receive/,['cash']],
  [{...record,signer_readiness_status:'ready',signers:[{...own,signed:true},{...other,signed:true}],client_cash_confirmed_at:'2026-10-02T09:00:00+08:00',activation_status:'released_pending_management'},'current',/Management verification/,[]],
  [{...record,signer_readiness_status:'ready',signers:[{...own,signed:true},{...other,signed:true}],client_cash_confirmed_at:'2026-10-02T09:00:00+08:00',activation_status:'active',new_loan_id:'10000000-0000-4000-8000-000000000004'},'history',/loan active/,[]],
 ];
 for(const [value,view,next,actions]of cases){
  const result=client.clientRenewalPresentation({requestsState:ready({requests:[value]}),workflowState:ready({requests:[value]}),view});assert.equal(result.cards.length,1);assert.match(result.cards[0].nextStep,next);
  const html=client.clientRenewalWorkflowRows([value]);for(const [kind,attribute]of [['cancel','data-client-renewal-cancel'],['decision','data-client-renewal-decision-request'],['sign','data-client-renewal-sign-request'],['cash','data-client-renewal-cash-confirm']])assert.equal(html.includes(attribute),actions.includes(kind),`${value.status}/${value.client_decision}/${value.activation_status} ${kind}`);
 }
});

test('same-name requests join only by exact IDs and conflict/error/stale selection never invents progress',()=>{
 const second={...record,request_id:'10000000-0000-4000-8000-000000000005',loan_id:'10000000-0000-4000-8000-000000000006'};
 const requestsState=ready({requests:[record,second]});
 let result=client.clientRenewalPresentation({requestsState,workflowState:ready({requests:[second,record]})});assert.deepEqual(result.cards.map(card=>card.workflow.request_id),[record.request_id,second.request_id]);
 result=client.clientRenewalPresentation({requestsState,workflowState:{status:'error'}});assert.ok(result.cards.every(card=>!card.workflow&&/unavailable/.test(card.nextStep)));
 result=client.clientRenewalPresentation({requestsState,workflowState:ready({requests:[{...record,loan_id:second.loan_id}]})});assert.equal(result.cards[0].conflict,true);assert.match(result.cards[0].nextStep,/disagree/);
 assert.equal(client.clientRenewalPresentation({requestsState,workflowState:ready({requests:[record]}),selectedRequestId:'missing'}).cards.length,0);
});


test('accepted verification-pending guidance does not ask for a signature before existing readiness permits it',()=>{
 for(const signers of [[{...own,government_id_verified:false},other],[{...own,selfie_verified:false},other],[{...own,has_app:false},other],[]]){
  const value={...record,signers};assert.match(presentation(value).cards[0].nextStep,/verification|register.*signer/i);assert.doesNotMatch(presentation(value).cards[0].nextStep,/Complete your own signer step/);assert.doesNotMatch(client.clientRenewalWorkflowRows([value]),/data-client-renewal-sign-request/);
 }
 const complete={...record,signer_readiness_status:'ready',signers:[{...own,signed:true},{...other,signed:true}]};assert.match(presentation(complete).cards[0].nextStep,/complete.*Waiting/i);assert.doesNotMatch(presentation(complete).cards[0].nextStep,/Complete your own signer step/);
});


for(const token of ['constructor','toString','__proto__'])test(`inherited-looking stage ${token} stays unavailable rather than becoming a known label`,()=>{
 const html=client.clientRenewalWorkflowRows([{...record,signer_readiness_status:token,client_cash_confirmed_at:'2026-10-02T09:00:00+08:00',handover_proof_status:token,activation_status:token}]);
 for(const text of [`<span>Signer status</span><strong>Status unavailable (${token})</strong>`,`Handover proof: Status unavailable (${token}) · Activation:`,`Activation: Status unavailable (${token})</p>`])assert.ok(html.includes(text));assert.doesNotMatch(html,/function Object|function toString|\[object Object\]|data-client-renewal-sign-request/);
});

test('authoritative ready state with own signature complete waits for office rather than inferring which other signer is required',()=>{
 const value={...record,signer_readiness_status:'ready',signers:[{...own,signed:true},other]};
 assert.match(presentation(value).cards[0].nextStep,/complete.*Waiting.*office/);assert.doesNotMatch(presentation(value).cards[0].nextStep,/Other signers must finish/);
});
