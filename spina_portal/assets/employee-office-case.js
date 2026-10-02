import {escapeHtml as esc} from './ui.js';
const steps=[['intake','employee-onboarding','Office intake'],['cif','employee-cif-review','CIF review'],['application','employee-application-review','Application review'],['first-loan','employee-first-loan','First-loan work']];
export function bindEmployeeOfficeCase({root,navigate,signal}) {
 let disposed=false,intakeReference='',applicationReference='',writing=false,lastStep=null;const listeners=[],strips=[],bound=new WeakSet();
 const section=step=>root.querySelector(`#${steps.find(item=>item[0]===step)?.[1]}`);
 const intake=(node,step)=>node?.querySelector(`[name="${['intake','cif'].includes(step)?'applicationReference':'intakeReference'}"]`);
 const application=(node,step)=>['application','first-loan'].includes(step)?node?.querySelector('[name="applicationReference"]'):null;
 function on(node,type,fn){if(!node)return;node.addEventListener(type,fn);listeners.push(()=>node.removeEventListener(type,fn));}
 function invalidate(node){if(!node)return;node.dispatchEvent(new Event('input',{bubbles:true}));node.dispatchEvent(new Event('change',{bubbles:true}));}
 function assign(node,value){if(!node)return;writing=true;node.value=value;invalidate(node);writing=false;}
 function bind(step,node){const input=intake(node,step),app=application(node,step);
  if(input&&!bound.has(input)){bound.add(input);on(input,'input',()=>{if(writing||disposed)return;const next=input.value.trim();if(next===intakeReference)return;intakeReference=next;applicationReference='';writing=true;
    for(const [key] of steps){const target=section(key);invalidate(intake(target,key));const reference=application(target,key);if(reference){reference.value='';invalidate(reference);}}
    writing=false;});}
  if(app&&!bound.has(app)){bound.add(app);on(app,'input',()=>{if(!writing&&input.value.trim()===intakeReference)applicationReference=app.value.trim();});}
 }
 function activate(step){if(disposed||signal?.aborted)return;const node=section(step);if(!node)return;
  const previous=section(lastStep),previousApplication=application(previous,lastStep);
  if(previousApplication&&intakeReference&&intake(previous,lastStep)?.value.trim()===intakeReference)applicationReference=previousApplication.value.trim();
  lastStep=step;bind(step,node);
  let strip=node.querySelector('[data-office-case-strip]');if(!strip){strip=root.ownerDocument.createElement('aside');strip.setAttribute('data-office-case-strip','');strip.className='notice-card';(node.prepend?node.prepend(strip):node.appendChild(strip));strips.push(strip);}
  const input=intake(node,step),app=application(node,step);
  const conflict=input?.value.trim()&&intakeReference&&input.value.trim()!==intakeReference || app?.value.trim()&&applicationReference&&app.value.trim()!==applicationReference;
  if(!conflict){if(input&&!input.value.trim()&&intakeReference)assign(input,intakeReference);if(app&&!app.value.trim()&&applicationReference)assign(app,applicationReference);}
  const index=steps.findIndex(item=>item[0]===step);
  strip.innerHTML=`<strong>Office case references</strong><p>Intake: ${esc(intakeReference||'Not entered')} · Loan application: ${esc(applicationReference||'Not entered')}</p><p>Carried references are typed and unverified. Open each step to verify its current authorized record.</p>${conflict?'<p>The target contains another case. Switching clears its loaded case and linked application before carrying these references.</p><button type="button" class="button button-secondary" data-office-case-switch>Switch case and discard target selection</button>':''}<div class="inline-actions">${index>0?`<button class="button button-outline" type="button" data-office-case-back>Back: ${steps[index-1][2]}</button>`:''}${index<steps.length-1?`<button class="button button-outline" type="button" data-office-case-next>Next: ${steps[index+1][2]}</button>`:''}</div>`;
  on(strip.querySelector('[data-office-case-switch]'),'click',()=>{assign(input,intakeReference);assign(app,applicationReference);activate(step);});
  on(strip.querySelector('[data-office-case-back]'),'click',()=>navigate(steps[index-1][1]));on(strip.querySelector('[data-office-case-next]'),'click',()=>navigate(steps[index+1][1]));
 }
 function dispose(){if(disposed)return;disposed=true;intakeReference='';applicationReference='';for(const remove of listeners)remove();for(const strip of strips){strip.textContent='';strip.remove();}signal?.removeEventListener('abort',dispose);}
 signal?.addEventListener('abort',dispose,{once:true});return {activate,dispose};
}
