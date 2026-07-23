# Reports notes panel visibility fix

The Reports notes button could change to `Hide Notes` while the notes drawer remained outside the visible area beneath the expanding reports table.

The Reports table is packed with `expand=True`, so later widgets can receive no visible space. This focused fix inserts the notes drawer and separator before the expanding table in Tk pack order while keeping them anchored at the bottom.

It does not change note storage, note merging, payments, balances, reports calculations, PostgreSQL operations, authentication, or other business logic.

Desktop smoke test:

1. Open Reports.
2. Click Notes.
3. Confirm the Report Notes drawer becomes visible above the client report list.
4. Click Hide Notes and confirm it closes.
