import 'package:flutter/material.dart';
import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/device/device_identity.dart';
import 'package:gilbic_mobile/src/core/management/ecl_a5_accounting_repository.dart';
import 'package:gilbic_mobile/src/core/management/ecl_allowance_posting_repository.dart';
import 'package:gilbic_mobile/src/core/management/financial_accounting.dart';
import 'package:gilbic_mobile/src/core/management/financial_accounting_repository.dart';
import 'package:gilbic_mobile/src/core/management/initial_capital_funding_repository.dart';
import 'package:gilbic_mobile/src/core/management/period_close_repository.dart';
import 'package:gilbic_mobile/src/core/management/tax_evidence_repository.dart';
import 'package:gilbic_mobile/src/core/management/tax_liability_repository.dart';
import 'package:gilbic_mobile/src/core/network/spina_api.dart';
import 'package:gilbic_mobile/src/features/management/management_ecl_allowance_posting_page.dart';
import 'package:gilbic_mobile/src/features/management/management_ecl_a5_accounting_page.dart';
import 'package:gilbic_mobile/src/features/management/management_initial_capital_funding_page.dart';
import 'package:gilbic_mobile/src/features/management/management_period_close_page.dart';
import 'package:gilbic_mobile/src/features/management/management_tax_accounting_page.dart';
import 'package:gilbic_mobile/src/features/management/review/management_review.dart';

class ManagementFinancialAccountingPage extends StatefulWidget {
  const ManagementFinancialAccountingPage({
    required this.session,
    required this.deviceIdentityProvider,
    this.repository,
    this.periodCloseRepository,
    this.eclAllowanceRepository,
    this.eclA5Repository,
    this.initialCapitalRepository,
    this.taxEvidenceRepository,
    this.taxLiabilityRepository,
    super.key,
  });

  final UserSession session;
  final DeviceIdentityProvider deviceIdentityProvider;
  final FinancialAccountingRepository? repository;
  final PeriodCloseRepository? periodCloseRepository;
  final EclAllowancePostingRepository? eclAllowanceRepository;
  final EclA5AccountingRepository? eclA5Repository;
  final InitialCapitalFundingRepository? initialCapitalRepository;
  final TaxEvidenceRepository? taxEvidenceRepository;
  final TaxLiabilityRepository? taxLiabilityRepository;

  @override
  State<ManagementFinancialAccountingPage> createState() =>
      _ManagementFinancialAccountingPageState();
}

