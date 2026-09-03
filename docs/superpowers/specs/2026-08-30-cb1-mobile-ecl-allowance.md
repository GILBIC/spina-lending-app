# CB1 Mobile Initial ECL Allowance Specification

## Authority

- GitHub Master Issue #296, CB1 Management mobile protected accounting queues.
- `gilbic_backend/sql/0077_add_protected_ecl_allowance_posting.sql` and
  `0078_harden_ecl_allowance_posting_queue.sql` are the initial-allowance
  accounting authority.
- `gilbic_backend/src/gilbic_backend/ecl_allowance_posting_api.py` already
  exposes the same protected handlers to `/api/v1/...` and `/api/mobile/v1/...`.
- A5 remeasurement, write-off, recovery, tax, period close, automatic source
  posting, and ECL calculation are separate workflows.

## Problem

The backend already exposes a Management-only, device-authorized initial ECL
allowance queue and exact prepare/post operations to mobile. Gilbic Mobile has
read-only ECL measurement and outcome-review screens, but no typed adapter or
Management workspace for this existing A4 authority. Management therefore
cannot safely review and perform the initial allowance prepare/post workflow
from mobile.

## Intended behavior

1. Management opens **Initial ECL allowance** from Financial Accounting.
2. The page displays the server queue, summary, filter, notice, authoritative
   measurement evidence, preparation evidence, journal status, and posting
   evidence. Flutter does not calculate ECL or account balances.
3. `preparation_required` exposes **Prepare allowance draft** only when:
   - the queue row is marked `protected_allowance_action_ready`;
   - the server response grants `accounting.ecl.allowance.prepare`; and
   - the current session contains that exact permission.
4. `posting_ready` exposes **Post initial allowance** only when the server and
   current session grant `accounting.ecl.allowance.post` and all protected
   posting coordinates are present.
5. Prepare and post each use the shared protected Management review component.
6. Prepare submits the exact server measurement digest, ECL amount, posting
   date, fiscal period, accounts, and prior allowance balance. Post submits the
   exact prepared journal, source key, preparation digest, dates, accounts,
   amount, and prior balance.
7. A 64-character lowercase hexadecimal review token is stable for an uncertain
   retry of the same authoritative snapshot. Preparation and posting use
   separate token namespaces.
8. After confirmed success the page reloads the authoritative queue. It does
   not infer the next accounting state locally.
9. Measurement-not-authoritative, zero-allowance, preparation-blocked,
   posted-current, A5-remeasurement-required, and audit-incomplete rows remain
   read-only with plain status/recovery language.

## Accounting and security invariants

- Active approved device, canonical Management role, and backend permission
  checks remain mandatory.
- Account 5000 Credit Loss Expense and account 1190 Allowance for Expected
  Credit Loss remain server-derived identifiers; the app shows their codes but
  sends the exact IDs supplied by the queue.
- A4 only permits an initial allowance where the exact prior protected balance
  is `0.00` and the authoritative ECL is greater than zero.
- Automatic source posting remains false.
- Flutter must not create a journal, calculate ECL, derive a balance, edit a
  digest, or fall back to a mobile-only posting path.
- No SQL, production data, protected/live migration, A5 action, tax action,
  signing, deployment, or release belongs to this slice.

## Acceptance evidence

- Repository tests prove strict parsing, device authorization, exact prepare
  and post bodies, safe errors, and same-snapshot token input.
- Widget tests prove server/session permission intersection, visible blockers,
  confirmation/cancel behavior, exact review facts, explicit retry, and
  authoritative reload after success.
- Financial Accounting tests prove the launcher opens the exact protected page.
- Focused tests, full Flutter/backend tests, strict analyzer, formatting, branch
  diff review, and exact-head CI must pass before the Draft PR checkpoint.

## Implementation checkpoint — 2026-08-30 PH

The bounded A4 mobile adapter, protected Management review page, and Financial
Accounting launcher are implemented. Mobile consumes the existing FastAPI
mobile aliases and never calculates ECL or creates a separate accounting path.

Local verification on implementation head
`905b646af8fe75cc5a2c4885701896512760b833` is green: 18 focused tests after
the final review correction, 412 complete Flutter tests, strict analyzer with
no issues, 1,282 backend tests passed with 188 configured skips, and zero Dart
format changes. Standards review found and corrected one missing server summary
field (`preparation_blocked_count`) plus strict returned-filter validation.

Draft PR, exact-head CI, and external status evidence are publication steps;
they do not authorize merge, deployment, signing, production data, protected
migrations, A5 remeasurement, or automatic source posting. The broad CB1
Master Checklist item remains open.
