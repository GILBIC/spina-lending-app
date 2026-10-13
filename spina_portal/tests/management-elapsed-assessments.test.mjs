import assert from 'node:assert/strict';
import test from 'node:test';
import { elapsedCandidate, elapsedPreparation, elapsedInputs, mountElapsedAssessments } from '../assets/management-elapsed-assessments.js';
import { Element, fire } from './helpers/dom.mjs';
const id = n => `00000000-0000-4000-8000-${String(n).padStart(12,'0')}`, digest = 'a'.repeat(64);
const tick = () => new Promise(resolve => setImmediate(resolve));
const book = {status:'configured',book_id:id(1),kind:'owner_operations',entity_label:'Owner books'};
const session = {user:{id:id(2),role:'Management',roles:['management']},permissions:['accounting.view','accounting.period.close.prepare','accounting.period.close.post']};
const scope = {bookId:id(1),periodId:id(3),loanId:id(4)};
const candidate = () => ({book,period_id:id(3),loan_id:id(4),ready:true,blockers:[],as_of_date:'2026-09-30',source_digest:digest,current_confirmation:false,eir:{cumulative_interest:'62.58',prior_recognized_interest:'31.20',incremental_interest:'31.38'},gross_carrying_amount:'5062.58',prior_allowance:'4.00',days_past_due:0,preparation:null,comprehensive_source_coverage:false});
const preparation = () => ({preparation_id:id(5),book_id:id(1),period_id:id(3),loan_id:id(4),as_of_date:'2026-09-30',source_digest:digest,confirmation_digest:'b'.repeat(64),calculated_at:'2026-10-05T08:12:00+00:00',policy_version:'historical_original_timing_cash_shortfall_v1',cumulative_interest:'62.58',incremental_interest:'31.38',prior_allowance:'4.00',ecl_amount:'3.50',allowance_delta:'-0.50',scenario_count:2,review_inputs:elapsedInputs(inputs(),'2026-09-30'),comprehensive_source_coverage:false});
const inputs = () => ({evidence_reference:'Risk review 123',review_note:'Contractual repayment facts reviewed at the selected cutoff.',review_rationale:'Reviewed the dated evidence and reasonable expected receipt scenarios.',scenarios:['0.7','0.3'].map((probability,i)=>({scenario_key:`Case ${i+1}`,probability,evidence_reference:`Forecast ${i+1}`,management_rationale:'Documented plausible receipts supported by dated economic evidence.',forward_evidence_ids:[id(10+i)],expected_cash_flows:[{cash_date:'2026-10-20',amount:'5000.00'}]}))});
function fixture(){ const writes=[]; return {writes,async request(path,options={}) {if(path.endsWith('/book'))return {book};if(path.includes('/ecl-forward-looking-evidence'))return {items:[0,1].map(i=>({id:id(10+i),source_name:`Forecast ${i+1}`,source_reference:`Forecast reference ${i+1}`,effective_date:'2026-09-01',forecast_period_start:'2026-09-01',forecast_period_end:'2026-12-31',evidence_status:'current'}))};if(options.method==='POST'){writes.push({path,body:structuredClone(options.body)});return path.endsWith('/prepare')?preparation():{posting_id:id(6)};}if(path.includes('/period-elapsed-assessments/'))return candidate();return {fiscal_periods:[{period_id:id(3),label:'September'}]};}};}
async function lookup(root){const f=root.querySelector('[data-elapsed-lookup]');f.querySelector('[name="period_id"]').value=id(3);f.querySelector('[name="loan_id"]').value=id(4);fire(f,'submit');await tick();await tick();}
function fill(root){for(let i=0;i<2;i++){const pick=root.querySelector(`[data-evidence-choice="${i}"]`);pick.value=id(10+i);fire(pick,'change');}const x=inputs(), f=root.querySelector('[data-elapsed-inputs]');for(const k of ['evidence_reference','review_note','review_rationale'])f.querySelector(`[name="${k}"]`).value=x[k];x.scenarios.forEach((s,i)=>{for(const k of ['scenario_key','probability','evidence_reference','management_rationale'])f.querySelector(`[name="s${i}_${k}"]`).value=s[k];f.querySelector(`[name="s${i}_c0_cash_date"]`).value=s.expected_cash_flows[0].cash_date;f.querySelector(`[name="s${i}_c0_amount"]`).value=s.expected_cash_flows[0].amount;});return f;}

