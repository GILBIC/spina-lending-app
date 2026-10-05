# Office usability corrections — 6 October 2026

Approved scope: make the existing Office flow easier to follow after the live UI review. The user requested “Fix.”

- Eligible intakes have a direct Continue to CIF action using the verified selected case. Successful handoff only reads the CIF; it does not create, confirm or activate it.
- Selected intake/CIF reference searches collapse. The compact case header keeps the applicant and intake visible, with source statuses and versions under Details.
- Applications appear in the relevant stage, with no empty paging controls. Employee moves the same finder between stages and returns to intake after an accepted client change. New application is the primary form action.
- CIF uses four expandable tasks: details, applicant signature, privacy acknowledgment and identity verification. Exact facts remain beside signing. Expanding tasks retains the mounted File, witness and verification controls. Only verified responses mark signature/privacy steps complete.
- Clearer labels, consistent action sizing, responsive signing layout and cache v31.

## Verification

Regression checks were observed failing before corrections. The complete serial portal suite passed 1,837 tests with zero failures or skips. Module validation passed 284 modules; the portal build passed. The standard npm test command is also recorded in the local verification evidence.

Independent read-only review identified and then confirmed corrections for hidden CIF reload errors, an Employee application picker in an inactive section, missing visible signing facts, and the Employee client-change return route. No material finding remained in the final scoped review.

CUA browser checks used the actual built modules with synthetic Management and Employee sessions. They verified direct CIF handoff, task disclosure, application-stage picker visibility, return to intake, a rejected blank signature, and retention of unfinished witness/privacy choices across stage changes. Navigation made no writes. At measured 390px CSS width the signing box was approximately 293 × 147px with no horizontal overflow; a measured 1706px desktop view also had no overflow. Final Employee checklist screenshot is retained in the local checkpoint. Browser screenshot capture was intermittent; failed captures are not counted as proof. Temporary viewport overrides were reset.

No real customer signature, financial operation, physical phone or production staff acceptance was performed. No backend/schema change or migration is required. CI, protected merge, deployment and independent live verification are release gates, recorded separately after publication.
