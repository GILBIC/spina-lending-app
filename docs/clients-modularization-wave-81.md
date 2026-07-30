# Complete Clients modularization — Wave 81

Wave 81 consolidates the active SPINA Clients runtime behind one idempotent feature installer while preserving existing Regular and 7x7 behavior.

## Runtime boundary

`spina_app/features/clients.py` owns the final `App` and `LoanDB` bindings. Repeated installation performs direct assignments and does not grow a monkey-patch wrapper chain.

## Focused modules

- `spina_app/services/clients.py` — loan-type normalization, base and flexible due schedules
- `spina_app/client_controller.py` — optimized/fallback refresh actions, bulk area assignment, delete, link/unlink, import/export
- `spina_app/client_pictures.py` — client-picture storage, cleanup, and UI actions
- `spina_app/client_archive.py` — archive, restore, row-ID restoration, and archived-client dialog
- `spina_app/client_renewal.py` — renewal dialog and PostgreSQL-safe renewal writes
- `spina_app/client_application.py` — modern client form plus add/edit actions
- `spina_app/client_queries.py` and `spina_app/linked_client_queries.py` — existing focused read-query boundaries
- `spina_app/tabs/clients.py` — modern Clients presentation and optimized row rendering

## Preserved behavior

- stable `client_uid` and `person_uid` linking
- Regular and 7x7 record separation
- fixed-principal 7x7 daily-interest basis
- PostgreSQL-safe renewal history writes
- hierarchical Areas and bulk assignment
- archive/history restoration
- client pictures
- optimized large-database refresh
- flexible salary, weekly, twice-weekly, nth-weekday, and exact-day schedules

## Bug fixed during extraction

The legacy twice-weekly weekday parser contained two literal backspace control characters where regex word boundaries were intended. Wave 81 normalizes them to `\b`, so rules such as `weekly Tuesday Friday` correctly produce `Weekly Tue/Fri` and recognize both due days.

## Validation

The guarded workflow:

1. inventories the active Clients runtime;
2. applies extraction twice;
3. normalizes the weekday regex twice;
4. compiles the desktop entry point and all Clients modules;
5. runs complete Clients regressions;
6. runs Waves 31, 32, 36, 38, 55, and 70 compatibility;
7. runs Reports Wave 80, Collector Route Wave 79, and Wave 74/75 financial compatibility;
8. checks the generated diff before allowing the scoped publisher.

Only the validated desktop file and six generated Clients modules are published by the workflow.
