import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gilbic_mobile/src/core/auth/app_role.dart';
import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/collector/collector_route_loader.dart';
import 'package:gilbic_mobile/src/core/device/device_identity.dart';
import 'package:gilbic_mobile/src/core/payments/collection_device_sequence.dart';
import 'package:gilbic_mobile/src/core/payments/payment_submission_repository.dart';
import 'package:gilbic_mobile/src/features/account/account_settings_page.dart';
import 'package:gilbic_mobile/src/features/collector/other_area_collection_page.dart';
import 'package:gilbic_mobile/src/features/dashboard/enhanced_role_dashboard.dart';
import 'package:gilbic_mobile/src/features/management/client_registration_approvals_page.dart';
import 'package:gilbic_mobile/src/features/management/management_accounting_measurement_page.dart';
import 'package:gilbic_mobile/src/features/management/management_collection_void_page.dart';
import 'package:gilbic_mobile/src/features/management/management_contract_collection_activation_page.dart';
import 'package:gilbic_mobile/src/features/management/management_ecl_outcome_review_page.dart';
import 'package:gilbic_mobile/src/features/management/management_financial_accounting_page.dart';
import 'package:gilbic_mobile/src/features/management/management_financial_statements_page.dart';
import 'package:gilbic_mobile/src/features/management/management_general_journal_launcher_page.dart';
import 'package:gilbic_mobile/src/features/management/management_loan_operations_page.dart';
import 'package:gilbic_mobile/src/features/management/management_loan_portfolio_page.dart';
import 'package:gilbic_mobile/src/features/management/management_no_collection_page.dart';
import 'package:gilbic_mobile/src/features/management/management_opening_balance_journal_page.dart';
import 'package:gilbic_mobile/src/features/management/management_opening_balance_workbook_page.dart';
import 'package:gilbic_mobile/src/features/management/management_renewal_requests_page.dart';
import 'package:gilbic_mobile/src/features/management/management_support_requests_page.dart';
import 'package:gilbic_mobile/src/features/management/management_staff_devices_page.dart';
import 'package:gilbic_mobile/src/features/notifications/activity_notifications_page.dart';
import 'package:gilbic_mobile/src/features/notifications/remittance_notifications_page.dart';
import 'package:gilbic_mobile/src/features/offline/mobile_offline_policy_page.dart';
import 'package:gilbic_mobile/src/theme/spina_theme.dart';

