import assert from 'node:assert/strict';
import test from 'node:test';
import {Element,fire} from './helpers/dom.mjs';
import {bindEmployeeOfficeCase} from '../assets/employee-office-case.js';
test('Employee navigation carries only verified context and keeps typed candidates separate',async()=>{
 const root=new Element();root.innerHTML='<section id="employee-onboarding"><input name="applicationReference" /></section><section id="employee-cif-review"><input name="applicationReference" /></section><section id="employee-application-review"><input name="intakeReference" /><input name="applicationReference" /></section><section id="employee-first-loan"><input name="intakeReference" /><input name="applicationReference" /></section>';
 const handle=bindEmployeeOfficeCase({root,navigate(){},getSession:()=>({user:{id:'staff',role:'employee'}})});
 await handle.activate('intake');const input=root.querySelector('#employee-onboarding').querySelector('input');input.value='UNVERIFIED';fire(input,'input');await handle.activate('cif');
 const cif=root.querySelector('#employee-cif-review').querySelector('input');assert.equal(cif.value,'');
 handle.coordinator.acceptVerifiedContext({mode:'saved-case',intakeReference:'INTAKE-A',clientId:'client-a'},handle.coordinator.getGeneration());await handle.activate('cif');assert.equal(cif.value,'INTAKE-A');
 await handle.activate('application');const application=root.querySelector('#employee-application-review');application.querySelector('[name="applicationReference"]').value='UNVERIFIED-APP';
 await handle.activate('first-loan');const first=root.querySelector('#employee-first-loan');assert.equal(first.querySelector('[name="applicationReference"]').value,'');
 handle.coordinator.acceptVerifiedContext({mode:'saved-case',intakeReference:'INTAKE-A',clientId:'client-a',applicationReference:'DRAFT-A',applicationSaved:false},handle.coordinator.getGeneration());await handle.activate('first-loan');assert.equal(first.querySelector('[name="applicationReference"]').value,'DRAFT-A');assert.match(first.textContent,/Draft reference — not saved/);
 input.value='INTAKE-B';fire(input,'input');await handle.activate('cif');assert.equal(cif.value,'INTAKE-A');assert.equal(handle.coordinator.getContext().intakeReference,'INTAKE-A');handle.dispose();assert.equal(handle.coordinator.getContext().mode,'none');
});