const settledCandidate=()=>({...candidate(),settled_by_exact_payoff:true,payoff_review_id:id(20),gross_carrying_amount:'0.00',eir:{cumulative_interest:'62.58',prior_recognized_interest:'62.58',incremental_interest:'0.00'}});
const settledRationale='Reviewed the exact posted payoff and complete settlement evidence.';
const settledPreparation=()=>({...preparation(),policy_version:'regular_exact_payoff_zero_ecl_v1',settled_by_exact_payoff:true,payoff_review_id:id(20),incremental_interest:'0.00',ecl_amount:'0.00',allowance_delta:'-4.00',scenario_count:0,review_inputs:{payoff_review_id:id(20),review_rationale:settledRationale}});
const renewedCandidate=()=>({...settledCandidate(),settled_by_exact_payoff:false,payoff_review_id:null,settled_by_exact_renewal:true,renewal_review_id:id(40)});
const renewedPreparation=()=>({...settledPreparation(),policy_version:'regular_exact_renewal_zero_ecl_v1',settled_by_exact_payoff:false,payoff_review_id:null,settled_by_exact_renewal:true,renewal_review_id:id(40),review_inputs:{renewal_review_id:id(40),review_rationale:settledRationale}});
test('old renewed loan has a separate exact zero assessment with no payoff or scenario substitution',async()=>{
 const c=elapsedCandidate(renewedCandidate(),scope);assert.equal(c.renewal_review_id,id(40));assert.equal(elapsedPreparation(renewedPreparation(),scope,c).settled_by_exact_renewal,true);
 for(const wrong of [{settled_by_exact_renewal:'true'},{renewal_review_id:null},{settled_by_exact_payoff:true,payoff_review_id:id(20)},{gross_carrying_amount:'0.01'}])assert.throws(()=>elapsedCandidate({...renewedCandidate(),...wrong},scope));
 assert.throws(()=>elapsedPreparation({...renewedPreparation(),renewal_review_id:id(41)},scope,c));
 const root=new Element(),api=fixture(),request=api.request.bind(api);api.request=async(path,options={})=>{if(path.endsWith('/prepare-renewed')){api.writes.push({path,body:structuredClone(options.body)});return renewedPreparation();}if(path.includes('/loans/')&&!options.method)return renewedCandidate();return request(path,options);};
 await mountElapsedAssessments({root,api,session});await lookup(root);assert.equal(root.querySelector('[data-elapsed-inputs]'),null);const form=root.querySelector('[data-elapsed-renewed]');assert.ok(form);
 form.querySelector('[name="review_rationale"]').value=settledRationale;fire(form,'submit');await tick();assert.equal(api.writes.length,0);fire(root.querySelector('[data-confirm]'),'click');await tick();await tick();
 assert.deepEqual(api.writes[0].body,{expected_book_id:id(1),source_digest:digest,renewal_review_id:id(40),review_rationale:settledRationale,confirm:true});assert.match(root.textContent,/Zero old-segment exposure/);assert.ok(root.querySelector('[data-confirm-assessment]'));
});

