import 'dart:math';

import 'package:flutter/material.dart';
import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/device/device_identity.dart';
import 'package:gilbic_mobile/src/core/management/tax_liability.dart';
import 'package:gilbic_mobile/src/core/management/tax_liability_repository.dart';
import 'package:gilbic_mobile/src/core/network/spina_api.dart';
import 'package:gilbic_mobile/src/features/management/review/management_review.dart';

class ManagementTaxLiabilityPage extends StatefulWidget {
  const ManagementTaxLiabilityPage({
    required this.session,
    required this.deviceIdentityProvider,
    this.repository,
    this.confirmationTokenGenerator,
    super.key,
  });

  final UserSession session;
  final DeviceIdentityProvider deviceIdentityProvider;
  final TaxLiabilityRepository? repository;
  final String Function()? confirmationTokenGenerator;

  @override
  State<ManagementTaxLiabilityPage> createState() =>
      _ManagementTaxLiabilityPageState();
}

class _ManagementTaxLiabilityPageState
    extends State<ManagementTaxLiabilityPage> {
  late final TaxLiabilityRepository _repository;
  late final String Function() _tokenGenerator;
  final Map<String, String> _postingTokens = <String, String>{};
  TaxLiabilityOverview? _overview;
  String? _error;
  String? _busy;
  bool _loading = true;

  @override
  void initState() {
    super.initState();
    _repository = widget.repository ?? SpinaTaxLiabilityRepository();
    _tokenGenerator = widget.confirmationTokenGenerator ?? _newToken;
    _load();
  }

  Future<void> _load() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final identity = await widget.deviceIdentityProvider.load();
      final overview = await _repository.load(
        widget.session,
        deviceId: identity.installationId,
      );
      if (mounted) setState(() => _overview = overview);
    } on SpinaApiException catch (error) {
      if (mounted) setState(() => _error = error.message);
    } on Object {
      if (mounted) {
        setState(
          () =>
              _error = 'The protected tax-liability queue could not be loaded.',
        );
      }
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  bool _canPrepare(TaxLiabilityOverview overview, TaxLiabilityItem item) =>
      item.isEvidenceReady &&
      overview.permissions.liabilityPrepare &&
      widget.session.hasPermission('accounting.tax.liability.prepare');

  bool _canPost(TaxLiabilityOverview overview, TaxLiabilityItem item) =>
      item.isPrepared &&
      overview.permissions.liabilityPost &&
      widget.session.hasPermission('accounting.tax.liability.post');

  Future<void> _prepare(TaxLiabilityItem item) async {
    final overview = _overview;
    if (overview == null || !_canPrepare(overview, item)) return;
    item.requirePrepareCoordinates();
    final confirmed = await _confirm(
      item,
      status: 'Current evidence ready for protected draft preparation',
      next: 'Prepare tax liability',
      consequence:
          'The backend will create a protected draft only. No balance changes until separate posting confirmation.',
    );
    if (!confirmed || !mounted) return;
    await _run(item.evidenceId, () async {
      final identity = await widget.deviceIdentityProvider.load();
      await _repository.prepare(
        widget.session,
        deviceId: identity.installationId,
        item: item,
      );
      _message('Protected tax-liability draft prepared.');
    });
  }

  Future<void> _post(TaxLiabilityItem item) async {
    final overview = _overview;
    if (overview == null || !_canPost(overview, item)) return;
    item.requirePostCoordinates();
    final confirmed = await _confirm(
      item,
      status: 'Prepared — exact posting confirmation required',
      next: 'Post tax liability',
      consequence:
          'The backend will immutably post the exact tax expense and Tax Payables journal with permanent audit evidence.',
      includePreparedCoordinates: true,
    );
    if (!confirmed || !mounted) return;
    final key = <String>[
      item.taxType,
      item.evidenceId,
      item.evidenceDigest,
      item.taxDue,
      item.expenseAccountCode!,
      item.taxPayableAccountCode!,
      item.recognitionDate,
      item.fiscalPeriodId!,
      item.journalEntryId!,
    ].join('|');
    final token = _postingTokens.putIfAbsent(key, _tokenGenerator);
    await _run(item.evidenceId, () async {
      final identity = await widget.deviceIdentityProvider.load();
      await _repository.post(
        widget.session,
        deviceId: identity.installationId,
        item: item,
        confirmationToken: token,
      );
      _postingTokens.remove(key);
      _message('Protected tax liability posted.');
    });
  }

  Future<bool> _confirm(
    TaxLiabilityItem item, {
    required String status,
    required String next,
    required String consequence,
    bool includePreparedCoordinates = false,
  }) => showManagementReviewConfirmation(
    context,
    ManagementReviewPresentation.validated(
      surface: ManagementMutationSurface.taxLiability,
      recordLabel: 'Tax evidence',
      recordValue: item.evidenceId,
      statusLabel: status,
      facts: <ManagementReviewFact>[
        ManagementReviewFact(label: 'Tax type', value: _taxType(item.taxType)),
        ManagementReviewFact(
          label: 'Recognition date',
          value: item.recognitionDate,
        ),
        ManagementReviewFact(label: 'Tax due', value: item.taxDue),
        ManagementReviewFact(
          label: 'Debit account',
          value: '${item.expenseAccountCode} ${item.expenseAccountName}',
        ),
        ManagementReviewFact(
          label: 'Credit account',
          value: '${item.taxPayableAccountCode} ${item.taxPayableAccountName}',
        ),
      ],
      secondaryReferences: <ManagementReviewFact>[
        ManagementReviewFact(
          label: 'Evidence fingerprint',
          value: item.evidenceDigest,
        ),
        if (includePreparedCoordinates)
          ManagementReviewFact(
            label: 'Fiscal period ID',
            value: item.fiscalPeriodId!,
          ),
        if (includePreparedCoordinates)
          ManagementReviewFact(
            label: 'Journal entry ID',
            value: item.journalEntryId!,
          ),
      ],
      warnings: const <ManagementReviewWarning>[
        ManagementReviewWarning(
          severity: ManagementReviewWarningSeverity.caution,
          message:
              'Use only current retained tax evidence. Automatic source posting remains disabled.',
        ),
      ],
      nextActionLabel: next,
      consequence: consequence,
      risk: ManagementReviewRisk.protectedFinancial,
    ),
  );

  Future<void> _run(String key, Future<void> Function() action) async {
    if (_busy != null) return;
    setState(() => _busy = key);
    var succeeded = false;
    try {
      await action();
      succeeded = true;
      await _load();
    } on SpinaApiException catch (error) {
      if (mounted) _message(error.message);
    } on Object {
      if (mounted) {
        _message(
          'The result is uncertain. Review authoritative tax state before retrying.',
        );
      }
    } finally {
      if (mounted) setState(() => _busy = null);
      if (!succeeded && mounted) setState(() {});
    }
  }

  void _message(String value) {
    final messenger = ScaffoldMessenger.of(context);
    messenger.clearSnackBars();
    messenger.showSnackBar(SnackBar(content: Text(value)));
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(
      title: const Text('Tax Liabilities'),
      actions: <Widget>[
        IconButton(
          tooltip: 'Refresh tax liabilities',
          onPressed: _loading || _busy != null ? null : _load,
          icon: const Icon(Icons.refresh),
        ),
      ],
    ),
    body: SafeArea(child: _body()),
  );

  Widget _body() {
    final overview = _overview;
    if (_loading && overview == null) {
      return const Center(child: CircularProgressIndicator());
    }
    if (_error != null && overview == null) {
      return _Error(message: _error!, onRetry: _load);
    }
    if (overview == null) return const SizedBox.shrink();
    return RefreshIndicator(
      onRefresh: _load,
      child: ListView(
        physics: const AlwaysScrollableScrollPhysics(),
        padding: const EdgeInsets.all(16),
        children: <Widget>[
          Card(
            child: Padding(
              padding: const EdgeInsets.all(14),
              child: Text(overview.notice),
            ),
          ),
          const SizedBox(height: 10),
          _Summary(summary: overview.summary),
          if (!overview.permissions.liabilityPrepare ||
              !widget.session.hasPermission('accounting.tax.liability.prepare'))
            const _Notice(
              'Tax-liability preparation permission is not assigned.',
            ),
          if (!overview.permissions.liabilityPost ||
              !widget.session.hasPermission('accounting.tax.liability.post'))
            const _Notice('Tax-liability posting permission is not assigned.'),
          if (_error != null) _Notice(_error!),
          const SizedBox(height: 4),
          if (overview.items.isEmpty)
            const Card(
              child: Padding(
                padding: EdgeInsets.all(18),
                child: Text('No protected tax-liability items yet.'),
              ),
            )
          else
            ...overview.items.map(
              (item) => _LiabilityCard(
                item: item,
                busy: _busy == item.evidenceId,
                canPrepare: _canPrepare(overview, item),
                canPost: _canPost(overview, item),
                onPrepare: () => _prepare(item),
                onPost: () => _post(item),
              ),
            ),
        ],
      ),
    );
  }
}

