# Employee Operations API â€” contract v1

Frozen public boundary, 20 September 2026. Requests are strict: unknown fields are 422 errors. Money is a decimal string (e.g. `"100.00"`), never a JSON number. Dates are ISO `YYYY-MM-DD`; timestamps include an offset; clock times are `HH:MM`. Week start is Sunday; work_days uses ISO Monday=1 through Sunday=7. All identifiers are UUIDs. Null is accepted only where shown. No provider transfers are initiated.

## HTTP and recovery

Both endpoints use the existing bearer Authorization and X-Device-Id. Backend revalidates the active account/device transactionally. Owner is the explicitly configured SPINA_EMPLOYEE_OWNER_USER_ID. A manager additionally needs the narrow employee_operations.manage grant and an active profile with staff_manager=true. The combined worker is not granted the Management role.

- GET `/api/v1/employee-operations/workspace` accepts optional `request_id` UUID. It returns only authorized domain records and, if supplied, the actor/device-bound recorded result for that request, otherwise `last_result:null`.
- POST `/api/v1/employee-operations/actions` takes ONE command below. Every command includes action, request_id, id, expected_version. The id is the stable domain record ID, employee_id is the core.users ID. Profile id MUST equal employee_id. Creation requires expected_version=0; updates require current version. Attendance id is the stable event ID and cannot be edited.
- Success is HTTP200: `{ "request_id":UUID, "id":UUID, "version":1, "status":"accepted", "replayed":false, "message":"..." }`. status is `accepted` or `pending_review`; replay returns the original result with replayed=true. State-specific status is read in the resulting workspace record.
- Error shape is `{ "detail": { "code":"employee_conflict", "message":"..." } }`. 403 authority/privacy; 409 stale version, conflicting idempotency key, unresolved input/state; 422 invalid typed request; 503 unavailable private setup/database. Never show success on errors.
- Retrying the SAME request_id and exact payload under the same account/device returns its prior result. Changed payload, employee or device is a conflict. After timeout read workspace?request_id=...; do not generate another financial request ID. Financial mutations stay online-only. A missing readback result means unconfirmed, not rejected/succeeded.

## Workspace response

All listed keys are always present. Empty visible collections are []. Private staff values are never seeded.

```json
{
 "contract_version":1,
 "actor":{"user_id":"00000000-0000-4000-8000-000000000001","device_id":"00000000-0000-4000-8000-000000000099","is_owner":false,"is_staff_manager":false,"employee_id":"00000000-0000-4000-8000-000000000001"},
 "capabilities":{"can_self_service":true,"can_manage_staff":false,"can_configure":false,"can_prepare_payroll":false,"can_approve_payroll":false,"can_record_payments":false,"can_assign_tasks":false,"can_review_requests":false,"can_review_shortages":false,"can_prepare_accounting":false,"can_view_statutory":false,"can_report_shortage":true,"can_record_advances":false},
 "setup_missing":[],
 "account_candidates":[],"payroll_history":[],"profiles":[],"schedules":[],"backups":[],"calendar":[],"statutory_months":[],"statutory_remittances":[],
 "attendance":[],"attendance_days":[],"requests":[],"leave_balances":[],"leave_ledger":[],"tasks":[],"advances":[],"shortages":[],"payroll":[],"payments":[],"accounting_preparations":[],"history":[],"last_result":null
}
```

Each persisted domain record uses `{id,employee_id,version,status,created_at,updated_at,created_by,allowed_actions,payload}`. employee_id is null for global records. allowed_actions is a string array drawn from the exact action names below; hiding controls is not an authority grant. payload is a typed domain projection described below, never a user-editable arbitrary JSON command.

