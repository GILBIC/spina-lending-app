import assert from 'node:assert/strict';
import test from 'node:test';
import {collectorSource} from '../assets/management-collector-accounting.js';

const id = n => `00000000-0000-4000-8000-${String(n).padStart(12, '0')}`;
const scope = kind => ({bookId:id(1),accountId:id(2),sourceId:id(3),sourceKind:kind});
const line = (code,debit,credit,n) => ({account_code:code,debit,credit,line_number:n,account_snapshot:{name:code}});
const split = {gross_obligation:'100.00',authorized_credit_amount:'4.00',physical_cash_required:'96.00',physical_amount:'98.00',excess_amount:'2.00'};
const source = (kind='credit_application') => ({book_id:id(1),treasury_account_id:id(2),source_id:id(3),source_kind:kind,fiscal_period_id:id(4),posting_date:'2026-10-05',amount:kind==='settlement'?'98.00':'4.00',fee:'0.00',source_digest:'a'.repeat(64),custody_split:{...split},lines:kind==='settlement'?[line('1010','98.00','0.00',1),line('1020','0.00','96.00',2),line('2210','0.00','2.00',3)]:[line('2220','4.00','0.00',1),line('1020','0.00','4.00',2)]});

test('application journal binds the exact custody split and contains no received cash',()=>{
 const value=collectorSource(source(),scope('credit_application'));
 assert.deepEqual(value.custody_split,split);
 for(const update of [{authorized_credit_amount:'5.00'},{gross_obligation:'99.00'},{physical_amount:'96.00'},{excess_amount:'-2.00'}])assert.throws(()=>collectorSource({...source(),custody_split:{...split,...update}},scope('credit_application')));
 const bad=source();bad.lines[1].account_code='1010';assert.throws(()=>collectorSource(bad,scope('credit_application')));
 assert.throws(()=>collectorSource({...source(),custody_split:undefined},scope('credit_application')));
});
test('cash leg retains only physical principal and actual excess',()=>{
 assert.deepEqual(collectorSource(source('settlement'),scope('settlement')).custody_split,split);
 const bad=source('settlement');bad.lines[1].credit='97.00';bad.lines[2].credit='1.00';assert.throws(()=>collectorSource(bad,scope('settlement')));
});
test('full credit plus excess cash has only received excess in its cash journal',()=>{
 const value={...source('settlement'),amount:'2.00',custody_split:{gross_obligation:'100.00',authorized_credit_amount:'100.00',physical_cash_required:'0.00',physical_amount:'2.00',excess_amount:'2.00'},lines:[line('1010','2.00','0.00',1),line('2210','0.00','2.00',2)]};
 assert.equal(collectorSource(value,scope('settlement')).amount,'2.00');
 assert.throws(()=>collectorSource({...value,custody_split:undefined},scope('settlement')));
});
