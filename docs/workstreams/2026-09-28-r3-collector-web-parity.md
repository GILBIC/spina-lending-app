# R3 — Collector Web operating parity

## Approved scope

Source: [SPINA approved-idea/code-gap review, R3](https://app.notion.com/p/3e35ade7bef48197be58f91c865a9d6f), 22 September 2026, and the user's repeated approval to complete all priorities without over-engineering. This slice exposes existing protected server workflows for Collector Web/iPhone use; it adds no calculation engine, provider, migration, policy configuration or financial posting route.

R3 starts from R2 commit `20c3f0bcbf287fa78a917d7cf548bde10261806c` on `gap/r3-collector-web-parity`. R4 code-copy handoff is separate commit `7963961d`; R3 implementation is `2897c235`. R6 exact-money commit `834b5464` was merged without rewriting either history. The shared validator retains R6 exact decimal normalization and unsafe-number rejection alongside R3 covered-date/allocation inputs. New money displays reuse the existing authoritative decimal display helper.

## Behavior

- Ordinary route payment now permits an explicit existing allocation intent and Past Due follow-up, including promise date/amount. Covered-date payment uses selected dates from the server's saved schedule.
- Combined Pay is available for one unprocessed Regular and one unprocessed 7x7 entry belonging to the same client. It sends one cash total to the server preview, validates that the preview matches the exact cash and both loan/route/revision identities, displays decimal money without Number conversion, and sends its review hash with the same UUID. Edits invalidate the preview. Three device sequence slots are reserved, matching the existing backend's possible scheduled/extra components.
- Corrections require `collection.correct.own_unremitted`, the server's `can_edit_today`, an unlocked transaction, a factual reason, and the current route revision. Existing covered dates remain selectable even if this receipt currently pays them in full.
- Other-area search preserves assigned ownership and records through the existing collection protocol. Server `can_collect_mobile` and `can_enter_payment` remain authoritative, including its existing 7x7 feature flag. Separate cross-remittance targets, preview, recipient capacity and history keep cross-route custody distinct from regular route remittance.
- Assigned renewal requests expose recommendation, cash received, cash given and handover-photo upload with the existing permission/stage rules. Cash confirmation requires an explicit physical-handover checkbox. Approved principal, signer verification, activation and Management review remain server/Management actions.
- Every financial action shares the existing workspace guard: one in-flight operation, no offline queue, and authoritative refresh after success or before any retry of an uncertain result. Abort/disposal prevents late responses or detached forms from enabling writes. New financial mutation results must match the submitted identity; unreadable/malformed success and HTTP 5xx responses also lock until authoritative refresh, while read-only preview errors remain editable.

## Verification

Integrated R2/R3/R4/R6 Portal syntax (116 modules), all 736 tests and the distributable build passed. Focused mounted-form tests cover reviewed Combined posting and edits, saved-date submission, correction scope/revision, late disposal, cross-area identity and recipient capacity, recommendation explanation, handover stages, uncertain lock and private photo type/size checks. Root spec review identified a missing Combined-preview response binding; fixed with 17 malformed-response variants plus exact large-value display regression. The scoped mutation-recovery fix covers null success, HTTP 500 and editable read-only preview errors. Root reviewed both fixes and the R4 handoff without further findings. The shell precaches all four new modules under cache v13. Additional standards review and repository CI remain separate from these local checks; no production acceptance is claimed.

## Limits

R4 QR-only handoff and trusted provider settlement are separate. No live collection, cash action, company value, provider setup, deployment or migration was performed. Tests use synthetic records and API doubles for Web orchestration; existing protected backend paths remain responsible for authorization, calculations, concurrency, schedule/cash correctness and audit evidence.
