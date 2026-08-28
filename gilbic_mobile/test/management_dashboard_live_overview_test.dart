import 'dart:async';
import 'dart:collection';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gilbic_mobile/src/core/auth/app_role.dart';
import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/device/device_identity.dart';
import 'package:gilbic_mobile/src/core/management/management_dashboard_overview.dart';
import 'package:gilbic_mobile/src/core/management/management_dashboard_overview_repository.dart';
import 'package:gilbic_mobile/src/core/network/spina_api.dart';
import 'package:gilbic_mobile/src/core/payments/collection_device_sequence.dart';
import 'package:gilbic_mobile/src/core/payments/payment_submission_repository.dart';
import 'package:gilbic_mobile/src/features/management/client_registration_approvals_page.dart';
import 'package:gilbic_mobile/src/features/management/management_dashboard.dart';
import 'package:gilbic_mobile/src/features/management/management_loan_operations_page.dart';
import 'package:gilbic_mobile/src/features/management/management_loan_portfolio_page.dart';
import 'package:gilbic_mobile/src/features/management/management_renewal_requests_page.dart';
import 'package:gilbic_mobile/src/features/management/management_staff_devices_page.dart';
import 'package:gilbic_mobile/src/features/management/management_support_requests_page.dart';
import 'package:gilbic_mobile/src/features/notifications/activity_notifications_page.dart';
import 'package:gilbic_mobile/src/features/notifications/remittance_notifications_page.dart';
import 'package:gilbic_mobile/src/theme/spina_theme.dart';

