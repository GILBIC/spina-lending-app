import assert from 'node:assert/strict';
import { setImmediate } from 'node:timers/promises';
import test from 'node:test';

import { mountManagementCollectionActions } from '../assets/management-collection-actions.js';
import { Element, fire } from './helpers/dom.mjs';

const ids = [
  '11111111-1111-4111-8111-111111111111',
  '22222222-2222-4222-8222-222222222222',
  '33333333-3333-4333-8333-333333333333',
  '44444444-4444-4444-8444-444444444444',
];

const commonBlockers = [
  'Signed-contract schedule has not been registered.',
  'Contract schedule/payment allocation is not DPD-ready (contract_schedule_required).',
];

const tick=async()=>{await setImmediate();await setImmediate();};

function activationData() {
  return {
    permission:true,
    loans:[
      {
        loan_id:ids[0],client_name:'Blocked One',loan_number:'LN-1',loan_type_name:'Regular',
        remaining_balance:'4800.00',is_active:false,can_activate:false,can_deactivate:false,
        blockers:[...commonBlockers],
      },
      {
        loan_id:ids[1],client_name:'Blocked Two',loan_number:'LN-2',loan_type_name:'7x7',
        remaining_balance:'3000.00',is_active:false,can_activate:false,can_deactivate:false,
        blockers:[...commonBlockers],
      },
      {
        loan_id:ids[2],client_name:'Ready Client',loan_number:'LN-3',loan_type_name:'Regular',
        remaining_balance:'2500.00',is_active:false,can_activate:true,can_deactivate:false,blockers:[],
      },
      {
        loan_id:ids[3],client_name:'Active Client',loan_number:'LN-4',loan_type_name:'Regular',
        remaining_balance:'1800.00',is_active:true,can_activate:false,can_deactivate:true,blockers:[],
      },
    ],
  };
}

test('Contract collection summarizes readiness and keeps repeated technical blockers collapsed', async (t) => {
  const root=new Element();
  const controller=new AbortController();
  t.after(()=>controller.abort());
  mountManagementCollectionActions({
    root,
    session:{user:{role:'management'},permissions:['lending.contract_collection.activate']},
    signal:controller.signal,
    api:{request:async()=>activationData()},
    confirm:()=>true,
  });
  await tick();

  const summary=root.querySelector('[data-contract-readiness-summary]');
  assert.ok(summary);
  assert.match(summary.textContent,/1\s+Active/i);
  assert.match(summary.textContent,/1\s+Ready/i);
  assert.match(summary.textContent,/2\s+Blocked/i);

  const common=root.querySelector('[data-contract-common-blockers]');
  assert.ok(common);
  assert.match(common.textContent,/2 loans need a verified signed repayment schedule/i);
  assert.equal((common.textContent.match(/contract_schedule_required/g)||[]).length,0);

  const rows=root.querySelectorAll('[data-contract-loan]');
  assert.equal(rows.length,4);
  const blocked=rows.find((row)=>row.textContent.includes('Blocked One'));
  assert.ok(blocked);
  assert.match(blocked.textContent,/Blocked/);
  const details=blocked.querySelector('[data-contract-technical-details]');
  assert.ok(details);
  assert.equal(details.getAttribute('open'),null);
  assert.match(details.textContent,/contract_schedule_required/);

  const ready=rows.find((row)=>row.textContent.includes('Ready Client'));
  assert.ok(ready.querySelector('[data-contract-activate]'));
});

test('Collection actions shows one local workflow at a time without starting mutations', async (t) => {
  const root=new Element();
  const calls=[];
  const controller=new AbortController();
  t.after(()=>controller.abort());
  mountManagementCollectionActions({
    root,
    session:{
      user:{role:'management'},
      permissions:[
        'lending.contract_collection.activate',
        'lending.no_collection.manage',
        'collection.void.unremitted',
      ],
    },
    signal:controller.signal,
    api:{request:async(path,options={})=>{calls.push({path,options});return activationData();}},
    confirm:()=>true,
  });
  await tick();

  const tabs=root.querySelectorAll('[data-management-collection-tab]');
  assert.deepEqual(
    tabs.map((tab)=>tab.getAttribute('data-management-collection-tab')),
    ['contract','no-collection','void'],
  );
  const contract=root.querySelector('[data-management-collection-panel="contract"]');
  const noCollection=root.querySelector('[data-management-collection-panel="no-collection"]');
  const voidPanel=root.querySelector('[data-management-collection-panel="void"]');
  assert.equal(contract.getAttribute('hidden'),null);
  assert.equal(noCollection.getAttribute('hidden'),'');
  assert.equal(voidPanel.getAttribute('hidden'),'');

  const before=calls.length;
  fire(tabs[1],'click');
  assert.equal(contract.getAttribute('hidden'),'');
  assert.equal(noCollection.getAttribute('hidden'),null);
  assert.equal(voidPanel.getAttribute('hidden'),'');
  assert.equal(calls.length,before,'switching local tabs must not perform a server action');
  assert.equal(tabs[1].getAttribute('aria-selected'),'true');
});
