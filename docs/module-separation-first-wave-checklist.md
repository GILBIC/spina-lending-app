# Module-separation first-wave checklist

Use this checklist after generating `module-separation-plan.json`.

## Candidate requirements

A first-wave extraction candidate should:

- appear in `recommended_first_wave_review`
- be low risk
- be 120 lines or fewer
- have no database or PDF dependency signal
- not be marked business-critical
- have few shared global reads
- form one cohesive helper group

## Before extraction

- record the exact functions and line ranges
- identify every caller
- add focused tests or before/after output checks
- choose one destination module
- preserve function names and call signatures
- avoid unrelated formatting or cleanup

## After extraction

- compile the application and new module
- run the focused tests
- run the existing quality and redundancy audits
- manually test the affected UI path
- compare observable behavior before and after

Do not combine utilities, reports, UI tabs, and business logic in the same extraction PR.
