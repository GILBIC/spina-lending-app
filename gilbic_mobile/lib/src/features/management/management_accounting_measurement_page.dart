import 'package:flutter/material.dart';
import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/device/device_identity.dart';
import 'package:gilbic_mobile/src/core/management/opening_balance_workbook.dart';
import 'package:gilbic_mobile/src/core/management/opening_balance_workbook_repository.dart';
import 'package:gilbic_mobile/src/core/network/spina_api.dart';

class ManagementAccountingMeasurementPage extends StatefulWidget {
  const ManagementAccountingMeasurementPage({
    required this.session,
    required this.deviceIdentityProvider,
    this.repository,
    super.key,
  });

  final UserSession session;
  final DeviceIdentityProvider deviceIdentityProvider;
  final OpeningBalanceWorkbookRepository? repository;

  @override
  State<ManagementAccountingMeasurementPage> createState() =>
      _ManagementAccountingMeasurementPageState();
}

class _ManagementAccountingMeasurementPageState
    extends State<ManagementAccountingMeasurementPage> {
  late final OpeningBalanceWorkbookRepository _repository;
  OpeningBalanceWorkbookData? _data;
  bool _loading = true;
  String? _error;

  @override
  void initState() {
    super.initState();
    _repository = widget.repository ?? SpinaOpeningBalanceWorkbookRepository();
    _load();
  }

  Future<void> _load() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final identity = await widget.deviceIdentityProvider.load();
      final data = await _repository.load(
        widget.session,
        deviceId: identity.installationId,
      );
      if (mounted) setState(() => _data = data);
    } on SpinaApiException catch (error) {
      if (mounted) setState(() => _error = error.message);
    } on Object {
      if (mounted) setState(() => _error = 'Loan measurement could not be loaded.');
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Loan Measurement'),
        actions: [
          IconButton(
            tooltip: 'Refresh loan measurement',
            onPressed: _loading ? null : _load,
            icon: const Icon(Icons.refresh),
          ),
        ],
      ),
      body: SafeArea(child: _body()),
    );
  }

  Widget _body() {
    final data = _data;
    if (_loading && data == null) {
      return const Center(child: CircularProgressIndicator());
    }
    if (_error != null && data == null) {
      return Center(
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              const Icon(Icons.error_outline, size: 40),
              const SizedBox(height: 10),
              Text(_error!, textAlign: TextAlign.center),
              const SizedBox(height: 12),
              FilledButton(onPressed: _load, child: const Text('Retry')),
            ],
          ),
        ),
      );
    }
    if (data == null) return const SizedBox.shrink();

    final measurement = data.measurement;
    final eclLine = _lineByCode(data.lines, '1190');
    return RefreshIndicator(
      onRefresh: _load,
      child: ListView(
        padding: const EdgeInsets.fromLTRB(16, 16, 16, 28),
        physics: const AlwaysScrollableScrollPhysics(),
        children: [
          Card(
            child: Padding(
              padding: const EdgeInsets.all(14),
              child: Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Icon(Icons.calculate_outlined),
                  const SizedBox(width: 10),
                  Expanded(child: Text(measurement.notice)),
                ],
              ),
            ),
          ),
          const SizedBox(height: 12),
          _MeasurementSummaryCard(
            summary: measurement.summary,
            cutoverDate: data.summary.cutoverDate,
          ),
          if (eclLine != null) ...[
            const SizedBox(height: 12),
            _EclReadinessCard(line: eclLine),
          ],
          const SizedBox(height: 12),
          _WorkbookMeasurementReferenceCard(lines: data.lines),
          const SizedBox(height: 12),
          Text('Loan measurement detail', style: Theme.of(context).textTheme.titleMedium),
          const SizedBox(height: 8),
          for (final loan in measurement.loans) ...[
            _LoanMeasurementCard(loan: loan),
            const SizedBox(height: 8),
          ],
          const SizedBox(height: 4),
          const Card(
            child: Padding(
              padding: EdgeInsets.all(14),
              child: Text(
                'Stage 5D provides reconciled EIR measurement. Stage 5E adds read-only ECL assessment readiness only: no PD, LGD, forward-looking scenario weight, ECL amount, verified workbook value, or General Ledger journal is created automatically.',
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class _MeasurementSummaryCard extends StatelessWidget {
  const _MeasurementSummaryCard({
    required this.summary,
    required this.cutoverDate,
  });

  final AccountingMeasurementSummary summary;
  final DateTime? cutoverDate;

  @override
  Widget build(BuildContext context) {
    return Card(
      key: const Key('accounting-measurement-summary'),
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                const Icon(Icons.account_balance_outlined),
                const SizedBox(width: 8),
                Expanded(
                  child: Text(
                    'Stage 5D EIR Cutover Measurement',
                    style: Theme.of(context).textTheme.titleSmall,
                  ),
                ),
                Chip(label: Text(_status(summary.measurementStatus))),
              ],
            ),
            const SizedBox(height: 8),
            _Row(label: 'Cutover date', value: cutoverDate == null ? 'Not set' : _date(cutoverDate!)),
            _Row(label: 'Measured / active', value: '${summary.measuredLoanCount} / ${summary.activeLoanCount}'),
            _Row(label: 'Review required', value: '${summary.reviewRequiredCount}'),
            _Row(label: 'Policy version', value: summary.measurementPolicyVersion),
            _Row(label: 'Actual cash through cutover', value: _money(summary.actualCashReceived)),
            _Row(label: 'EIR interest income to date', value: _money(summary.effectiveInterestIncome)),
            _Row(label: 'Regular loan component', value: _money(summary.regularLoanComponent)),
            _Row(label: '7x7 loan component', value: _money(summary.sevenBySevenLoanComponent)),
            _Row(label: 'Accrued interest component', value: _money(summary.accruedInterestComponent)),
            _Row(label: 'Gross carrying amount', value: _money(summary.grossCarryingAmount)),
            _Row(label: 'ECL included', value: summary.eclIncluded ? 'Yes' : 'No'),
            _Row(label: 'Ready to post', value: summary.readyToPost ? 'Yes' : 'No'),
          ],
        ),
      ),
    );
  }
}