class _ManagementFinancialAccountingPageState
    extends State<ManagementFinancialAccountingPage> {
  late final FinancialAccountingRepository _repository;
  FinancialAccountingOverview? _overview;
  String? _errorMessage;
  bool _loading = true;
  bool _periodActionInProgress = false;

  @override
  void initState() {
    super.initState();
    _repository = widget.repository ?? SpinaFinancialAccountingRepository();
    _load();
  }

  Future<void> _load() async {
    setState(() {
      _loading = true;
      _errorMessage = null;
    });
    try {
      final identity = await widget.deviceIdentityProvider.load();
      final overview = await _repository.loadOverview(
        widget.session,
        deviceId: identity.installationId,
      );
      if (mounted) {
        setState(() => _overview = overview);
      }
    } on SpinaApiException catch (error) {
      if (mounted) {
        setState(() => _errorMessage = error.message);
      }
    } on Object {
      if (mounted) {
        setState(
          () => _errorMessage = 'Financial Accounting could not be loaded.',
        );
      }
    } finally {
      if (mounted) {
        setState(() => _loading = false);
      }
    }
  }

  Future<void> _createFiscalPeriod() async {
    final draft = await showDialog<_FiscalPeriodDraft>(
      context: context,
      builder: (context) => const _CreateFiscalPeriodDialog(),
    );
    if (draft == null || !mounted) {
      return;
    }
    final confirmed = await showManagementReviewConfirmation(
      context,
      ManagementReviewPresentation.validated(
        binding: ManagementMutationBinding.fiscalPeriod,
        recordLabel: 'New fiscal period',
        recordValue:
            '${draft.label} • ${_date(draft.startDate)} – ${_date(draft.endDate)}',
        statusLabel: 'Will start Open for permitted journal work',
        facts: <ManagementReviewFact>[
          ManagementReviewFact(
            label: 'Start date',
            value: _date(draft.startDate),
          ),
          ManagementReviewFact(label: 'End date', value: _date(draft.endDate)),
          const ManagementReviewFact(label: 'Journals', value: '0'),
        ],
        nextActionLabel: 'Create fiscal period',
        consequence:
            'A new open fiscal period will be created. This does not post a journal '
            'or change any account balance.',
      ),
    );
    if (!confirmed || !mounted) {
      return;
    }
    await _runPeriodAction(() async {
      final identity = await widget.deviceIdentityProvider.load();
      await _repository.createFiscalPeriod(
        widget.session,
        deviceId: identity.installationId,
        label: draft.label,
        startDate: draft.startDate,
        endDate: draft.endDate,
      );
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('${draft.label} accounting period created.')),
        );
      }
    });
  }

  Future<void> _changeFiscalPeriodStatus(
    AccountingFiscalPeriod period,
    String targetStatus,
  ) async {
    final targetLabel = _statusLabel(targetStatus);
    final consequence = switch (targetStatus) {
      'review' =>
        'The period will move to Management review and the server will apply '
            'review-state restrictions. Posted journals remain unchanged.',
      _ =>
        'The period will return to Open. This changes only the period workflow '
            'state and does not grant new posting authority.',
    };
    final confirmed = await showManagementReviewConfirmation(
      context,
      ManagementReviewPresentation.validated(
        binding: ManagementMutationBinding.fiscalPeriod,
        recordLabel: 'Fiscal period',
        recordValue:
            '${period.label} • ${_date(period.startDate)} – ${_date(period.endDate)}',
        statusLabel:
            plainManagementStatus(period.status, const <String, String>{
              'open': 'Open for permitted journal work',
              'review': 'Waiting for Management review',
              'closed': 'Closed to new journal work',
            }),
        facts: <ManagementReviewFact>[
          ManagementReviewFact(
            label: 'Journals',
            value: '${period.journalCount}',
          ),
          ManagementReviewFact(
            label: 'Posted journals',
            value: '${period.postedJournalCount}',
          ),
          ManagementReviewFact(
            label: 'Draft journals',
            value: '${period.draftJournalCount}',
          ),
          ManagementReviewFact(label: 'Next status', value: targetLabel),
        ],
        nextActionLabel: 'Change period to $targetLabel',
        consequence: consequence,
        secondaryReferences: <ManagementReviewFact>[
          ManagementReviewFact(label: 'Period ID', value: period.periodId),
        ],
      ),
    );
    if (!confirmed || !mounted) {
      return;
    }
    await _runPeriodAction(() async {
      final identity = await widget.deviceIdentityProvider.load();
      await _repository.changeFiscalPeriodStatus(
        widget.session,
        deviceId: identity.installationId,
        periodId: period.periodId,
        status: targetStatus,
      );
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text(
              '${period.label} moved to ${_statusLabel(targetStatus).toLowerCase()}.',
            ),
          ),
        );
      }
    });
  }

  Future<void> _openFormalPeriodClose() async {
    await Navigator.of(context).push<void>(
      MaterialPageRoute<void>(
        builder: (context) => ManagementPeriodClosePage(
          session: widget.session,
          deviceIdentityProvider: widget.deviceIdentityProvider,
          repository: widget.periodCloseRepository,
        ),
      ),
    );
    if (mounted) await _load();
  }

  Future<void> _openInitialEclAllowance() async {
    await Navigator.of(context).push<void>(
      MaterialPageRoute<void>(
        builder: (context) => ManagementEclAllowancePostingPage(
          session: widget.session,
          deviceIdentityProvider: widget.deviceIdentityProvider,
          repository: widget.eclAllowanceRepository,
        ),
      ),
    );
    if (mounted) await _load();
  }

  Future<void> _openEclAdjustments() async {
    await Navigator.of(context).push<void>(
      MaterialPageRoute<void>(
        builder: (context) => ManagementEclA5AccountingPage(
          session: widget.session,
          deviceIdentityProvider: widget.deviceIdentityProvider,
          repository: widget.eclA5Repository,
        ),
      ),
    );
    if (mounted) await _load();
  }

  Future<void> _openInitialCapitalFunding() async {
    await Navigator.of(context).push<void>(
      MaterialPageRoute<void>(
        builder: (context) => ManagementInitialCapitalFundingPage(
          session: widget.session,
          deviceIdentityProvider: widget.deviceIdentityProvider,
          repository: widget.initialCapitalRepository,
        ),
      ),
    );
    if (mounted) await _load();
  }

  Future<void> _openTaxAccounting() async {
    await Navigator.of(context).push<void>(
      MaterialPageRoute<void>(
        builder: (context) => ManagementTaxAccountingPage(
          session: widget.session,
          deviceIdentityProvider: widget.deviceIdentityProvider,
          evidenceRepository: widget.taxEvidenceRepository,
          liabilityRepository: widget.taxLiabilityRepository,
        ),
      ),
    );
    if (mounted) await _load();
  }

  Future<void> _runPeriodAction(Future<void> Function() action) async {
    if (_periodActionInProgress) {
      return;
    }
    setState(() => _periodActionInProgress = true);
    try {
      await action();
      await _load();
    } on SpinaApiException catch (error) {
      if (mounted) {
        ScaffoldMessenger.of(
          context,
        ).showSnackBar(SnackBar(content: Text(error.message)));
      }
    } on Object {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Accounting period action failed.')),
        );
      }
    } finally {
      if (mounted) {
        setState(() => _periodActionInProgress = false);
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Financial Accounting'),
        actions: [
          IconButton(
            tooltip: 'Refresh accounting overview',
            onPressed: _loading ? null : _load,
            icon: const Icon(Icons.refresh),
          ),
        ],
      ),
      body: SafeArea(child: _buildBody()),
    );
  }

  Widget _buildBody() {
    final overview = _overview;
    if (_loading && overview == null) {
      return const Center(child: CircularProgressIndicator());
    }
    if (_errorMessage != null && overview == null) {
      return _ErrorPanel(message: _errorMessage!, onRetry: _load);
    }
    if (overview == null) {
      return const SizedBox.shrink();
    }

    return RefreshIndicator(
      onRefresh: _load,
      child: ListView(
        physics: const AlwaysScrollableScrollPhysics(),
        padding: const EdgeInsets.fromLTRB(16, 16, 16, 28),
        children: [
          Card(
            key: const Key('financial-accounting-management-guidance'),
            child: Padding(
              padding: const EdgeInsets.all(14),
              child: Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Icon(Icons.visibility_outlined),
                  const SizedBox(width: 12),
                  const Expanded(
                    child: Text(
                      'Official amounts come from protected server records. '
                      'Review balances, posting readiness, accounting periods, '
                      'and loan controls below. Posting, period changes, and '
                      'reversals still require Management confirmation and '
                      'permanent audit evidence.',
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
          Text(
            'Accounting control center',
            style: Theme.of(context).textTheme.titleMedium,
          ),
          const SizedBox(height: 8),
          _SummaryGrid(summary: overview.summary),
          const SizedBox(height: 16),
          _ReadinessCard(overview: overview),
          const SizedBox(height: 16),
          _CutoverReadinessCard(overview: overview),
          const SizedBox(height: 16),
          _OpeningBalanceWorksheetCard(overview: overview),
          const SizedBox(height: 16),
          Card(
            child: ListTile(
              key: const Key('formal-period-close'),
              leading: const Icon(Icons.lock_clock_outlined),
              title: const Text('Formal period close'),
              subtitle: const Text(
                'Prepare an exact retained-earnings snapshot, review its digest, then post through the protected server workflow.',
              ),
              trailing: const Icon(Icons.chevron_right),
              onTap: _periodActionInProgress ? null : _openFormalPeriodClose,
            ),
          ),
          const SizedBox(height: 10),
          Card(
            child: ListTile(
              key: const Key('tax-accounting'),
              leading: const Icon(Icons.receipt_long_outlined),
              title: const Text('Tax Accounting'),
              subtitle: const Text(
                'Review retained tax evidence and use protected tax-liability preparation/posting.',
              ),
              trailing: const Icon(Icons.chevron_right),
              onTap: _periodActionInProgress ? null : _openTaxAccounting,
            ),
          ),
          const SizedBox(height: 10),
          Card(
            child: ListTile(
              key: const Key('initial-capital-funding'),
              leading: const Icon(Icons.savings_outlined),
              title: const Text('Initial capital funding'),
              subtitle: const Text(
                'Record retained funding evidence, prepare the protected journal, and post only after exact Management review.',
              ),
              trailing: const Icon(Icons.chevron_right),
              onTap: _periodActionInProgress
                  ? null
                  : _openInitialCapitalFunding,
            ),
          ),
          const SizedBox(height: 10),
          Card(
            child: ListTile(
              key: const Key('initial-ecl-allowance'),
              leading: const Icon(Icons.shield_outlined),
              title: const Text('Initial ECL allowance'),
              subtitle: const Text(
                'Review exact authoritative ECL evidence, prepare the protected draft, and post only through the server workflow.',
              ),
              trailing: const Icon(Icons.chevron_right),
              onTap: _periodActionInProgress ? null : _openInitialEclAllowance,
            ),
          ),
          const SizedBox(height: 10),
          Card(
            child: ListTile(
              key: const Key('ecl-adjustments'),
              leading: const Icon(Icons.tune_outlined),
              title: const Text('ECL adjustments'),
              subtitle: const Text(
                'Review and confirm protected remeasurement, full write-off, and post-write-off recovery actions from exact server evidence.',
              ),
              trailing: const Icon(Icons.chevron_right),
              onTap: _periodActionInProgress ? null : _openEclAdjustments,
            ),
          ),
          const SizedBox(height: 16),
          _FiscalPeriodsCard(
            periods: overview.fiscalPeriods,
            canManage: overview.periodManagementEnabled,
            busy: _periodActionInProgress,
            onCreate: _createFiscalPeriod,
            onStatusChange: _changeFiscalPeriodStatus,
          ),
          const SizedBox(height: 16),
          _ChartOfAccountsCard(
            foundation: overview.foundation,
            accounts: overview.accounts,
          ),
          const SizedBox(height: 18),
          Row(
            children: [
              Text(
                'Loan accounting policies',
                style: Theme.of(context).textTheme.titleMedium,
              ),
              const Spacer(),
              Text('${overview.policies.length} active'),
            ],
          ),
          const SizedBox(height: 8),
          for (final policy in overview.policies) ...[
            _PolicyCard(policy: policy),
            const SizedBox(height: 10),
          ],
        ],
      ),
    );
  }
}

class _SummaryGrid extends StatelessWidget {
  const _SummaryGrid({required this.summary});

  final FinancialAccountingSummary summary;

  @override
  Widget build(BuildContext context) {
    final items = <_MetricData>[
      _MetricData(
        'Active loans',
        '${summary.activeLoanCount}',
        _money(summary.activePrincipal),
        Icons.account_balance_outlined,
      ),
      _MetricData(
        'Operational outstanding',
        _money(summary.operationalOutstanding),
        'Current lending balances',
        Icons.payments_outlined,
      ),
      _MetricData(
        'Regular outstanding',
        _money(summary.regularOutstanding),
        'Operational balance',
        Icons.calendar_month_outlined,
      ),
      _MetricData(
        '7x7 outstanding',
        _money(summary.sevenBySevenOutstanding),
        'Principal balance source',
        Icons.calculate_outlined,
      ),
      _MetricData(
        'Unremitted cash',
        _money(summary.unremittedCash),
        'Unlocked collection cash',
        Icons.account_balance_wallet_outlined,
      ),
      _MetricData(
        'Received remittances',
        _money(summary.receivedRemittanceTotal),
        'Accepted remittance total',
        Icons.verified_outlined,
      ),
      _MetricData(
        'Valid collections',
        '${summary.validCollectionCount}',
        'Non-voided source entries',
        Icons.receipt_long,
      ),
      _MetricData(
        'Corrections / voids',
        '${summary.correctionCount} / ${summary.voidCount}',
        'Audit source records',
        Icons.fact_check_outlined,
      ),
    ];
    return GridView.builder(
      shrinkWrap: true,
      physics: const NeverScrollableScrollPhysics(),
      itemCount: items.length,
      gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
        crossAxisCount: 2,
        mainAxisExtent: 116,
        crossAxisSpacing: 10,
        mainAxisSpacing: 10,
      ),
      itemBuilder: (context, index) => _MetricCard(data: items[index]),
    );
  }
}

class _ReadinessCard extends StatelessWidget {
  const _ReadinessCard({required this.overview});

  final FinancialAccountingOverview overview;

  @override
  Widget build(BuildContext context) {
    final foundation = overview.foundation;
    return Card(
      key: const Key('financial-accounting-readiness'),
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                const Icon(Icons.rule_folder_outlined),
                const SizedBox(width: 8),
                Text(
                  'Posting readiness',
                  style: Theme.of(context).textTheme.titleSmall,
                ),
              ],
            ),
            const SizedBox(height: 10),
            _DetailRow(
              label: 'Foundation',
              value: _statusLabel(overview.foundationStatus),
            ),
            _DetailRow(
              label: 'Chart of accounts',
              value:
                  '${foundation.postingAccountCount} / ${foundation.accountCount} posting',
            ),
            _DetailRow(
              label: 'Fiscal periods',
              value:
                  '${_statusLabel(overview.fiscalPeriodStatus)} • ${foundation.fiscalPeriodCount}',
            ),
            _DetailRow(
              label: 'General journal',
              value:
                  '${_statusLabel(overview.journalStatus)} • ${foundation.journalEntryCount}',
            ),
            _DetailRow(
              label: 'Posted / drafts',
              value:
                  '${foundation.postedJournalCount} / ${foundation.draftJournalCount}',
            ),
            _DetailRow(
              label: 'Trial balance',
              value: _statusLabel(overview.trialBalanceStatus),
            ),
            const SizedBox(height: 8),
            const Text(
              'Manual General Journal posting is protected and available. Opening-balance conversion and automatic lending entries remain disabled until the cutover worksheet is completed and approved.',
            ),
          ],
        ),
      ),
    );
  }
}

