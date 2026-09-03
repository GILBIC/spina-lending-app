import 'package:flutter/material.dart';
import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/device/device_identity.dart';
import 'package:gilbic_mobile/src/core/notifications/remittance_notification_repository.dart';
import 'package:gilbic_mobile/src/features/account/account_settings_page.dart';
import 'package:gilbic_mobile/src/features/notifications/notification_center_page.dart';
import 'package:gilbic_mobile/src/features/notifications/remittance_notifications_page.dart';
import 'package:gilbic_mobile/src/features/offline/mobile_offline_policy_page.dart';

class EmployeeDashboard extends StatelessWidget {
  const EmployeeDashboard({
    required this.session,
    required this.onSignOut,
    required this.deviceIdentityProvider,
    this.remittanceNotificationRepository,
    super.key,
  });

  final UserSession session;
  final Future<void> Function() onSignOut;
  final DeviceIdentityProvider deviceIdentityProvider;
  final RemittanceNotificationRepository? remittanceNotificationRepository;

  void _push(BuildContext context, Widget page) {
    Navigator.of(
      context,
    ).push(MaterialPageRoute<void>(builder: (context) => page));
  }

  void _openModule(BuildContext context, _EmployeeModule module) {
    if (!module.isVisibleFor(session)) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(
            'Your current server permissions do not allow ${module.title}.',
          ),
        ),
      );
      return;
    }

    if (module.availability != _EmployeeModuleAvailability.available) {
      final message = switch (module.availability) {
        _EmployeeModuleAvailability.notAvailableYet =>
          '${module.title} is not available yet. No official Employee record will be changed.',
        _EmployeeModuleAvailability.permissionAssignedNotConnected =>
          '${module.title} is assigned by permission, but its protected Employee workflow is not connected yet.',
        _EmployeeModuleAvailability.available => '',
      };
      ScaffoldMessenger.of(
        context,
      ).showSnackBar(SnackBar(content: Text(message)));
      return;
    }

    final page = switch (module.action) {
      _EmployeeAction.notifications => NotificationCenterPage(
        session: session,
        deviceIdentityProvider: deviceIdentityProvider,
      ),
      _EmployeeAction.account => AccountSettingsPage(
        session: session,
        onSignOut: onSignOut,
        deviceIdentityProvider: deviceIdentityProvider,
      ),
      _EmployeeAction.offlinePolicy => MobileOfflinePolicyPage(
        session: session,
      ),
      _EmployeeAction.remittance => RemittanceNotificationsPage(
        session: session,
        deviceIdentityProvider: deviceIdentityProvider,
        repository: remittanceNotificationRepository,
      ),
      _EmployeeAction.attendance ||
      _EmployeeAction.payroll ||
      _EmployeeAction.tasks ||
      _EmployeeAction.leaveRequests ||
      _EmployeeAction.clientSupport ||
      _EmployeeAction.accounting => null,
    };
    if (page != null) _push(context, page);
  }

  @override
  Widget build(BuildContext context) {
    final sections = _employeeSections
        .map((section) => section.visibleFor(session))
        .toList(growable: false);
    return Scaffold(
      appBar: AppBar(
        title: const Text('Employee Dashboard'),
        actions: [
          IconButton(
            tooltip: 'Sign out',
            onPressed: onSignOut,
            icon: const Icon(Icons.logout),
          ),
        ],
      ),
      body: SafeArea(
        child: ListView(
          key: const Key('employee-dashboard-list'),
          padding: const EdgeInsets.fromLTRB(16, 16, 16, 28),
          children: [
            Text(
              'Welcome, ${session.displayName}',
              style: Theme.of(context).textTheme.headlineSmall,
            ),
            const SizedBox(height: 6),
            Text(
              'Your personal records and office tools stay separate. Office functions appear only when the server assigns their exact permission.',
              style: Theme.of(context).textTheme.bodyMedium,
            ),
            const SizedBox(height: 22),
            for (var index = 0; index < sections.length; index++) ...[
              _EmployeeSectionCard(
                section: sections[index],
                onOpen: (module) => _openModule(context, module),
              ),
              if (index != sections.length - 1) const SizedBox(height: 20),
            ],
          ],
        ),
      ),
    );
  }
}

class _EmployeeSectionCard extends StatelessWidget {
  const _EmployeeSectionCard({required this.section, required this.onOpen});

