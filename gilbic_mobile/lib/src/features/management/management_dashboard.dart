import 'package:flutter/material.dart';
import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/device/device_identity.dart';
import 'package:gilbic_mobile/src/core/payments/collection_device_sequence.dart';
import 'package:gilbic_mobile/src/core/payments/payment_submission_repository.dart';
import 'package:gilbic_mobile/src/features/account/account_settings_page.dart';
import 'package:gilbic_mobile/src/features/collector/other_area_collection_page.dart';
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
import 'package:gilbic_mobile/src/features/notifications/activity_notifications_page.dart';
import 'package:gilbic_mobile/src/features/notifications/remittance_notifications_page.dart';
import 'package:gilbic_mobile/src/features/offline/mobile_offline_policy_page.dart';

class ManagementDashboard extends StatelessWidget {
  const ManagementDashboard({
    required this.session,
    required this.onSignOut,
    required this.paymentSubmissionRepository,
    required this.deviceIdentityProvider,
    required this.collectionDeviceSequence,
    super.key,
  });

  final UserSession session;
  final Future<void> Function() onSignOut;
  final PaymentSubmissionRepository paymentSubmissionRepository;
  final DeviceIdentityProvider deviceIdentityProvider;
  final CollectionDeviceSequence collectionDeviceSequence;

  void _push(BuildContext context, Widget page) {
    Navigator.of(
      context,
    ).push(MaterialPageRoute<void>(builder: (context) => page));
  }

  void _openModule(BuildContext context, _ManagementModule module) {
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

    final page = switch (module.action) {
      _ManagementAction.alertsActivity => ActivityNotificationsPage(
        session: session,
        deviceIdentityProvider: deviceIdentityProvider,
      ),
      _ManagementAction.myAccountDevices => AccountSettingsPage(
        session: session,
        onSignOut: onSignOut,
        deviceIdentityProvider: deviceIdentityProvider,
      ),
      _ManagementAction.offlinePolicy => MobileOfflinePolicyPage(
        session: session,
      ),
      _ManagementAction.loans => ManagementLoanPortfolioPage(
        session: session,
        deviceIdentityProvider: deviceIdentityProvider,
      ),
      _ManagementAction.contractCollectionActivation =>
        ManagementContractCollectionActivationPage(
          session: session,
          deviceIdentityProvider: deviceIdentityProvider,
        ),
      _ManagementAction.noCollection => ManagementNoCollectionPage(
        session: session,
        deviceIdentityProvider: deviceIdentityProvider,
      ),
      _ManagementAction.loanOperations => ManagementLoanOperationsPage(
        session: session,
        deviceIdentityProvider: deviceIdentityProvider,
      ),
      _ManagementAction.remittanceNotifications => RemittanceNotificationsPage(
        session: session,
        deviceIdentityProvider: deviceIdentityProvider,
      ),
      _ManagementAction.directPayment => OtherAreaCollectionPage(
        session: session,
        paymentRepository: paymentSubmissionRepository,
        deviceIdentityProvider: deviceIdentityProvider,
        deviceSequence: collectionDeviceSequence,
      ),
      _ManagementAction.voidPayment => ManagementCollectionVoidPage(
        session: session,
        deviceIdentityProvider: deviceIdentityProvider,
      ),
      _ManagementAction.renewals => ManagementRenewalRequestsPage(
        session: session,
        deviceIdentityProvider: deviceIdentityProvider,
      ),
      _ManagementAction.support => ManagementSupportRequestsPage(
        session: session,
        deviceIdentityProvider: deviceIdentityProvider,
      ),
      _ManagementAction.clientRegistrationApprovals =>
        ClientRegistrationApprovalsPage(
          session: session,
          deviceIdentityProvider: deviceIdentityProvider,
        ),
      _ManagementAction.financialAccounting =>
        ManagementFinancialAccountingPage(
          session: session,
          deviceIdentityProvider: deviceIdentityProvider,
        ),
      _ManagementAction.eclOutcomeReview => ManagementEclOutcomeReviewPage(
        session: session,
        deviceIdentityProvider: deviceIdentityProvider,
      ),
      _ManagementAction.accountingMeasurement =>
        ManagementAccountingMeasurementPage(
          session: session,
          deviceIdentityProvider: deviceIdentityProvider,
        ),
      _ManagementAction.openingBalanceWorkbook =>
        ManagementOpeningBalanceWorkbookPage(
          session: session,
          deviceIdentityProvider: deviceIdentityProvider,
        ),
      _ManagementAction.openingBalanceJournal =>
        ManagementOpeningBalanceJournalPage(
          session: session,
          deviceIdentityProvider: deviceIdentityProvider,
        ),
      _ManagementAction.generalJournal => ManagementGeneralJournalLauncherPage(
        session: session,
        deviceIdentityProvider: deviceIdentityProvider,
      ),
      _ManagementAction.financialStatements =>
        ManagementFinancialStatementsPage(
          session: session,
          deviceIdentityProvider: deviceIdentityProvider,
        ),
    };
    _push(context, page);
  }

