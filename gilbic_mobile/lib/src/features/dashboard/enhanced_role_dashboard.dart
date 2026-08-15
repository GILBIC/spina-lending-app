import 'package:flutter/material.dart';
import 'package:gilbic_mobile/src/core/auth/app_role.dart';
import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/collector/collector_route_loader.dart';
import 'package:gilbic_mobile/src/core/device/device_identity.dart';
import 'package:gilbic_mobile/src/core/payments/collection_device_sequence.dart';
import 'package:gilbic_mobile/src/core/payments/payment_submission_repository.dart';
import 'package:gilbic_mobile/src/features/account/account_settings_page.dart';
import 'package:gilbic_mobile/src/features/dashboard/role_dashboard.dart';
import 'package:gilbic_mobile/src/features/management/management_accounting_measurement_page.dart';
import 'package:gilbic_mobile/src/features/management/management_contract_collection_activation_page.dart';
import 'package:gilbic_mobile/src/features/management/management_ecl_outcome_review_page.dart';
import 'package:gilbic_mobile/src/features/management/management_opening_balance_workbook_page.dart';

class EnhancedRoleDashboard extends StatelessWidget {
  const EnhancedRoleDashboard({
    required this.session,
    required this.onSignOut,
    required this.collectorRouteLoader,
    required this.paymentSubmissionRepository,
    required this.deviceIdentityProvider,
    required this.collectionDeviceSequence,
    super.key,
  });

  final UserSession session;
  final Future<void> Function() onSignOut;
  final CollectorRouteLoader collectorRouteLoader;
  final PaymentSubmissionRepository paymentSubmissionRepository;
  final DeviceIdentityProvider deviceIdentityProvider;
  final CollectionDeviceSequence collectionDeviceSequence;

  void _openAccount(BuildContext context) {
    Navigator.of(context).push(
      MaterialPageRoute<void>(
        builder: (context) => AccountSettingsPage(
          session: session,
          onSignOut: onSignOut,
          deviceIdentityProvider: deviceIdentityProvider,
        ),
      ),
    );
  }