class _CutoverReadinessCard extends StatelessWidget {
  const _CutoverReadinessCard({required this.overview});

  final FinancialAccountingOverview overview;

  @override
  Widget build(BuildContext context) {
    final summary = overview.cutoverSummary;
    final sevenBySeven = overview.cutoverLoans
        .where((loan) => loan.isSevenBySeven)
        .toList(growable: false);
    final regularReady = overview.cutoverLoans
        .where(
          (loan) =>
              !loan.isSevenBySeven && loan.readinessStatus == 'source_ready',
        )
        .length;

    return Card(
      key: const Key('financial-accounting-cutover-readiness'),
      clipBehavior: Clip.antiAlias,
      child: ExpansionTile(
        initiallyExpanded: false,
        leading: const Icon(Icons.fact_check_outlined),
        title: const Text('Accounting Cutover Readiness'),
        subtitle: Text(
          '${summary.sourceReadyCount} / ${summary.activeLoanCount} loan sources ready',
        ),
        childrenPadding: const EdgeInsets.fromLTRB(16, 0, 16, 16),
        children: [
          _DetailRow(
            label: 'Overall status',
            value: _statusLabel(summary.overallStatus),
          ),
          _DetailRow(
            label: 'Source ready',
            value: '${summary.sourceReadyCount}',
          ),
          _DetailRow(label: 'Blocked', value: '${summary.blockedCount}'),
          _DetailRow(label: 'Regular ready', value: '$regularReady'),
          _DetailRow(
            label: '7x7 schedules',
            value: '${sevenBySeven.length} validated',
          ),
          _DetailRow(
            label: 'Opening balances',
            value: summary.openingBalancesConfigured
                ? 'Configured'
                : 'Not configured',
          ),
          _DetailRow(
            label: 'Automatic posting',
            value: summary.automaticSourcePostingEnabled
                ? 'Enabled'
                : 'Disabled',
          ),
          const SizedBox(height: 10),
          const Align(
            alignment: Alignment.centerLeft,
            child: Text(
              '7x7 validated base contract schedule',
              style: TextStyle(fontWeight: FontWeight.w600),
            ),
          ),
          const SizedBox(height: 6),
          const Align(
            alignment: Alignment.centerLeft,
            child: Text(
              'Daily contractual interest is based on original principal. Principal is due on or before maturity; optional principal prepayments do not reduce the fixed daily contractual interest. This validates source cash flows only and does not post EIR income yet.',
            ),
          ),
          const SizedBox(height: 10),
          for (final loan in sevenBySeven) ...[
            Container(
              width: double.infinity,
              padding: const EdgeInsets.all(12),
              decoration: BoxDecoration(
                border: Border.all(color: Theme.of(context).dividerColor),
                borderRadius: BorderRadius.circular(12),
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    loan.clientName,
                    style: Theme.of(context).textTheme.titleSmall,
                  ),
                  Text(
                    '${loan.loanNumber} • ${_statusLabel(loan.readinessStatus)}',
                    style: Theme.of(context).textTheme.bodySmall,
                  ),
                  const SizedBox(height: 6),
                  _DetailRow(label: 'Principal', value: _money(loan.principal)),
                  _DetailRow(
                    label: 'Daily interest',
                    value: _money(loan.sevenBySevenExpectedDailyInterest ?? 0),
                  ),
                  _DetailRow(
                    label: '${loan.termDays}-day interest',
                    value: _money(loan.sevenBySevenContractInterestTotal ?? 0),
                  ),
                  _DetailRow(
                    label: 'Base contract total',
                    value: _money(
                      loan.sevenBySevenContractTotalIfPrincipalAtMaturity ?? 0,
                    ),
                  ),
                  _DetailRow(
                    label: 'Base daily rate',
                    value:
                        '${(loan.sevenBySevenBaseDailyRatePercent ?? 0).toStringAsFixed(4)}%',
                  ),
                ],
              ),
            ),
            const SizedBox(height: 8),
          ],
        ],
      ),
    );
  }
}