void main() {
  testWidgets('shows loading without hiding protected launchers', (
    tester,
  ) async {
    final pending = Completer<ManagementDashboardOverview>();
    final repository = FakeManagementDashboardOverviewRepository(
      Queue.of(<Future<ManagementDashboardOverview>>[pending.future]),
    );

    await _pumpDashboard(tester, repository: repository);
    await tester.pump();

    expect(
      find.byKey(const Key('management-overview-loading')),
      findsOneWidget,
    );
    expect(find.byKey(const Key('management-section-review')), findsOneWidget);
    expect(repository.calls, 1);
  });

  testWidgets('shows live facts and only nonzero authorized attention', (
    tester,
  ) async {
    final repository = _completedRepository(_completeOverview);

    await _pumpDashboard(tester, repository: repository);
    await tester.pumpAndSettle();

    expect(find.byKey(const Key('management-overview-facts')), findsOneWidget);
    expect(
      find.byKey(const Key('management-overview-attention')),
      findsOneWidget,
    );
    expect(find.text('41 active clients'), findsOneWidget);
    expect(find.text('7 overdue loans'), findsOneWidget);
    expect(find.text('PHP 987,654.32 outstanding'), findsOneWidget);
    expect(find.text('PHP 3,750.50 unremitted collector cash'), findsOneWidget);
    expect(
      find.byKey(const Key('management-overview-metric-protectedRenewals')),
      findsOneWidget,
    );
    expect(
      find.byKey(const Key('management-overview-metric-borrowerSupport')),
      findsNothing,
    );
    expect(find.textContaining('Updated '), findsOneWidget);
  });

  testWidgets(
    'shows no pending state when returned attention metrics are zero',
    (tester) async {
      final overview = _overview(
        attention: const <ManagementDashboardMetric>[
          ManagementDashboardMetric(
            key: ManagementDashboardMetricKey.protectedRenewals,
            count: 0,
          ),
          ManagementDashboardMetric(
            key: ManagementDashboardMetricKey.unreadActivity,
            count: 0,
          ),
        ],
      );

      await _pumpDashboard(tester, repository: _completedRepository(overview));
      await tester.pumpAndSettle();

      expect(
        find.byKey(const Key('management-overview-no-pending')),
        findsOneWidget,
      );
      expect(
        find.byKey(const Key('management-overview-metric-assignedRemittances')),
        findsNothing,
      );
      expect(
        find.byKey(const Key('management-overview-metric-protectedRenewals')),
        findsNothing,
      );
    },
  );

  testWidgets('initial failure offers retry and keeps launchers usable', (
    tester,
  ) async {
    final failed = Completer<ManagementDashboardOverview>();
    final repository = FakeManagementDashboardOverviewRepository(
      Queue.of(<Future<ManagementDashboardOverview>>[failed.future]),
    );

    await _pumpDashboard(tester, repository: repository);
    await tester.pump();
    failed.completeError(
      const SpinaApiException(
        'The live overview is unavailable.',
        statusCode: 503,
      ),
    );
    await tester.pumpAndSettle();

    expect(find.byKey(const Key('management-overview-error')), findsOneWidget);
    expect(find.byKey(const Key('management-overview-retry')), findsOneWidget);
    expect(find.text('Live overview unavailable'), findsOneWidget);
    expect(find.byKey(const Key('management-section-review')), findsOneWidget);
    expect(find.byKey(const Key('management-loans')), findsOneWidget);
  });

  testWidgets('retry replaces an initial failure with live facts', (
    tester,
  ) async {
    final failed = Completer<ManagementDashboardOverview>();
    final retry = Completer<ManagementDashboardOverview>();
    final repository = FakeManagementDashboardOverviewRepository(
      Queue.of(<Future<ManagementDashboardOverview>>[
        failed.future,
        retry.future,
      ]),
    );

    await _pumpDashboard(tester, repository: repository);
    await tester.pump();
    failed.completeError(const SpinaApiException('Offline.'));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('management-overview-retry')));
    await tester.pump();
    retry.complete(_completeOverview);
    await tester.pumpAndSettle();

    expect(repository.calls, 2);
    expect(find.byKey(const Key('management-overview-facts')), findsOneWidget);
    expect(find.byKey(const Key('management-overview-error')), findsNothing);
  });

  testWidgets('concurrent refreshes load the installation identity only once', (
    tester,
  ) async {
    final identity = Completer<DeviceIdentity>();
    final first = Completer<ManagementDashboardOverview>();
    final second = Completer<ManagementDashboardOverview>();
    final deviceIdentityProvider = _ControlledDeviceIdentityProvider(
      identity.future,
    );
    final repository = FakeManagementDashboardOverviewRepository(
      Queue.of(<Future<ManagementDashboardOverview>>[
        first.future,
        second.future,
      ]),
    );

    await _pumpDashboard(
      tester,
      repository: repository,
      deviceIdentityProvider: deviceIdentityProvider,
    );
    await tester.pump();
    await tester.tap(find.byKey(const Key('management-overview-refresh')));
    await tester.pump();

    expect(deviceIdentityProvider.calls, 1);
    identity.complete(
      const DeviceIdentity(
        installationId: 'management-phone',
        platform: 'android',
        appVersion: '1.0.0+1',
      ),
    );
    await tester.pump();
    first.complete(_overview(activeClients: 41));
    second.complete(_overview(activeClients: 73));
    await tester.pumpAndSettle();
    expect(find.text('73 active clients'), findsOneWidget);
  });

  testWidgets('late initial response cannot replace a newer refresh', (
    tester,
  ) async {
    final first = Completer<ManagementDashboardOverview>();
    final second = Completer<ManagementDashboardOverview>();
    final repository = FakeManagementDashboardOverviewRepository(
      Queue.of(<Future<ManagementDashboardOverview>>[
        first.future,
        second.future,
      ]),
    );

    await _pumpDashboard(tester, repository: repository);
    await tester.pump();
    await tester.tap(find.byKey(const Key('management-overview-refresh')));
    await tester.pump();
    second.complete(_overview(activeClients: 222));
    await tester.pumpAndSettle();
    first.complete(_overview(activeClients: 111));
    await tester.pumpAndSettle();

    expect(find.text('222 active clients'), findsOneWidget);
    expect(find.text('111 active clients'), findsNothing);
  });

  testWidgets('failed refresh keeps the last snapshot and its timestamp', (
    tester,
  ) async {
    final refresh = Completer<ManagementDashboardOverview>();
    final repository = FakeManagementDashboardOverviewRepository(
      Queue.of(<Future<ManagementDashboardOverview>>[
        Future<ManagementDashboardOverview>.value(_completeOverview),
        refresh.future,
      ]),
    );

    await _pumpDashboard(tester, repository: repository);
    await tester.pumpAndSettle();
    final updatedText = tester
        .widget<Text>(find.textContaining('Updated '))
        .data;
    await tester.tap(find.byKey(const Key('management-overview-refresh')));
    await tester.pump();
    refresh.completeError(
      const SpinaApiException('Refresh unavailable.', statusCode: 503),
    );
    await tester.pumpAndSettle();

    expect(find.byKey(const Key('management-overview-facts')), findsOneWidget);
    expect(
      find.byKey(const Key('management-overview-refresh-error')),
      findsOneWidget,
    );
    expect(find.text(updatedText!), findsOneWidget);
  });

  testWidgets('pull to refresh requests a newer snapshot', (tester) async {
    final repository = FakeManagementDashboardOverviewRepository(
      Queue.of(<Future<ManagementDashboardOverview>>[
        Future<ManagementDashboardOverview>.value(_completeOverview),
        Future<ManagementDashboardOverview>.value(
          _overview(activeClients: 73),
        ),
      ]),
    );

    await _pumpDashboard(tester, repository: repository);
    await tester.pumpAndSettle();
    final refreshFuture = tester
        .widget<RefreshIndicator>(find.byType(RefreshIndicator))
        .onRefresh();
    await tester.pump();
    expect(repository.calls, 2);
    await refreshFuture;
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('management-overview-facts')), findsOneWidget);
  });

  testWidgets(
    '401 offers sign in again and 403 never signs out automatically',
    (tester) async {
      var signOuts = 0;
      final unauthorized = Completer<ManagementDashboardOverview>();
      await _pumpDashboard(
        tester,
        repository: FakeManagementDashboardOverviewRepository(
          Queue.of(<Future<ManagementDashboardOverview>>[unauthorized.future]),
        ),
        onSignOut: () async => signOuts += 1,
      );
      await tester.pump();
      unauthorized.completeError(
        const SpinaApiException('Expired.', statusCode: 401),
      );
      await tester.pumpAndSettle();
      expect(find.text('Session expired'), findsOneWidget);
      expect(signOuts, 0);
      await tester.tap(find.byKey(const Key('management-overview-sign-in')));
      await tester.pump();
      expect(signOuts, 1);

      await tester.pumpWidget(const SizedBox.shrink());
      await tester.pump();
      final forbidden = Completer<ManagementDashboardOverview>();
      await _pumpDashboard(
        tester,
        repository: FakeManagementDashboardOverviewRepository(
          Queue.of(<Future<ManagementDashboardOverview>>[forbidden.future]),
        ),
        onSignOut: () async => signOuts += 1,
      );
      await tester.pump();
      forbidden.completeError(
        const SpinaApiException('Denied.', statusCode: 403),
      );
      await tester.pumpAndSettle();
      expect(find.text('Live data access unavailable'), findsOneWidget);
      expect(signOuts, 1);
    },
  );

  testWidgets('every live metric opens its existing protected destination', (
    tester,
  ) async {
    await tester.binding.setSurfaceSize(const Size(1000, 1800));
    addTearDown(() async => tester.binding.setSurfaceSize(null));

    const destinations = <(ManagementDashboardMetricKey, Type)>[
      (ManagementDashboardMetricKey.activeClients, ManagementLoanPortfolioPage),
      (ManagementDashboardMetricKey.activeLoans, ManagementLoanPortfolioPage),
      (ManagementDashboardMetricKey.overdueLoans, ManagementLoanPortfolioPage),
      (
        ManagementDashboardMetricKey.outstandingBalance,
        ManagementLoanPortfolioPage,
      ),
      (
        ManagementDashboardMetricKey.latestCollections,
        ManagementLoanOperationsPage,
      ),
      (
        ManagementDashboardMetricKey.unremittedCollections,
        ManagementLoanOperationsPage,
      ),
      (
        ManagementDashboardMetricKey.assignedRemittances,
        RemittanceNotificationsPage,
      ),
      (
        ManagementDashboardMetricKey.protectedRenewals,
        ManagementRenewalRequestsPage,
      ),
      (
        ManagementDashboardMetricKey.staffRegistrations,
        ManagementStaffDevicesPage,
      ),
      (
        ManagementDashboardMetricKey.clientRegistrations,
        ClientRegistrationApprovalsPage,
      ),
      (
        ManagementDashboardMetricKey.collectorMobileDevices,
        ManagementStaffDevicesPage,
      ),
      (
        ManagementDashboardMetricKey.borrowerSupport,
        ManagementSupportRequestsPage,
      ),
      (ManagementDashboardMetricKey.unreadActivity, ActivityNotificationsPage),
    ];

    for (final destination in destinations) {
      await _pumpDashboard(
        tester,
        repository: _completedRepository(_allAttentionOverview),
      );
      await tester.pumpAndSettle();
      final card = find.byKey(
        Key('management-overview-metric-${destination.$1.name}'),
      );
      expect(card, findsOneWidget, reason: destination.$1.name);
      await tester.ensureVisible(card);
      await tester.tap(card);
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 350));
      expect(
        find.byType(destination.$2),
        findsOneWidget,
        reason: destination.$1.name,
      );
      await tester.pumpWidget(const SizedBox.shrink());
      await tester.pump();
    }
  });

  testWidgets('metric taps still enforce the launcher permission at tap time', (
    tester,
  ) async {
    const restrictedSession = UserSession(
      userId: 'management-2',
      username: 'restricted.manager',
      displayName: 'Restricted Manager',
      role: AppRole.management,
      rawRole: 'management',
      accessToken: 'restricted-token',
      permissions: <String>['management.dashboard.view'],
    );

    await _pumpDashboard(
      tester,
      repository: _completedRepository(_allAttentionOverview),
      session: restrictedSession,
    );
    await tester.pumpAndSettle();
    final card = find.byKey(
      const Key('management-overview-metric-assignedRemittances'),
    );
    await tester.ensureVisible(card);
    await tester.tap(card);
    await tester.pump();

    expect(find.byType(RemittanceNotificationsPage), findsNothing);
    expect(
      find.textContaining(
        'current server permissions do not allow Remittance requests',
      ),
      findsOneWidget,
    );
  });

  testWidgets('live overview fits a small phone with larger text', (
    tester,
  ) async {
    await tester.binding.setSurfaceSize(const Size(360, 640));
    addTearDown(() async => tester.binding.setSurfaceSize(null));

    await _pumpDashboard(
      tester,
      repository: _completedRepository(_allAttentionOverview),
      textScaler: const TextScaler.linear(1.3),
    );
    await tester.pumpAndSettle();

    final bottomCard = find.byKey(
      const Key('management-overview-metric-unreadActivity'),
    );
    await tester.scrollUntilVisible(
      bottomCard,
      400,
      scrollable: find.byType(Scrollable).first,
    );
    expect(bottomCard, findsOneWidget);
    expect(tester.takeException(), isNull);
  });
}