  @override
  Widget build(BuildContext context) {
    final sections = _managementSections
        .map((section) => section.availableFor(session))
        .where((section) => section.modules.isNotEmpty)
        .toList(growable: false);

    return Scaffold(
      appBar: AppBar(
        title: const Text('Management'),
        actions: [
          IconButton(
            tooltip: 'Sign out',
            onPressed: onSignOut,
            icon: const Icon(Icons.logout),
          ),
        ],
      ),
      body: SafeArea(
        child: SingleChildScrollView(
          padding: const EdgeInsets.fromLTRB(16, 16, 16, 32),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              _ManagementWelcomeCard(session: session),
              const SizedBox(height: 20),
              for (var index = 0; index < sections.length; index++) ...[
                _ManagementSectionCard(
                  section: sections[index],
                  onOpen: (module) => _openModule(context, module),
                ),
                if (index != sections.length - 1) const SizedBox(height: 16),
              ],
            ],
          ),
        ),
      ),
    );
  }
}

class _ManagementWelcomeCard extends StatelessWidget {
  const _ManagementWelcomeCard({required this.session});

  final UserSession session;

  @override
  Widget build(BuildContext context) {
    return Card(
      color: Theme.of(context).colorScheme.primaryContainer,
      child: Padding(
        padding: const EdgeInsets.all(20),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              'Welcome, ${session.displayName}',
              style: Theme.of(context).textTheme.headlineSmall,
            ),
            const SizedBox(height: 8),
            const Text(
              'Start with alerts and review queues, then move into lending, '
              'cash custody, account settings, or accounting.',
            ),
          ],
        ),
      ),
    );
  }
}

class _ManagementSectionCard extends StatelessWidget {
  const _ManagementSectionCard({required this.section, required this.onOpen});

  final _ManagementSection section;
  final ValueChanged<_ManagementModule> onOpen;

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
              const SizedBox(height: 4),
              Text(
                section.description,
                style: Theme.of(context).textTheme.bodyMedium,
              ),
            ],
          ),
        ),
        const SizedBox(height: 8),
        Card(
          margin: EdgeInsets.zero,
          clipBehavior: Clip.antiAlias,
          child: Column(
            children: [
              for (var index = 0; index < section.modules.length; index++) ...[
                _ManagementModuleTile(
                  module: section.modules[index],
                  onTap: () => onOpen(section.modules[index]),
                ),
                if (index != section.modules.length - 1)
                  const Divider(height: 1),
              ],
            ],
          ),
        ),
      ],
    );
  }
}

class _ManagementModuleTile extends StatelessWidget {
  const _ManagementModuleTile({required this.module, required this.onTap});

  final _ManagementModule module;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return ListTile(
      key: Key(module.action.keyName),
      contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 6),
      leading: Icon(module.icon),
      title: Text(module.title),
      subtitle: Text(module.description),
      trailing: const Icon(Icons.chevron_right),
      onTap: onTap,
    );
  }
}

