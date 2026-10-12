import assert from 'node:assert/strict';
import test from 'node:test';
import * as elapsed from '../assets/management-elapsed-assessments.js';
import {Element,fire} from './helpers/dom.mjs';
const id=n=>`00000000-0000-4000-8000-${String(n).padStart(12,'0')}`;
const scope={bookId:id(1),periodId:id(3),loanId:id(4),applicationId:id(5)};
const candidate=()=>({book:{book_id:id(1)},period_id:id(3),loan_id:id(4),application_id:id(5),as_of_date:'2026-09-29',ready:true,blockers:[],source_digest:'a'.repeat(64),gross_carrying_amount:'510.00',opening_assessment_id:id(6),opening_cutoff_date:'2026-09-28',retained_review_id:null,current_confirmation:false,review:null});
const scenarios=()=>[0,1].map(i=>({scenario_key:`Case ${i}`,probability:'0.5',evidence_reference:'Dated forecast',management_rationale:'Reviewed actual dated expected recovery evidence.',forward_evidence_ids:[id(10+i)],expected_cash_flows:[{cash_date:'2026-09-29',amount:'110.00'}]}));
const inputs=()=>({scenarios:scenarios(),review_rationale:'Reviewed the actual after-cash dated expected receipt evidence.'});
const review=()=>({review_id:id(7),book_id:id(1),period_id:id(3),loan_id:id(4),application_id:id(5),as_of_date:'2026-09-29',calculated_at:'2026-10-10T03:00:00Z',source_digest:'a'.repeat(64),confirmation_digest:'b'.repeat(64),policy_version:'native_impaired_cash_expected_receipts_v1',loss_basis:'gross_carrying_less_expected_pv',opening_assessment_id:id(6),opening_cutoff_date:'2026-09-28',gross_carrying_amount:'510.00',expected_cash_present_value:'110.00',weighted_expected_cash_present_value_raw:'110.00',currency_rounding_adjustment:'0.00',ecl_amount:'400.00',scenario_count:2,review_inputs:inputs()});
const renewalOpening={opening_assessment_id:null,opening_renewal_review_id:id(41),opening_cutoff_date:'2026-09-29'};
test('same-day impaired successor cash binds a renewal opening without fabricating a fiscal assessment',()=>{
 const raw={...candidate(),...renewalOpening},c=elapsed.impairedCashCandidate(raw,scope),p={...review(),...renewalOpening};
 assert.equal(c.opening_assessment_id,null);assert.equal(c.opening_renewal_review_id,id(41));assert.equal(elapsed.impairedCashReview(p,scope,c).opening_renewal_review_id,id(41));
 for(const bad of [{opening_assessment_id:id(6)},{opening_renewal_review_id:null},{opening_cutoff_date:'2026-09-30'}])assert.throws(()=>elapsed.impairedCashCandidate({...raw,...bad},scope));
 assert.throws(()=>elapsed.impairedCashCandidate({...candidate(),opening_cutoff_date:'2026-09-29'},scope));
 assert.throws(()=>elapsed.impairedCashReview({...p,opening_renewal_review_id:id(42)},scope,c));
});
test('dated impaired cash measurement binds exact event and gross-minus-PV without allowance or stage inputs',()=>{
 const c=elapsed.impairedCashCandidate({...candidate(),private_chain:'PRIVATE'},scope);
 assert.doesNotMatch(JSON.stringify(c),/PRIVATE/);
 const p=elapsed.impairedCashReview(review(),scope,c);assert.equal(p.ecl_amount,'400.00');assert.equal(p.review_inputs.target_allowance,undefined);
 for(const bad of [{application_id:id(99)},{gross_carrying_amount:'511.00'},{expected_cash_present_value:'109.00'},{opening_assessment_id:id(99)},{source_digest:'c'.repeat(64)}])assert.throws(()=>elapsed.impairedCashReview({...review(),...bad},scope,c));
 const invalid=inputs();invalid.scenarios[0].expected_cash_flows[0].cash_date='2026-09-28';assert.throws(()=>elapsed.impairedCashInputs(invalid,c));
});
test('half-cent expected PV is rounded only after final loss measurement',()=>{
 const c=elapsed.impairedCashCandidate({...candidate(),gross_carrying_amount:'100.00'},scope);
 const p={...review(),gross_carrying_amount:'100.00',expected_cash_present_value:'100.00',weighted_expected_cash_present_value_raw:'99.995',currency_rounding_adjustment:'0.01',ecl_amount:'0.01'};
 assert.equal(elapsed.impairedCashReview(p,scope,c).ecl_amount,'0.01');
 assert.throws(()=>elapsed.impairedCashReview({...p,ecl_amount:'0.00',currency_rounding_adjustment:'0.00'},scope,c));
 assert.throws(()=>elapsed.impairedCashReview({...p,weighted_expected_cash_present_value_raw:99.995},scope,c));
});
test('blocked fiscal candidate reaches dated cash evidence review without financial posting',async()=>{
 const root=new Element(),writes=[],tick=()=>new Promise(r=>setImmediate(r)),book={status:'configured',book_id:id(1),entity_label:'Synthetic books'};
 const session={user:{id:id(2),role:'Management',roles:['management']},permissions:['accounting.view','accounting.period.close.prepare']};
 const api={async request(path,o={}){if(path.endsWith('/book'))return{book};if(path.includes('/ecl-forward-looking'))return{items:[0,1].map(i=>({id:id(10+i),source_name:'Forecast',source_reference:`Source ${i}`,effective_date:'2026-09-28',forecast_period_start:'2026-09-28',forecast_period_end:'2026-10-30',evidence_status:'current'}))};if(path.includes('/impaired-cash/')){if(o.method==='POST'){writes.push({path,body:structuredClone(o.body)});return{...review(),...renewalOpening};}return{...candidate(),...renewalOpening};}if(path.includes('/loans/'))return{book,period_id:id(3),loan_id:id(4),ready:false,blockers:['dated_impaired_cash_measurement_required'],as_of_date:'2026-09-30',source_digest:null,eir:null,gross_carrying_amount:null,prior_allowance:null,preparation:null,current_confirmation:false,comprehensive_source_coverage:false,impaired_cash_reviews:[{...candidate(),...renewalOpening}]};return{fiscal_periods:[{period_id:id(3),label:'September'}]};}};
 await elapsed.mountElapsedAssessments({root,api,session});const lookup=root.querySelector('[data-elapsed-lookup]');lookup.querySelector('[name="period_id"]').value=id(3);lookup.querySelector('[name="loan_id"]').value=id(4);fire(lookup,'submit');await tick();await tick();
 assert.ok(root.querySelector('[data-impaired-cash]'));fire(root.querySelector('[data-impaired-cash]'),'click');await tick();await tick();assert.match(root.textContent,/2026-09-29/);assert.match(root.textContent,/Opening renewal review/);assert.doesNotMatch(root.textContent,/Opening impaired assessment/);assert.equal(root.querySelector('[name="credit_risk_review_id"]'),null);
 for(let i=0;i<2;i++){const choice=root.querySelector(`[data-evidence-choice="${i}"]`);choice.value=id(10+i);fire(choice,'change');}
 const f=root.querySelector('[data-elapsed-inputs]'),x=inputs();f.querySelector('[name="review_rationale"]').value=x.review_rationale;
 x.scenarios.forEach((s,i)=>{for(const k of ['scenario_key','probability','evidence_reference','management_rationale'])f.querySelector(`[name="s${i}_${k}"]`).value=s[k];f.querySelector(`[name="s${i}_c0_cash_date"]`).value=s.expected_cash_flows[0].cash_date;f.querySelector(`[name="s${i}_c0_amount"]`).value=s.expected_cash_flows[0].amount;});
 fire(f,'submit');await tick();assert.match(root.textContent,/measurement evidence only/i);assert.equal(writes.length,0);fire(root.querySelector('[data-confirm]'),'click');await tick();await tick();
 assert.equal(writes.length,1);assert.match(writes[0].path,/impaired-cash.*review$/);assert.deepEqual(writes[0].body,{expected_book_id:id(1),source_digest:'a'.repeat(64),...inputs(),confirm:true});assert.match(root.textContent,/Cash-date measurement retained/);assert.equal(root.querySelector('[data-confirm-assessment]'),null);
});