class _OpeningBalanceWorksheetCard extends StatelessWidget {
  const _OpeningBalanceWorksheetCard({required this.overview});

  final FinancialAccountingOverview overview;

  @override
  Widget build(BuildContext context) {
    final summary = overview.openingBalanceSummary;
    return Card(
      key: const Key('financial-accounting-opening-balance-worksheet'),
      clipBehavior: Clip.antiAlias,
      child: ExpansionTile(
        leading: const Icon(Icons.table_view_outlined),
        title: const Text('Opening Balance / Cutover Worksheet'),
        subtitle: Text(
          '${summary.worksheetLineCount} balance-sheet accounts • ${_statusLabel(summary.worksheetStatus)}',
        ),
        childrenPadding: const EdgeInsets.fromLTRB(16, 0, 16, 16),
        children: [
          _DetailRow(
            label: 'Cutover date',
            value: summary.cutoverDate == null
                ? 'Not selected'
                : _date(summary.cutoverDate!),
          ),
          _DetailRow(
            label: 'Source references',
            value: '${summary.sourceReferenceCount}',
          ),
          _DetailRow(
            label: 'Manual balances',
            value: '${summary.manualRequiredCount} required',
          ),
          _DetailRow(
            label: 'Reconciliations',
            value: '${summary.reconciliationRequiredCount} required',
          ),
          _DetailRow(
            label: 'Calculations',
            value: '${summary.calculationRequiredCount} required',
          ),
          _DetailRow(
            label: 'ECL assessment',
            value: '${summary.assessmentRequiredCount} required',
          ),
          _DetailRow(
            label: 'P&L migration policy',
            value: summary.profitLossMigrationPolicyRequired
                ? 'Required'
                : 'Set',
          ),
          _DetailRow(
            label: 'Worksheet balanced',
            value: summary.worksheetBalanced ? 'Yes' : 'No',
          ),
          _DetailRow(
            label: 'Ready to post',
            value: summary.readyToPost ? 'Yes' : 'No',
          ),
          _DetailRow(
            label: 'Opening posting',
            value: summary.openingBalancePostingEnabled
                ? 'Enabled'
                : 'Disabled',
          ),
          const SizedBox(height: 10),
          const Align(
            alignment: Alignment.centerLeft,
            child: Text(
              'Source amounts below are references only. They are not opening journal balances and cannot post from this stage.',
            ),
          ),
          const SizedBox(height: 10),
          for (final line in overview.openingBalanceLines) ...[
            Container(
              width: double.infinity,
              padding: const EdgeInsets.all(12),
              decoration: BoxDecoration(
                border: Border.all(color: Theme.of(context).dividerColor),
                borderRadius: BorderRadius.circular(12),
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      SizedBox(
                        width: 48,
                        child: Text(
                          line.accountCode,
                          style: Theme.of(context).textTheme.labelLarge,
                        ),
                      ),
                      Expanded(
                        child: Text(
                          line.accountName,
                          style: Theme.of(context).textTheme.titleSmall,
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 4),
                  _DetailRow(
                    label: 'Source reference',
                    value: line.sourceReferenceAmount == null
                        ? 'Not set'
                        : _money(line.sourceReferenceAmount!),
                  ),
                  _DetailRow(
                    label: 'Status',
                    value: _statusLabel(line.readinessStatus),
                  ),
                  const SizedBox(height: 4),
                  Text(
                    line.guidance,
                    style: Theme.of(context).textTheme.bodySmall,
                  ),
                ],
              ),
            ),
            const SizedBox(height: 8),
          ],
        ],
      ),
    );
  }
}