void main() {
  testWidgets(
    'management home groups each priority workflow by its day-to-day purpose',
    (tester) async {
      await tester.binding.setSurfaceSize(const Size(1100, 2400));
      addTearDown(() async => tester.binding.setSurfaceSize(null));

      await tester.pumpWidget(
        MaterialApp(
          theme: SpinaTheme.light,
          home: _dashboard(_managementSession),
        ),
      );
      await tester.pumpAndSettle();

      final review = find.byKey(const Key('management-section-review'));
      final clients = find.byKey(const Key('management-section-clients-loans'));
      final collections = find.byKey(
        const Key('management-section-collections-custody'),
      );
      final renewals = find.byKey(
        const Key('management-section-renewals-support'),
      );
      final account = find.byKey(
        const Key('management-section-account-connectivity'),
      );
      final accounting = find.byKey(
        const Key('management-section-reports-accounting'),
      );

      expect(review, findsOneWidget);
      expect(clients, findsOneWidget);
      expect(collections, findsOneWidget);
      expect(renewals, findsOneWidget);
      expect(account, findsOneWidget);
      expect(accounting, findsOneWidget);
      expect(find.text('People, access & requests'), findsOneWidget);

      final peopleLaunchers = find.descendant(
        of: renewals,
        matching: find.byType(ListTile),
      );
      expect(
        find.byKey(const Key('management-staff-devices')),
        findsOneWidget,
      );
      expect(
        tester.widget<ListTile>(peopleLaunchers.first).key,
        const Key('management-staff-devices'),
      );

      expect(
        find.descendant(
          of: review,
          matching: find.byKey(const Key('management-alerts-activity')),
        ),
        findsOneWidget,
      );
      expect(
        find.descendant(
          of: clients,
          matching: find.byKey(const Key('management-loans')),
        ),
        findsOneWidget,
      );
      expect(
        find.descendant(
          of: collections,
          matching: find.byKey(const Key('management-loan-operations')),
        ),
        findsOneWidget,
      );
      expect(
        find.descendant(
          of: renewals,
          matching: find.byKey(const Key('management-renewals')),
        ),
        findsOneWidget,
      );
      expect(
        find.descendant(
          of: account,
          matching: find.byKey(const Key('management-my-account-devices')),
        ),
        findsOneWidget,
      );
      expect(
        find.descendant(
          of: accounting,
          matching: find.byKey(const Key('management-financial-accounting')),
        ),
        findsOneWidget,
      );
    },
  );

  testWidgets(
    'management home exposes one launcher per workflow without overlay actions',
    (tester) async {
      await tester.binding.setSurfaceSize(const Size(1100, 2400));
      addTearDown(() async => tester.binding.setSurfaceSize(null));

      await tester.pumpWidget(
        MaterialApp(
          theme: SpinaTheme.light,
          home: _dashboard(_managementSession),
        ),
      );
      await tester.pumpAndSettle();

      expect(
        find.byKey(const Key('management-contract-collection-activation')),
        findsOneWidget,
      );
      expect(
        find.byKey(const Key('management-ecl-outcome-review')),
        findsOneWidget,
      );
      expect(
        find.byKey(const Key('management-accounting-measurement')),
        findsOneWidget,
      );
      expect(
        find.byKey(const Key('management-opening-balance-workbook')),
        findsOneWidget,
      );
      expect(find.byType(FloatingActionButton), findsNothing);

      expect(find.byKey(const Key('open-notification-center')), findsNothing);
      expect(find.byKey(const Key('open-account-settings')), findsNothing);
      expect(find.byKey(const Key('open-offline-policy')), findsNothing);
      expect(
        find.byKey(const Key('management-offline-policy')),
        findsOneWidget,
      );
    },
  );

  testWidgets(
    'management sections stay reachable on a small phone with larger text',
    (tester) async {
      await tester.binding.setSurfaceSize(const Size(360, 640));
      addTearDown(() async => tester.binding.setSurfaceSize(null));

      await tester.pumpWidget(
        MaterialApp(
          theme: SpinaTheme.light,
          builder: (context, child) => MediaQuery(
            data: MediaQuery.of(
              context,
            ).copyWith(textScaler: const TextScaler.linear(1.3)),
            child: child!,
          ),
          home: _dashboard(_managementSession),
        ),
      );
      await tester.pumpAndSettle();

      const sectionKeys = <String>[
        'management-section-review',
        'management-section-clients-loans',
        'management-section-collections-custody',
        'management-section-renewals-support',
        'management-section-account-connectivity',
        'management-section-reports-accounting',
      ];
      final scrollable = find.byType(Scrollable).first;

      for (final sectionKey in sectionKeys) {
        final section = find.byKey(Key(sectionKey));
        expect(section, findsOneWidget);
        await tester.scrollUntilVisible(section, 400, scrollable: scrollable);
        expect(tester.takeException(), isNull, reason: sectionKey);
      }

      expect(
        find.byKey(const Key('management-financial-statements')),
        findsOneWidget,
      );
      expect(tester.takeException(), isNull);
    },
  );

  testWidgets(
    'every management launcher opens its exact protected destination',
    (tester) async {
      await tester.binding.setSurfaceSize(const Size(1100, 2400));
      addTearDown(() async => tester.binding.setSurfaceSize(null));

      const destinations = <(String, Type)>[
        ('management-alerts-activity', ActivityNotificationsPage),
        ('management-loans', ManagementLoanPortfolioPage),
        (
          'management-contract-collection-activation',
          ManagementContractCollectionActivationPage,
        ),
        ('management-no-collection', ManagementNoCollectionPage),
        ('management-loan-operations', ManagementLoanOperationsPage),
        ('remittance-notifications', RemittanceNotificationsPage),
        ('management-direct-payment', OtherAreaCollectionPage),
        ('management-void-payment', ManagementCollectionVoidPage),
        ('management-staff-devices', ManagementStaffDevicesPage),
        ('management-renewals', ManagementRenewalRequestsPage),
        ('management-support', ManagementSupportRequestsPage),
        ('client-registration-approvals', ClientRegistrationApprovalsPage),
        ('management-my-account-devices', AccountSettingsPage),
        ('management-offline-policy', MobileOfflinePolicyPage),
        ('management-financial-accounting', ManagementFinancialAccountingPage),
        ('management-ecl-outcome-review', ManagementEclOutcomeReviewPage),
        (
          'management-accounting-measurement',
          ManagementAccountingMeasurementPage,
        ),
        (
          'management-opening-balance-workbook',
          ManagementOpeningBalanceWorkbookPage,
        ),
        (
          'management-opening-balance-journal',
          ManagementOpeningBalanceJournalPage,
        ),
        ('management-general-journal', ManagementGeneralJournalLauncherPage),
        ('management-financial-statements', ManagementFinancialStatementsPage),
      ];

      for (final destination in destinations) {
        await tester.pumpWidget(
          MaterialApp(
            theme: SpinaTheme.light,
            home: _dashboard(_managementSession),
          ),
        );
        await tester.pumpAndSettle();

        final launcher = find.byKey(Key(destination.$1));
        expect(launcher, findsOneWidget, reason: destination.$1);
        await tester.ensureVisible(launcher);
        await tester.tap(launcher);
        await tester.pumpAndSettle();

        expect(
          find.byType(destination.$2),
          findsOneWidget,
          reason: destination.$1,
        );
        await tester.pumpWidget(const SizedBox.shrink());
        await tester.pump();
      }
    },
  );
}

EnhancedRoleDashboard _dashboard(UserSession session) {
  return EnhancedRoleDashboard(
    session: session,
    onSignOut: () async {},
    collectorRouteLoader: _UnusedRouteLoader(),
    paymentSubmissionRepository: SpinaPaymentSubmissionRepository(),
    deviceIdentityProvider: DeviceIdentityProvider(
      store: MemoryDeviceIdentityStore(),
      platformResolver: () => 'android',
      appVersionResolver: () async => '1.0.0+1',
    ),
    collectionDeviceSequence: MemoryCollectionDeviceSequence(),
  );
}

const _managementSession = UserSession(
  userId: 'management-1',
  username: 'management.one',
  displayName: 'Management One',
  role: AppRole.management,
  rawRole: 'Management',
  accessToken: 'management-token',
  permissions: <String>[
    'management.dashboard.view',
    'accounting.view',
    'accounting.ecl.review',
    'accounting.cutover.manage',
    'account.manage',
    'collection.create',
    'collection.void.unremitted',
    'device.manage',
    'lending.contract_collection.activate',
    'lending.no_collection.manage',
    'remittance.view',
    'renewal.manage',
    'support.manage',
  ],
);

class _UnusedRouteLoader implements CollectorRouteLoader {
  @override
  Future<CollectorRouteLoadResult> loadToday(UserSession session) {
    throw StateError('Route loading is not expected in Management tests.');
  }
}
