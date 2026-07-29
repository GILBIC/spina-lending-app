# Collector Route Modularization — Wave 79

Wave 79 fully modularizes the active Collector Route feature from the SPINA desktop entry file.

## Target architecture

- `spina_app/repositories/collector_route.py` — collector JSON persistence, active-area/client queries, ADV/reason/payment/link reads
- `spina_app/services/collector_route.py` — schema normalization, route coverage/conflict calculations, route row preparation, expected/paid totals, balance and completion helpers
- `spina_app/collector_route_report.py` — selected-route and full daily-ledger report engine, including closed-route copies
- `spina_app/collector_route_controller.py` — selection, filters, notes, inline/bulk editing, refresh orchestration, and route actions
- existing modern presentation modules remain responsible for widgets and dialogs
- `spina_app/features/collector_route.py` — one idempotent installer and runtime binding point

## Extraction boundary

The guarded extractor removes the active Collector Route runtime helper block, duplicated report patch, late selection/details fixes, balance/ADV/closed-copy patches, and direct Collector Route bindings from the desktop entry file. They are replaced by one Wave 79 feature installer.

## Safety gates

- exact production source generation is idempotent
- generated app compiles
- collector JSON writes are atomic and schema-compatible
- PostgreSQL-compatible reads retain legacy route aliases and linked Regular/7x7 behavior
- selected route remains two-payment-column, Regular-first, and deduplicated
- 7x7 balances keep the fixed-principal interest basis
- closed Collector Route copies preserve actual paid amounts and route layout
- Wave 78, Wave 77, Wave 76, Wave 75, and Wave 74 regressions stay green
