# R4 — Web provider payment-code handoff

Approved source: [SPINA approved-idea/code-gap review, R4](https://app.notion.com/p/3e35ade7bef48197be58f91c865a9d6f), and the user's approval to complete the recorded priorities.

Client Web now exposes a nonblank provider `qr_value` as an escaped, read-only GCash QR/payment code, including when no checkout URL exists. Copy preserves the provider code; unavailable clipboard access leaves a selectable manual fallback. Existing intent controls are bound on initial display and after creation or refresh. The protected intent refresh remains the source of payment status.

This follows the existing Android code-copy behavior. An opaque value is not claimed to be a scannable QR image. No QR service, settlement verification, official posting, provider setup, production request or migration is introduced; the existing official-payment warning remains visible.

Verification: six Client GCash tests passed, including QR-only escaping/unsafe-link rejection, exact copy, clipboard denial, initial/refreshed binding and no API call from copying. Two new regressions failed before implementation. Integrated R2/R3/R4/R6 Portal syntax, all 736 tests and build passed. Root independently reviewed the R4 diff without further findings.