test('payoff and cured Stage 2 preserve prior Stage 3 net interest and full unwind release',()=>{
 const c=elapsedCandidate({...settledCandidate(),prior_allowance:'600.00',credit_impaired_interest:impairedInterest()},scope);
 const p=elapsedPreparation({...settledPreparation(),prior_allowance:'600.00',allowance_delta:'-610.00',credit_impaired_interest:impairedInterest()},scope,c);
 assert.equal(p.credit_impaired_interest.allowance_unwind,'10.00');assert.equal(p.allowance_delta,'-610.00');
 assert.throws(()=>elapsedPreparation({...settledPreparation(),prior_allowance:'600.00',allowance_delta:'-600.00',credit_impaired_interest:impairedInterest()},scope,c));
 const cured=elapsedCandidate({...impairedCandidate(),eligible_credit_risk_review:{...retainedRisk(),recovery_label:'cured'}},scope);
 const recovered=elapsedPreparation({...impairedPreparation(),stage_label:'stage_2_lifetime',default_label:false,loss_basis:'contractual_cash_shortfall'},scope,cured);
 assert.equal(recovered.credit_impaired_interest.net_interest,'5.10');assert.equal(recovered.gross_carrying_amount,undefined);
 const first={basis:'gross_before_initial_impaired_cutoff',opening_assessment_id:null,opening_cutoff_date:null,impairment_boundary_date:'2026-09-30',gross_interest:'15.10',net_interest:'15.10',allowance_unwind:'0.00'};
 const initial=elapsedCandidate({...impairedCandidate(),credit_impaired_interest:first},scope);
 assert.equal(elapsedPreparation({...impairedPreparation(),credit_impaired_interest:first,allowance_delta:'-196.00'},scope,initial).credit_impaired_interest.opening_assessment_id,null);
});