- profiles payload: profile_save fields minus envelope/employee_id, plus full_name from core.users, is_self, can_review, can_approve_payroll, can_approve_advance. Rate/profile history is retained; current display is the latest version.
- schedules payload: schedule_save fields; approved shift requests create a new effective schedule. Older versions remain authoritative for prior dates.
- backups/calendar/statutory_months/statutory_remittances payload: corresponding create fields. Remittance entries record actual agency payment evidence, never automatic filing/payment.
- attendance payload: attendance_record fields plus received_at. status accepted/pending_review. Out-of-order/missing/conflicting chains appear pending_review; approval uses correction_request rather than editing events. The device_id is the authenticated session's registered database device UUID, not a raw installation string. Offline queue must bind account and registered device and retain request/event IDs and captured_at, sequence, previous_event_id. Server date/anomaly review is authoritative.
- attendance_days are computed objects `{employee_id,work_date,working_minutes,unpaid_break_minutes,status,event_ids,issues}`; status accepted/pending_review and issues string[]. Client must not calculate salary from these.
- requests payload: corresponding correction/leave/shift/overtime/conversion request fields, plus request_kind (correction/leave/shift/overtime/leave_conversion), decision_reason, decided_by, paid_minutes where decided. status pending/approved/rejected/cancelled/settled. Future approved leave/shift/conversion can be cancelled by an independent authorized reviewer; historical time needs a correction. request_decide id targets the request ID.
- leave_balances are computed `{employee_id,as_of,accrued_minutes,opening_minutes,used_minutes,reserved_minutes,available_minutes,eligible}`. ledger payload includes as_of,minutes,kind,reason and linked_request_id where relevant. Ordinary leave minutes are eight-hour-day units. Requests reserve approved credits; conversion settlement consumes them once.
- tasks payload: task_save fields plus notes/progress reason. status todo/in_progress/done/cancelled. Only assigner/owner can reopen completed tasks; assignee can progress.
- advances payload: advance_request fields plus disbursed_amount,repaid_amount,outstanding_amount (money strings), decision_reason,approved_by,disbursed_at and repayment_history (list of amount,occurred_at,reference,source). status requested/approved/rejected/disbursed/repaid/terms_pending. Terms changes require acknowledgment and renewed independent approval. No interest/fees. Only actual disbursement creates outstanding principal.
- shortages payload: shortage_report fields plus explanation,decision_reason,response_opportunity,decided_by,shortage_amount. status reported/responded/confirmed/dismissed/reversed. Owner alone decides all employees' shortage cases. Reported issues never automatically forfeit the benefit or deduct wages.
- payroll payload: payroll_prepare fields plus period_end,components (list `{code,label,amount}`; deductions negative), gross_pay,deductions,net_pay,paid_amount,balance_due (money strings),input_fingerprint,input_versions,issues (string[]),advance_allocations,statutory_allocations,approved_by,approval_reason,original_payroll_id (null unless adjustment). status draft/approved/rejected/stale/partially_paid/paid; separate loss-recovery evidence has allocated/cancelled status. Partial/failed/pending individual attempts are in payments. Approved snapshots cannot be overwritten after any completed payment; paid corrections use payroll_adjustment with a NEW id.
- payments payload: payroll_payment/advance disbursement/repayment fields plus payroll_id or advance_id, recorded_by. status completed/pending/failed. A reference alone cannot complete salary payment: cash needs acknowledgment; transfer needs settlement_evidence. Amount cannot exceed outstanding balance.
- accounting_preparations payload: accounting_prepare fields. status draft. These are supporting draft records only; existing owner posting/reconciliation controls stay authoritative. Never claim a draft posts a journal or confirms payment.

## Domain rules surfaced to clients

Setup missing is a list of plain-language missing inputs (owner mapping, staff profile, schedule, leave opening balance, monthly statutory review, holiday coverage). Missing mandatory payroll inputs cause 409 and do not fabricate a zero-pay successful run. Salary input changes make unpaid approval stale; the owner/reviewer regenerates then reapproves. A payroll line with a review issue does not block other employees.

Profile/schedule/calendar/backup/statutory/leave-opening setup, shortage decisions, salary payment and payroll adjustment are owner-only. Managers may prepare payroll, assign tasks, prepare accounting and review OTHER employees' requests/advances/payroll. Named, dated backup grants apply only to explicit duties and never self-approval. Employees see their own records. Employees submit own requests/attendance/advance and explanation; authorized reviewers cannot forge employee acknowledgment.

Statutory_month_save stores reviewed monthly employee/employer amounts with compensation basis and effective official-source evidence. Weekly payroll allocates across month payroll Saturdays without repeating the full monthly amount and reconciles prior recorded allocations. Current BIR weekly 2023-onward withholding computation applies unless a reviewed explicit override/basis is supplied. Unknown coverage/classification does not imply exemption. Payroll_kind thirteenth_month and separation use verified eligible basic-pay history, reviewed imported opening inputs and paid snapshots; no invented historical earnings. Leave conversion requires an approved conversion request. Shortage payroll recovery is unavailable by ordinary shortcut: only a separate owner adjustment with all lawful-basis, responsibility, response and cap evidence is eligible; no automatic deduction/advance laundering.

## Ordering, history and required setup clarifications

- Attendance previous_event_id chains per EMPLOYEE and Manila work date. First event each date uses null; later events reference the latest same-day captured event, including a known predecessor on another registered device. Compare captured_at as aware instants (then id to detect ambiguous equal captures), not string order. sequence starts1 for each registered DEVICE and Manila date and increases. Offline pending entries extend their existing daily chain; simultaneous/conflicting chains require review. A valid incomplete prefix is an accepted EVENT, while its incomplete DAY remains unavailable to payroll.
- actor.device_id is the current registered database device UUID. Owner-only account_candidates contains {user_id,full_name,username,roles}; everyone else receives []. Account selection never grants owner authority.
- capabilities.can_report_shortage permits own reports or scoped staff reports; can_record_advances is owner-only. Existing advance transitions still require the per-record allowed_actions.
- workspace.history contains {record_id,employee_id,domain,version,action,actor_user_id,created_at,payload,status}, restricted by the exact authorized domain/record/employee identity. Task-only backup profiles expose names/activity/reviewer flags without wages or private salary history.
- advances in terms_pending include proposed_terms and prior_status alongside the existing agreement. A second proposal waits for review. Changing terms cannot bypass an already partly paid payroll reservation.
- profile_save may specify ordinary_leave_days_per_year (default5,5..365) and leave_eligible_from (defaultnull) to preserve reviewed better terms. Leave conversion supports1..1,000,000 minutes and must fit eligible available credits. Special statutory leave approval requires explicit paid_minutes plus eligibility evidence; agency benefits remain separately reviewed.
- statutory_month_save prior_employee_deductions is nullable during configuration, but payroll requires an explicitly reviewed amount (including0). It represents deductions already taken before Spina for that employee/month, avoiding repeated collection. Unknown values block payroll. Cross-month weeks allocate by days within each month and reconcile reviewed remaining monthly totals.
- All request/attendance/advance/shortage creations, immutable ledger/history/remittance entries, new schedules and payroll adjustments require expected_version0 and a new domain ID. They cannot reset prior decisions or principal balances. Use the named update transition; retries reuse the original request_id.
- A completed GCash/bank transfer reference cannot be counted twice for the same payroll/method under fresh request IDs. External advance references and agency/month remittance references likewise cannot be reused. Pending or failed attempts are not settlement.
- Approved/partly paid/paid payroll reservations participate in input fingerprints. A competing draft must regenerate after another approval changes statutory or principal reservations. Historical payroll imports cannot be used for earlier as-of dates and annual facts include linked basic-pay and tax corrections.
- accounting_prepare journal payload includes journal_entry_id from the EXISTING accounting journal draft created/updated in the same transaction. Supporting reconciliation notes never post money. Owner retains existing final posting controls.
- Profile, daily-rate and schedule inputs remain private actual setup; no people, owner mapping, wages, balances or holiday/contribution facts are seeded.