  final _EmployeeSection section;
  final ValueChanged<_EmployeeModule> onOpen;

  @override
  Widget build(BuildContext context) {
    return Column(
      key: Key(section.keyName),
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Padding(
          padding: const EdgeInsets.symmetric(horizontal: 4),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                section.title,
                style: Theme.of(context).textTheme.titleLarge,
              ),
              const SizedBox(height: 3),
              Text(
                section.description,
                style: Theme.of(context).textTheme.bodyMedium,
              ),
            ],
          ),
        ),
        const SizedBox(height: 8),
        if (section.modules.isEmpty)
          Card(
            child: Padding(
              padding: const EdgeInsets.all(14),
              child: Text(
                section.emptyMessage ?? 'No items are available.',
                style: Theme.of(context).textTheme.bodyMedium,
              ),
            ),
          )
        else
          for (final module in section.modules)
            Padding(
              padding: const EdgeInsets.only(bottom: 8),
              child: _EmployeeModuleRow(
                module: module,
                onTap: () => onOpen(module),
              ),
            ),
      ],
    );
  }
}

class _EmployeeModuleRow extends StatelessWidget {
  const _EmployeeModuleRow({required this.module, required this.onTap});

  final _EmployeeModule module;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final colors = Theme.of(context).colorScheme;
    final available =
        module.availability == _EmployeeModuleAvailability.available;
    final statusColor = available ? colors.primary : colors.onSurfaceVariant;
    return Card(
      margin: EdgeInsets.zero,
      clipBehavior: Clip.antiAlias,
      child: Semantics(
        button: true,
        label: '${module.title}. ${module.description}. ${module.statusLabel}',
        child: InkWell(
          key: Key(module.action.keyName),
          onTap: onTap,
          child: Padding(
            padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
            child: Row(
              children: [
                Container(
                  width: 36,
                  height: 36,
                  decoration: BoxDecoration(
                    color: available
                        ? colors.primaryContainer
                        : colors.surfaceContainerHighest,
                    borderRadius: BorderRadius.circular(11),
                  ),
                  child: Icon(
                    module.icon,
                    size: 20,
                    color: available
                        ? colors.onPrimaryContainer
                        : colors.onSurfaceVariant,
                  ),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        module.title,
                        style: Theme.of(context).textTheme.titleSmall,
                      ),
                      const SizedBox(height: 2),
                      Text(
                        module.description,
                        style: Theme.of(context).textTheme.bodySmall,
                      ),
                      const SizedBox(height: 4),
                      Text(
                        module.statusLabel,
                        style: Theme.of(context).textTheme.labelSmall?.copyWith(
                          color: statusColor,
                          fontWeight: FontWeight.w700,
                        ),
                      ),
                    ],
                  ),
                ),
                const SizedBox(width: 8),
                Icon(
                  available ? Icons.chevron_right : Icons.info_outline,
                  size: 20,
                  color: colors.onSurfaceVariant,
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

enum _EmployeeAction {
  attendance('employee-attendance'),
  payroll('employee-payroll'),
  tasks('employee-tasks'),
  leaveRequests('employee-leave'),
  remittance('employee-remittance'),
  clientSupport('employee-client-support'),
  accounting('employee-accounting'),
  notifications('employee-notifications'),
  account('employee-account'),
  offlinePolicy('employee-offline');

  const _EmployeeAction(this.keyName);

  final String keyName;
}

enum _EmployeeModuleAvailability {
  available,
  notAvailableYet,
  permissionAssignedNotConnected,
}

class _EmployeeModule {
  const _EmployeeModule(
    this.title,
    this.description,
    this.icon, {
    required this.action,
    required this.availability,
    this.requiredPermission,
  });

  final String title;
  final String description;
  final IconData icon;
  final _EmployeeAction action;
  final _EmployeeModuleAvailability availability;
  final String? requiredPermission;

  String get statusLabel => switch (availability) {
    _EmployeeModuleAvailability.available => 'Available now',
    _EmployeeModuleAvailability.notAvailableYet => 'Not available yet',
    _EmployeeModuleAvailability.permissionAssignedNotConnected =>
      'Employee workflow not connected yet',
  };

  bool isVisibleFor(UserSession session) {
    final permission = requiredPermission;
    return permission == null || session.hasPermission(permission);
  }
}

class _EmployeeSection {
  const _EmployeeSection({
    required this.keyName,
    required this.title,
    required this.description,
    required this.modules,
    this.emptyMessage,
  });

  final String keyName;
  final String title;
  final String description;
  final List<_EmployeeModule> modules;
  final String? emptyMessage;

  _EmployeeSection visibleFor(UserSession session) => _EmployeeSection(
    keyName: keyName,
    title: title,
    description: description,
    modules: modules
        .where((module) => module.isVisibleFor(session))
        .toList(growable: false),
    emptyMessage: emptyMessage,
  );
}

const _employeeSections = <_EmployeeSection>[
  _EmployeeSection(
    keyName: 'employee-section-workday',
    title: 'My workday',
    description: 'Attendance and assigned work stay in one personal area.',
    modules: <_EmployeeModule>[
      _EmployeeModule(
        'Attendance',
        'Time records and attendance history',
        Icons.schedule_outlined,
        action: _EmployeeAction.attendance,
        availability: _EmployeeModuleAvailability.notAvailableYet,
      ),
      _EmployeeModule(
        'Tasks & work items',
        'Assigned work, priorities, and completion status',
        Icons.task_alt_outlined,
        action: _EmployeeAction.tasks,
        availability: _EmployeeModuleAvailability.notAvailableYet,
      ),
    ],
  ),
  _EmployeeSection(
    keyName: 'employee-section-pay-requests',
    title: 'Pay & requests',
    description: 'Private payroll records and Employee requests stay separate.',
    modules: <_EmployeeModule>[
      _EmployeeModule(
        'Payroll & payslips',
        'Your payroll summaries and payslip history',
        Icons.price_check_outlined,
        action: _EmployeeAction.payroll,
        availability: _EmployeeModuleAvailability.notAvailableYet,
      ),
      _EmployeeModule(
        'Leave & requests',
        'Submit and review your own Employee requests',
        Icons.event_available_outlined,
        action: _EmployeeAction.leaveRequests,
        availability: _EmployeeModuleAvailability.notAvailableYet,
      ),
    ],
  ),
  _EmployeeSection(
    keyName: 'employee-section-office',
    title: 'Office functions',
    description:
        'Operational tools appear only when your current server permissions assign them.',
    emptyMessage:
        'No office functions are assigned by your current server permissions.',
    modules: <_EmployeeModule>[
      _EmployeeModule(
        'Remittance requests',
        'Review authorized cash handovers and custody updates',
        Icons.move_to_inbox_outlined,
        action: _EmployeeAction.remittance,
        availability: _EmployeeModuleAvailability.available,
        requiredPermission: 'remittance.view',
      ),
      _EmployeeModule(
        'Client support',
        'Handle assigned borrower inquiries and follow-ups',
        Icons.support_agent_outlined,
        action: _EmployeeAction.clientSupport,
        availability:
            _EmployeeModuleAvailability.permissionAssignedNotConnected,
        requiredPermission: 'support.manage',
      ),
      _EmployeeModule(
        'Accounting & bookkeeping',
        'Prepare authorized records without gaining posting authority',
        Icons.menu_book_outlined,
        action: _EmployeeAction.accounting,
        availability:
            _EmployeeModuleAvailability.permissionAssignedNotConnected,
        requiredPermission: 'accounting.view',
      ),
    ],
  ),
  _EmployeeSection(
    keyName: 'employee-section-updates',
    title: 'Updates & account',
    description: 'Review notices, your own profile, device, and connectivity.',
    modules: <_EmployeeModule>[
      _EmployeeModule(
        'Notifications',
        'Assigned updates, approvals, and custody changes',
        Icons.notifications_outlined,
        action: _EmployeeAction.notifications,
        availability: _EmployeeModuleAvailability.available,
      ),
      _EmployeeModule(
        'My account & devices',
        'Profile, current session, registered devices, and sign-out controls',
        Icons.account_circle_outlined,
        action: _EmployeeAction.account,
        availability: _EmployeeModuleAvailability.available,
      ),
      _EmployeeModule(
        'Connectivity & offline policy',
        'See which Employee information and actions require the live server',
        Icons.cloud_off_outlined,
        action: _EmployeeAction.offlinePolicy,
        availability: _EmployeeModuleAvailability.available,
      ),
    ],
  ),
];
