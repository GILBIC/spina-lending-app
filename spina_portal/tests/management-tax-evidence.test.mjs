import test from 'node:test';
import assert from 'node:assert/strict';
import {setImmediate, setTimeout} from 'node:timers/promises';
import {Element, fire} from './helpers/dom.mjs';

const module=await import('../assets/management-tax-evidence.js').catch(()=>({}));
const ID='10000000-0000-4000-8000-000000000001', OTHER='20000000-0000-4000-8000-000000000002', HASH='b'.repeat(64);
const tax='documentary_stamp_tax';
const suffixes=['rule','dst','percentage','return','payment','adjustment','additional_amendment','additional_payment','recoverable_refund','recoverable_credit'];
const session={user:{roles:['management'],permissions:suffixes.map(s=>`accounting.tax.${s}_evidence.record`)}};
const permissions=Object.fromEntries(suffixes.map(s=>[`${s.replace('recoverable_','')}_evidence_record`,true]));
permissions.amendment_evidence_record=true;
const common={evidence_reference:'Archive/filing.pdf',evidence_digest:HASH,evidence_note:'Reviewed against the retained signed original.'};
const candidate={tax_type:tax,posting_id:ID,tax_due:'90071992547409.93',recognition_date:'2026-09-20',entry_number:'TAX-1'};
const second={...candidate,posting_id:OTHER,tax_due:'0.08'};
const queue={return_liability_candidates:[candidate,second],items:[],permissions,automatic_source_posting:false};
const returnInput={...common,tax_type:tax,return_period_start:'2026-09-01',return_period_end:'2026-09-30',filing_date:'2026-10-01',return_reference:'September filing',liability_posting_ids:[ID,OTHER]};
function build(kind,data,row,input){assert.equal(typeof module.buildTaxEvidenceAction,'function');return module.buildTaxEvidenceAction(kind,data,row,session,input,ID);}

test('return evidence selects exact server liabilities and sums cents without numeric rounding',()=>{
 const action=build('return',queue,null,returnInput);
 assert.ok(action.path.endsWith('/settlements/returns'));
 assert.deepEqual(action.body,{idempotency_key:ID,...returnInput,declared_tax_due:'90071992547410.01'});
 assert.equal(action.body.confirm,undefined);
 for(const input of [{...returnInput,liability_posting_ids:[ID,ID]},{...returnInput,liability_posting_ids:[]},{...returnInput,tax_type:'percentage_tax_lending'},{...returnInput,return_period_start:'2026-09-21'},{...returnInput,filing_date:'2026-09-29'}])assert.throws(()=>build('return',queue,null,input));
 assert.throws(()=>build('return',{...queue,return_liability_candidates:[candidate]},null,returnInput));
});

test('rule and source evidence retain reviewed facts and immutable correction links',()=>{
 const rule={id:OTHER,tax_type:tax,rule_key:'Reviewed DST',effective_from:'2026-01-01',effective_to:null,treatment:'taxable',rate:'0.01'};
 const row={loan_id:ID,disbursement_event_id:OTHER,issue_date:'2026-09-20',protected_issue_price:'90071992547409.93',protected_term_days:30,evidence_id:ID,automatic_source_posting:false,tax_posting_enabled:false};
 const data={permissions,automatic_source_posting:false,tax_posting_enabled:false,rules:[rule],dst:[row],percentage_tax:[]};
 const action=build('dst',data,row,{rule_evidence_id:OTHER,expected_tax_due:'10.12',instrument_reference:'Archive/instrument',instrument_digest:HASH,calculation_reference:'Archive/calculation',calculation_digest:HASH,management_rationale:common.evidence_note});
 assert.equal(action.body.expected_issue_price,'90071992547409.93');assert.equal(action.body.expected_term_days,30);assert.equal(action.body.supersedes_evidence_id,ID);assert.equal(action.body.confirm,true);
 assert.throws(()=>build('dst',data,{...row},{}));
 const input={...rule,legal_source:'Published authority',legal_reference:'Article 1',retained_source_reference:'Archive/rule',evidence_digest:HASH,management_rationale:common.evidence_note,maturity_max_days:'',supersedes_rule_id:OTHER};
 const correction=build('rule',data,rule,input);assert.equal(correction.body.supersedes_rule_id,OTHER);assert.equal(correction.body.rate,'0.01');assert.equal(correction.body.id,undefined);
 assert.throws(()=>build('rule',data,rule,{...input,rate:'1.0000000001'}));
});

