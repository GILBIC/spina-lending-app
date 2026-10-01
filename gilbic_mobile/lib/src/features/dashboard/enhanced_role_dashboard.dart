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
import 'package:gilbic_mobile/src/features/management/management_dashboard.dart';
import 'package:gilbic_mobile/src/features/client/client_dashboard.dart';
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
    final roles = session.workspaceRoles
        .where((role) => _hasDashboardAccess(session, role))
        .toList();
    if (roles.isEmpty) {
      return _DashboardPermissionDenied(
        session: session,
        onSignOut: onSignOut,
        deviceIdentityProvider: deviceIdentityProvider,
      );
    }
    if (roles.length == 1) return _workspace(roles.single);
    return _CombinedWorkerWorkspace(
      key: ValueKey(session.userId),
      roles: roles,
      preferredRole: session.role,
      workspace: _workspace,
    );
  }

  // Workspace selection is presentation only: every destination receives the
  // original authenticated session and its unchanged server permissions.
  Widget _workspace(AppRole role) => switch (role) {
    AppRole.collector => CollectorFieldHomePage(
      session: session,
      onSignOut: onSignOut,
      collectorRouteLoader: collectorRouteLoader,
      paymentSubmissionRepository: paymentSubmissionRepository,
      deviceIdentityProvider: deviceIdentityProvider,
      collectionDeviceSequence: collectionDeviceSequence,
    ),
    AppRole.employee => EmployeeDashboard(
      session: session,
      onSignOut: onSignOut,
      deviceIdentityProvider: deviceIdentityProvider,
    ),
    AppRole.management => ManagementDashboard(
      session: session,
      onSignOut: onSignOut,
      paymentSubmissionRepository: paymentSubmissionRepository,
      deviceIdentityProvider: deviceIdentityProvider,
      collectionDeviceSequence: collectionDeviceSequence,
      overviewRepository: managementDashboardOverviewRepository,
      alertsAuditRepository: managementAlertsAuditRepository,
      employeeActivityRepository: managementEmployeeActivityRepository,
    ),
    AppRole.client => ClientDashboard(
      session: session,
      onSignOut: onSignOut,
      deviceIdentityProvider: deviceIdentityProvider,
      loanRepository: clientLoanRepository,
    ),
  };
}

class _CombinedWorkerWorkspace extends StatefulWidget {
  const _CombinedWorkerWorkspace({
    required this.roles,
    required this.preferredRole,
    required this.workspace,
    super.key,
  });
  final List<AppRole> roles;
  final AppRole preferredRole;
  final Widget Function(AppRole) workspace;
  @override
  State<_CombinedWorkerWorkspace> createState() =>
      _CombinedWorkerWorkspaceState();
}

class _CombinedWorkerWorkspaceState extends State<_CombinedWorkerWorkspace> {
  late AppRole _selected = _initialRole;
  AppRole get _initialRole => widget.roles.contains(widget.preferredRole)
      ? widget.preferredRole
      : widget.roles.first;

  @override
  void didUpdateWidget(covariant _CombinedWorkerWorkspace oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (!widget.roles.contains(_selected)) _selected = _initialRole;
  }

  @override
  Widget build(BuildContext context) => Column(
    children: [
      Material(
        child: SafeArea(
          bottom: false,
          child: Padding(
            padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
            child: SingleChildScrollView(
              scrollDirection: Axis.horizontal,
              child: SegmentedButton<AppRole>(
                key: const Key('employee-collector-workspace-switch'),
                segments: [
                  for (final role in widget.roles)
                    ButtonSegment(
                      value: role,
                      label: Text(
                        role == AppRole.employee
                            ? 'Office & staff'
                            : role.label,
                      ),
                      icon: Icon(switch (role) {
                        AppRole.collector => Icons.route_outlined,
                        AppRole.employee => Icons.badge_outlined,
                        AppRole.management => Icons.dashboard_outlined,
                        AppRole.client => Icons.person_outline,
                      }),
                    ),
                ],
                selected: {_selected},
                onSelectionChanged: (selection) =>
                    setState(() => _selected = selection.single),
              ),
            ),
          ),
        ),
      ),
      Expanded(child: widget.workspace(_selected)),
    ],
  );
}

bool _hasDashboardAccess(UserSession session, AppRole role) {
  return switch (role) {
    AppRole.client => session.hasPermission('loan.self.view'),
    AppRole.collector => session.hasPermission('route.view'),
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
