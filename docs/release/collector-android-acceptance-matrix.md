# Collector Android Release-Candidate Acceptance Matrix

This document is the executable evidence map for **SPINA V1 Master #296 Section C.1**. It does not enable a live 7x7 loan type, does not create production financial records, and does not replace the final signed Android release requirement in C.6.

The dedicated workflow `.github/workflows/collector-android-release-candidate-acceptance.yml` must run on one exact release-candidate commit. Every matrix row below must be green on that same commit and a debug Android APK must package successfully from that tree.

| Required C.1 behavior | Android/client proof | Server/control proof | Acceptance condition |
|---|---|---|---|
| Login + device authorization | `app_widget_test.dart`, `auth_repository_test.dart` | `test_auth_api.py` | Collector reaches Collector Dashboard only after authenticated session/device contract; rejected device/auth states stay blocked. |
| Route + area ordering | `app_widget_test.dart`, `collector_route_grouping_test.dart`, `collector_route_collection_gate_test.dart` | `test_collector_route_api.py` | Saved area order is preserved; grouped Regular/7x7 rows stay distinct; online/offline state and server collection gates are visible. |
| Regular payment | `collection_entry_page_test.dart` | `test_collection_posting.py` | One confirmed payment produces one official server transaction, receipt, balance, and next route revision. |
| Exact covered dates | `collection_entry_page_test.dart` | `test_collection_posting.py` | Non-contiguous selected dates remain exact; no inclusive-range substitution or duplicate date coverage. |
| Unable to pay | `collection_entry_page_test.dart` | `test_collection_posting.py` | Reason/date can be recorded without cash; existing covered dates and duplicate PASS rules remain protected. |
| Collector correction | `collection_correction_page_test.dart`, `collector_route_collection_gate_test.dart` | `test_collection_correction_api.py` | Only permitted own/unremitted collection can be corrected; remitted/locked history remains protected. |
| Cross-area payment | `other_area_collection_page_test.dart` | `test_other_area_api.py`, `test_cross_collector_posting.py` | Collector explicitly sees assigned-collector/recorder warning, can enter a permitted Regular payment, and cannot bypass other source-state guards. |
| Remittance submission | `collector_remittance_page_test.dart` | `test_remittance_api.py`, `test_cross_remittance_api.py` | Server preview drives total; submission locks included entries and notifies the selected recipient while cash remains with the collector. |
| Remittance acceptance + custody | `remittance_notifications_page_test.dart` | `test_notification_api.py` | Recipient must explicitly confirm physical receipt; only acceptance transfers custody state. |
| Recorder/custody attribution | `app_widget_test.dart`, `other_area_collection_page_test.dart`, `collector_remittance_page_test.dart`, `remittance_notifications_page_test.dart` | `test_cross_collector_posting.py`, `test_cross_remittance_api.py`, `test_activity_notification_api.py` | Recorder identity remains visible and cash-custody transitions are explicit rather than inferred from posting. |
| Official receipts/balances | `collection_entry_page_test.dart` | `test_collection_posting.py` | Android displays server-returned receipt/balance; retry reuses the same idempotency coordinates. |
| Notifications | `remittance_notifications_page_test.dart` | `test_notification_api.py`, `test_activity_notification_api.py` | Action-required and custody/payment update notifications preserve server state and authorization. |

## Release-candidate packaging boundary

C.1 uses a **debug APK** only as a packaging/smoke artifact proving that the exact accepted Flutter tree can be packaged for Android. This is not the C.6 production artifact. The final C.6 checkbox requires a separately produced **signed Android release build** plus the documented update/release procedure.

## Fail-closed rules during C.1

- Cached offline routes are read-only; C.3 owns the final dedicated offline acceptance assertion.
- Production/live `mobile_seven_by_seven_enabled` remains unchanged. Disposable 7x7 acceptance from B.5 remains the evidence for enabled 7x7 mechanics; C.4 separately proves Regular/7x7 records never mix.
- A failed matrix row, analyzer failure, backend control failure, Android packaging failure, or dirty tree means C.1 is not complete.
- No acceptance test may write to the live/production database.
