import assert from 'node:assert/strict';
import test from 'node:test';
import {setImmediate} from 'node:timers/promises';

import { mountManagementWorkspace } from '../assets/roles/management.js';
import { Element, fire } from './helpers/dom.mjs';

class ManagementElement extends Element {
  querySelectorAll(selector) {
    if (/^\[[^\]]+\]\[[^\]]+\]$/.test(selector)) return [];
    return super.querySelectorAll(selector);
  }
}

function response(path) {
  if(path.includes('/onboarding/applicants/by-reference/'))return {applicant_id:'11111111-1111-4111-8111-111111111111',application_reference:'INTAKE-123',status:'under_verification',client_id:null,full_name:'Saved office applicant',phone_number:'00000000000',email:null,present_address:'Saved address',privacy_consent:true,accuracy_declaration:true,bypassed_requirements:[],bypass_reason:null,requirements:Object.fromEntries(['national_id','tin_id','meralco_bill','collector_visit'].map(name=>[name,{status:'pending',evidence_reference:null,note:null}]))};
  if (path === '/api/v1/account') return { profile: { full_name: 'Management User' }, devices: [] };
  if (path === '/api/v1/management/dashboard-overview') return { metrics: [] };
  if (path.startsWith('/api/v1/management/loans')) return { summary: {}, loans: [] };
  if (path.startsWith('/api/v1/management/loan-operations')) return { summary: {}, entries: [], audits: [], notice: '' };
  if (path.startsWith('/api/v1/activity-notifications')) return [];
  return {};
}

test('Continue to CIF opens the selected intake with reads only and keeps the application picker out of the way',async()=>{
 const root=new ManagementElement(),controller=new AbortController(),calls=[];
 const clientId='22222222-2222-4222-8222-222222222222',cifVersionId='33333333-3333-4333-8333-333333333333';
 try {
  const tasks=await mountManagementWorkspace({root,signal:controller.signal,setNavigation(){},activateNavigation(){},
   session:{user:{role:'management'},permissions:['client_onboarding.requirement.review']},
   sessionStore:{deviceId:()=> 'synthetic-device',nextDeviceSequence:()=>1},
   api:{async request(path,options={}){calls.push({path,options});
    if(path.endsWith('/cif-client'))return {application_reference:'INTAKE-123',client_id:clientId};
    if(path.includes('/cif/review-summary'))return {client_id:clientId,cif_version_id:cifVersionId,version_number:1,status:'draft',review_scope:'cif_information_only',full_name:'Synthetic applicant',phone_number:'00000000000',email:null,present_address:'Synthetic address'};
    if(path.endsWith('/case'))return {...response(path),status:'eligible_for_cif',client_id:clientId};
    return response(path);
   }}});
  await tasks.activate('management-clients-loans','management-office');
  const intake=root.querySelector('[data-office-onboarding]');intake.querySelector('[name="applicationReference"]').value='INTAKE-123';
  fire(intake.querySelector('[data-case-lookup]'),'submit');await setImmediate();
  const next=intake.querySelector('[data-continue-cif]');assert.ok(next);
  fire(next,'click');await setImmediate();await setImmediate();
  assert.equal(root.querySelector('[data-office-step="cif"]').getAttribute('hidden'),null);
  assert.match(root.querySelector('[data-office-cif-review]').textContent,/Synthetic applicant/);
  assert.equal(root.querySelector('[data-cif-lookup]').getAttribute('open'),null);
  assert.equal(root.querySelector('[data-application-panel]').getAttribute('hidden'),'');
  assert.equal(calls.some(call=>call.options.method&&call.options.method!=='GET'),false);
 }finally{controller.abort();}
});

