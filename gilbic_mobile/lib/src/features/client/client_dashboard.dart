import 'package:gilbic_mobile/src/features/treasury/treasury_workspace_page.dart';
import 'dart:async';
import 'package:gilbic_mobile/src/features/shared/spina_status.dart';
import 'package:gilbic_mobile/src/features/shared/daily_workspace_widgets.dart';
import 'package:flutter/material.dart';
import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/device/device_identity.dart';
import 'package:gilbic_mobile/src/core/loans/client_loan.dart';
import 'package:gilbic_mobile/src/core/loans/client_loan_repository.dart';
import 'package:gilbic_mobile/src/core/loans/client_schedule.dart';
import 'package:gilbic_mobile/src/core/loans/client_schedule_repository.dart';
import 'package:gilbic_mobile/src/core/network/spina_api.dart';
import 'package:gilbic_mobile/src/features/client/client_loans_page.dart';
import 'package:gilbic_mobile/src/features/client/client_payments_page.dart';
import 'package:gilbic_mobile/src/features/client/client_renewal_page.dart';
import 'package:gilbic_mobile/src/features/client/client_support_page.dart';
import 'package:gilbic_mobile/src/features/notifications/activity_notifications_page.dart';
import 'package:gilbic_mobile/src/features/notifications/notification_center_page.dart';

class ClientDashboard extends StatefulWidget {
  const ClientDashboard({
    required this.session,
    required this.onSignOut,
    required this.deviceIdentityProvider,
    this.loanRepository,
    this.scheduleRepository,
    super.key,
  });

  final UserSession session;
  final Future<void> Function() onSignOut;
  final DeviceIdentityProvider deviceIdentityProvider;
  final ClientLoanRepository? loanRepository;
  final ClientScheduleRepository? scheduleRepository;

  @override
  State<ClientDashboard> createState() => _ClientDashboardState();
}

class _ClientDashboardState extends State<ClientDashboard> {
  late ClientLoanRepository _loanRepository;
  late ClientScheduleRepository _scheduleRepository;
  ClientLoanPortfolio? _portfolio;
  Map<String, ClientLoanSchedule> _homeObligationSchedules = const {};
  String? _errorMessage;
  bool _loading = true;
  int _generation = 0;
  int? _failureStatus;
  final _scheduleLoading = <String>{};
  final _scheduleUnavailable = <String>{};

  @override
  void initState() {
    super.initState();
    _loanRepository = widget.loanRepository ?? SpinaClientLoanRepository();
    _scheduleRepository =
        widget.scheduleRepository ?? SpinaClientScheduleRepository();
    _loadPortfolio();
  }

