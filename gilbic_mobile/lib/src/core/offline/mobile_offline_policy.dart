import 'package:gilbic_mobile/src/core/auth/app_role.dart';

class MobileOfflinePolicy {
  const MobileOfflinePolicy({
    required this.role,
    required this.summary,
    required this.availableOffline,
    required this.blockedOffline,
    required this.hasPersistentOfflineData,
    required this.financialWritesOfflineAllowed,
    required this.financialWritesSilentlyQueued,
    required this.financialWritesAutomaticallyRetried,
    required this.explicitIdempotentRetryAvailable,
  });

  final AppRole role;
  final String summary;
  final List<String> availableOffline;
  final List<String> blockedOffline;
  final bool hasPersistentOfflineData;
  final bool financialWritesOfflineAllowed;
  final bool financialWritesSilentlyQueued;
  final bool financialWritesAutomaticallyRetried;
  final bool explicitIdempotentRetryAvailable;

  static MobileOfflinePolicy forRole(AppRole role) {
    return switch (role) {
      AppRole.management => _management,
      AppRole.employee => _employee,
      AppRole.collector => _collector,
      AppRole.client => _client,
    };
  }

  static const _management = MobileOfflinePolicy(
    role: AppRole.management,
    summary:
        'Management mobile workflows require a live SPINA server connection. '
        'No protected approval, accounting, tax, ECL, close, device, or custody action is an offline write.',
    availableOffline: <String>[
      'A still-valid secure session may remain open during a temporary network outage.',
      'Already-rendered screens may remain visible, but their values must be treated as stale until refreshed.',
      'The Offline & sync policy remains available from the app shell.',
    ],
    blockedOffline: <String>[
      'Client, loan, collection, remittance, staff, device, report, and alert refreshes.',
      'Approvals, reviews, protected accounting/tax/ECL/close actions, reversals, and custody decisions.',
      'Any operation that would create, change, approve, post, reverse, or revoke authoritative server state.',
    ],
    hasPersistentOfflineData: false,
    financialWritesOfflineAllowed: false,
    financialWritesSilentlyQueued: false,
    financialWritesAutomaticallyRetried: false,
    explicitIdempotentRetryAvailable: false,
  );

  static const _employee = MobileOfflinePolicy(
    role: AppRole.employee,
    summary:
        'Configured employees can record attendance and breaks in a protected, account-and-device-bound outbox. '
        'These events sync when the app reconnects or resumes. Payroll, reviews, tasks, requests and office financial actions require the live server.',
    availableOffline: <String>[
      'A still-valid secure session may remain open during a temporary network outage.',
      'Already-rendered screens may remain visible, but their values must be treated as stale until refreshed.',
      'The Offline & sync policy remains available from the app shell.',
    ],
    blockedOffline: <String>[
      'Attendance/time, payroll, task, leave/request, notification, and support refreshes.',
      'Remittance receipt/acceptance and other permissioned office operations.',
      'All reviews, requests and financial changes. Only attendance capture is saved offline; server review remains authoritative.',
    ],
    hasPersistentOfflineData: true,
    financialWritesOfflineAllowed: false,
    financialWritesSilentlyQueued: false,
    financialWritesAutomaticallyRetried: false,
    explicitIdempotentRetryAvailable: false,
  );

  static const _collector = MobileOfflinePolicy(
    role: AppRole.collector,
    summary:
        'Collectors may view the last encrypted assigned-route snapshot and capture their configured employee attendance offline. '
        'The cached route is explicitly read-only; collection, correction, remittance, custody, and other financial writes require the live server.',
    availableOffline: <String>[
      'The last successfully downloaded assigned route may be shown as an encrypted Offline copy for the signed-in collector.',
      'Cached route values are presentation-only and may be stale; Gilbic does not recalculate balances or eligibility offline.',
      'Attendance and break events are encrypted for this account and device, keep their original capture time, and sync automatically when the app resumes or reconnects.',
      'A still-valid secure session may remain open during a temporary network outage.',
    ],
    blockedOffline: <String>[
      'Regular and 7x7 payment or unable-to-pay recording, covered-date payment, correction, and cross-area collection.',
      'Remittance submission/acceptance, custody transfer, route refresh, and any server balance or receipt change.',
      'Any new financial write from an Offline copy.',
    ],
    hasPersistentOfflineData: true,
    financialWritesOfflineAllowed: false,
    financialWritesSilentlyQueued: false,
    financialWritesAutomaticallyRetried: false,
    explicitIdempotentRetryAvailable: true,
  );

  static const _client = MobileOfflinePolicy(
    role: AppRole.client,
    summary:
        'Client mobile financial data and request/evidence workflows require a live SPINA server connection. '
        'Gilbic does not create an offline borrower ledger or silently queue renewal/payment-proof requests.',
    availableOffline: <String>[
      'A still-valid secure session may remain open during a temporary network outage.',
      'Already-rendered screens may remain visible, but their loan/payment values must be treated as stale until refreshed.',
      'The Offline & sync policy remains available from the app shell.',
    ],
    blockedOffline: <String>[
      'Loan, statement, payment, receipt, notification, renewal, and support refreshes.',
      'Renewal requests, payment-proof upload/re-upload/correction, and other evidence submissions.',
      'Any operation that would create or change authoritative borrower or financial workflow state.',
    ],
    hasPersistentOfflineData: false,
    financialWritesOfflineAllowed: false,
    financialWritesSilentlyQueued: false,
    financialWritesAutomaticallyRetried: false,
    explicitIdempotentRetryAvailable: false,
  );
}
