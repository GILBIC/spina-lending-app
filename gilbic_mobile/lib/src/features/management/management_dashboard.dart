import 'dart:async';

import 'package:flutter/material.dart';
import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/device/device_identity.dart';
import 'package:gilbic_mobile/src/core/management/management_alerts_audit.dart';
import 'package:gilbic_mobile/src/core/management/management_alerts_audit_repository.dart';
import 'package:gilbic_mobile/src/core/management/management_dashboard_overview.dart';
import 'package:gilbic_mobile/src/core/management/management_dashboard_overview_repository.dart';
import 'package:gilbic_mobile/src/core/management/management_employee_activity_repository.dart';
import 'package:gilbic_mobile/src/core/network/spina_api.dart';
import 'package:gilbic_mobile/src/core/payments/collection_device_sequence.dart';
import 'package:gilbic_mobile/src/core/payments/payment_submission_repository.dart';
import 'package:gilbic_mobile/src/features/account/account_settings_page.dart';
import 'package:gilbic_mobile/src/features/collector/other_area_collection_page.dart';
import 'package:gilbic_mobile/src/features/management/client_registration_approvals_page.dart';
import 'package:gilbic_mobile/src/features/management/management_alerts_audit_page.dart';
import 'package:gilbic_mobile/src/features/management/management_accounting_measurement_page.dart';
import 'package:gilbic_mobile/src/features/management/management_collection_void_page.dart';
import 'package:gilbic_mobile/src/features/management/management_contract_collection_activation_page.dart';
import 'package:gilbic_mobile/src/features/management/management_ecl_outcome_review_page.dart';
import 'package:gilbic_mobile/src/features/management/management_employee_activity_page.dart';
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

class ManagementDashboard extends StatefulWidget {
  const ManagementDashboard({
    required this.session,
    required this.onSignOut,
    required this.paymentSubmissionRepository,
    required this.deviceIdentityProvider,
    required this.collectionDeviceSequence,
    this.overviewRepository,
    this.alertsAuditRepository,
    this.employeeActivityRepository,
    super.key,
  });

  final UserSession session;
  final Future<void> Function() onSignOut;
  final PaymentSubmissionRepository paymentSubmissionRepository;
  final DeviceIdentityProvider deviceIdentityProvider;
  final CollectionDeviceSequence collectionDeviceSequence;
  final ManagementDashboardOverviewRepository? overviewRepository;
  final ManagementAlertsAuditRepository? alertsAuditRepository;
  final ManagementEmployeeActivityRepository? employeeActivityRepository;

  @override
  State<ManagementDashboard> createState() => _ManagementDashboardState();
}

class _ManagementDashboardState extends State<ManagementDashboard> {
  late final ManagementDashboardOverviewRepository _overviewRepository;
  ManagementDashboardOverview? _overview;
  bool _loadingOverview = true;
  String? _overviewError;
  int? _overviewStatusCode;
  String? _deviceId;
  Future<String>? _deviceIdLoad;
  int _requestGeneration = 0;

  UserSession get session => widget.session;
  Future<void> Function() get onSignOut => widget.onSignOut;
  PaymentSubmissionRepository get paymentSubmissionRepository =>
      widget.paymentSubmissionRepository;
  DeviceIdentityProvider get deviceIdentityProvider =>
      widget.deviceIdentityProvider;
  CollectionDeviceSequence get collectionDeviceSequence =>
      widget.collectionDeviceSequence;

  @override
  void initState() {
    super.initState();
    _overviewRepository =
        widget.overviewRepository ??
        SpinaManagementDashboardOverviewRepository();
    unawaited(_loadOverview());
  }

  @override
  void dispose() {
    _requestGeneration += 1;
    super.dispose();
  }

  Future<String> _loadDeviceIdOnce() {
    final cached = _deviceId;
    if (cached != null) return Future<String>.value(cached);
    return _deviceIdLoad ??= _loadAndCacheDeviceId();
  }

  Future<String> _loadAndCacheDeviceId() async {
    try {
      final identity = await widget.deviceIdentityProvider.load();
      _deviceId = identity.installationId;
      return identity.installationId;
    } finally {
      _deviceIdLoad = null;
    }
  }

