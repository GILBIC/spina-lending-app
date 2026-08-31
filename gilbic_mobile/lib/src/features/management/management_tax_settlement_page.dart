import 'dart:math';

import 'package:flutter/material.dart';
import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/device/device_identity.dart';
import 'package:gilbic_mobile/src/core/management/tax_settlement.dart';
import 'package:gilbic_mobile/src/core/management/tax_settlement_repository.dart';
import 'package:gilbic_mobile/src/core/management/tax_value.dart';
import 'package:gilbic_mobile/src/core/network/spina_api.dart';
import 'package:gilbic_mobile/src/features/management/review/management_review.dart';

class ManagementTaxSettlementPage extends StatefulWidget {
  const ManagementTaxSettlementPage({
    required this.session,
    required this.deviceIdentityProvider,
    this.repository,
    this.confirmationTokenGenerator,
    this.idempotencyKeyGenerator,
    super.key,
  });
  final UserSession session;
  final DeviceIdentityProvider deviceIdentityProvider;
  final TaxSettlementRepository? repository;
  final String Function()? confirmationTokenGenerator;
  final String Function()? idempotencyKeyGenerator;

  @override
  State<ManagementTaxSettlementPage> createState() =>
      _ManagementTaxSettlementPageState();
}

class _ManagementTaxSettlementPageState
    extends State<ManagementTaxSettlementPage> {
  late final TaxSettlementRepository _repository;
  late final String Function() _tokenGenerator;
  late final String Function() _idempotencyGenerator;
  final Set<String> _selectedPostingIds = <String>{};
  final Map<String, String> _postingTokens = <String, String>{};
  TaxSettlementOverview? _overview;
  String? _error;
  String? _busy;
  bool _loading = true;
  bool _writeStateUncertain = false;

  @override
  void initState() {
    super.initState();
    _repository = widget.repository ?? SpinaTaxSettlementRepository();
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
          _selectedPostingIds.removeWhere(
            (id) => !overview.returnLiabilityCandidates.any(
              (candidate) => candidate.postingId == id,
            ),
          );
        });
      }
    } on SpinaApiException catch (error) {
      if (mounted) setState(() => _error = error.message);
    } on Object {
      if (mounted) {
        setState(() => _error = 'Tax settlements could not be loaded.');
      }
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  List<TaxReturnLiabilityCandidate> get _selected {
    final overview = _overview;
    if (overview == null) return const <TaxReturnLiabilityCandidate>[];
    return overview.returnLiabilityCandidates
        .where((candidate) => _selectedPostingIds.contains(candidate.postingId))
        .toList(growable: false);
  }

  int get _selectedCents => _selected.fold<int>(
    0,
    (total, candidate) => total + taxCents(candidate.taxDue),
  );

  bool _hasPermission(String serverPermission, String sessionPermission) {
    final overview = _overview;
    if (overview == null) return false;
    final serverAllowed = switch (serverPermission) {
      'return' => overview.permissions.returnEvidenceRecord,
      'payment' => overview.permissions.paymentEvidenceRecord,
      'prepare' => overview.permissions.settlementPrepare,
      'post' => overview.permissions.settlementPost,
      _ => false,
    };
    return serverAllowed &&
        !_writeStateUncertain &&
        widget.session.hasPermission(sessionPermission);
  }

  Future<void> _recordReturn() async {
    final candidates = _selected;
    if (candidates.isEmpty ||
        !_hasPermission('return', 'accounting.tax.return_evidence.record')) {
      return;
    }
    final fields = await showDialog<_ReturnEvidenceFields>(
      context: context,
      builder: (_) => const _ReturnEvidenceDialog(),
    );
    if (fields == null || !mounted) return;
    final confirmed = await showManagementReviewConfirmation(
      context,
      ManagementReviewPresentation.validated(
        binding: ManagementMutationBinding.taxSettlement,
        recordLabel: 'Tax return composition',
        recordValue: '${candidates.length} exact posted liabilities',
        statusLabel: 'Server-derived liabilities selected',
        facts: <ManagementReviewFact>[
          ManagementReviewFact(
            label: 'Tax type',
            value: _taxType(candidates.first.taxType),
          ),
          ManagementReviewFact(
            label: 'Return period',
            value: '${fields.periodStart} to ${fields.periodEnd}',
          ),
          ManagementReviewFact(label: 'Filing date', value: fields.filingDate),
          ManagementReviewFact(
            label: 'Declared total',
            value: _money(_selectedCents),
          ),
        ],
        secondaryReferences: candidates
            .map(
              (candidate) => ManagementReviewFact(
                label: candidate.entryNumber,
                value: '${candidate.recognitionDate} • ${candidate.taxDue}',
              ),
            )
            .toList(growable: false),
        warnings: const <ManagementReviewWarning>[
          ManagementReviewWarning(
            severity: ManagementReviewWarningSeverity.caution,
            message:
                'The backend revalidates every immutable liability before recording the return.',
          ),
        ],
        nextActionLabel: 'Record return evidence',
        consequence:
            'Records retained return evidence only; no settlement journal is posted.',
      ),
    );
    if (!confirmed || !mounted) return;
    await _run('new-return', () async {
      final identity = await widget.deviceIdentityProvider.load();
      await _repository.recordReturn(
        widget.session,
        deviceId: identity.installationId,
        candidates: candidates,
        idempotencyKey: _idempotencyGenerator(),
        returnPeriodStart: fields.periodStart,
        returnPeriodEnd: fields.periodEnd,
        filingDate: fields.filingDate,
        returnReference: fields.returnReference,
        evidenceReference: fields.evidenceReference,
        evidenceDigest: fields.evidenceDigest,
        evidenceNote: fields.evidenceNote,
      );
      _selectedPostingIds.clear();
      _message('Immutable tax return evidence recorded.');
    });
  }

  Future<void> _recordPayment(TaxSettlementItem item) async {
    if (!_hasPermission('payment', 'accounting.tax.payment_evidence.record')) {
      return;
    }
    item.requirePaymentCoordinates();
    final fields = await showDialog<_PaymentEvidenceFields>(
      context: context,
      builder: (_) => _PaymentEvidenceDialog(minimumDate: item.filingDate),
    );
    if (fields == null || !mounted) return;
    final confirmed = await _confirmItem(
      item,
      status: 'Return recorded — exact payment evidence pending',
      next: 'Record full-payment evidence',
      consequence:
          'Records retained payment evidence only. A separate preparation and posting confirmation remains required.',
      extra: <ManagementReviewFact>[
        ManagementReviewFact(label: 'Payment date', value: fields.paymentDate),
        ManagementReviewFact(
          label: 'Cash account',
          value: fields.cashAccountSystemKey,
        ),
      ],
    );
    if (!confirmed || !mounted) return;
    await _run(item.taxReturnId, () async {
      final identity = await widget.deviceIdentityProvider.load();
      await _repository.recordPayment(
        widget.session,
        deviceId: identity.installationId,
        item: item,
        idempotencyKey: _idempotencyGenerator(),
        paymentDate: fields.paymentDate,
        cashAccountSystemKey: fields.cashAccountSystemKey,
        paymentReference: fields.paymentReference,
        evidenceReference: fields.evidenceReference,
        evidenceDigest: fields.evidenceDigest,
        evidenceNote: fields.evidenceNote,
      );
      _message('Immutable full-payment evidence recorded.');
    });
  }

  Future<void> _prepare(TaxSettlementItem item) async {
    if (!_hasPermission('prepare', 'accounting.tax.settlement.prepare')) return;
    item.requirePrepareCoordinates();
    final confirmed = await _confirmItem(
      item,
      status: 'Exact return and payment evidence ready',
      next: 'Prepare settlement draft',
      consequence:
          'Creates a protected draft only. No balance changes until separate posting confirmation.',
    );
    if (!confirmed || !mounted) return;
    await _run(item.taxReturnId, () async {
      final identity = await widget.deviceIdentityProvider.load();
      await _repository.prepare(
        widget.session,
        deviceId: identity.installationId,
        item: item,
      );
      _message('Protected tax-settlement draft prepared.');
    });
  }

  Future<void> _post(TaxSettlementItem item) async {
    if (!_hasPermission('post', 'accounting.tax.settlement.post')) return;
    item.requirePostCoordinates();
    final confirmed = await _confirmItem(
      item,
      status: 'Prepared — exact posting confirmation required',
      next: 'Post tax settlement',
      consequence:
          'Immutably posts Dr Tax Payables / Cr the exact approved cash account with permanent audit evidence.',
      extra: <ManagementReviewFact>[
        ManagementReviewFact(
          label: 'Debit',
          value: '${item.taxPayableAccountCode} ${item.taxPayableAccountName}',
        ),
        ManagementReviewFact(
          label: 'Credit',
          value: '${item.cashAccountCode} ${item.cashAccountName}',
        ),
        ManagementReviewFact(
          label: 'Fiscal period ID',
          value: item.fiscalPeriodId!,
        ),
      ],
    );
    if (!confirmed || !mounted) return;
    final key = <String>[
      item.paymentEvidenceId!,
      item.returnEvidenceDigest,
      item.paymentEvidenceDigest!,
      item.paymentAmount!,
      item.taxPayableAccountCode!,
      item.cashAccountCode!,
      item.paymentDate!,
      item.fiscalPeriodId!,
    ].join('|');
    final token = _postingTokens.putIfAbsent(key, _tokenGenerator);
    await _run(item.taxReturnId, () async {
      final identity = await widget.deviceIdentityProvider.load();
      await _repository.post(
        widget.session,
        deviceId: identity.installationId,
        item: item,
        confirmationToken: token,
      );
      _postingTokens.remove(key);
      _message('Protected tax settlement posted.');
    });
  }

  Future<bool> _confirmItem(
    TaxSettlementItem item, {
    required String status,
    required String next,
    required String consequence,
    List<ManagementReviewFact> extra = const <ManagementReviewFact>[],
  }) => showManagementReviewConfirmation(
    context,
    ManagementReviewPresentation.validated(
      binding: ManagementMutationBinding.taxSettlement,
      recordLabel: 'Tax return',
      recordValue: item.taxReturnId,
      statusLabel: status,
      facts: <ManagementReviewFact>[
        ManagementReviewFact(label: 'Tax type', value: _taxType(item.taxType)),
        ManagementReviewFact(
          label: 'Return period',
          value: '${item.returnPeriodStart} to ${item.returnPeriodEnd}',
        ),
        ManagementReviewFact(
          label: 'Declared tax due',
          value: item.declaredTaxDue,
        ),
        ...extra,
      ],
      secondaryReferences: <ManagementReviewFact>[
        ManagementReviewFact(
          label: 'Return evidence fingerprint',
          value: item.returnEvidenceDigest,
        ),
        if (item.paymentEvidenceDigest != null)
          ManagementReviewFact(
            label: 'Payment evidence fingerprint',
            value: item.paymentEvidenceDigest!,
          ),
      ],
      warnings: const <ManagementReviewWarning>[
        ManagementReviewWarning(
          severity: ManagementReviewWarningSeverity.caution,
          message:
              'Automatic source posting remains disabled; stale screens fail closed.',
        ),
      ],
      nextActionLabel: next,
      consequence: consequence,
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
          'The result is uncertain. Refresh authoritative settlement state before retrying.',
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
          'The result is uncertain. Refresh authoritative settlement state before retrying.',
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
      title: const Text('Tax Returns & Settlements'),
      actions: <Widget>[
        IconButton(
          tooltip: 'Refresh settlements',
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
    final selectedType = _selected.isEmpty ? null : _selected.first.taxType;
    final canRecordReturn = _hasPermission(
      'return',
      'accounting.tax.return_evidence.record',
    );
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
          _SettlementSummary(summary: overview.summary),
          const SizedBox(height: 10),
          Text(
            'Unfiled posted liabilities',
            style: Theme.of(context).textTheme.titleMedium,
          ),
          ...overview.returnLiabilityCandidates.map((candidate) {
            final compatible =
                selectedType == null || selectedType == candidate.taxType;
            return CheckboxListTile(
              key: Key('return-candidate-${candidate.postingId}'),
              value: _selectedPostingIds.contains(candidate.postingId),
              onChanged: !canRecordReturn || !compatible || _busy != null
                  ? null
                  : (selected) => setState(() {
                      if (selected ?? false) {
                        _selectedPostingIds.add(candidate.postingId);
                      } else {
                        _selectedPostingIds.remove(candidate.postingId);
                      }
                    }),
              title: Text(
                '${_taxType(candidate.taxType)} • ${candidate.taxDue}',
              ),
              subtitle: Text(
                '${candidate.recognitionDate} • ${candidate.entryNumber}',
              ),
              controlAffinity: ListTileControlAffinity.leading,
            );
          }),
          if (overview.returnLiabilityCandidates.isEmpty)
            const Card(
              child: Padding(
                padding: EdgeInsets.all(14),
                child: Text('No posted liabilities are waiting for a return.'),
              ),
            ),
          FilledButton.icon(
            key: const Key('record-tax-return'),
            onPressed: canRecordReturn && _selected.isNotEmpty && _busy == null
                ? _recordReturn
                : null,
            icon: const Icon(Icons.description_outlined),
            label: Text('Record return • ${_money(_selectedCents)}'),
          ),
          const SizedBox(height: 14),
          Text(
            'Return and settlement queue',
            style: Theme.of(context).textTheme.titleMedium,
          ),
          if (overview.items.isEmpty)
            const Card(
              child: Padding(
                padding: EdgeInsets.all(14),
                child: Text('No retained tax returns yet.'),
              ),
            )
          else
            ...overview.items.map(
              (item) => _SettlementRow(
                item: item,
                busy: _busy == item.taxReturnId,
                canRecordPayment:
                    item.isAwaitingPayment &&
                    _hasPermission(
                      'payment',
                      'accounting.tax.payment_evidence.record',
                    ),
                canPrepare:
                    item.isReady &&
                    _hasPermission(
                      'prepare',
                      'accounting.tax.settlement.prepare',
                    ),
                canPost:
                    item.isPrepared &&
                    _hasPermission('post', 'accounting.tax.settlement.post'),
                onRecordPayment: () => _recordPayment(item),
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

class _SettlementSummary extends StatelessWidget {
  const _SettlementSummary({required this.summary});
  final TaxSettlementSummary summary;
  @override
  Widget build(BuildContext context) => Card(
    key: const Key('tax-settlement-summary'),
    child: Padding(
      padding: const EdgeInsets.all(14),
      child: Wrap(
        spacing: 14,
        runSpacing: 8,
        children: <Widget>[
          Text('Returns: ${summary.returnCount}'),
          Text('Awaiting payment: ${summary.awaitingPaymentEvidenceCount}'),
          Text('Ready: ${summary.readyToPrepareCount}'),
          Text('Prepared: ${summary.preparedCount}'),
          Text('Settled: ${summary.settledCount}'),
          Text('Settled total: ${summary.settledTaxTotal}'),
        ],
      ),
    ),
  );
}

class _SettlementRow extends StatelessWidget {
  const _SettlementRow({
    required this.item,
    required this.busy,
    required this.canRecordPayment,
    required this.canPrepare,
    required this.canPost,
    required this.onRecordPayment,
    required this.onPrepare,
    required this.onPost,
  });
  final TaxSettlementItem item;
  final bool busy;
  final bool canRecordPayment;
  final bool canPrepare;
  final bool canPost;
  final VoidCallback onRecordPayment;
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
              Chip(label: Text(_settlementStatus(item.settlementStatus))),
            ],
          ),
          Text(
            '${item.returnPeriodStart} to ${item.returnPeriodEnd} • ${item.declaredTaxDue}',
          ),
          Text('Return ${item.returnReference}'),
          if (item.settlementBlocker != null)
            Text(
              item.settlementBlocker!,
              style: TextStyle(color: Theme.of(context).colorScheme.error),
            ),
          if (canRecordPayment)
            FilledButton.icon(
              key: Key('record-tax-payment-${item.taxReturnId}'),
              onPressed: busy ? null : onRecordPayment,
              icon: const Icon(Icons.receipt_long_outlined),
              label: const Text('Record full-payment evidence'),
            ),
          if (canPrepare)
            FilledButton.icon(
              key: Key('prepare-tax-settlement-${item.taxReturnId}'),
              onPressed: busy ? null : onPrepare,
              icon: const Icon(Icons.fact_check_outlined),
              label: const Text('Prepare settlement'),
            ),
          if (canPost)
            FilledButton.icon(
              key: Key('post-tax-settlement-${item.taxReturnId}'),
              onPressed: busy ? null : onPost,
              icon: const Icon(Icons.lock_outline),
              label: const Text('Post settlement'),
            ),
          if (busy) const LinearProgressIndicator(),
        ],
      ),
    ),
  );
}

class _ReturnEvidenceFields {
  const _ReturnEvidenceFields(
    this.periodStart,
    this.periodEnd,
    this.filingDate,
    this.returnReference,
    this.evidenceReference,
    this.evidenceDigest,
    this.evidenceNote,
  );
  final String periodStart;
  final String periodEnd;
  final String filingDate;
  final String returnReference;
  final String evidenceReference;
  final String evidenceDigest;
  final String evidenceNote;
}

class _ReturnEvidenceDialog extends StatefulWidget {
  const _ReturnEvidenceDialog();
  @override
  State<_ReturnEvidenceDialog> createState() => _ReturnEvidenceDialogState();
}

class _ReturnEvidenceDialogState extends State<_ReturnEvidenceDialog> {
  final _controllers = List<TextEditingController>.generate(
    7,
    (_) => TextEditingController(),
  );
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
      'Period start (YYYY-MM-DD)',
      'Period end (YYYY-MM-DD)',
      'Filing date (YYYY-MM-DD)',
      'Return reference',
      'Evidence reference',
      'Evidence SHA-256',
      'Evidence note',
    ];
    return AlertDialog(
      title: const Text('Retained return evidence'),
      content: SingleChildScrollView(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: List<Widget>.generate(
            labels.length,
            (index) => Padding(
              padding: const EdgeInsets.only(bottom: 8),
              child: TextField(
                controller: _controllers[index],
                decoration: InputDecoration(labelText: labels[index]),
                minLines: index == 6 ? 2 : 1,
                maxLines: index == 6 ? 4 : 1,
              ),
            ),
          ),
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
            _ReturnEvidenceFields(
              _controllers[0].text.trim(),
              _controllers[1].text.trim(),
              _controllers[2].text.trim(),
              _controllers[3].text.trim(),
              _controllers[4].text.trim(),
              _controllers[5].text.trim(),
              _controllers[6].text.trim(),
            ),
          ),
          child: const Text('Review'),
        ),
      ],
    );
  }
}

