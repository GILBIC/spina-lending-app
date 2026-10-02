import assert from 'node:assert/strict';
import test from 'node:test';
import {Element,fire} from './helpers/dom.mjs';
import {staffInviteMarkup} from '../assets/staff-invite.js';
import * as management from '../assets/roles/management.js';
const tick=()=>new Promise(resolve=>setImmediate(resolve));
const session={user:{id:'manager'},permissions:['account.manage']};
test('verified invitation resets only its form and refreshes staff locally, with saved/read-failed distinction',async()=>{
 assert.ok(management.bindStaffInvite);const root=new Element();root.innerHTML=staffInviteMarkup(session)+'<input name="unrelated" value="Keep me" />';const form=root.querySelector('#management-staff-invite-form'),other=root.querySelector('[name="unrelated"]');
 form.querySelector('[name="fullName"]').value='New Employee';form.querySelector('[name="username"]').value='new.employee';form.querySelector('[name="email"]').value='staff@example.test';form.querySelector('[name="role"]').value='employee';let resets=0,reads=0;form.reset=()=>resets++;
 const h=management.bindStaffInvite({root,session,api:{async request(){return {invitation_sent:true,account:{id:'10000000-0000-4000-8000-000000000001',username:'new.employee',email:'staff@example.test',roles:['employee']}};}},async refreshStaff(){reads++;return false;}});
 fire(form,'submit');await tick();assert.equal(resets,1);assert.equal(reads,1);assert.equal(root.querySelector('[name="unrelated"]'),other);assert.match(root.textContent,/Invitation sent; staff list refresh failed/);h.dispose();
});
test('wrong invitation result stays locked and does not clear or resubmit the draft',async()=>{
 assert.ok(management.bindStaffInvite);const root=new Element();root.innerHTML=staffInviteMarkup(session);const form=root.querySelector('#management-staff-invite-form');for(const [name,value]of Object.entries({fullName:'New Staff',username:'staff.name',email:'staff@example.test',role:'employee'}))form.querySelector(`[name="${name}"]`).value=value;let writes=0,resets=0;form.reset=()=>resets++;
 const h=management.bindStaffInvite({root,session,api:{async request(){writes++;return {};}}});fire(form,'submit');await tick();fire(form,'submit');await tick();assert.equal(writes,1);assert.equal(resets,0);assert.equal(h.isWritePending(),true);h.dispose();
});