## Exact commands

Every command has a strict finite schema below. Required fields must be sent. Optional defaults may be omitted; a null setup input may still block a dependent payroll calculation. Money uses decimal strings only. The tables are generated from employee_operations_models.py, the executable source of truth.

### accounting_prepare

| Field | Type / constraint | Required |
| --- | --- | --- |
| request_id | `{"format":"uuid","type":"string"}` | Yes |
| id | `{"format":"uuid","type":"string"}` | Yes |
| expected_version | `{"minimum":0,"type":"integer"}` | Yes |
| action | `{"const":"accounting_prepare","type":"string"}` | Yes |
| preparation_kind | `{"enum":["journal","reconciliation"],"type":"string"}` | Yes |
| description | `{"maxLength":2000,"minLength":1,"type":"string"}` | Yes |
| as_of | `{"format":"date","type":"string"}` | Yes |
| evidence | `{"maxLength":2000,"minLength":1,"type":"string"}` | Yes |
| lines | `{"items":{"$ref":"#/$defs/AccountingLine"},"maxItems":100,"type":"array"}` | No |
| statement_balance | `{"anyOf":[{"decimal_places":2,"ge":0,"max_digits":14,"type":"string"},{"type":"null"}],"default":null}` | No |
| ledger_balance | `{"anyOf":[{"decimal_places":2,"ge":0,"max_digits":14,"type":"string"},{"type":"null"}],"default":null}` | No |

### advance_decide

| Field | Type / constraint | Required |
| --- | --- | --- |
| request_id | `{"format":"uuid","type":"string"}` | Yes |
| id | `{"format":"uuid","type":"string"}` | Yes |
| expected_version | `{"minimum":0,"type":"integer"}` | Yes |
| employee_id | `{"format":"uuid","type":"string"}` | Yes |
| action | `{"const":"advance_decide","type":"string"}` | Yes |
| decision | `{"enum":["approved","rejected"],"type":"string"}` | Yes |
| reason | `{"maxLength":2000,"minLength":1,"type":"string"}` | Yes |

### advance_disburse

| Field | Type / constraint | Required |
| --- | --- | --- |
| request_id | `{"format":"uuid","type":"string"}` | Yes |
| id | `{"format":"uuid","type":"string"}` | Yes |
| expected_version | `{"minimum":0,"type":"integer"}` | Yes |
| employee_id | `{"format":"uuid","type":"string"}` | Yes |
| action | `{"const":"advance_disburse","type":"string"}` | Yes |
| occurred_at | `{"format":"date-time","type":"string"}` | Yes |
| payment_method | `{"enum":["cash","gcash","bank"],"type":"string"}` | Yes |
| reference | `{"maxLength":2000,"minLength":1,"type":"string"}` | Yes |
| settlement_evidence | `{"maxLength":2000,"minLength":1,"type":"string"}` | Yes |
| employee_acknowledgment | `{"maxLength":2000,"minLength":1,"type":"string"}` | Yes |

### advance_repay

| Field | Type / constraint | Required |
| --- | --- | --- |
| request_id | `{"format":"uuid","type":"string"}` | Yes |
| id | `{"format":"uuid","type":"string"}` | Yes |
| expected_version | `{"minimum":0,"type":"integer"}` | Yes |
| employee_id | `{"format":"uuid","type":"string"}` | Yes |
| action | `{"const":"advance_repay","type":"string"}` | Yes |
| amount | `{"decimal_places":2,"ge":0,"max_digits":14,"type":"string"}` | Yes |
| occurred_at | `{"format":"date-time","type":"string"}` | Yes |
| reference | `{"maxLength":2000,"minLength":1,"type":"string"}` | Yes |
| settlement_evidence | `{"maxLength":2000,"minLength":1,"type":"string"}` | Yes |

### advance_request