const retainedRisk=()=>({id:71,stage_label:'stage_2_lifetime',default_label:false,recovery_label:'none',write_off_label:'none',reviewed_at:'2026-09-30T08:00:00+00:00',as_of_date:'2026-09-30',evidence_reference:'Dated borrower credit review',primary_evidence_basis:'verified_source_document'});
test('eligible retained risk review is exact to the cutoff and strips private label evidence',()=>{
 const risk={...retainedRisk(),private_origin:'PRIVATE'};
 const out=elapsedCandidate({...candidate(),eligible_credit_risk_review:risk},scope);
 assert.deepEqual(out.eligible_credit_risk_review,retainedRisk());
 assert.doesNotMatch(JSON.stringify(out),/PRIVATE/);
 for(const wrong of [{id:'71'},{id:0},{as_of_date:'2026-10-05'},{stage_label:'unknown_stage'},{default_label:'false'},{recovery_label:'invented_cure'},{write_off_label:'executed'},{reviewed_at:'2026-10-05'}])assert.throws(()=>elapsedCandidate({...candidate(),eligible_credit_risk_review:{...risk,...wrong}},scope));
});
const riskPreparation=()=>({...preparation(),policy_version:'historical_native_lifetime_cash_shortfall_v1',credit_risk_review_id:71,stage_label:'stage_2_lifetime',default_label:false,loss_horizon:'lifetime',loss_basis:'contractual_cash_shortfall',review_inputs:{credit_risk_review_id:71,scenarios:inputs().scenarios,review_rationale:inputs().review_rationale}});
test('lifetime preparation binds the retained review and never silently becomes Stage 1',()=>{
 const c=elapsedCandidate({...candidate(),eligible_credit_risk_review:retainedRisk()},scope);
 const out=elapsedPreparation(riskPreparation(),scope,c);
 assert.equal(out.credit_risk_review_id,71);assert.equal(out.loss_horizon,'lifetime');assert.deepEqual(out.review_inputs,riskPreparation().review_inputs);
 for(const wrong of [{credit_risk_review_id:72},{default_label:true},{stage_label:'stage_3_credit_impaired'},{loss_horizon:'12_month'}])assert.throws(()=>elapsedPreparation({...riskPreparation(),...wrong},scope,c));
 assert.throws(()=>elapsedPreparation(preparation(),scope,c));
 assert.throws(()=>elapsedPreparation({...riskPreparation(),review_inputs:{...riskPreparation().review_inputs,credit_risk_review_id:72}},scope,c));
});
const impairedInterest=()=>({basis:'original_eir_on_reviewed_net_carrying',opening_assessment_id:id(30),opening_cutoff_date:'2026-09-28',impairment_boundary_date:'2026-09-28',gross_interest:'15.10',net_interest:'5.10',allowance_unwind:'10.00'});
test('explicit retained Stage 1 review keeps its separate 12-month policy and cannot become lifetime',()=>{
 const c=elapsedCandidate({...candidate(),days_past_due:35,eligible_credit_risk_review:{...retainedRisk(),stage_label:'stage_1_12_month'}},scope);
 const p={...riskPreparation(),policy_version:'historical_native_reviewed_12_month_cash_shortfall_v1',stage_label:'stage_1_12_month',loss_horizon:'12_month'};
 assert.equal(elapsedPreparation(p,scope,c).loss_horizon,'12_month');
 assert.throws(()=>elapsedPreparation({...p,policy_version:'historical_native_lifetime_cash_shortfall_v1',loss_horizon:'lifetime'},scope,c));
 assert.throws(()=>elapsedPreparation(preparation(),scope,c));
});
const impairedCandidate=()=>({...candidate(),gross_carrying_amount:'515.10',prior_allowance:'600.00',eir:{cumulative_interest:'15.10',prior_recognized_interest:'10.00',incremental_interest:'5.10'},eligible_credit_risk_review:{...retainedRisk(),stage_label:'stage_3_credit_impaired',default_label:true},credit_impaired_interest:impairedInterest()});
const impairedPreparation=()=>({...riskPreparation(),stage_label:'stage_3_credit_impaired',default_label:true,loss_basis:'gross_carrying_less_expected_pv',gross_carrying_amount:'515.10',expected_cash_present_value:'111.10',weighted_expected_cash_present_value_raw:'111.10',currency_rounding_adjustment:'0.00',ecl_amount:'404.00',prior_allowance:'600.00',allowance_delta:'-206.00',cumulative_interest:'15.10',incremental_interest:'5.10',credit_impaired_interest:impairedInterest()});
const signedInterest=()=>({...impairedInterest(),gross_interest:'1.63',net_interest:'1.64',allowance_unwind:'-0.01',currency_rounding_adjustment:'-0.01'});
const signedCandidate=()=>({...impairedCandidate(),gross_carrying_amount:'1008.16',prior_allowance:'0.01',eir:{cumulative_interest:'8.16',prior_recognized_interest:'6.53',incremental_interest:'1.63'},credit_impaired_interest:signedInterest()});
const signedPreparation=()=>({...impairedPreparation(),gross_carrying_amount:'1008.16',prior_allowance:'0.01',expected_cash_present_value:'1008.15',weighted_expected_cash_present_value_raw:'1008.15',ecl_amount:'0.01',allowance_delta:'0.01',cumulative_interest:'8.16',incremental_interest:'1.63',credit_impaired_interest:signedInterest()});
test('cent rounding preserves source gross, direct net and signed reconciliation with disclosed currency adjustment',()=>{
 const c=elapsedCandidate(signedCandidate(),scope),p=elapsedPreparation(signedPreparation(),scope,c);assert.deepEqual(c.credit_impaired_interest,signedInterest());assert.equal(p.allowance_delta,'0.01');assert.equal(p.credit_impaired_interest.currency_rounding_adjustment,'-0.01');
 for(const patch of [{allowance_unwind:'-0.02'},{allowance_unwind:-0.01},{allowance_unwind:'-10000000000000000.00'},{currency_rounding_adjustment:null},{currency_rounding_adjustment:'0.00'},{currency_rounding_adjustment:'1.64'},{gross_interest:'-0.01'},{net_interest:'-0.01'}])assert.throws(()=>elapsedCandidate({...signedCandidate(),credit_impaired_interest:{...signedInterest(),...patch}},scope));
 const absent=signedInterest();delete absent.currency_rounding_adjustment;assert.throws(()=>elapsedCandidate({...signedCandidate(),credit_impaired_interest:absent},scope));
 for(const patch of [{allowance_delta:'-0.01'},{prior_allowance:'-0.01'},{ecl_amount:'-0.01'},{credit_impaired_interest:{...signedInterest(),currency_rounding_adjustment:'-0.02'}}])assert.throws(()=>elapsedPreparation({...signedPreparation(),...patch},scope,c));
});
test('signed source interest review displays reconciliation and its currency rounding separately',async()=>{
 const root=new Element(),api=fixture(),request=api.request.bind(api);api.request=(path,options={})=>path.includes('/loans/')&&!options.method?Promise.resolve({...signedCandidate(),preparation:signedPreparation()}):request(path,options);
 await mountElapsedAssessments({root,api,session});await lookup(root);
 assert.match(root.textContent,/Gross\/net allowance reconciliation/);assert.match(root.textContent,/Interest currency rounding adjustment/);assert.match(root.textContent,/1.64/);assert.match(root.textContent,/-0.01/);assert.ok(root.querySelector('[data-confirm-assessment]'));
});
test('renewal opening interest retains distinct provenance and rejects mixed or future boundaries',async()=>{
 const interest={...impairedInterest(),opening_assessment_id:null,opening_renewal_review_id:id(41)};
 const raw={...impairedCandidate(),credit_impaired_interest:interest},p={...impairedPreparation(),credit_impaired_interest:interest};
 const c=elapsedCandidate(raw,scope);assert.equal(c.credit_impaired_interest.opening_renewal_review_id,id(41));assert.equal(elapsedPreparation(p,scope,c).credit_impaired_interest.opening_assessment_id,null);
 for(const wrong of [{opening_assessment_id:id(30)},{opening_renewal_review_id:null},{opening_cutoff_date:'2026-10-01',impairment_boundary_date:'2026-10-01'},{basis:'gross_before_initial_impaired_cutoff'}])assert.throws(()=>elapsedCandidate({...raw,credit_impaired_interest:{...interest,...wrong}},scope));
 assert.throws(()=>elapsedPreparation({...p,credit_impaired_interest:{...interest,opening_renewal_review_id:id(42)}},scope,c));
 const root=new Element(),api=fixture(),request=api.request.bind(api);api.request=(path,options={})=>path.includes('/loans/')&&!options.method?Promise.resolve({...raw,preparation:p}):request(path,options);
 await mountElapsedAssessments({root,api,session});await lookup(root);assert.match(root.textContent,/Opening renewal review/);assert.doesNotMatch(root.textContent,/Opening assessment reference/);
});
test('retained stage controls loss basis independently from default and cash recovery labels',()=>{
 const stage2=elapsedCandidate({...candidate(),eligible_credit_risk_review:{...retainedRisk(),default_label:true,recovery_label:'cash_recovery_observed'}},scope);
 assert.equal(elapsedPreparation({...riskPreparation(),default_label:true},scope,stage2).loss_basis,'contractual_cash_shortfall');
 const stage3=elapsedCandidate({...impairedCandidate(),eligible_credit_risk_review:{...retainedRisk(),stage_label:'stage_3_credit_impaired',default_label:false,write_off_label:'supported_no_reasonable_expectation_of_recovery'}},scope);
 assert.equal(elapsedPreparation({...impairedPreparation(),default_label:false},scope,stage3).loss_basis,'gross_carrying_less_expected_pv');
 assert.throws(()=>elapsedCandidate({...candidate(),eligible_credit_risk_review:{...retainedRisk(),stage_label:'stage_1_12_month',default_label:true}},scope));
 assert.throws(()=>elapsedPreparation({...impairedPreparation(),default_label:'false'},scope,stage3));
});
test('Stage 3 projection verifies gross-minus-expected-PV loss and exactly one unwind',()=>{
 const raw=impairedCandidate();raw.credit_impaired_interest.private_chain='PRIVATE';const c=elapsedCandidate(raw,scope);
 const p=elapsedPreparation(impairedPreparation(),scope,c);assert.equal(p.ecl_amount,'404.00');assert.equal(p.allowance_delta,'-206.00');assert.equal(p.credit_impaired_interest.net_interest,'5.10');assert.doesNotMatch(JSON.stringify(c),/PRIVATE/);
 for(const wrong of [{loss_basis:'contractual_cash_shortfall'},{expected_cash_present_value:'110.00'},{allowance_delta:'-196.00'},{credit_impaired_interest:{...impairedInterest(),allowance_unwind:'9.99'}}])assert.throws(()=>elapsedPreparation({...impairedPreparation(),...wrong},scope,c));
 const zero={...impairedPreparation(),expected_cash_present_value:'0.00',weighted_expected_cash_present_value_raw:'0.00',currency_rounding_adjustment:'0.00',ecl_amount:'515.10',allowance_delta:'-94.90'};assert.equal(elapsedPreparation(zero,scope,c).ecl_amount,c.gross_carrying_amount);
 for(const wrong of [{opening_assessment_id:null},{opening_cutoff_date:'2026-10-01'},{impairment_boundary_date:'2026-09-27'},{basis:'guessed_prior_measurement'}])assert.throws(()=>elapsedCandidate({...impairedCandidate(),credit_impaired_interest:{...impairedInterest(),...wrong}},scope));
});
test('recovered impaired assessment displays net revenue separately from gross tail and impairment adjustment',async()=>{
 const root=new Element(),api=fixture(),request=api.request.bind(api);
 api.request=(path,options={})=>path.includes('/loans/')&&!options.method?Promise.resolve({...impairedCandidate(),preparation:impairedPreparation()}):request(path,options);
 await mountElapsedAssessments({root,api,session});await lookup(root);
 assert.match(root.textContent,/Stage 3 credit-impaired/);assert.match(root.textContent,/Period net interest revenue/);assert.match(root.textContent,/Unposted gross interest tail/);assert.match(root.textContent,/Impairment adjustment/);assert.match(root.textContent,/Total allowance balance change/);assert.match(root.textContent,/-196.00/);assert.match(root.textContent,/-206.00/);
 assert.match(root.textContent,/Expected cash present value/);assert.ok(root.querySelector('[data-confirm-assessment]'));
});
test('Stage 2 requires explicit retained review selection and prepares lifetime inputs separately',async()=>{
 const root=new Element(),api=fixture(),request=api.request.bind(api);
 api.request=async(path,options={})=>{if(path.endsWith('/prepare-risk')){api.writes.push({path,body:structuredClone(options.body)});return riskPreparation();}if(path.includes('/loans/')&&!options.method)return {...candidate(),eligible_credit_risk_review:retainedRisk()};return request(path,options);};
 await mountElapsedAssessments({root,api,session});await lookup(root);
 assert.ok(root.querySelector('[name="credit_risk_review_id"]'));assert.equal(root.querySelector('[name="review_note"]'),null);
 for(let i=0;i<2;i++){const pick=root.querySelector(`[data-evidence-choice="${i}"]`);pick.value=id(10+i);fire(pick,'change');}
 const f=root.querySelector('[data-elapsed-inputs]'),x=inputs();f.querySelector('[name="review_rationale"]').value=x.review_rationale;
 x.scenarios.forEach((s,i)=>{for(const k of ['scenario_key','probability','evidence_reference','management_rationale'])f.querySelector(`[name="s${i}_${k}"]`).value=s[k];f.querySelector(`[name="s${i}_c0_cash_date"]`).value=s.expected_cash_flows[0].cash_date;f.querySelector(`[name="s${i}_c0_amount"]`).value=s.expected_cash_flows[0].amount;});
 fire(f,'submit');await tick();assert.equal(root.querySelector('[data-confirm]'),null);assert.equal(api.writes.length,0);
 f.querySelector('[name="credit_risk_review_id"]').value='71';fire(f,'submit');await tick();assert.match(root.textContent,/Stage 2.*lifetime/i);
 fire(root.querySelector('[data-confirm]'),'click');await tick();await tick();
 assert.deepEqual(api.writes[0].body,{expected_book_id:id(1),source_digest:digest,credit_risk_review_id:71,scenarios:x.scenarios,review_rationale:x.review_rationale,confirm:true});
 assert.ok(root.querySelector('[data-confirm-assessment]'));assert.match(root.textContent,/Retained credit-risk review/);
});

