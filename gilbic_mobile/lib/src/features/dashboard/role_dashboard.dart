import 'package:flutter/material.dart';
import 'package:gilbic_mobile/src/core/auth/app_role.dart';
import 'package:gilbic_mobile/src/core/auth/user_session.dart';

class RoleDashboard extends StatelessWidget {
  const RoleDashboard({
    required this.session,
    required this.onSignOut,
    super.key,
  });

  final UserSession session;
  final Future<void> Function() onSignOut;

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
              'Gilbic foundation preview for '
              '${session.role.label.toLowerCase()} operations.',
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
                    onTap: () {
                      ScaffoldMessenger.of(context).showSnackBar(
                        SnackBar(
                          content: Text('${module.title} is planned next.'),
                        ),
                      );
                    },
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
  const _DashboardModule(this.title, this.description, this.icon);

  final String title;
  final String description;
  final IconData icon;
}

List<_DashboardModule> _modulesFor(AppRole role) {
  return switch (role) {
    AppRole.client => const [
        _DashboardModule(
          'My Loans',
          'Balances, schedules, and loan history',
          Icons.account_balance_wallet,
        ),
        _DashboardModule(
          'Payments',
          'Timeline, receipts, and payment proofs',
          Icons.receipt_long,
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
          'Assigned areas and collection clients',
          Icons.route,
        ),
        _DashboardModule(
          'Record Payment',
          'Full, partial, ADV, and PASS entries',
          Icons.payments,
        ),
        _DashboardModule(
          'Offline Sync',
          'Pending transactions and conflict status',
          Icons.sync,
        ),
        _DashboardModule(
          'End of Day',
          'Collection totals and cash accountability',
          Icons.summarize,
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
          'Requests',
          'Leave and internal service requests',
          Icons.assignment,
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
