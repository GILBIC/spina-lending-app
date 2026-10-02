import {escapeHtml as esc,titleCase} from './ui.js';
const uuid=/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
const money=value=>typeof value==='string'&&/^(0|[1-9]\d*)\.\d{2}$/.test(value);
const date=value=>typeof value==='string'&&/^\d{4}-\d{2}-\d{2}$/.test(value);
export function payslipPrintable(record) {const p=record?.payload;return uuid.test(record?.id)&&uuid.test(record?.employee_id)&&Number.isSafeInteger(record?.version)&&record.version>0&&['approved','partially_paid','paid'].includes(record.status)&&p&&date(p.week_start)&&date(p.period_end)&&typeof p.payroll_kind==='string'&&p.payroll_kind.length>0&&['gross_pay','deductions','net_pay','paid_amount','balance_due'].every(key=>money(p[key]))&&Array.isArray(p.issues)&&p.issues.length===0&&Array.isArray(p.components)&&p.components.every(item=>typeof item?.label==='string'&&item.label.length>0&&typeof item.amount==='string'&&/^-?(0|[1-9]\d*)\.\d{2}$/.test(item.amount));}
export function buildPayslipPrintMarkup({record,employeeName}) {
 if(!payslipPrintable(record)||typeof employeeName!=='string'||!employeeName.trim())throw new Error('This authorized payroll snapshot is incomplete or unpublished.');
 const p=record.payload;
 return `<article class="employee-payslip-copy"><h1>SPINA payroll record copy</h1><p><strong>Payroll record copy — not proof of payment</strong></p><h2>${esc(employeeName)}</h2><p>Employee: ${esc(record.employee_id)}</p><p>Payroll: ${esc(record.id)} · Revision ${record.version}</p><p>${esc(titleCase(p.payroll_kind))} · ${esc(p.week_start)} to ${esc(p.period_end)} · ${esc(titleCase(record.status))}</p><table><thead><tr><th>Recorded component</th><th>Server amount (PHP)</th></tr></thead><tbody>${p.components.map(item=>`<tr><th>${esc(item.label)}</th><td>${esc(item.amount)}</td></tr>`).join('')}</tbody></table><dl>${[['gross_pay','Gross pay'],['deductions','Deductions'],['net_pay','Net pay'],['paid_amount','Completed payments'],['balance_due','Still due']].map(([key,label])=>`<div><dt>${label}</dt><dd>PHP ${esc(p[key])}</dd></div>`).join('')}</dl>${p.paid_amount==='0.00'?'<p>No completed payment is recorded. Approved payroll can remain unpaid.</p>':''}<p>This copy contains the selected server snapshot. Component amounts and totals are not recalculated here.</p></article>`;
}
export function mountEmployeePayslipPrint({root,getCurrentScope,loadWorkspace,signal,print=()=>globalThis.print()}) {
 let disposed=false,generation=0,region=null;
 function close(){generation+=1;if(region){region.textContent='';region.remove();region=null;}}
 function dispose(){if(disposed)return;disposed=true;close();signal?.removeEventListener('abort',dispose);globalThis.removeEventListener?.('afterprint',close);}
 async function open(recordId,expectedVersion){
  close();if(disposed||signal?.aborted||globalThis.navigator?.onLine===false)throw new Error('An online authorized payroll read is required.');
  const original=getCurrentScope(),current=++generation;if(!original)throw new Error('The employee scope is no longer authorized.');
  const value=await loadWorkspace();if(disposed||signal?.aborted||current!==generation)return;
  const scope=getCurrentScope();if(!scope||scope.userId!==original.userId||scope.employeeId!==original.employeeId||scope.deviceId!==original.deviceId||value?.actor?.user_id!==scope.userId||value.actor.employee_id!==scope.employeeId||value.actor.device_id!==scope.deviceId)throw new Error('The authorized employee scope changed.');
  const matches=Array.isArray(value.payroll)?value.payroll.filter(record=>record?.id===recordId&&record.employee_id===scope.employeeId):[];
  if(matches.length!==1)throw new Error('The selected payroll record is not authorized.');
  const record=matches[0];if(record.version!==expectedVersion)throw new Error('The payroll record changed. Review the current revision before printing.');
  const names=Array.isArray(value.profiles)?value.profiles.filter(item=>item.employee_id===scope.employeeId):[];
  const markup=buildPayslipPrintMarkup({record,employeeName:names.length===1?names[0].payload?.full_name:'Employee'});
  region=root.ownerDocument.createElement('section');region.setAttribute('data-employee-print-region','');region.innerHTML=markup;
  (root.ownerDocument.body||root).appendChild(region);try{print();}catch(error){close();throw error;}
 }
 signal?.addEventListener('abort',dispose,{once:true});globalThis.addEventListener?.('afterprint',close);if(signal?.aborted)dispose();return {open,close,dispose};
}
