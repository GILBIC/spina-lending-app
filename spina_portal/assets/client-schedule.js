import {asArray,badge,escapeHtml,formatDate,formatExactMoney} from './ui.js';
import {createClientReadController} from './client-workspace-state.js';
export function formatAuthoritativeMoney(value) {return formatExactMoney(value,{minimumFractionDigits:0});}
const validMoney = value => typeof value === 'string' && /^[+-]?\d+(?:\.\d+)?$/.test(value);
const validCount = value => Number.isSafeInteger(value) && value >= 0;
const money = value => validMoney(value) ? formatAuthoritativeMoney(value) : 'Unavailable';
export function manilaToday() {return new Intl.DateTimeFormat('en-CA',{timeZone:'Asia/Manila',year:'numeric',month:'2-digit',day:'2-digit'}).format(new Date());}
const validDate = value => {
 if(typeof value !== 'string' || !/^\d{4}-\d{2}-\d{2}$/.test(value) || value.startsWith('0000-'))return false;
 const date=new Date(`${value}T00:00:00Z`);return !Number.isNaN(date.getTime()) && date.toISOString().slice(0,10)===value;
};
export function validateClientSchedule(value,loanId) {
 if (!value || value.loan_id !== loanId || value.read_only !== true || !Array.isArray(value.rows) || value.rows.some(row=>!row || typeof row !== 'object' || !validDate(row.payment_date))) throw Error('The schedule does not match this loan or is incomplete.');
 return value;
}
export function createClientScheduleController({api,reads,signal,isCurrent,onState=()=>{}}) {
 const ownReads = !reads;reads ||= createClientReadController({signal,isCurrent});let disposed=false;const ids=new Set();
 const get = id => reads.state(`schedule:${id}`);
 return {get,async load(id,options){if(disposed)return get(id);ids.add(id);const result=await reads.load(`schedule:${id}`,async({signal:requestSignal})=>({...validateClientSchedule(await api.request(`/api/v1/client/loans/${encodeURIComponent(id)}/schedule`,{signal:requestSignal}),id),snapshot_day:manilaToday()}),options);if(!disposed)onState(id,result);return result;},dispose(){disposed=true;if(ownReads)reads.dispose();else for(const id of ids)reads.invalidate(`schedule:${id}`);}};
}
export function renderClientPayoff(stateOrSchedule) {
 const state=stateOrSchedule?.status && ['idle','loading','ready','error'].includes(stateOrSchedule.status)?stateOrSchedule:null;
 if(state && state.status!=='ready')return `<div class="notice-card warning"><strong>${state.status==='error'?'Payoff information unavailable':'Loading payoff information…'}</strong><p>Open the schedule to retry this loan.</p></div>`;
 const schedule=state?.data||stateOrSchedule;const status=schedule?.penalty_status;
 if(status==='management_review_required')return `<div class="notice-card warning"><strong>Management review required</strong><p>${escapeHtml(schedule.management_review_required_reason||'Open the schedule for the current review status.')}</p></div>`;
 if(!['projected','penalty_outstanding','cap_exhausted'].includes(status))return status && status!=='not_applicable'?'<div class="notice-card warning">Payoff information unavailable. Open the schedule for details.</div>':'';
 return `<div class="notice-card" data-client-home-obligation><strong>Exact payoff</strong><p>${money(schedule.exact_payoff_total)}</p><div class="loan-meta"><div class="detail-item"><span>Assessed penalty balance</span><strong>${money(schedule.assessed_penalty_balance)}</strong></div><div class="detail-item"><span>Projected penalty (not yet assessed)</span><strong>${money(schedule.projected_penalty)}</strong></div></div></div>`;
}
export function clientInstallmentGuidance({loan,scheduleState,today}) {
 const data=scheduleState?.status==='ready'?scheduleState.data:null;
 const fallback={status:'unavailable',selectedRow:null,pastDueAmount:validMoney(data?.past_due_amount)?data.past_due_amount:null,pastDueCount:validCount(data?.past_due_count)?data.past_due_count:null,message:'Open schedule for the current amount'};
 if(!data||!validDate(today)||data.snapshot_day&&data.snapshot_day!==today)return {...fallback,status:data?.snapshot_day&&data.snapshot_day!==today?'stale':'unavailable'};
 const rows=asArray(data.rows);if(rows.some(row=>!validDate(row?.payment_date)))return fallback;const candidates=rows.filter(row=>row.payment_date>=today);
 if(candidates.some(row=>!['Due Today','Scheduled','Paid','No Collection'].includes(row.status)))return fallback;
 const todayRows=candidates.filter(row=>row.payment_date===today);
 if(todayRows.length>1)return fallback;
 const row=todayRows[0]||candidates.filter(row=>row.status==='Scheduled').sort((a,b)=>a.payment_date.localeCompare(b.payment_date))[0];
 if(!row||candidates.filter(item=>item.payment_date===row.payment_date).length!==1)return fallback;
 if(['Paid','No Collection'].includes(row.status))return {...fallback,status:'covered',selectedRow:row,message:`${row.status} · ${row.payment_date}`};
 if(!['Due Today','Scheduled'].includes(row.status)||money(row.details?.remaining_amount)==='Unavailable')return fallback;
 return {...fallback,status:'ready',selectedRow:row,message:`${row.payment_date} · Remaining installment ${money(row.details.remaining_amount)}`};
}
export function renderClientSchedule(schedule={}, {view='upcoming',today=manilaToday(),visibleLimit=20}={}) {
 const all=asArray(schedule.rows);const rows=all.filter(row=>view==='all'||(view==='history'?row.payment_date<today:row.payment_date>=today));const visible=rows.slice(0,visibleLimit);
 return `<div class="notice-card client-schedule"><strong>Authoritative SPINA schedule · ${escapeHtml(schedule.is_7x7===true?'7x7':schedule.loan_type||'Loan')}</strong><p class="meta">Read-only server schedule. Displayed Manila date ${escapeHtml(today)}.</p>${renderClientPayoff(schedule)}<div class="loan-meta"><div class="detail-item"><span>Contractual maturity</span><strong>${validDate(schedule.contractual_maturity)?formatDate(schedule.contractual_maturity):'Unavailable'}</strong></div><div class="detail-item"><span>Current operational completion</span><strong>${validDate(schedule.operational_maturity)?formatDate(schedule.operational_maturity):'Unavailable'}</strong></div><div class="detail-item"><span>Past due</span><strong>${money(schedule.past_due_amount)}</strong></div><div class="detail-item"><span>Past-due rows</span><strong>${escapeHtml(validCount(schedule.past_due_count)?schedule.past_due_count:'Unavailable')}</strong></div><div class="detail-item"><span>Schedule status</span><strong>${escapeHtml(schedule.maturity_status||'Unavailable')}</strong></div></div><div class="inline-actions">${['upcoming','history','all'].map(v=>`<button class="button button-secondary" type="button" data-schedule-view="${v}" aria-pressed="${view===v}">${v==='history'?'History / past due':v==='all'?'All':'Upcoming'}</button>`).join('')}<button class="button button-secondary" type="button" data-schedule-refresh>Refresh</button><button class="button button-secondary" type="button" data-schedule-close>Close schedule</button></div><p data-schedule-count tabindex="-1">Showing ${visible.length} of ${rows.length} matching rows · ${all.length} loaded rows</p>${visible.length?`<div class="table-wrap"><table class="mobile-card-table client-schedule-table"><thead><tr><th>Date</th><th>Required amount</th><th>Status</th><th>Remaining</th><th>Note</th></tr></thead><tbody>${visible.map(row=>`<tr><td data-label="Date">${formatDate(row.payment_date)}</td><td data-label="Required amount">${money(row.amount)}</td><td data-label="Status">${badge(row.status||'Unknown')}</td><td data-label="Remaining">${money(row.details?.remaining_amount)}</td><td data-label="Note">${escapeHtml(row.details?.note||'—')}</td></tr>`).join('')}</tbody></table></div>`:'<div class="empty-state">No schedule rows in this view. This does not establish that the loan is paid.</div>'}${visible.length<rows.length?'<button class="button button-secondary" type="button" data-schedule-more>Show more</button>':''}</div>`;
}
export function bindClientScheduleButtons(context) {
 const {root,api,signal}=context;const schedules=context.clientSchedules||createClientScheduleController({api,signal});const removers=[],draws=new Map();let disposed=false;
 const listen=(el,event,fn)=>{el?.addEventListener(event,fn);if(el)removers.push(()=>el.removeEventListener(event,fn));};
 for(const button of root.querySelectorAll('[data-client-schedule-loan]')) {
  const id=String(button.dataset.clientScheduleLoan||'');const panel=button.closest('.loan-card')?.querySelector('[data-client-schedule-panel]');let generation=0,view='upcoming',limit=20;let today=manilaToday();
  let panelRemovers=[];const clearPanelListeners=()=>{for(const remove of panelRemovers)remove();panelRemovers=[];};removers.push(clearPanelListeners);
  const panelListen=(el,fn)=>{if(el){el.addEventListener('click',fn);panelRemovers.push(()=>el.removeEventListener('click',fn));}};
  const draw=()=>{if(disposed||signal?.aborted||!panel||panel.hidden)return;const focused=panel.ownerDocument?.activeElement;const focusSelector=['[data-schedule-refresh]','[data-schedule-close]','[data-schedule-more]',...['upcoming','history','all'].map(value=>`[data-schedule-view="${value}"]`)].find(selector=>focused&&panel.querySelector(selector)===focused);const state=schedules.get(id);if(state.status==='ready')today=state.data.snapshot_day||today;context.beforeTaskChange?.();clearPanelListeners();panel.innerHTML=state.status==='ready'?renderClientSchedule(state.data,{view,today,visibleLimit:limit}):`<div class="notice-card warning"><strong>${state.status==='error'?'Payoff information unavailable. Schedule unavailable.':'Loading authoritative schedule…'}</strong><button class="button button-secondary" type="button" data-schedule-refresh>Retry</button><button class="button button-secondary" type="button" data-schedule-close>Close schedule</button></div>`;context.afterTaskChange?.();
   panelListen(panel.querySelector('[data-schedule-close]'),()=>{generation++;context.beforeTaskChange?.();panel.hidden=true;button.textContent='View schedule';button.focus();context.afterTaskChange?.();});
   panelListen(panel.querySelector('[data-schedule-refresh]'),()=>load(true));panelListen(panel.querySelector('[data-schedule-more]'),()=>{limit+=20;draw();});for(const b of panel.querySelectorAll('[data-schedule-view]'))panelListen(b,()=>{view=b.dataset.scheduleView;limit=20;draw();});
   if(focusSelector)(panel.querySelector(focusSelector)||panel.querySelector('[data-schedule-count]')||panel.querySelector('[data-schedule-refresh]'))?.focus?.({preventScroll:true});
  };
  const load=async(refresh=false)=>{if(disposed||signal?.aborted||!panel)return;const version=++generation;panel.hidden=false;button.textContent='Schedule open';const promise=schedules.load(id,{refresh});draw();await promise;if(version===generation)draw();};
  listen(button,'click',()=>load(schedules.get(id).status==='error'));
  draws.set(id,draw);
 }
 context.onController?.({renderState:id=>{if(!disposed)draws.get(id)?.();}});
 return ()=>{if(disposed)return;disposed=true;draws.clear();for(const remove of removers)remove();if(!context.clientSchedules)schedules.dispose();};
}

