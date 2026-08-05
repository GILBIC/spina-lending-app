import 'package:flutter/material.dart';
import 'package:gilbic_mobile/src/core/auth/app_role.dart';
import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/collector/collector_route_loader.dart';
import 'package:gilbic_mobile/src/core/device/device_identity.dart';
import 'package:gilbic_mobile/src/core/payments/collection_device_sequence.dart';
import 'package:gilbic_mobile/src/core/payments/payment_submission_repository.dart';
import 'package:gilbic_mobile/src/features/client/client_loans_page.dart';
import 'package:gilbic_mobile/src/features/client/client_payments_page.dart';
import 'package:gilbic_mobile/src/features/collector/collector_remittance_page.dart';
import 'package:gilbic_mobile/src/features/collector/collector_route_page.dart';
import 'package:gilbic_mobile/src/features/collector/cross_collector_remittance_page.dart';
import 'package:gilbic_mobile/src/features/collector/other_area_collection_page.dart';
import 'package:gilbic_mobile/src/features/management/client_registration_approvals_page.dart';
import 'package:gilbic_mobile/src/features/management/management_collection_void_page.dart';
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

  void _openModule(BuildContext context, _DashboardModule module) {
    final collectorRouteAction =
        module.action == 'daily-route' || module.action == 'record-payment';
    if (session.role == AppRole.collector && collectorRouteAction) {
      Navigator.of(context).push(
        MaterialPageRoute<void>(
          builder: (context) => CollectorRoutePage(
            session: session,
            loader: collectorRouteLoader,
            paymentRepository: paymentSubmissionRepository,
            deviceIdentityProvider: deviceIdentityProvider,
            deviceSequence: collectionDeviceSequence,
          ),
        ),
      );
      return;
    }

    if ((session.role == AppRole.collector &&
            module.action == 'other-area-payment') ||
        (session.role == AppRole.management &&
            module.action == 'management-direct-payment')) {
      Navigator.of(context).push(
        MaterialPageRoute<void>(
          builder: (context) => OtherAreaCollectionPage(
            session: session,
            paymentRepository: paymentSubmissionRepository,
            deviceIdentityProvider: deviceIdentityProvider,
            deviceSequence: collectionDeviceSequence,
          ),
        ),
      );
      return;
    }

    if (session.role == AppRole.collector && module.action == 'remittance') {
      Navigator.of(context).push(
        MaterialPageRoute<void>(
          builder: (context) => CollectorRemittancePage(
            session: session,
            deviceIdentityProvider: deviceIdentityProvider,
          ),
        ),
      );
      return;
    }

    if (session.role == AppRole.collector &&
        module.action == 'assigned-collector-remittance') {
      Navigator.of(context).push(
        MaterialPageRoute<void>(
          builder: (context) => CrossCollectorRemittancePage(
            session: session,
            deviceIdentityProvider: deviceIdentityProvider,
          ),
        ),
      );
      return;
    }

    if (session.role == AppRole.client && module.action == 'my-loans') {
      Navigator.of(context).push(
        MaterialPageRoute<void>(
          builder: (context) => ClientLoansPage(
            session: session,
            deviceIdentityProvider: deviceIdentityProvider,
          ),
        ),
      );
      return;
    }

    if (session.role == AppRole.client && module.action == 'payments') {
      Navigator.of(context).push(
        MaterialPageRoute<void>(
          builder: (context) => ClientPaymentsPage(
            session: session,
            deviceIdentityProvider: deviceIdentityProvider,
          ),
        ),
      );
      return;
    }

    if (module.action == 'payment-updates') {
      Navigator.of(context).push(
        MaterialPageRoute<void>(
          builder: (context) => ActivityNotificationsPage(
            session: session,
            deviceIdentityProvider: deviceIdentityProvider,
          ),
        ),
      );
      return;
    }

    if (module.action == 'remittance-notifications' &&
        (session.role == AppRole.collector ||
            session.role == AppRole.employee ||
            session.role == AppRole.management)) {
      Navigator.of(context).push(
        MaterialPageRoute<void>(
          builder: (context) => RemittanceNotificationsPage(
            session: session,
            deviceIdentityProvider: deviceIdentityProvider,
          ),
        ),
      );
      return;
    }

    if (session.role == AppRole.management &&
        module.action == 'client-registration-approvals') {
      Navigator.of(context).push(
        MaterialPageRoute<void>(
          builder: (context) => ClientRegistrationApprovalsPage(
            session: session,
            deviceIdentityProvider: deviceIdentityProvider,
          ),
        ),
      );
      return;
    }

    if (session.role == AppRole.management &&
        module.action == 'management-void-payment') {
      Navigator.of(context).push(
        MaterialPageRoute<void>(
          builder: (context) => ManagementCollectionVoidPage(
            session: session,
            deviceIdentityProvider: deviceIdentityProvider,
          ),
        ),
      );
      return;
    }

    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(content: Text('${module.title} is planned next.')),
    );
  }

  @override
  Widget build(BuildContext context) {
    final modules = _modulesFor(session.role);
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
  const _DashboardModule(this.title, this.description, this.icon, {this.action});

  final String title;
  final String description;
  final IconData icon;
  final String? action;
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
        ),
        _DashboardModule(
          'Support',
          'Notices, corrections, and assistance',
          Icons.support_agent,
        ),
      ],
    AppRole.collector => const [
        _DashboardModule(
          'Daily Route',
          'Compact online collection ledger',
          Icons.route,
          action: 'daily-route',
        ),
        _DashboardModule(
          'Record Payment',
          'Open the route and record assigned collections',
          Icons.payments,
          action: 'record-payment',
        ),
        _DashboardModule(
          'Other Area Payment',
          'Search a client who paid a different collector',
          Icons.person_search,
          action: 'other-area-payment',
        ),
        _DashboardModule(
          'Management Remittance',
          'Submit regular route cash to authorized staff',
          Icons.account_balance_outlined,
          action: 'remittance',
        ),
        _DashboardModule(
          'Assigned Collector Remittance',
          'Send only other-area payments to their route owner',
          Icons.compare_arrows,
          action: 'assigned-collector-remittance',
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
        ),
      ],
    AppRole.management => const [
        _DashboardModule(
          'Loan Management',
          'Products, approvals, releases, and renewals',
          Icons.account_balance,
        ),
        _DashboardModule(
          'Loan Operations',
          'Collections, corrections, and portfolio monitoring',
          Icons.insights,
        ),
        _DashboardModule(
          'Direct Payment Entry',
          'Record a client payment made directly to Management',
          Icons.point_of_sale,
          action: 'management-direct-payment',
        ),
        _DashboardModule(
          'Void Incorrect Payment',
          'Reverse an unlocked wrong payment with a permanent audit trail',
          Icons.block,
          action: 'management-void-payment',
        ),
        _DashboardModule(
          'Notifications',
          'Accept assigned remittances after receiving the cash',
          Icons.notifications_active,
          action: 'remittance-notifications',
        ),
        _DashboardModule(
          'Client Portal Approvals',
          'Approve registrations and link borrower records',
          Icons.how_to_reg,
          action: 'client-registration-approvals',
        ),
        _DashboardModule(
          'Financial Accounting',
          'Ledgers, journals, and financial reports',
          Icons.calculate,
        ),
        _DashboardModule(
          'Billing & Taxation',
          'Billing records and tax schedules',
          Icons.request_quote,
        ),
        _DashboardModule(
          'Risk & Compliance',
          'KYC, alerts, incidents, and audit reviews',
          Icons.verified_user,
        ),
        _DashboardModule(
          'Administration',
          'Users, roles, devices, and settings',
          Icons.admin_panel_settings,
        ),
      ],
  };
}
