import 'package:flutter/material.dart';
import 'package:gilbic_mobile/src/core/auth/app_role.dart';
import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/collector/collector_route_loader.dart';
import 'package:gilbic_mobile/src/core/device/device_identity.dart';
import 'package:gilbic_mobile/src/core/payments/collection_device_sequence.dart';
import 'package:gilbic_mobile/src/core/payments/payment_submission_repository.dart';
import 'package:gilbic_mobile/src/features/client/client_loans_page.dart';
import 'package:gilbic_mobile/src/features/client/client_payments_page.dart';
import 'package:gilbic_mobile/src/features/client/client_renewal_page.dart';
import 'package:gilbic_mobile/src/features/client/client_support_page.dart';
import 'package:gilbic_mobile/src/features/collector/collector_remittance_page.dart';
import 'package:gilbic_mobile/src/features/collector/collector_route_page.dart';
import 'package:gilbic_mobile/src/features/collector/cross_collector_remittance_page.dart';
import 'package:gilbic_mobile/src/features/collector/delegated_area_access_page.dart';
import 'package:gilbic_mobile/src/features/collector/other_area_collection_page.dart';
import 'package:gilbic_mobile/src/features/management/management_dashboard.dart';
import 'package:gilbic_mobile/src/features/notifications/activity_notifications_page.dart';
import 'package:gilbic_mobile/src/features/notifications/remittance_notifications_page.dart';

class RoleDashboard extends StatelessWidget {
  const RoleDashboard({
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

  void _push(BuildContext context, Widget page) {
    Navigator.of(
      context,
    ).push(MaterialPageRoute<void>(builder: (context) => page));
  }

  void _openModule(BuildContext context, _DashboardModule module) {
    if (!module.isAvailableFor(session)) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(
            'Your current server permissions do not allow ${module.title}.',
          ),
        ),
      );
      return;
    }

    final action = module.action;
    if (session.role == AppRole.collector &&
        (action == 'daily-route' || action == 'record-payment')) {
      _push(
        context,
        CollectorRoutePage(
          session: session,
          loader: collectorRouteLoader,
          paymentRepository: paymentSubmissionRepository,
          deviceIdentityProvider: deviceIdentityProvider,
          deviceSequence: collectionDeviceSequence,
        ),
      );
      return;
    }
    if (session.role == AppRole.collector &&
        action == 'delegated-area-access') {
      _push(
        context,
        DelegatedAreaAccessPage(
          session: session,
          deviceIdentityProvider: deviceIdentityProvider,
        ),
      );
      return;
    }
    if (session.role == AppRole.collector && action == 'other-area-payment') {
      _push(
        context,
        OtherAreaCollectionPage(
          session: session,
          paymentRepository: paymentSubmissionRepository,
          deviceIdentityProvider: deviceIdentityProvider,
          deviceSequence: collectionDeviceSequence,
        ),
      );
      return;
    }
    if (session.role == AppRole.collector && action == 'remittance') {
      _push(
        context,
        CollectorRemittancePage(
          session: session,
          deviceIdentityProvider: deviceIdentityProvider,
        ),
      );
      return;
    }
    if (session.role == AppRole.collector &&
        action == 'assigned-collector-remittance') {
      _push(
        context,
        CrossCollectorRemittancePage(
          session: session,
          deviceIdentityProvider: deviceIdentityProvider,
        ),
      );
      return;
    }
    if (session.role == AppRole.client && action == 'my-loans') {
      _push(
        context,
        ClientLoansPage(
          session: session,
          deviceIdentityProvider: deviceIdentityProvider,
        ),
      );
      return;
    }
    if (session.role == AppRole.client && action == 'payments') {
      _push(
        context,
        ClientPaymentsPage(
          session: session,
          deviceIdentityProvider: deviceIdentityProvider,
        ),
      );
      return;
    }
    if (session.role == AppRole.client && action == 'renewal') {
      _push(
        context,
        ClientRenewalPage(
          session: session,
          deviceIdentityProvider: deviceIdentityProvider,
        ),
      );
      return;
    }
    if (session.role == AppRole.client && action == 'support') {
      _push(
        context,
        ClientSupportPage(
          session: session,
          deviceIdentityProvider: deviceIdentityProvider,
        ),
      );
      return;
    }
    if (action == 'payment-updates') {
      _push(
        context,
        ActivityNotificationsPage(
          session: session,
          deviceIdentityProvider: deviceIdentityProvider,
        ),
      );
      return;
    }
    if (action == 'remittance-notifications' &&
        (session.role == AppRole.collector ||
            session.role == AppRole.employee)) {
      _push(
        context,
        RemittanceNotificationsPage(
          session: session,
          deviceIdentityProvider: deviceIdentityProvider,
        ),
      );
      return;
    }
    ScaffoldMessenger.of(
      context,
    ).showSnackBar(SnackBar(content: Text('${module.title} is planned next.')));
  }

  @override
  Widget build(BuildContext context) {
    if (session.role == AppRole.management) {
      return ManagementDashboard(
        session: session,
        onSignOut: onSignOut,
        paymentSubmissionRepository: paymentSubmissionRepository,
        deviceIdentityProvider: deviceIdentityProvider,
        collectionDeviceSequence: collectionDeviceSequence,
      );
    }

    final modules = _modulesFor(
      session.role,
    ).where((module) => module.isAvailableFor(session)).toList(growable: false);
    return Scaffold(
      appBar: AppBar(
        title: Text('${session.role.label} Dashboard'),
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
          padding: const EdgeInsets.all(20),
          children: [
            Text(
              'Welcome, ${session.displayName}',
              style: Theme.of(context).textTheme.headlineSmall,
            ),
            const SizedBox(height: 6),
            Text(
              '${session.rawRole} account • permissions enforced by SPINA',
              style: Theme.of(context).textTheme.bodyLarge,
            ),
            const SizedBox(height: 24),
            GridView.builder(
              shrinkWrap: true,
              physics: const NeverScrollableScrollPhysics(),
              itemCount: modules.length,
              gridDelegate: const SliverGridDelegateWithMaxCrossAxisExtent(
                maxCrossAxisExtent: 280,
                mainAxisExtent: 176,
                crossAxisSpacing: 12,
                mainAxisSpacing: 12,
              ),
              itemBuilder: (context, index) {
                final module = modules[index];
                return Card(
                  clipBehavior: Clip.antiAlias,
                  child: InkWell(
                    key: module.action == null ? null : Key(module.action!),
                    onTap: () => _openModule(context, module),
                    child: Padding(
                      padding: const EdgeInsets.all(18),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Icon(module.icon, size: 32),
                          const SizedBox(height: 12),
                          Text(
                            module.title,
                            maxLines: 2,
                            overflow: TextOverflow.ellipsis,
                            style: Theme.of(context).textTheme.titleMedium,
                          ),
                          const SizedBox(height: 4),
                          Expanded(
                            child: Align(
                              alignment: Alignment.topLeft,
                              child: Text(
                                module.description,
                                maxLines: 2,
                                overflow: TextOverflow.ellipsis,
                              ),
                            ),
                          ),
                        ],
                      ),
                    ),
                  ),
                );
              },
            ),
          ],
        ),
      ),
    );
  }
}

