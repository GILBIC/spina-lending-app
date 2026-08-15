import 'package:flutter/material.dart';
import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/device/device_identity.dart';
import 'package:gilbic_mobile/src/core/management/management_loan.dart';
import 'package:gilbic_mobile/src/core/management/management_loan_repository.dart';
import 'package:gilbic_mobile/src/core/management/management_operations.dart';
import 'package:gilbic_mobile/src/core/management/management_operations_repository.dart';
import 'package:gilbic_mobile/src/core/network/spina_api.dart';

class ManagementOperationalOverviewPage extends StatefulWidget {
  const ManagementOperationalOverviewPage({
    required this.session,
    required this.deviceIdentityProvider,
    this.loanRepository,
    this.operationsRepository,
    super.key,
  });

  final UserSession session;
  final DeviceIdentityProvider deviceIdentityProvider;
  final ManagementLoanRepository? loanRepository;
  final ManagementOperationsRepository? operationsRepository;

  @override
  State<ManagementOperationalOverviewPage> createState() =>
      _ManagementOperationalOverviewPageState();
}

class _ManagementOperationalOverviewPageState
    extends State<ManagementOperationalOverviewPage> {
  late final ManagementLoanRepository _loanRepository;
  late final ManagementOperationsRepository _operationsRepository;
  ManagementLoanPortfolio? _loans;
  ManagementOperationsOverview? _operations;
  String? _errorMessage;
  bool _loading = true;

  @override
  void initState() {
    super.initState();
    _loanRepository = widget.loanRepository ?? SpinaManagementLoanRepository();
    _operationsRepository =
        widget.operationsRepository ?? SpinaManagementOperationsRepository();
    _load();
  }

  Future<void> _load() async {
    if (mounted) {
      setState(() {
        _loading = true;
        _errorMessage = null;
      });
    }
    try {
      final identity = await widget.deviceIdentityProvider.load();
      final loans = await _loanRepository.loadPortfolio(
        widget.session,
        deviceId: identity.installationId,
        query: '',
        status: 'active',
      );
      final operations = await _operationsRepository.loadOverview(
        widget.session,
        deviceId: identity.installationId,
        query: '',
        status: 'all',
      );
      if (!mounted) {
        return;
      }
      setState(() {
        _loans = loans;
        _operations = operations;
      });
    } on SpinaApiException catch (error) {
      if (mounted) {
        setState(() => _errorMessage = error.message);
      }
    } on Object {
      if (mounted) {
        setState(() {
          _errorMessage = 'Management overview could not be loaded.';
        });
      }
    } finally {
      if (mounted) {
        setState(() => _loading = false);
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      key: const Key('management-operational-overview-page'),
      appBar: AppBar(
        title: const Text('Management Overview'),
        actions: [
          IconButton(
            tooltip: 'Refresh overview',
            onPressed: _loading ? null : _load,
            icon: const Icon(Icons.refresh),
          ),
        ],
      ),
      body: SafeArea(child: _buildBody()),
    );
  }

  Widget _buildBody() {
    final loans = _loans;
    final operations = _operations;
    if (_loading && (loans == null || operations == null)) {
      return const Center(child: CircularProgressIndicator());
    }
    if (_errorMessage != null && (loans == null || operations == null)) {
      return _OverviewError(message: _errorMessage!, onRetry: _load);
    }
    if (loans == null || operations == null) {
      return const SizedBox.shrink();
    }

    final loanSummary = loans.summary;
    final operationSummary = operations.summary;
    final alerts = _alerts(loanSummary, operationSummary);

    return RefreshIndicator(
      onRefresh: _load,
      child: ListView(
        physics: const AlwaysScrollableScrollPhysics(),
        padding: const EdgeInsets.fromLTRB(16, 16, 16, 28),
        children: [
          const Card(
            child: Padding(
              padding: EdgeInsets.all(14),
              child: Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Icon(Icons.verified_user_outlined),
                  SizedBox(width: 12),
                  Expanded(
                    child: Text(
                      'Read-only operational overview from the same protected SPINA loan and collection APIs. Server authorization remains authoritative.',
                    ),
                  ),
                ],
              ),
            ),
          ),
          if (_errorMessage != null) ...[
            const SizedBox(height: 10),
            Card(
              child: Padding(
                padding: const EdgeInsets.all(12),
                child: Text(
                  _errorMessage!,
                  style: TextStyle(color: Theme.of(context).colorScheme.error),
                ),
              ),
            ),
          ],
          const SizedBox(height: 16),
          Text('Portfolio', style: Theme.of(context).textTheme.titleLarge),
          const SizedBox(height: 8),
          _MetricGrid(
            metrics: <_OverviewMetric>[
              _OverviewMetric(
                'Active clients',
                '${loanSummary.activeClientCount}',
                'Borrowers with active loans',
                Icons.people_outline,
              ),
              _OverviewMetric(
                'Active loans',
                '${loanSummary.activeLoanCount}',
                '${loanSummary.activeSevenBySevenCount} are 7x7',
                Icons.account_balance_outlined,
              ),
              _OverviewMetric(
                'Remaining balance',
                _money(loanSummary.activeRemainingTotal),
                'Authoritative active portfolio',
                Icons.account_balance_wallet_outlined,
              ),
              _OverviewMetric(
                'Overdue active',
                '${loanSummary.overdueActiveCount}',
                'Needs Management review',
                Icons.warning_amber_outlined,
              ),
            ],
          ),
          const SizedBox(height: 18),
          Text('Collections & custody',
              style: Theme.of(context).textTheme.titleLarge),
          const SizedBox(height: 8),
          _MetricGrid(
            metrics: <_OverviewMetric>[
              _OverviewMetric(
                'Latest collections',
                _money(operationSummary.latestDayAmount),
                _latestDayLabel(operationSummary),
                Icons.payments_outlined,
              ),
              _OverviewMetric(
                'Unremitted cash',
                _money(operationSummary.unremittedAmount),
                '${operationSummary.unremittedEntryCount} entries',
                Icons.wallet_outlined,
              ),
              _OverviewMetric(
                'Pending remittance',
                _money(operationSummary.pendingRemittanceAmount),
                '${operationSummary.pendingRemittanceCount} submissions',
                Icons.hourglass_top,
              ),
              _OverviewMetric(
                'Received remittance',
                _money(operationSummary.receivedRemittanceAmount),
                '${operationSummary.receivedRemittanceCount} received',
                Icons.verified_outlined,
              ),
            ],
          ),
          const SizedBox(height: 18),
          Text('Actionable alerts',
              style: Theme.of(context).textTheme.titleLarge),
          const SizedBox(height: 8),
          if (alerts.isEmpty)
            const Card(
              key: Key('management-overview-no-alerts'),
              child: Padding(
                padding: EdgeInsets.all(18),
                child: Row(
                  children: [
                    Icon(Icons.check_circle_outline),
                    SizedBox(width: 10),
                    Expanded(
                      child: Text(
                        'No overdue, remittance, custody, or approved-renewal alert is present in the current server summaries.',
                      ),
                    ),
                  ],
                ),
              ),
            )
          else
            for (final alert in alerts) ...[
              Card(
                key: Key('management-overview-alert-${alert.code}'),
                child: ListTile(
                  leading: Icon(alert.icon),
                  title: Text(alert.title),
                  subtitle: Text(alert.detail),
                ),
              ),
              const SizedBox(height: 6),
            ],
          const SizedBox(height: 12),
          Text(
            'Staff/device status, client registration approvals, and additional review queues are completed in the next C2 slices. This overview does not create or post any financial transaction.',
            style: Theme.of(context).textTheme.bodySmall,
            textAlign: TextAlign.center,
          ),
        ],
      ),
    );
  }
}