  Future<void> _loadOverview({bool refresh = false}) async {
    final generation = ++_requestGeneration;
    setState(() {
      _loadingOverview = true;
      _overviewError = null;
      _overviewStatusCode = null;
    });
    try {
      final deviceId = await _loadDeviceIdOnce();
      final overview = await _overviewRepository.loadOverview(
        widget.session,
        deviceId: deviceId,
      );
      if (!mounted || generation != _requestGeneration) return;
      setState(() => _overview = overview);
    } on Object catch (error) {
      if (!mounted || generation != _requestGeneration) return;
      setState(() {
        _overviewError = error is SpinaApiException
            ? error.message
            : refresh
            ? 'The live Management overview could not be refreshed.'
            : 'The live Management overview could not be loaded.';
        _overviewStatusCode = error is SpinaApiException
            ? error.statusCode
            : null;
      });
    } finally {
      if (mounted && generation == _requestGeneration) {
        setState(() => _loadingOverview = false);
      }
    }
  }

  void _push(BuildContext context, Widget page) {
    Navigator.of(
      context,
    ).push(MaterialPageRoute<void>(builder: (context) => page));
  }

  void _openAlertsDestination(
    BuildContext context,
    ManagementAlertsAuditNavigation destination,
  ) {
    final isAvailable = switch (destination) {
      ManagementAlertsAuditNavigation.paymentUpdates => true,
      ManagementAlertsAuditNavigation.staffDevices =>
        session.hasPermission('account.manage') ||
            session.hasPermission('device.manage'),
      ManagementAlertsAuditNavigation.clientRegistrations =>
        session.hasPermission('account.manage'),
      ManagementAlertsAuditNavigation.renewals => session.hasPermission(
        'renewal.manage',
      ),
      ManagementAlertsAuditNavigation.support => session.hasPermission(
        'support.manage',
      ),
      ManagementAlertsAuditNavigation.remittanceReview => session.hasPermission(
        'remittance.view',
      ),
      ManagementAlertsAuditNavigation.financialAccounting =>
        session.hasPermission('accounting.view'),
    };
    if (!isAvailable) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text(
            'Your current permissions do not allow this Management view.',
          ),
        ),
      );
      return;
    }
    final page = switch (destination) {
      ManagementAlertsAuditNavigation.paymentUpdates =>
        ActivityNotificationsPage(
          session: session,
          deviceIdentityProvider: deviceIdentityProvider,
        ),
      ManagementAlertsAuditNavigation.staffDevices =>
        ManagementStaffDevicesPage(
          session: session,
          deviceIdentityProvider: deviceIdentityProvider,
        ),
      ManagementAlertsAuditNavigation.clientRegistrations =>
        ClientRegistrationApprovalsPage(
          session: session,
          deviceIdentityProvider: deviceIdentityProvider,
        ),
      ManagementAlertsAuditNavigation.renewals => ManagementRenewalRequestsPage(
        session: session,
        deviceIdentityProvider: deviceIdentityProvider,
      ),
      ManagementAlertsAuditNavigation.support => ManagementSupportRequestsPage(
        session: session,
        deviceIdentityProvider: deviceIdentityProvider,
      ),
      ManagementAlertsAuditNavigation.remittanceReview =>
        RemittanceNotificationsPage(
          session: session,
          deviceIdentityProvider: deviceIdentityProvider,
        ),
      ManagementAlertsAuditNavigation.financialAccounting =>
        ManagementFinancialAccountingPage(
          session: session,
          deviceIdentityProvider: deviceIdentityProvider,
        ),
    };
    _push(context, page);
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
      _ManagementAction.alertsActivity => ManagementAlertsAuditPage(
        session: session,
        deviceIdentityProvider: deviceIdentityProvider,
        repository: widget.alertsAuditRepository,
        onOpenDestination: (destination) =>
            _openAlertsDestination(context, destination),
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
      _ManagementAction.staffDevices => ManagementStaffDevicesPage(
        session: session,
        deviceIdentityProvider: deviceIdentityProvider,
      ),
      _ManagementAction.employeeActivity => ManagementEmployeeActivityPage(
        session: session,
        deviceIdentityProvider: deviceIdentityProvider,
        repository: widget.employeeActivityRepository,
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

  void _openOverviewMetric(
    BuildContext context,
    ManagementDashboardMetricKey key,
  ) {
    final action = _metricActions[key];
    if (action == null) return;
    for (final section in _managementSections) {
      for (final module in section.modules) {
        if (module.action == action) {
          _openModule(context, module);
          return;
        }
      }
    }
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
        child: RefreshIndicator(
          onRefresh: () => _loadOverview(refresh: true),
          child: SingleChildScrollView(
            physics: const AlwaysScrollableScrollPhysics(),
            padding: const EdgeInsets.fromLTRB(16, 16, 16, 32),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                _ManagementWelcomeCard(session: session),
                const SizedBox(height: 16),
                _ManagementLiveOverview(
                  overview: _overview,
                  loading: _loadingOverview,
                  error: _overviewError,
                  statusCode: _overviewStatusCode,
                  onRefresh: () => unawaited(_loadOverview(refresh: true)),
                  onRetry: () => unawaited(_loadOverview()),
                  onSignInAgain: () => unawaited(onSignOut()),
                  onOpenMetric: (key) => _openOverviewMetric(context, key),
                ),
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
      ),
    );
  }
}

class _ManagementWelcomeCard extends StatelessWidget {
  const _ManagementWelcomeCard({required this.session});

  final UserSession session;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 4),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            'Welcome, ${session.displayName}',
            style: Theme.of(context).textTheme.titleLarge,
          ),
          const SizedBox(height: 4),
          Text(
            'Your live numbers and authorized Management tools.',
            style: Theme.of(context).textTheme.bodyMedium,
          ),
        ],
      ),
    );
  }
}