class _FiscalPeriodsCard extends StatelessWidget {
  const _FiscalPeriodsCard({
    required this.periods,
    required this.canManage,
    required this.busy,
    required this.onCreate,
    required this.onStatusChange,
  });

  final List<AccountingFiscalPeriod> periods;
  final bool canManage;
  final bool busy;
  final VoidCallback onCreate;
  final Future<void> Function(
    AccountingFiscalPeriod period,
    String targetStatus,
  )
  onStatusChange;

  @override
  Widget build(BuildContext context) {
    return Card(
      key: const Key('financial-accounting-fiscal-periods'),
      clipBehavior: Clip.antiAlias,
      child: ExpansionTile(
        initiallyExpanded: true,
        leading: const Icon(Icons.date_range_outlined),
        title: const Text('Fiscal Periods'),
        subtitle: Text(
          periods.isEmpty
              ? 'No periods configured'
              : '${periods.length} configured',
        ),
        trailing: canManage
            ? IconButton(
                key: const Key('create-accounting-period'),
                tooltip: 'Create accounting period',
                onPressed: busy ? null : onCreate,
                icon: const Icon(Icons.add_circle_outline),
              )
            : null,
        childrenPadding: const EdgeInsets.fromLTRB(16, 0, 16, 16),
        children: [
          const Align(
            alignment: Alignment.centerLeft,
            child: Text(
              'Periods must not overlap. Open periods move to Review before the separate protected close workflow. Closed periods are permanently protected from ordinary changes.',
            ),
          ),
          const SizedBox(height: 12),
          if (periods.isEmpty)
            const Align(
              alignment: Alignment.centerLeft,
              child: Text('No fiscal period has been created.'),
            )
          else
            for (final period in periods) ...[
              _FiscalPeriodRow(
                period: period,
                canManage: canManage,
                busy: busy,
                onStatusChange: onStatusChange,
              ),
              const Divider(height: 18),
            ],
        ],
      ),
    );
  }
}

