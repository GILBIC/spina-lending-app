"""Data Bank payment mutation helpers extracted in Wave 61."""
from __future__ import annotations

_DATABANK_CELL_WRITE_DEPENDENCIES = {}
_PROTECTED_GLOBALS = {'_DATABANK_CELL_WRITE_DEPENDENCIES', 'delete_selected_cell', '_save_cell_edit', '_PROTECTED_GLOBALS', 'configure_databank_cell_write_dependencies', '_mark_missed_for_selected', 'DATABANK_CELL_WRITE_METHODS'}

def configure_databank_cell_write_dependencies(namespace):
    _DATABANK_CELL_WRITE_DEPENDENCIES.clear()
    _DATABANK_CELL_WRITE_DEPENDENCIES.update(namespace)
    for name, value in namespace.items():
        if name not in _PROTECTED_GLOBALS:
            globals()[name] = value

DATABANK_CELL_WRITE_METHODS = {'_save_cell_edit': {'lines': 84, 'source_sha256': '3f421b85935c6bdb2f9a5e53a689a81a362a3332889104b858d2b5e3689c7410', 'dedented_sha256': '817aa342b4a960d1b53d0056589c2ce20ab7b26780c5675c7d76a4921337aead', 'signature': 'self, client, day, dt_str, ent_widget', 'calls': ['_log_suppressed_once', 'dict', 'ent_widget.destroy', 'ent_widget.get', 'float', 'get', 'getattr', 'messagebox.showerror', 'replace', 'row.keys', 'self._pick_missed_reason', 'self.db.add_or_update_transaction', 'self.db.get_transaction', 'self.refresh_data_grid', 'simpledialog.askstring', 'str', 'strip'], 'db_calls': ['self.db.add_or_update_transaction', 'self.db.get_transaction']}, 'delete_selected_cell': {'lines': 88, 'source_sha256': '218ac3dadc0dfd0540b27b1cac968da8a6cf1b2197f0973b90577810e7097d6a', 'dedented_sha256': '4d27860a520a0474b54ab11c46d3cdc67a0ff15ab3297dcba45c2813bcbf0df0', 'signature': 'self, *_', 'calls': ['_date', '_log_suppressed_once', 'getattr', 'hasattr', 'int', 'messagebox.showerror', 'messagebox.showinfo', 'self._update_data_toolbar', 'self.days_tree.get_children', 'self.days_tree.set', 'self.db.delete_transaction', 'self.db.get_transaction', 'self.refresh_data_grid', 'strftime'], 'db_calls': ['self.db.delete_transaction', 'self.db.get_transaction']}, '_mark_missed_for_selected': {'lines': 71, 'source_sha256': 'df6545048882965daf68fca634445086426e358ca0b39fa4f319d865c648be67', 'dedented_sha256': '77c06f387f8902b78b683074d302cea98569535181549167fb42a88a9e391342', 'signature': 'self', 'calls': ['_date', '_log_suppressed_once', 'dict', 'get', 'getattr', 'int', 'messagebox.showerror', 'messagebox.showinfo', 'replace', 'row.keys', 'self._mode_filter', 'self._pick_missed_reason', 'self.db.add_or_update_transaction', 'self.db.get_transaction', 'self.refresh_data_grid', 'simpledialog.askstring', 'str', 'strftime', 'strip'], 'db_calls': ['self.db.add_or_update_transaction', 'self.db.get_transaction']}}

