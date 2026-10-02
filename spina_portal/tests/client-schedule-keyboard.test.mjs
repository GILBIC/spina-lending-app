import test from 'node:test';
import assert from 'node:assert/strict';
import {Element,fire} from './helpers/dom.mjs';
import {bindClientScheduleButtons,renderClientSchedule} from '../assets/client-schedule.js';

const flush=()=>new Promise(resolve=>setImmediate(resolve));
const rows=count=>Array.from({length:count},(_,index)=>({payment_date:index%3===0?'2026-10-01':index%3===1?'2026-10-02':'2026-10-03',status:'Unknown',amount:index%2?'90071992547409.93':'-10.50',details:{remaining_amount:'0.00',note:`Saved row ${index} ${'Long original note '.repeat(8)}`}}));
function mounted(t,count=120){
 const originalFocus=Element.prototype.focus;Element.prototype.focus=function(){this.ownerDocument.activeElement=this;};t.after(()=>Element.prototype.focus=originalFocus);
 const root=new Element();root.ownerDocument={activeElement:null};
 root.innerHTML='<textarea name="unrelated"></textarea><article class="loan-card"><button data-client-schedule-loan="loan">View schedule</button><div data-client-schedule-panel hidden></div></article>';
 let state={status:'ready',data:{rows:rows(count),past_due_amount:'105.00',past_due_count:2,snapshot_day:'2026-10-02'}};let handle;
 const dispose=bindClientScheduleButtons({root,clientSchedules:{get:()=>state,load:async()=>state},onController:value=>handle=value});t.after(dispose);
 const panel=root.querySelector('[data-client-schedule-panel]');
 fire(root.querySelector('[data-client-schedule-loan]'),'click');
 return{root,panel,get handle(){return handle;},setState:value=>state=value};
}

test('keyboard filters and expansion retain logical focus, including the last page',async t=>{
 const h=mounted(t);await flush();
 for(const view of ['history','upcoming','all']){
  const button=h.panel.querySelector(`[data-schedule-view="${view}"]`);button.focus();fire(button,'click');
  assert.ok(h.root.ownerDocument.activeElement===h.panel.querySelector(`[data-schedule-view="${view}"]`),'focus stays on the activated filter');
  assert.equal(h.root.ownerDocument.activeElement.getAttribute('aria-pressed'),'true');
 }
 for(const total of [40,60,80,100,120]){
  const button=h.panel.querySelector('[data-schedule-more]');button.focus();fire(button,'click');
  const target=h.panel.querySelector(total===120?'[data-schedule-count]':'[data-schedule-more]');
  assert.ok(target);assert.ok(h.root.ownerDocument.activeElement===target,'focus stays on expansion or final row count');
  assert.match(h.panel.textContent,new RegExp(`Showing ${total} of 120`));
 }
 assert.equal(h.panel.querySelectorAll('tbody')[0].querySelectorAll('tr').length,120);
});

test('shared Loading and recovery keep the focused control but do not steal focus from another editor',async t=>{
 const h=mounted(t);await flush();
 h.panel.querySelector('[data-schedule-view="all"]').focus();
 h.setState({status:'loading'});h.handle.renderState('loan');
 assert.ok(h.root.ownerDocument.activeElement===h.panel.querySelector('[data-schedule-refresh]'),'Loading preserves the focused Refresh action');
 h.setState({status:'error'});h.handle.renderState('loan');
 assert.ok(h.root.ownerDocument.activeElement===h.panel.querySelector('[data-schedule-refresh]'),'error preserves the focused Retry action');
 const other=h.root.querySelector('[name="unrelated"]');other.value='Keep unrelated draft';other.focus();
 h.setState({status:'ready',data:{rows:rows(30),snapshot_day:'2026-10-02'}});h.handle.renderState('loan');
 assert.equal(h.root.ownerDocument.activeElement,other);assert.equal(other.value,'Keep unrelated draft');
 const close=h.panel.querySelector('[data-schedule-close]');close.focus();fire(close,'click');
 assert.equal(h.panel.hidden,true);assert.equal(h.root.ownerDocument.activeElement,h.root.querySelector('[data-client-schedule-loan]'));
});

for(const count of [0,30,120])test(`schedule ${count} keeps exact supplied order, distinct rows and date-only filtering`,()=>{
 const supplied=rows(count);const snapshot=JSON.stringify(supplied);
 for(const view of ['upcoming','history','all']){
  const root=new Element();root.innerHTML=renderClientSchedule({rows:supplied,past_due_amount:'105.00',past_due_count:2},{view,today:'2026-10-02',visibleLimit:200});
  const expected=supplied.filter(row=>view==='all'||(view==='history'?row.payment_date<'2026-10-02':row.payment_date>='2026-10-02'));
  const notes=root.querySelectorAll('[data-label="Note"]').map(node=>node.textContent);
  assert.deepEqual(notes,expected.map(row=>row.details.note.trim()));
  const amounts=root.querySelectorAll('[data-label="Required amount"]').map(node=>node.textContent);
  assert.deepEqual(amounts,expected.map(row=>row.amount.startsWith('-')?'-₱10.50':'₱90,071,992,547,409.93'));
  assert.match(root.textContent,/105.00/);
  if(!count)assert.match(root.textContent,/does not establish that the loan is paid/);
 }
 assert.equal(JSON.stringify(supplied),snapshot);
});
