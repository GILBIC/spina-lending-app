import 'package:flutter/material.dart';
import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/device/device_identity.dart';
import 'package:gilbic_mobile/src/core/management/management_loan.dart';
import 'package:gilbic_mobile/src/core/management/management_loan_repository.dart';
import 'package:gilbic_mobile/src/core/network/spina_api.dart';

class ManagementLoanPortfolioPage extends StatefulWidget {
  const ManagementLoanPortfolioPage({
    required this.session,
    required this.deviceIdentityProvider,
    this.repository,
    super.key,
  });

  final UserSession session;
  final DeviceIdentityProvider deviceIdentityProvider;
  final ManagementLoanRepository? repository;

  @override
  State<ManagementLoanPortfolioPage> createState() =>
      _ManagementLoanPortfolioPageState();
}

class _ManagementLoanPortfolioPageState
    extends State<ManagementLoanPortfolioPage> {
  late final ManagementLoanRepository _repository;
  final TextEditingController _searchController = TextEditingController();
  ManagementLoanPortfolio? _portfolio;
  String _status = 'active';
  String? _deviceId;
  String? _errorMessage;
  bool _loading = true;

  @override
  void initState() {
    super.initState();
    _repository = widget.repository ?? SpinaManagementLoanRepository();
    _load();
  }

  @override
  void dispose() {
    _searchController.dispose();
    super.dispose();
  }

  Future<void> _load() async {
    setState(() {
      _loading = true;
      _errorMessage = null;
    });
    try {
      final identity = await widget.deviceIdentityProvider.load();
      final portfolio = await _repository.loadPortfolio(
        widget.session,
        deviceId: identity.installationId,
        query: _searchController.text,
        status: _status,
      );
      if (!mounted) {
        return;
      }
      setState(() {
        _deviceId = identity.installationId;
        _portfolio = portfolio;
      });
    } on SpinaApiException catch (error) {
      if (mounted) {
        setState(() => _errorMessage = error.message);
      }
    } on Object {
      if (mounted) {
        setState(() => _errorMessage = 'Loan Management could not be loaded.');
      }
    } finally {
      if (mounted) {
        setState(() => _loading = false);
      }
    }
  }

  void _clearSearch() {
    _searchController.clear();
    _load();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Loan Management'),
        actions: [
          IconButton(
            tooltip: 'Refresh loans',
            onPressed: _loading ? null : _load,
            icon: const Icon(Icons.refresh),
          ),
        ],
      ),
      body: SafeArea(child: _body()),
    );
  }

  Widget _body() {
    if (_loading && _portfolio == null) {
      return const Center(child: CircularProgressIndicator());
    }
    if (_errorMessage != null && _portfolio == null) {
      return _ErrorPanel(message: _errorMessage!, onRetry: _load);
    }
    final portfolio = _portfolio!;

    return RefreshIndicator(
      onRefresh: _load,
      child: ListView(
        physics: const AlwaysScrollableScrollPhysics(),
        padding: const EdgeInsets.fromLTRB(16, 16, 16, 28),
        children: [
          Card(
            child: Padding(
              padding: const EdgeInsets.all(14),
              child: Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Icon(Icons.visibility_outlined),
                  const SizedBox(width: 12),
                  Expanded(child: Text(portfolio.notice)),
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
          const SizedBox(height: 12),
          _SummaryGrid(summary: portfolio.summary),
          const SizedBox(height: 16),
          TextField(
            key: const Key('management-loan-search'),
            controller: _searchController,
            textInputAction: TextInputAction.search,
            onSubmitted: (_) => _load(),
            decoration: InputDecoration(
              labelText: 'Search client, code, loan, or area',
              prefixIcon: const Icon(Icons.search),
              suffixIcon: _searchController.text.trim().isEmpty
                  ? IconButton(
                      tooltip: 'Search',
                      onPressed: _loading ? null : _load,
                      icon: const Icon(Icons.arrow_forward),
                    )
                  : IconButton(
                      tooltip: 'Clear search',
                      onPressed: _loading ? null : _clearSearch,
                      icon: const Icon(Icons.clear),
                    ),
            ),
          ),
          const SizedBox(height: 10),
          DropdownButtonFormField<String>(
            key: const Key('management-loan-status-filter'),
            initialValue: _status,
            decoration: const InputDecoration(labelText: 'Loan status'),
            items: const [
              DropdownMenuItem(value: 'active', child: Text('Active')),
              DropdownMenuItem(value: 'paid', child: Text('Paid')),
              DropdownMenuItem(value: 'all', child: Text('All loans')),
            ],
            onChanged: _loading
                ? null
                : (value) {
                    if (value != null && value != _status) {
                      setState(() => _status = value);
                      _load();
                    }
                  },
          ),
          const SizedBox(height: 18),
          Row(
            children: [
              Text('Loan records', style: Theme.of(context).textTheme.titleMedium),
              const Spacer(),
              Text('${portfolio.loans.length} shown'),
            ],
          ),
          const SizedBox(height: 8),
          if (portfolio.loans.isEmpty)
            const Card(
              child: Padding(
                padding: EdgeInsets.all(24),
                child: Text(
                  'No loan record matches the selected filter.',
                  textAlign: TextAlign.center,
                ),
              ),
            )
          else
            for (final loan in portfolio.loans) ...[
              _ManagementLoanCard(loan: loan),
              const SizedBox(height: 10),
            ],
          if (_deviceId == null) const SizedBox.shrink(),
        ],
      ),
    );
  }
}

class _SummaryGrid extends StatelessWidget {
  const _SummaryGrid({required this.summary});

  final ManagementLoanSummary summary;

  @override
  Widget build(BuildContext context) {
    final items = <_MetricData>[
      _MetricData('Active loans', '${summary.activeLoanCount}', Icons.receipt_long),
      _MetricData('Active clients', '${summary.activeClientCount}', Icons.people),
      _MetricData(
        'Outstanding',
        _money(summary.activeRemainingTotal),
        Icons.account_balance_wallet_outlined,
      ),
      _MetricData(
        'Active principal',
        _money(summary.activePrincipalTotal),
        Icons.payments_outlined,
      ),
      _MetricData('Overdue', '${summary.overdueActiveCount}', Icons.warning_amber),
      _MetricData(
        '7x7 active',
        '${summary.activeSevenBySevenCount}',
        Icons.grid_view_rounded,
      ),
      _MetricData(
        'Approved renewals',
        '${summary.approvedRenewalCount}',
        Icons.autorenew,
      ),
    ];
    return GridView.builder(
      shrinkWrap: true,
      physics: const NeverScrollableScrollPhysics(),
      itemCount: items.length,
      gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
        crossAxisCount: 2,
        mainAxisExtent: 104,
        crossAxisSpacing: 10,
        mainAxisSpacing: 10,
      ),
      itemBuilder: (context, index) => _MetricCard(data: items[index]),
    );
  }
}

