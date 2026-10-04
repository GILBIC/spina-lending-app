# Loan payout destinations — C7/C8 continuation

Authority: approved Cash & GCash Control design C7/C8 and Task6, the owner decision “Either option but mostly to the collector since we are not an online lending app”, and the subsequent Continue instruction. Existing source controls remain binding. Base main0a576036; branch codex/loan-payout-destinations. PR498/496/497 remain separate. This implementation records manual payments; it never sends money.

## Contract

Collector is the default destination; direct named-borrower payout is an explicit alternative. An approved source, selected specific wallet, exact approved net proceeds, immutable source snapshot, selected destination and private recipient reference are reviewed together. No arbitrary payee or principal-as-net assumption. Changing a selection invalidates the preview. Only verified actual debit creates wallet movement. Planned payout, Collector receipt, borrower receipt and protected source completion are distinct facts.

Retain current Office/wet-signature/authorization/CIF/date/schedule and renewal acceptance/signature/offset/proof controls. A Collector receipt never stands for borrower receipt. Cash and GCash receipt evidence must state the actual method. The direct route cannot call a cash-only release endpoint with fabricated evidence. Source completion and its original accounting/schedule/credential intent must remain one protected transaction. Actual debit survives a later unavailable/invalid source completion as a visible exception; retries do not send or create money again.

Add only a private typed payout record and source bindings needed by those stages, using the existing Treasury command/audit/outcome/private-evidence infrastructure. Current source authority and assignment are rechecked on reads, commands and replay. Recipient views contain their own payout only; no whole-wallet history or beneficiary identifiers for other parties. No broad account grant. Locked sources cannot also take the old independent cash path. One active payout per protected source; exact event/source/context/payee/amount identity, reference uniqueness and current versions prevent duplicate funding.

GL remains explicitly reviewed and unmapped wallet/owner context remains blocked. Do not label an unmapped wallet as Office cash or invent a legal account mapping. Existing cash records retain their legacy semantics. New source-aware data must remain visible with entry disabled, restore with private bytes, and prevent unsafe rollback to old cash-only readers.

## Task 1 — Typed stages and private persistence

- Write failing strict-command and real PostgreSQL cases for both destinations, Collector default, wrong recipient, missing source authority, stale digest, cancelled/released source and private access.
- Implement source-specific preview/prepare with exact net amount, immutable reviewed destination/source, private payout state and source uniqueness. Preparation creates no cash movement and no activated loan.
- Verify defaults at the actual consumer boundary; server validation never chooses an arbitrary Collector when assignment is missing.

## Task 2 — One verified debit and separate recipient custody

- Reproduce debit-without-destination-confirmation, retry/new-request duplicate, wrong payee/amount/account, concurrent funding and audit rollback.
- Link the actual Treasury debit to its exact prepared payout; preserve unclassified debit exceptions on failed business linking.
- Record actual recipient confirmation separately, with private evidence and current recipient authority; Collector route remains pending borrower handover. Direct borrower route requires the named borrower's destination proof.

## Task 3 — Protected first-loan completion

- Exercise real approved/signed/authorized first-loan fixtures; prove both routes preserve exact packet/date/net amount/Office authority and source-private evidence.
- Extract a caller-owned transaction seam from existing release behavior, keeping existing cash API/retry behavior compatible.
- Add truthful typed payout receipt evidence and completion, atomic schedule/activation/disbursement/receipt/credential intent and payout consumption. No second Treasury debit; unmapped GL stays blocked.

## Task 4 — Protected renewal completion

- Bind approved accepted renewal, exact authoritative execution/offset/new-loan/net amount, required signers, source/context and current assigned Collector.
- Keep legacy cash path unchanged for unfunded renewals and block competing cash steps once a payout is bound.
- Use actual receipt method and distinct Collector/borrower confirmation; preserve proof review, independent borrower acceptance and old-loan settlement before activation. No new deductions or policy shortcuts.

## Task 5 — Shared Web/Windows and Android workflow

- Add explicit reviewed destination selection (Collector default), source-aware amount/payee, prepare/debit/receipt/completion states and private exact-retry recovery.
- Preserve existing form File nodes, pending locks, permissions/session teardown and source/evidence binding. No new financial persistence or automatic retry.
- Verify both routes, malformed/stale/cross-source responses, wrong actor, unknown results, small-screen keyboard and private recipient projections. Refresh PWA assets when needed.

## Task 6 — Integration, review and handoff

- Run real disposable schema/financial/source integration, existing affected Office/renewal tests, portal checks/build/tests and pinned Flutter analysis/tests. Verify restore/private bytes and compatibility guard.
- Perform one fresh independent whole-change review, repair important findings with RED/GREEN, then publish a separate draft PR and verify exact-head CI. Leave draft/open/unmerged, auto-merge off.
- Record exact implemented coverage, all remaining native/owner/other-adapter limits and source-aware disable behavior. Sync local/GitHub/Notion handoff; no declined Create State action.

## Review focus

Money can leave before source/borrower completion. Check all old and new cash paths for double release and false cash acknowledgment; current permission/assignment/evidence on replay; default Collector absent/changed; first-loan borrower without an active app account; revoked authorization or day rollover after debit; source cancellation/change and conflicting retries; direct-borrower path bypassing Collector without bypassing signatures/Office/borrower proof; protected renewal offset/activation; cross-context/GL/rollback/restore safety. Synthetic tests and CI do not establish native device/accessibility acceptance.
