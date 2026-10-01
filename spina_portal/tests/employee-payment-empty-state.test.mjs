import assert from 'node:assert/strict';
import { setImmediate } from 'node:timers/promises';
import test from 'node:test';

import { mountEmployeeOperations } from '../assets/employee-operations.js';
import { mountPaymentProofs } from '../assets/payment-proofs.js';
import { Element } from './helpers/dom.mjs';

const SELF='10000000-0000-4000-8000-000000000001';
const DEVICE='30000000-0000-4000-8000-000000000001';

function emptyEmployeeWorkspace() {
  return {
    contract_version:1,
    actor:{user_id:SELF,employee_id:null,device_id:DEVICE,is_owner:true,is_staff_manager:false},
    capabilities:{
      can_self_service:false,can_manage_staff:true,can_configure:true,can_prepare_payroll:true,
      can_approve_payroll:true,can_record_payments:true,can_assign_tasks:true,can_review_requests:true,
      can_review_shortages:true,can_prepare_accounting:true,can_view_statutory:true,
      can_report_shortage:false,can_record_advances:true,
    },
    setup_missing:[
      'The real owner account must be configured privately',
      'No employee profile is mapped to this account',
    ],
    profiles:[],schedules:[],backups:[],calendar:[],statutory_months:[],statutory_remittances:[],
    payroll_history:[],attendance:[],attendance_days:[],requests:[],leave_balances:[],leave_ledger:[],
    tasks:[],advances:[],shortages:[],payroll:[],payments:[],accounting_preparations:[],
    account_candidates:[],last_result:null,
  };
}

test('empty Management employee workspace is compact but keeps setup diagnostics available', async () => {
  const root = new Element();
  const controller = new AbortController();
  try {
    mountEmployeeOperations({
      root,
      session:{user:{id:SELF,role:'management',roles:['management']}},
      signal:controller.signal,
      api:{request:async()=>emptyEmployeeWorkspace()},
    });
    await setImmediate();

    assert.match(root.textContent,/Employee work and pay/);
    assert.match(root.textContent,/Employee setup incomplete/i);
    assert.ok(root.querySelector('[data-employee-work-summary]'));
    assert.equal(root.querySelectorAll('.employee-record-section').length,0);

    const setupDetails=root.querySelector('[data-employee-setup-details]');
    assert.ok(setupDetails);
    assert.equal(setupDetails.getAttribute('open'),null);
    assert.match(setupDetails.textContent,/real owner account/i);
    assert.match(setupDetails.textContent,/No employee profile/i);

    assert.doesNotMatch(root.textContent,/No requests and decisions are available/i);
    assert.doesNotMatch(root.textContent,/No extra tasks are available/i);
    assert.doesNotMatch(root.textContent,/No advances and repayments are available/i);
    assert.doesNotMatch(root.textContent,/No shortage cases are available/i);
    assert.doesNotMatch(root.textContent,/No payslips and payroll are available/i);
  } finally {
    controller.abort();
  }
});

test('empty Management payment evidence review uses one compact zero-state row', async () => {
  const root = new Element();
  const controller = new AbortController();
  try {
    mountPaymentProofs({
      root,
      mode:'management',
      signal:controller.signal,
      api:{request:async()=>({proofs:[],capability:{upload_available:false},has_more:false})},
    });
    await new Promise((resolve)=>setTimeout(resolve,0));

    assert.ok(root.querySelector('[data-payment-proof-empty]'));
    assert.match(root.textContent,/No payment evidence awaiting review/i);
    assert.ok(root.querySelector('[data-proof-refresh]'));
    assert.equal(root.querySelectorAll('.empty-state').length,0);
    assert.doesNotMatch(root.textContent,/No payment-proof submissions on this page/i);
  } finally {
    controller.abort();
  }
});