def _save_cell_edit(self, client, day, dt_str, ent_widget):
    """Save an edited day-cell value into the DB (no undo/redo).
    - amount == 0 → prompt for reason (stored in description)
    - amount  > 0 → clears description
    """
    from tkinter import messagebox, simpledialog

    # 1) Parse input
    try:
        raw = (ent_widget.get() if ent_widget else "").strip()
        amount = float(raw) if raw != "" else 0.0
    except Exception:
        messagebox.showerror("Invalid", "Enter a valid number.")
        try:
            if ent_widget: ent_widget.destroy()
        except Exception as __spina_exc:
            _log_suppressed_once('excpass_0255', 'suppressed exception excpass_0255', __spina_exc)
            pass
        return

    # 2) Load previous (for prefill reason only)
    try:
        row = self.db.get_transaction(client, dt_str)
        if row is not None:
            try:
                old_amt = float(row["payment"])
            except Exception:
                old_amt = float(dict(row).get("payment") or 0.0)
            old_desc = (row["description"] if "description" in row.keys()
                        else dict(row).get("description")) or ""
        else:
            old_amt, old_desc = 0.0, ""
    except Exception:
        old_amt, old_desc = 0.0, ""

    # 3) If zero payment, ask for a (multi) reason string
    desc = ""
    if amount == 0.0:
        prefill = (old_desc or "").replace("\n", " ").strip()
        parent = getattr(self, "days_tree", getattr(self, "root", None))
        try:
            desc = self._pick_missed_reason(parent, prefill_text=prefill)
        except Exception:
            # Fallback simple input
            desc = simpledialog.askstring("Missed Payment", "Enter reason(s):", initialvalue=prefill)
        if desc is None:
            # user cancelled → just close editor and exit
            try:
                if ent_widget: ent_widget.destroy()
            except Exception as __spina_exc:
                _log_suppressed_once('excpass_0256', 'suppressed exception excpass_0256', __spina_exc)
                pass
            return
        desc = (desc or "").strip()

    # 4) Write to DB
    try:
        self.db.add_or_update_transaction(
            client, dt_str, amount,
            description=(desc if amount == 0.0 else "")
        )
    except Exception as e:
        messagebox.showerror("Save Error", str(e))
        try:
            if ent_widget: ent_widget.destroy()
        except Exception as __spina_exc:
            _log_suppressed_once('excpass_0257', 'suppressed exception excpass_0257', __spina_exc)
            pass
        return

    # 5) Cleanup editor + refresh UI gracefully
    try:
        if ent_widget: ent_widget.destroy()
    except Exception as __spina_exc:
        _log_suppressed_once('excpass_0258', 'suppressed exception excpass_0258', __spina_exc)
        pass

    # If you have a lightweight way to update just this cell, do it here.
    # Otherwise, refresh the whole grid to keep it simple & safe:
    try:
        self.refresh_data_grid()
    except Exception:
        # soft-fail; UI stays as-is if refresh fails
        pass


