# Whole-code review repairs — 9 October 2026

All seven findings are repaired. Integration verification and independent reviews are complete; all implementation changes are committed locally. Based on `bfd33ff7cdef94c1c7ff7ca0d13af38b8ac4c1db`, on local branch `codex/review-fixes-20261006`.

Scope is all seven findings from the whole-code review retained at `C:/Users/pc/OneDrive/Documents/ChatGPT/Gilbic/artifacts/code-review-20261009-bfd33ff7/SPINA-code-review.md`. The preceding eight repairs remain compatibility requirements. This work adds no migration or provider operation.

| Finding | Required repair | Verification status |
| --- | --- | --- |
| F1: Generic correction erases retained Collector cash | Reject correction of movements bound to Collector settlements or exceptions, including partially and fully returned custody; preserve unbound correction and exact replay. | Implemented and independently approved in `794b47e7`; actual PostgreSQL regression coverage passed. |
| F2: Corrected movements still satisfy reconciliation matches | Derive valid matches from current in-scope uncorrected events; retain historical matches, block invalid closure, and permit protected replacement/supersession. | Implemented and independently approved; zero-net pair, closed history, open replacement and replay controls passed. |
| F3: Legacy native pages retain private state after denial | Clear private data/actions on 401/403/426 and fence late responses, dialogs and changed authority across all six affected pages; evict current and superseded private photo cache entries. | Independently approved after the cache fix, committed in `d1d2af1`; 52 final private-state cases passed, including six decoded-cache regressions. Complete native suite passed. |
| F4: Back/reopen discards uncertain intake protection | Keep create uncertainty at the authorized-session lifetime across all intake entry routes, retaining read-only record review. | Mounted app double-Back, Finder, compatible-refresh, late original success and authority-teardown controls passed; independently approved in `d1d2af1`. |
| F5: Portal accepts incomplete final payment facts | Require canonical acknowledgement facts and exact submitted identity before marking saved or clearing drafts, including shared and combined consumers. | Implemented and independently approved in `dacc3a0c`; 126 focused tests and the complete 1,967-case Portal suite passed. |
| S1: Area transfer uses host date | Use the existing Manila collections business-date authority in both preview and commit. | Eight API/repository boundary cases passed, including before/after Manila midnight and independent host dates. |
| S2: Management invents paid amount from balance subtraction | Share Renewal's nonvoid applied-payment total and active registered contractual total; render an unavailable percentage when the denominator is unknown. | Backend SQL/serializer and native model/widget controls passed, retaining actual 100.00 paid and known 1.7% or unavailable percentage. |

## Backend evidence

The complete 4,870-case collection was covered across an interrupted invocation and an explicit continuation, with **3,397 unique passes, 1,473 skips, and no unresolved failures**. This is not a single uninterrupted passing invocation. The first run hit its controller's 1,500-second deadline after 3,181 reports. The continuation covered the interrupted module, all remaining cases, and the complete failed module: 1,364 passed and 383 skipped. There were 58 repeated cases; counts above remove that overlap.

The first invocation's sole failure was caused by placing pytest temporary storage inside the application repository. The private-evidence policy correctly rejects that location. Identical sanitized single-case runs failed inside the repository and passed in an owned directory outside it; the test and product source were unchanged. The continuation used external temporary storage and passed the affected module without changing assertions.

Opt-in database cases are skipped in the general suite. Targeted affected financial paths were run separately against a new synthetic PostgreSQL 18 database through schema 0141. All 32 new backend regressions passed; focused owner/compatibility runs also passed. Counts overlap and must not be added as unique tests.

An early focused Renewal run set only the test database variable; five existing tests therefore attempted the default loopback port 5432 and failed its no-password handshake. No connection succeeded and no database read/write occurred there. Both application and test variables were then explicitly bound to the owned database, with a connection/dotenv guard; the corrected 36-case run passed. The initial harness failures remain in the evidence.

All 12 changed/new Python files compile and are formatted. Ruff comparison against the base found no added code/message diagnostics; 56 inherited diagnostics became 52. The existing test-helper rewrite warning and installed Starlette/httpx deprecation remain explicit baselines.

## Native and Portal evidence

The complete Flutter 3.44.7 suite passed **1,468 tests with one platform skip**. The final analyzer reported **No issues found**. The final focused native group passed 104 cases; the subsequent private-image cache fix passed all 52 private-authority cases, including six real decoded-image ownership tests. The full suite then exercised the final implementation. Tests cover actual mounted screens, compatible refresh, old and current authority completions, stale dialogs, double Back, Finder intake entry, original create completion after unmount, and nullable Management progress.

