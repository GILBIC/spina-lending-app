import test from 'node:test';
import assert from 'node:assert/strict';
import {setImmediate} from 'node:timers/promises';
import {Element, fire} from './helpers/dom.mjs';

const module = await import('../assets/management-tax-ecl.js').catch(() => ({}));
const ID='10000000-0000-4000-8000-000000000001';
const HASH='b'.repeat(64);
const TOKEN='c'.repeat(64);
const session={user:{roles:['management'],permissions:['accounting.tax.liability.prepare','accounting.tax.liability.post','accounting.ecl.allowance.prepare','accounting.ecl.allowance.post']}};
const liability={evidence_id:ID,tax_type:'documentary_stamp_tax',loan_id:ID,tax_due:'90071992547409.93',evidence_digest:HASH,expense_account_code:'5100',tax_payable_account_code:'2100',recognition_date:'2026-09-29',fiscal_period_id:ID,accounting_status:'prepared_not_posted',protected_tax_liability_posting_enabled:true,automatic_source_posting:false};
const queue={items:[liability],permissions:{liability_prepare:true,liability_post:true},automatic_source_posting:false};

test('tax posting binds exact reviewed amount, date, accounts and evidence without numeric coercion',()=>{
 assert.equal(typeof module.buildTaxEclAction,'function');
 const action=module.buildTaxEclAction('liabilities','post',queue,liability,session,{},TOKEN);
 assert.equal(action.path,`/api/v1/management/financial-accounting/tax/liabilities/documentary_stamp_tax/${ID}/post`);
 assert.deepEqual(action.body,{confirm:true,confirmation_token:TOKEN,expected_evidence_digest:HASH,expected_tax_due:'90071992547409.93',expected_expense_account_code:'5100',expected_tax_payable_account_code:'2100',expected_posting_date:'2026-09-29',expected_fiscal_period_id:ID});
});

test('role, server permission, stale status and unsupported automatic posting all fail closed',()=>{
 assert.equal(typeof module.buildTaxEclAction,'function');
 for(const [data,row,actor] of [
  [queue,liability,{user:{roles:['employee'],permissions:session.user.permissions}}],
  [{...queue,permissions:{liability_post:false}},liability,session],
  [queue,{...liability,accounting_status:'posted'},session],
  [queue,{...liability,automatic_source_posting:true},session],
  [queue,{...liability,evidence_digest:null},session],
  [queue,{...liability,tax_due:90071992547409.94},session],
 ]) assert.throws(()=>module.buildTaxEclAction('liabilities','post',data,row,actor,{},TOKEN));
});

test('initial ECL preparation copies the exact measurement and never posts in the same request',()=>{
 const row={loan_id:ID,measurement_id:ID,calculation_digest:HASH,authoritative_ecl_amount:'400.25',posting_date:'2026-09-29',fiscal_period_id:ID,credit_loss_expense_account_id:ID,allowance_account_id:ID,prior_allowance_balance:'0.00',allowance_posting_status:'preparation_required',protected_allowance_action_ready:true,automatic_source_posting:false};
 const action=module.buildTaxEclAction('allowance','prepare',{prepare_permission:true,items:[row]},row,session,{},TOKEN);
 assert.ok(action.path.endsWith(`/${ID}/prepare`));
 assert.equal(action.body.expected_ecl_amount,'400.25');
 assert.equal(action.body.expected_calculation_digest,HASH);
 assert.equal(action.body.preparation_review_token,TOKEN);
 assert.equal(action.body.expected_prior_allowance_balance,'0.00');
 assert.throws(()=>module.buildTaxEclAction('allowance','post',{post_permission:true,items:[row]},row,session,{},TOKEN));
});

test('Web management can review a tax posting; uncertain completion blocks another write until authoritative refresh',async()=>{
 assert.equal(typeof module.mountManagementTaxEcl,'function');
 const root=new Element();const controller=new AbortController();const calls=[];let resolvePost;
 const api={request:async(path,options={})=>{calls.push({path,options});if(options.method==='POST')return new Promise(resolve=>{resolvePost=resolve;});return structuredClone(queue);}};
 const dispose=await module.mountManagementTaxEcl({root,api,session,signal:controller.signal,initialView:'liabilities',confirm:()=>true});
 const button=root.querySelector('[data-tax-action="post"]');assert.ok(button);
 fire(button,'click');await setImmediate();
 assert.equal(calls.filter(c=>c.options.method==='POST').length,1);
 fire(button,'click');await setImmediate();assert.equal(calls.filter(c=>c.options.method==='POST').length,1);
 resolvePost(null);await setImmediate();await setImmediate();
 assert.match(root.textContent,/uncertain|refresh/i);
 fire(button,'click');await setImmediate();assert.equal(calls.filter(c=>c.options.method==='POST').length,1);
 dispose();assert.equal(root.textContent,'');
});