test('percentage evidence reconciles reviewed allocation to protected cash exactly',()=>{
 const row={transaction_id:ID,source_cash_amount:'100.01',collection_date:'2026-09-20',is_voided:false,evidence_id:null,automatic_source_posting:false,tax_posting_enabled:false};
 const rule={id:OTHER,tax_type:'percentage_tax_lending',effective_from:'2026-01-01',effective_to:null};
 const data={permissions,automatic_source_posting:false,tax_posting_enabled:false,rules:[rule],percentage_tax:[row]};
 const input={rule_evidence_id:OTHER,taxable_lending_receipt_amount:'10.01',principal_receipt_amount:'90.00',expected_tax_due:'0.30',allocation_reference:'Archive/allocation',allocation_digest:HASH,management_rationale:common.evidence_note};
 assert.equal(build('percentage',data,row,input).body.expected_source_cash_amount,'100.01');
 assert.throws(()=>build('percentage',data,row,{...input,principal_receipt_amount:'90.01'}));
 row.is_voided=true;assert.throws(()=>build('percentage',data,row,input));
});

test('all retained follow-on evidence uses selected server coordinates and exact full payment',()=>{
 const row={tax_return_id:ID,tax_type:tax,declared_tax_due:'90071992547409.93',filing_date:'2026-10-01',settlement_status:'return_recorded_awaiting_payment',payment_evidence_id:null,automatic_source_posting:false};
 const data={...queue,items:[row]};
 const input={...common,payment_date:'2026-10-02',cash_account_system_key:'cash_office',payment_reference:'Receipt 1'};
 assert.equal(build('payment',data,row,input).body.payment_amount,row.declared_tax_due);
 assert.throws(()=>build('payment',data,row,{...input,payment_date:'2026-09-30'}));
 row.payment_evidence_id=OTHER;assert.throws(()=>build('payment',data,row,input));
 const adjustment={tax_liability_posting_id:ID,replacement_evidence_id:OTHER,adjustment_kind:'reverse_unsettled_liability',fiscal_period_start:'2026-01-01',fiscal_period_end:'2026-12-31'};
 const correction=build('adjustment',{...queue,adjustment_candidates:[adjustment]},adjustment,{...common,adjustment_date:'2026-09-29',adjustment_reference:'Correction 1'});
 assert.equal(correction.body.replacement_evidence_id,OTHER);assert.equal(correction.body.adjustment_kind,adjustment.adjustment_kind);
 const additional={tax_return_id:ID,tax_liability_posting_id:OTHER,replacement_evidence_id:ID,filing_date:'2026-10-01',recognition_date:'2026-09-20'};
 assert.equal(build('additional',{...queue,amendment_candidates:[additional]},additional,{...common,amendment_basis:'amended_return',amendment_date:'2026-10-02',amendment_reference:'Amendment 1'}).body.recognition_date,'2026-09-20');
 const extra={amendment_evidence_id:ID,amendment_status:'additional_liability_posted_awaiting_payment',additional_liability_posting_id:OTHER,liability_confirmation_digest:HASH,additional_payment_evidence_id:null,amendment_date:'2026-10-01',payment_required_amount:'123.45',automatic_source_posting:false};
 assert.equal(build('additional_payment',{...queue,items:[extra]},extra,input).body.payment_amount,'123.45');
 const refund={adjustment_posting_id:ID,minimum_refund_date:'2026-10-01'};
 assert.deepEqual(build('refund',{...queue,refund_candidates:[refund]},refund,{refund_date:'2026-10-02',cash_account_code:'1030',refund_reference:'Receipt',authority_reference:'Authority',evidence_digest:HASH,evidence_note:common.evidence_note}).body,{idempotency_key:ID,adjustment_posting_id:ID,refund_date:'2026-10-02',cash_account_code:'1030',refund_reference:'Receipt',authority_reference:'Authority',evidence_digest:HASH,evidence_note:common.evidence_note});
 const credit={adjustment_posting_id:ID,target_tax_return_id:OTHER,minimum_application_date:'2026-10-01'};
 assert.equal(build('credit',{...queue,credit_candidates:[credit]},credit,{application_date:'2026-10-02',application_reference:'Credit 1',authority_reference:'Authority',evidence_digest:HASH,evidence_note:common.evidence_note}).body.target_tax_return_id,OTHER);
});

test('both Management permission and current server capability are required',()=>{
 assert.equal(typeof module.buildTaxEvidenceAction,'function');
 for(const [data,actor] of [[{...queue,permissions:{}},session],[queue,{user:{roles:['employee'],permissions:session.user.permissions}}],[queue,{user:{roles:['management'],permissions:[]}}],[{...queue,automatic_source_posting:true},session]])assert.throws(()=>module.buildTaxEvidenceAction('return',data,null,actor,returnInput,ID));
});

