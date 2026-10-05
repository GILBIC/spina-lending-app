# Office workflow implementation decisions

These decisions were made while executing the approved PR497 plan. They preserve the requested outcome and record the tradeoffs. The dated local execution ledger retains the original wording, failed attempts and detailed receipts.

| Decision, in execution order | Reason | Cost or limitation |
| --- | --- | --- |
| Preserve the owner's refusal of Create State and cleanup; use GitHub, Notion and the local continuation pointer | The old plan's Create State instruction was superseded | No duplicate Create State record; protected cleanup remains untouched |
| Merge current main into the planning branch before implementation | Preserve deployed payout behavior and migration 0139 | One normal merge commit in the draft branch |
| Use one implementation agent followed by independent review, starting with the independent backend Task 6 | Separate the new read contract from shared frontend case changes | Task order changes; requirements remain the same |
| Serialize heavy checks and stop the positively identified incomplete backend run when memory was exhausted | Keep validation reliable on the 7.6 GiB host without touching owner processes | The stopped 11% run is not a pass; final full backend coverage remains required |
| Move the minimal generated-draft context callback from Task 3 into Task 1 | Removing editable-field identity otherwise broke the existing generated-reference handoff | A small application-module seam enters the foundation review; drafts remain explicitly unsaved with null saved IDs |
| Complete registered intake/CIF handoffs in Task 2, then application/release adoption in Task 3 | Clearing forms before their dirty/lock handles exist would discard protected work | All-stage completion is demonstrated later, without dropping the requirement |
| Implement the finder before the responsive pass | Style and capture the actual list/picker instead of a temporary empty panel | Task 7 temporarily uses baseline styling; there is no release between tasks |
| Retain compatible intake/CIF owners when selecting an application for the same verified intake/client | Replacing all owners would lose valid facts and native Files | More explicit transition tests: different application/version guards application/release; exact same identity/version guards its destination reader; global locks remain |
| Use existing exact-final-head CI for full backend and real Office PostgreSQL proof after local PostgreSQL ran out of memory | The local failed run cannot supply passing evidence | Completion waits for actual CI logs/counts/zero skips; no coverage or gate is weakened |
| Carry the minor return-focus finding from Task 7 into the immediately following Task 5 accessibility work | The implementation sequence already assigned keyboard/layout acceptance there | Two finder files join Task 5's scope; the requirement must be repaired and independently reviewed before acceptance. This was completed at f5a071be |
| Update two old authorized-entry test assertions during Task 5 | S1 now requires one automatic recent-list read | One additional test file enters review; exact one-read, no implicit protected-case selection and original retention assertions remain |
| Run required CI and the final read-only whole-branch review concurrently after all scoped local reviews pass | These independent gates can examine the same immutable candidate without changing draft status | A review fix may supersede the first CI run; every final source head still needs its own passing required checks |

Review findings about listener warnings and dense helper/test formatting remain explicitly available to the final whole-branch reviewer. Known prior focus, version, privacy-race and malformed-cursor findings were repaired and independently re-reviewed. The final acceptance record distinguishes their original tests from subsequent source changes.

The current implementation and CI disposition belong to [PR497](https://github.com/GILBIC/spina-lending-app/pull/497). Required checks are tied to the exact current implementation commit. Final CI results and the dated completion checkpoint are recorded on that PR and in the continuation handoff after this source evidence is committed, so bookkeeping does not create a new unverified implementation head.