class _MetricData {
  const _MetricData(this.label, this.value, this.icon);

  final String label;
  final String value;
  final IconData icon;
}

class _MetricCard extends StatelessWidget {
  const _MetricCard({required this.data});

  final _MetricData data;

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Icon(data.icon, size: 22),
            const Spacer(),
            Text(
              data.value,
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
              style: Theme.of(context).textTheme.titleMedium,
            ),
            Text(data.label, maxLines: 1, overflow: TextOverflow.ellipsis),
          ],
        ),
      ),
    );
  }
}

class _ManagementLoanCard extends StatelessWidget {
  const _ManagementLoanCard({required this.loan});

  final ManagementLoanItem loan;

  @override
  Widget build(BuildContext context) {
    return Card(
      key: Key('management-loan-${loan.loanId}'),
      clipBehavior: Clip.antiAlias,
      child: ExpansionTile(
        initiallyExpanded: loan.renewalRequestStatus == 'approved',
        leading: Icon(
          loan.isSevenBySeven ? Icons.grid_view_rounded : Icons.receipt_long,
        ),
        title: Text(loan.clientName),
        subtitle: Text(
          '${loan.clientCode} • ${loan.loanTypeName}\n${loan.loanNumber}',
        ),
        trailing: _StatusChip(loan: loan),
        childrenPadding: const EdgeInsets.fromLTRB(16, 0, 16, 16),
        children: [
          if (loan.renewalRequestStatus != null) ...[
            Container(
              width: double.infinity,
              padding: const EdgeInsets.all(10),
              decoration: BoxDecoration(
                color: Theme.of(context).colorScheme.secondaryContainer,
                borderRadius: BorderRadius.circular(10),
              ),
              child: Text(
                loan.renewalRequestStatus == 'approved'
                    ? 'Renewal approved and awaiting SPINA office processing.'
                    : 'Renewal request is pending Management review.',
              ),
            ),
            const SizedBox(height: 12),
          ],
          _ValueRow(
            label: 'Official remaining balance',
            value: _money(loan.remainingBalance),
            emphasized: true,
          ),
          _ValueRow(label: 'Principal', value: _money(loan.principal)),
          _ValueRow(label: 'Paid toward balance', value: _money(loan.paidAmount)),
          _ValueRow(label: 'Daily amount', value: _money(loan.dailyAmount)),
          if (loan.interestRate != null)
            _ValueRow(
              label: 'Interest rate',
              value: '${_trimNumber(loan.interestRate!)}%',
            ),
          const SizedBox(height: 8),
          LinearProgressIndicator(
            value: (loan.paidPercent / 100).clamp(0.0, 1.0),
          ),
          const SizedBox(height: 5),
          Align(
            alignment: Alignment.centerRight,
            child: Text('${loan.paidPercent.toStringAsFixed(1)}% paid'),
          ),
          const Divider(height: 24),
          _DetailRow(label: 'Area', value: loan.clientArea ?? 'Not assigned'),
          _DetailRow(label: 'Released', value: _date(loan.dateReleased)),
          _DetailRow(label: 'Due date', value: _date(loan.dueDate)),
          _DetailRow(
            label: 'Last payment',
            value: _date(loan.lastPaymentDate, empty: 'No payment recorded'),
          ),
          _DetailRow(
            label: 'Advance until',
            value: _date(loan.advanceUntil, empty: 'None'),
          ),
          _DetailRow(label: 'Payments', value: '${loan.paymentCount}'),
          _DetailRow(label: 'PASS count', value: '${loan.passCount}'),
          _DetailRow(label: 'Audit state', value: '${loan.stateVersion}'),
        ],
      ),
    );
  }
}

