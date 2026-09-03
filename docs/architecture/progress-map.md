# Product Progress Map — Archived

**Archived:** 2026-08-13, Asia/Manila

This file is retained only as a historical architecture/progress reference.

**Supersession notice — 2026-08-29:** the statement below that Client, Employee, and Management native mobile expansion was deferred to V1.1+ is historical release-scope context, not the current product architecture. The approved direction now requires functional Management/Employee capability parity across Desktop and mobile through shared FastAPI contracts and server-derived permissions. Release sequencing and completion still remain governed by Issue #296 and separately approved scope; this archived file is not a live tracker.

## Authoritative roadmap

GitHub Issue **#296 — SPINA V1 Final Master Plan — Release, Legal Go-Live, First Close** is now the **only authoritative V1 roadmap and completion checklist**.

Do not use the older wave order, PR status, planned offline-outbox sequence, mobile-scope assumptions, or “next” recommendations previously recorded in this file to decide current work. Those entries became stale as the accounting, mobile, remittance, 7x7 and ECL work progressed.

The final V1 plan in Issue #296 now fixes:

- the definition of **V1 Software Release Complete** separately from legal go-live and first-period close;
- explicit Management-only accounting posting with `automatic_source_posting=false`;
- final ECL readiness/calculation/posting order;
- final 7x7 operational/server/mobile parity gate;
- Android collector as the V1 mobile target;
- online-only collector writes for V1, with offline route view remaining read-only;
- Client Web Portal as the V1 client surface, with Client/Employee/Management native mobile expansion deferred to V1.1+;
- production engineering, security, UAT and release gates;
- frozen scope/change-control rules.

## Historical architecture material

The detailed modularization waves, old PR milestones and earlier product status remain available in Git history and the relevant merged PRs/issues. They should be consulted for provenance only, not for current prioritization.

New Client Fund, renewal fund, and smart client capacity are intended future server-authoritative modules. They are not implemented or calculated by the current live Management overview, and this archive does not assign them a release date.

## Tracking rule

- **Issue #296:** authoritative roadmap/checklist.
- **PRs and Issue #296 comments:** completion and validation evidence.
- **Notion SPINA Project Memory:** checkpoint/memory log only.
- **This file:** archived pointer only.

Do not expand this file into a second live tracker again.