function fill(root,values){for(const [key,value] of Object.entries(values)){const field=root.querySelector(`[name="${key}"]`);if(field)field.value=value;}}
test('review is readable, double submission and uncertain save lock until authoritative reload',async()=>{
 assert.equal(typeof module.mountTaxEvidence,'function');
 const root=new Element(),calls=[];let finishReview,finishPost,review;
 const api={request:async(path,options={})=>{calls.push({path,options});return options.method==='POST'?new Promise(resolve=>{finishPost=resolve;}):structuredClone(queue);}};
 const dispose=await module.mountTaxEvidence({root,api,session,initialView:'return',confirm:message=>{review=message;return new Promise(resolve=>{finishReview=resolve;});}});
 fill(root,returnInput);for(const box of root.querySelectorAll('[data-liability]'))box.checked=true;
 const form=root.querySelector('[data-evidence-form]');assert.ok(form);fire(form,'submit');fire(form,'submit');await setImmediate();
 assert.match(review,/90071992547410\.01|90,071,992,547,410\.01/);assert.match(review,/September filing/);assert.match(review,/TAX-1/);
 finishReview(true);await setImmediate();assert.equal(calls.filter(c=>c.options.method==='POST').length,1);
 fire(form,'submit');await setImmediate();assert.equal(calls.filter(c=>c.options.method==='POST').length,1);
 finishPost(null);await setImmediate();assert.match(root.textContent,/uncertain/i);fire(form,'submit');await setImmediate();assert.equal(calls.filter(c=>c.options.method==='POST').length,1);
 fire(root.querySelector('[data-evidence-reload]'),'click');await setImmediate();assert.ok(root.querySelector('[data-evidence-form]'));dispose();fire(form,'submit');await setImmediate();assert.equal(root.textContent,'');
});

test('aborted or replaced evidence workspaces ignore late reads',async()=>{
 const root=new Element(),controller=new AbortController();let finish;
 const mounting=module.mountTaxEvidence({root,api:{request:()=>new Promise(resolve=>{finish=resolve;})},session,signal:controller.signal,initialView:'return'});
 controller.abort();finish(queue);await mounting;assert.equal(root.textContent,'');
});

test('return form works with browser NodeLists instead of array-only DOM shortcuts',async()=>{
 const root=new Element(),calls=[];
 const dispose=await module.mountTaxEvidence({root,api:{request:async(path,options={})=>{calls.push({path,options});return structuredClone(queue);}},session,initialView:'return',confirm:()=>true});
 fill(root,returnInput);for(const box of root.querySelectorAll('[data-liability]'))box.checked=true;
 const form=root.querySelector('[data-evidence-form]'),query=form.querySelectorAll.bind(form);
 form.querySelectorAll=selector=>{const values=query(selector);return Object.assign(Object.create({[Symbol.iterator]:function*(){yield* values;}}),Object.fromEntries(values.map((value,index)=>[index,value])),{length:values.length});};
 fire(form,'submit');await setImmediate();assert.equal(calls.filter(c=>c.options.method==='POST').length,1);dispose();
});

test('checksum is derived from the retained file locally and late hashing cannot revive an aborted form',async()=>{
 const root=new Element(),controller=new AbortController(),calls=[];
 const dispose=await module.mountTaxEvidence({root,api:{request:async(path,options={})=>{calls.push({path,options});return structuredClone(queue);}},session,signal:controller.signal,initialView:'return'});
 const file=root.querySelector('[data-evidence-file="evidence_digest"]'),checksum=root.querySelector('[name="evidence_digest"]');
 file.files=[{name:'retained.txt',size:3,arrayBuffer:async()=>new TextEncoder().encode('abc').buffer}];fire(file,'change');
 for(let attempt=0;attempt<100&&!checksum.value;attempt++)await setTimeout(5);
 assert.equal(checksum.value,'ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad');
 let finish;file.files=[{name:'later.txt',size:3,arrayBuffer:()=>new Promise(resolve=>{finish=resolve;})}];fire(file,'change');controller.abort();finish(new TextEncoder().encode('def').buffer);await setImmediate();await setImmediate();assert.equal(root.textContent,'');assert.equal(calls.filter(c=>c.options.method==='POST').length,0);dispose();
});

test('cancelling a review creates no write and a detached form cannot submit after navigation',async()=>{
 const root=new Element(),calls=[];
 const api={request:async(path,options={})=>{calls.push({path,options});return path.includes('settlements')?structuredClone(queue):{rules:[],dst:[],percentage_tax:[],permissions,automatic_source_posting:false,tax_posting_enabled:false};}};
 const dispose=await module.mountTaxEvidence({root,api,session,initialView:'return',confirm:()=>false});
 fill(root,returnInput);for(const box of root.querySelectorAll('[data-liability]'))box.checked=true;
 const form=root.querySelector('[data-evidence-form]');fire(form,'submit');await setImmediate();assert.equal(calls.filter(c=>c.options.method==='POST').length,0);
 fire(root.querySelector('[data-evidence-view="rule"]'),'click');await setImmediate();fire(form,'submit');await setImmediate();assert.equal(calls.filter(c=>c.options.method==='POST').length,0);assert.match(root.textContent,/New rule evidence/);dispose();
});