def delete_selected_cell(self, *_):
    from datetime import date as _date
    import tkinter.messagebox as messagebox

    client = getattr(self, "_dbank_last_client", None)
    day    = getattr(self, "_dbank_last_day", None)
    if not client or not day:
        messagebox.showinfo("Delete", "Click a payment cell first (right grid).")
        return

    # Build YYYY-MM-DD from current grid month/year
    try:
        dt = _date(self.grid_year, self.grid_month, int(day)).strftime("%Y-%m-%d")
    except Exception:
        messagebox.showerror("Delete", "Invalid day/month/year.")
        return

    # Check if there is something to delete
    has_txn = False
    try:
        row = self.db.get_transaction(client, dt)
        if row is not None:
            has_txn = True
    except Exception:
        has_txn = False

    # If no existing transaction → just blank the UI cell and return
    if not has_txn:
        try:
            if hasattr(self, 'days_tree') and self.days_tree:
                for item in self.days_tree.get_children():
                    try:
                        if self.days_tree.set(item, 'client') == client:
                            # Column id assumed 'd{day}' (e.g., d1..d31)
                            self.days_tree.set(item, f'd{day}', '')
                            break
                    except Exception as __spina_exc:
                        _log_suppressed_once('excpass_0259', 'suppressed exception excpass_0259', __spina_exc)
                        pass
        except Exception as __spina_exc:
            _log_suppressed_once('excpass_0260', 'suppressed exception excpass_0260', __spina_exc)
            pass
        try:
            # If you keep a toolbar updater, call it; otherwise this is harmless
            if hasattr(self, '_update_data_toolbar'):
                self._update_data_toolbar()
        except Exception as __spina_exc:
            _log_suppressed_once('excpass_0261', 'suppressed exception excpass_0261', __spina_exc)
            pass
        return

    # Delete from DB
    try:
        self.db.delete_transaction(client, dt)
    except Exception as e:
        messagebox.showerror("Delete", f"Failed to delete payment: {e}")
        return

    # Update UI — either targeted cell update or full refresh
    updated = False
    try:
        if hasattr(self, 'days_tree') and self.days_tree:
            for item in self.days_tree.get_children():
                try:
                    if self.days_tree.set(item, 'client') == client:
                        self.days_tree.set(item, f'd{day}', '')
                        updated = True
                        break
                except Exception as __spina_exc:
                    _log_suppressed_once('excpass_0262', 'suppressed exception excpass_0262', __spina_exc)
                    pass
    except Exception:
        updated = False

    if not updated:
        # When in doubt, refresh the whole grid to keep things consistent
        try:
            self.refresh_data_grid()
        except Exception as __spina_exc:
            _log_suppressed_once('excpass_0263', 'suppressed exception excpass_0263', __spina_exc)
            pass

    try:
        if hasattr(self, '_update_data_toolbar'):
            self._update_data_toolbar()
    except Exception as __spina_exc:
        _log_suppressed_once('excpass_0264', 'suppressed exception excpass_0264', __spina_exc)
        pass


def _mark_missed_for_selected(self):
    """Right-click action in Data Bank: set selected day as MISSED (0.0) with a reason."""
    from datetime import date as _date
    from tkinter import messagebox, simpledialog

    client = getattr(self, "_dbank_last_client", None)
    day    = getattr(self, "_dbank_last_day", None)
    if not client or not day:
        try:
            messagebox.showinfo("Missed Payment", "Click a day cell first (right grid).")
        except Exception as __spina_exc:
            _log_suppressed_once('excpass_0265', 'suppressed exception excpass_0265', __spina_exc)
            pass
        return

    try:
        dt_str = _date(self.grid_year, self.grid_month, int(day)).strftime("%Y-%m-%d")
    except Exception:
        try:
            messagebox.showerror("Missed Payment", "Invalid day/month/year.")
        except Exception as __spina_exc:
            _log_suppressed_once('excpass_0266', 'suppressed exception excpass_0266', __spina_exc)
            pass
        return

    # Prefill from existing description (if any)
    prefill = ""
    try:
        row = self.db.get_transaction(client, dt_str, loan_type=self._mode_filter())
        if row is not None:
            try:
                prefill = (row["description"] if "description" in row.keys() else dict(row).get("description")) or ""
            except Exception:
                prefill = ""
    except Exception:
        prefill = ""

    # Pick reason(s)
    reason = None
    try:
        reason = self._pick_missed_reason(self.root, prefill_text=(prefill or "").replace("\n", " ").strip())
    except Exception:
        try:
            reason = simpledialog.askstring("Missed Payment", "Enter reason(s):", initialvalue=(prefill or "").strip())
        except Exception:
            reason = None
    if reason is None:
        return
    reason = str(reason or "").strip()

    # Write 0.0 payment + reason
    try:
        self.db.add_or_update_transaction(
            client, dt_str, 0.0,
            description=reason,
            loan_type=self._mode_filter()
        )
    except Exception as e:
        try:
            messagebox.showerror("Missed Payment", f"Failed to save: {e}")
        except Exception as __spina_exc:
            _log_suppressed_once('excpass_0267', 'suppressed exception excpass_0267', __spina_exc)
            pass
        return

    # Refresh grid
    try:
        self.refresh_data_grid()
    except Exception as __spina_exc:
        _log_suppressed_once('excpass_0268', 'suppressed exception excpass_0268', __spina_exc)
        pass