class FakeManagementDashboardOverviewRepository
    implements ManagementDashboardOverviewRepository {
  FakeManagementDashboardOverviewRepository(this.responses);

  final Queue<Future<ManagementDashboardOverview>> responses;
  int calls = 0;

  @override
  Future<ManagementDashboardOverview> loadOverview(
    UserSession session, {
    required String deviceId,
  }) {
    calls += 1;
    expect(deviceId, 'management-phone');
    return responses.removeFirst();
  }
}

FakeManagementDashboardOverviewRepository _completedRepository(
  ManagementDashboardOverview overview,
) {
  return FakeManagementDashboardOverviewRepository(
    Queue.of(<Future<ManagementDashboardOverview>>[
      Future<ManagementDashboardOverview>.value(overview),
    ]),
  );
}

Future<void> _pumpDashboard(
  WidgetTester tester, {
  required ManagementDashboardOverviewRepository repository,
  UserSession session = _managementSession,
  Future<void> Function()? onSignOut,
  DeviceIdentityProvider? deviceIdentityProvider,
  TextScaler textScaler = TextScaler.noScaling,
}) async {
  final store = MemoryDeviceIdentityStore()..value = 'management-phone';
  await tester.pumpWidget(
    MaterialApp(
      theme: SpinaTheme.light,
      builder: (context, child) => MediaQuery(
        data: MediaQuery.of(context).copyWith(textScaler: textScaler),
        child: child!,
      ),
      home: ManagementDashboard(
        session: session,
        onSignOut: onSignOut ?? () async {},
        paymentSubmissionRepository: SpinaPaymentSubmissionRepository(),
        deviceIdentityProvider:
            deviceIdentityProvider ??
            DeviceIdentityProvider(
              store: store,
              platformResolver: () => 'android',
              appVersionResolver: () async => '1.0.0+1',
            ),
        collectionDeviceSequence: MemoryCollectionDeviceSequence(),
        overviewRepository: repository,
      ),
    ),
  );
}

