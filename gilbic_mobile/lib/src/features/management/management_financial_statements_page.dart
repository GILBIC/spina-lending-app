import 'package:flutter/material.dart';
import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/device/device_identity.dart';
import 'package:gilbic_mobile/src/core/management/financial_accounting.dart';
import 'package:gilbic_mobile/src/core/management/financial_accounting_repository.dart';
import 'package:gilbic_mobile/src/core/management/financial_statements.dart';
import 'package:gilbic_mobile/src/core/management/financial_statements_repository.dart';
import 'package:gilbic_mobile/src/core/network/spina_api.dart';

class ManagementFinancialStatementsPage extends StatefulWidget {
  const ManagementFinancialStatementsPage({
    required this.session,
    required this.deviceIdentityProvider,
    this.accountingRepository,
    this.statementsRepository,
    super.key,
  });

  final UserSession session;
  final DeviceIdentityProvider deviceIdentityProvider;
  final FinancialAccountingRepository? accountingRepository;
  final FinancialStatementsRepository? statementsRepository;

  @override
  State<ManagementFinancialStatementsPage> createState() =>
      _ManagementFinancialStatementsPageState();
}

class _ManagementFinancialStatementsPageState
    extends State<ManagementFinancialStatementsPage> {
  late final FinancialAccountingRepository _accountingRepository;
  late final FinancialStatementsRepository _statementsRepository;

  List<AccountingFiscalPeriod> _periods = const <AccountingFiscalPeriod>[];
  String? _selectedPeriodId;
  AccountingFinancialStatements? _statements;
  String? _errorMessage;
  bool _loading = true;

  @override
  void initState() {
    super.initState();
    _accountingRepository =
        widget.accountingRepository ?? SpinaFinancialAccountingRepository();
    _statementsRepository =
        widget.statementsRepository ?? SpinaFinancialStatementsRepository();
    _load(initial: true);
  }

  Future<void> _load({bool initial = false}) async {
    setState(() {
      _loading = true;
      _errorMessage = null;
    });
    try {
      final identity = await widget.deviceIdentityProvider.load();
      if (initial || _periods.isEmpty) {
        final overview = await _accountingRepository.loadOverview(
          widget.session,
          deviceId: identity.installationId,
        );
        final periods = [...overview.fiscalPeriods]
          ..sort((a, b) => b.endDate.compareTo(a.endDate));
        if (periods.isEmpty) {
          throw const SpinaApiException(
            'Create an accounting period before generating Financial Statements.',
            code: 'accounting_period_required',
          );
        }
        _periods = periods;
        _selectedPeriodId ??= periods.first.periodId;
      }

      final statements = await _statementsRepository.loadStatements(
        widget.session,
        deviceId: identity.installationId,
        periodId: _selectedPeriodId,
      );
      if (mounted) {
        setState(() => _statements = statements);
      }
    } on SpinaApiException catch (error) {
      if (mounted) {
        setState(() => _errorMessage = error.message);
      }
    } on Object {
      if (mounted) {
        setState(
          () => _errorMessage = 'Financial Statements could not be loaded.',
        );
      }
    } finally {
      if (mounted) {
        setState(() => _loading = false);
      }
    }
  }

  Future<void> _selectPeriod(String? periodId) async {
    if (periodId == null || periodId == _selectedPeriodId) {
      return;
    }
    setState(() => _selectedPeriodId = periodId);
    await _load();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Financial Statements'),
        actions: [
          IconButton(
            tooltip: 'Refresh Financial Statements',
            onPressed: _loading ? null : () => _load(),
            icon: const Icon(Icons.refresh),
          ),
        ],
      ),
      body: SafeArea(child: _buildBody()),
    );
  }

  Widget _buildBody() {
    final statements = _statements;
    if (_loading && statements == null) {
      return const Center(child: CircularProgressIndicator());
    }
    if (_errorMessage != null && statements == null) {
      return _ErrorPanel(message: _errorMessage!, onRetry: () => _load(initial: true));
    }
    if (statements == null) {
      return const SizedBox.shrink();
    }

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
                  const Icon(Icons.verified_outlined),
                  const SizedBox(width: 12),
                  Expanded(
                    child: Text(
                      'Read-only statements from posted General Ledger entries. Draft journals are excluded.',
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
          const SizedBox(height: 14),
          DropdownButtonFormField<String>(
            key: const Key('financial-statements-period'),
            initialValue: _selectedPeriodId,
            decoration: const InputDecoration(
              labelText: 'Accounting period',
              border: OutlineInputBorder(),
            ),
            items: _periods
                .map(
                  (period) => DropdownMenuItem<String>(
                    value: period.periodId,
                    child: Text('${period.label} • ${_statusLabel(period.status)}'),
                  ),
                )
                .toList(growable: false),
            onChanged: _loading ? null : _selectPeriod,
          ),
          const SizedBox(height: 16),
          _ProfitOrLossCard(statements: statements),
          const SizedBox(height: 16),
          _FinancialPositionCard(statements: statements),
          const SizedBox(height: 16),
          Card(
            child: Padding(
              padding: const EdgeInsets.all(14),
              child: Text(statements.notice),
            ),
          ),
        ],
      ),
    );
  }
}

class _ProfitOrLossCard extends StatelessWidget {
  const _ProfitOrLossCard({required this.statements});