| Field | Type / constraint | Required |
| --- | --- | --- |
| request_id | `{"format":"uuid","type":"string"}` | Yes |
| id | `{"format":"uuid","type":"string"}` | Yes |
| expected_version | `{"minimum":0,"type":"integer"}` | Yes |
| employee_id | `{"format":"uuid","type":"string"}` | Yes |
| action | `{"const":"advance_request","type":"string"}` | Yes |
| amount | `{"decimal_places":2,"ge":0,"max_digits":14,"type":"string"}` | Yes |
| reason | `{"maxLength":2000,"minLength":1,"type":"string"}` | Yes |
| installments | `{"items":{"$ref":"#/$defs/Installment"},"maxItems":104,"minItems":1,"type":"array"}` | Yes |
| employee_acknowledgment | `{"maxLength":2000,"minLength":1,"type":"string"}` | Yes |
| payroll_authorization | `{"maxLength":2000,"minLength":1,"type":"string"}` | Yes |

### advance_terms

| Field | Type / constraint | Required |
| --- | --- | --- |
| request_id | `{"format":"uuid","type":"string"}` | Yes |
| id | `{"format":"uuid","type":"string"}` | Yes |
| expected_version | `{"minimum":0,"type":"integer"}` | Yes |
| employee_id | `{"format":"uuid","type":"string"}` | Yes |
| action | `{"const":"advance_terms","type":"string"}` | Yes |
| installments | `{"items":{"$ref":"#/$defs/Installment"},"maxItems":104,"minItems":1,"type":"array"}` | Yes |
| employee_acknowledgment | `{"maxLength":2000,"minLength":1,"type":"string"}` | Yes |
| payroll_authorization | `{"maxLength":2000,"minLength":1,"type":"string"}` | Yes |
| reason | `{"maxLength":2000,"minLength":1,"type":"string"}` | Yes |

### attendance_record

| Field | Type / constraint | Required |
| --- | --- | --- |
| request_id | `{"format":"uuid","type":"string"}` | Yes |
| id | `{"format":"uuid","type":"string"}` | Yes |
| expected_version | `{"minimum":0,"type":"integer"}` | Yes |
| employee_id | `{"format":"uuid","type":"string"}` | Yes |
| action | `{"const":"attendance_record","type":"string"}` | Yes |
| event_type | `{"enum":["clock_in","break_start","break_end","clock_out"],"type":"string"}` | Yes |
| captured_at | `{"format":"date-time","type":"string"}` | Yes |
| device_id | `{"format":"uuid","type":"string"}` | Yes |
| previous_event_id | `{"anyOf":[{"format":"uuid","type":"string"},{"type":"null"}]}` | Yes |
| sequence | `{"minimum":1,"type":"integer"}` | Yes |
| offline | `{"type":"boolean"}` | Yes |

### backup_save

| Field | Type / constraint | Required |
| --- | --- | --- |
| request_id | `{"format":"uuid","type":"string"}` | Yes |
| id | `{"format":"uuid","type":"string"}` | Yes |
| expected_version | `{"minimum":0,"type":"integer"}` | Yes |
| action | `{"const":"backup_save","type":"string"}` | Yes |
| user_id | `{"format":"uuid","type":"string"}` | Yes |
| starts_on | `{"format":"date","type":"string"}` | Yes |
| ends_on | `{"format":"date","type":"string"}` | Yes |
| duties | `{"items":{"enum":["review_requests","approve_payroll","approve_advances","assign_tasks","prepare_payroll"],"type":"string"},"maxItems":5,"type":"array"}` | Yes |
| reason | `{"maxLength":2000,"minLength":1,"type":"string"}` | Yes |

### calendar_save

| Field | Type / constraint | Required |
| --- | --- | --- |
| request_id | `{"format":"uuid","type":"string"}` | Yes |
| id | `{"format":"uuid","type":"string"}` | Yes |
| expected_version | `{"minimum":0,"type":"integer"}` | Yes |
| action | `{"const":"calendar_save","type":"string"}` | Yes |
| work_date | `{"format":"date","type":"string"}` | Yes |
| day_kind | `{"enum":["ordinary","special_working","special_nonworking","regular_holiday","double_regular_holiday"],"type":"string"}` | Yes |
| source | `{"maxLength":2000,"minLength":1,"type":"string"}` | Yes |

### correction_request

| Field | Type / constraint | Required |
| --- | --- | --- |
| request_id | `{"format":"uuid","type":"string"}` | Yes |
| id | `{"format":"uuid","type":"string"}` | Yes |
| expected_version | `{"minimum":0,"type":"integer"}` | Yes |
| employee_id | `{"format":"uuid","type":"string"}` | Yes |
| action | `{"const":"correction_request","type":"string"}` | Yes |
| work_date | `{"format":"date","type":"string"}` | Yes |
| clock_in | `{"format":"date-time","type":"string"}` | Yes |
| clock_out | `{"format":"date-time","type":"string"}` | Yes |
| unpaid_break_minutes | `{"maximum":1440,"minimum":0,"type":"integer"}` | Yes |
| reason | `{"maxLength":2000,"minLength":1,"type":"string"}` | Yes |

### leave_balance_adjust