class _ControlledDeviceIdentityProvider extends DeviceIdentityProvider {
  _ControlledDeviceIdentityProvider(this.result)
    : super(store: MemoryDeviceIdentityStore());

  final Future<DeviceIdentity> result;
  int calls = 0;

  @override
  Future<DeviceIdentity> load() {
    calls += 1;
    return result;
  }
}

ManagementDashboardOverview _overview({
  int activeClients = 41,
  DateTime? generatedAt,
  List<ManagementDashboardMetric> attention =
      const <ManagementDashboardMetric>[],
}) {
  return ManagementDashboardOverview(
    generatedAt: generatedAt ?? DateTime.utc(2026, 8, 29, 4, 15, 30),
    currency: 'PHP',
    metrics: <ManagementDashboardMetric>[
      ManagementDashboardMetric(
        key: ManagementDashboardMetricKey.activeClients,
        count: activeClients,
      ),
      const ManagementDashboardMetric(
        key: ManagementDashboardMetricKey.activeLoans,
        count: 48,
      ),
      const ManagementDashboardMetric(
        key: ManagementDashboardMetricKey.overdueLoans,
        count: 7,
      ),
      const ManagementDashboardMetric(
        key: ManagementDashboardMetricKey.outstandingBalance,
        amount: '987654.32',
      ),
      ManagementDashboardMetric(
        key: ManagementDashboardMetricKey.latestCollections,
        count: 32,
        amount: '18450.00',
        asOfDate: DateTime.utc(2026, 8, 28),
      ),
      const ManagementDashboardMetric(
        key: ManagementDashboardMetricKey.unremittedCollections,
        count: 6,
        amount: '3750.50',
      ),
      ...attention,
    ],
    ignoredMetricKeys: const <String>[],
  );
}

