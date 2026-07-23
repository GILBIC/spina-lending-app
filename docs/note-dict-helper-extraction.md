# Note dictionary helper extraction

## Helper

`_as_note_dict` normalizes a stored note entry into a dictionary used by the note-merging code.

## Extraction

The exact helper body is moved from the main SPINA desktop file to:

`spina_app/utilities/notes.py`

The original location contains a same-name import, so its callers remain unchanged.

## Preserved behavior

- `None`, empty text, and whitespace-only text return an empty dictionary.
- Dictionary inputs return a shallow copy.
- Other values are converted to trimmed text under the `__default__` key.
- Existing dated keys and nested values are preserved.

## Scope

This change does not alter note-merging rules, payment logic, balances, interest, 7x7, reports, PostgreSQL operations, authentication, or UI callbacks.

## Validation

The focused regression test records the original outputs and verifies dictionary copy semantics before and after extraction. Permanent read-only CI compiles the app, utility module, extractor, and test.
