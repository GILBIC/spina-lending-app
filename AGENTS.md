# SPINA Repository Instructions

Before architecture, authorization, accounting, Desktop, Mobile, or Web work,
read:

1. `docs/architecture/platform-direction.md` for intended future behavior.
2. `docs/architecture/system-map.md` for current and target ownership.
3. `CONTEXT.md` for canonical domain terms.
4. GitHub Master Issue #296 and its latest approved amendments for live status,
   release gates, and exact sequencing.

Keep current implementation and future intention explicit. Merged code,
migrations, and tests describe current behavior; planned documents and Draft PRs
do not.

The platform authorization model is new and responsibility-based. Never map,
alias, template, or derive new grants from legacy Desktop profiles `Admin`,
`Encoder`, `Viewer`, or `System`. Preserve a legacy value only as historical
account-cutover evidence.

Evolve the current repository's SPINA Desktop in place. Do not copy an earlier
Desktop, reconnect a legacy Client/Staff backend, or create a second source of
truth. Supabase Auth proves identity; the GitHub-first FastAPI backend enforces
server-derived roles, permissions, resource scopes, device policy, and protected
commands; PostgreSQL owns official financial records and permanent audit
evidence.

Employees record and reconcile source transactions. Management financial totals
are derived from posted evidence, never manually entered. Sensitive accounting
uses maker-checker separation, server-validated double entry, explicit posting
authority, and append-only reversals.

Large implementation work requires a reviewed phase design and implementation
plan. Keep pull requests Draft until separately authorized, and do not merge,
deploy, restart a protected service, mutate protected/live data, or perform a
production cutover without explicit approval.