enum _ManagementAction {
  alertsActivity('management-alerts-activity'),
  myAccountDevices('management-my-account-devices'),
  offlinePolicy('management-offline-policy'),
  loans('management-loans'),
  contractCollectionActivation('management-contract-collection-activation'),
  noCollection('management-no-collection'),
  loanOperations('management-loan-operations'),
  remittanceNotifications('remittance-notifications'),
  directPayment('management-direct-payment'),
  voidPayment('management-void-payment'),
  renewals('management-renewals'),
  support('management-support'),
  clientRegistrationApprovals('client-registration-approvals'),
  financialAccounting('management-financial-accounting'),
  eclOutcomeReview('management-ecl-outcome-review'),
  accountingMeasurement('management-accounting-measurement'),
  openingBalanceWorkbook('management-opening-balance-workbook'),
  openingBalanceJournal('management-opening-balance-journal'),
  generalJournal('management-general-journal'),
  financialStatements('management-financial-statements');

  const _ManagementAction(this.keyName);

  final String keyName;
}

class _ManagementModule {
  const _ManagementModule(
    this.title,
    this.description,
    this.icon, {
    required this.action,
    this.requiredPermissions = const <String>[],
  });

  final String title;
  final String description;
  final IconData icon;
  final _ManagementAction action;
  final List<String> requiredPermissions;

  bool isAvailableFor(UserSession session) {
    return requiredPermissions.every(session.hasPermission);
  }
}

class _ManagementSection {
  const _ManagementSection({
    required this.keyName,
    required this.title,
    required this.description,
    required this.modules,
  });

  final String keyName;
  final String title;
  final String description;
  final List<_ManagementModule> modules;

  _ManagementSection availableFor(UserSession session) {
    return _ManagementSection(
      keyName: keyName,
      title: title,
      description: description,
      modules: modules
          .where((module) => module.isAvailableFor(session))
          .toList(growable: false),
    );
  }
}

