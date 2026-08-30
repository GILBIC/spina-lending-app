import 'dart:math';

import 'package:flutter/material.dart';
import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/device/device_identity.dart';
import 'package:gilbic_mobile/src/core/management/tax_adjustment.dart';
import 'package:gilbic_mobile/src/core/management/tax_adjustment_repository.dart';
import 'package:gilbic_mobile/src/core/network/spina_api.dart';
import 'package:gilbic_mobile/src/features/management/review/management_review.dart';

class ManagementTaxAdjustmentPage extends StatefulWidget {
  const ManagementTaxAdjustmentPage({
    required this.session,
    required this.deviceIdentityProvider,
    this.repository,
    this.confirmationTokenGenerator,
    this.idempotencyKeyGenerator,
    super.key,
  });
  final UserSession session;
  final DeviceIdentityProvider deviceIdentityProvider;
  final TaxAdjustmentRepository? repository;
  final String Function()? confirmationTokenGenerator;
  final String Function()? idempotencyKeyGenerator;

  @override
  State<ManagementTaxAdjustmentPage> createState() =>
      _ManagementTaxAdjustmentPageState();
}

class _ManagementTaxAdjustmentPageState
    extends State<ManagementTaxAdjustmentPage> {
  late final TaxAdjustmentRepository _repository;
  late final String Function() _tokenGenerator;
  late final String Function() _idempotencyGenerator;
  final Map<String, String> _postingTokens = <String, String>{};
  TaxAdjustmentOverview? _overview;
  String? _error;
  String? _busy;
  bool _loading = true;
  bool _writeStateUncertain = false;

  @override
  void initState() {
    super.initState();
    _repository = widget.repository ?? SpinaTaxAdjustmentRepository();
    _tokenGenerator = widget.confirmationTokenGenerator ?? _newDigest;
    _idempotencyGenerator = widget.idempotencyKeyGenerator ?? _newUuid;
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
      if (mounted) {
        setState(() {
          _overview = overview;
          _writeStateUncertain = false;
        });
      }
    } on SpinaApiException catch (error) {
      if (mounted) setState(() => _error = error.message);
    } on Object {
      if (mounted) {
        setState(() => _error = 'Tax corrections could not be loaded.');
      }
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  bool _allowed(String action, String permission) {
    final overview = _overview;
    if (overview == null) return false;
    final serverAllowed = switch (action) {
      'evidence' => overview.permissions.adjustmentEvidenceRecord,
      'prepare' => overview.permissions.adjustmentPrepare,
      'post' => overview.permissions.adjustmentPost,
      _ => false,
    };
    return serverAllowed &&
        !_writeStateUncertain &&
        widget.session.hasPermission(permission);
  }

  Future<void> _recordEvidence(TaxAdjustmentCandidate candidate) async {
    if (!_allowed('evidence', 'accounting.tax.adjustment_evidence.record')) {
      return;
    }
    final fields = await showDialog<_AdjustmentEvidenceFields>(
      context: context,
      builder: (_) => _AdjustmentEvidenceDialog(candidate: candidate),
    );
    if (fields == null || !mounted) return;
    final confirmed = await showManagementReviewConfirmation(
      context,
      ManagementReviewPresentation.validated(
        surface: ManagementMutationSurface.taxAdjustment,
        recordLabel: 'Tax correction candidate',
        recordValue: candidate.taxLiabilityPostingId,
        statusLabel: 'Server-derived exact stale/current evidence pair',
        facts: <ManagementReviewFact>[
          ManagementReviewFact(
            label: 'Correction',
            value: _kind(candidate.adjustmentKind),
          ),
          ManagementReviewFact(
            label: 'Original tax',
            value: candidate.originalTaxDue,
          ),
          ManagementReviewFact(
            label: 'Replacement tax',
            value: candidate.replacementTaxDue,
          ),
          ManagementReviewFact(
            label: 'Adjustment amount',
            value: candidate.adjustmentAmount,
          ),
          ManagementReviewFact(
            label: 'Adjustment date',
            value: fields.adjustmentDate,
          ),
        ],
        secondaryReferences: <ManagementReviewFact>[
          ManagementReviewFact(
            label: 'Original evidence',
            value: candidate.originalEvidenceDigest,
          ),
          ManagementReviewFact(
            label: 'Replacement evidence',
            value: candidate.replacementEvidenceDigest,
          ),
          ManagementReviewFact(
            label: 'Fiscal period ID',
            value: candidate.fiscalPeriodId,
          ),
        ],
        warnings: const <ManagementReviewWarning>[
          ManagementReviewWarning(
            severity: ManagementReviewWarningSeverity.caution,
            message:
                'Posted history is never rewritten. The backend revalidates the pair and allowed correction kind.',
          ),
        ],
        nextActionLabel: 'Record correction evidence',
        consequence:
            'Records immutable correction evidence only; no adjustment journal is posted.',
        risk: ManagementReviewRisk.protectedFinancial,
      ),
    );
    if (!confirmed || !mounted) return;
    await _run(candidate.taxLiabilityPostingId, () async {
      final identity = await widget.deviceIdentityProvider.load();
      await _repository.recordEvidence(
        widget.session,
        deviceId: identity.installationId,
        candidate: candidate,
        idempotencyKey: _idempotencyGenerator(),
        adjustmentDate: fields.adjustmentDate,
        adjustmentReference: fields.adjustmentReference,
        evidenceReference: fields.evidenceReference,
        evidenceDigest: fields.evidenceDigest,
        evidenceNote: fields.evidenceNote,
      );
      _message('Immutable tax-correction evidence recorded.');
    });
  }

  Future<void> _prepare(TaxAdjustmentItem item) async {
    if (!_allowed('prepare', 'accounting.tax.adjustment.prepare')) return;
    item.requirePrepareCoordinates();
    final confirmed = await _confirmItem(
      item,
      status: 'Correction evidence ready',
      next: 'Prepare correction draft',
      consequence:
          'Creates a protected draft only. No balance changes until separate posting confirmation.',
    );
    if (!confirmed || !mounted) return;
    await _run(item.adjustmentEvidenceId, () async {
      final identity = await widget.deviceIdentityProvider.load();
      await _repository.prepare(
        widget.session,
        deviceId: identity.installationId,
        item: item,
      );
      _message('Protected tax-correction draft prepared.');
    });
  }

  Future<void> _post(TaxAdjustmentItem item) async {
    if (!_allowed('post', 'accounting.tax.adjustment.post')) return;
    item.requirePostCoordinates();
    final confirmed = await _confirmItem(
      item,
      status: 'Prepared — exact posting confirmation required',
      next: 'Post tax correction',
      consequence:
          'Immutably posts the exact protected reversal or Tax Recoverable journal with permanent audit evidence.',
      prepared: true,
    );
    if (!confirmed || !mounted) return;
    final key = <String>[
      item.adjustmentEvidenceId,
      item.evidenceDigest,
      item.originalTaxDue,
      item.replacementTaxDue,
      item.adjustmentAmount,
      item.debitAccountCode!,
      item.creditAccountCode!,
      item.adjustmentDate,
      item.fiscalPeriodId!,
    ].join('|');
    final token = _postingTokens.putIfAbsent(key, _tokenGenerator);
    await _run(item.adjustmentEvidenceId, () async {
      final identity = await widget.deviceIdentityProvider.load();
      await _repository.post(
        widget.session,
        deviceId: identity.installationId,
        item: item,
        confirmationToken: token,
      );
      _postingTokens.remove(key);
      _message('Protected tax correction posted.');
    });
  }

  Future<bool> _confirmItem(
    TaxAdjustmentItem item, {
    required String status,
    required String next,
    required String consequence,
    bool prepared = false,
  }) => showManagementReviewConfirmation(
    context,
    ManagementReviewPresentation.validated(
      surface: ManagementMutationSurface.taxAdjustment,
      recordLabel: 'Tax correction evidence',
      recordValue: item.adjustmentEvidenceId,
      statusLabel: status,
      facts: <ManagementReviewFact>[
        ManagementReviewFact(
          label: 'Correction',
          value: _kind(item.adjustmentKind),
        ),
        ManagementReviewFact(label: 'Original tax', value: item.originalTaxDue),
        ManagementReviewFact(
          label: 'Replacement tax',
          value: item.replacementTaxDue,
        ),
        ManagementReviewFact(
          label: 'Adjustment amount',
          value: item.adjustmentAmount,
        ),
        if (prepared)
          ManagementReviewFact(
            label: 'Debit',
            value: '${item.debitAccountCode} ${item.debitAccountName}',
          ),
        if (prepared)
          ManagementReviewFact(
            label: 'Credit',
            value: '${item.creditAccountCode} ${item.creditAccountName}',
          ),
      ],
      secondaryReferences: <ManagementReviewFact>[
        ManagementReviewFact(
          label: 'Evidence fingerprint',
          value: item.evidenceDigest,
        ),
        if (prepared)
          ManagementReviewFact(
            label: 'Fiscal period ID',
            value: item.fiscalPeriodId!,
          ),
        if (prepared)
          ManagementReviewFact(
            label: 'Journal entry ID',
            value: item.journalEntryId!,
          ),
      ],
      warnings: const <ManagementReviewWarning>[
        ManagementReviewWarning(
          severity: ManagementReviewWarningSeverity.caution,
          message:
              'Posted liability and settlement history remain immutable; automatic posting is disabled.',
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
      if (mounted && error.code == 'network_unavailable') {
        setState(() => _writeStateUncertain = true);
        _message(
          'The result is uncertain. Refresh authoritative correction state before retrying.',
        );
      } else if (mounted) {
        _message(error.message);
      }
    } on ArgumentError catch (error) {
      if (mounted) {
        _message(error.message ?? 'Exact evidence fields are required.');
      }
    } on Object {
      if (mounted) {
        _message(
          'The result is uncertain. Refresh authoritative correction state before retrying.',
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
      title: const Text('Tax Corrections'),
      actions: <Widget>[
        IconButton(
          tooltip: 'Refresh corrections',
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
          _AdjustmentSummary(summary: overview.summary),
          const SizedBox(height: 10),
          Text(
            'Server-derived correction candidates',
            style: Theme.of(context).textTheme.titleMedium,
          ),
          if (overview.adjustmentCandidates.isEmpty)
            const Card(
              child: Padding(
                padding: EdgeInsets.all(14),
                child: Text(
                  'No exact tax correction candidates are currently eligible.',
                ),
              ),
            )
          else
            ...overview.adjustmentCandidates.map(
              (candidate) => Card(
                margin: const EdgeInsets.only(top: 10),
                child: ListTile(
                  key: Key(
                    'tax-adjustment-candidate-${candidate.taxLiabilityPostingId}',
                  ),
                  leading: const Icon(Icons.rule_folder_outlined),
                  title: Text(_kind(candidate.adjustmentKind)),
                  subtitle: Text(
                    '${candidate.originalTaxDue} → ${candidate.replacementTaxDue} • adjustment ${candidate.adjustmentAmount}',
                  ),
                  trailing: FilledButton(
                    onPressed:
                        _allowed(
                              'evidence',
                              'accounting.tax.adjustment_evidence.record',
                            ) &&
                            _busy == null
                        ? () => _recordEvidence(candidate)
                        : null,
                    child: const Text('Record'),
                  ),
                ),
              ),
            ),
          const SizedBox(height: 14),
          Text(
            'Correction queue',
            style: Theme.of(context).textTheme.titleMedium,
          ),
          if (overview.items.isEmpty)
            const Card(
              child: Padding(
                padding: EdgeInsets.all(14),
                child: Text('No retained tax corrections yet.'),
              ),
            )
          else
            ...overview.items.map(
              (item) => _AdjustmentRow(
                item: item,
                busy: _busy == item.adjustmentEvidenceId,
                canPrepare:
                    item.isEvidenceReady &&
                    _allowed('prepare', 'accounting.tax.adjustment.prepare'),
                canPost:
                    item.isPrepared &&
                    _allowed('post', 'accounting.tax.adjustment.post'),
                onPrepare: () => _prepare(item),
                onPost: () => _post(item),
              ),
            ),
          if (_error != null)
            Card(
              child: Padding(
                padding: const EdgeInsets.all(12),
                child: Text(_error!),
              ),
            ),
        ],
      ),
    );
  }
}

class _AdjustmentSummary extends StatelessWidget {
  const _AdjustmentSummary({required this.summary});
  final TaxAdjustmentSummary summary;
  @override
  Widget build(BuildContext context) => Card(
    key: const Key('tax-adjustment-summary'),
    child: Padding(
      padding: const EdgeInsets.all(14),
      child: Wrap(
        spacing: 14,
        runSpacing: 8,
        children: <Widget>[
          Text('Evidence: ${summary.adjustmentEvidenceCount}'),
          Text('Ready: ${summary.readyToPrepareCount}'),
          Text('Prepared: ${summary.preparedCount}'),
          Text('Reversed: ${summary.postedReversalCount}'),
          Text('Recoverable: ${summary.postedRecoverableCount}'),
          Text('Posted total: ${summary.postedAdjustmentTotal}'),
        ],
      ),
    ),
  );
}

class _AdjustmentRow extends StatelessWidget {
  const _AdjustmentRow({
    required this.item,
    required this.busy,
    required this.canPrepare,
    required this.canPost,
    required this.onPrepare,
    required this.onPost,
  });
  final TaxAdjustmentItem item;
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
                  _kind(item.adjustmentKind),
                  style: Theme.of(context).textTheme.titleMedium,
                ),
              ),
              Chip(label: Text(_status(item.adjustmentStatus))),
            ],
          ),
          Text('${item.adjustmentDate} • ${item.adjustmentAmount}'),
          Text('Loan ${item.loanId}'),
          if (item.adjustmentBlocker != null)
            Text(
              item.adjustmentBlocker!,
              style: TextStyle(color: Theme.of(context).colorScheme.error),
            ),
          if (canPrepare)
            FilledButton.icon(
              key: Key('prepare-tax-adjustment-${item.adjustmentEvidenceId}'),
              onPressed: busy ? null : onPrepare,
              icon: const Icon(Icons.fact_check_outlined),
              label: const Text('Prepare correction'),
            ),
          if (canPost)
            FilledButton.icon(
              key: Key('post-tax-adjustment-${item.adjustmentEvidenceId}'),
              onPressed: busy ? null : onPost,
              icon: const Icon(Icons.lock_outline),
              label: const Text('Post correction'),
            ),
          if (busy) const LinearProgressIndicator(),
        ],
      ),
    ),
  );
}

