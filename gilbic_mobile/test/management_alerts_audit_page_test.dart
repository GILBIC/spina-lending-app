import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gilbic_mobile/src/core/auth/app_role.dart';
import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/device/device_identity.dart';
import 'package:gilbic_mobile/src/core/management/management_alerts_audit.dart';
import 'package:gilbic_mobile/src/core/management/management_alerts_audit_repository.dart';
import 'package:gilbic_mobile/src/core/network/spina_api.dart';
import 'package:gilbic_mobile/src/features/management/management_alerts_audit_page.dart';
import 'package:gilbic_mobile/src/theme/spina_theme.dart';

void main() {
  testWidgets('compact read-only alerts and audit remain usable on a phone', (
    tester,
  ) async {
    await tester.binding.setSurfaceSize(const Size(360, 640));
    addTearDown(() async => tester.binding.setSurfaceSize(null));
    ManagementAlertsAuditNavigation? opened;
    final repository = _FakeRepository(_snapshot);

    await tester.pumpWidget(
      MaterialApp(
        theme: SpinaTheme.light,
        home: ManagementAlertsAuditPage(
          session: _session,
          deviceIdentityProvider: _deviceProvider,
          repository: repository,
          onOpenDestination: (destination) => opened = destination,
        ),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.text('Alerts & Audit'), findsOneWidget);
    expect(
      find.byKey(const Key('management-alert-assigned_remittances')),
      findsOneWidget,
    );
    expect(find.text('Read-only visibility.'), findsOneWidget);
    await tester.scrollUntilVisible(
      find.byKey(const Key('management-audit-financial:91')),
      240,
      scrollable: find.byType(Scrollable).first,
    );
    expect(find.text('Protected journal posted'), findsOneWidget);
    expect(find.text('Tax Recoverable refund'), findsOneWidget);
    expect(find.text('Approve'), findsNothing);
    expect(find.text('Reject'), findsNothing);
    expect(find.text('Edit'), findsNothing);
    expect(tester.takeException(), isNull);

    await tester.ensureVisible(
      find.byKey(const Key('management-alerts-payment-updates')),
    );
    await tester.tap(
      find.byKey(const Key('management-alerts-payment-updates')),
    );
    await tester.pump();
    expect(opened, ManagementAlertsAuditNavigation.paymentUpdates);
  });

  testWidgets('a refresh error preserves the last authoritative snapshot', (
    tester,
  ) async {
    final repository = _ScriptedRepository();
    await tester.pumpWidget(
      MaterialApp(
        theme: SpinaTheme.light,
        home: ManagementAlertsAuditPage(
          session: _session,
          deviceIdentityProvider: _deviceProvider,
          repository: repository,
        ),
      ),
    );
    await tester.pumpAndSettle();
    expect(find.text('Protected journal posted'), findsOneWidget);

    await tester.tap(find.byKey(const Key('management-alerts-audit-refresh')));
    await tester.pumpAndSettle();

    expect(find.text('Protected journal posted'), findsOneWidget);
    expect(
      find.byKey(const Key('management-alerts-audit-refresh-error')),
      findsOneWidget,
    );
    expect(find.textContaining('last successful snapshot'), findsOneWidget);
  });

  testWidgets('permission failure is safe, explicit, and retryable', (
    tester,
  ) async {
    final repository = _ErrorRepository();
    await tester.pumpWidget(
      MaterialApp(
        theme: SpinaTheme.light,
        home: ManagementAlertsAuditPage(
          session: _session,
          deviceIdentityProvider: _deviceProvider,
          repository: repository,
        ),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.text('Alerts & Audit access unavailable'), findsOneWidget);
    expect(
      find.byKey(const Key('management-alerts-audit-retry')),
      findsOneWidget,
    );
    expect(find.textContaining('dashboard permission'), findsOneWidget);
  });
}

class _FakeRepository implements ManagementAlertsAuditRepository {
  _FakeRepository(this.snapshot);

  final ManagementAlertsAuditSnapshot snapshot;

  @override
  Future<ManagementAlertsAuditSnapshot> loadSnapshot(
    UserSession session, {
    required String deviceId,
    int windowDays = 30,
    int limit = 100,
  }) async => snapshot;
}

class _ScriptedRepository implements ManagementAlertsAuditRepository {
  int calls = 0;

  @override
  Future<ManagementAlertsAuditSnapshot> loadSnapshot(
    UserSession session, {
    required String deviceId,
    int windowDays = 30,
    int limit = 100,
  }) async {
    calls += 1;
    if (calls == 1) return _snapshot;
    throw const SpinaApiException(
      'Management alerts are temporarily unavailable.',
      statusCode: 503,
      code: 'management_alerts_audit_unavailable',
    );
  }
}

class _ErrorRepository implements ManagementAlertsAuditRepository {
  @override
  Future<ManagementAlertsAuditSnapshot> loadSnapshot(
    UserSession session, {
    required String deviceId,
    int windowDays = 30,
    int limit = 100,
  }) => throw const SpinaApiException(
    'Management dashboard permission is required.',
    statusCode: 403,
    code: 'management_dashboard_permission_required',
  );
}

final _deviceProvider = DeviceIdentityProvider(
  store: MemoryDeviceIdentityStore(),
  platformResolver: () => 'android',
  appVersionResolver: () async => '1.0.0+1',
);

const _session = UserSession(
  userId: '22222222-2222-4222-8222-222222222222',
  username: 'manager',
  displayName: 'Management User',
  role: AppRole.management,
  rawRole: 'Management',
  accessToken: 'access-token',
  permissions: <String>['management.dashboard.view', 'accounting.view'],
);

final _snapshot = ManagementAlertsAuditSnapshot(
  generatedAt: DateTime.utc(2026, 8, 30, 3, 5),
  windowDays: 30,
  limit: 100,
  visibleDomains: const <ManagementAlertsAuditDomain>[
    ManagementAlertsAuditDomain.paymentUpdates,
    ManagementAlertsAuditDomain.remittanceCustody,
    ManagementAlertsAuditDomain.financial,
  ],
  alerts: const <ManagementAlert>[
    ManagementAlert(
      code: ManagementAlertCode.assignedRemittances,
      domain: ManagementAlertsAuditDomain.remittanceCustody,
      title: 'Remittances assigned for review',
      count: 3,
      amount: '1450.00',
      severity: ManagementAlertsAuditSeverity.review,
      navigation: ManagementAlertsAuditNavigation.remittanceReview,
    ),
  ],
  events: <ManagementAuditEvent>[
    ManagementAuditEvent(
      eventKey: 'financial:91',
      domain: ManagementAlertsAuditDomain.financial,
      action: ManagementAuditAction.financialPosted,
      title: 'Protected journal posted',
      severity: ManagementAlertsAuditSeverity.attention,
      navigation: ManagementAlertsAuditNavigation.financialAccounting,
      occurredAt: DateTime.utc(2026, 8, 30, 3),
      businessDate: DateTime.utc(2026, 8, 30),
      recordId: '44444444-4444-4444-8444-444444444444',
      reference: 'GJ-2026-00000091',
      currentState: 'posted',
      actorName: 'Accounting Manager',
      checkerName: 'Accounting Manager',
      sourceType: 'v1_tax_recoverable_refund',
      sourceLabel: 'Tax Recoverable refund',
      reason: null,
    ),
  ],
  eventTotalCount: 1,
  notice: 'Read-only visibility.',
);
