# Client Info Logs Modularization — Wave 78

Wave 78 completes the Client Info Logs extraction from the SPINA desktop entry file.

## Final module ownership

- `spina_app/repositories/client_info_logs.py`
  - creates the compatible `client_history` table when needed
  - reads newest history records
  - returns plain dictionaries
- `spina_app/services/client_info_logs.py`
  - maps internal field names to readable labels
  - parses old/new JSON snapshots
  - expands each history record into field-level changes
  - normalizes actions and display values
- `spina_app/tabs/client_info_logs.py`
  - owns the existing modern cards, charts, filters, table, details, render, and refresh presentation
- `spina_app/features/client_info_logs.py`
  - connects repository/service data to the modern tab
  - installs the tab once
  - refreshes logs after client refresh operations
  - preserves tolerant logging behavior

## Removed desktop blocks

The guarded extractor removes both:

1. `Easy Client Info Logs tab`, which contained schema/query/transformation code and startup hooks.
2. `v24 Modern Client Info Logs UI`, which rebound the modern presentation functions later in the file.

They are replaced by one `install_client_info_logs_feature(...)` call.

## Preserved behavior

- newest history first
- up to 5,000 loaded field changes in the modern view
- readable field labels
- money and percentage formatting
- UPDATE action classification into EDIT, PICTURE, LINK, or AREA UPDATE based on source
- modern search, action, loan-type, and date filters
- cards and charts
- automatic refresh after `refresh_clients`
- idempotent startup installation

## Safety and validation

- repository and service contain no Tkinter imports
- service performs no database mutations
- extractor applies twice to prove idempotence
- generated desktop app compiles
- Wave 78 layer, installer, and extraction tests run
- Cash Control Wave 77, Dashboard Wave 76, Wave 75, and Wave 74 regressions rerun
- generated publish is restricted to the single desktop entry file
- the temporary write-enabled publisher is removed after the validated production commit