The final Portal gate checked **286 modules** and passed **1,978 tests with zero failures or skips**. The original F5 focused group passed 126 cases. The final teardown correction and affected consumer group passed 179 cases. The base-source replay retained in the evidence produced 68 expected failures and 20 passes before the F5 repair; the final correction's red run separately reproduced ten teardown failures with 51 passing controls. Healthy accepted/duplicate, zero-PASS, exact large money, short combined cash, omitted zero components, and all supported extra-allocation shapes have positive controls. Tests use mounted workspace handlers with synthetic API responses.

The full Portal log contains five Node `MaxListenersExceededWarning` messages (one `visibilitychange`, four `focusin`). Their origin was not established; they are an explicit non-blocking caveat, not a claim of clean warning output or a proven inherited baseline. The independent review caught and corrected the implementation report's original omission.

Final source verification compares every retained test fingerprint against the current checkout: **1,147 backend/tooling files, 511 native files and 293 Portal/checker files**. All match. Native tests began against frozen staged changes before their commit; the committed bytes match exactly. `git diff --check` passes. No suite is represented as testing later changed source.

## Recovery boundaries and response contracts

Office create has no server-side command identity or exact outcome lookup. A matching applicant or unrelated successful reference lookup cannot prove that an uncertain create succeeded. The repair retains the write block for the authorized-session lifetime unless the original response establishes a known result, while allowing record review. The owner sits above ordinary navigation in the existing authorization-keyed app. It does not add a manual success override, automatic replay, or process-restart persistence.

Portal uncertainty retains the exact submitted request in memory and keeps the existing reconciliation lock through ordinary refresh and direct submit attempts. Disposal or signal abort clears that private retained request, and late completion or retention cannot repopulate a disposed owner. Existing authoritative/Office reconciliation and session boundaries remain the recovery path; no replay UI was added. Single responses require the exact submitted command UUID, a nonblank opaque server transaction ID, canonical nonnegative money, a valid accepted timestamp and a PAY/ADV receipt. Legitimate PASS may omit the receipt.

Combined responses have a different existing producer contract: no accepted timestamp, only nonzero posted components, and potentially multiple components for one loan. Validation compares the exact component set and canonical facts to the retained authoritative reviewed preview, including command/client/review hash and totals. It does not calculate loan allocations in the browser or require nonexistent single-entry fields.

## Independent review and shutdown

The independent whole-change Spec review found no actionable defect. The Standards review identified one P2: private pending Portal commands survived disposal. The final correction clears and fences that owner; its fresh scoped re-review confirms the finding is addressed with no new material breakage. All three original task reviews and the final source provenance check are complete. There are no unresolved actionable findings from these repair reviews. The owned PostgreSQL cluster is stopped after live directory/database/loopback/port ownership verification.

All verification uses synthetic local fixtures. It does not certify production provider behavior, physical phones, native-engine SQLCipher encryption, every possible financial history, or every line in the repository. Historical migrations and all opt-in/platform paths were not re-executed by the general suite. Previously deferred extreme-value precision and malformed-document renderability hardening remain outside these seven repairs. No dependency install, schema change, production operation, push, merge or deployment is included.

## Local source commits

| Commit | Change |
| --- | --- |
| `794b47e75fd7ecfd13c0a7dad5a53c5458578dd9` | fix: preserve custody and authoritative loan projections |
| `d1d2af1cc3cc47a375e1b690e740a6872a53fbb9` | fix: revoke native private state and retain intake uncertainty |
| `dacc3a0c98a31a784ce4e193b908237ce26463e7` | fix: validate final collector payment acknowledgements |
| `b683f7c4f42719323e0e5cc388d1187e23fe1db3` | fix: clear pending collector commands on disposal |

Final product HEAD: `b683f7c4f42719323e0e5cc388d1187e23fe1db3`. The following documentation-only commit records this plan and report. The archive's FINAL-STATUS.md and manifest pin the final delivery HEAD. Branch and linked worktree are preserved locally.

## Separate review verdicts

- Standards: initial P2 corrected; [original report](C:/Users/pc/OneDrive/Documents/ChatGPT/Gilbic/artifacts/code-review-20261009-fixes/evidence/final-standards-review.md) and [scoped closure](C:/Users/pc/OneDrive/Documents/ChatGPT/Gilbic/artifacts/code-review-20261009-fixes/evidence/final-fix-review.md).
- Spec: no actionable defect found; [independent report](C:/Users/pc/OneDrive/Documents/ChatGPT/Gilbic/artifacts/code-review-20261009-fixes/evidence/final-spec-review.md) and [coverage](C:/Users/pc/OneDrive/Documents/ChatGPT/Gilbic/artifacts/code-review-20261009-fixes/evidence/final-spec-coverage.md).

## Rulings I made

Every ledger ruling is reproduced below in order. The first three receive explicit cost notes; later rulings already contain their trade-offs.

Ruling: Reuse the already isolated repair worktree — verified linked checkout with a non-main branch and clean source — creates no parallel checkout or dependency reinstall.