List<_OverviewAlert> _alerts(
  ManagementLoanSummary loans,
  ManagementOperationsSummary operations,
) {
  final alerts = <_OverviewAlert>[];
  if (loans.overdueActiveCount > 0) {
    alerts.add(
      _OverviewAlert(
        'overdue',
        'Overdue active loans',
        '${loans.overdueActiveCount} active loan(s) are overdue.',
        Icons.warning_amber_outlined,
      ),
    );
  }
  if (operations.unremittedEntryCount > 0) {
    alerts.add(
      _OverviewAlert(
        'unremitted',
        'Cash awaiting remittance',
        '${operations.unremittedEntryCount} collection entr${operations.unremittedEntryCount == 1 ? 'y is' : 'ies are'} still unremitted (${_money(operations.unremittedAmount)}).',
        Icons.account_balance_wallet_outlined,
      ),
    );
  }
  if (operations.pendingRemittanceCount > 0) {
    alerts.add(
      _OverviewAlert(
        'pending-remittance',
        'Remittance awaiting receipt',
        '${operations.pendingRemittanceCount} remittance(s) are submitted and awaiting receipt (${_money(operations.pendingRemittanceAmount)}).',
        Icons.hourglass_top,
      ),
    );
  }
  if (loans.approvedRenewalCount > 0) {
    alerts.add(
      _OverviewAlert(
        'approved-renewal',
        'Approved renewals awaiting office processing',
        '${loans.approvedRenewalCount} approved renewal(s) remain in the active portfolio summary.',
        Icons.autorenew,
      ),
    );
  }
  return alerts;
}