test('settled cutoff requires exact payoff identity, zero carrying and retained zero-ECL policy',()=>{
 const c=elapsedCandidate(settledCandidate(),scope);assert.equal(c.settled_by_exact_payoff,true);
 assert.equal(elapsedPreparation(settledPreparation(),scope,c).review_inputs.payoff_review_id,id(20));
 for(const wrong of [{gross_carrying_amount:'0.01'},{payoff_review_id:null},{settled_by_exact_payoff:'true'}])assert.throws(()=>elapsedCandidate({...settledCandidate(),...wrong},scope));
 for(const wrong of [{ecl_amount:'0.01',allowance_delta:'-3.99'},{scenario_count:2},{payoff_review_id:id(21)}])assert.throws(()=>elapsedPreparation({...settledPreparation(),...wrong},scope,c));
});

test('settled cutoff reviews payoff rationale without inventing scenarios then separately confirms posting',async()=>{
 const root=new Element(),api=fixture(),request=api.request.bind(api);
 api.request=async(path,options={})=>{if(path.endsWith('/prepare-settled')){api.writes.push({path,body:structuredClone(options.body)});return settledPreparation();}if(path.includes('/loans/')&&!options.method)return settledCandidate();return request(path,options);};
 await mountElapsedAssessments({root,api,session});await lookup(root);
 assert.equal(root.querySelector('[data-elapsed-inputs]'),null);assert.match(root.textContent,/exact posted payoff/i);
 const form=root.querySelector('[data-elapsed-settled]');form.querySelector('[name="review_rationale"]').value=settledRationale;fire(form,'submit');await tick();assert.equal(api.writes.length,0);
 fire(root.querySelector('[data-confirm]'),'click');await tick();await tick();
 assert.deepEqual(api.writes[0].body,{expected_book_id:id(1),source_digest:digest,payoff_review_id:id(20),review_rationale:settledRationale,confirm:true});
 assert.match(root.textContent,/-4.00/);assert.equal(root.querySelector('[data-elapsed-inputs]'),null);
 fire(root.querySelector('[data-confirm-assessment]'),'click');await tick();fire(root.querySelector('[data-confirm]'),'click');await tick();await tick();
 assert.equal(api.writes.length,2);assert.match(root.textContent,/Assessment posted/);
});
test('historical projections reject scope and money mismatches and strip private snapshots',()=>{const v=candidate();v.snapshot={secret:'PRIVATE'};v.eir.private='PRIVATE';assert.doesNotMatch(JSON.stringify(elapsedCandidate(v,scope)),/PRIVATE/);assert.throws(()=>elapsedCandidate(v,{...scope,bookId:id(99)}));assert.throws(()=>elapsedPreparation({...preparation(),allowance_delta:'0.50'},scope,v));assert.throws(()=>elapsedPreparation({...preparation(),ecl_amount:3.5},scope,v));});
test('scenario arithmetic stays decimal-exact and rejects malformed dates, duplicates and unsupported probabilities',()=>{const x=inputs();const out=elapsedInputs(x,'2026-09-30');assert.equal(out.scenarios[0].probability,'0.7');assert.equal(out.scenarios[0].expected_cash_flows[0].amount,'5000.00');for(const bad of [0.7,'0.7000000000001','1e-1'])assert.throws(()=>elapsedInputs({...x,scenarios:[{...x.scenarios[0],probability:bad},x.scenarios[1]]},'2026-09-30'));x.scenarios[0].expected_cash_flows[0].cash_date='2026-02-30';assert.throws(()=>elapsedInputs(x,'2026-09-30'));});
test('prepare retains exact scenarios; confirmation separately shows cutoff, calculation time and EIR/ECL amounts',async()=>{const root=new Element(),api=fixture();await mountElapsedAssessments({root,api,session});await lookup(root);assert.match(root.textContent,/2026-09-30/);fire(fill(root),'submit');await tick();assert.equal(api.writes.length,0);fire(root.querySelector('[data-confirm]'),'click');await tick();await tick();assert.equal(api.writes.length,1);assert.deepEqual(api.writes[0].body.scenarios,inputs().scenarios);assert.match(root.textContent,/2026-10-05T08:12:00/);assert.match(root.textContent,/-0.50/);fire(root.querySelector('[data-confirm-assessment]'),'click');await tick();assert.equal(api.writes.length,1);fire(root.querySelector('[data-confirm]'),'click');await tick();await tick();assert.deepEqual(api.writes[1].body,{expected_book_id:id(1),confirmation_digest:'b'.repeat(64),confirm:true});assert.match(root.textContent,/Assessment posted/);});
test('unknown response permits only unchanged retry and scope change removes private inputs',async()=>{const root=new Element(),api=fixture(),attempts=[];let fail=true,current=structuredClone(session);const request=api.request.bind(api);api.request=async(path,options={})=>{if(options.method==='POST'){attempts.push(structuredClone(options.body));if(fail)throw Error('Lost response');}return request(path,options);};await mountElapsedAssessments({root,api,session,getSession:()=>current});await lookup(root);fire(fill(root),'submit');await tick();fire(root.querySelector('[data-confirm]'),'click');await tick();await tick();assert.equal(root.querySelector('[data-elapsed-inputs]'),null);fail=false;fire(root.querySelector('[data-retry]'),'click');await tick();await tick();assert.deepEqual(attempts[0],attempts[1]);current={...current,access_token:'changed'};fire(root.querySelector('[data-confirm-assessment]'),'click');await tick();assert.doesNotMatch(root.textContent,/Forecast|Owner books|62.58/);assert.equal(root.querySelector('[data-confirm]'),null);});
test('blocked and view-only candidates cannot prepare; abort ignores delayed private results',async()=>{const root=new Element(),api=fixture();await mountElapsedAssessments({root,api,session:{...session,permissions:['accounting.view']}});await lookup(root);assert.equal(root.querySelector('[data-elapsed-inputs]'),null);const controller=new AbortController();let finish;const request=api.request.bind(api);api.request=(p,o)=>p.includes('/loans/')?new Promise(r=>{finish=r;}):request(p,o);await mountElapsedAssessments({root,api,session,signal:controller.signal});const f=root.querySelector('[data-elapsed-lookup]');f.querySelector('[name="period_id"]').value=id(3);f.querySelector('[name="loan_id"]').value=id(4);fire(f,'submit');await tick();controller.abort();finish(candidate());await tick();assert.equal(root.textContent,'');});

