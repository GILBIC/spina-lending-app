# Reports notes panel visibility fix

The Reports notes button could change to `Hide Notes` while the notes drawer remained outside the visible area beneath the expanding reports table.

This focused fix reserves bottom space for the notes drawer and separator. It does not change note storage, note merging, payments, balances, reports, PostgreSQL operations, authentication, or other business logic.

Desktop smoke test:

1. Open Reports.
2. Click Notes.
3. Confirm the Report Notes drawer becomes visible.
4. Click Hide Notes and confirm it closes.
