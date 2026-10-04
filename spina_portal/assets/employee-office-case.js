import {escapeHtml as esc} from './ui.js';
import {createOfficeCaseContext} from './office-case-context.js';
const steps=[['intake','employee-onboarding','Office intake'],['cif','employee-cif-review','CIF review'],['application','employee-application-review','Application review'],['first-loan','employee-first-loan','First-loan work']];
export function bindEmployeeOfficeCase({root,navigate,signal,getSession=()=>null,confirmDiscard}) {
 let disposed=false,lastStep='intake';const strips=new Map();
 const coordinator=createOfficeCaseContext({getSession,confirmDiscard,onChange:()=>{if(!disposed)render(lastStep);}});
 const section=step=>root.querySelector(`#${steps.find(item=>item[0]===step)?.[1]}`);
 function render(step) {
  const node=section(step);if(!node)return;
  let strip=strips.get(step);if(!strip){strip=root.ownerDocument.createElement('aside');strip.setAttribute('data-office-case-strip','');strip.className='notice-card';(node.prepend?node.prepend(strip):node.appendChild(strip));strips.set(step,strip);}
  const context=coordinator.getContext(),index=steps.findIndex(item=>item[0]===step);
  strip.innerHTML=`<strong>Office case</strong><p>${context.mode==='new-intake'?'New intake — not yet saved':context.intakeReference?`Intake: ${esc(context.intakeReference)}`:'No intake selected'} · Loan application: ${esc(context.applicationReference ? `${context.applicationReference}${context.applicationSaved?'':' — Draft reference — not saved'}` : 'Not loaded')}</p><p>Viewing ${esc(steps[index][2])}. Open this stage to verify its current record.</p><div class="inline-actions">${index>0?`<button class="button button-outline" type="button" data-office-case-back>Back: ${steps[index-1][2]}</button>`:''}${index<steps.length-1?`<button class="button button-outline" type="button" data-office-case-next>Next: ${steps[index+1][2]}</button>`:''}</div>`;
  const go=async target=>{if(await coordinator.requestTransition({kind:'navigate',targetStage:target[0]}))navigate(target[1]);};
  strip.querySelector('[data-office-case-back]')?.addEventListener('click',()=>void go(steps[index-1]));
  strip.querySelector('[data-office-case-next]')?.addEventListener('click',()=>void go(steps[index+1]));
 }
 async function activate(step){if(disposed||signal?.aborted)return false;const node=section(step);if(!node)return false;
  if(!await coordinator.requestTransition({kind:'navigate',targetStage:step})||disposed)return false;lastStep=step;
  const context=coordinator.getContext();
  const input=node.querySelector(`[name="${['intake','cif'].includes(step)?'applicationReference':'intakeReference'}"]`);
  const app=['application','first-loan'].includes(step)?node.querySelector('[name="applicationReference"]'):null;
  if(input&&!input.value.trim()&&context.intakeReference)input.value=context.intakeReference;
  if(app&&!app.value.trim()&&context.applicationReference)app.value=context.applicationReference;
  render(step);return true;
 }
 function dispose(){if(disposed)return;disposed=true;coordinator.dispose();for(const strip of strips.values()){strip.textContent='';strip.remove();}strips.clear();signal?.removeEventListener('abort',dispose);}
 signal?.addEventListener('abort',dispose,{once:true});return {activate,dispose,coordinator};
}