| Field | Type / constraint | Required |
| --- | --- | --- |
| request_id | `{"format":"uuid","type":"string"}` | Yes |
| id | `{"format":"uuid","type":"string"}` | Yes |
| expected_version | `{"minimum":0,"type":"integer"}` | Yes |
| employee_id | `{"format":"uuid","type":"string"}` | Yes |
| action | `{"const":"leave_balance_adjust","type":"string"}` | Yes |
| as_of | `{"format":"date","type":"string"}` | Yes |
| minutes | `{"maximum":1000000,"minimum":-1000000,"type":"integer"}` | Yes |
| kind | `{"enum":["opening","correction"],"type":"string"}` | Yes |
| reason | `{"maxLength":2000,"minLength":1,"type":"string"}` | Yes |

### leave_conversion_request

| Field | Type / constraint | Required |
| --- | --- | --- |
| request_id | `{"format":"uuid","type":"string"}` | Yes |
| id | `{"format":"uuid","type":"string"}` | Yes |
| expected_version | `{"minimum":0,"type":"integer"}` | Yes |
| employee_id | `{"format":"uuid","type":"string"}` | Yes |
| action | `{"const":"leave_conversion_request","type":"string"}` | Yes |
| as_of | `{"format":"date","type":"string"}` | Yes |
| minutes | `{"maximum":1000000,"minimum":1,"type":"integer"}` | Yes |
| reason | `{"maxLength":2000,"minLength":1,"type":"string"}` | Yes |

### leave_request

| Field | Type / constraint | Required |
| --- | --- | --- |
| request_id | `{"format":"uuid","type":"string"}` | Yes |
| id | `{"format":"uuid","type":"string"}` | Yes |
| expected_version | `{"minimum":0,"type":"integer"}` | Yes |
| employee_id | `{"format":"uuid","type":"string"}` | Yes |
| action | `{"const":"leave_request","type":"string"}` | Yes |
| work_date | `{"format":"date","type":"string"}` | Yes |
| minutes | `{"maximum":1440,"minimum":0,"type":"integer"}` | Yes |
| leave_kind | `{"enum":["ordinary","maternity","paternity","solo_parent","vawc","special_women","unpaid"],"type":"string"}` | Yes |
| reason | `{"maxLength":2000,"minLength":1,"type":"string"}` | Yes |
| eligibility_evidence | `{"default":"","maxLength":2000,"type":"string"}` | No |

### overtime_request

| Field | Type / constraint | Required |
| --- | --- | --- |
| request_id | `{"format":"uuid","type":"string"}` | Yes |
| id | `{"format":"uuid","type":"string"}` | Yes |
| expected_version | `{"minimum":0,"type":"integer"}` | Yes |
| employee_id | `{"format":"uuid","type":"string"}` | Yes |
| action | `{"const":"overtime_request","type":"string"}` | Yes |
| work_date | `{"format":"date","type":"string"}` | Yes |
| minutes | `{"maximum":1440,"minimum":0,"type":"integer"}` | Yes |
| reason | `{"maxLength":2000,"minLength":1,"type":"string"}` | Yes |

### payroll_adjustment

| Field | Type / constraint | Required |
| --- | --- | --- |
| request_id | `{"format":"uuid","type":"string"}` | Yes |
| id | `{"format":"uuid","type":"string"}` | Yes |
| expected_version | `{"minimum":0,"type":"integer"}` | Yes |
| employee_id | `{"format":"uuid","type":"string"}` | Yes |
| action | `{"const":"payroll_adjustment","type":"string"}` | Yes |
| original_payroll_id | `{"format":"uuid","type":"string"}` | Yes |
| component | `{"enum":["basic_pay","leave_pay","overtime","premium_pay","performance_benefit","tax","statutory","advance_repayment","lawful_recovery","other"],"type":"string"}` | Yes |
| amount | `{"decimal_places":2,"max_digits":14,"type":"string"}` | Yes |
| reason | `{"maxLength":2000,"minLength":1,"type":"string"}` | Yes |
| lawful_basis | `{"default":"","maxLength":2000,"type":"string"}` | No |
| responsibility_evidence | `{"default":"","maxLength":2000,"type":"string"}` | No |
| employee_response | `{"default":"","maxLength":2000,"type":"string"}` | No |
| maximum_authorized_recovery | `{"anyOf":[{"decimal_places":2,"ge":0,"max_digits":14,"type":"string"},{"type":"null"}],"default":null}` | No |
| shortage_id | `{"anyOf":[{"format":"uuid","type":"string"},{"type":"null"}],"default":null}` | No |

### payroll_approve

| Field | Type / constraint | Required |
| --- | --- | --- |
| request_id | `{"format":"uuid","type":"string"}` | Yes |
| id | `{"format":"uuid","type":"string"}` | Yes |
| expected_version | `{"minimum":0,"type":"integer"}` | Yes |
| employee_id | `{"format":"uuid","type":"string"}` | Yes |
| action | `{"const":"payroll_approve","type":"string"}` | Yes |
| decision | `{"enum":["approved","rejected"],"type":"string"}` | Yes |
| reason | `{"maxLength":2000,"minLength":1,"type":"string"}` | Yes |

### payroll_history_import