class _DashboardModule {
  const _DashboardModule(
    this.title,
    this.description,
    this.icon, {
    this.action,
    this.requiredPermissions = const <String>[],
  });

  final String title;
  final String description;
  final IconData icon;
  final String? action;
  final List<String> requiredPermissions;

  bool isAvailableFor(UserSession session) {
    return requiredPermissions.isEmpty ||
        requiredPermissions.every(session.hasPermission);
  }
}

List<_DashboardModule> _modulesFor(AppRole role) {
  return switch (role) {
    AppRole.client => const [
      _DashboardModule(
        'My Loans',
        'Balances, schedules, and loan history',
        Icons.account_balance_wallet,
        action: 'my-loans',
      ),
      _DashboardModule(
        'Payments',
        'Timeline, receipts, and payment proofs',
        Icons.receipt_long,
        action: 'payments',
      ),
      _DashboardModule(
        'Payment Updates',
        'See who posted, remitted, and accepted your payment',
        Icons.notifications_active,
        action: 'payment-updates',
      ),
      _DashboardModule(
        'Renewal',
        'Submit and monitor renewal requests',
        Icons.autorenew,
        action: 'renewal',
      ),
      _DashboardModule(
        'Support',
        'Notices, corrections, and assistance',
        Icons.support_agent,
        action: 'support',
      ),
    ],
    AppRole.collector => const [
      _DashboardModule(
        'Daily Route',
        'Compact online collection ledger',
        Icons.route,
        action: 'daily-route',
        requiredPermissions: <String>['route.view'],
      ),
      _DashboardModule(
        'Record Payment',
        'Open the route and record assigned collections',
        Icons.payments,
        action: 'record-payment',
        requiredPermissions: <String>['route.view', 'collection.create'],
      ),
      _DashboardModule(
        'Temporary Area Access',
        'Request, approve, review, or revoke Collector area access',
        Icons.add_location_alt_outlined,
        action: 'delegated-area-access',
        requiredPermissions: <String>['delegated_area.view'],
      ),
      _DashboardModule(
        'Other-Area Work',
        "Today's clients inside currently approved temporary areas",
        Icons.person_search,
        action: 'other-area-payment',
        requiredPermissions: <String>[
          'delegated_area.view',
          'collection.create',
        ],
      ),
      _DashboardModule(
        'Management Remittance',
        'Submit regular route cash to authorized staff',
        Icons.account_balance_outlined,
        action: 'remittance',
        requiredPermissions: <String>['remittance.create'],
      ),
      _DashboardModule(
        'Assigned Collector Remittance',
        'Send only other-area payments to their route owner',
        Icons.compare_arrows,
        action: 'assigned-collector-remittance',
        requiredPermissions: <String>['remittance.create'],
      ),
      _DashboardModule(
        'Payment Updates',
        'See other-collector posts and cash-custody updates',
        Icons.receipt_long,
        action: 'payment-updates',
      ),
      _DashboardModule(
        'Remittance Requests',
        'Review and accept remittances sent to your assigned route',
        Icons.notifications_active,
        action: 'remittance-notifications',
        requiredPermissions: <String>['remittance.view'],
      ),
    ],
    AppRole.employee => const [
      _DashboardModule(
        'Attendance',
        'Time records and attendance history',
        Icons.schedule,
      ),
      _DashboardModule(
        'Payroll',
        'Payslips and payroll summaries',
        Icons.price_check,
      ),
      _DashboardModule(
        'Tasks',
        'Assigned work and announcements',
        Icons.task_alt,
      ),
      _DashboardModule(
        'Notifications',
        'Accept assigned remittances after receiving the cash',
        Icons.notifications_active,
        action: 'remittance-notifications',
        requiredPermissions: <String>['remittance.view'],
      ),
    ],
    AppRole.management => const <_DashboardModule>[],
  };
}
