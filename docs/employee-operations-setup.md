# Employee operations setup and verification

The employee module uses the existing SPINA backend, portal and Android app. It
does not initiate bank/GCash transfers or government remittances.

## Owner and staff accounts

Set `SPINA_EMPLOYEE_OWNER_USER_ID` to the actual owner's `core.users.id` in the
backend deployment environment. This is a private setup value; no real account
is seeded by the migration. A missing or invalid value fails closed. Possessing
the Management display role does not automatically confer employee-owner powers.
The configured owner still needs an active staff account and approved device.

After migration `0128_add_employee_operations.sql` is deployed through the normal
release process, the owner configures existing employee accounts through Employee
work and pay. Configure the actual three people, rates, service dates, payout
methods and reviewed classifications. For the combined worker, the staff-manager
responsibility preserves Collector membership and adds Employee plus the narrow
`employee_manager` responsibility. It refuses an existing unrestricted Management
membership. It grants no loan approval. Removing this responsibility removes the
staff-manager role, while preserving separately assigned Collector/Employee access.

Sign in again after changing memberships to refresh the client workspace choices.
Server authorization always uses current account/device state. The combined
worker's own requests and payroll cannot be self-approved by switching workspace.
The owner can designate a named independent backup for explicit duties and dates.

## Private payroll setup

Enter effective schedules and working/rest days, verified leave opening balances
(including an explicit zero when accurate), applicable calendar classifications,
reviewed monthly employee/employer contribution amounts and their official source.
Record verified employee contributions already collected outside Spina for that
month, including an explicit zero when none were collected, to avoid collecting
the same amount again.
Enter verified historical earnings when annual or separation calculations need
pre-system records. Preserve better existing recurring leave/benefit terms using
the reviewed profile options. Missing inputs produce an explanation and block the
affected calculation; they are not treated as zero deductions or zero wages.

Daily-rate wages cover Sunday through Saturday and are paid after Saturday's
shift. Employees record attendance and meal breaks; corrections retain the original
events. Review unresolved time, leave and overtime before approval. The owner or
authorized manager approves the other two employees; only an independent authorized
approver handles the combined worker's records. Payroll approval and actual payment
are separate. Record cash acknowledgment or independently verified transfer evidence
only after the money moves. Pending/failed attempts do not mark a salary paid.

Payroll history is preserved. Unpaid changed inputs require recalculation and
reapproval. Paid corrections use linked adjustments. An actual shortage case and
loss of conditional Good Performance Benefits are separate from any wage recovery.
A policy name or signature alone is not sufficient recovery authority: reviewed
lawful basis, individual responsibility, employee response and applicable limit
must be established before a recovery is recorded.

## Attendance without a connection

On Android, first open Employee work and pay online with the registered device.
Only clock-in/out and meal-break events are saved to the protected local outbox.
They retain the original capture time, account/device binding and stable IDs across
restart. Pending sync means the server has not confirmed the event. Reconnect/resume
to synchronize. Rejected/conflicting events require the recorded correction process;
they never silently change salary. Switching accounts cannot upload another person's
queue. Payroll approvals, advances, accounting and payments remain online actions.

Web attendance requires a connection. After an uncertain mutation, read back the
same request ID before retrying; do not create a second payment to resolve a timeout.

## Accounting and release checks

Journal preparations use the existing accounting draft tables and validations in
the same transaction as the employee request receipt. They do not post, reverse or
close periods. The existing owner Accounting workspace performs those actions.
Reconciliation preparations retain supporting balances and evidence without asserting
that a provider transaction is settled. Existing loan approvals, release prerequisites
and the prohibition on receiving one's own remittance continue to apply.

Before release, run the automated employee/combined-role cases and the existing full
suites, then Android device checks for offline capture, restart, reconnect, account
switching and revoked access. Automated mocks do not replace device UAT. This guide
is not evidence that a production migration, payroll or deployment has occurred.
