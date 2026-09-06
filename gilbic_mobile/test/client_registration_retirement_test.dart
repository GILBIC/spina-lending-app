import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gilbic_mobile/src/core/auth/app_role.dart';
import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/device/device_identity.dart';
import 'package:gilbic_mobile/src/core/management/management_dashboard_overview.dart';
import 'package:gilbic_mobile/src/core/management/management_dashboard_overview_repository.dart';
import 'package:gilbic_mobile/src/core/payments/collection_device_sequence.dart';
import 'package:gilbic_mobile/src/core/payments/payment_submission_repository.dart';
import 'package:gilbic_mobile/src/features/management/management_dashboard.dart';

void main() {
  testWidgets(
    'Management account access does not restore retired Client registration approvals',
    (tester) async {
      await tester.binding.setSurfaceSize(const Size(1100, 2400));
      addTearDown(() async => tester.binding.setSurfaceSize(null));

      const session = UserSession(
        userId: 'management-1',
        username: 'management.one',
        displayName: 'Management One',
        role: AppRole.management,
        rawRole: 'Management',
        accessToken: 'management-token',
        permissions: <String>[
          'management.dashboard.view',
          'account.manage',
        ],
      );

      await tester.pumpWidget(
        MaterialApp(
          home: ManagementDashboard(
            session: session,
            onSignOut: () async {},
            paymentSubmissionRepository: SpinaPaymentSubmissionRepository(),
            deviceIdentityProvider: DeviceIdentityProvider(
              store: MemoryDeviceIdentityStore(),
              platformResolver: () => 'android',
              appVersionResolver: () async => '1.0.0+1',
              randomByteGenerator: (length) => List<int>.filled(length, 7),
            ),
            collectionDeviceSequence: MemoryCollectionDeviceSequence(),
            overviewRepository: _OverviewRepository(),
          ),
        ),
      );
      await tester.pumpAndSettle();

      expect(
        find.byKey(const Key('client-registration-approvals')),
        findsNothing,
      );
      expect(find.text('Client registrations'), findsNothing);
    },
  );
}

class _OverviewRepository implements ManagementDashboardOverviewRepository {
  @override
  Future<ManagementDashboardOverview> loadOverview(
    UserSession session, {
    required String deviceId,
  }) async {
    return ManagementDashboardOverview(
      generatedAt: DateTime.utc(2026, 9, 6, 2, 40),
      currency: 'PHP',
      ignoredMetricKeys: const <String>[],
      metrics: const <ManagementDashboardMetric>[
        ManagementDashboardMetric(
          key: ManagementDashboardMetricKey.activeClients,
          count: 0,
        ),
        ManagementDashboardMetric(
          key: ManagementDashboardMetricKey.activeLoans,
          count: 0,
        ),
        ManagementDashboardMetric(
          key: ManagementDashboardMetricKey.overdueLoans,
          count: 0,
        ),
        ManagementDashboardMetric(
          key: ManagementDashboardMetricKey.outstandingBalance,
          amount: '0.00',
        ),
        ManagementDashboardMetric(
          key: ManagementDashboardMetricKey.latestCollections,
          count: 0,
          amount: '0.00',
        ),
        ManagementDashboardMetric(
          key: ManagementDashboardMetricKey.unremittedCollections,
          count: 0,
          amount: '0.00',
        ),
        ManagementDashboardMetric(
          key: ManagementDashboardMetricKey.unreadActivity,
          count: 0,
        ),
      ],
    );
  }
}