| Field | Type / constraint | Required |
| --- | --- | --- |
| request_id | `{"format":"uuid","type":"string"}` | Yes |
| id | `{"format":"uuid","type":"string"}` | Yes |
| expected_version | `{"minimum":0,"type":"integer"}` | Yes |
| employee_id | `{"format":"uuid","type":"string"}` | Yes |
| action | `{"const":"payroll_history_import","type":"string"}` | Yes |
| year | `{"maximum":2200,"minimum":2000,"type":"integer"}` | Yes |
| through_date | `{"format":"date","type":"string"}` | Yes |
| basic_earned | `{"decimal_places":2,"ge":0,"max_digits":14,"type":"string"}` | Yes |
| taxable_earned | `{"decimal_places":2,"ge":0,"max_digits":14,"type":"string"}` | Yes |
| tax_withheld | `{"decimal_places":2,"ge":0,"max_digits":14,"type":"string"}` | Yes |
| thirteenth_paid | `{"decimal_places":2,"ge":0,"max_digits":14,"type":"string"}` | Yes |
| other_benefits_paid | `{"decimal_places":2,"ge":0,"max_digits":14,"type":"string"}` | Yes |
| source | `{"maxLength":2000,"minLength":1,"type":"string"}` | Yes |

### payroll_payment

| Field | Type / constraint | Required |
| --- | --- | --- |
| request_id | `{"format":"uuid","type":"string"}` | Yes |
| id | `{"format":"uuid","type":"string"}` | Yes |
| expected_version | `{"minimum":0,"type":"integer"}` | Yes |
| employee_id | `{"format":"uuid","type":"string"}` | Yes |
| action | `{"const":"payroll_payment","type":"string"}` | Yes |
| amount | `{"decimal_places":2,"ge":0,"max_digits":14,"type":"string"}` | Yes |
| occurred_at | `{"format":"date-time","type":"string"}` | Yes |
| payment_method | `{"enum":["cash","gcash","bank"],"type":"string"}` | Yes |
| reference | `{"default":"","maxLength":2000,"type":"string"}` | No |
| settlement_evidence | `{"default":"","maxLength":2000,"type":"string"}` | No |
| employee_acknowledgment | `{"default":"","maxLength":2000,"type":"string"}` | No |
| result | `{"enum":["completed","pending","failed"],"type":"string"}` | Yes |

### payroll_prepare

| Field | Type / constraint | Required |
| --- | --- | --- |
| request_id | `{"format":"uuid","type":"string"}` | Yes |
| id | `{"format":"uuid","type":"string"}` | Yes |
| expected_version | `{"minimum":0,"type":"integer"}` | Yes |
| employee_id | `{"format":"uuid","type":"string"}` | Yes |
| action | `{"const":"payroll_prepare","type":"string"}` | Yes |
| week_start | `{"format":"date","type":"string"}` | Yes |
| payroll_kind | `{"default":"weekly","enum":["weekly","thirteenth_month","separation","leave_conversion"],"type":"string"}` | No |
| leave_conversion_request_id | `{"anyOf":[{"format":"uuid","type":"string"},{"type":"null"}],"default":null}` | No |
| withholding_override | `{"anyOf":[{"decimal_places":2,"ge":0,"max_digits":14,"type":"string"},{"type":"null"}],"default":null}` | No |
| withholding_basis | `{"default":"","maxLength":2000,"type":"string"}` | No |
| unworked_holiday_dates | `{"items":{"format":"date","type":"string"},"maxItems":7,"type":"array"}` | No |
| unworked_holiday_basis | `{"default":"","maxLength":2000,"type":"string"}` | No |
| reason | `{"maxLength":2000,"minLength":1,"type":"string"}` | Yes |

### profile_save

| Field | Type / constraint | Required |
| --- | --- | --- |
| request_id | `{"format":"uuid","type":"string"}` | Yes |
| id | `{"format":"uuid","type":"string"}` | Yes |
| expected_version | `{"minimum":0,"type":"integer"}` | Yes |
| employee_id | `{"format":"uuid","type":"string"}` | Yes |
| action | `{"const":"profile_save","type":"string"}` | Yes |
| hire_date | `{"format":"date","type":"string"}` | Yes |
| effective_from | `{"format":"date","type":"string"}` | Yes |
| daily_rate | `{"decimal_places":2,"ge":0,"max_digits":14,"type":"string"}` | Yes |
| payout_method | `{"enum":["cash","gcash","bank"],"type":"string"}` | Yes |
| staff_manager | `{"type":"boolean"}` | Yes |
| active | `{"type":"boolean"}` | Yes |
| premium_pay_covered | `{"type":"boolean"}` | Yes |
| holiday_pay_covered | `{"type":"boolean"}` | Yes |
| tax_exempt | `{"type":"boolean"}` | Yes |
| gp_partial_day_policy | `{"enum":["prorated","full_day"],"type":"string"}` | Yes |
| classification_basis | `{"maxLength":2000,"minLength":1,"type":"string"}` | Yes |
| ordinary_leave_days_per_year | `{"default":5,"maximum":365,"minimum":5,"type":"integer"}` | No |
| leave_eligible_from | `{"anyOf":[{"format":"date","type":"string"},{"type":"null"}],"default":null}` | No |

### request_decide

