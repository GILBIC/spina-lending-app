import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gilbic_mobile/src/core/auth/app_role.dart';
import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/device/device_identity.dart';
import 'package:gilbic_mobile/src/core/management/management_loan.dart';
import 'package:gilbic_mobile/src/core/management/management_loan_repository.dart';
import 'package:gilbic_mobile/src/core/management/management_operations.dart';
import 'package:gilbic_mobile/src/core/management/management_operations_repository.dart';
import 'package:gilbic_mobile/src/core/network/spina_api.dart';
import 'package:gilbic_mobile/src/features/management/management_operational_overview_page.dart';

void main() {
  for (final platform in <TargetPlatform>[
    TargetPlatform.android,
    TargetPlatform.iOS,
  ]) {
    testWidgets('Management operational overview renders on ${platform.name}', (
      tester,
    ) async {
      await tester.binding.setSurfaceSize(const Size(900, 1600));
      final originalPlatform = debugDefaultTargetPlatformOverride;
      debugDefaultTargetPlatformOverride = platform;
      try {
        await tester.pumpWidget(
          MaterialApp(
            home: ManagementOperationalOverviewPage(
              session: _managementSession,
              deviceIdentityProvider: _deviceIdentity(
                platform == TargetPlatform.iOS ? 'ios' : 'android',
              ),
              loanRepository: _LoanRepository(),
              operationsRepository: _OperationsRepository(),
            ),
          ),
        );
        await tester.pumpAndSettle();

        expect(
          find.byKey(const Key('management-operational-overview-page')),
          findsOneWidget,
        );
        expect(find.text('Active clients'), findsOneWidget);
        expect(find.text('12'), findsOneWidget);
        expect(find.text('Remaining balance'), findsOneWidget);
        expect(find.text('₱85,000.00'), findsOneWidget);
        expect(find.text('Latest collections'), findsOneWidget);
        expect(find.text('₱4,500.00'), findsOneWidget);
        expect(
          find.byKey(const Key('management-overview-alert-overdue')),
          findsOneWidget,
        );
        expect(
          find.byKey(const Key('management-overview-alert-unremitted')),
          findsOneWidget,
        );
        expect(
          find.byKey(const Key('management-overview-alert-pending-remittance')),
          findsOneWidget,
        );
        expect(
          find.byKey(const Key('management-overview-alert-approved-renewal')),
          findsOneWidget,
        );
      } finally {
        await tester.pumpWidget(const SizedBox.shrink());
        debugDefaultTargetPlatformOverride = originalPlatform;
        await tester.binding.setSurfaceSize(null);
      }
    });
  }

  testWidgets('overview exposes server failure and explicit retry', (tester) async {
    await tester.pumpWidget(
      MaterialApp(
        home: ManagementOperationalOverviewPage(
          session: _managementSession,
          deviceIdentityProvider: _deviceIdentity('android'),
          loanRepository: _FailingLoanRepository(),
          operationsRepository: _OperationsRepository(),
        ),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.text('Management overview server unavailable.'), findsOneWidget);
    expect(
      find.byKey(const Key('management-overview-retry')),
      findsOneWidget,
    );
  });
}

const _managementSession = UserSession(
  userId: 'management-overview',
  username: 'management.one',
  displayName: 'Management One',
  role: AppRole.management,
  rawRole: 'Management',
  accessToken: 'management-token',
  permissions: <String>['management.dashboard.view'],
);

DeviceIdentityProvider _deviceIdentity(String platform) {
  return DeviceIdentityProvider(
    store: MemoryDeviceIdentityStore(),
    platformResolver: () => platform,
    appVersionResolver: () async => '1.0.0',
    randomByteGenerator: (length) => List<int>.filled(length, 7),
  );
}

class _LoanRepository implements ManagementLoanRepository {
  @override
  Future<ManagementLoanPortfolio> loadPortfolio(
    UserSession session, {
    required String deviceId,
    required String query,
    required String status,
  }) async {
    expect(session.role, AppRole.management);
    expect(query, isEmpty);
    expect(status, 'active');
    return const ManagementLoanPortfolio(
      summary: ManagementLoanSummary(
        activeLoanCount: 15,
        activeClientCount: 12,
        activePrincipalTotal: 120000,
        activeRemainingTotal: 85000,
        overdueActiveCount: 2,
        activeSevenBySevenCount: 3,
        approvedRenewalCount: 1,
      ),
      loans: <ManagementLoanItem>[],
      notice: 'View only.',
    );
  }
}

class _FailingLoanRepository implements ManagementLoanRepository {
  @override
  Future<ManagementLoanPortfolio> loadPortfolio(
    UserSession session, {
    required String deviceId,
    required String query,
    required String status,
  }) {
    throw const SpinaApiException(
      'Management overview server unavailable.',
      code: 'network_unavailable',
    );
  }
}

class _OperationsRepository implements ManagementOperationsRepository {
  @override
  Future<ManagementOperationsOverview> loadOverview(
    UserSession session, {
    required String deviceId,
    required String query,
    required String status,
  }) async {
    expect(session.role, AppRole.management);
    expect(query, isEmpty);
    expect(status, 'all');
    return ManagementOperationsOverview(
      summary: ManagementOperationsSummary(
        latestCollectionDate: DateTime(2026, 8, 15),
        latestDayAmount: 4500,
        latestDayPaymentCount: 28,
        latestDayUnableToPayCount: 2,
        unremittedAmount: 1200,
        unremittedEntryCount: 4,
        pendingRemittanceAmount: 3000,
        pendingRemittanceCount: 2,
        receivedRemittanceAmount: 18000,
        receivedRemittanceCount: 6,
        correctionCount: 1,
        voidCount: 0,
      ),
      entries: const <ManagementOperationEntry>[],
      audits: const <ManagementOperationAudit>[],
      notice: 'View only.',
    );
  }
}