test('recovered preparations include exact retained review inputs and reject altered risk policy',()=>{const v=candidate();v.preparation=preparation();v.preparation.review_inputs.risk_review.private='PRIVATE';const p=elapsedCandidate(v,scope);assert.doesNotMatch(JSON.stringify(p),/PRIVATE/);assert.equal(p.preparation.review_inputs.scenarios[0].expected_cash_flows[0].amount,'5000.00');v.preparation.review_inputs.risk_review.default_label=true;assert.throws(()=>elapsedCandidate(v,scope));});

test('failed preflight retains the reviewed request without issuing a financial write',async()=>{const root=new Element(),api=fixture();let failBook=false;const request=api.request.bind(api);api.request=(p,o)=>{if(p.endsWith('/book')&&failBook)throw Error('Book read unavailable');return request(p,o);};await mountElapsedAssessments({root,api,session});await lookup(root);fire(fill(root),'submit');await tick();failBook=true;fire(root.querySelector('[data-confirm]'),'click');await tick();await tick();assert.equal(api.writes.length,0);assert.ok(root.querySelector('[data-retry]'));failBook=false;fire(root.querySelector('[data-retry]'),'click');await tick();await tick();assert.equal(api.writes.length,1);assert.ok(root.querySelector('[data-confirm-assessment]'));});

test('mismatched retained scenario response cannot reach posting confirmation',async()=>{const root=new Element(),api=fixture(),request=api.request.bind(api);api.request=async(p,o)=>{const value=await request(p,o);if(p.endsWith('/prepare'))value.review_inputs.scenarios[0].expected_cash_flows[0].amount='5001.00';return value;};await mountElapsedAssessments({root,api,session});await lookup(root);fire(fill(root),'submit');await tick();fire(root.querySelector('[data-confirm]'),'click');await tick();await tick();assert.match(root.textContent,/differ from the reviewed request/);assert.equal(root.querySelector('[data-confirm-assessment]'),null);assert.ok(root.querySelector('[data-retry]'));});
