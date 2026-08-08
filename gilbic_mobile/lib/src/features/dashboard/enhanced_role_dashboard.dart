import 'package:flutter/material.dart';
import 'package:gilbic_mobile/src/core/auth/app_role.dart';
import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/collector/collector_route_loader.dart';
import 'package:gilbic_mobile/src/core/device/device_identity.dart';
import 'package:gilbic_mobile/src/core/payments/collection_device_sequence.dart';
import 'package:gilbic_mobile/src/core/payments/payment_submission_repository.dart';
import 'package:gilbic_mobile/src/features/dashboard/role_dashboard.dart';
import 'package:gilbic_mobile/src/features/management/management_accounting_measurement_page.dart';
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

  @override
  Widget build(BuildContext context) {
    final dashboard = RoleDashboard(
      session: session,
      onSignOut: onSignOut,
      collectorRouteLoader: collectorRouteLoader,
      paymentSubmissionRepository: paymentSubmissionRepository,
      deviceIdentityProvider: deviceIdentityProvider,
      collectionDeviceSequence: collectionDeviceSequence,
    );
    if (session.role != AppRole.management) {
      return dashboard;
    }
    return Stack(
      children: [
        dashboard,
        Positioned(
          right: 18,
          bottom: 18,
          child: SafeArea(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.end,
              mainAxisSize: MainAxisSize.min,
              children: [
                FloatingActionButton.extended(
                  key: const Key('management-accounting-measurement'),
                  heroTag: 'management-accounting-measurement',
                  onPressed: () {
                    Navigator.of(context).push(
                      MaterialPageRoute<void>(
                        builder: (context) => ManagementAccountingMeasurementPage(
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
                FloatingActionButton.extended(
                  key: const Key('management-opening-balance-workbook'),
                  heroTag: 'management-opening-balance-workbook',
                  onPressed: () {
                    Navigator.of(context).push(
                      MaterialPageRoute<void>(
                        builder: (context) => ManagementOpeningBalanceWorkbookPage(
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
      ],
    );
  }
}