  final AccountingFinancialStatements statements;

  @override
  Widget build(BuildContext context) {
    final result = statements.profitOrLoss;
    return Card(
      key: const Key('profit-or-loss-statement'),
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              'Statement of Profit or Loss',
              style: Theme.of(context).textTheme.titleMedium,
            ),
            const SizedBox(height: 4),
            Text(
              '${_date(statements.period.startDate)} – ${_date(statements.period.endDate)}',
            ),
            const Divider(height: 24),
            const _SectionTitle('Income'),
            ...result.incomeLines.map(_StatementLineRow.new),
            if (result.incomeLines.isEmpty) const _EmptyLine('No posted income.'),
            _TotalRow('Total income', result.totalIncome),
            const SizedBox(height: 10),
            const _SectionTitle('Expenses'),
            ...result.expenseLines.map(_StatementLineRow.new),
            if (result.expenseLines.isEmpty) const _EmptyLine('No posted expenses.'),
            _TotalRow('Total expenses', result.totalExpenses),
            const Divider(height: 24),
            _TotalRow(
              result.netIncome >= 0 ? 'Net income' : 'Net loss',
              result.netIncome,
              emphasized: true,
            ),
          ],
        ),
      ),
    );
  }
}

class _FinancialPositionCard extends StatelessWidget {
  const _FinancialPositionCard({required this.statements});

  final AccountingFinancialStatements statements;

  @override
  Widget build(BuildContext context) {
    final result = statements.financialPosition;
    return Card(
      key: const Key('financial-position-statement'),
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Expanded(
                  child: Text(
                    'Statement of Financial Position',
                    style: Theme.of(context).textTheme.titleMedium,
                  ),
                ),
                Chip(
                  label: Text(result.balanced ? 'Balanced' : 'Not balanced'),
                ),
              ],
            ),
            const SizedBox(height: 4),
            Text('As of ${_date(result.asOfDate)}'),
            const Divider(height: 24),
            const _SectionTitle('Assets'),
            ...result.assetLines.map(_StatementLineRow.new),
            if (result.assetLines.isEmpty) const _EmptyLine('No posted assets.'),
            _TotalRow('Total assets', result.totalAssets),
            const SizedBox(height: 10),
            const _SectionTitle('Liabilities'),
            ...result.liabilityLines.map(_StatementLineRow.new),
            if (result.liabilityLines.isEmpty)
              const _EmptyLine('No posted liabilities.'),
            _TotalRow('Total liabilities', result.totalLiabilities),
            const SizedBox(height: 10),
            const _SectionTitle('Equity'),
            ...result.equityLines.map(_StatementLineRow.new),
            if (result.equityLines.isEmpty) const _EmptyLine('No posted equity.'),
            _SimpleRow('Unclosed earnings to date', result.unclosedEarningsToDate),
            _TotalRow('Total equity', result.totalEquity),
            const Divider(height: 24),
            _TotalRow(
              'Liabilities + equity',
              result.totalLiabilitiesAndEquity,
              emphasized: true,
            ),
          ],
        ),
      ),
    );
  }
}

class _SectionTitle extends StatelessWidget {
  const _SectionTitle(this.text);

  final String text;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 6),
      child: Text(
        text,
        style: Theme.of(context).textTheme.titleSmall,
      ),
    );
  }
}

class _StatementLineRow extends StatelessWidget {
  const _StatementLineRow(this.line);

  final FinancialStatementLine line;

  @override
  Widget build(BuildContext context) {
    return _SimpleRow('${line.accountCode} ${line.accountName}', line.amount);
  }
}

class _SimpleRow extends StatelessWidget {
  const _SimpleRow(this.label, this.amount);

  final String label;
  final double amount;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 3),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Expanded(child: Text(label)),
          const SizedBox(width: 12),
          Text(_money(amount)),
        ],
      ),
    );
  }
}

class _TotalRow extends StatelessWidget {
  const _TotalRow(this.label, this.amount, {this.emphasized = false});

  final String label;
  final double amount;
  final bool emphasized;

  @override
  Widget build(BuildContext context) {
    final style = emphasized
        ? Theme.of(context).textTheme.titleSmall?.copyWith(fontWeight: FontWeight.w700)
        : const TextStyle(fontWeight: FontWeight.w600);
    return Padding(
      padding: const EdgeInsets.only(top: 6),
      child: Row(
        children: [
          Expanded(child: Text(label, style: style)),
          Text(_money(amount), style: style),
        ],
      ),
    );
  }
}

class _EmptyLine extends StatelessWidget {
  const _EmptyLine(this.text);

  final String text;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 4),
      child: Text(text, style: Theme.of(context).textTheme.bodySmall),
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

String _money(double amount) {
  final absolute = amount.abs().toStringAsFixed(2);
  return amount < 0 ? '(₱$absolute)' : '₱$absolute';
}

String _date(DateTime value) {
  final month = value.month.toString().padLeft(2, '0');
  final day = value.day.toString().padLeft(2, '0');
  return '${value.year}-$month-$day';
}

String _statusLabel(String value) {
  if (value.isEmpty) return value;
  return value
      .split('_')
      .where((part) => part.isNotEmpty)
      .map((part) => '${part[0].toUpperCase()}${part.substring(1)}')
      .join(' ');
}
