import assert from 'node:assert/strict';
import test from 'node:test';
import * as risk from '../assets/management-elapsed-assessments.js';
import {Element,fire} from './helpers/dom.mjs';
const id=n=>`00000000-0000-4000-8000-${String(n).padStart(12,'0')}`;
export const riskScope={bookId:id(1),periodId:id(3),loanId:id(4)};
export const context=()=>({book_id:id(1),period_id:id(3),loan_id:id(4),ready:true,blockers:[],as_of_date:'2026-10-10',source_digest:'a'.repeat(64),schedule_id:id(8),schedule_version:1,days_past_due:35,due_unpaid_amount:'100.00',thirty_day_sicr_backstop_reached:true,ninety_day_default_backstop_reached:false,prior_review:null});
export const review=()=>({stage_label:'stage_2_lifetime',default_label:false,write_off_label:'none',recovery_label:'none',primary_evidence_basis:'contractual_dpd',evidence_reference:'Dated borrower evidence',review_note:'Reviewed the current dated repayment evidence.',sicr_backstop_rebutted:false,default_backstop_rebutted:false,rebuttal_evidence_reference:null,rebuttal_note:null,write_off_evidence_reference:null,write_off_note:null,recovery_transaction_id:null});
const inherited=()=>({id:53,review_version:2,loan_id:id(7),stage_label:'stage_3_credit_impaired',default_label:false,write_off_label:'none',recovery_label:'cash_recovery_observed',reviewed_at:'2026-10-09T03:00:00Z'});
test('inherited impairment context preserves exact predecessor identity without setting current labels',()=>{
 const raw={...context(),inherited_review:{...inherited(),private_snapshot:'PRIVATE'}};
 const out=risk.currentRiskContext(raw,riskScope);assert.deepEqual(out.inherited_review,inherited());assert.equal(out.prior_review,null);assert.doesNotMatch(JSON.stringify(out),/PRIVATE/);
 for(const patch of [{loan_id:id(4)},{loan_id:'unknown'},{stage_label:'unknown'},{review_version:0},{default_label:'false'},{reviewed_at:'2026-10-09'}])assert.throws(()=>risk.currentRiskContext({...raw,inherited_review:{...inherited(),...patch}},riskScope));
 for(const stage_label of ['stage_1_12_month','stage_2_lifetime']){const prior={...inherited(),stage_label,recovery_label:'none'};const context=risk.currentRiskContext({...raw,inherited_review:prior},riskScope);assert.deepEqual(context.inherited_review,prior);assert.equal(context.prior_review,null);assert.equal(Object.hasOwn(context,'credit_impaired_interest'),false);}
 assert.equal(risk.currentRiskInputs({...review(),recovery_label:'cured',primary_evidence_basis:'verified_source_document'},out).recovery_label,'cured');
});
test('current risk context binds server cutoff, exact scope and source without exposing snapshots',()=>{
 const out=risk.currentRiskContext({...context(),private_snapshot:'PRIVATE'},riskScope);
 assert.equal(out.as_of_date,'2026-10-10');assert.doesNotMatch(JSON.stringify(out),/PRIVATE/);
 for(const bad of [{book_id:id(9)},{schedule_version:0},{days_past_due:'35'},{due_unpaid_amount:100},{thirty_day_sicr_backstop_reached:false}])assert.throws(()=>risk.currentRiskContext({...context(),...bad},riskScope));
});
test('risk labels are explicit and require separate substantive rebuttal evidence',()=>{
 assert.deepEqual(risk.currentRiskInputs(review(),context()),review());
 for(const bad of [{stage_label:''},{default_label:''},{write_off_label:''},{recovery_label:''},{stage_label:'stage_1_12_month'},{sicr_backstop_rebutted:true}])assert.throws(()=>risk.currentRiskInputs({...review(),...bad},context()));
 const rebutted={...review(),stage_label:'stage_1_12_month',primary_evidence_basis:'verified_source_document',sicr_backstop_rebutted:true,rebuttal_evidence_reference:'Separate rebuttal',rebuttal_note:'Documented reasons supporting the reviewed rebuttal.'};
 assert.equal(risk.currentRiskInputs(rebutted,context()).stage_label,'stage_1_12_month');
});
for(const stage of ['stage_3_credit_impaired','stage_2_lifetime'])test(`${stage} inherited cutoff review preserves history and explicitly confirms unchanged current evidence`,async()=>{
 const root=new Element(),writes=[],tick=()=>new Promise(r=>setImmediate(r));let lose=true;
 const book={status:'configured',book_id:id(1),entity_label:'Synthetic books'};
 const session={user:{id:id(2),role:'Management',roles:['management']},permissions:['accounting.view','accounting.ecl.credit_risk_label.review']};
 const api={async request(path,o={}){if(path.endsWith('/book'))return{book};if(path.includes('/ecl-forward-looking'))return{items:[]};if(path.endsWith('/risk-review')){if(o.method==='POST'){writes.push(structuredClone(o.body));if(lose)throw Error('Lost response');return{review_id:71,reviewed_at:'2026-10-10T03:00:00Z',as_of_date:'2026-10-10',stage_label:o.body.review.stage_label,default_label:o.body.review.default_label,recovery_label:o.body.review.recovery_label};}return{...context(),inherited_review:{...inherited(),stage_label:stage}};}if(path.includes('/loans/'))return{book,period_id:id(3),loan_id:id(4),ready:false,blockers:['credit_risk_review_required'],as_of_date:'2026-10-10',source_digest:null,eir:null,gross_carrying_amount:null,prior_allowance:null,preparation:null,current_confirmation:false,comprehensive_source_coverage:false};return{fiscal_periods:[{period_id:id(3),label:'Today'}]};}};
 await risk.mountElapsedAssessments({root,api,session});let f=root.querySelector('[data-elapsed-lookup]');f.querySelector('[name="period_id"]').value=id(3);f.querySelector('[name="loan_id"]').value=id(4);fire(f,'submit');await tick();await tick();
 assert.ok(root.querySelector('[data-current-risk]'));fire(root.querySelector('[data-current-risk]'),'click');await tick();await tick();
 f=root.querySelector('[data-current-risk-inputs]');assert.ok(f);assert.match(root.textContent,/Inherited credit-risk review/);assert.match(root.textContent,new RegExp(id(7)));assert.match(root.textContent,new RegExp(stage));if(stage==='stage_2_lifetime')assert.doesNotMatch(root.textContent,/Impairment continues/);for(const key of ['stage_label','default_label','recovery_label'])assert.equal(f.querySelector(`[name="${key}"]`).value,'');fire(f,'submit');await tick();assert.equal(writes.length,0);assert.equal(root.querySelector('[data-confirm]'),null);
 const cure={...review(),recovery_label:stage==='stage_3_credit_impaired'?'cured':'none',primary_evidence_basis:'verified_source_document'};
 for(const [key,value] of Object.entries(cure))if(value!==null)f.querySelector(`[name="${key}"]`).value=String(value);
 fire(f,'submit');await tick();assert.match(root.textContent,/Schedule version/);assert.match(root.textContent,/No financial journal/);assert.equal(writes.length,0);
 fire(root.querySelector('[data-confirm]'),'click');await tick();await tick();assert.ok(root.querySelector('[data-retry]'));lose=false;fire(root.querySelector('[data-retry]'),'click');await tick();await tick();
 assert.deepEqual(writes[0],writes[1]);assert.deepEqual(writes[0],{expected_book_id:id(1),source_digest:'a'.repeat(64),confirm:true,review:cure});assert.match(root.textContent,/Credit-risk review retained/);assert.equal(root.querySelector('[data-confirm-assessment]'),null);
});