class _EclReadinessCard extends StatelessWidget {
  const _EclReadinessCard({required this.line});

  final OpeningBalanceWorkbookLine line;

  @override
  Widget build(BuildContext context) {
    return Card(
      key: const Key('accounting-ecl-readiness'),
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                const Icon(Icons.shield_outlined),
                const SizedBox(width: 8),
                Expanded(
                  child: Text(
                    'Stage 5E Expected Credit Loss Readiness',
                    style: Theme.of(context).textTheme.titleSmall,
                  ),
                ),
                Chip(
                  label: Text(_status(line.measurementStatus ?? 'assessment_required')),
                ),
              ],
            ),
            const SizedBox(height: 8),
            _Row(label: 'Allowance account', value: '${line.accountCode} ${line.accountName}'),
            _Row(
              label: 'ECL amount',
              value: line.measurementReferenceAmount == null
                  ? 'Not calculated'
                  : _money(line.measurementReferenceAmount!),
            ),
            _Row(label: 'ECL included', value: 'No'),
            _Row(label: 'Ready to post', value: 'No'),
            const SizedBox(height: 8),
            Text(
              line.measurementNote ?? line.guidance,
              style: Theme.of(context).textTheme.bodySmall,
            ),
          ],
        ),
      ),
    );
  }
}

class _WorkbookMeasurementReferenceCard extends StatelessWidget {
  const _WorkbookMeasurementReferenceCard({required this.lines});

  final List<OpeningBalanceWorkbookLine> lines;

  @override
  Widget build(BuildContext context) {
    final refs = lines
        .where((line) => const {'1100', '1110', '1120', '1190'}.contains(line.accountCode))
        .toList(growable: false);
    return Card(
      key: const Key('accounting-measurement-workbook-references'),
      child: Padding(
        padding: const EdgeInsets.all(14),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text('Workbook measurement references', style: Theme.of(context).textTheme.titleSmall),
            const SizedBox(height: 6),
            const Text('Reference only — these values are not automatically verified or posted.'),
            const SizedBox(height: 8),
            for (final line in refs) ...[
              _Row(
                label: '${line.accountCode} ${line.accountName}',
                value: line.measurementReferenceAmount == null
                    ? _status(line.measurementStatus ?? 'review_required')
                    : _money(line.measurementReferenceAmount!),
              ),
              if (line.accountCode == '1190' && line.measurementNote != null) ...[
                const SizedBox(height: 4),
                Text(line.measurementNote!, style: Theme.of(context).textTheme.bodySmall),
                const SizedBox(height: 6),
              ],
            ],
          ],
        ),
      ),
    );
  }
}

