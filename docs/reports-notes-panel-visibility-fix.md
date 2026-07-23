# Reports Notes dialog fix

The modern Reports screen used an inline notes drawer. On Windows, clicking `Notes` changed the button to `Hide Notes`, but the drawer remained invisible even though Tk reported it as packed.

The app already contains a complete `_open_note_dialog` method that opens `NoteEditorDialog` for the selected Reports client. The modern Reports Notes button now uses that existing method instead of the unreliable inline drawer callback.

The dialog preserves the selected client, report end date, current loan view, client UID, and person UID. No note storage, note merging, payment, balance, report calculation, PostgreSQL, authentication, or role/access logic changed.

Desktop smoke test:

1. Open Reports.
2. Select a client.
3. Click Notes.
4. Confirm a separate note editor window opens for the selected client.
5. Close the note editor window and confirm Reports remains usable.
