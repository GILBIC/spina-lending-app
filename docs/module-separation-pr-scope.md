# Scope of this PR

This PR only adds planning and validation tools for future module separation.

It does not:

- move any production function or class
- create the final `spina_app` package structure
- change application startup
- change Tkinter callbacks
- change PostgreSQL behavior
- change reports or PDFs
- change payments, balances, interest, 7x7, renewals, collectors, payroll, authentication, backups, or report math

Any production extraction must happen in a later, narrowly scoped PR after the generated JSON report is reviewed.
