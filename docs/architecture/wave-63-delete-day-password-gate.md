# Wave 63 — Delete Day Password Gate

Wave 63 changes the Data Bank **Delete Day** password-verification error path from fail-open to fail-closed.

## Root cause

The Wave 62 extraction preserved the legacy behavior exactly. In that behavior, an exception raised by `_prompt_current_password(...)` assigned `ok = True`, allowing the destructive database operation to continue even though the application could not verify the current account password.

## Corrected behavior

When password verification raises an exception, Delete Day now:

1. shows a `Password verification failed` error,
2. returns immediately,
3. does not call `delete_transactions_for_day`, and
4. does not refresh Data Bank, Reports, or Audit as though deletion succeeded.

Normal successful verification and ordinary wrong-password cancellation remain unchanged.

## Permanent regression

`tools/test_databank_delete_day_password_gate_wave_63.py` forces the password service to raise and verifies that no database delete or refresh occurs.
