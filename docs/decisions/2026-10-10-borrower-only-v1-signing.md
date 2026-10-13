# Borrower-only V1 signing

The owner approved this recommendation on 10 October 2026 with “Approve, explain s4?” after reviewing S03. It resolves the earlier conflict between the September 11 borrower-only application scope and September 13 supporting-signature wording audit.

- New V1 applications and renewal terms use borrower-only signing. New guarantor, surety, or solidary co-maker creation is deferred pending separate approval of the forms and authority design.
- The borrower personally signs, accepts their terms, and confirms their own proceeds under the existing workflow. A relative's ability to pay an obligation does not authorize receipt or signing for the borrower.
- Existing supporting-party and signed evidence is preserved, including its original role and own-account signing path. Pending terms containing supporting or signed evidence must be reviewed separately instead of silently overwritten.
- Remote terms require exactly one borrower and the borrower's authoritative linked account. Office terms allow no electronic signer or one borrower with an optional linked account, but any provided account must still be the borrower's. Existing office and identity gates remain.

The implementation contract is [Collector renewal: signers and remote renewal](../features/collector_renewal_and_atomic_combined_pay.md#signers-and-remote-renewal). Historical planning documents retain their original dated scope and are superseded on new signer creation by this decision.

Read-only preflight on the connected database at 2026-10-10 09:55:22 UTC found one renewal request and zero required signer rows. No database records were changed. Recheck before release; this snapshot cannot establish future usage. No schema removal or historical-data migration is required.

This product decision does not assert a legal requirement for borrower-only signing. S04 company accounting was requested for explanation separately and is not included in this implementation.
