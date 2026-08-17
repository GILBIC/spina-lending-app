# Delegated Collector area access

## Status

Management-approved CA4 refinement. This document defines the required behavior before Collector UI sign-off. It does not by itself enable access or change financial records.

## Purpose

Allow a Collector to temporarily work in an area or sub-area owned by another Collector, with the assigned Collector's explicit consent, while preserving permanent route ownership, recorder identity, cash custody, remittance controls, and audit history.

## Area hierarchy

SPINA areas are hierarchical and may have unlimited depth. A Collector may own multiple assigned paths, and each path may contain sub-areas.

Example:

- CARDONA
  - Looc
  - Calahan
- MORONG
  - Bombongan
  - Lagundi

A grant may cover:

1. one selected sub-area/path;
2. one selected area and all descendants;
3. multiple selected paths owned by the same assigned Collector; or
4. **All my assigned areas**, meaning every area currently owned by the Collector granting access.

**All my assigned areas never means every area in SPINA.** A Collector can grant only scope that is currently assigned to that same Collector.

## Ownership versus delegated access

Permanent assignment and delegated access are separate concepts.

- **Assigned route**: permanent route ownership and the Collector's normal Daily Route/Master list.
- **Delegated area access**: temporary operational authority granted by the assigned Collector over selected owned area paths.
- A Collector may have both at the same time.
- Delegated clients never become part of the visiting Collector's permanent Daily Route or Master list.
- Granting access never changes the client's assigned Collector or assigned area.

## Consent authority

- Only the Collector who owns an area may grant or revoke delegated access to that owned scope.
- One Collector cannot grant or revoke another Collector's area.
- A request for **All Areas** is a convenience request only. It must be split by owner, and each assigned Collector independently decides access to their own assigned areas.
- Revocation blocks new delegated work immediately. Already-posted official transactions remain immutable history and continue through the normal remittance/custody flow.
- Expired access behaves the same as revoked access for new actions.

## Delegated Collector workspace

Approved delegated areas appear in a separate **Other-Area Work** workspace, never mixed into **My Daily Route**.

The visiting Collector may perform the normal Collector collection workflow inside the granted scope, subject to the same server feature gates, stale-route checks, idempotency, device authorization, and online-only financial-write rules as their own route. This includes, when otherwise allowed for that loan:

- Regular payment;
- 7x7 payment through the protected dedicated allocator;
- exact covered dates / ADV;
- unable-to-pay / PASS;
- permitted collection notes;
- official receipt/balance viewing;
- correction of the visiting Collector's own eligible unlocked entry before remittance;
- remittance of the visiting Collector's cross-area collections.

Delegated access does **not** transfer route ownership or administrative authority. It does not allow the visiting Collector to reassign clients/areas, change another Collector's route configuration, alter another Collector's historical receipt, bypass Management-only actions, or bypass any protected loan/accounting rule.

## Immediate assigned-route visibility

When a visiting Collector posts an official entry for a delegated client, the assigned Collector's authoritative Daily Route must reflect that server transaction immediately after refresh.

The assigned route should clearly show, as applicable:

- collected / unable-to-pay / covered status;
- amount and official receipt;
- **Collected by / Recorded by: <visiting Collector>**;
- cash-custody holder while not yet remitted;
- remittance status.

This prevents the assigned Collector from visiting the same client again because another Collector already handled that client.

The visiting Collector does not edit the assigned Collector's route. Both screens independently render the same authoritative server transaction.

## Separate cross-area work and cash summary

The visiting Collector must have a **My Other-Area Collections** summary separate from their own assigned-route collections.

At minimum it groups by assigned Collector and area/path and shows:

- client;
- loan type;
- official receipt number;
- amount;
- recorder;
- collection time/date;
- remittance number when applicable;
- current cash/remittance state.

Required states:

1. **Not yet remitted** — official cross-area receipt exists and cash remains with the visiting Collector.
2. **Awaiting acceptance** — remittance has been submitted and included entries are locked, but cash custody has not transferred.
3. **Accepted** — the selected recipient confirmed physical receipt and custody transferred.

This summary must derive from the authoritative collection transaction/remittance/custody records. It must not create a second financial ledger or duplicate payment.

## Remittance destinations

Cross-area collections may be remitted to:

- the authoritative assigned Collector for those transactions; or
- an authorized Management recipient.

Submission locks included Collector-editable entries. Acceptance, not submission, transfers cash custody.

Recorder identity never changes. Example history remains:

- Assigned Collector: Collector A
- Recorded by: Collector B
- Remitted to / accepted by: Collector A or Management
- Receipt: original official receipt

## Required server enforcement

Every delegated read or write must be revalidated server-side. The phone must not be trusted merely because it displays a granted area.

For each delegated action the server must verify:

- authenticated active Collector/device and required permission;
- active non-expired, non-revoked grant covering the client's exact hierarchical area path;
- grantor still owns the granted scope;
- client/loan is still inside the granted scope;
- current route/loan revision and normal collection eligibility;
- transaction recorder and assigned-Collector attribution;
- remittance/lock state for corrections;
- existing idempotency and duplicate protections.

If ownership changes while a grant is active, the grant must fail closed until the new assigned owner explicitly grants access. A stale grant must never silently follow an area to a new owner.

## Proposed protected data model

Implementation should use dedicated audited authorization records rather than changing `lending.collector_area_assignments`.

Recommended concepts:

- access request: requester, requested owner/scope, request status, requested duration/reason;
- access grant: grantor, visiting Collector, owned area-path scope, descendant coverage flag, effective/expiry time, revoked state;
- immutable audit events for request, allow, decline, revoke, expiry-sensitive use, and any Management override if a separate policy is ever approved.

The permanent assigned-area table remains the source of route ownership. Delegated grants are authorization overlays only.

## Android UI acceptance

CA4 cannot be signed off until the exact Android candidate proves:

- own assigned route remains separate from delegated work;
- assigned Collector can grant/revoke only their own area/sub-area scope;
- **All my assigned areas** never exposes another owner's scope;
- visiting Collector sees only active approved scope;
- visiting Collector can use permitted normal collection actions in that scope;
- assigned route reflects delegated collection immediately with recorder attribution;
- no duplicate visit/payment is encouraged by stale UI;
- visiting Collector sees Not yet remitted / Awaiting acceptance / Accepted summary states;
- remittance to assigned Collector or Management preserves original recorder and transfers custody only on acceptance;
- revoked/expired/stale-owner grant fails closed;
- offline delegated financial writes remain blocked.

## Migration from current Other Area Payment search

The current open search-based Other Area Payment entry is not the final CA4 design. Collector access must move to grant-scoped **Other-Area Work**. Management direct payment remains a separate Management workflow and is not governed by Collector-to-Collector delegated access.
