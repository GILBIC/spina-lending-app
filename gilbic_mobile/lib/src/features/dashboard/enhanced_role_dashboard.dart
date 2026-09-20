import 'package:flutter/material.dart';
import 'package:gilbic_mobile/src/core/auth/app_role.dart';
import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/collector/collector_route_loader.dart';
import 'package:gilbic_mobile/src/core/device/device_identity.dart';
import 'package:gilbic_mobile/src/core/loans/client_loan_repository.dart';
import 'package:gilbic_mobile/src/core/management/management_alerts_audit_repository.dart';
import 'package:gilbic_mobile/src/core/management/management_dashboard_overview_repository.dart';
import 'package:gilbic_mobile/src/core/management/management_employee_activity_repository.dart';
import 'package:gilbic_mobile/src/core/payments/collection_device_sequence.dart';
import 'package:gilbic_mobile/src/core/payments/payment_submission_repository.dart';
import 'package:gilbic_mobile/src/features/account/account_settings_page.dart';
import 'package:gilbic_mobile/src/features/collector/collector_field_home_page.dart';
import 'package:gilbic_mobile/src/features/dashboard/role_dashboard.dart';
import 'package:gilbic_mobile/src/features/notifications/notification_center_page.dart';
import 'package:gilbic_mobile/src/features/offline/mobile_offline_policy_page.dart';
import 'package:gilbic_mobile/src/features/employee/employee_dashboard.dart';

class EnhancedRoleDashboard extends StatelessWidget {
  const EnhancedRoleDashboard({
    required this.session,
    required this.onSignOut,
    required this.collectorRouteLoader,
    required this.paymentSubmissionRepository,
    required this.deviceIdentityProvider,
    required this.collectionDeviceSequence,
    this.managementDashboardOverviewRepository,
    this.managementAlertsAuditRepository,
    this.managementEmployeeActivityRepository,
    this.clientLoanRepository,
    super.key,
  });

  final UserSession session;
  final Future<void> Function() onSignOut;
  final CollectorRouteLoader collectorRouteLoader;
  final PaymentSubmissionRepository paymentSubmissionRepository;
  final DeviceIdentityProvider deviceIdentityProvider;
  final CollectionDeviceSequence collectionDeviceSequence;
  final ManagementDashboardOverviewRepository?
  managementDashboardOverviewRepository;
  final ManagementAlertsAuditRepository? managementAlertsAuditRepository;
  final ManagementEmployeeActivityRepository?
  managementEmployeeActivityRepository;
  final ClientLoanRepository? clientLoanRepository;

  @override
  Widget build(BuildContext context) {
    if (session.hasRole(AppRole.collector) && session.hasRole(AppRole.employee)) {
      final collectorAllowed = session.hasAllPermissions(['route.view', 'collection.create']);
      final officeAllowed = session.hasPermission('employee.portal.view');
      final collector = CollectorFieldHomePage(session: session, onSignOut: onSignOut,
        collectorRouteLoader: collectorRouteLoader, paymentSubmissionRepository: paymentSubmissionRepository,
        deviceIdentityProvider: deviceIdentityProvider, collectionDeviceSequence: collectionDeviceSequence);
      final office = EmployeeDashboard(session: session, onSignOut: onSignOut, deviceIdentityProvider: deviceIdentityProvider);
      if (collectorAllowed && officeAllowed) {
        return _CombinedWorkerWorkspace(collector: collector, office: office, startInOffice: session.role == AppRole.employee);
      }
      if (collectorAllowed) return collector;
      if (officeAllowed) return office;
    }
    if (!_hasDashboardAccess(session)) {
      return _DashboardPermissionDenied(
        session: session,
        onSignOut: onSignOut,
        deviceIdentityProvider: deviceIdentityProvider,
      );
    }

    // Collector field work is ledger-first by design. Keep the familiar old
    // route information hierarchy as the first screen after sign-in and move
    // secondary tools to a compact field navigation bar.
    if (session.role == AppRole.collector) {
      return CollectorFieldHomePage(
        session: session,
        onSignOut: onSignOut,
        collectorRouteLoader: collectorRouteLoader,
        paymentSubmissionRepository: paymentSubmissionRepository,
        deviceIdentityProvider: deviceIdentityProvider,
        collectionDeviceSequence: collectionDeviceSequence,
      );
    }

    final dashboard = RoleDashboard(
      session: session,
      onSignOut: onSignOut,
      collectorRouteLoader: collectorRouteLoader,
      paymentSubmissionRepository: paymentSubmissionRepository,
      deviceIdentityProvider: deviceIdentityProvider,
      collectionDeviceSequence: collectionDeviceSequence,
      managementDashboardOverviewRepository:
          managementDashboardOverviewRepository,
      managementAlertsAuditRepository: managementAlertsAuditRepository,
      managementEmployeeActivityRepository:
          managementEmployeeActivityRepository,
      clientLoanRepository: clientLoanRepository,
    );

    // Management, Employee, and Client each own a purpose-grouped command
    // surface. Account, notification, offline-policy, and protected
    // destinations live inside those hierarchies without duplicate overlays.
    return dashboard;
  }
}

class _CombinedWorkerWorkspace extends StatefulWidget {
  const _CombinedWorkerWorkspace({required this.collector, required this.office, required this.startInOffice});
  final Widget collector, office;
  final bool startInOffice;
  @override
  State<_CombinedWorkerWorkspace> createState() => _CombinedWorkerWorkspaceState();
}
class _CombinedWorkerWorkspaceState extends State<_CombinedWorkerWorkspace> {
  late bool _office = widget.startInOffice;
  @override
  Widget build(BuildContext context) => Column(children: [
    Material(child: SafeArea(bottom: false, child: Padding(padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6), child:
      SegmentedButton<bool>(key: const Key('employee-collector-workspace-switch'), segments: const [ButtonSegment(value: false, label: Text('Collector'), icon: Icon(Icons.route_outlined)), ButtonSegment(value: true, label: Text('Office & staff'), icon: Icon(Icons.badge_outlined))],
        selected: {_office}, onSelectionChanged: (selection) => setState(() => _office = selection.single))))),
    Expanded(child: _office ? widget.office : widget.collector),
  ]);
}

bool _hasDashboardAccess(UserSession session) {
  return switch (session.role) {
    AppRole.client => session.hasPermission('loan.self.view'),
    AppRole.collector => session.hasAllPermissions(const <String>[
      'route.view',
      'collection.create',
    ]),
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

  void _openNotifications(BuildContext context) {
    Navigator.of(context).push(
      MaterialPageRoute<void>(
        builder: (context) => NotificationCenterPage(
          session: session,
          deviceIdentityProvider: deviceIdentityProvider,
        ),
      ),
    );
  }

  void _openOfflinePolicy(BuildContext context) {
    Navigator.of(context).push(
      MaterialPageRoute<void>(
        builder: (context) => MobileOfflinePolicyPage(session: session),
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
            key: const Key('open-offline-policy'),
            tooltip: 'Offline & sync',
            onPressed: () => _openOfflinePolicy(context),
            icon: const Icon(Icons.cloud_off_outlined),
          ),
          IconButton(
            key: const Key('open-notification-center'),
            tooltip: 'Notifications',
            onPressed: () => _openNotifications(context),
            icon: const Icon(Icons.notifications_outlined),
          ),
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
                '${session.role.label} dashboard. You can still review your notifications, '
                'offline policy, profile, session, and registered devices or sign out.',
                textAlign: TextAlign.center,
              ),
            ],
          ),
        ),
      ),
    );
  }
}
