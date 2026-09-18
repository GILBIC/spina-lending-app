# Saved office application review

Continue approved Task 3 from accepted correction head `d63932c0` as one
backend, portal and verification batch. Read saved request/repayment facts using
the two office references, without making an approval or confirmation claim.

- Add a protected latest-version review GET beneath the selected Client:
  `/api/v1/management/clients/{client_id}/loan-applications/by-reference/{application_reference:path}/review-summary`.
- Trim outer application-reference whitespace; retain existing case-sensitive
  exact reference semantics. Require the application to belong to the Client.
- Reuse persisted office authorization and active-device API authentication.
  Unknown/cross-Client references return generic 404; handled outcomes use
  no-store. Selection makes no writes or row locks.
- Select the latest immutable version, preserving its exact attached CIF identity
  even after CIF supersession. Existing historical read semantics remain; no
  current-CIF eligibility gate or current-CIF personal-data overlay is added.
- Return the existing application payload plus the attached CIF version number
  and nullable current catalog product label. A separate projection type keeps
  the persisted version record unchanged. Current catalog labels are identified
  as display metadata, not immutable historical product names.
- Give permitted Employee/Management workspaces an Application review section.
  Enter office intake reference and exact loan application reference. Resolve the
  stable Client with the existing onboarding GET, then read the application.
- Display all saved request, repayment and obligation fields, preserving null,
  false and zero. Render decimal money strings without binary-number conversion
  or guessed calculations. Missing fields come from the server and cover only
  these two sections, not full T01, privacy or approval readiness.
- The component never fetches the current CIF or offers approval/confirmation,
  editing, release, credentials or other writes. Do not show raw identity UUIDs
  as form inputs or user-facing product labels.
- Clear and invalidate results on either reference change, Clear, remount,
  logout and disposal. Preserve independent CIF/Area workflows and permissions.

Verify API and real PostgreSQL authorization, exact case/reference/Client binding,
latest selection, historical source, null catalog metadata and absence of writes.
Run portal component/workspace regressions, browser form checks, build and review.
Publish together, check matching CI, save GitHub/Notion/local handoff. Keep PR #420
Draft/open/unmerged. Application encoding/confirmation, protected acknowledgment,
full T01/privacy and later approval/release remain separate unfinished work.

## Local verification

- 51 focused application API tests passed; 27 cover the new reference reader.
- 306 real PostgreSQL tests passed, including 18 new reference-review cases;
  the disposable database was dropped and zero leftovers verified.
- 291 portal tests and syntax checks for 57 modules passed.
- Edge checks passed for Employee desktop, Management mobile width, and a
  permission-denied Employee, including stale response cleanup and exact money.
- Portal build/source byte checks and independent review passed. Scratch
  PostgreSQL and the local browser test server were stopped.

These are local results. Matching published-head CI still determines full
batch acceptance; the current priority remains 43% until Task 3 is complete.
