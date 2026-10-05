import assert from 'node:assert/strict';
import test from 'node:test';
import {Element} from './helpers/dom.mjs';
import {mountOfficeOnboarding} from '../assets/office-onboarding.js';
import {officeCaseBanner,officeStageLabels} from '../assets/employee-office-case.js';
import {mountEmployeeWorkspace} from '../assets/employee-workspace.js';
import {mountManagementWorkspace} from '../assets/roles/management.js';
import {setImmediate} from 'node:timers/promises';

test('Office entry gives New its own first action and keeps exact-reference continuation in its real form',()=>{
 const root=new Element();const dispose=mountOfficeOnboarding({root,api:{request:async()=>({})},session:{user:{id:'staff',role:'employee'},permissions:['client_onboarding.requirement.review']}});
 try{const start=root.querySelector('[data-new-intake]'),lookup=root.querySelector('[data-case-lookup]');
 assert.ok(start);assert.equal(start.parentElement.tag,'div');assert.equal(start.parentElement.parentElement,root);assert.ok(root.innerHTML.indexOf('data-new-intake')<root.innerHTML.indexOf('data-case-lookup'));
 assert.match(root.textContent,/Start an intake for an applicant visiting the office/);assert.match(lookup.textContent,/Continue existing intake.*Enter a saved office intake reference/);
 assert.equal(lookup.querySelector('[name="applicationReference"]').getAttribute('required'),'');assert.equal(lookup.querySelector('[type="submit"]').textContent,'Open intake case');
 }finally{dispose();}
});
for(const role of ['management','employee'])test(`${role} actual Office entry preserves stage navigation and exposes intake and finder`,async()=>{
 const root=new Element(),controller=new AbortController();let navigation,handle;
 try{await (role==='management'?mountManagementWorkspace:mountEmployeeWorkspace)({root,session:{user:{id:'staff',role,roles:[role]},permissions:['client_onboarding.requirement.review']},signal:controller.signal,setNavigation:items=>navigation=items,activateNavigation(){},registerWorkspaceHandle:value=>handle=value,api:{request:async path=>path==='/api/v1/account'?{profile:{full_name:'Synthetic operator'},devices:[]}:path.includes('activity-notifications')?[]:{}}});
 if(role==='management'){await handle.activate('management-clients-loans','management-office');assert.deepEqual(navigation.map(item=>item.label),['Today','Clients & loans','Collections','Accounting','People & operations','Account']);assert.deepEqual(root.querySelectorAll('[data-office-step-target]').map(el=>el.getAttribute('data-office-step-target')),['intake','cif','application','first-loan']);}
 else{handle.activate('employee-onboarding');await setImmediate();await setImmediate();assert.deepEqual(navigation.filter(item=>item.group==='Office work').map(item=>item.label),Object.values(officeStageLabels));}
 assert.ok(root.querySelector('[data-new-intake]'));assert.ok(root.querySelector('[data-office-finder]'));
 assert.ok(root.querySelector('[data-case-lookup]').querySelector('[type="submit"]'));
 }finally{controller.abort();}
});
test('compact private banner labels returned intake status separately and preserves exact identity and unknown stage status',()=>{
 const context={mode:'saved-case',intakeReference:'INT/EXACT',applicantName:'Synthetic Name',applicationReference:'APP/EXACT',applicationSaved:true,stageFacts:{intake:{status:'eligible_for_cif'},application:{status:'awaiting_confirmation',versionNumber:2}}};
 const markup=officeCaseBanner(context,'application');
 assert.match(markup,/INT\/EXACT/);assert.match(markup,/APP\/EXACT/);assert.match(markup,/Intake status: Eligible for CIF/);assert.match(markup,/Application status: awaiting_confirmation.*Saved version 2/);assert.match(markup,/CIF status: Not loaded/);assert.match(markup,/Viewing Loan application/);
 assert.deepEqual(Object.values(officeStageLabels),['Intake & requirements','Client information (CIF)','Loan application','Approval & release']);
});