| Field | Type / constraint | Required |
| --- | --- | --- |
| request_id | `{"format":"uuid","type":"string"}` | Yes |
| id | `{"format":"uuid","type":"string"}` | Yes |
| expected_version | `{"minimum":0,"type":"integer"}` | Yes |
| employee_id | `{"format":"uuid","type":"string"}` | Yes |
| action | `{"const":"request_decide","type":"string"}` | Yes |
| decision | `{"enum":["approved","rejected","cancelled"],"type":"string"}` | Yes |
| reason | `{"maxLength":2000,"minLength":1,"type":"string"}` | Yes |
| paid_minutes | `{"anyOf":[{"maximum":1440,"minimum":0,"type":"integer"},{"type":"null"}],"default":null}` | No |

### schedule_save

| Field | Type / constraint | Required |
| --- | --- | --- |
| request_id | `{"format":"uuid","type":"string"}` | Yes |
| id | `{"format":"uuid","type":"string"}` | Yes |
| expected_version | `{"minimum":0,"type":"integer"}` | Yes |
| employee_id | `{"format":"uuid","type":"string"}` | Yes |
| action | `{"const":"schedule_save","type":"string"}` | Yes |
| effective_from | `{"format":"date","type":"string"}` | Yes |
| work_days | `{"items":{"maximum":7,"minimum":1,"type":"integer"},"maxItems":6,"minItems":1,"type":"array"}` | Yes |
| start_time | `{"pattern":"^(?:[01][0-9]\|2[0-3]):[0-5][0-9]$","type":"string"}` | Yes |
| end_time | `{"pattern":"^(?:[01][0-9]\|2[0-3]):[0-5][0-9]$","type":"string"}` | Yes |
| meal_minutes | `{"maximum":1440,"minimum":0,"type":"integer"}` | Yes |
| reason | `{"maxLength":2000,"minLength":1,"type":"string"}` | Yes |

### shift_request

| Field | Type / constraint | Required |
| --- | --- | --- |
| request_id | `{"format":"uuid","type":"string"}` | Yes |
| id | `{"format":"uuid","type":"string"}` | Yes |
| expected_version | `{"minimum":0,"type":"integer"}` | Yes |
| employee_id | `{"format":"uuid","type":"string"}` | Yes |
| action | `{"const":"shift_request","type":"string"}` | Yes |
| effective_from | `{"format":"date","type":"string"}` | Yes |
| work_days | `{"items":{"maximum":7,"minimum":1,"type":"integer"},"maxItems":6,"minItems":1,"type":"array"}` | Yes |
| start_time | `{"pattern":"^(?:[01][0-9]\|2[0-3]):[0-5][0-9]$","type":"string"}` | Yes |
| end_time | `{"pattern":"^(?:[01][0-9]\|2[0-3]):[0-5][0-9]$","type":"string"}` | Yes |
| meal_minutes | `{"maximum":1440,"minimum":0,"type":"integer"}` | Yes |
| reason | `{"maxLength":2000,"minLength":1,"type":"string"}` | Yes |

### shortage_decide

| Field | Type / constraint | Required |
| --- | --- | --- |
| request_id | `{"format":"uuid","type":"string"}` | Yes |
| id | `{"format":"uuid","type":"string"}` | Yes |
| expected_version | `{"minimum":0,"type":"integer"}` | Yes |
| employee_id | `{"format":"uuid","type":"string"}` | Yes |
| action | `{"const":"shortage_decide","type":"string"}` | Yes |
| decision | `{"enum":["confirmed","dismissed","reversed"],"type":"string"}` | Yes |
| reason | `{"maxLength":2000,"minLength":1,"type":"string"}` | Yes |
| response_opportunity | `{"maxLength":2000,"minLength":1,"type":"string"}` | Yes |

### shortage_report

| Field | Type / constraint | Required |
| --- | --- | --- |
| request_id | `{"format":"uuid","type":"string"}` | Yes |
| id | `{"format":"uuid","type":"string"}` | Yes |
| expected_version | `{"minimum":0,"type":"integer"}` | Yes |
| employee_id | `{"format":"uuid","type":"string"}` | Yes |
| action | `{"const":"shortage_report","type":"string"}` | Yes |
| work_date | `{"format":"date","type":"string"}` | Yes |
| expected_cash | `{"decimal_places":2,"ge":0,"max_digits":14,"type":"string"}` | Yes |
| accounted_cash | `{"decimal_places":2,"ge":0,"max_digits":14,"type":"string"}` | Yes |
| evidence | `{"maxLength":2000,"minLength":1,"type":"string"}` | Yes |

### shortage_respond

| Field | Type / constraint | Required |
| --- | --- | --- |
| request_id | `{"format":"uuid","type":"string"}` | Yes |
| id | `{"format":"uuid","type":"string"}` | Yes |
| expected_version | `{"minimum":0,"type":"integer"}` | Yes |
| employee_id | `{"format":"uuid","type":"string"}` | Yes |
| action | `{"const":"shortage_respond","type":"string"}` | Yes |
| explanation | `{"maxLength":2000,"minLength":1,"type":"string"}` | Yes |

### statutory_month_save