class _FiscalPeriodRow extends StatelessWidget {
  const _FiscalPeriodRow({
    required this.period,
    required this.canManage,
    required this.busy,
    required this.onStatusChange,
  });

  final AccountingFiscalPeriod period;
  final bool canManage;
  final bool busy;
  final Future<void> Function(
    AccountingFiscalPeriod period,
    String targetStatus,
  )
  onStatusChange;

  @override
  Widget build(BuildContext context) {
    return Column(
      key: Key('accounting-period-${period.periodId}'),
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    period.label,
                    style: Theme.of(context).textTheme.titleSmall,
                  ),
                  Text('${_date(period.startDate)} – ${_date(period.endDate)}'),
                ],
              ),
            ),
            const SizedBox(width: 8),
            Chip(label: Text(_statusLabel(period.status))),
          ],
        ),
        const SizedBox(height: 4),
        Text(
          '${period.journalCount} journals • ${period.postedJournalCount} posted • ${period.draftJournalCount} drafts',
          style: Theme.of(context).textTheme.bodySmall,
        ),
        if (period.status == 'closed') ...[
          const SizedBox(height: 4),
          Text(
            'Closed${period.closedByName == null ? '' : ' by ${period.closedByName}'}${period.closedAt == null ? '' : ' • ${_dateTime(period.closedAt!)}'}',
            style: Theme.of(context).textTheme.bodySmall,
          ),
        ],
        if (canManage && period.status != 'closed') ...[
          const SizedBox(height: 8),
          Wrap(
            spacing: 8,
            runSpacing: 6,
            children: [
              if (period.status == 'open')
                OutlinedButton.icon(
                  key: Key('period-review-${period.periodId}'),
                  onPressed: busy
                      ? null
                      : () => onStatusChange(period, 'review'),
                  icon: const Icon(Icons.rate_review_outlined),
                  label: const Text('Send to review'),
                ),
              if (period.status == 'review') ...[
                OutlinedButton.icon(
                  key: Key('period-reopen-${period.periodId}'),
                  onPressed: busy ? null : () => onStatusChange(period, 'open'),
                  icon: const Icon(Icons.lock_open_outlined),
                  label: const Text('Reopen'),
                ),
              ],
            ],
          ),
        ],
      ],
    );
  }
}

