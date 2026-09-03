import 'package:flutter/material.dart';
import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/device/device_identity.dart';
import 'package:gilbic_mobile/src/core/loans/client_loan.dart';
import 'package:gilbic_mobile/src/core/loans/client_loan_repository.dart';
import 'package:gilbic_mobile/src/core/network/spina_api.dart';
import 'package:gilbic_mobile/src/features/account/account_settings_page.dart';
import 'package:gilbic_mobile/src/features/client/client_loans_page.dart';
import 'package:gilbic_mobile/src/features/client/client_payments_page.dart';
import 'package:gilbic_mobile/src/features/client/client_renewal_page.dart';
import 'package:gilbic_mobile/src/features/client/client_support_page.dart';
import 'package:gilbic_mobile/src/features/notifications/activity_notifications_page.dart';
import 'package:gilbic_mobile/src/features/notifications/notification_center_page.dart';
import 'package:gilbic_mobile/src/features/offline/mobile_offline_policy_page.dart';

class ClientDashboard extends StatefulWidget {
  const ClientDashboard({
    required this.session,
    required this.onSignOut,
    required this.deviceIdentityProvider,
    this.loanRepository,
    super.key,
  });

  final UserSession session;
  final Future<void> Function() onSignOut;
  final DeviceIdentityProvider deviceIdentityProvider;
  final ClientLoanRepository? loanRepository;

  @override
  State<ClientDashboard> createState() => _ClientDashboardState();
}

class _ClientDashboardState extends State<ClientDashboard> {
  late final ClientLoanRepository _loanRepository;
  ClientLoanPortfolio? _portfolio;
  String? _errorMessage;
  bool _loading = true;

  @override
  void initState() {
    super.initState();
    _loanRepository = widget.loanRepository ?? SpinaClientLoanRepository();
    _loadPortfolio();
  }

  Future<void> _loadPortfolio() async {
    setState(() {
      _loading = true;
      _errorMessage = null;
    });
    try {
      final identity = await widget.deviceIdentityProvider.load();
      final portfolio = await _loanRepository.loadPortfolio(
        widget.session,
        deviceId: identity.installationId,
      );
      if (!mounted) return;
      setState(() => _portfolio = portfolio);
    } on SpinaApiException catch (error) {
      if (!mounted) return;
      setState(() => _errorMessage = _clientHomeFailureMessage(error));
    } on Object {
      if (!mounted) return;
      setState(
        () => _errorMessage =
            'Your latest loan information could not be loaded. Try again in a moment.',
      );
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

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
          'Your current server permissions do not allow $title. Sign in again or contact Management.',
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

  void _openAccount() {
    _push(
      AccountSettingsPage(
        session: widget.session,
        onSignOut: widget.onSignOut,
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

  void _openOfflinePolicy() {
    _push(MobileOfflinePolicyPage(session: widget.session));
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('SPINA'),
        actions: [
          IconButton(
            key: const Key('open-offline-policy'),
            tooltip: 'Offline & sync',
            onPressed: _openOfflinePolicy,
            icon: const Icon(Icons.cloud_off_outlined),
          ),
          IconButton(
            key: const Key('open-notification-center'),
            tooltip: 'Notifications',
            onPressed: _openNotifications,
            icon: const Icon(Icons.notifications_outlined),
          ),
          IconButton(
            key: const Key('open-account-settings'),
            tooltip: 'Profile & security',
            onPressed: _openAccount,
            icon: const Icon(Icons.account_circle_outlined),
          ),
          IconButton(
            tooltip: 'Sign out',
            onPressed: widget.onSignOut,
            icon: const Icon(Icons.logout),
          ),
        ],
      ),
      body: SafeArea(
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
                'Review your official SPINA records and choose what you need next.',
                style: Theme.of(context).textTheme.bodyMedium,
              ),
              const SizedBox(height: 20),
              _CurrentLoansSection(
                portfolio: _portfolio,
                loading: _loading,
                errorMessage: _errorMessage,
                onRetry: _loadPortfolio,
                onOpenLoans: _openLoans,
              ),
              const SizedBox(height: 22),
              Text(
                'Next actions',
                style: Theme.of(context).textTheme.titleLarge,
              ),
              const SizedBox(height: 4),
              Text(
                'These pages are view-only unless a protected client action is clearly offered.',
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
                key: const Key('client-home-payments'),
                title: 'Payments & official receipts',
                description:
                    'Timeline, statement, receipts, and direct-payment status',
                icon: Icons.receipt_long_outlined,
                onTap: _openPayments,
              ),
              _ClientActionRow(
                key: const Key('client-home-payment-updates'),
                title: 'Payment updates',
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
    );
  }
}

class _CurrentLoansSection extends StatelessWidget {
  const _CurrentLoansSection({
    required this.portfolio,
    required this.loading,
    required this.errorMessage,
    required this.onRetry,
    required this.onOpenLoans,
  });

  final ClientLoanPortfolio? portfolio;
  final bool loading;
  final String? errorMessage;
  final VoidCallback onRetry;
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
        Row(
          children: [
            Expanded(
              child: Text(
                'Current loans',
                style: Theme.of(context).textTheme.titleLarge,
              ),
            ),
            if (portfolio != null) Chip(label: Text(countLabel)),
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
          _ClientHomeError(message: errorMessage!, onRetry: onRetry)
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
              child: _ClientLoanSummaryRow(loan: loan, onTap: onOpenLoans),
            ),
        if (errorMessage != null && portfolio != null) ...[
          const SizedBox(height: 4),
          _ClientHomeError(message: errorMessage!, onRetry: onRetry),
        ],
      ],
    );
  }
}

class _ClientLoanSummaryRow extends StatelessWidget {
  const _ClientLoanSummaryRow({required this.loan, required this.onTap});

  final ClientLoan loan;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final colors = Theme.of(context).colorScheme;
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
                  Chip(
                    visualDensity: VisualDensity.compact,
                    label: Text(_titleCase(loan.status)),
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
    return Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Expanded(child: Text(label, style: style)),
        const SizedBox(width: 12),
        Text(value, style: style, textAlign: TextAlign.right),
      ],
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

class _ClientHomeError extends StatelessWidget {
  const _ClientHomeError({required this.message, required this.onRetry});

  final String message;
  final VoidCallback onRetry;

  @override
  Widget build(BuildContext context) {
    final colors = Theme.of(context).colorScheme;
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(14),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Icon(Icons.info_outline, color: colors.error),
                const SizedBox(width: 10),
                Expanded(child: Text(message)),
              ],
            ),
            const SizedBox(height: 10),
            OutlinedButton.icon(
              key: const Key('client-home-retry'),
              onPressed: onRetry,
              icon: const Icon(Icons.refresh),
              label: const Text('Try again'),
            ),
          ],
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

String _money(double value) {
  final parts = value.toStringAsFixed(2).split('.');
  final whole = parts.first.replaceAllMapped(
    RegExp(r'\B(?=(\d{3})+(?!\d))'),
    (_) => ',',
  );
  return '₱$whole.${parts.last}';
}

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
