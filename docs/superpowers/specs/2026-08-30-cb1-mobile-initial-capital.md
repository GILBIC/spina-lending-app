# CB1 Management Mobile Initial Capital

Status: approved bounded implementation slice under Master Issue #296. This
extends the existing protected initial-capital accounting workflow to Gilbic
Mobile; it does not create a second accounting authority or authorize real
production funding.

## Current authority

The existing FastAPI/PostgreSQL workflow is authoritative:

1. Management records immutable retained funding evidence with an exact retry
   identity.
2. The backend validates an eligible cash/financial-account and Capital 3000.
3. Management prepares the protected two-line General Journal draft.
4. Management confirms and posts the exact evidence, amount, account, date,
   fiscal period, and draft through the protected posting function.
5. Automatic posting and synthetic opening balances remain disabled.

## Mobile behavior in this slice

- Add `/api/mobile/v1/.../initial-capital-funding` aliases to the same
  handlers and repository used by the existing API.
- The list response supplies a server-derived summary, exact permissions,
  eligible cash-account choices, queue items, and safety policy flags.
- Management may record evidence, prepare an eligible record, and post a
  prepared record only when the canonical role, approved device, current
  session permission, and current server permission all agree.
- Evidence recording requires funding date, exact positive two-decimal amount,
  one server-supplied eligible cash account, retained source/reference, a
  64-character lowercase SHA-256 evidence fingerprint, and a meaningful note.
- The existing stable UUID retry identity is used for evidence recording, and
  the existing 64-character lowercase hexadecimal confirmation token is used
  for posting. A retry after an uncertain result reuses the same identity for
  the unchanged snapshot.
- Every confirmed success reloads the authoritative queue. Errors preserve safe
  FastAPI codes/messages and never optimistically change official state.

## Fail-closed rules

- Flutter never decides which accounts are eligible and never constructs or
  posts journal lines.
- Flutter never derives the posting date or fiscal period. The funding date and
  prepared fiscal-period identity must come back from the authoritative queue.
- Actionable records missing exact coordinates are rejected as invalid server
  responses before any financial request is sent.
- Posted evidence is immutable and read-only. Blocked evidence remains
  read-only with the server blocker shown.
- `protected_initial_capital_funding_enabled=true`,
  `synthetic_opening_balance_required=false`, and
  `automatic_source_posting=false` are mandatory response invariants.

## Explicit boundaries

- No SQL migration, production funding evidence, live/protected database
  action, automatic posting, synthetic opening balance, generic manual journal,
  merge, deployment, signing, release, or Master #296 checkbox change.
- This slice supplies software capability only. Actual capital is a Gate B
  Management/legal-go-live action using real retained evidence.
- Human Android/iOS acceptance remains deferred and unchecked.
- Client direct GCash remains a non-interactive Xendit placeholder.