class _PaymentEvidenceFields {
  const _PaymentEvidenceFields(
    this.paymentDate,
    this.cashAccountSystemKey,
    this.paymentReference,
    this.evidenceReference,
    this.evidenceDigest,
    this.evidenceNote,
  );
  final String paymentDate;
  final String cashAccountSystemKey;
  final String paymentReference;
  final String evidenceReference;
  final String evidenceDigest;
  final String evidenceNote;
}

class _PaymentEvidenceDialog extends StatefulWidget {
  const _PaymentEvidenceDialog({required this.minimumDate});
  final String minimumDate;
  @override
  State<_PaymentEvidenceDialog> createState() => _PaymentEvidenceDialogState();
}

class _PaymentEvidenceDialogState extends State<_PaymentEvidenceDialog> {
  final _controllers = List<TextEditingController>.generate(
    5,
    (_) => TextEditingController(),
  );
  String _cash = 'cash_office';
  @override
  void initState() {
    super.initState();
    _controllers.first.text = widget.minimumDate;
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
      'Payment date (YYYY-MM-DD)',
      'Payment reference',
      'Evidence reference',
      'Evidence SHA-256',
      'Evidence note',
    ];
    return AlertDialog(
      title: const Text('Retained full-payment evidence'),
      content: SingleChildScrollView(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: <Widget>[
            DropdownButtonFormField<String>(
              initialValue: _cash,
              decoration: const InputDecoration(labelText: 'Cash account'),
              items: const <DropdownMenuItem<String>>[
                DropdownMenuItem(
                  value: 'cash_office',
                  child: Text('Cash - Office'),
                ),
                DropdownMenuItem(
                  value: 'cash_bank_gcash',
                  child: Text('Cash - Bank / GCash'),
                ),
              ],
              onChanged: (value) => setState(() => _cash = value ?? _cash),
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
            _PaymentEvidenceFields(
              _controllers[0].text.trim(),
              _cash,
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

String _taxType(String value) => value == 'documentary_stamp_tax'
    ? 'Documentary stamp tax'
    : 'Percentage tax — lending';
String _settlementStatus(String value) => switch (value) {
  'return_recorded_awaiting_payment' => 'Awaiting payment',
  'payment_evidence_ready' => 'Ready',
  'settlement_prepared' => 'Prepared',
  'settled' => 'Settled',
  'settled_adjustment_review_required' => 'Adjustment review',
  'settled_adjustment_in_progress' => 'Adjustment in progress',
  'settled_adjustment_recorded' => 'Adjusted',
  _ => 'Blocked',
};
String _money(int cents) =>
    '${cents ~/ 100}.${(cents % 100).toString().padLeft(2, '0')}';
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