test('an aborted mount never renders a late accounting response',async()=>{
 assert.equal(typeof module.mountManagementTaxEcl,'function');
 const root=new Element();const controller=new AbortController();let resolveRead;
 const promise=module.mountManagementTaxEcl({root,api:{request:()=>new Promise(resolve=>{resolveRead=resolve;})},session,signal:controller.signal,initialView:'liabilities'});
 controller.abort();resolveRead(queue);await promise;
 assert.equal(root.textContent,'');
});

test('revoked accounting access clears private records and disables retained handlers',async()=>{
 const root=new Element();let posts=0;
 const api={request:async(_path,options={})=>{if(options.method==='POST'){posts++;throw Object.assign(new Error('Access revoked'),{status:403});}return structuredClone({...queue,items:[{...liability,loan_number:'PRIVATE-LOAN-42'}]});}};
 const dispose=await module.mountManagementTaxEcl({root,api,session,confirm:()=>true});
 const oldButton=root.querySelector('[data-tax-action="post"]');
 assert.match(root.textContent,/PRIVATE-LOAN-42/);
 fire(oldButton,'click');await setImmediate();await setImmediate();
 assert.doesNotMatch(root.textContent,/PRIVATE-LOAN-42|90,071,992,547,409/);
 assert.match(root.textContent,/access|sign in/i);
 fire(oldButton,'click');await setImmediate();assert.equal(posts,1);
 dispose();
});

test('unlabelled liabilities identify the exact loan and evidence in the review',async()=>{
 const root=new Element();let review;
 const dispose=await module.mountManagementTaxEcl({root,api:{request:async()=>structuredClone(queue)},session,confirm:message=>{review=message;return false;}});
 assert.match(root.textContent,new RegExp(ID));
 fire(root.querySelector('[data-tax-action="post"]'),'click');await setImmediate();
 assert.match(review,new RegExp(`Loan Id: ${ID}`));
 assert.match(review,new RegExp(`Evidence Id: ${ID}`));
 dispose();
});

test('a delayed confirmation cannot post after the reviewed view changes',async()=>{
 const root=new Element();let resolveConfirm;let posts=0;
 const api={request:async(_path,options={})=>{if(options.method==='POST')posts++;return structuredClone(queue);}};
 const dispose=await module.mountManagementTaxEcl({root,api,session,confirm:()=>new Promise(resolve=>{resolveConfirm=resolve;})});
 fire(root.querySelector('[data-tax-action="post"]'),'click');await setImmediate();
 fire(root.querySelector('[data-tax-reload]'),'click');await setImmediate();
 resolveConfirm(true);await setImmediate();assert.equal(posts,0);dispose();
});

test('a mismatched server receipt locks the record until a fresh read',async()=>{
 const root=new Element();let posts=0;
 const api={request:async(_path,options={})=>{if(options.method==='POST'){posts++;return {item:{...liability,evidence_id:'20000000-0000-4000-8000-000000000002'}};}return structuredClone(queue);}};
 const dispose=await module.mountManagementTaxEcl({root,api,session,confirm:()=>true});
 const button=root.querySelector('[data-tax-action="post"]');fire(button,'click');await setImmediate();await setImmediate();
 assert.match(root.textContent,/uncertain|refresh/i);fire(button,'click');await setImmediate();assert.equal(posts,1);dispose();
});

test('permissions revoked during confirmation prevent a tax write',async()=>{
 const root=new Element();const actor=structuredClone(session);let posts=0;
 const api={request:async(_path,options={})=>{if(options.method==='POST')posts++;return structuredClone(queue);}};
 const dispose=await module.mountManagementTaxEcl({root,api,session:actor,confirm:()=>{actor.user.permissions=[];return true;}});
 fire(root.querySelector('[data-tax-action="post"]'),'click');await setImmediate();
 assert.equal(posts,0);assert.match(root.textContent,/permission/i);dispose();
});

test('tax evidence opens from accounting and returning fetches current records',async()=>{
 await import('../assets/management-tax-evidence.js');
 const root=new Element();const calls=[];
 const api={request:async path=>{calls.push(path);return path.includes('/tax?')?{rules:[],dst:[],percentage_tax:[],permissions:{},automatic_source_posting:false,tax_posting_enabled:false}:structuredClone(queue);}};
 const dispose=await module.mountManagementTaxEcl({root,api,session});
 fire(root.querySelector('[data-tax-evidence]'),'click');
 for(let i=0;i<20&&!calls.some(path=>path.includes('/tax?'));i++)await setImmediate();
 assert.ok(root.querySelector('[data-tax-back]'));
 assert.ok(calls.some(path=>path.includes('/tax?')));
 fire(root.querySelector('[data-tax-back]'),'click');await setImmediate();
 assert.ok(root.querySelector('[data-tax-action="post"]'));assert.equal(calls.filter(path=>path.includes('/liabilities?')).length,2);dispose();
});