class _CreateFiscalPeriodDialog extends StatefulWidget {
  const _CreateFiscalPeriodDialog();

  @override
  State<_CreateFiscalPeriodDialog> createState() =>
      _CreateFiscalPeriodDialogState();
}

class _CreateFiscalPeriodDialogState extends State<_CreateFiscalPeriodDialog> {
  late final TextEditingController _labelController;
  late DateTime _startDate;
  late DateTime _endDate;

  @override
  void initState() {
    super.initState();
    final now = DateTime.now();
    _startDate = DateTime(now.year, now.month, 1);
    _endDate = DateTime(now.year, now.month + 1, 0);
    _labelController = TextEditingController(text: _monthLabel(_startDate));
  }

  @override
  void dispose() {
    _labelController.dispose();
    super.dispose();
  }

  Future<void> _pickStartDate() async {
    final selected = await showDatePicker(
      context: context,
      initialDate: _startDate,
      firstDate: DateTime(2020),
      lastDate: DateTime(2100),
    );
    if (selected != null && mounted) {
      setState(() {
        _startDate = selected;
        if (_endDate.isBefore(_startDate)) {
          _endDate = _startDate;
        }
      });
    }
  }

  Future<void> _pickEndDate() async {
    final selected = await showDatePicker(
      context: context,
      initialDate: _endDate.isBefore(_startDate) ? _startDate : _endDate,
      firstDate: _startDate,
      lastDate: DateTime(2100),
    );
    if (selected != null && mounted) {
      setState(() => _endDate = selected);
    }
  }

  @override
  Widget build(BuildContext context) {
    return AlertDialog(
      title: const Text('Create accounting period'),
      content: SingleChildScrollView(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            TextField(
              key: const Key('accounting-period-label'),
              controller: _labelController,
              maxLength: 80,
              decoration: const InputDecoration(labelText: 'Period label'),
            ),
            ListTile(
              contentPadding: EdgeInsets.zero,
              title: const Text('Start date'),
              subtitle: Text(_date(_startDate)),
              trailing: const Icon(Icons.calendar_today_outlined),
              onTap: _pickStartDate,
            ),
            ListTile(
              contentPadding: EdgeInsets.zero,
              title: const Text('End date'),
              subtitle: Text(_date(_endDate)),
              trailing: const Icon(Icons.event_outlined),
              onTap: _pickEndDate,
            ),
            const Align(
              alignment: Alignment.centerLeft,
              child: Text(
                'The new period starts Open. It cannot overlap another accounting period.',
              ),
            ),
          ],
        ),
      ),
      actions: [
        TextButton(
          onPressed: () => Navigator.of(context).pop(),
          child: const Text('Cancel'),
        ),
        FilledButton(
          key: const Key('save-accounting-period'),
          onPressed: () {
            final label = _labelController.text.trim();
            if (label.length < 3) {
              return;
            }
            Navigator.of(context).pop(
              _FiscalPeriodDraft(
                label: label,
                startDate: _startDate,
                endDate: _endDate,
              ),
            );
          },
          child: const Text('Create period'),
        ),
      ],
    );
  }
}

class _FiscalPeriodDraft {
  const _FiscalPeriodDraft({
    required this.label,
    required this.startDate,
    required this.endDate,
  });

  final String label;
  final DateTime startDate;
  final DateTime endDate;
}

class _ChartOfAccountsCard extends StatelessWidget {
  const _ChartOfAccountsCard({
    required this.foundation,
    required this.accounts,
  });

  final AccountingFoundationSummary foundation;
  final List<AccountingAccount> accounts;

  @override
  Widget build(BuildContext context) {
    return Card(
      key: const Key('financial-accounting-chart-of-accounts'),
      clipBehavior: Clip.antiAlias,
      child: ExpansionTile(
        leading: const Icon(Icons.account_tree_outlined),
        title: const Text('Chart of Accounts'),
        subtitle: Text(
          '${foundation.accountCount} accounts • ${foundation.postingAccountCount} posting',
        ),
        childrenPadding: const EdgeInsets.fromLTRB(16, 0, 16, 16),
        children: [
          const Align(
            alignment: Alignment.centerLeft,
            child: Text(
              'Seeded foundation accounts only. Balances remain subject to the approved cutover/opening-balance process.',
            ),
          ),
          const SizedBox(height: 10),
          for (final account in accounts) ...[
            _AccountRow(account: account),
            const Divider(height: 10),
          ],
        ],
      ),
    );
  }
}

class _AccountRow extends StatelessWidget {
  const _AccountRow({required this.account});

  final AccountingAccount account;