  @override
  void didUpdateWidget(ClientDashboard oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.session != widget.session ||
        oldWidget.deviceIdentityProvider != widget.deviceIdentityProvider ||
        oldWidget.loanRepository != widget.loanRepository ||
        oldWidget.scheduleRepository != widget.scheduleRepository) {
      _portfolio = null;
      _homeObligationSchedules = const {};
      _scheduleLoading.clear();
      _scheduleUnavailable.clear();
      _loanRepository = widget.loanRepository ?? SpinaClientLoanRepository();
      _scheduleRepository =
          widget.scheduleRepository ?? SpinaClientScheduleRepository();
      unawaited(_loadPortfolio());
    }
  }

  bool _current(int generation) => mounted && generation == _generation;

  void _failedRead(Object error, int generation) {
    if (!_current(generation)) return;
    setState(() {
      _failureStatus = error is SpinaApiException ? error.statusCode : null;
      _errorMessage = error is SpinaApiException
          ? _clientHomeFailureMessage(error)
          : 'Your latest loan information could not be loaded. Try again in a moment.';
      if (_failureStatus == 401 || _failureStatus == 403) {
        _generation++;
        _portfolio = null;
        _homeObligationSchedules = const {};
        _scheduleLoading.clear();
        _scheduleUnavailable.clear();
        _loading = false;
      }
    });
  }

  Future<void> _loadPortfolio() async {
    final generation = ++_generation;
    final session = widget.session;
    final repository = _loanRepository;
    setState(() {
      _loading = true;
      _errorMessage = null;
      _failureStatus = null;
      _scheduleLoading.clear();
    });
    try {
      final identity = await widget.deviceIdentityProvider.load();
      if (!_current(generation)) return;
      final portfolio = await repository.loadPortfolio(
        session,
        deviceId: identity.installationId,
      );
      if (!_current(generation)) return;
      setState(() {
        _portfolio = portfolio;
        _homeObligationSchedules = const {};
        _scheduleUnavailable.clear();
        _loading = false;
      });
      for (final loan in portfolio.activeLoans.where(
        (loan) => loan.isSevenBySeven,
      )) {
        unawaited(_loadScheduleForLoan(loan.loanId));
      }
    } on Object catch (error) {
      _failedRead(error, generation);
    } finally {
      if (_current(generation)) setState(() => _loading = false);
    }
  }

  Future<void> _loadScheduleForLoan(String loanId) async {
    if (_scheduleLoading.contains(loanId) ||
        !(_portfolio?.activeLoans.any((loan) => loan.loanId == loanId) ??
            false)) {
      return;
    }
    final generation = _generation;
    final session = widget.session;
    final repository = _scheduleRepository;
    setState(() {
      _scheduleLoading.add(loanId);
      _scheduleUnavailable.remove(loanId);
    });
    bool valid() =>
        _current(generation) &&
        (_portfolio?.activeLoans.any((loan) => loan.loanId == loanId) ?? false);
    try {
      final identity = await widget.deviceIdentityProvider.load();
      if (!valid()) return;
      final schedule = await repository.loadSchedule(
        session,
        deviceId: identity.installationId,
        loanId: loanId,
      );
      if (!valid()) return;
      if (schedule.loanId != loanId) {
        throw const SpinaApiException(
          'Schedule identity unavailable',
          code: 'invalid_client_schedule_payload',
        );
      }
      setState(
        () => _homeObligationSchedules = {
          ..._homeObligationSchedules,
          loanId: schedule,
        },
      );
    } on Object catch (error) {
      if (!valid()) return;
      if (error is SpinaApiException &&
          (error.statusCode == 401 || error.statusCode == 403)) {
        _failedRead(error, generation);
      } else {
        setState(() => _scheduleUnavailable.add(loanId));
      }
    } finally {
      if (valid()) setState(() => _scheduleLoading.remove(loanId));
    }
  }

  String get _recoveryLabel => switch (_failureStatus) {
    401 => 'Sign in again',
    403 => 'Access unavailable',
    _ => 'Retry',
  };

  void _push(Widget page) {
    Navigator.of(
      context,
    ).push(MaterialPageRoute<void>(builder: (context) => page));
  }

  bool _canOpen(String title) {
    if (widget.session.hasPermission('loan.self.view')) return true;
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text(
          'Your account does not have access to $title. Sign in again or contact Management.',
        ),
      ),
    );
    return false;
  }

  void _openLoans() {
    if (!_canOpen('My loans')) return;
    _push(
      ClientLoansPage(
        session: widget.session,
        deviceIdentityProvider: widget.deviceIdentityProvider,
        repository: _loanRepository,
      ),
    );
  }

  void _openPayments() {
    if (!_canOpen('Payments & receipts')) return;
    _push(
      ClientPaymentsPage(
        session: widget.session,
        deviceIdentityProvider: widget.deviceIdentityProvider,
      ),
    );
  }

  void _openPaymentUpdates() {
    if (!_canOpen('Payment updates')) return;
    _push(
      ActivityNotificationsPage(
        session: widget.session,
        deviceIdentityProvider: widget.deviceIdentityProvider,
      ),
    );
  }

  void _openRenewal() {
    if (!_canOpen('Renewal status')) return;
    _push(
      ClientRenewalPage(
        session: widget.session,
        deviceIdentityProvider: widget.deviceIdentityProvider,
      ),
    );
  }

  void _openSupport() {
    if (!_canOpen('Support')) return;
    _push(
      ClientSupportPage(
        session: widget.session,
        deviceIdentityProvider: widget.deviceIdentityProvider,
      ),
    );
  }

  void _openNotifications() {
    _push(
      NotificationCenterPage(
        session: widget.session,
        deviceIdentityProvider: widget.deviceIdentityProvider,
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('My day'),
        actions: [
          IconButton(
            key: const Key('open-notification-center'),
            tooltip: 'Notifications',
            onPressed: _openNotifications,
            icon: const Icon(Icons.notifications_outlined),
          ),
          WorkspaceAccountMenu(
            session: widget.session,
            deviceIdentityProvider: widget.deviceIdentityProvider,
            onSignOut: widget.onSignOut,
          ),
        ],
      ),
      body: SafeArea(
        child: WorkspaceBody(
          child: RefreshIndicator(
            onRefresh: _loadPortfolio,
            child: ListView(
              key: const Key('client-dashboard-list'),
              physics: const AlwaysScrollableScrollPhysics(),
              padding: const EdgeInsets.fromLTRB(16, 16, 16, 28),
              children: [
                Text(
                  'Welcome, ${widget.session.displayName}',
                  style: Theme.of(context).textTheme.headlineSmall,
                ),
                const SizedBox(height: 5),
                Text(
                  'Your loans and payments, in one place.',
                  style: Theme.of(context).textTheme.bodyMedium,
                ),
                const SizedBox(height: 20),
                _CurrentLoansSection(
                  portfolio: _portfolio,
                  homeObligationSchedules: _homeObligationSchedules,
                  loading: _loading,
                  errorMessage: _errorMessage,
                  onRetry: _failureStatus == 401
                      ? () => unawaited(widget.onSignOut())
                      : _failureStatus == 403
                      ? null
                      : _loadPortfolio,
                  recoveryLabel: _recoveryLabel,
                  scheduleLoading: _scheduleLoading,
                  scheduleUnavailable: _scheduleUnavailable,
                  onRetrySchedule: _loadScheduleForLoan,
                  onOpenLoans: _openLoans,
                ),
                const SizedBox(height: 22),
                Text(
                  'Next actions',
                  style: Theme.of(context).textTheme.titleLarge,
                ),
                const SizedBox(height: 4),
                Text(
                  'Choose a task to continue.',
                  style: Theme.of(context).textTheme.bodyMedium,
                ),
                const SizedBox(height: 8),
                _ClientActionRow(
                  key: const Key('client-home-loans'),
                  title: 'My loans',
                  description: 'Balances, schedules, and loan history',
                  icon: Icons.account_balance_wallet_outlined,
                  onTap: _openLoans,
                ),
                _ClientActionRow(
                  key: const Key('client-home-treasury'),
                  title: 'Cash and GCash payment proof',
                  description:
                      'Receiving instructions, own proof and recording status',
                  icon: Icons.account_balance_wallet_outlined,
                  onTap: () => Navigator.of(context).push<void>(
                    MaterialPageRoute(
                      builder: (_) => TreasuryWorkspacePage(
                        session: widget.session,
                        deviceIdentityProvider: widget.deviceIdentityProvider,
                        borrowerChoices: _portfolio == null
                            ? const []
                            : [
                                {
                                  'client_id': _portfolio!.clientId,
                                  'name': _portfolio!.clientName,
                                  'loans': [
                                    for (final loan in _portfolio!.activeLoans)
                                      {
                                        'loan_id': loan.loanId,
                                        'loan_number': loan.loanNumber,
                                        'loan_type': loan.loanTypeName,
                                        'expected_version': loan.stateVersion,
                                      },
                                  ],
                                },
                              ],
                      ),
                    ),
                  ),
                ),
                _ClientActionRow(
                  key: const Key('client-home-payments'),
                  title: 'Payments & official receipts',
                  description:
                      'Timeline, statement, receipts, and direct-payment status',
                  icon: Icons.receipt_long_outlined,
                  onTap: _openPayments,
                ),
                _ClientActionRow(
                  key: const Key('client-home-payment-updates'),
                  title: 'Payment status',
                  description:
                      'See recorded, remitted, accepted, or corrected activity',
                  icon: Icons.notifications_active_outlined,
                  onTap: _openPaymentUpdates,
                ),
                _ClientActionRow(
                  key: const Key('client-home-renewal'),
                  title: 'Renewal status',
                  description: 'Request renewal and follow its review status',
                  icon: Icons.autorenew,
                  onTap: _openRenewal,
                ),
                _ClientActionRow(
                  key: const Key('client-home-support'),
                  title: 'Support',
                  description:
                      'Questions, concerns, follow-ups, and communication history',
                  icon: Icons.support_agent_outlined,
                  onTap: _openSupport,
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

class _CurrentLoansSection extends StatelessWidget {
  const _CurrentLoansSection({
    required this.portfolio,
    required this.homeObligationSchedules,
    required this.loading,
    required this.errorMessage,
    required this.onRetry,
    required this.onOpenLoans,
    required this.recoveryLabel,
    required this.scheduleLoading,
    required this.scheduleUnavailable,
    required this.onRetrySchedule,
  });

  final ClientLoanPortfolio? portfolio;
  final Map<String, ClientLoanSchedule> homeObligationSchedules;
  final bool loading;
  final String? errorMessage;
  final VoidCallback? onRetry;
  final String recoveryLabel;
  final Set<String> scheduleLoading;
  final Set<String> scheduleUnavailable;
  final ValueChanged<String> onRetrySchedule;
  final VoidCallback onOpenLoans;

  @override
  Widget build(BuildContext context) {
    final activeLoans = portfolio?.activeLoans ?? const <ClientLoan>[];
    final countLabel = switch (activeLoans.length) {
      0 => 'No active loan',
      1 => '1 active loan',
      _ => '${activeLoans.length} active loans',
    };
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Wrap(
          spacing: 12,
          runSpacing: 4,
          crossAxisAlignment: WrapCrossAlignment.center,
          children: [
            Text(
              'Current loans',
              style: Theme.of(context).textTheme.titleLarge,
            ),
            if (portfolio != null)
              Text(countLabel, style: Theme.of(context).textTheme.labelLarge),
          ],
        ),
        const SizedBox(height: 8),
        if (loading && portfolio == null)
          const Card(
            child: Padding(
              padding: EdgeInsets.all(20),
              child: Center(child: CircularProgressIndicator()),
            ),
          )
        else if (errorMessage != null && portfolio == null)
          WorkspaceReadNotice(
            key: const Key('client-home-retry'),
            message: errorMessage!,
            actionLabel: recoveryLabel,
            onAction: onRetry,
            stale: portfolio != null,
          )
        else if (activeLoans.isEmpty)
          Card(
            child: Padding(
              padding: const EdgeInsets.all(16),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    'You have no active loan',
                    style: Theme.of(context).textTheme.titleMedium,
                  ),
                  const SizedBox(height: 4),
                  const Text(
                    'Your loan history remains available in My loans.',
                  ),
                ],
              ),
            ),
          )
        else
          for (final loan in activeLoans)
            Padding(
              padding: const EdgeInsets.only(bottom: 8),
              child: _ClientLoanSummaryRow(
                loan: loan,
                obligationSchedule: homeObligationSchedules[loan.loanId],
                onTap: onOpenLoans,
                scheduleLoading: scheduleLoading.contains(loan.loanId),
                scheduleUnavailable: scheduleUnavailable.contains(loan.loanId),
                onRetrySchedule: () => onRetrySchedule(loan.loanId),
              ),
            ),
        if (errorMessage != null && portfolio != null) ...[
          const SizedBox(height: 4),
          WorkspaceReadNotice(
            key: const Key('client-home-retry'),
            message: errorMessage!,
            actionLabel: recoveryLabel,
            onAction: onRetry,
            stale: portfolio != null,
          ),
        ],
      ],
    );
  }
}

class _ClientLoanSummaryRow extends StatelessWidget {
  const _ClientLoanSummaryRow({
    required this.loan,
    required this.obligationSchedule,
    required this.scheduleLoading,
    required this.scheduleUnavailable,
    required this.onRetrySchedule,
    required this.onTap,
  });

  final ClientLoan loan;
  final ClientLoanSchedule? obligationSchedule;
  final bool scheduleLoading;
  final bool scheduleUnavailable;
  final VoidCallback onRetrySchedule;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final colors = Theme.of(context).colorScheme;
    final schedule = loan.isSevenBySeven ? obligationSchedule : null;
    final reviewReason = schedule?.managementReviewRequiredReason.trim() ?? '';
    final penaltyStatus = schedule?.penaltyStatus.trim().toLowerCase() ?? '';
    final managementReviewRequired =
        schedule != null &&
        (penaltyStatus == 'management_review_required' ||
            reviewReason.isNotEmpty);
    final showExactPayoff =
        schedule != null &&
        !managementReviewRequired &&
        const <String>{
          'projected',
          'penalty_outstanding',
          'cap_exhausted',
        }.contains(penaltyStatus);

    return Card(
      key: Key('client-home-loan-${loan.loanId}'),
      margin: EdgeInsets.zero,
      clipBehavior: Clip.antiAlias,
      child: InkWell(
        onTap: onTap,
        child: Padding(
          padding: const EdgeInsets.all(14),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              Wrap(
                spacing: 8,
                runSpacing: 4,
                crossAxisAlignment: WrapCrossAlignment.center,
                children: [
                  Icon(
                    loan.isSevenBySeven
                        ? Icons.grid_view_rounded
                        : Icons.receipt_long_outlined,
                    size: 20,
                    color: colors.primary,
                  ),
                  Text(
                    loan.loanTypeName,
                    style: Theme.of(context).textTheme.titleMedium,
                  ),
                  SpinaStatusLabel(
                    label: _titleCase(loan.status),
                    tone: SpinaStatusTone.information,
                  ),
                ],
              ),
              const SizedBox(height: 2),
              Text(
                loan.loanNumber,
                style: Theme.of(context).textTheme.bodySmall,
              ),
              const Divider(height: 18),
              _LoanAmountLine(
                label: 'Official remaining balance',
                value: _money(loan.remainingBalance),
                emphasized: true,
              ),
              const SizedBox(height: 5),
              _LoanAmountLine(
                label: 'Scheduled daily amount',
                value: _money(loan.dailyAmount),
              ),
              if (loan.dueDate != null) ...[
                const SizedBox(height: 5),
                _LoanAmountLine(label: 'Due date', value: _date(loan.dueDate!)),
              ],
              if (loan.isSevenBySeven && scheduleLoading) ...[
                const SizedBox(height: 8),
                const Text('Loading schedule/payoff information'),
              ],
              if (loan.isSevenBySeven && scheduleUnavailable)
                WorkspaceReadNotice(
                  message: 'Schedule/payoff information unavailable',
                  actionLabel: 'Retry schedule',
                  onAction: onRetrySchedule,
                ),
              if (managementReviewRequired) ...[
                const SizedBox(height: 10),
                Text(
                  'Management review required',
                  style: Theme.of(context).textTheme.titleSmall,
                ),
                if (reviewReason.isNotEmpty) ...[
                  const SizedBox(height: 3),
                  Text(reviewReason),
                ],
              ] else if (showExactPayoff) ...[
                const SizedBox(height: 8),
                _LoanAmountLine(
                  label: 'Exact payoff',
                  value: _money(schedule.exactPayoffTotal),
                  emphasized: true,
                ),
              ],
              const SizedBox(height: 8),
              Text(
                'Open schedule and details',
                textAlign: TextAlign.right,
                style: Theme.of(
                  context,
                ).textTheme.labelLarge?.copyWith(color: colors.primary),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _LoanAmountLine extends StatelessWidget {
  const _LoanAmountLine({
    required this.label,
    required this.value,
    this.emphasized = false,
  });

  final String label;
  final String value;
  final bool emphasized;

  @override
  Widget build(BuildContext context) {
    final style = emphasized ? Theme.of(context).textTheme.titleSmall : null;
    return LayoutBuilder(
      builder: (context, constraints) {
        final scale = MediaQuery.textScalerOf(context).scale(14) / 14;
        if (constraints.maxWidth < 350 || scale > 1.2 || value.length > 14) {
          return Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(label, style: style),
              Text(value, style: style),
            ],
          );
        }
        return Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Expanded(child: Text(label, style: style)),
            const SizedBox(width: 12),
            Text(value, style: style, textAlign: TextAlign.right),
          ],
        );
      },
    );
  }
}

class _ClientActionRow extends StatelessWidget {
  const _ClientActionRow({
    required this.title,
    required this.description,
    required this.icon,
    required this.onTap,
    super.key,
  });

  final String title;
  final String description;
  final IconData icon;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final colors = Theme.of(context).colorScheme;
    return Padding(
      padding: const EdgeInsets.only(bottom: 8),
      child: Card(
        margin: EdgeInsets.zero,
        clipBehavior: Clip.antiAlias,
        child: InkWell(
          onTap: onTap,
          child: Padding(
            padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
            child: Row(
              children: [
                Container(
                  width: 36,
                  height: 36,
                  decoration: BoxDecoration(
                    color: colors.primaryContainer,
                    borderRadius: BorderRadius.circular(11),
                  ),
                  child: Icon(icon, size: 20, color: colors.onPrimaryContainer),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        title,
                        style: Theme.of(context).textTheme.titleSmall,
                      ),
                      const SizedBox(height: 2),
                      Text(
                        description,
                        style: Theme.of(context).textTheme.bodySmall,
                      ),
                    ],
                  ),
                ),
                const SizedBox(width: 8),
                Icon(Icons.chevron_right, color: colors.onSurfaceVariant),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

String _clientHomeFailureMessage(SpinaApiException error) {
  if (error.statusCode == 401) {
    return 'Your session is no longer valid. Sign in again to refresh your loan information.';
  }
  if (error.statusCode == 403) {
    return 'This account or device is not allowed to view these loan records. Contact Management if this is unexpected.';
  }
  if (error.code == 'network_unavailable') {
    return 'SPINA could not refresh your loan information. Check your connection and try again.';
  }
  return 'Your latest loan information could not be loaded. Try again in a moment.';
}

String _money(String value) => formatClientLoanMoney(value);

String _date(DateTime value) {
  return '${value.year.toString().padLeft(4, '0')}-'
      '${value.month.toString().padLeft(2, '0')}-'
      '${value.day.toString().padLeft(2, '0')}';
}

String _titleCase(String value) {
  final normalized = value.trim();
  if (normalized.isEmpty) return 'Unknown';
  return normalized
      .split(RegExp(r'\s+'))
      .map(
        (part) => '${part[0].toUpperCase()}${part.substring(1).toLowerCase()}',
      )
      .join(' ');
}