| Field | Type / constraint | Required |
| --- | --- | --- |
| request_id | `{"format":"uuid","type":"string"}` | Yes |
| id | `{"format":"uuid","type":"string"}` | Yes |
| expected_version | `{"minimum":0,"type":"integer"}` | Yes |
| employee_id | `{"format":"uuid","type":"string"}` | Yes |
| action | `{"const":"statutory_month_save","type":"string"}` | Yes |
| month | `{"format":"date","type":"string"}` | Yes |
| sss_employee | `{"decimal_places":2,"ge":0,"max_digits":14,"type":"string"}` | Yes |
| sss_employer | `{"decimal_places":2,"ge":0,"max_digits":14,"type":"string"}` | Yes |
| philhealth_employee | `{"decimal_places":2,"ge":0,"max_digits":14,"type":"string"}` | Yes |
| philhealth_employer | `{"decimal_places":2,"ge":0,"max_digits":14,"type":"string"}` | Yes |
| pagibig_employee | `{"decimal_places":2,"ge":0,"max_digits":14,"type":"string"}` | Yes |
| pagibig_employer | `{"decimal_places":2,"ge":0,"max_digits":14,"type":"string"}` | Yes |
| employer_other | `{"decimal_places":2,"ge":0,"max_digits":14,"type":"string"}` | Yes |
| compensation_basis | `{"maxLength":2000,"minLength":1,"type":"string"}` | Yes |
| source | `{"maxLength":2000,"minLength":1,"type":"string"}` | Yes |
| prior_employee_deductions | `{"anyOf":[{"decimal_places":2,"ge":0,"max_digits":14,"type":"string"},{"type":"null"}],"default":null}` | No |

### statutory_remittance

| Field | Type / constraint | Required |
| --- | --- | --- |
| request_id | `{"format":"uuid","type":"string"}` | Yes |
| id | `{"format":"uuid","type":"string"}` | Yes |
| expected_version | `{"minimum":0,"type":"integer"}` | Yes |
| action | `{"const":"statutory_remittance","type":"string"}` | Yes |
| month | `{"format":"date","type":"string"}` | Yes |
| agency | `{"enum":["sss","philhealth","pagibig","bir"],"type":"string"}` | Yes |
| amount | `{"decimal_places":2,"ge":0,"max_digits":14,"type":"string"}` | Yes |
| occurred_at | `{"format":"date-time","type":"string"}` | Yes |
| reference | `{"maxLength":2000,"minLength":1,"type":"string"}` | Yes |
| settlement_evidence | `{"maxLength":2000,"minLength":1,"type":"string"}` | Yes |

### task_progress

| Field | Type / constraint | Required |
| --- | --- | --- |
| request_id | `{"format":"uuid","type":"string"}` | Yes |
| id | `{"format":"uuid","type":"string"}` | Yes |
| expected_version | `{"minimum":0,"type":"integer"}` | Yes |
| employee_id | `{"format":"uuid","type":"string"}` | Yes |
| action | `{"const":"task_progress","type":"string"}` | Yes |
| status | `{"enum":["todo","in_progress","done","cancelled"],"type":"string"}` | Yes |
| reason | `{"maxLength":2000,"minLength":1,"type":"string"}` | Yes |

### task_save

| Field | Type / constraint | Required |
| --- | --- | --- |
| request_id | `{"format":"uuid","type":"string"}` | Yes |
| id | `{"format":"uuid","type":"string"}` | Yes |
| expected_version | `{"minimum":0,"type":"integer"}` | Yes |
| employee_id | `{"format":"uuid","type":"string"}` | Yes |
| action | `{"const":"task_save","type":"string"}` | Yes |
| description | `{"maxLength":2000,"minLength":1,"type":"string"}` | Yes |
| due_date | `{"format":"date","type":"string"}` | Yes |
| notes | `{"default":"","maxLength":2000,"type":"string"}` | No |
| related_client_id | `{"anyOf":[{"format":"uuid","type":"string"},{"type":"null"}],"default":null}` | No |
| related_application_id | `{"anyOf":[{"format":"uuid","type":"string"},{"type":"null"}],"default":null}` | No |

## Nested exact schemas

```json
{
  "AccountingLine": {
    "additionalProperties": false,
    "properties": {
      "account_code": {
        "maxLength": 100,
        "minLength": 1,
        "title": "Account Code",
        "type": "string"
      },
      "debit": {
        "decimal_places": 2,
        "ge": 0,
        "max_digits": 14,
        "title": "Debit",
        "type": "string"
      },
      "credit": {
        "decimal_places": 2,
        "ge": 0,
        "max_digits": 14,
        "title": "Credit",
        "type": "string"
      }
    },
    "required": [
      "account_code",
      "debit",
      "credit"
    ],
    "title": "AccountingLine",
    "type": "object"
  },
  "Installment": {
    "additionalProperties": false,
    "properties": {
      "due_date": {
        "format": "date",
        "title": "Due Date",
        "type": "string"
      },
      "amount": {
        "decimal_places": 2,
        "ge": 0,
        "max_digits": 14,
        "title": "Amount",
        "type": "string"
      }
    },
    "required": [
      "due_date",
      "amount"
    ],
    "title": "Installment",
    "type": "object"
  }
}
```
