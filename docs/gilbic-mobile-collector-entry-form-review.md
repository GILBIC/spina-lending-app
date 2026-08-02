# Collector Entry Form Review Checklist

## Automated evidence — passed

GitHub Actions run #30 passed on commit `c8760ab73aeede8a0d028dd10104ee7680d67698`.

- [x] Flutter 3.44.7 dependency resolution succeeds.
- [x] `flutter analyze --fatal-infos` succeeds.
- [x] Full `flutter test` suite succeeds.
- [x] Online ready route enables collection.
- [x] Offline route copy disables collection.
- [x] Direct 7x7 form access remains blocked.
- [x] Payment starts with the server daily amount.
- [x] ADV requires valid coverage dates.
- [x] PASS sends no amount or ADV dates.
- [x] Confirmation appears before submission.
- [x] Network uncertainty shows **Retry same entry**.
- [x] Retry reuses the same idempotency key and device sequence.
- [x] Duplicate success shows the server receipt and official balance.
- [x] No automatic retry worker or offline payment outbox is enabled.
- [x] The committed tree remains clean after validation.

## Manual emulator or phone acceptance — pending

Use a test collector account and approved disposable or test data. Do not use a live borrower until the flow is accepted.

- [ ] Sign in and open **Daily Route**.
- [ ] Confirm an online Regular loan shows **Record Collection**.
- [ ] Confirm an offline route copy remains read-only.
- [ ] Confirm an account without `collection.create` cannot record an entry.
- [ ] Confirm a missing or stale route revision requires refresh.
- [ ] Confirm a server-disabled loan shows its plain-language `collection_message`.
- [ ] Confirm a 7x7 loan cannot open or submit Payment, ADV, or PASS.
- [ ] Confirm Payment defaults to the expected server daily amount.
- [ ] Confirm ADV dates and amount are shown correctly before saving.
- [ ] Confirm PASS contains no payment amount or ADV dates.
- [ ] Confirm the confirmation dialog appears before the write.
- [ ] Confirm a successful entry shows the official receipt and balance.
- [ ] Confirm **Done and refresh route** reloads the route.
- [ ] Simulate network uncertainty and confirm **Retry same entry** is clear.
- [ ] Confirm editing an uncertain entry creates a new draft only after the collector intentionally changes it.
- [ ] Confirm no collection is queued automatically while offline.

## Merge gate

Keep PR #225 as a draft until the manual acceptance list is completed. After acceptance, mark it ready for review and merge only with the exact-head CI still green.
