# Office CIF corrections

Continue approved office-only plan Task 3 from accepted head `3f128992`.
Implement and verify the complete backend/UI batch before publishing.

## Scope

Staff may correct the four recorded CIF information fields before confirmation,
using the existing audited correction API. This does not complete full T01,
privacy, applicant acknowledgment, Management approval, or release.

- Keep the existing reference lookup and read-only review's two initial GETs.
- Add a separate Correct information action to permitted office workspaces.
- Opening it requests the existing review summary with
  `include_correction_availability=true`.
- That optional response adds `can_correct_information`, computed in the same
  database query from the existing correction gates: current eligible draft,
  inactive Client, and no confirmation for that Client/CIF version.
- Default review payload is unchanged. No schema or new permission is needed.
- A false/missing/invalid availability value must never enable Save.
- Keep the exact original four-field snapshot separate from edited controls.
  PATCH includes that snapshot, exact CIF ID, corrected fields and a reason.
- The existing transactional repository remains authoritative for concurrent
  changes, eligibility, confirmation locks and audit insertion.
- One explicit Save sends one PATCH. No automatic mutation retry.
- Validation errors retain edits. Conflict or uncertain outcome blocks another
  save until Staff explicitly reloads current information. Never replay edits
  onto a silently replaced expected snapshot.
- Cancel and success refresh the authoritative read-only summary. Input changes,
  Clear, remount, logout and authorization loss clear all editor data and make
  pending responses inert. A disposed request may still have committed on the
  server, so cancellation must not be reported as an undone mutation.
- Preserve the read-only panel's rendered behavior and all published regression
  tests. Its additive return value lets selection mount the editor only after a
  valid review response. SW cache includes the correction module.

## Verification

Use focused API and real disposable PostgreSQL tests for availability gates and
unchanged correction authority. Run the complete portal suite plus event-driven
component/selection tests for exact snapshots, permissions, validation, duplicate
submission, stale/uncertain outcomes and disposal. Exercise actual browser forms
with synthetic API fixtures, build the portal and review the combined changes.
Publish once, verify matching CI and save GitHub/Notion/local continuation state.
PR #420 stays Draft/open/unmerged; no production operations.