final _completeOverview = _overview(
  attention: const <ManagementDashboardMetric>[
    ManagementDashboardMetric(
      key: ManagementDashboardMetricKey.assignedRemittances,
      count: 2,
      amount: '1400.00',
    ),
    ManagementDashboardMetric(
      key: ManagementDashboardMetricKey.protectedRenewals,
      count: 5,
    ),
    ManagementDashboardMetric(
      key: ManagementDashboardMetricKey.staffRegistrations,
      count: 3,
    ),
    ManagementDashboardMetric(
      key: ManagementDashboardMetricKey.clientRegistrations,
      count: 4,
    ),
    ManagementDashboardMetric(
      key: ManagementDashboardMetricKey.collectorMobileDevices,
      count: 1,
    ),
    ManagementDashboardMetric(
      key: ManagementDashboardMetricKey.unreadActivity,
      count: 9,
    ),
  ],
);

final _allAttentionOverview = _overview(
  attention: const <ManagementDashboardMetric>[
    ManagementDashboardMetric(
      key: ManagementDashboardMetricKey.assignedRemittances,
      count: 2,
      amount: '1400.00',
    ),
    ManagementDashboardMetric(
      key: ManagementDashboardMetricKey.protectedRenewals,
      count: 5,
    ),
    ManagementDashboardMetric(
      key: ManagementDashboardMetricKey.staffRegistrations,
      count: 3,
    ),
    ManagementDashboardMetric(
      key: ManagementDashboardMetricKey.clientRegistrations,
      count: 4,
    ),
    ManagementDashboardMetric(
      key: ManagementDashboardMetricKey.collectorMobileDevices,
      count: 1,
    ),
    ManagementDashboardMetric(
      key: ManagementDashboardMetricKey.borrowerSupport,
      count: 8,
    ),
    ManagementDashboardMetric(
      key: ManagementDashboardMetricKey.unreadActivity,
      count: 9,
    ),
  ],
);

const _managementSession = UserSession(
  userId: 'management-1',
  username: 'management.one',
  displayName: 'Management One',
  role: AppRole.management,
  rawRole: 'management',
  accessToken: 'management-token',
  permissions: <String>[
    'management.dashboard.view',
    'account.manage',
    'device.manage',
    'remittance.view',
    'renewal.manage',
    'support.manage',
  ],
);
