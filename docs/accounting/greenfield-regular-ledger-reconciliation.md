# Stage 5D.27 — Greenfield Regular protected-ledger reconciliation

Stage 5D.27 is a prerequisite engineering slice inside the existing V1 **renewal/refinance/restructure source-event accounting** item. It does not add a new top-level master-plan item.

## Purpose

Stage 5D.25 established a protected greenfield initial Regular EIR/carrying anchor from an uncancelled protected new-loan release and verified original signed-contract cash flows. Stage 5D.26 then produced a deterministic read-only EIR roll-forward to the authoritative Stage 5D.24 renewal execution date.

Stage 5D.27 connects that measurement chain to the immutable Stage 5D.17/5D.18 protected Regular collection accounting history. It answers a narrower question before renewal modification/derecognition treatment may be considered:

> Does the actually posted protected Regular ledger history exactly reproduce the event-date EIR state from the Stage 5D.25 greenfield anchor through every pre-renewal cash source?

## Exact reconciliation contract

For each supported active PAYMENT/ADV before the renewal business date, the stage independently replays the already-approved accounting coordinates:

- each positive EIR segment uses **Dr Accrued Interest Receivable / Cr Regular Interest Income**;
- cross-period EIR cents use the existing largest-remainder allocation policy;
- deterministic EIR source identity remains `eir_accrual:collection:<transaction_uuid>:fiscal_period:<period_uuid>`;
- collection identity remains `collection:<transaction_uuid>`;
- collection lines remain **Dr Collector Custody**, then credits only to **Accrued Interest Receivable** and/or **Loans Receivable - Regular** according to the event-date EIR allocation;
- posting date, fiscal period, source reference, source key, line dimensions, balances and the immutable Stage 5D.17 posting audit must all match exactly.

A voided source may be ignored only when its protected posted history has an exact Stage 5D.18 controlled reversal. Active sources with reversal history, partial posting/audit state, duplicated source identities, unprotected posted Regular journals, changed lines, changed dimensions or changed posting coordinates all fail closed.

The resulting loan and accrued-interest ledger components are compared with the Stage 5D.26 state immediately after the final pre-renewal cash source. Operational settlement is never substituted for accounting carrying amount.

## Renewal-boundary no-cash EIR remains separate

The existing Stage 5D.13–5D.18 protected Regular path is collection-triggered. Stage 5D.26 may therefore contain a positive **no-cash EIR tail** from the last cash boundary through the authoritative renewal business date that has no posted journal in that path.

Stage 5D.27 deliberately does **not** invent or silently post that accrual. When the protected source journals reconcile but this tail remains positive, exact reconciliation returns:

`renewal_boundary_eir_accrual_not_posted`

with `protected_regular_journals_reconciled=true` but `accounting_carrying_amount_ready=false`.

A later protected stage must establish the renewal-boundary no-cash EIR accrual evidence/coordinates and controlled accounting lifecycle before the Stage 5D.26 target can become authoritative renewal-date carrying evidence.

## Safety boundaries

Stage 5D.27 is read-only in production. Migration 0053 creates only a reconciliation target view. The API creates no source event, journal entry, journal line, preparation, posting or reversal. The SQL coarse gate never enables accounting carrying amount; only the exact in-memory reconciliation may report readiness, and only when every protected journal and target component agrees and no unposted tail remains.

`journal_lines_enabled=false` and `automatic_source_posting=false` remain enforced.

Disposable integration validation must use a newly initialized loopback-only PostgreSQL cluster. Synthetic protected journals used to exercise the real Stage 5D.17 posting function are permitted only inside that disposable cluster and must never run against production or Supabase data.