class _AdjustmentEvidenceFields {
  const _AdjustmentEvidenceFields(
    this.adjustmentDate,
    this.adjustmentReference,
    this.evidenceReference,
    this.evidenceDigest,
    this.evidenceNote,
  );
  final String adjustmentDate;
  final String adjustmentReference;
  final String evidenceReference;
  final String evidenceDigest;
  final String evidenceNote;
}

class _AdjustmentEvidenceDialog extends StatefulWidget {
  const _AdjustmentEvidenceDialog({required this.candidate});
  final TaxAdjustmentCandidate candidate;
  @override
  State<_AdjustmentEvidenceDialog> createState() =>
      _AdjustmentEvidenceDialogState();
}

class _AdjustmentEvidenceDialogState extends State<_AdjustmentEvidenceDialog> {
  final _controllers = List<TextEditingController>.generate(
    5,
    (_) => TextEditingController(),
  );
  @override
  void initState() {
    super.initState();
    _controllers.first.text = widget.candidate.fiscalPeriodEnd;
  }

  @override
  void dispose() {
    for (final controller in _controllers) {
      controller.dispose();
    }
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    const labels = <String>[
      'Adjustment date (YYYY-MM-DD)',
      'Adjustment reference',
      'Evidence reference',
      'Evidence SHA-256',
      'Evidence note',
    ];
    return AlertDialog(
      title: const Text('Retained correction evidence'),
      content: SingleChildScrollView(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: <Widget>[
            Text(
              '${_kind(widget.candidate.adjustmentKind)} • ${widget.candidate.adjustmentAmount}',
            ),
            ...List<Widget>.generate(
              labels.length,
              (index) => Padding(
                padding: const EdgeInsets.only(top: 8),
                child: TextField(
                  controller: _controllers[index],
                  decoration: InputDecoration(labelText: labels[index]),
                  minLines: index == 4 ? 2 : 1,
                  maxLines: index == 4 ? 4 : 1,
                ),
              ),
            ),
          ],
        ),
      ),
      actions: <Widget>[
        TextButton(
          onPressed: () => Navigator.pop(context),
          child: const Text('Cancel'),
        ),
        FilledButton(
          onPressed: () => Navigator.pop(
            context,
            _AdjustmentEvidenceFields(
              _controllers[0].text.trim(),
              _controllers[1].text.trim(),
              _controllers[2].text.trim(),
              _controllers[3].text.trim(),
              _controllers[4].text.trim(),
            ),
          ),
          child: const Text('Review'),
        ),
      ],
    );
  }
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

String _kind(String value) => value == 'reverse_unsettled_liability'
    ? 'Reverse unpaid stale liability'
    : 'Recognize settled Tax Recoverable';
String _status(String value) => switch (value) {
  'evidence_ready' => 'Evidence ready',
  'prepared_not_posted' => 'Prepared',
  'posted_unsettled_liability_reversal' => 'Reversed',
  'posted_settled_tax_recoverable' => 'Recoverable posted',
  'posted_further_adjustment_review_required' => 'Further review',
  _ => 'Blocked',
};
String _newDigest() => List<int>.generate(
  32,
  (_) => Random.secure().nextInt(256),
).map((value) => value.toRadixString(16).padLeft(2, '0')).join();
String _newUuid() {
  final bytes = List<int>.generate(16, (_) => Random.secure().nextInt(256));
  bytes[6] = (bytes[6] & 0x0f) | 0x40;
  bytes[8] = (bytes[8] & 0x3f) | 0x80;
  final hex = bytes
      .map((value) => value.toRadixString(16).padLeft(2, '0'))
      .join();
  return '${hex.substring(0, 8)}-${hex.substring(8, 12)}-${hex.substring(12, 16)}-${hex.substring(16, 20)}-${hex.substring(20)}';
}
