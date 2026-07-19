# Scope

This PR prepares one guarded extraction only: the top-level `fmt_currency` helper.

It does not change the 48,000-line production application yet. The tool must be merged, run in dry-run mode, and then applied locally so the generated app/module diff can be reviewed in a separate PR.

No database, payment, balance, 7x7, PDF, report, authentication, collector, payroll, backup, PostgreSQL, or Tkinter callback code is selected.