class _OverviewMetric {
  const _OverviewMetric(this.label, this.value, this.detail, this.icon);

  final String label;
  final String value;
  final String detail;
  final IconData icon;
}

class _OverviewAlert {
  const _OverviewAlert(this.code, this.title, this.detail, this.icon);

  final String code;
  final String title;
  final String detail;
  final IconData icon;
}

class _MetricGrid extends StatelessWidget {
  const _MetricGrid({required this.metrics});

  final List<_OverviewMetric> metrics;

  @override
  Widget build(BuildContext context) {
    return GridView.builder(
      shrinkWrap: true,
      physics: const NeverScrollableScrollPhysics(),
      itemCount: metrics.length,
      gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
        crossAxisCount: 2,
        mainAxisExtent: 124,
        crossAxisSpacing: 10,
        mainAxisSpacing: 10,
      ),
      itemBuilder: (context, index) {
        final metric = metrics[index];
        return Card(
          child: Padding(
            padding: const EdgeInsets.all(12),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Icon(metric.icon, size: 21),
                const Spacer(),
                Text(
                  metric.value,
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: Theme.of(context).textTheme.titleMedium,
                ),
                Text(metric.label,
                    maxLines: 1, overflow: TextOverflow.ellipsis),
                Text(
                  metric.detail,
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: Theme.of(context).textTheme.bodySmall,
                ),
              ],
            ),
          ),
        );
      },
    );
  }
}

class _OverviewError extends StatelessWidget {
  const _OverviewError({required this.message, required this.onRetry});

  final String message;
  final VoidCallback onRetry;

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(24),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(Icons.error_outline,
                size: 48, color: Theme.of(context).colorScheme.error),
            const SizedBox(height: 12),
            Text(message, textAlign: TextAlign.center),
            const SizedBox(height: 16),
            FilledButton.icon(
              key: const Key('management-overview-retry'),
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

String _latestDayLabel(ManagementOperationsSummary summary) {
  final value = summary.latestCollectionDate;
  if (value == null) {
    return 'No collection date yet';
  }
  return '${value.year.toString().padLeft(4, '0')}-'
      '${value.month.toString().padLeft(2, '0')}-'
      '${value.day.toString().padLeft(2, '0')} • '
      '${summary.latestDayPaymentCount} payment(s)';
}

String _money(double value) {
  final parts = value.toStringAsFixed(2).split('.');
  final whole = parts.first.replaceAllMapped(
    RegExp(r'\B(?=(\d{3})+(?!\d))'),
    (_) => ',',
  );
  return '₱$whole.${parts.last}';
}