class _ManagementLiveOverview extends StatelessWidget {
  const _ManagementLiveOverview({
    required this.overview,
    required this.loading,
    required this.error,
    required this.statusCode,
    required this.onRefresh,
    required this.onRetry,
    required this.onSignInAgain,
    required this.onOpenMetric,
  });

  final ManagementDashboardOverview? overview;
  final bool loading;
  final String? error;
  final int? statusCode;
  final VoidCallback onRefresh;
  final VoidCallback onRetry;
  final VoidCallback onSignInAgain;
  final ValueChanged<ManagementDashboardMetricKey> onOpenMetric;

  @override
  Widget build(BuildContext context) {
    final snapshot = overview;
    if (snapshot == null && error != null) {
      return _ManagementOverviewInitialError(
        error: error!,
        statusCode: statusCode,
        onRetry: onRetry,
        onSignInAgain: onSignInAgain,
      );
    }
    if (snapshot == null) {
      return Card(
        key: const Key('management-overview-loading'),
        child: Padding(
          padding: const EdgeInsets.all(18),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              _ManagementOverviewHeader(
                onRefresh: onRefresh,
                refreshing: loading,
              ),
              const SizedBox(height: 12),
              const LinearProgressIndicator(),
              const SizedBox(height: 12),
              const Text('Loading current lending, cash, and review totals…'),
            ],
          ),
        ),
      );
    }

    final facts = _factMetricKeys
        .map(snapshot.metric)
        .whereType<ManagementDashboardMetric>()
        .toList(growable: false);
    final returnedAttention = _attentionMetricKeys
        .map(snapshot.metric)
        .whereType<ManagementDashboardMetric>()
        .toList(growable: false);
    final attention = returnedAttention
        .where(_metricHasAttention)
        .toList(growable: false);

    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        _ManagementOverviewHeader(onRefresh: onRefresh, refreshing: loading),
        if (loading) ...[
          const SizedBox(height: 6),
          const LinearProgressIndicator(
            key: Key('management-overview-refreshing'),
          ),
        ],
        const SizedBox(height: 4),
        Text(
          _updatedText(context, snapshot.generatedAt),
          style: Theme.of(context).textTheme.bodySmall,
        ),
        if (error != null) ...[
          const SizedBox(height: 10),
          Material(
            key: const Key('management-overview-refresh-error'),
            color: Theme.of(context).colorScheme.errorContainer,
            borderRadius: BorderRadius.circular(12),
            child: Padding(
              padding: const EdgeInsets.all(12),
              child: Text(
                'Refresh failed. The last successful snapshot remains visible. '
                '$error',
              ),
            ),
          ),
        ],
        const SizedBox(height: 14),
        Text(
          'Today & portfolio',
          style: Theme.of(context).textTheme.titleMedium,
        ),
        const SizedBox(height: 8),
        KeyedSubtree(
          key: const Key('management-overview-facts'),
          child: _ManagementKpiGrid(
            key: const Key('management-kpi-grid'),
            metrics: facts,
            onOpenMetric: onOpenMetric,
          ),
        ),
        const SizedBox(height: 16),
        Text('Needs attention', style: Theme.of(context).textTheme.titleMedium),
        const SizedBox(height: 8),
        if (attention.isEmpty)
          Card(
            key: const Key('management-overview-no-pending'),
            margin: EdgeInsets.zero,
            child: const Padding(
              padding: EdgeInsets.all(16),
              child: Text('No pending items in your authorized queues.'),
            ),
          )
        else
          _ManagementAttentionGrid(
            key: const Key('management-overview-attention'),
            metrics: attention,
            onOpenMetric: onOpenMetric,
          ),
      ],
    );
  }
}

