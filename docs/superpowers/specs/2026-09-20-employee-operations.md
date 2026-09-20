# Spina employee operations — consolidated recommendation

Prepared 19 September 2026 for the user's request: **Recommend all**.

Status: user approved the consolidated recommendation on 20 September 2026. Implement the employee batch and combined verification. Approval does not invent actual staff setup values, establish a legal basis for shortage deductions, or authorize live payroll, merge or deployment. PR437 remains separate; employee implementation is on feature/employee-operations, based on its verified f059b943 head.

## Outcome and scope

Give the three Collector employees one personal account each for attendance, breaks, tasks, leave, advances and payslips. One of those same people also handles office and staff-management duties. The user remains the final loan approver and the independent approver for that combined worker's own records. Keep the existing FastAPI/Postgres service, Flutter Android app and portal. Build and verify the employee batch together, without adding another app, a generic workflow engine or an external payroll/payment provider.

## Confirmed choices to preserve

- Three employees total: two Collector-only, one Collector/office/Management. One person has one attendance and payroll identity.
- Daily-rate wages; eight compensated hours, usually starting at 06:00 or 07:00 Asia/Manila. Individual working/rest days vary. A normally unpaid one-hour meal period produces typical 06:00–15:00 or 07:00–16:00 schedules, with paid short rests and worked/interrupted-break exceptions preserved.
- Weekly Sunday–Saturday payroll, paid after Saturday's shift. Payment can be cash or GCash/bank transfer per employee.
- Employees record clock-in/out and Start break/End break. Corrections require a request and reason: Management reviews the other two; the user reviews the combined worker's own requests. The user explicitly approved offline attendance/break capture, durable local storage, automatic sync, Pending sync status, deduplication and conflict review.
- Employees request shift changes before the schedule changes. The combined worker's own leave and shift changes go to the user.
- The user can approve all three payrolls; Management can approve the other two only. Either authorized approver is sufficient for those two.
- Good Performance Benefits: PHP100 per day; Sunday–Saturday assessment; one cash shortage cancels that employee's entire weekly benefit. Paid leave does not currently earn the extra PHP100. The user says this is an existing verbally explained, unsigned rule. The intended additional salary recovery is the exact actual shortage, separately from lost benefits; legality and process have not been established.
- Advances exist, with individually agreed repayment amounts, no interest or fees. Management approves the other two employees' advances/terms; the user approves the combined worker's own advance/terms.
- Simple extra tasks are required; both the user and Management may assign them.
- The combined worker prepares loan applications and releases approved funds. The user approves loans and retains existing release authorization. The user personally receives and verifies this worker's collected cash.

## Recommended policy defaults

### 1. People, schedules and continuity

Enter actual daily rates, service/hire dates, individual payout methods, work/rest schedules and account mappings during private setup. Use effective dates for rate/schedule changes; do not invent these values, copy example wages into production or overwrite historical payroll rates. Check applicable regional wage rules using the actual location and establishment details.

Use each person's assigned rest day rather than assuming Sunday is everyone's rest day. Default schedules must preserve the applicable weekly rest entitlement. Keep previous schedule versions when a change is approved.

Give the owner remote access to approve when away. Let the owner designate a named, independent backup with explicit duties and effective dates before an absence. Until that person is configured, do not silently give the combined worker authority over their own records or their own cash receipt. Plan coverage before payday; owner absence is not a payroll-forfeiture rule. Existing self-remittance prohibition remains enforced.

Use existing account/device verification for attendance. Do not add GPS, selfies or continuous location tracking by default.

### 2. Ordinary pay, half-days and overtime

For an ordinary eight-hour day, use verified compensable time: **daily rate / 480 × ordinary paid minutes**, capped at that day's ordinary eight hours. Add paid-leave and other payable time through distinct lines without counting the same interval twice. Four worked hours ordinarily earn half the basic daily rate. Compute from actual time, with no arbitrary late fines or punitive rounding; round final currency amounts consistently to centavos. Incomplete/offline/conflicting records are exceptions to review, not automatic unpaid absences.