test('revoked access erases private facts and disables the retained form',async()=>{
 const root=new Element();let posts=0;
 const dispose=await module.mountTaxEvidence({root,api:{request:async(path,options={})=>{if(options.method==='POST'){posts++;throw Object.assign(new Error('Revoked'),{status:403});}return structuredClone(queue);}},session,initialView:'return',confirm:()=>true});
 fill(root,returnInput);for(const box of root.querySelectorAll('[data-liability]'))box.checked=true;
 const form=root.querySelector('[data-evidence-form]');fire(form,'submit');await setImmediate();
 assert.doesNotMatch(root.textContent,/TAX-1|90,071,992/);assert.match(root.textContent,/access|sign in/i);fire(form,'submit');await setImmediate();assert.equal(posts,1);dispose();
});

test('a permission change during confirmation cannot send retained evidence',async()=>{
 const root=new Element(),actor=structuredClone(session);let posts=0,finish;
 const dispose=await module.mountTaxEvidence({root,api:{request:async(path,options={})=>{if(options.method==='POST')posts++;return structuredClone(queue);}},session:actor,initialView:'return',confirm:()=>new Promise(resolve=>{finish=resolve;})});
 fill(root,returnInput);for(const box of root.querySelectorAll('[data-liability]'))box.checked=true;
 fire(root.querySelector('[data-evidence-form]'),'submit');actor.user.permissions=[];finish(true);await setImmediate();assert.equal(posts,0);dispose();
});

test('a confirmed receipt still requires an authoritative refresh before another write',async()=>{
 const root=new Element();let posts=0;
 const dispose=await module.mountTaxEvidence({root,api:{request:async(path,options={})=>{if(options.method==='POST'){posts++;return {item:{tax_return_id:ID,return_evidence_digest:HASH,return_reference:returnInput.return_reference,declared_tax_due:'90071992547410.01',automatic_source_posting:false}};}return structuredClone(queue);}},session,initialView:'return',confirm:()=>true});
 fill(root,returnInput);for(const box of root.querySelectorAll('[data-liability]'))box.checked=true;
 const form=root.querySelector('[data-evidence-form]');fire(form,'submit');await setImmediate();assert.match(root.textContent,/Evidence recorded/);assert.match(root.textContent,/Refresh/);fire(form,'submit');await setImmediate();assert.equal(posts,1);dispose();
});

test('loading more liabilities preserves typed return facts and only explicit selections across server pages',async()=>{
 const root=new Element(),calls=[];
 const rows=Array.from({length:201},(_,index)=>({...candidate,posting_id:`30000000-0000-4000-8000-${String(index+1).padStart(12,'0')}`,tax_due:'1.00'}));
 const dispose=await module.mountTaxEvidence({root,api:{request:async(path,options={})=>{calls.push({path,options});if(options.method==='POST')return null;return {...queue,return_liability_candidates:path.includes('offset=200')?rows.slice(200):rows.slice(0,200)};}},session,initialView:'return',confirm:()=>true});
 fill(root,returnInput);root.querySelector('[data-liability="0"]').checked=true;
 const more=root.querySelector('[data-evidence-more]');assert.ok(more);fire(more,'click');await setImmediate();
 assert.equal(root.querySelector('[name="return_reference"]').value,'September filing');
 assert.equal(root.querySelector('[data-liability="0"]').checked,true);assert.ok(!root.querySelector('[data-liability="200"]').checked);
 assert.equal(root.querySelector('[data-evidence-more]'),null);
 root.querySelector('[data-liability="200"]').checked=true;fire(root.querySelector('[data-evidence-form]'),'submit');await setImmediate();
 const post=calls.find(call=>call.options.method==='POST');assert.equal(post.options.body.declared_tax_due,'2.00');assert.deepEqual(post.options.body.liability_posting_ids,[rows[0].posting_id,rows[200].posting_id]);dispose();
});

test('empty evidence queues have no blank facts grid or inverted count',async()=>{
 const root=new Element();
 const dispose=await module.mountTaxEvidence({root,api:{request:async()=>({...queue,return_liability_candidates:[]})},session,initialView:'return'});
 assert.equal(root.querySelector('dl'),null);assert.match(root.textContent,/0 records/);assert.doesNotMatch(root.textContent,/1–0/);dispose();
});