class _LoanMeasurementCard extends StatelessWidget {
  const _LoanMeasurementCard({required this.loan});

  final LoanAccountingMeasurement loan;

  @override
  Widget build(BuildContext context) {
    return Card(
      key: Key('loan-measurement-${loan.loanNumber}'),
      child: ExpansionTile(
        initiallyExpanded: false,
        title: Text(loan.loanNumber),
        subtitle: Text('${loan.clientName} • ${_typeLabel(loan.calculationMode)}'),
        trailing: Chip(label: Text(_status(loan.measurementStatus))),
        childrenPadding: const EdgeInsets.fromLTRB(16, 0, 16, 14),
        children: [
          _Row(label: 'Released', value: _date(loan.dateReleased)),
          _Row(label: 'Due', value: _date(loan.dueDate)),
          _Row(label: 'Days elapsed', value: loan.daysElapsed?.toString() ?? '—'),
          _Row(label: 'Original principal', value: _money(loan.principal)),
          _Row(label: 'Operational balance', value: _money(loan.operationalBalance)),
          _Row(
            label: 'Daily EIR',
            value: loan.dailyEirPercent == null
                ? 'Not measured'
                : '${loan.dailyEirPercent!.toStringAsFixed(8)}%',
          ),
          _Row(
            label: 'Contractual cash due',
            value: loan.contractualCashDue == null ? '—' : _money(loan.contractualCashDue!),
          ),
          _Row(
            label: 'Actual cash received',
            value: loan.actualCashReceived == null ? '—' : _money(loan.actualCashReceived!),
          ),
          _Row(
            label: 'EIR interest income',
            value: loan.effectiveInterestIncome == null ? '—' : _money(loan.effectiveInterestIncome!),
          ),
          _Row(
            label: 'Loan component',
            value: loan.loanComponent == null ? '—' : _money(loan.loanComponent!),
          ),
          _Row(
            label: 'Accrued interest component',
            value: loan.accruedInterestComponent == null
                ? '—'
                : _money(loan.accruedInterestComponent!),
          ),
          _Row(
            label: 'Gross carrying amount',
            value: loan.grossCarryingAmount == null ? '—' : _money(loan.grossCarryingAmount!),
          ),
          if (loan.contractualUnpaidInterest != null)
            _Row(
              label: '7x7 contractual unpaid interest',
              value: _money(loan.contractualUnpaidInterest!),
            ),
          const SizedBox(height: 6),
          Align(
            alignment: Alignment.centerLeft,
            child: Text(loan.measurementNote, style: Theme.of(context).textTheme.bodySmall),
          ),
        ],
      ),
    );
  }
}

class _Row extends StatelessWidget {
  const _Row({required this.label, required this.value});

  final String label;
  final String value;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 2),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Expanded(child: Text(label)),
          const SizedBox(width: 12),
          Flexible(child: Text(value, textAlign: TextAlign.end)),
        ],
      ),
    );
  }
}

OpeningBalanceWorkbookLine? _lineByCode(
  List<OpeningBalanceWorkbookLine> lines,
  String code,
) {
  for (final line in lines) {
    if (line.accountCode == code) return line;
  }
  return null;
}

String _typeLabel(String mode) => switch (mode) {
      'fixed_daily' => 'Regular',
      'seven_by_seven' => '7x7',
      _ => mode,
    };

String _status(String value) => value
    .split('_')
    .where((part) => part.isNotEmpty)
    .map((part) => '${part[0].toUpperCase()}${part.substring(1)}')
    .join(' ');

String _date(DateTime value) {
  final month = value.month.toString().padLeft(2, '0');
  final day = value.day.toString().padLeft(2, '0');
  return '${value.year}-$month-$day';
}

String _money(double value) {
  final negative = value < 0;
  final fixed = value.abs().toStringAsFixed(2);
  final parts = fixed.split('.');
  final chars = parts.first.split('').reversed.toList();
  final groups = <String>[];
  for (var index = 0; index < chars.length; index += 3) {
    groups.add(chars.skip(index).take(3).toList().reversed.join());
  }
  final whole = groups.reversed.join(',');
  return '${negative ? '-' : ''}₱$whole.${parts[1]}';
}