class _ManagementOverviewHeader extends StatelessWidget {
  const _ManagementOverviewHeader({
    required this.onRefresh,
    required this.refreshing,
  });

  final VoidCallback onRefresh;
  final bool refreshing;

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        Expanded(
          child: Text(
            'Live Management overview',
            style: Theme.of(context).textTheme.titleLarge,
          ),
        ),
        IconButton(
          key: const Key('management-overview-refresh'),
          tooltip: refreshing ? 'Refresh again' : 'Refresh live overview',
          onPressed: onRefresh,
          icon: const Icon(Icons.refresh),
        ),
      ],
    );
  }
}

class _ManagementOverviewInitialError extends StatelessWidget {
  const _ManagementOverviewInitialError({
    required this.error,
    required this.statusCode,
    required this.onRetry,
    required this.onSignInAgain,
  });

  final String error;
  final int? statusCode;
  final VoidCallback onRetry;
  final VoidCallback onSignInAgain;

  @override
  Widget build(BuildContext context) {
    final title = switch (statusCode) {
      401 => 'Session expired',
      403 => 'Live data access unavailable',
      _ => 'Live overview unavailable',
    };
    final guidance = switch (statusCode) {
      401 => 'Sign in again to load current Management data.',
      403 =>
        'Your current role, permission, or device approval does not allow '
            'this live snapshot.',
      _ => 'Retry when the live server is available.',
    };

    return Card(
      key: const Key('management-overview-error'),
      color: Theme.of(context).colorScheme.errorContainer,
      child: Padding(
        padding: const EdgeInsets.all(18),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Text(title, style: Theme.of(context).textTheme.titleLarge),
            const SizedBox(height: 8),
            Text('$guidance $error'),
            const SizedBox(height: 12),
            Align(
              alignment: Alignment.centerLeft,
              child: statusCode == 401
                  ? FilledButton.icon(
                      key: const Key('management-overview-sign-in'),
                      onPressed: onSignInAgain,
                      icon: const Icon(Icons.login),
                      label: const Text('Sign in again'),
                    )
                  : OutlinedButton.icon(
                      key: const Key('management-overview-retry'),
                      onPressed: onRetry,
                      icon: const Icon(Icons.refresh),
                      label: const Text('Retry'),
                    ),
            ),
          ],
        ),
      ),
    );
  }
}

class _ManagementAttentionGrid extends StatelessWidget {
  const _ManagementAttentionGrid({
    required super.key,
    required this.metrics,
    required this.onOpenMetric,
  });

  final List<ManagementDashboardMetric> metrics;
  final ValueChanged<ManagementDashboardMetricKey> onOpenMetric;

  @override
  Widget build(BuildContext context) {
    return LayoutBuilder(
      builder: (context, constraints) {
        const spacing = 8.0;
        final columnCount = constraints.maxWidth >= 900
            ? 6
            : constraints.maxWidth >= 600
            ? 5
            : 4;
        final itemWidth =
            (constraints.maxWidth - (spacing * (columnCount - 1))) /
            columnCount;
        return Wrap(
          spacing: spacing,
          runSpacing: spacing,
          children: [
            for (final metric in metrics)
              SizedBox(
                width: itemWidth,
                child: _ManagementAttentionCard(
                  metric: metric,
                  onTap: () => onOpenMetric(metric.key),
                ),
              ),
          ],
        );
      },
    );
  }
}