const _managementSections = <_ManagementSection>[
  _ManagementSection(
    keyName: 'management-section-review',
    title: 'Review now',
    description: 'See alerts and activity that may need your attention first.',
    modules: <_ManagementModule>[
      _ManagementModule(
        'Alerts & activity',
        'Payments, custody changes, approvals, failures, and other updates',
        Icons.notifications_active_outlined,
        action: _ManagementAction.alertsActivity,
      ),
    ],
  ),
  _ManagementSection(
    keyName: 'management-section-clients-loans',
    title: 'Clients & loans',
    description: 'Review active lending relationships and protected changes.',
    modules: <_ManagementModule>[
      _ManagementModule(
        'Loan portfolio',
        'Active clients, balances, due dates, and loan status',
        Icons.account_balance,
        action: _ManagementAction.loans,
      ),
      _ManagementModule(
        'Contract collection',
        'Activate collection only from verified contract evidence',
        Icons.verified_user_outlined,
        action: _ManagementAction.contractCollectionActivation,
        requiredPermissions: <String>['lending.contract_collection.activate'],
      ),
      _ManagementModule(
        'No Collection',
        'Move one loan schedule forward with protected audit evidence',
        Icons.event_busy_outlined,
        action: _ManagementAction.noCollection,
        requiredPermissions: <String>['lending.no_collection.manage'],
      ),
    ],
  ),
  _ManagementSection(
    keyName: 'management-section-collections-custody',
    title: 'Collections & custody',
    description:
        'Monitor client cash, remittances, corrections, and reversals.',
    modules: <_ManagementModule>[
      _ManagementModule(
        'Collection oversight',
        'Collections, remittances, custody, corrections, and voids',
        Icons.insights,
        action: _ManagementAction.loanOperations,
      ),
      _ManagementModule(
        'Remittance requests',
        'Review cash handovers sent to your Management account',
        Icons.move_to_inbox_outlined,
        action: _ManagementAction.remittanceNotifications,
        requiredPermissions: <String>['remittance.view'],
      ),
      _ManagementModule(
        'Direct payment entry',
        'Record client cash paid directly to Management',
        Icons.point_of_sale,
        action: _ManagementAction.directPayment,
        requiredPermissions: <String>['collection.create'],
      ),
      _ManagementModule(
        'Void incorrect payment',
        'Reverse an unlocked wrong payment with permanent evidence',
        Icons.block,
        action: _ManagementAction.voidPayment,
        requiredPermissions: <String>['collection.void.unremitted'],
      ),
    ],
  ),
  _ManagementSection(
    keyName: 'management-section-renewals-support',
    title: 'Renewals & support',
    description: 'Handle borrower requests and client-account access reviews.',
    modules: <_ManagementModule>[
      _ManagementModule(
        'Renewal requests',
        'Review recommendations, set terms, and control handover status',
        Icons.autorenew,
        action: _ManagementAction.renewals,
        requiredPermissions: <String>['renewal.manage'],
      ),
      _ManagementModule(
        'Client support',
        'Answer and resolve borrower assistance requests',
        Icons.support_agent,
        action: _ManagementAction.support,
        requiredPermissions: <String>['support.manage'],
      ),
      _ManagementModule(
        'Client registrations',
        'Approve portal access and link the correct borrower record',
        Icons.how_to_reg,
        action: _ManagementAction.clientRegistrationApprovals,
        requiredPermissions: <String>['account.manage'],
      ),
    ],
  ),
  _ManagementSection(
    keyName: 'management-section-account-connectivity',
    title: 'My account & connectivity',
    description:
        'Review your own Management account, session, device, and live-server requirements.',
    modules: <_ManagementModule>[
      _ManagementModule(
        'My account & devices',
        'Profile, current session, registered devices, and sign-out controls',
        Icons.admin_panel_settings_outlined,
        action: _ManagementAction.myAccountDevices,
      ),
      _ManagementModule(
        'Connectivity & offline policy',
        'See which Management data and actions require the live server',
        Icons.cloud_off_outlined,
        action: _ManagementAction.offlinePolicy,
      ),
    ],
  ),
  _ManagementSection(
    keyName: 'management-section-reports-accounting',
    title: 'Reports & accounting',
    description:
        'Review financial status and use protected accounting workflows.',
    modules: <_ManagementModule>[
      _ManagementModule(
        'Financial Accounting',
        'Periods, accounts, readiness, and loan policy controls',
        Icons.calculate,
        action: _ManagementAction.financialAccounting,
        requiredPermissions: <String>['accounting.view'],
      ),
      _ManagementModule(
        'Historical outcome review',
        'Review protected ECL outcome evidence before measurement',
        Icons.fact_check_outlined,
        action: _ManagementAction.eclOutcomeReview,
        requiredPermissions: <String>['accounting.ecl.review'],
      ),
      _ManagementModule(
        'Loan measurement',
        'Inspect protected carrying amounts and measurement readiness',
        Icons.calculate_outlined,
        action: _ManagementAction.accountingMeasurement,
        requiredPermissions: <String>['accounting.view'],
      ),
      _ManagementModule(
        'Opening workbook',
        'Prepare and review controlled first-book evidence',
        Icons.table_view_outlined,
        action: _ManagementAction.openingBalanceWorkbook,
        requiredPermissions: <String>['accounting.cutover.manage'],
      ),
      _ManagementModule(
        'Opening Balance Journal',
        'Prepare the protected cutover journal for explicit posting',
        Icons.lock_clock_outlined,
        action: _ManagementAction.openingBalanceJournal,
        requiredPermissions: <String>['accounting.view'],
      ),
      _ManagementModule(
        'General Journal',
        'Manual journals, posting, reversals, and Trial Balance',
        Icons.menu_book_outlined,
        action: _ManagementAction.generalJournal,
        requiredPermissions: <String>['accounting.view'],
      ),
      _ManagementModule(
        'Financial Statements',
        'Posted-ledger Profit or Loss and Financial Position',
        Icons.assessment_outlined,
        action: _ManagementAction.financialStatements,
        requiredPermissions: <String>['accounting.view'],
      ),
    ],
  ),
];