class _StatusChip extends StatelessWidget {
  const _StatusChip({required this.loan});

  final ManagementLoanItem loan;

  @override
  Widget build(BuildContext context) {
    final label = loan.isOverdue ? 'Overdue' : _titleCase(loan.loanStatus);
    return Chip(
      label: Text(label),
      avatar: Icon(
        loan.isOverdue ? Icons.warning_amber : Icons.check_circle,
        size: 18,
      ),
    );
  }
}

class _ValueRow extends StatelessWidget {
  const _ValueRow({
    required this.label,
    required this.value,
    this.emphasized = false,
  });

  final String label;
  final String value;
  final bool emphasized;

  @override
  Widget build(BuildContext context) {
    final style = emphasized ? Theme.of(context).textTheme.titleMedium : null;
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 3),
      child: Row(
        children: [
          Expanded(child: Text(label, style: style)),
          Text(value, style: style),
        ],
      ),
    );
  }
}

class _DetailRow extends StatelessWidget {
  const _DetailRow({required this.label, required this.value});

  final String label;
  final String value;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 3),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          SizedBox(width: 116, child: Text(label)),
          Expanded(child: Text(value, textAlign: TextAlign.right)),
        ],
      ),
    );
  }
}

class _ErrorPanel extends StatelessWidget {
  const _ErrorPanel({required this.message, required this.onRetry});

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
            Icon(
              Icons.error_outline,
              size: 48,
              color: Theme.of(context).colorScheme.error,
            ),
            const SizedBox(height: 12),
            Text(message, textAlign: TextAlign.center),
            const SizedBox(height: 16),
            FilledButton.icon(
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

String _money(double value) {
  final parts = value.toStringAsFixed(2).split('.');
  final whole = parts.first.replaceAllMapped(
    RegExp(r'\B(?=(\d{3})+(?!\d))'),
    (_) => ',',
  );
  return '₱$whole.${parts.last}';
}

String _trimNumber(double value) {
  return value.toStringAsFixed(4).replaceFirst(RegExp(r'\.?0+$'), '');
}

String _date(DateTime? value, {String empty = 'Not available'}) {
  if (value == null) {
    return empty;
  }
  return '${value.year.toString().padLeft(4, '0')}-'
      '${value.month.toString().padLeft(2, '0')}-'
      '${value.day.toString().padLeft(2, '0')}';
}

String _titleCase(String value) {
  final normalized = value.trim();
  if (normalized.isEmpty) {
    return 'Unknown';
  }
  return normalized
      .split(RegExp(r'\s+'))
      .map((part) => '${part[0].toUpperCase()}${part.substring(1)}')
      .join(' ');
}