Keep overtime separate. Request advance approval where practical, using the same independent approval pattern as attendance corrections. Missing preapproval flags review; it does not automatically erase compensable work the employer permitted or suffered. For covered ordinary work, the standard overtime minimum after eight compensable hours is 125% of the hourly rate. Do not offset one day's overtime against another day's undertime. [Labor Code, Articles 84 and 87–88](https://lawphil.net/statutes/presdecs/pd1974/pd_442_1974b.html)

Configure holiday/rest-day treatment using effective-dated official calendars and the reviewed employment/establishment coverage. For covered staff, ordinary rest/special-day work starts at 130%, special day on rest day 150%, regular holiday 200%, and regular holiday on rest day 260%; corresponding overtime uses the applicable day's additional multiplier. Unworked-day eligibility must be evaluated separately. These statutory examples are not a finding that every exemption applies or fails here. Preserve better existing benefits. [DOLE handbook, holiday/premium/overtime sections](https://nwpc.dole.gov.ph/wp-content/uploads/2024/11/Workers-Statutory-Monetary-Benefits-Handbook-2024-Edition.pdf)

Do not classify an employee as legally exempt solely from the app label Collector or Management, or from having only three employees.

### 3. Good Performance Benefits and shortages

Recommend the same opportunity for all three employees, with the combined worker assessed on their own accountable collections. Pay the approved benefit with Saturday wages for the same Sunday–Saturday week.

For future clearly documented partial-day treatment, recommend **PHP100 × actual credited working minutes / 480**, capped at PHP100 per day: eight hours PHP100; four hours PHP50. Paid short rests remain within working time; leave and unworked days add no benefit, and overtime does not increase the daily PHP100 cap. If the current established policy is more generous for short days, preserve that existing entitlement until a lawful prospective policy is settled.

The shortage assessment concerns actual money received and accounted for, not a missed collection target, a borrower who did not pay, a pending transfer, a synchronization delay or another person's shortage. A discrepancy starts as reported, not proven. Record expected accountable cash, counted/remitted cash, evidence, the employee's explanation, reviewer and decision. The owner makes the final shortage/benefit-disqualification decision for all three as the recommended default; the combined worker can prepare evidence but cannot decide their own case.

Under the user's stated weekly condition, a confirmed shortage makes that employee's weekly benefit zero; it must not produce a second negative benefit deduction. A mistaken shortage that is reversed restores the appropriate benefit through a traceable adjustment. Repaying a genuine shortage does not by itself erase the historical shortage condition; any more favorable existing agreement still governs.

Keep loss recovery in a separate record. **Do not enable automatic salary deductions merely because a shortage exists or a policy is signed.** Establish the applicable lawful basis, individual responsibility, employee opportunity to respond, actual unrecovered amount and any applicable limits before a payroll recovery is accepted. If no lawful payroll basis exists, do not route it through an advance or miscellaneous deduction to bypass the restriction. Settle/review disputed benefit amounts separately from timely payment of undisputed wages. [Marby Food Ventures, G.R.244629](https://lawphil.net/judjuris/juri2020/jul2020/gr_244629_2020.html)

Document the existing benefit accurately before any prospective change. A conditional period bonus is different from taking away an already earned or established unconditional benefit; renaming daily earnings as provisional does not resolve that distinction. [Eastern Telecommunications, G.R.185665](https://lawphil.net/judjuris/juri2012/feb2012/gr_185665_2012.html)

### 4. Leave

Recommend a uniform company benefit of **five paid ordinary leave days per service year**, usable after completing one year, shared between sick/vacation/ordinary leave. Offer it to all three as a voluntary baseline and preserve any better existing benefit. The small-establishment SIL exemption does not mean every other benefit is exempt. Special statutory leave stays separate and follows its own eligibility/payment rules.

Recommended ledger convention: accrue at five days per twelve months of qualifying service, with proportional partial periods; the first five become usable when the first qualifying year is completed. Subsequent service continues earning proportional credits. Import verified historical balances rather than assuming zero. Record leave in the employee's scheduled working-time units, so four hours of an eight-hour day uses half a day. Approved leave contributes its normal leave pay, without Good Performance Benefits.

Offer year-end cash conversion of eligible unused ordinary credits; otherwise preserve the unused balance. Do not silently expire it. At separation, reconcile unused eligible credits and applicable proportional accrual using the appropriate salary rate. [DOLE handbook, SIL section](https://nwpc.dole.gov.ph/wp-content/uploads/2024/11/Workers-Statutory-Monetary-Benefits-Handbook-2024-Edition.pdf)

Recommend requests three days ahead for planned ordinary leave, with emergency/sick notice as soon as reasonably possible. This notice preference must not arbitrarily remove legal entitlement. Management reviews the other two employees; the owner can review all and must review the combined worker's own request. Prevent overlapping approved leave/attendance from being paid twice.

### 5. Advances

Keep a principal ledger with requested, approved, disbursed, repaid and outstanding amounts. The agreed repayment terms must include the amount per installment, start date and due dates, acknowledged by the employee. Recommend Saturday installments beginning on the next agreed payday, with per-advance overrides because the user explicitly chose individual agreements.

At each scheduled recovery, take no more than the agreed installment and outstanding principal, subject to lawful payroll authorization. The final installment is the smaller remaining balance. Do not collect interest, fees or hidden charges. If the installment cannot be taken within the lawful available pay, flag it for review and leave the balance outstanding; do not create negative wages or automatically double next week's installment. Any reschedule/change records the employee agreement and authorized approver.

A payroll allocation, cash repayment or external transfer must produce one repayment entry only. Approval is not proof of advance disbursement. Never transform a disputed shortage into an advance to create an apparent repayment authorization.

### 6. Payroll, payment and statutory setup

Use one weekly run with individual employee lines: **draft → reviewed/approved → paid**, with explicit pending/partial/failed payment states where needed. The combined worker can prepare payroll. The owner can approve all; Management can approve only the other two. Recommend salary-payout recording reserved to the owner initially, while preparation can include payment instructions. Payout authority is a separate permission from approving payroll or releasing loans.

After Saturday's completed shifts, calculate from accepted attendance, approved corrections/leave, versioned rates, benefit decisions and agreed advances. Show basic pay, paid leave, overtime/premiums, Good Performance Benefits, statutory deductions, approved recoveries and net pay separately. Employees see their own payslip and balances; authorized staff see only their permitted scope.

For cash payment, record amount, date and employee acknowledgment. For GCash/bank payments, record amount, reference and completion evidence. An entered reference or attached screenshot alone does not prove settlement. Preserve who marked it paid and the basis. This batch records actual payments; it does not initiate provider transfers.

Lock approved input versions. Any material change invalidates the prior unpaid approval and requires reapproval. Paid records are not overwritten: correct them with linked adjustments/reversals and, where required, an additional payment. Unresolved exceptions on one employee do not prevent the others' correct payroll from progressing.

Keep SSS, PhilHealth and Pag-IBIG obligations in employee/month records separate from weekly pay. Use reviewed, effective-dated official schedules and agency-specific compensation bases; allocate/reconcile employee deductions across weekly runs so a full monthly amount is not charged every week. Employer shares and employer-only costs stay company expenses. Include handling for four/five Saturdays and weeks crossing month boundaries. [SSS employer duties](https://www.sss.gov.ph/employer-er/), [PhilHealth employers](https://www.philhealth.gov.ph/partners/employers/)

Use the applicable weekly BIR withholding rules and annual/separation reconciliation. Keep earning classifications explicit; the name Good Performance Benefits does not establish tax or contribution exemption. Produce payroll/contribution summaries for review and filing rather than claiming filings or remittances occurred. [BIR RR11-2018](https://bir-cdn.bir.gov.ph/local/pdf/RR%20No.%2011-2018.pdf)

Recommend 13th-month pay for all three under a consistent company policy, preserving better terms. Track eligible basic salary and calculate at least its annual total divided by twelve, including appropriate separation proration; schedule payment by December24. App roles do not decide statutory coverage. [DOLE guidance](https://dole.gov.ph/no-delays-allowed-on-13th-month-pay-dole1/)

This is a three-employee payroll module, not a new general tax-compliance platform. Agency schedules and reviewed adjustments are configuration; automatic agency filing/payment and complex benefits administration are outside this batch.

### 7. Tasks and accounting access

Keep tasks simple: description, one assignee, due date, notes and Todo/In progress/Done/Cancelled. Owner or Management assigns; the assignee marks progress/done; the assigner can reopen with a reason. Preserve history. Link existing borrower/application records when relevant; do not duplicate route assignment or introduce another financial approval mechanism through task completion.

Recommend the combined worker may prepare journal drafts, supporting schedules and cash/bank reconciliations. Reserve final journal posting, reversals, opening-balance edits, period closing, permission changes and payroll-rate changes to the owner. Keep existing collection/remittance/loan state machines authoritative. Preparing a draft or reconciliation does not post money, forgive debt, confirm a provider payment or approve a loan.

## Permission matrix

| Action | Collector-only employees | Combined worker | Owner/user |
| --- | --- | --- | --- |
| Own attendance, breaks, requests, payslips | Own records | Own records | Authorized oversight |
| Review corrections/leave/shifts | No general review | Other two only | All; required for combined worker |
| Assign additional tasks | No general assignment | Yes | Yes |
| Prepare payroll | No | Yes | Yes |
| Approve payroll | No | Other two only | All three |
| Approve advances/terms | No | Other two only | All; required for combined worker |
| Loan application preparation | Existing exact grants | Yes | Existing exact grants |
| Loan approval and release authorization | No | No | Yes |
| Release a loan | Existing exact grants only | After required owner authorization and prerequisites | Existing exact grants |
| Receive combined worker's own remittance | No new grant | Never self-receive | Personally, as confirmed |
| Prepare accounting drafts/reconciliations | No | Recommended | Yes |
| Post/reverse journals or change permissions/rates | No | No | Recommended owner-only |
| Record salary payout | No | Preparation only by default | Recommended owner-only |

Owner is a business authority, not an invented fourth payroll employee or an assumption about a new top-level app role. Map the actual authenticated account during setup. Named backup grants must be explicit and cannot permit self-approval.

## User stories

1. As an employee, I want my own account and payslip, so that combined job duties do not duplicate my pay or expose coworkers' pay.
2. As an employee, I want to see my assigned working/rest days and request a shift change, so that expectations are clear.
3. As an employee, I want clock and meal-break buttons, so that actual working time is recorded.
4. As a collector, I want to record attendance without internet, so that signal loss does not erase my work record.
5. As an employee, I want pending and accepted entries to be distinguishable, so that I know whether synchronization succeeded.
6. As an employee, I want to request a correction with a reason, so that missing or incorrect time can be resolved transparently.
7. As an approver, I want the original entry and requested change together, so that I can make an accountable decision.
8. As the owner, I want the combined worker's own requests routed to me, so that workspace switching cannot authorize self-approval.
9. As an employee, I want paid leave, worked time and overtime shown separately, so that my pay can be checked.
10. As an employee, I want overtime reviewed even when preapproval is missing, so that compensable actual work is not discarded.
11. As an employee, I want ordinary and special leave balances handled distinctly, so that one benefit is not wrongly consumed for another.
12. As an employee, I want to choose eligible unused-leave cash conversion and see its settlement, so that credits do not silently disappear.
13. As an employee, I want Good Performance Benefits and any shortage decision explained, so that I can understand and dispute errors.
14. As the owner, I want shortage evidence and the employee's response, so that a reported discrepancy is not automatically treated as proven liability.
15. As an employee, I want my advance amount, agreed installments and remaining principal, so that I can verify repayment without hidden charges.
16. As an approver, I want actual disbursement and repayment recorded separately from approval, so that balances reflect money actually received or paid.
17. As an employee, I want assigned tasks and a simple way to mark progress, so that office work can be followed without another approval bureaucracy.
18. As Management, I want to prepare weekly payroll and review the other two workers, so that Saturday pay is ready on time.
19. As the owner, I want to approve any employee's payroll and record payment, so that authority and payment evidence remain clear.
20. As an employee, I want a corrected paid payslip linked to the original, so that changes are visible and never silently rewrite history.
21. As the combined worker, I want to prepare applications and release authorized loans without loan-approval authority, so that I can do my actual duties.
22. As the combined worker, I want to prepare accounting drafts for the owner, so that bookkeeping can progress without unapproved posting.
23. As the owner, I want contribution/tax summaries and separate remittance evidence, so that payroll deductions are not mistaken for government payments.
24. As an employee, I want retries, device changes and interrupted connections handled without duplicate pay/time records or another person's data, so that the system remains reliable.
25. As the owner, I want verified setup values and explicit backup authority, so that missing configuration cannot create fabricated pay or unauthorized decisions.

## Existing code and implementation decisions

Read-only inspection at `f059b943` found HR destinations unavailable in the Flutter Employee dashboard and portal. No implemented HR profile, attendance, payroll, leave, shift-request or task tables/API/repositories were found. Employee Activity is a read-only aggregation of accounting/support/remittance sources, not an HR system of record. The mobile offline policy currently excludes HR writes; its generic local-database abstraction is memory-only, so it is not sufficient for approved offline capture.

Use the established `*_api.py` / `*_repository.py` structure, strict request models, transactions and incremental SQL migrations in `gilbic_backend`. Reuse `core.users`, memberships, permission/device verification, audit and private-document patterns. New HR data must stay within the existing private-schema security boundary, with no anonymous/direct-public-table access.

Add focused records for employee profiles/effective schedules, attendance events and requests, leave ledger/requests, tasks, advance ledger/terms, payroll runs/employee snapshots/decisions, payment evidence and monthly statutory summaries. Do not create a shared generic workflow engine. Backend validation decides actor scope and record ownership; frontend workspace visibility is not authorization.

Use permission-aware navigation in the existing mobile/portal clients. Preserve Collector ownership and existing membership checks. Default Management membership currently includes `lending.first_loan.approve`; therefore it cannot be granted unchanged to the combined worker. Introduce a narrowly scoped staff-management responsibility grant within existing RBAC and keep user loan authority separate. The implementation plan must prove effective permissions after combining memberships; no unconditional Management grant or role-switch workaround is acceptable. No new top-level mobile role or server session-context framework is required by this design.

The existing first-loan flow already supports separate preparation, approval, authorization and release actors. Reuse its checks for an exact approved packet, current unrevoked release authorization, approved net cash and account/device state. Do not replace this flow. Other loan/reloan paths need focused implementation review before applying a permission change to them.

Expose employee-owned reads/writes and scoped review/administration APIs through the existing application. Attendance upload accepts stable event IDs and event versions; repeated identical uploads return the same result, while conflicting reuse of an ID is rejected. Correction/approval/payment actions require expected current versions and idempotency keys. Each API response distinguishes accepted, pending review, rejected and already completed results; uncertain network responses prompt readback, not blind repeat financial actions.

For mobile attendance only, create a durable local outbox using appropriate protected device storage. Store original captured timestamps separately from server receipt time and retain enough ordering/context for review. Bind pending events to their employee/account/device and never upload them under a different signed-in user. Preserve pending entries across restart and interrupted sync; display per-entry errors and use the agreed correction process. Server permission/device revocation still applies when events are received. Do not infer proof of working solely from an editable device clock.

Persist approved payroll input versions and money in exact decimal/centavo form. Each payroll employee line, payout and advance repayment has a unique idempotent identity. Atomically enforce approval scope, prior state, current version and remaining balances; concurrency must not approve/pay/recover twice. Link payroll adjustments and any accounting postings exactly once. Enforce employee self-service privacy on the server and exclude payroll information from general activity views.

## Verification and acceptance

Use high-level seams already present: FastAPI dependency-override permission tests; real Postgres tests through the guarded disposable loopback fixture; Flutter repository/widget and portal presenter/action tests. Existing references include `tests/test_area_management_api.py`, `test_management_employee_activity_api.py`, `test_first_loan_postgres.py`, `test_client_cif_review_confirmation_postgres.py`, `gilbic_mobile/test/employee_dashboard_test.dart` and `spina_portal/tests/presenters.test.mjs`. Extend the disposable migration runner, never a production database.

Required combined cases:
- All three identities and every allowed/denied action in the matrix, including combined memberships, revoked permission/device, cross-employee access and self-approval attempts.
- Full/partial days, paid/interrupted breaks, leave overlap, overtime without preapproval, holiday/rest-day combinations, rate changes, cross-month weeks and exact currency calculations.
- Offline capture, restart, account switch, reordered/duplicate events, expired authorization, clock anomalies, sync timeout/readback and corrections arriving before/after payroll approval.
- Weekly Good Performance Benefits, no paid-leave credit, verified versus disputed/false shortages, reinstated benefits and prevention of duplicate forfeiture/recovery.
- Principal-only advances, installment agreement, final small balance, insufficient pay, concurrent repayment and repeated payment notifications.
- Leave eligibility/opening balances, partial leave, rejected/cancelled requests, conversion and separation without silent expiry.
- Payroll approval by either permitted actor, owner-only combined-worker approval, stale input rejection, paid/partial/failed payout evidence and traceable post-payment corrections.
- Existing first-loan, collection, remittance, accounting and account/device behavior preserved. No HR feature may weaken existing financial permissions.

After one coherent implementation batch, run focused checks during development and the full required combined suite once at the candidate head. Then do Android device UAT across online/offline/reconnect/restart cases. User Red/Green reports remain current-priority progress signals, not a reason to split the work into tiny manual gates. Do not claim device UAT, implementation or tests complete based on this document.

## Real setup and activation dependencies

These are factual inputs or release prerequisites, not another policy questionnaire: actual employee/account identities; rates and service dates; initial schedules/rest days; existing benefit/advance balances; payout destinations; employer location/classification/registrations; employee agency/tax identifiers and reviewed classifications; effective official contribution/holiday/tax schedules; and a named independent backup if wanted. Provide these privately during setup; do not publish personal payroll data to GitHub/Notion project notes.

Before live payroll, review actual existing employment terms, Good Performance Benefits and any proposed recovery document with an appropriately qualified Philippine labor/payroll professional. An unsigned/verbal policy is not erased by this recommendation, and a new signature does not cure every wage-deduction issue. Keep shortage deductions disabled until the applicable basis/procedure is established. Unknown statutory/setup data must block an affected payroll calculation with a clear missing-input explanation rather than silently using zero.

## Outside this batch

No PR437 merge, deployment, production migrations, live payroll/loan/cash mutations, automatic GCash/bank transfers or government filings are authorized by this specification. No new office employee, generic project-management suite, continuous GPS/selfies, biometric hardware, new native iOS app, third-party payroll platform, lending-rule redesign or frozen-roadmap reorder. No change to historical earned benefits by relabeling them. Existing GCash confirmation feasibility work remains separate.

## Sources and limits

Sources reviewed on 19 September 2026 include the Labor Code/implementing rules, DOLE handbook and cited Supreme Court decisions, SSS employer/contribution resources, PhilHealth employers/circulars and BIR withholding rules. Official references supplement company defaults; they do not establish this employer's individual legal classifications. Pag-IBIG's circular site presented CAPTCHA during research, so no current numerical Pag-IBIG table is asserted here. Confirm the effective official schedule during setup.

Additional official references: [SSS tables](https://www.sss.gov.ph/sss-contribution-table/), [SSS contribution basis](https://www.sss.gov.ph/pay-contribution/), [PhilHealth contribution basis](https://www.philhealth.gov.ph/circulars/2020/circ2020-0005.pdf), [DOLE wage-deduction guidance](https://car.dole.gov.ph/news/authorized-deductions-in-workersae-pay/).