  @override
  Widget build(BuildContext context) {
    return Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        SizedBox(
          width: 46,
          child: Text(
            account.code,
            style: Theme.of(context).textTheme.labelLarge,
          ),
        ),
        const SizedBox(width: 8),
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(account.name),
              Text(
                '${_titleCase(account.accountType)} • ${_titleCase(account.normalBalance)} normal',
                style: Theme.of(context).textTheme.bodySmall,
              ),
            ],
          ),
        ),
        const SizedBox(width: 8),
        Icon(
          account.isActive
              ? Icons.check_circle_outline
              : Icons.pause_circle_outline,
          size: 18,
        ),
      ],
    );
  }
}

class _PolicyCard extends StatelessWidget {
  const _PolicyCard({required this.policy});

  final LoanAccountingPolicy policy;

  @override
  Widget build(BuildContext context) {
    final isSevenBySeven = policy.calculationMode == 'seven_by_seven';
    return Card(
      key: Key('financial-accounting-policy-${policy.code}'),
      clipBehavior: Clip.antiAlias,
      child: ExpansionTile(
        initiallyExpanded: true,
        leading: Icon(isSevenBySeven ? Icons.grid_4x4 : Icons.calendar_month),
        title: Text(policy.name),
        subtitle: Text(
          '${policy.termDays} days • ${_mode(policy.calculationMode)}',
        ),
        childrenPadding: const EdgeInsets.fromLTRB(16, 0, 16, 16),
        children: [
          _DetailRow(label: 'Term', value: '${policy.termDays} days'),
          if (policy.dailyInterestPer1000 > 0)
            _DetailRow(
              label: 'Daily interest',
              value: '${_money(policy.dailyInterestPer1000)} / ₱1,000',
            ),
          _DetailRow(
            label: 'Mobile collections',
            value: policy.mobileCollectionsEnabled ? 'Enabled' : 'Disabled',
          ),
          const SizedBox(height: 10),
          _RuleSection(title: 'Operational rule', text: policy.operationalRule),
          _RuleSection(title: 'Accounting rule', text: policy.accountingRule),
          _RuleSection(title: 'Renewal rule', text: policy.renewalRule),
        ],
      ),
    );
  }
}

class _RuleSection extends StatelessWidget {
  const _RuleSection({required this.title, required this.text});

  final String title;
  final String text;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(top: 8),
      child: Align(
        alignment: Alignment.centerLeft,
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(title, style: Theme.of(context).textTheme.labelLarge),
            const SizedBox(height: 3),
            Text(text),
          ],
        ),
      ),
    );
  }
}

class _MetricData {
  const _MetricData(this.label, this.value, this.detail, this.icon);

  final String label;
  final String value;
  final String detail;
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
            Icon(data.icon, size: 21),
            const Spacer(),
            Text(
              data.value,
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
              style: Theme.of(context).textTheme.titleMedium,
            ),
            Text(data.label, maxLines: 1, overflow: TextOverflow.ellipsis),
            Text(
              data.detail,
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
              style: Theme.of(context).textTheme.bodySmall,
            ),
          ],
        ),
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

String _mode(String value) {
  return switch (value) {
    'seven_by_seven' => '7x7 daily-interest model',
    'fixed_daily' => 'Regular fixed-daily model',
    _ => value.replaceAll('_', ' '),
  };
}

String _statusLabel(String value) {
  return switch (value) {
    'ready' => 'Ready',
    'foundation_ready' => 'Foundation ready',
    'manual_ready' => 'Manual ready',
    'not_configured' => 'Not configured',
    'configured' => 'Configured',
    'open' => 'Open',
    'review' => 'Review',
    'closed' => 'Closed',
    'not_started' => 'Not started',
    'unavailable' => 'Unavailable',
    'source_ready' => 'Source ready',
    'opening_balances_required' => 'Opening balances required',
    'source_review_required' => 'Source review required',
    'manual_required' => 'Manual balance required',
    'reconciliation_required' => 'Reconciliation required',
    'calculation_required' => 'Accounting calculation required',
    'assessment_required' => 'Assessment required',
    _ => _titleCase(value.replaceAll('_', ' ')),
  };
}

String _titleCase(String value) {
  if (value.isEmpty) {
    return value;
  }
  return value[0].toUpperCase() + value.substring(1);
}

String _date(DateTime value) {
  final month = value.month.toString().padLeft(2, '0');
  final day = value.day.toString().padLeft(2, '0');
  return '${value.year}-$month-$day';
}

String _dateTime(DateTime value) {
  final local = value.toLocal();
  final hour = local.hour.toString().padLeft(2, '0');
  final minute = local.minute.toString().padLeft(2, '0');
  return '${_date(local)} $hour:$minute';
}

String _monthLabel(DateTime value) {
  const months = <String>[
    'January',
    'February',
    'March',
    'April',
    'May',
    'June',
    'July',
    'August',
    'September',
    'October',
    'November',
    'December',
  ];
  return '${months[value.month - 1]} ${value.year}';
}
