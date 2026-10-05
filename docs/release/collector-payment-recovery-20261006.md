# Collector payment recovery release

This release carries the Collector recovery changes from the accounting development branch onto production commit `471e7abe827a6209606cc5d19daf7356afe07293`. It preserves the Office workflow and on-screen signing changes already on main. No accounting-book migrations or configuration are included.

Android version: **0.5.1+8**, using the existing application ID and owner release certificate.

## Behavior

- The Collector can select Correction, confirm Undo payment with a reason, then record Unable to pay. The prior missed-payment count is restored before the new missed event adds one.
- Undo is restricted to the original recorder, today's latest unremitted cash receipt, and the reviewed route revision. A repeated request returns the original result without a second reversal.
- Paid-off loans remain accessible for correction on the payment date. Other-area work exposes recovery to the original recorder for supported loans. Other-area 7x7 corrections remain with Management because that screen cannot record the replacement collection entry.
- Remitted, Treasury-funded, penalty-linked, extra-principal and linked follow-up receipts retain their protected Management workflows.
- Legacy Pay-to-pass corrections update receipt allocation fields together with the balance and missed count.

## Verification and release

`tools/run_collector_payment_recovery_validation.py` creates its own loopback database and applies the production migration set through `0140_add_office_screen_signatures.sql`. It checks real reversal, correction, route, Treasury exclusion and concurrent retry behavior, requiring at least 50 tests and zero skipped or failed tests. It is included in the required financial CI job.

The local production-schema run passed 101 checks with zero skips; the focused Flutter recovery and other-area suite passed 17 tests. Required CI must also pass on the final PR head before merge. The deployment workflow verifies the active server SHA and public HTTPS hosts; the delivery workflow verifies the signed APK's source SHA, API endpoint, version and certificate.

The published APK still requires an update on each Collector phone. Automated tests do not substitute for a physical-device check of installation, login, Correction / Undo payment / Unable to pay, refresh and receipt history. Existing Android installations must be updated with the same certificate, without clearing app data.
