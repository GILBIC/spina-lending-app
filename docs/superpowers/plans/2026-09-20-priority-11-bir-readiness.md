# Priority 11: BIR readiness and registration preparation

## Authority, scope and baseline

Management's frozen Master296 amendment5628126560 defines this work. The user instructed Next after the complete P10 technical batch and has repeatedly asked for one whole implementation batch followed by combined verification, with routine decisions made from Notion/GitHub and preserved state. This authorizes the scoped preparation below without repeating design-approval rounds. No merge, actual filing, tax classification, signature, production financial operation or live activation is implied.

Base is the verified clean candidate0c1610c59db5e936a66c8c9383b91fe5656c2a31, not yet merged PR440. Preserve its checkout. P11 is isolated in spina-p11/priority-11/bir-readiness and will use a stacked PR against priority-10/release-hardening until the base is merged. Current code and official-source audits are retained outside the repository and will be incorporated into the public documentation without private facts.

Ruling: use the existing posted ledger and protected read authorization. A parallel accounting engine or automatic invoice/tax implementation would exceed the approved readiness scope. Generic CSV does not establish SAF acceptance. The technical output is a review package; taxpayer classification, current official-form copies, signatures, registration and production acceptance remain explicit gaps.

## Shared contracts

### Complete accounting export

Add GET /api/v1/management/financial-accounting/export with start_date and end_date (inclusive ISOdates; maximum366days) and only the existing Management role + accounting.view + approved device authority. Scope the audit to accounting.journal_events and immutable cancelled_journal_draft_audit; do not expose general core audit payloads or imply full system-wide logs.

Use one PostgreSQL REPEATABLE READ READ ONLY transaction and bounded statement timeout. Books contain all posted lines in range, retain reversals, exclude drafts/cancellations from posted money, include pre-range opening balances and by-account closing balances. Retired accounts remain visible. Deterministic dates/entryIDs/line order. Limit resource consumption explicitly (maximum100000 rows per dataset and maximum64MiB exported uncompressed content); return a clear413 before returning any download if too large. Never silently truncate.

Output application/zip; safe fixed ASCII filename; Cache-Control:no-store; nosniff. ZIP inventory: manifest.json, README.md, general-journal.csv, general-ledger.csv, trial-balance.csv, chart-of-accounts.csv, accounting-audit.csv, cancelled-drafts.json, print-view.html. Additional fiscal-period metadata is allowed inside manifest. Amounts use exact Decimal, never floats. Validate per-entry and cross-report balances. All display text escaped; CSV textual cells protect formula prefixes and controls while numeric money remains canonical. Metadata states date range/timezone, generation time/user, backend version, dataset row counts and hashes, posted-only and audit scopes, and internal-review status. Actual taxpayer/registration identity is not fabricated; missing required report identity stays explicit. Print view is static, escaped, printable and includes source/scope warnings.

The existing Management General Journal page gets one date-range export form and safe binary download using the existing API request blob support. Preserve session/role/device controls; ignore stale responses after disposal; revoke object URLs. No second dashboard, offline export queue or new phone-only flow.

### Registration preparation and version record

One offline command tools/build_bir_registration_package.py uses explicit clean repository/candidate SHA, explicit output directory, optional outside-repo profile/evidence JSON, and optional actual accounting export ZIP. It must never connect to a database or government service. Output unsigned review documents, required-file/readiness matrix, source-linked system description, schema/module inventory, data/role/process/control descriptions, official-source references and an exact Git/source-file hash manifest. Retain original supplied evidence files by hash and safe relative names; never copy arbitrary filesystem trees.

Treat initial system registration, annual books registration and electronic invoicing/reporting applicability separately. Missing company name/address/TIN/branch/RDO/classification, applicable official forms, signed/notarized documents, invoice/SAF decisions, operational policies and owner/accountant review are visible pending items. No registered/compliant/filed/certified label or generated acknowledgement/QR/signature. Profile facts and evidence are operator declarations, not independently authenticated legal findings. CLI errors must not dump private values.

Preserve a candidate-version manifest and allow comparison against a prior retained manifest. Record added/removed/changed financial/code/schema assets and require an impact review; do not guess legally major/minor changes or mutate a prior submitted record. No Git tag, signing key or registration is created. Validate source identity, paths/symlinks/sizes, ZIP duplicates/traversal/resource bounds, artifact hashes, malformed profile and reused output destinations. Require exact expected source before producing a version-bound packet; a dirty checkout fails.

### Narrow status cleanup

Correct the outdated Stage5B API notice and V1 tax policy status using retained A1-A6 implementation evidence. Preserve explicit Management posting, evidence/permissions, no automatic source posting, legacy cutover support and actual legal-book activation gates. Do not redesign mobile accounting screens or retrospectively rewrite stage history.

## Five technical milestones

1. Current official-requirement and repository inventory, with applicability limits.
2. Protected complete export + Management download.
3. Draft registration package + immutable version comparison and current source documentation.
4. Focused regressions, actual disposable PostgreSQL export proof, independent combined review.
5. Exact-source full CI/artifacts, one stacked draft PR, GitHub/Notion/local handoff; Create State capture if connection restored.

These percentages describe technical preparation only. Registration/go-live readiness is separate and remains pending actual facts and government processes.

## Verification

Prove >250 journals and >200 audit events are complete, opening/closing arithmetic, reversals and cancelled audit retained, drafts excluded, retired accounts, Unicode/exact money/formula handling, auth/device/role failure, invalid scope and oversized output rejection, consistent read-only snapshot/no mutations. Reuse existing disposable schema/fixtures and owned loopback DB only.

Package tests prove clean exact SHA/tree, tampered/missing/oversized/unsafe evidence rejection, false invoice/SAF/registration claims not promoted to acceptance, unsigned drafts not filed, prior manifests not modified, and source changes reported. One complete synthetic package and actual export sample are retained outside the repo.

Use existing patched Python/pytest/Ruff tooling rooted in this worktree. New lint/type errors are forbidden; historical scanner baseline is not blanket clearance. Full CI once after the assembled batch and necessary focused checks. Do not rerun P10's already-green baseline. Final review and necessary corrections precede publication; no production operation.

## Working ledger

- 20Sep2026: P10 candidate and frozen roadmap verified; official/repository research completed. Create State returns reauthentication-required; Notion/GitHub/local continuity remain usable.
- Ruling: separate P11 worktree preserves the still-open P10 exact-candidate evidence checkout. This is a new approved priority, not a duplicate of its completed implementation.
- 20Sep2026: complete export, Management download, offline package and seven preparation documents implemented. Independent review resolved JSONB decimal precision, pre-buffering resource limits, manifest row-count compatibility, contradictory registration flags, malformed JSON handling and source links in retained drafts. Existing accounting status wording was corrected without changing posting behavior.
- Focused verification: 37 export/API tests, 30 package tests (one Windows symlink-permission skip), seven accounting overview tests and all 618 portal tests passed. Actual disposable PostgreSQL proof retained 261 posted entries, 522 lines/events, opening/closing balances, reversal/cancelled/retired history and a concurrent snapshot; no export mutation occurred. Disposable resources were removed and stopped. CI now also builds the unsigned synthetic package from its exact source revision. Full CI and exact-commit package verification are the final technical milestone; no actual taxpayer filing or release acceptance is implied.