class _ManagementKpiGrid extends StatelessWidget {
  const _ManagementKpiGrid({
    required super.key,
    required this.metrics,
    required this.onOpenMetric,
  });

  final List<ManagementDashboardMetric> metrics;
  final ValueChanged<ManagementDashboardMetricKey> onOpenMetric;

  @override
  Widget build(BuildContext context) {
    return LayoutBuilder(
      builder: (context, constraints) {
        const spacing = 10.0;
        final columnCount = constraints.maxWidth >= 900 ? 3 : 2;
        final cardWidth =
            (constraints.maxWidth - (spacing * (columnCount - 1))) /
            columnCount;
        return Wrap(
          spacing: spacing,
          runSpacing: spacing,
          children: [
            for (final metric in metrics)
              SizedBox(
                width: cardWidth,
                child: _ManagementKpiCard(
                  metric: metric,
                  onTap: () => onOpenMetric(metric.key),
                ),
              ),
          ],
        );
      },
    );
  }
}

class _ManagementKpiCard extends StatelessWidget {
  const _ManagementKpiCard({required this.metric, required this.onTap});

  final ManagementDashboardMetric metric;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final content = _kpiContent(context, metric);
    return SizedBox(
      height: 104,
      child: Card(
        key: Key('management-overview-metric-${metric.key.name}'),
        margin: EdgeInsets.zero,
        clipBehavior: Clip.antiAlias,
        child: Semantics(
          button: true,
          label:
              '${content.$1} ${content.$2}. '
              'Open ${_metricDestinationLabel(metric.key)}.',
          child: InkWell(
            onTap: onTap,
            child: Padding(
              padding: const EdgeInsets.all(10),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  FittedBox(
                    fit: BoxFit.scaleDown,
                    alignment: Alignment.centerLeft,
                    child: Text(
                      content.$1,
                      style: Theme.of(context).textTheme.titleLarge,
                    ),
                  ),
                  const SizedBox(height: 2),
                  Text(
                    content.$2,
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                    style: Theme.of(context).textTheme.labelMedium,
                  ),
                  if (content.$3 != null) ...[
                    const SizedBox(height: 2),
                    Text(
                      content.$3!,
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                      style: Theme.of(context).textTheme.bodySmall,
                    ),
                  ],
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }
}

class _ManagementAttentionCard extends StatelessWidget {
  const _ManagementAttentionCard({required this.metric, required this.onTap});

  final ManagementDashboardMetric metric;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final content = _attentionContent(metric);
    final colors = Theme.of(context).colorScheme;
    return SizedBox(
      key: Key('management-overview-metric-${metric.key.name}'),
      height: 92,
      child: Semantics(
        button: true,
        label:
            '${content.$1}. ${content.$2} '
            'Open ${_metricDestinationLabel(metric.key)}.',
        child: Tooltip(
          message: content.$2,
          child: Material(
            color: Colors.transparent,
            child: InkWell(
              borderRadius: BorderRadius.circular(12),
              onTap: onTap,
              child: Padding(
                padding: const EdgeInsets.symmetric(horizontal: 2, vertical: 4),
                child: Column(
                  mainAxisAlignment: MainAxisAlignment.center,
                  children: [
                    Stack(
                      clipBehavior: Clip.none,
                      children: [
                        Container(
                          width: 36,
                          height: 36,
                          decoration: BoxDecoration(
                            color: colors.primaryContainer,
                            borderRadius: BorderRadius.circular(12),
                          ),
                          child: Icon(
                            _metricIcon(metric.key),
                            size: 20,
                            color: colors.onPrimaryContainer,
                          ),
                        ),
                        Positioned(
                          top: -7,
                          right: -10,
                          child: Badge(
                            key: Key(
                              'management-attention-badge-${metric.key.name}',
                            ),
                            label: Text(_attentionBadgeText(metric)),
                          ),
                        ),
                      ],
                    ),
                    const SizedBox(height: 4),
                    Text(
                      content.$1,
                      maxLines: 2,
                      overflow: TextOverflow.ellipsis,
                      textAlign: TextAlign.center,
                      style: Theme.of(context).textTheme.labelSmall,
                    ),
                  ],
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }
}

const _factMetricKeys = <ManagementDashboardMetricKey>[
  ManagementDashboardMetricKey.activeClients,
  ManagementDashboardMetricKey.activeLoans,
  ManagementDashboardMetricKey.overdueLoans,
  ManagementDashboardMetricKey.outstandingBalance,
  ManagementDashboardMetricKey.latestCollections,
  ManagementDashboardMetricKey.unremittedCollections,
];

const _attentionMetricKeys = <ManagementDashboardMetricKey>[
  ManagementDashboardMetricKey.assignedRemittances,
  ManagementDashboardMetricKey.protectedRenewals,
  ManagementDashboardMetricKey.staffRegistrations,
  ManagementDashboardMetricKey.clientRegistrations,
  ManagementDashboardMetricKey.collectorMobileDevices,
  ManagementDashboardMetricKey.borrowerSupport,
  ManagementDashboardMetricKey.unreadActivity,
];

bool _metricHasAttention(ManagementDashboardMetric metric) {
  return (metric.count ?? 0) > 0 ||
      (metric.amount != null && metric.amount != '0.00');
}

(String, String) _attentionContent(ManagementDashboardMetric metric) {
  final amount = _formatMoney(metric.amount ?? '0.00');
  return switch (metric.key) {
    ManagementDashboardMetricKey.assignedRemittances => (
      'Remittances',
      'PHP $amount awaiting receipt',
    ),
    ManagementDashboardMetricKey.protectedRenewals => (
      'Renewal requests',
      'Protected Management review',
    ),
    ManagementDashboardMetricKey.staffRegistrations => (
      'Staff registrations',
      'Account approval queue',
    ),
    ManagementDashboardMetricKey.clientRegistrations => (
      'Client registrations',
      'Portal access approval queue',
    ),
    ManagementDashboardMetricKey.collectorMobileDevices => (
      'Collector devices',
      'Pending device approval',
    ),
    ManagementDashboardMetricKey.borrowerSupport => (
      'Client support',
      'Open or awaiting resolution',
    ),
    ManagementDashboardMetricKey.unreadActivity => (
      'Activity updates',
      'Payments, approvals, and custody events',
    ),
    _ => (_metricDestinationLabel(metric.key), 'Open current details'),
  };
}

String _attentionBadgeText(ManagementDashboardMetric metric) {
  final count = metric.count ?? 0;
  if (count > 99) return '99+';
  if (count > 0) return '$count';
  return '•';
}

(String, String, String?) _kpiContent(
  BuildContext context,
  ManagementDashboardMetric metric,
) {
  final count = metric.count ?? 0;
  final amount = _formatMoney(metric.amount ?? '0.00');
  return switch (metric.key) {
    ManagementDashboardMetricKey.activeClients => (
      '$count',
      'Active clients',
      null,
    ),
    ManagementDashboardMetricKey.activeLoans => (
      '$count',
      'Active loans',
      null,
    ),
    ManagementDashboardMetricKey.overdueLoans => (
      '$count',
      'Overdue loans',
      null,
    ),
    ManagementDashboardMetricKey.outstandingBalance => (
      'PHP $amount',
      'Outstanding',
      null,
    ),
    ManagementDashboardMetricKey.latestCollections => (
      'PHP $amount',
      'Collected',
      '$count entries${_asOfText(context, metric.asOfDate)}',
    ),
    ManagementDashboardMetricKey.unremittedCollections => (
      'PHP $amount',
      'Unremitted cash',
      '$count collection entries',
    ),
    _ => ('$count', _metricDestinationLabel(metric.key), null),
  };
}

String _updatedText(BuildContext context, DateTime generatedAt) {
  final local = generatedAt.toLocal();
  final date = MaterialLocalizations.of(context).formatMediumDate(local);
  final time = TimeOfDay.fromDateTime(local).format(context);
  return 'Updated $date at $time';
}

String _asOfText(BuildContext context, DateTime? asOfDate) {
  if (asOfDate == null) return '';
  final calendarDate = DateTime(asOfDate.year, asOfDate.month, asOfDate.day);
  final date = MaterialLocalizations.of(context).formatMediumDate(calendarDate);
  return ' • $date';
}

String _formatMoney(String value) {
  final parts = value.split('.');
  final integer = parts.first;
  final grouped = StringBuffer();
  for (var index = 0; index < integer.length; index++) {
    if (index > 0 && (integer.length - index) % 3 == 0) {
      grouped.write(',');
    }
    grouped.write(integer[index]);
  }
  return '${grouped.toString()}.${parts[1]}';
}

String _metricDestinationLabel(ManagementDashboardMetricKey key) {
  return switch (key) {
    ManagementDashboardMetricKey.activeClients ||
    ManagementDashboardMetricKey.activeLoans ||
    ManagementDashboardMetricKey.overdueLoans ||
    ManagementDashboardMetricKey.outstandingBalance => 'Loan portfolio',
    ManagementDashboardMetricKey.latestCollections ||
    ManagementDashboardMetricKey.unremittedCollections =>
      'Collection oversight',
    ManagementDashboardMetricKey.assignedRemittances => 'Remittance requests',
    ManagementDashboardMetricKey.protectedRenewals => 'Renewal requests',
    ManagementDashboardMetricKey.staffRegistrations ||
    ManagementDashboardMetricKey.collectorMobileDevices => 'Staff and devices',
    ManagementDashboardMetricKey.clientRegistrations => 'Client registrations',
    ManagementDashboardMetricKey.borrowerSupport => 'Client support',
    ManagementDashboardMetricKey.unreadActivity => 'Alerts and activity',
  };
}

IconData _metricIcon(ManagementDashboardMetricKey key) {
  return switch (key) {
    ManagementDashboardMetricKey.activeClients => Icons.groups_outlined,
    ManagementDashboardMetricKey.activeLoans => Icons.account_balance_outlined,
    ManagementDashboardMetricKey.overdueLoans => Icons.warning_amber_outlined,
    ManagementDashboardMetricKey.outstandingBalance =>
      Icons.account_balance_wallet_outlined,
    ManagementDashboardMetricKey.latestCollections => Icons.payments_outlined,
    ManagementDashboardMetricKey.unremittedCollections =>
      Icons.inventory_2_outlined,
    ManagementDashboardMetricKey.assignedRemittances =>
      Icons.move_to_inbox_outlined,
    ManagementDashboardMetricKey.protectedRenewals => Icons.autorenew,
    ManagementDashboardMetricKey.staffRegistrations =>
      Icons.person_add_alt_outlined,
    ManagementDashboardMetricKey.clientRegistrations =>
      Icons.how_to_reg_outlined,
    ManagementDashboardMetricKey.collectorMobileDevices =>
      Icons.phonelink_lock_outlined,
    ManagementDashboardMetricKey.borrowerSupport => Icons.support_agent,
    ManagementDashboardMetricKey.unreadActivity =>
      Icons.notifications_active_outlined,
  };
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
        _ManagementModuleGrid(
          key: Key('management-module-grid-${section.keyName}'),
          modules: section.modules,
          onOpen: onOpen,
        ),
      ],
    );
  }
}

class _ManagementModuleGrid extends StatelessWidget {
  const _ManagementModuleGrid({
    required super.key,
    required this.modules,
    required this.onOpen,
  });

  final List<_ManagementModule> modules;
  final ValueChanged<_ManagementModule> onOpen;

  @override
  Widget build(BuildContext context) {
    return LayoutBuilder(
      builder: (context, constraints) {
        const spacing = 8.0;
        final columnCount = constraints.maxWidth >= 900
            ? 6
            : constraints.maxWidth >= 600
            ? 5
            : 4;
        final itemWidth =
            (constraints.maxWidth - (spacing * (columnCount - 1))) /
            columnCount;
        return Wrap(
          spacing: spacing,
          runSpacing: spacing,
          children: [
            for (final module in modules)
              SizedBox(
                width: itemWidth,
                child: _ManagementModuleShortcut(
                  module: module,
                  onTap: () => onOpen(module),
                ),
              ),
          ],
        );
      },
    );
  }
}

class _ManagementModuleShortcut extends StatelessWidget {
  const _ManagementModuleShortcut({required this.module, required this.onTap});

  final _ManagementModule module;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final colors = Theme.of(context).colorScheme;
    return SizedBox(
      key: Key(module.action.keyName),
      height: 92,
      child: Semantics(
        button: true,
        label: '${module.title}. ${module.description}',
        child: Tooltip(
          message: module.description,
          child: Material(
            color: Colors.transparent,
            child: InkWell(
              borderRadius: BorderRadius.circular(12),
              onTap: onTap,
              child: Padding(
                padding: const EdgeInsets.symmetric(horizontal: 2, vertical: 4),
                child: Column(
                  mainAxisAlignment: MainAxisAlignment.center,
                  children: [
                    Container(
                      width: 36,
                      height: 36,
                      decoration: BoxDecoration(
                        color: colors.primaryContainer,
                        borderRadius: BorderRadius.circular(12),
                      ),
                      child: Icon(
                        module.icon,
                        size: 20,
                        color: colors.onPrimaryContainer,
                      ),
                    ),
                    const SizedBox(height: 4),
                    Text(
                      module.title,
                      maxLines: 2,
                      overflow: TextOverflow.ellipsis,
                      textAlign: TextAlign.center,
                      style: Theme.of(context).textTheme.labelSmall,
                    ),
                  ],
                ),
              ),
            ),
          ),
        ),
      ),
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
  staffDevices('management-staff-devices'),
  employeeActivity('management-employee-activity'),
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

const _metricActions = <ManagementDashboardMetricKey, _ManagementAction>{
  ManagementDashboardMetricKey.activeClients: _ManagementAction.loans,
  ManagementDashboardMetricKey.activeLoans: _ManagementAction.loans,
  ManagementDashboardMetricKey.overdueLoans: _ManagementAction.loans,
  ManagementDashboardMetricKey.outstandingBalance: _ManagementAction.loans,
  ManagementDashboardMetricKey.latestCollections:
      _ManagementAction.loanOperations,
  ManagementDashboardMetricKey.unremittedCollections:
      _ManagementAction.loanOperations,
  ManagementDashboardMetricKey.assignedRemittances:
      _ManagementAction.remittanceNotifications,
  ManagementDashboardMetricKey.protectedRenewals: _ManagementAction.renewals,
  ManagementDashboardMetricKey.staffRegistrations:
      _ManagementAction.staffDevices,
  ManagementDashboardMetricKey.clientRegistrations:
      _ManagementAction.clientRegistrationApprovals,
  ManagementDashboardMetricKey.collectorMobileDevices:
      _ManagementAction.staffDevices,
  ManagementDashboardMetricKey.borrowerSupport: _ManagementAction.support,
  ManagementDashboardMetricKey.unreadActivity: _ManagementAction.alertsActivity,
};

class _ManagementModule {
  const _ManagementModule(
    this.title,
    this.description,
    this.icon, {
    required this.action,
    this.requiredPermissions = const <String>[],
    this.permissionMode = _PermissionMode.all,
  });

  final String title;
  final String description;
  final IconData icon;
  final _ManagementAction action;
  final List<String> requiredPermissions;
  final _PermissionMode permissionMode;

  bool isAvailableFor(UserSession session) {
    return switch (permissionMode) {
      _PermissionMode.all => requiredPermissions.every(session.hasPermission),
      _PermissionMode.any => requiredPermissions.any(session.hasPermission),
    };
  }
}

enum _PermissionMode { all, any }

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
    title: 'People, access & requests',
    description: 'Manage staff access, borrower requests, and support reviews.',
    modules: <_ManagementModule>[
      _ManagementModule(
        'Staff & devices',
        'Invite staff, review access, and manage registered devices',
        Icons.manage_accounts_outlined,
        action: _ManagementAction.staffDevices,
        requiredPermissions: <String>['account.manage', 'device.manage'],
        permissionMode: _PermissionMode.any,
      ),
      _ManagementModule(
        'Employee activity',
        'Review authorized Employee work, approvals, and exceptions',
        Icons.manage_search_outlined,
        action: _ManagementAction.employeeActivity,
        requiredPermissions: <String>['employee.activity.review'],
      ),
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
