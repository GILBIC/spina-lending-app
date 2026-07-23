# Append unique text helper extraction

## Helper

`_append_unique_text` combines an existing note value with a new note value while preserving the helper's original trimming and duplicate-suppression behavior.

## Extraction

The exact helper body was moved from the main SPINA desktop file to:

`spina_app/utilities/notes.py`

The original location now contains a same-name import, so `_merge_note_dict` remains unchanged.

## Preserved behavior

- blank additions leave the existing text unchanged
- blank existing values return the new text
- distinct text is joined with one newline
- additions already contained in the existing text are not appended again
- leading and trailing whitespace is removed
- existing behavior for non-string inputs is preserved

## Scope

This change does not alter note storage, note-merging rules, payments, balances, interest, 7x7, reports, PDFs, PostgreSQL operations, authentication, roles, or UI callbacks.

## Validation

The focused regression fixture was captured from the original helper before extraction. Permanent read-only CI compiles the app and utility module and compares all current outputs with that fixture.
