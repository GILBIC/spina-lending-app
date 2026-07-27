# Wave 61 Data Bank write-boundary plan

This planner analyzes the three adjacent Data Bank cell-write methods before extraction.
Delete Day remains protected and outside the boundary.

- Base merge: `Wave 60 merge 7f074da81499cc67f05a61517d9a5d87cd0b2a8b`
- Target methods: 3
- Total active source lines: **243**
- Risk class: **database write / payment mutation**

## `App._save_cell_edit`

- Lines: 9931–10014 (84)
- Signature: `self, client, day, dt_str, ent_widget`
- Source SHA-256: `3f421b85935c6bdb2f9a5e53a689a81a362a3332889104b858d2b5e3689c7410`
- Dedented SHA-256: `817aa342b4a960d1b53d0056589c2ce20ab7b26780c5675c7d76a4921337aead`
- Database calls: `["self.db.add_or_update_transaction", "self.db.get_transaction"]`
- Write-sensitive calls: `["self.db.add_or_update_transaction", "self.db.get_transaction"]`
- Full calls: `["_log_suppressed_once", "dict", "ent_widget.destroy", "ent_widget.get", "float", "get", "getattr", "messagebox.showerror", "replace", "row.keys", "self._pick_missed_reason", "self.db.add_or_update_transaction", "self.db.get_transaction", "self.refresh_data_grid", "simpledialog.askstring", "str", "strip"]`

## `App.delete_selected_cell`

- Lines: 10017–10104 (88)
- Signature: `self, *_`
- Source SHA-256: `218ac3dadc0dfd0540b27b1cac968da8a6cf1b2197f0973b90577810e7097d6a`
- Dedented SHA-256: `4d27860a520a0474b54ab11c46d3cdc67a0ff15ab3297dcba45c2813bcbf0df0`
- Database calls: `["self.db.delete_transaction", "self.db.get_transaction"]`
- Write-sensitive calls: `["self.db.delete_transaction", "self.db.get_transaction"]`
- Full calls: `["_date", "_log_suppressed_once", "getattr", "hasattr", "int", "messagebox.showerror", "messagebox.showinfo", "self._update_data_toolbar", "self.days_tree.get_children", "self.days_tree.set", "self.db.delete_transaction", "self.db.get_transaction", "self.refresh_data_grid", "strftime"]`

## `App._mark_missed_for_selected`

- Lines: 10108–10178 (71)
- Signature: `self`
- Source SHA-256: `df6545048882965daf68fca634445086426e358ca0b39fa4f319d865c648be67`
- Dedented SHA-256: `77c06f387f8902b78b683074d302cea98569535181549167fb42a88a9e391342`
- Database calls: `["self.db.add_or_update_transaction", "self.db.get_transaction"]`
- Write-sensitive calls: `["self.db.add_or_update_transaction", "self.db.get_transaction"]`
- Full calls: `["_date", "_log_suppressed_once", "dict", "get", "getattr", "int", "messagebox.showerror", "messagebox.showinfo", "replace", "row.keys", "self._mode_filter", "self._pick_missed_reason", "self.db.add_or_update_transaction", "self.db.get_transaction", "self.refresh_data_grid", "simpledialog.askstring", "str", "strftime", "strip"]`

## Protected boundary

- `App.open_delete_day_dialog` remains in the main application.
- Protected source SHA-256: `b41b22e7c18f2e7f391f4cd400a9f0034c9ca535d2c7b10a9045db35af3d0407`
- Daily Close, import, authentication, balances, interest, ADV/PASS, 7x7, reports, backups, and Collector Route remain outside this extraction.

## Planned validation

- Exact source, dedented source, signature, call-set, and database-call preservation
- Real save/update/zero-payment/missed-reason/delete behavior with fake database objects
- Existing Tkinter editor and Data Bank grid regression suites
- Protected Delete Day source hash
- Permanent architecture map and repository audits
- Desktop testing before merge
