import 'package:flutter/material.dart';
import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/device/device_identity.dart';
import 'package:gilbic_mobile/src/core/loans/client_loan.dart';
import 'package:gilbic_mobile/src/core/loans/client_loan_repository.dart';
import 'package:gilbic_mobile/src/core/network/spina_api.dart';

class ClientLoansPage extends StatefulWidget {
  const ClientLoansPage({
    required this.session,
    required this.deviceIdentityProvider,
    this.repository,
    super.key,
  });

  final UserSession session;
  final DeviceIdentityProvider deviceIdentityProvider;
  final ClientLoanRepository? repository;

  @override
  State<ClientLoansPage> createState() => _ClientLoansPageState();
}

class _ClientLoansPageState extends State<ClientLoansPage> {
  late final ClientLoanRepository _repository;
  ClientLoanPortfolio? _portfolio;
  String? _errorMessage;
  bool _loading = true;

  @override
  void initState() {
    super.initState();
    _repository = widget.repository ?? SpinaClientLoanRepository();
    _load();
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
      );
      if (mounted) {
        setState(() => _portfolio = portfolio);
      }
    } on SpinaApiException catch (error) {
      if (mounted) {
        setState(() => _errorMessage = error.message);
      }
    } on Object {
      if (mounted) {
        setState(() => _errorMessage = 'My Loans could not be loaded.');
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
      appBar: AppBar(
        title: const Text('My Loans'),
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
        padding: const EdgeInsets.all(16),
        children: [
          _BorrowerCard(portfolio: portfolio),
          if (_errorMessage != null) ...[
            const SizedBox(height: 10),
            Card(
              child: Padding(
                padding: const EdgeInsets.all(12),
                child: Text(
                  _errorMessage!,
                  style: TextStyle(
                    color: Theme.of(context).colorScheme.error,
                  ),
                ),
              ),
            ),
          ],
          const SizedBox(height: 16),
          _SectionTitle(
            title: 'Active loans',
            count: portfolio.activeLoans.length,
          ),
          const SizedBox(height: 8),
          if (portfolio.activeLoans.isEmpty)
            const _EmptyCard(message: 'No active loans were found.')
          else
            for (final loan in portfolio.activeLoans) ...[
              _LoanCard(loan: loan),
              const SizedBox(height: 10),
            ],
          if (portfolio.previousLoans.isNotEmpty) ...[
            const SizedBox(height: 12),
            _SectionTitle(
              title: 'Previous loans',
              count: portfolio.previousLoans.length,
            ),
            const SizedBox(height: 8),
            for (final loan in portfolio.previousLoans) ...[
              _LoanCard(loan: loan),
              const SizedBox(height: 10),
            ],
          ],
          const SizedBox(height: 8),
          const Card(
            child: Padding(
              padding: EdgeInsets.all(14),
              child: Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Icon(Icons.visibility_outlined),
                  SizedBox(width: 10),
                  Expanded(
                    child: Text(
                      'My Loans is view-only. Payments and corrections are recorded by authorized SPINA staff.',
                    ),
                  ),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class _BorrowerCard extends StatelessWidget {
  const _BorrowerCard({required this.portfolio});

  final ClientLoanPortfolio portfolio;

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Row(
          children: [
            const CircleAvatar(
              radius: 24,
              child: Icon(Icons.account_balance_wallet_outlined),
            ),
            const SizedBox(width: 12),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    portfolio.clientName,
                    style: Theme.of(context).textTheme.titleLarge,
                  ),
                  const SizedBox(height: 4),
                  Text(
                    '${portfolio.clientCode}'
                    '${portfolio.area == null ? '' : ' • ${portfolio.area}'}',
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _SectionTitle extends StatelessWidget {
  const _SectionTitle({required this.title, required this.count});

  final String title;
  final int count;

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        Expanded(
          child: Text(title, style: Theme.of(context).textTheme.titleMedium),
        ),
        Chip(label: Text('$count')),
      ],
    );
  }
}

class _LoanCard extends StatelessWidget {
  const _LoanCard({required this.loan});

  final ClientLoan loan;

  @override
  Widget build(BuildContext context) {
    return Card(
      key: Key('client-loan-${loan.loanId}'),
      clipBehavior: Clip.antiAlias,
      child: ExpansionTile(
        initiallyExpanded: loan.status.toLowerCase() == 'active',
        leading: Icon(
          loan.isSevenBySeven ? Icons.grid_view_rounded : Icons.receipt_long,
        ),
        title: Text(loan.loanTypeName),
        subtitle: Text(
          '${loan.loanNumber}\nRemaining: ${_money(loan.remainingBalance)}',
        ),
        trailing: _StatusChip(status: loan.status),
        childrenPadding: const EdgeInsets.fromLTRB(16, 0, 16, 16),
        children: [
          if (loan.isSevenBySeven) ...[
            Container(
              width: double.infinity,
              padding: const EdgeInsets.all(10),
              decoration: BoxDecoration(
                color: Theme.of(context).colorScheme.secondaryContainer,
                borderRadius: BorderRadius.circular(10),
              ),
              child: const Text(
                '7x7 mobile collection remains disabled. This loan is shown for viewing only.',
              ),
            ),
            const SizedBox(height: 14),
          ],
          _AmountRow(
            label: 'Official remaining balance',
            value: _money(loan.remainingBalance),
            emphasized: true,
          ),
          _AmountRow(label: 'Principal', value: _money(loan.principal)),
          _AmountRow(label: 'Paid toward balance', value: _money(loan.paidAmount)),
          _AmountRow(label: 'Daily amount', value: _money(loan.dailyAmount)),
          if (loan.interestRate != null)
            _AmountRow(
              label: 'Interest rate',
              value: '${_trimNumber(loan.interestRate!)}%',
            ),
          const SizedBox(height: 10),
          LinearProgressIndicator(value: loan.progress),
          const SizedBox(height: 6),
          Align(
            alignment: Alignment.centerRight,
            child: Text('${(loan.progress * 100).toStringAsFixed(1)}% paid'),
          ),
          const Divider(height: 24),
          _DetailRow(label: 'Released', value: _date(loan.dateReleased)),
          _DetailRow(label: 'Due date', value: _date(loan.dueDate)),
          _DetailRow(
            label: 'Last payment',
            value: _date(loan.lastPaymentDate, empty: 'No payment recorded'),
          ),
          _DetailRow(
            label: 'Paid in advance until',
            value: _date(loan.advanceUntil, empty: 'None'),
          ),
          _DetailRow(label: 'Recorded payments', value: '${loan.paymentCount}'),
          _DetailRow(label: 'PASS count', value: '${loan.passCount}'),
        ],
      ),
    );
  }
}

class _StatusChip extends StatelessWidget {
  const _StatusChip({required this.status});

  final String status;

  @override
  Widget build(BuildContext context) {
    final normalized = status.trim().toLowerCase();
    return Chip(
      label: Text(normalized.isEmpty ? 'Unknown' : _titleCase(normalized)),
      avatar: Icon(
        normalized == 'active' ? Icons.check_circle : Icons.history,
        size: 18,
      ),
    );
  }
}

class _AmountRow extends StatelessWidget {
  const _AmountRow({
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
          SizedBox(width: 132, child: Text(label)),
          Expanded(child: Text(value, textAlign: TextAlign.right)),
        ],
      ),
    );
  }
}

class _EmptyCard extends StatelessWidget {
  const _EmptyCard({required this.message});

  final String message;

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(20),
        child: Text(message, textAlign: TextAlign.center),
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
  final text = value.toStringAsFixed(4);
  return text.replaceFirst(RegExp(r'\.?0+$'), '');
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
  return value
      .split(RegExp(r'\s+'))
      .where((part) => part.isNotEmpty)
      .map((part) => '${part[0].toUpperCase()}${part.substring(1)}')
      .join(' ');
}
