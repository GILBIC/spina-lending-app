# Quality safety fixes Wave 73

Wave 73 ports the four still-missing fixes from obsolete PR #3 onto the current modularized `main` branch.

## Scope

1. Ensure a failed background task cannot execute `work_fn` a second time.
2. Make account saves return success/failure and prevent false password-change success.
3. Maintain `users.json.bak`, distinguish missing from corrupt account files, recover safely, and fail closed when both files are unreadable.
4. Create performance indexes once per application process and remove the extra module-startup `LoanDB` connection.

## Approach

The workflow fetches the previously reviewed PR #3 branch, transplants only the four approved function blocks into current source locations, compiles the result, runs permanent regression checks, and commits the validated source changes to the Wave 73 branch.

The old PR is not merged because it predates hundreds of later commits and is no longer mergeable.

## Automated port result

The source transplant compiled successfully. The Wave 73 safety regression and the updated Wave 42 exact-source regression both passed before the generated source commit was pushed. This documentation update triggers validation against the resulting human-authored PR head.
