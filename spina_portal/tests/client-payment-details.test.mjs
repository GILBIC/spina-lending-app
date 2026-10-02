import test from 'node:test';import assert from 'node:assert/strict';import {Element,fire} from './helpers/dom.mjs';
const module=await import('../assets/client-payment-details.js').catch(()=>({}));
const id='10000000-0000-4000-8000-000000000001';
test('exact detail and matching record copy never calculate allocations or auto-download',()=>{
 assert.equal(typeof module.renderClientPaymentDetails,'function');const html=module.renderClientPaymentDetails({transaction_id:id,amount:'90071992547409.93',collector_name:'Synthetic',covered_dates:['2026-10-01','2026-10-03'],previous_balance:'3100.00',official_balance:'2205.00',is_voided:true,void_reason:'Duplicate <script>',collection_origin:'assigned_route',note:'Saved note'});assert.match(html,/90,071,992,547,409\.93/);assert.match(html,/2026-10-03/);assert.match(html,/Voided/);assert.match(html,/Saved note/);assert.match(html,/Not recorded/);assert.doesNotMatch(html,/<script>|Principal allocation|Interest allocation/);
 const root=new Element();root.innerHTML=`<button data-payment-details="${id}">View</button><div data-payment-detail-panel="${id}"></div>`;let downloads=0;module.bindClientPaymentDetails({root,paymentsState:{status:'ready',data:{payments:[{transaction_id:id}]}},onDownload:()=>downloads++});assert.equal(downloads,0);fire(root.querySelector('[data-payment-details]'),'click');assert.match(root.textContent,/Payment record/);assert.equal(downloads,0);fire(root.querySelector('[data-payment-record-copy]'),'click');assert.equal(downloads,1);
});


test('payment detail displays every supported producer fact exactly, including non-contiguous coverage and void history facts',()=>{
 const root=new Element();
 // Mirrors _payment_payload in client_payment_api.py, with synthetic large decimals.
 root.innerHTML=module.renderClientPaymentDetails({
  transaction_id:id,receipt_number:'SYNTHETIC-RECEIPT-06',loan_id:'20000000-0000-4000-8000-000000000001',loan_number:'SYNTHETIC-LOAN',loan_type_name:'Regular',
  collector_name:'Test Collector',collection_date:'2026-08-06',recorded_at:'2026-08-06T09:12:00+08:00',entry_type:'payment',
  amount:'90071992547409.93',covered_dates:['2026-08-06','2026-08-08'],previous_balance:'3100.00',official_balance:'2205.00',
  note:'Saved note <private>',collection_origin:'assigned_route',status:'voided',is_voided:true,voided_at:'2026-08-07T10:13:00+08:00',void_reason:'Duplicate <script>',edit_version:3,
  remittance_number:'SYNTHETIC-REMITTANCE-08',remittance_status:'received',remittance_submitted_at:'2026-08-06T11:14:00+08:00',remittance_received_at:'2026-08-06T12:15:00+08:00',
 });
 const facts=Object.fromEntries(root.querySelectorAll('.detail-item').map(row=>[row.querySelector('span').textContent,row.querySelector('strong').textContent]));
 assert.deepEqual(facts,{
  Transaction:id,Receipt:'SYNTHETIC-RECEIPT-06',Loan:'SYNTHETIC-LOAN',Collector:'Test Collector','Collection date':'Aug 6, 2026',Recorded:'Aug 6, 2026, 9:12 AM',
  Amount:'₱90,071,992,547,409.93','Covered dates':'2026-08-06, 2026-08-08','Previous balance':'₱3,100.00','Official balance':'₱2,205.00',Origin:'assigned_route',Status:'Voided',
  'Void date':'Aug 7, 2026, 10:13 AM','Void reason':'Duplicate &lt;script&gt;','Record version':'3',Note:'Saved note &lt;private&gt;',
  'Remittance reference':'SYNTHETIC-REMITTANCE-08','Remittance status':'received','Remittance submitted':'Aug 6, 2026, 11:14 AM','Remittance received':'Aug 6, 2026, 12:15 PM',
 });
 assert.match(root.querySelector('[data-payment-record-copy]').textContent,/Download voided payment record copy/);
 assert.equal(root.querySelector('[data-payment-record-copy]').getAttribute('data-payment-record-copy'),id);
 assert.match(root.textContent,/Current record copies reflect corrections and voids/);
 assert.match(root.textContent,/Internal remittance is separate from your official payment record/);
 assert.doesNotMatch(root.innerHTML,/<script>|<private>|2026-08-07,|Principal allocation|Interest allocation|Extra amount/);
});

test('sparse optional payment facts remain Not recorded without deriving balances or allocations',()=>{
 const root=new Element();root.innerHTML=module.renderClientPaymentDetails({transaction_id:id,status:'posted',is_voided:false,amount:'0.00',edit_version:0});
 const facts=Object.fromEntries(root.querySelectorAll('.detail-item').map(row=>[row.querySelector('span').textContent,row.querySelector('strong').textContent]));
 assert.equal(facts.Amount,'₱0.00');assert.equal(facts['Record version'],'0');assert.equal(facts.Status,'posted');
 for(const key of ['Collector','Collection date','Recorded','Covered dates','Previous balance','Official balance','Origin','Void date','Void reason','Note','Remittance reference','Remittance status','Remittance submitted','Remittance received'])assert.equal(facts[key],'Not recorded',key);
 assert.doesNotMatch(root.textContent,/paid off|principal allocation|interest allocation|Download voided/i);
});

test('unknown, malformed and unread payment targets cannot open an unrelated detail',()=>{
 for(const state of [{status:'loading'},{status:'error'},{status:'ready',data:{payments:[{transaction_id:'20000000-0000-4000-8000-000000000001'}]}}]){
  const root=new Element();root.innerHTML=`<button data-payment-details="${id}">View</button><div data-payment-detail-panel="${id}"></div>`;
  let downloads=0;const dispose=module.bindClientPaymentDetails({root,paymentsState:state,onDownload:()=>downloads++});
  fire(root.querySelector('[data-payment-details]'),'click');assert.equal(root.querySelector('[data-payment-record-copy]'),null);assert.equal(downloads,0);dispose();
 }
});
