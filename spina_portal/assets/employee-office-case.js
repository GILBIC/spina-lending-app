import {escapeHtml as esc} from './ui.js';
import {createOfficeCaseContext} from './office-case-context.js';
export const officeStageLabels={intake:'Intake & requirements',cif:'Client information (CIF)',application:'Loan application','first-loan':'Approval & release'};
const steps=Object.entries(officeStageLabels).map(([stage,label],index)=>[stage,['employee-onboarding','employee-cif-review','employee-application-review','employee-first-loan'][index],label]);
export function officeCaseBanner(context,stage) {
 const labels={intake:'Intake status',cif:'CIF status',application:'Application status','first-loan':'Approval & release status'};
 const facts=Object.entries(labels).map(([key,label])=>{const fact=context.stageFacts[key];return `${label}: ${esc(fact?.status || 'Not loaded')}${fact?.versionNumber!=null ? ` · Saved version ${esc(fact.versionNumber)}` : ''}`;}).join(' · ');
 return `<strong>Office case</strong><p>${context.mode==='new-intake'?'New intake — not yet saved':context.intakeReference?`Intake: ${esc(context.intakeReference)}`:'No intake selected'} · Applicant: ${esc(context.applicantName || 'Not loaded')} · Loan application: ${esc(context.applicationReference ? `${context.applicationReference}${context.applicationSaved?'':' · Draft reference — not saved'}` : 'Not loaded')}</p><p>${facts}</p><p>Viewing ${esc(officeStageLabels[stage])}. Open this stage to verify its current record. Intake eligibility, applicant confirmation, Management approval, signing and cash receipt remain separate.</p>`;
}

export function bindEmployeeOfficeCase({root,navigate,signal,getSession=()=>null,confirmDiscard}) {
 let disposed=false,lastStep='intake';const strips=new Map();
 const coordinator=createOfficeCaseContext({getSession,confirmDiscard,onChange:(_value,lifecycle)=>{if(lifecycle?.disposed){for(const strip of strips.values()){strip.textContent='';if(lifecycle.accessDenied){strip.textContent='Office access is unavailable. Sign in again before continuing.';strip.setAttribute('role','alert');}else strip.remove();}if(!lifecycle.accessDenied)strips.clear();return;}if(!disposed)render(lastStep);}});
 const section=step=>root.querySelector(`#${steps.find(item=>item[0]===step)?.[1]}`);
 function render(step) {
  const node=section(step);if(!node)return;
  let strip=strips.get(step);if(!strip){strip=root.ownerDocument.createElement('aside');strip.setAttribute('data-office-case-strip','');strip.className='notice-card';(node.prepend?node.prepend(strip):node.appendChild(strip));strips.set(step,strip);}
  const context=coordinator.getContext(),index=steps.findIndex(item=>item[0]===step);
  strip.innerHTML=officeCaseBanner(context,step)+`<div class="inline-actions">${index>0?`<button class="button button-outline" type="button" data-office-case-back>Back: ${steps[index-1][2]}</button>`:''}${index<steps.length-1?`<button class="button button-outline" type="button" data-office-case-next>Next: ${steps[index+1][2]}</button>`:''}</div>`;
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