test('Management office workflow carries verified identity while lookup and application text stay candidates', async () => {
  const root = new ManagementElement();
  root.dataset = {};
  const calls = [];
  const controller = new AbortController();
  try {
    const tasks = await mountManagementWorkspace({
      root,
      api: { async request(path, options = {}) { calls.push({ path, options }); return response(path); } },
      session: {
        user: { role: 'management', roles: ['management'] },
        permissions: ['client_onboarding.requirement.review'],
      },
      signal: controller.signal,
      setNavigation() {},
      activateNavigation() {},
      sessionStore: {
        deviceId: () => 'synthetic-device',
        nextDeviceSequence: () => 1,
      },
    });

    await tasks.activate('management-clients-loans', 'management-office');
    const hub = root.querySelector('#management-clients-loans');
    const workflow = hub.querySelector('[data-office-workflow]');
    assert.ok(workflow);

    const buttons = workflow.querySelectorAll('[data-office-step-target]');
    assert.deepEqual(
      buttons.map((button) => button.attributes['data-office-step-target']),
      ['intake', 'cif', 'application', 'first-loan'],
    );

    const step=async index=>{fire(buttons[index],'click');await setImmediate();};
    const panels = workflow.querySelectorAll('[data-office-step]');
    assert.equal(panels.length, 4);
    assert.equal(panels[0].getAttribute('hidden'), null);
    for (const panel of panels.slice(1)) assert.equal(panel.getAttribute('hidden'), '');

    const intakeInput = panels[0].querySelector('[name="applicationReference"]');
    intakeInput.value = 'INTAKE-123';

    const baselineCalls = calls.length;
    await step(1);
    assert.equal(calls.length, baselineCalls, 'step navigation does not invent API authority');
    assert.equal(panels[0].getAttribute('hidden'), '');
    assert.equal(panels[1].getAttribute('hidden'), null);
    assert.equal(panels[1].querySelector('[name="applicationReference"]').value, '', 'typed text has no case authority');
    await step(0);
    fire(panels[0].querySelector('[data-case-lookup]'),'submit');await setImmediate();
    await step(1);
    assert.equal(panels[1].querySelector('[name="applicationReference"]').value,'INTAKE-123');
    const verifiedCalls=calls.length;

    await step(2);
    assert.equal(panels[2].querySelector('[name="intakeReference"]').value, 'INTAKE-123');
    panels[2].querySelector('[name="applicationReference"]').value = 'APP-456';

    await step(3);
    assert.equal(panels[3].querySelector('[name="intakeReference"]').value, 'INTAKE-123');
    assert.equal(panels[3].querySelector('[name="applicationReference"]').value, '', 'typed application reference has no saved or draft authority');
    assert.equal(buttons[3].getAttribute('aria-current'), 'step');
    assert.equal(buttons[0].getAttribute('aria-current'), null);

    await step(0);
    intakeInput.value = 'INTAKE-OTHER';
    const firstLoanIntake=panels[3].querySelector('[name="intakeReference"]');
    await step(1);
    assert.equal(buttons[1].getAttribute('aria-current'), 'step', 'editing a candidate does not replace the verified case');
    assert.equal(firstLoanIntake.value,'INTAKE-123');
    assert.equal(calls.length,verifiedCalls);
    assert.equal(buttons[1].getAttribute('aria-current'),'step');
    assert.equal(panels[1].querySelector('[name="applicationReference"]').value,'INTAKE-123');

    await step(2);
    firstLoanIntake.value='';
    panels[3].querySelector('[name="applicationReference"]').value='OTHER-APPLICATION';
    await step(3);
    assert.equal(firstLoanIntake.value,'INTAKE-123');
    assert.equal(buttons[3].getAttribute('aria-current'),'step');
    assert.equal(panels[3].querySelector('[name="applicationReference"]').value,'OTHER-APPLICATION');
    firstLoanIntake.value='OTHER-INTAKE';await step(0);await step(3);
    assert.equal(buttons[0].getAttribute('aria-current'),'step');
    assert.match(workflow.querySelector('[data-office-case-feedback]').textContent,/different case/i);
    const staleConflict=workflow.querySelector('[data-office-show-existing]');
    await step(0);
    fire(staleConflict,'click');
    assert.equal(buttons[0].getAttribute('aria-current'),'step','A superseded conflict control cannot change the current stage');
  } finally {
    controller.abort();
  }
});
