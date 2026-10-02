import 'package:flutter/material.dart';
import 'package:gilbic_mobile/src/core/auth/app_role.dart';
import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/collector/collector_route.dart';
import 'package:gilbic_mobile/src/core/collector/collector_route_loader.dart';
import 'package:gilbic_mobile/src/core/management/management_dashboard_overview.dart';
import 'package:gilbic_mobile/src/core/management/management_dashboard_overview_repository.dart';
import 'package:gilbic_mobile/src/core/payments/collection_device_sequence.dart';
import 'package:gilbic_mobile/src/core/payments/payment_submission_repository.dart';
import 'package:gilbic_mobile/src/features/client/client_dashboard.dart';
import 'package:gilbic_mobile/src/features/collector/collector_field_home_page.dart';
import 'package:gilbic_mobile/src/features/employee/employee_dashboard.dart';
import 'package:gilbic_mobile/src/features/management/management_dashboard.dart';
import 'client_fixture.dart';

UserSession roleSession(AppRole role) => UserSession(
  userId: 'synthetic-${role.name}',
  username: 'synthetic',
  displayName: 'Synthetic Worker With A Long Full Name',
  role: role,
  rawRole: role.name,
  accessToken: 'synthetic-only-token',
  permissions: switch (role) {
    AppRole.management => [
      'management.dashboard.view',
      'account.manage',
      'device.manage',
      'remittance.view',
      'renewal.manage',
      'support.manage',
    ],
    AppRole.employee => ['employee.portal.view'],
    AppRole.collector => [
      'collection.assigned.view',
      'collection.create',
      'employee.portal.view',
    ],
    _ => ['loan.self.view'],
  },
);

Widget roleHome(
  AppRole role, {
  ManagementDashboardOverviewRepository? overview,
}) => switch (role) {
  AppRole.management => ManagementDashboard(
    session: roleSession(role),
    onSignOut: () async {},
    deviceIdentityProvider: clientIdentity(),
    collectionDeviceSequence: MemoryCollectionDeviceSequence(),
    paymentSubmissionRepository: SpinaPaymentSubmissionRepository(),
    overviewRepository: overview ?? SyntheticOverview(),
  ),
  AppRole.employee => EmployeeDashboard(
    session: roleSession(role),
    onSignOut: () async {},
    deviceIdentityProvider: clientIdentity(),
  ),
  AppRole.collector => CollectorFieldHomePage(
    session: roleSession(role),
    onSignOut: () async {},
    deviceIdentityProvider: clientIdentity(),
    collectionDeviceSequence: MemoryCollectionDeviceSequence(),
    paymentSubmissionRepository: SpinaPaymentSubmissionRepository(),
    collectorRouteLoader: SyntheticRoute(),
  ),
  _ => ClientDashboard(
    session: clientSession(),
    onSignOut: () async {},
    deviceIdentityProvider: clientIdentity(),
    loanRepository: FakeClientLoanRepository(clientPortfolio()),
    scheduleRepository: FakeClientScheduleRepository(),
  ),
};

class SyntheticOverview implements ManagementDashboardOverviewRepository {
  @override
  Future<ManagementDashboardOverview> loadOverview(
    UserSession session, {
    required String deviceId,
  }) async => ManagementDashboardOverview(
    generatedAt: DateTime.utc(2026, 10, 2),
    currency: 'PHP',
    ignoredMetricKeys: const [],
    metrics: [
      for (final key in ManagementDashboardMetricKey.values)
        ManagementDashboardMetric(
          key: key,
          count: 12,
          amount: '123456789.01',
          asOfDate: DateTime(2026, 10, 2),
        ),
    ],
  );
}

class SyntheticRoute implements CollectorRouteLoader {
  @override
  Future<CollectorRouteLoadResult> loadToday(UserSession session) async =>
      CollectorRouteLoadResult(
        route: CollectorRoute(
          routeDate: DateTime(2026, 10, 2),
          collectorName: 'Synthetic Collector',
          areas: const ['Area'],
          expectedTotal: 123456789.01,
          entries: const [
            CollectorRouteEntry(
              id: 'regular',
              clientId: 'client',
              loanId: 'regular-loan',
              clientName: 'Synthetic Borrower With A Long Full Name',
              area: 'Area',
              loanType: 'Regular',
              dailyAmount: 123456789.01,
              balance: 123456789.01,
              status: 'Pending',
              passCount: 0,
              routeRevision: 'r:1',
            ),
            CollectorRouteEntry(
              id: 'seven',
              clientId: 'client',
              loanId: 'seven-loan',
              clientName: 'Synthetic Borrower With A Long Full Name',
              area: 'Area',
              loanType: '7x7',
              dailyAmount: 21,
              balance: 3000,
              status: 'Pending',
              passCount: 0,
              routeRevision: 's:1',
              sevenBySevenMobileEnabled: true,
            ),
          ],
        ),
        syncedAt: DateTime.utc(2026, 10, 2),
        isFromCache: false,
      );
}