Cost if wrong: misidentified isolation could mix unrelated work; linked-worktree identity and clean starting source were verified.

Ruling: Review staged task diffs before local commits, with full integration suites once after all batches — focused red-green evidence gates each slice and avoids repeated nine-minute Flutter runs; any later product edit invalidates its affected final check.

Cost if wrong: later source edits could invalidate an earlier suite; final per-file hash checks gate evidence reuse and affected edits trigger reruns.

Ruling: No Supabase/provider or schema operation is required; fresh local synthetic PostgreSQL through existing schema0141 supplies SQL evidence. Deployment and push are outside scope.

Cost: local synthetic SQL does not establish production/provider acceptance; deployment remains a separate activity.

Ruling: Preserve unknown paid percentage when the authoritative contractual total is missing, and update its native Management consumer in Task2 — existing Renewal semantics and Portal already support unknown; cost if wrong is an additional unavailable indicator where prior UI guessed zero. Native currently requires a number, so this is a required producer/consumer integration change.

Ruling: Do not add a manual confirmation override for an unknown non-idempotent Office create — matching applicant fields or a different reference cannot prove command identity. Keep the workspace latch until the original response establishes a known result, or actual authority teardown; reads remain reachable and compatible refresh/navigation cannot reset it. Cost: a truly lost acknowledgement without command lookup blocks new intake for that authority lifetime; this limitation is safer than a fabricated resolution and must be disclosed.

Ruling: Extend Task2 with a narrow OfficeIntakeAuthorityHost inside the existing session-keyed app builder — source inspection proved OfficeWorkspace itself is a pushed/remountable route, so a route-owned create operation would repeat F4 after double Back. The host follows authorizationScopeKey, remains separate from cache/Employee scopes, and clears on authority teardown. Cost: one additional app-level lifetime owner and app.dart integration; actual double-Back, compatible-refresh and authority-teardown regressions plus full native verification cover it.

Ruling: Keep the existing Portal uncertainty lock and preserve the exact pending request through ordinary refresh; do not add a new replay UI — F5 fixes false confirmation, while this workspace has no existing authorized replay control. Cost: recovery continues through existing authoritative/Office reconciliation and session boundaries, not a new in-place retry flow.

Ruling: Treat server transaction IDs as nonblank opaque strings, while requiring exact submitted command UUID equality — the repaired Dart parser and shared contract require text and do not normatively restrict server IDs to UUID syntax. Cost: syntactically non-UUID server IDs remain accepted; missing/blank/wrong-type IDs remain rejected.

Ruling: Correct Task3's combined response requirement to the actual protected API — combined_collection_api.py:1512–1648 emits nonzero posted components, can repeat a loan for scheduled/extra components, omits zero allocations and supplies no accepted_at. Validate exact expected component membership/amounts against the retained reviewed server allocation, plus command/review identity and canonical receipt/balance facts. Cost: the validator must understand the stable component labels, with healthy short/excess/duplicate controls; literal one-result-per-submitted-loan/time checks would reject valid saves. Plan and brief updated before implementation.

## Retained evidence

[Complete archive](C:/Users/pc/OneDrive/Documents/ChatGPT/Gilbic/artifacts/code-review-20261009-fixes/FINAL-STATUS.md) contains the reports, full logs, exact commands, valid red/green regressions, initial harness failures, staged review packages, source hashes, decisions, and owned PostgreSQL shutdown proof. Nested database/cache directories and the reproducible base replay copy are excluded; the unmerged task workspace is retained.

- backend-continuation: [verification](C:/Users/pc/OneDrive/Documents/ChatGPT/Gilbic/artifacts/code-review-20261009-fixes/evidence/backend-continuation-1791516338320895600.json).
- native-full: [verification](C:/Users/pc/OneDrive/Documents/ChatGPT/Gilbic/artifacts/code-review-20261009-fixes/evidence/native-full-1791518999242037500.json).
- portal-full: [verification](C:/Users/pc/OneDrive/Documents/ChatGPT/Gilbic/artifacts/code-review-20261009-fixes/evidence/portal-full-1791520636936257000.json).
- Complete backend coverage: [4,870-case accounting](C:/Users/pc/OneDrive/Documents/ChatGPT/Gilbic/artifacts/code-review-20261009-fixes/evidence/backend-integrated-verification.json).
- Final source continuity: [hash verification](C:/Users/pc/OneDrive/Documents/ChatGPT/Gilbic/artifacts/code-review-20261009-fixes/evidence/final-source-verification.json).
- Synthetic PostgreSQL: [stopped with ownership checked](C:/Users/pc/OneDrive/Documents/ChatGPT/Gilbic/artifacts/code-review-20261009-fixes/evidence/pg-stopped.json).