class _Summary extends StatelessWidget {
  const _Summary({required this.summary});
  final TaxLiabilitySummary summary;
  @override
  Widget build(BuildContext context) => Card(
    key: const Key('tax-liability-summary'),
    child: Padding(
      padding: const EdgeInsets.all(14),
      child: Wrap(
        spacing: 14,
        runSpacing: 8,
        children: <Widget>[
          Text('Evidence: ${summary.evidenceItemCount}'),
          Text('Ready: ${summary.readyToPrepareCount}'),
          Text('Prepared: ${summary.preparedCount}'),
          Text('Posted: ${summary.postedCount}'),
          Text('Needs review: ${summary.blockedOrAdjustmentReviewCount}'),
          Text('Posted total: ${summary.postedTaxLiabilityTotal}'),
        ],
      ),
    ),
  );
}

class _LiabilityCard extends StatelessWidget {
  const _LiabilityCard({
    required this.item,
    required this.busy,
    required this.canPrepare,
    required this.canPost,
    required this.onPrepare,
    required this.onPost,
  });
  final TaxLiabilityItem item;
  final bool busy;
  final bool canPrepare;
  final bool canPost;
  final VoidCallback onPrepare;
  final VoidCallback onPost;
  @override
  Widget build(BuildContext context) => Card(
    margin: const EdgeInsets.only(top: 10),
    child: Padding(
      padding: const EdgeInsets.all(14),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: <Widget>[
          Row(
            children: <Widget>[
              Expanded(
                child: Text(
                  _taxType(item.taxType),
                  style: Theme.of(context).textTheme.titleMedium,
                ),
              ),
              Chip(label: Text(_status(item.accountingStatus))),
            ],
          ),
          Text('${item.recognitionDate} • ${item.taxDue}'),
          Text('Loan ${item.loanId}'),
          if (item.accountingBlocker != null)
            Text(
              item.accountingBlocker!,
              style: TextStyle(color: Theme.of(context).colorScheme.error),
            ),
          if (item.entryNumber != null) Text('Journal: ${item.entryNumber}'),
          if (canPrepare)
            FilledButton.icon(
              key: Key('prepare-tax-liability-${item.evidenceId}'),
              onPressed: busy ? null : onPrepare,
              icon: const Icon(Icons.fact_check_outlined),
              label: const Text('Prepare tax liability'),
            ),
          if (canPost)
            FilledButton.icon(
              key: Key('post-tax-liability-${item.evidenceId}'),
              onPressed: busy ? null : onPost,
              icon: const Icon(Icons.lock_outline),
              label: const Text('Post tax liability'),
            ),
          if (busy) const LinearProgressIndicator(),
        ],
      ),
    ),
  );
}