  Widget _accountButton(BuildContext context) {
    return Positioned(
      right: 56,
      top: 0,
      child: SafeArea(
        child: IconButton(
          key: const Key('open-account-settings'),
          tooltip: 'Profile & security',
          onPressed: () => _openAccount(context),
          icon: const Icon(Icons.account_circle_outlined),
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    if (!_hasDashboardAccess(session)) {
      return _DashboardPermissionDenied(
        session: session,
        onSignOut: onSignOut,
        deviceIdentityProvider: deviceIdentityProvider,
      );
    }

    final dashboard = RoleDashboard(
      session: session,
      onSignOut: onSignOut,
      collectorRouteLoader: collectorRouteLoader,
      paymentSubmissionRepository: paymentSubmissionRepository,
      deviceIdentityProvider: deviceIdentityProvider,
      collectionDeviceSequence: collectionDeviceSequence,
    );

    final layers = <Widget>[
      dashboard,
      _accountButton(context),
    ];

    if (session.role == AppRole.management) {
      final canActivateContractCollection =
          session.hasPermission('lending.contract_collection.activate');
      final canReviewEcl = session.hasPermission('accounting.ecl.review');
      final canViewLoanMeasurement = session.hasPermission('accounting.view');
      final canManageOpeningWorkbook =
          session.hasPermission('accounting.cutover.manage');
      final hasEnhancedAction = canActivateContractCollection ||
          canReviewEcl ||
          canViewLoanMeasurement ||
          canManageOpeningWorkbook;

      if (hasEnhancedAction) {
        layers.add(
          Positioned(
            right: 18,
            bottom: 18,
            child: SafeArea(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.end,
                mainAxisSize: MainAxisSize.min,
                children: [
                  if (canActivateContractCollection) ...[
                    FloatingActionButton.extended(
                      key: const Key('management-contract-collection-activation'),
                      heroTag: 'management-contract-collection-activation',
                      onPressed: () {
                        Navigator.of(context).push(
                          MaterialPageRoute<void>(
                            builder: (context) =>
                                ManagementContractCollectionActivationPage(
                              session: session,
                              deviceIdentityProvider: deviceIdentityProvider,
                            ),
                          ),
                        );
                      },
                      icon: const Icon(Icons.verified_user_outlined),
                      label: const Text('Contract Collection'),
                    ),
                    const SizedBox(height: 10),
                  ],
                  if (canReviewEcl) ...[
                    FloatingActionButton.extended(
                      key: const Key('management-ecl-outcome-review'),
                      heroTag: 'management-ecl-outcome-review',
                      onPressed: () {
                        Navigator.of(context).push(
                          MaterialPageRoute<void>(
                            builder: (context) => ManagementEclOutcomeReviewPage(
                              session: session,
                              deviceIdentityProvider: deviceIdentityProvider,
                            ),
                          ),
                        );
                      },
                      icon: const Icon(Icons.fact_check_outlined),
                      label: const Text('Outcome Review'),
                    ),
                    const SizedBox(height: 10),
                  ],
                  if (canViewLoanMeasurement) ...[
                    FloatingActionButton.extended(
                      key: const Key('management-accounting-measurement'),
                      heroTag: 'management-accounting-measurement',
                      onPressed: () {
                        Navigator.of(context).push(
                          MaterialPageRoute<void>(
                            builder: (context) =>
                                ManagementAccountingMeasurementPage(
                              session: session,
                              deviceIdentityProvider: deviceIdentityProvider,
                            ),
                          ),
                        );
                      },
                      icon: const Icon(Icons.calculate_outlined),
                      label: const Text('Loan Measurement'),
                    ),
                    const SizedBox(height: 10),
                  ],
                  if (canManageOpeningWorkbook)
                    FloatingActionButton.extended(
                      key: const Key('management-opening-balance-workbook'),
                      heroTag: 'management-opening-balance-workbook',
                      onPressed: () {
                        Navigator.of(context).push(
                          MaterialPageRoute<void>(
                            builder: (context) =>
                                ManagementOpeningBalanceWorkbookPage(
                              session: session,
                              deviceIdentityProvider: deviceIdentityProvider,
                            ),
                          ),
                        );
                      },
                      icon: const Icon(Icons.table_view_outlined),
                      label: const Text('Opening Workbook'),
                    ),
                ],
              ),
            ),
          ),
        );
      }
    }

    return Stack(children: layers);
  }
}

bool _hasDashboardAccess(UserSession session) {
  return switch (session.role) {
    AppRole.client => session.hasPermission('loan.self.view'),
    AppRole.collector => session.hasAllPermissions(
        const <String>['route.view', 'collection.create'],
      ),
    AppRole.employee => session.hasPermission('employee.portal.view'),
    AppRole.management => session.hasPermission('management.dashboard.view'),
  };
}

class _DashboardPermissionDenied extends StatelessWidget {
  const _DashboardPermissionDenied({
    required this.session,
    required this.onSignOut,
    required this.deviceIdentityProvider,
  });

  final UserSession session;
  final Future<void> Function() onSignOut;
  final DeviceIdentityProvider deviceIdentityProvider;

  void _openAccount(BuildContext context) {
    Navigator.of(context).push(
      MaterialPageRoute<void>(
        builder: (context) => AccountSettingsPage(
          session: session,
          onSignOut: onSignOut,
          deviceIdentityProvider: deviceIdentityProvider,
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: Text('${session.role.label} Access'),
        actions: [
          IconButton(
            key: const Key('open-account-settings'),
            tooltip: 'Profile & security',
            onPressed: () => _openAccount(context),
            icon: const Icon(Icons.account_circle_outlined),
          ),
          IconButton(
            tooltip: 'Sign out',
            onPressed: onSignOut,
            icon: const Icon(Icons.logout),
          ),
        ],
      ),
      body: Center(
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: Column(
            key: const Key('dashboard-permission-denied'),
            mainAxisSize: MainAxisSize.min,
            children: [
              const Icon(Icons.lock_outline, size: 44),
              const SizedBox(height: 12),
              Text(
                'Access unavailable',
                style: Theme.of(context).textTheme.titleLarge,
              ),
              const SizedBox(height: 8),
              Text(
                'Your current server permissions do not allow this '
                '${session.role.label} dashboard. You can still review your profile, '
                'session, and registered devices or sign out.',
                textAlign: TextAlign.center,
              ),
            ],
          ),
        ),
      ),
    );
  }
}
