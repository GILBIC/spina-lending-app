# CILOG action-label extraction

This change moves one display-only Client Information Log helper into the shared text utility module.

## Extracted helper

- `_spina_cilog_action_label`

## Destination

- `spina_app/utilities/text.py`

## Preserved behavior

The helper name and function body are unchanged. It converts audit actions into display labels:

- updates involving pictures become `PICTURE`
- updates involving links become `LINK`
- updates involving areas become `AREA UPDATE`
- other updates become `EDIT`
- other actions are trimmed and uppercased
- empty actions become `CHANGE`

## Safety boundary

This extraction does not change database access, payment entry, allocations, balances, principal or interest calculations, 7x7 logic, renewals, reports, PDFs, authentication, roles, or Tkinter callbacks.

## Verification

A committed behavior fixture covers update-source priorities, create/delete labels, blank values, spaces, numbers, and fallback behavior. Permanent read-only CI compiles the app and text utility module and compares current behavior with the saved outputs.
