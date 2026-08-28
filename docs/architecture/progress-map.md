# Product Progress Map — Archived

**Archived:** 2026-08-13, Asia/Manila

This file is retained only as a historical architecture/progress reference.

## Authoritative roadmap

GitHub Issue **#296 — SPINA V1 Final Master Plan — Release, Legal Go-Live, First Close** is now the **only authoritative V1 roadmap and completion checklist**.

Do not use the older wave order, PR status, planned offline-outbox sequence, mobile-scope assumptions, or “next” recommendations previously recorded in this file to decide current work. Those entries became stale as the accounting, mobile, remittance, 7x7 and ECL work progressed.

The final V1 plan in Issue #296 now fixes:

- the definition of **V1 Software Release Complete** separately from legal go-live and first-period close;
- explicit Management-only accounting posting with `automatic_source_posting=false`;
- final ECL readiness/calculation/posting order;
- final 7x7 operational/server/mobile parity gate;
- Management, Employee, Collector, and Client mobile apps on both Android and
  iOS as V1 targets, with Android UI approval first and iOS parity afterward;
- online-only collector writes for V1, with offline route view remaining read-only;
- Client Web Portal as an additional V1 client surface using the same backend;
- production engineering, security, UAT and release gates;
- frozen scope/change-control rules.

## Approved future platform direction

Management approved a broader future platform model on 2026-08-28. The stable
intention, clean new role decision, employee accounting responsibilities, and
phased surface/data migration are recorded in
[`platform-direction.md`](platform-direction.md). In particular, legacy Desktop
profiles are not templates or inputs for the new permission model, and the
current repository's Desktop must evolve in place rather than being replaced by
an old copy.

This approval does not mark future modules complete and does not reopen this
archived file as a tracker. Any sequencing change to the frozen V1 checklist is
recorded as an approved amendment in Issue #296.

## Historical architecture material

The detailed modularization waves, old PR milestones and earlier product status remain available in Git history and the relevant merged PRs/issues. They should be consulted for provenance only, not for current prioritization.

## Tracking rule

- **Issue #296:** authoritative roadmap/checklist.
- **`platform-direction.md`:** authoritative intended future product model.
- **PRs and Issue #296 comments:** completion and validation evidence.
- **Notion SPINA Project Memory:** checkpoint/memory log only.
- **This file:** archived pointer only.

Do not expand this file into a second live tracker again.
