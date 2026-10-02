import assert from 'node:assert/strict';
import test from 'node:test';
import {Element,fire} from './helpers/dom.mjs';
import {renderManagedDevicePanel,bindManagedDevicePanel} from '../assets/management-devices.js';
import {managementAlertsAuditMarkup,bindManagementAlertsAudit} from '../assets/management-alerts-audit.js';
const visible=(root,selector)=>root.querySelectorAll(selector).filter(node=>node.getAttribute('hidden')===null);
test('36 devices default to Pending; All reveals ten at a time with original action indices',()=>{
 const root=new Element();root.innerHTML=renderManagedDevicePanel({full_name:'Staff'},Array.from({length:36},(_,i)=>({id:`d${i}`,status:i===12||i===29?'pending':i===35?'other':'active'})),{canManageDevices:true});
 const state={};const cleanup=bindManagedDevicePanel(root,{state});
 assert.equal(visible(root,'[data-managed-device-status]').length,2);assert.equal(state.filter,'pending');
 fire(root.querySelector('[data-managed-device-filter="all"]'),'click');assert.equal(visible(root,'[data-managed-device-status]').length,10);
 fire(root.querySelector('[data-managed-device-more]'),'click');assert.equal(visible(root,'[data-managed-device-status]').length,20);assert.equal(root.querySelectorAll('.managed-device-action')[12].getAttribute('data-managed-device-index'),'12');
 cleanup();root.innerHTML=renderManagedDevicePanel({},[{status:'active'}]);bindManagedDevicePanel(root,{state});assert.equal(state.filter,'all');
});
test('audit retains 100 loaded rows, reveals10 then20, and filters without discarding evidence',()=>{
 const root=new Element();root.innerHTML=managementAlertsAuditMarkup({event_total_count:150,visible_domains:['approvals'],events:Array.from({length:100},(_,i)=>({event_key:`e${i}`,domain:i<12?'approvals':'unknown',title:'Repeated title',reason:`Reason ${i}`}))});
 const cleanup=bindManagementAlertsAudit(root);assert.equal(root.querySelectorAll('[data-audit-event-key]').length,100);assert.equal(visible(root,'[data-audit-event-key]').length,10);
 fire(root.querySelector('[data-audit-more]'),'click');assert.equal(visible(root,'[data-audit-event-key]').length,20);
 fire(root.querySelector('[data-alert-domain-filter="approvals"]'),'click');assert.equal(visible(root,'[data-audit-event-key]').length,10);fire(root.querySelector('[data-audit-more]'),'click');assert.equal(visible(root,'[data-audit-event-key]').length,12);assert.match(root.textContent,/150 authorized/);assert.match(root.textContent,/100 loaded/);cleanup();
});
