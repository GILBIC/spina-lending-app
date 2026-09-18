# Protected CIF Review Confirmation API

This is the next bounded Task 3 slice in the approved office-only CIF/first-loan
plan. Expose the accepted confirmation repository through the existing CIF API;
do not add repository, schema, evidence-storage or financial behavior.

## Accepted starting point

Head `1134de0bca722ace5267093045219b5b5d5321a8` passed CI2343,
Annex A63 and 7x7 PostgreSQL165. Backend: 1929 passed, 491 skipped, two warnings.
Financial: all 258 actual onboarding/CIF/application cases passed in 11.57s,
with disposable database cleanup and private-schema barrier PASS. PR420 remains
Draft/open/unmerged. The protected CIF-confirmation HTTP route is missing.

## HTTP contract

Add POST `/api/v1/management/clients/{client_id}/cif/review-confirmations`,
returning 201, including when the repository returns an identical retry.

The required JSON body contains only:

- `cif_version_id`: a UUID identifying the exact reviewed CIF version.
- `expected_information`: reuse existing `CifReviewInformation` unchanged. All
  four fields are required: full_name, phone_number, email and present_address.
  Preserve exact text, punctuation, case and whitespace; only email may be null.
  Reject extra keys and non-text values. Do not normalize the reviewed snapshot
  or impose fresh completeness rules in HTTP, which would break historical retry.
- `applicant_confirmation_evidence_reference`: nonblank text, stripped before
  delegation. Reject missing, null, non-string or whitespace-only values. Use
  the existing application-confirmation convention; invent no new length limit.

Forbid extra body fields, including caller-supplied actor, witness, time, cycle,
Client identity, activation or approval status. Malformed UUID/body values return
422 before the repository call.

Reuse `_office_cif_actor` and existing dependencies. Require authentication,
registered active device, persisted account context, existing
`client_onboarding.requirement.review` permission and explicit Employee or
Management role. Preserve current 401/400/403 authentication/device semantics;
Collector/Client are denied even with the permission. No new grants.

Call `confirm_review` exactly once per authorized valid request, with persisted
actor.user_id, path Client UUID, body CIF UUID, the unchanged expected snapshot
and normalized evidence reference. Do not call current-summary, activation,
correction or other source selectors first. The repository owns source binding,
fresh eligibility, completeness, transaction locks, cycles and immutable retries.

Return an explicit allowlist from the saved record:

- `review_confirmation_id`, `client_id`, `cif_version_id` as UUID strings;
- `review_cycle_number`, `witnessed_by_user_id` and `confirmed_at`;
- `review_scope`: `cif_information_only`.

Convert confirmed_at to UTC before ISO serialization with a trailing Z; the
existing generic CIF timestamp helper does not convert non-UTC offsets. Set
`Cache-Control: no-store`. Do not return the acknowledgment reference, snapshot,
private evidence or activation/approval/release fields. Do not generate identity,
cycle, witness or time in the route.

Map repository ValueError to 400, ClientCifAccessDenied to 403 and
ClientCifConflict to 409, preserving the existing error detail convention.
Expose only POST at this collection and no public/Client route aliases.

## Tests-first publication and verification

Add only this plan and
`gilbic_backend/tests/test_client_cif_review_confirmation_api.py` initially.
Use existing FastAPI dependency overrides and synthetic identifiers. Test office
roles, exact delegation and raw snapshot, response allowlist/UTC/no-store,
identical retries, auth/device/account/permission denials, strict body/UUID and
nested snapshot validation, repository error mappings and route exposure.

Check missing POST through app.openapi() inside test setup and fail explicitly
with `CIF review confirmation API is not implemented`. Do not add import-time
failures, skips, production stubs or an API implementation in the tests-only head.
The fake repository implements only confirm_review so extra HTTP source calls
cannot silently pass. These are HTTP-boundary tests, not new database proof.

Run every new case to its intended missing-route failure; independently review
the contract/tests and run the 79 existing focused CIF repository/API cases plus
35 accepted application-confirmation API cases. Check compilation/whitespace and
unchanged production files. Publish only the two new files as a non-force child
of the verified head, rechecking the live branch immediately before publication.

Inspect new-head CI once, update GitHub/Notion/Create State/local handoff and wait
for the user's next Red/all-green signal. No polling or manual rerun. After
actual expected CI Red, minimally extend existing client_cif_api.py, keeping
published tests and repository unchanged. Later acceptance requires all five CI
lanes plus 258 actual Financial cases, cleanup and private-schema barrier.

## Local tests-only verification

All 45 new cases collect and fail solely with
`CIF review confirmation API is not implemented`: 45 failed, two existing
dependency deprecation warnings in 94.75s. No collection errors or skips.
All 114 retained cases pass in 126.08s with the same two warnings. Pytest cache
writing was disabled locally. Compilation, whitespace and independent review
passed. Only this plan and the new test file are added; existing production,
repository, SQL, runner, workflow and test files remain unchanged. No new local
database execution is claimed; parent CI supplies the 258-case database proof.

This confirms only the reviewed four-field information. It does not establish
full T01/privacy completeness or evidence authenticity. Protected acknowledgment
capture/retrieval, office UI, Management approval, documents/signing and release
remain separate unfinished dependencies. No priority reorder, main/frozen
Master296/other-owner change, mark-ready, merge, deployment or production action.
