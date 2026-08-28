# ADR 0002: One Office Working Fund with Tracked Allocations

- **Status:** Accepted as business architecture; implementation requires written-spec and plan approval
- **Date:** 2026-08-28
- **Decision owner:** Management

SPINA will represent office-controlled cash as one Office Working Fund backed by
official ledger, custody, and reconciliation evidence. New Client Fund is a
user-facing tracked allocation and capacity view within that fund, while new-
client releases, renewal net releases, authorized obligations, and transfers
use tagged, expiring reservations against the same real cash. This preserves
flexible office operation and owner visibility without duplicating money. A
deterministic server-side New Client Fund Capacity Guard will combine current
spendable cash, protected reserves, commitments, portfolio limits, and operating
capacity; it will explain Green, Amber, or Red results and atomically reserve
cash, but it will not replace credit approval or accountable human authority.

## Alternatives considered

- **Separate physical or ledger funds for new clients and renewals:** rejected
  because it fragments custody, creates idle silos, and risks double counting.
- **One editable cash log without reservations:** rejected because concurrent
  approvals can overcommit the same money and totals lack protected evidence.
- **Autonomous AI funding decisions:** rejected because official balances and
  lending authority must remain deterministic, reproducible, and accountable.

## Consequences

- Every purpose view must reconcile to one underlying cash and custody ledger.
- New Client Fund must never be posted or displayed as extra cash.
- Approved pending releases reserve exact cash atomically and expire or consume
  through protected commands.
- Owner oversight uses explicit Management permissions; office delegation is
  limited, versioned, and maker-checker controlled.
- Existing disbursement and renewal evidence remains authoritative for actual
  releases and must be integrated rather than replaced.
