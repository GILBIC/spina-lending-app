# Merge note dictionary helper extraction

## Helper

`_merge_note_dict` combines a source note entry into a destination note entry while preserving existing text.

## Extraction

The exact helper body is moved from the main SPINA desktop file to:

`spina_app/utilities/notes.py`

The original location keeps a same-name import, so all callers remain unchanged.

## Preserved behavior

- normalizes both inputs through `_as_note_dict`
- ignores blank or `None` incoming values
- fills missing or blank destination keys
- appends distinct conflicting text with `_append_unique_text`
- preserves the current substring duplicate rule
- returns a new destination dictionary instead of mutating the input dictionaries

## Scope

This change does not alter note storage, legacy-note migration decisions, payments, balances, interest, 7x7, reports, PDFs, PostgreSQL operations, authentication, roles, or UI callbacks.

## Validation

The behavior fixture is captured from the original function before extraction. The focused regression test covers default notes, dated notes, conflicts, duplicates, blank values, non-dictionary inputs, and input isolation.