class _Notice extends StatelessWidget {
  const _Notice(this.message);
  final String message;
  @override
  Widget build(BuildContext context) => Card(
    child: Padding(
      padding: const EdgeInsets.all(12),
      child: Row(
        children: <Widget>[
          const Icon(Icons.info_outline),
          const SizedBox(width: 8),
          Expanded(child: Text(message)),
        ],
      ),
    ),
  );
}

class _Error extends StatelessWidget {
  const _Error({required this.message, required this.onRetry});
  final String message;
  final Future<void> Function() onRetry;
  @override
  Widget build(BuildContext context) => Center(
    child: Padding(
      padding: const EdgeInsets.all(24),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: <Widget>[
          Text(message, textAlign: TextAlign.center),
          const SizedBox(height: 12),
          FilledButton(onPressed: onRetry, child: const Text('Try again')),
        ],
      ),
    ),
  );
}

String _taxType(String value) => value == 'documentary_stamp_tax'
    ? 'Documentary stamp tax'
    : 'Percentage tax — lending';
String _status(String value) => switch (value) {
  'evidence_ready' => 'Evidence ready',
  'prepared_not_posted' => 'Prepared',
  'posted' => 'Posted',
  'posted_adjustment_review_required' => 'Adjustment review',
  'posted_adjusted_reversed' => 'Adjusted — reversed',
  'posted_adjusted_recoverable' => 'Adjusted — recoverable',
  'covered_by_settled_adjustment' => 'Covered',
  'no_liability_required' => 'No liability',
  _ => 'Blocked',
};

String _newToken() {
  final random = Random.secure();
  return List<int>.generate(
    32,
    (_) => random.nextInt(256),
  ).map((value) => value.toRadixString(16).padLeft(2, '0')).join();
}
