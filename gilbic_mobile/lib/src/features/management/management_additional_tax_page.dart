import 'dart:math';

import 'package:flutter/material.dart';
import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/device/device_identity.dart';
import 'package:gilbic_mobile/src/core/management/additional_tax.dart';
import 'package:gilbic_mobile/src/core/management/additional_tax_repository.dart';
import 'package:gilbic_mobile/src/core/network/spina_api.dart';
import 'package:gilbic_mobile/src/features/management/review/management_review.dart';

class ManagementAdditionalTaxPage extends StatefulWidget {
  const ManagementAdditionalTaxPage({
    required this.session,
    required this.deviceIdentityProvider,
    this.repository,
    this.confirmationTokenGenerator,
    this.idempotencyKeyGenerator,
    super.key,
  });
  final UserSession session;
  final DeviceIdentityProvider deviceIdentityProvider;
  final AdditionalTaxRepository? repository;
  final String Function()? confirmationTokenGenerator;
  final String Function()? idempotencyKeyGenerator;
  @override
  State<ManagementAdditionalTaxPage> createState() =>
      _ManagementAdditionalTaxPageState();
}

class _ManagementAdditionalTaxPageState
    extends State<ManagementAdditionalTaxPage> {
  late final AdditionalTaxRepository _repository;
  late final String Function() _token;
  late final String Function() _idempotency;
  final Map<String, String> _postingTokens = <String, String>{};
  AdditionalTaxOverview? _overview;
  String? _error;
  String? _busy;
  bool _loading = true;
  bool _writeStateUncertain = false;

  @override
  void initState() {
    super.initState();
    _repository = widget.repository ?? SpinaAdditionalTaxRepository();
    _token = widget.confirmationTokenGenerator ?? _newDigest;
    _idempotency = widget.idempotencyKeyGenerator ?? _newUuid;
    _load();
  }

  Future<void> _load() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final device = await widget.deviceIdentityProvider.load();
      final overview = await _repository.load(
        widget.session,
        deviceId: device.installationId,
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
      if (mounted)
        setState(() => _error = 'Additional tax could not be loaded.');
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  bool _allowed(String action, String permission) {
    final p = _overview?.permissions;
    if (p == null || _writeStateUncertain) return false;
    final server = switch (action) {
      'evidence' => p.amendmentEvidenceRecord,
      'prepare-liability' => p.liabilityPrepare,
      'post-liability' => p.liabilityPost,
      'payment' => p.paymentEvidenceRecord,
      'prepare-settlement' => p.settlementPrepare,
      'post-settlement' => p.settlementPost,
      _ => false,
    };
    return server && widget.session.hasPermission(permission);
  }

  Future<bool> _confirm({
    required String record,
    required String status,
    required String next,
    required String consequence,
    required List<ManagementReviewFact> facts,
  }) => showManagementReviewConfirmation(
    context,
    ManagementReviewPresentation.validated(
      surface: ManagementMutationSurface.additionalTax,
      recordLabel: 'Protected additional-tax workflow',
      recordValue: record,
      statusLabel: status,
      facts: facts,
      warnings: const <ManagementReviewWarning>[
        ManagementReviewWarning(
          severity: ManagementReviewWarningSeverity.caution,
          message:
              'Original return, liability, payment and settlement history remain immutable. The server revalidates every coordinate.',
        ),
      ],
      nextActionLabel: next,
      consequence: consequence,
      risk: ManagementReviewRisk.protectedFinancial,
    ),
  );

  Future<void> _record(AdditionalTaxCandidate candidate) async {
    if (!_allowed(
      'evidence',
      'accounting.tax.additional_amendment_evidence.record',
    ))
      return;
    final fields = await showDialog<_AmendmentFields>(
      context: context,
      builder: (_) => _AmendmentDialog(candidate: candidate),
    );
    if (fields == null || !mounted) return;
    if (!await _confirm(
          record: candidate.taxLiabilityPostingId,
          status: 'Server-derived upward amendment candidate',
          next: 'Record amendment evidence',
          consequence:
              'Records immutable evidence only; no liability or cash balance changes yet.',
          facts: <ManagementReviewFact>[
            ManagementReviewFact(
              label: 'Additional tax',
              value: candidate.additionalTaxDue,
            ),
            ManagementReviewFact(
              label: 'Revised return',
              value: candidate.revisedDeclaredTaxDue,
            ),
            ManagementReviewFact(
              label: 'Required payment',
              value: candidate.paymentRequiredAmount,
            ),
            ManagementReviewFact(label: 'Basis', value: fields.basis),
          ],
        ) ||
        !mounted)
      return;
    await _run(candidate.taxLiabilityPostingId, () async {
      final device = await widget.deviceIdentityProvider.load();
      await _repository.recordAmendmentEvidence(
        widget.session,
        deviceId: device.installationId,
        candidate: candidate,
        idempotencyKey: _idempotency(),
        amendmentBasis: fields.basis,
        amendmentDate: fields.date,
        amendmentReference: fields.reference,
        evidenceReference: fields.evidenceReference,
        evidenceDigest: fields.digest,
        evidenceNote: fields.note,
      );
      _message('Immutable additional-tax amendment evidence recorded.');
    });
  }

  Future<void> _prepareLiability(AdditionalTaxItem item) => _itemAction(
    item: item,
    action: 'prepare-liability',
    permission: 'accounting.tax.additional_amendment.prepare',
    status: 'Amendment evidence ready',
    next: 'Prepare additional liability',
    consequence: 'Creates a protected General Journal draft only.',
    call: (device) => _repository.prepareLiability(
      widget.session,
      deviceId: device,
      item: item,
    ),
  );

  Future<void> _postLiability(AdditionalTaxItem item) async {
    item.requirePostLiability();
    final key =
        '${item.amendmentEvidenceId}|liability|${item.evidenceDigest}|${item.additionalTaxDue}|${item.liabilityFiscalPeriodId}';
    await _itemAction(
      item: item,
      action: 'post-liability',
      permission: 'accounting.tax.additional_amendment.post',
      status: 'Additional-liability draft prepared',
      next: 'Post additional liability',
      consequence:
          'Posts Dr tax expense / Cr 2100 with permanent audit evidence.',
      call: (device) => _repository.postLiability(
        widget.session,
        deviceId: device,
        item: item,
        confirmationToken: _postingTokens.putIfAbsent(key, _token),
      ),
      success: () => _postingTokens.remove(key),
    );
  }

  Future<void> _payment(AdditionalTaxItem item) async {
    if (!_allowed(
      'payment',
      'accounting.tax.additional_payment_evidence.record',
    ))
      return;
    item.requirePayment();
    final fields = await showDialog<_PaymentFields>(
      context: context,
      builder: (_) => _PaymentDialog(item: item),
    );
    if (fields == null || !mounted) return;
    if (!await _confirm(
          record: item.amendmentEvidenceId,
          status: 'Additional liability posted — exact payment required',
          next: 'Record payment evidence',
          consequence:
              'Records immutable payment evidence only; no cash journal posts yet.',
          facts: <ManagementReviewFact>[
            ManagementReviewFact(
              label: 'Required amount',
              value: item.paymentRequiredAmount,
            ),
            ManagementReviewFact(label: 'Payment date', value: fields.date),
            ManagementReviewFact(label: 'Cash account', value: fields.cashKey),
          ],
        ) ||
        !mounted)
      return;
    await _run(item.amendmentEvidenceId, () async {
      final device = await widget.deviceIdentityProvider.load();
      await _repository.recordPayment(
        widget.session,
        deviceId: device.installationId,
        item: item,
        idempotencyKey: _idempotency(),
        paymentDate: fields.date,
        cashAccountSystemKey: fields.cashKey,
        paymentReference: fields.reference,
        evidenceReference: fields.evidenceReference,
        evidenceDigest: fields.digest,
        evidenceNote: fields.note,
      );
      _message('Exact additional-tax payment evidence recorded.');
    });
  }

  Future<void> _prepareSettlement(AdditionalTaxItem item) => _itemAction(
    item: item,
    action: 'prepare-settlement',
    permission: 'accounting.tax.additional_settlement.prepare',
    status: 'Exact additional payment evidence ready',
    next: 'Prepare additional settlement',
    consequence: 'Creates a protected Dr 2100 / Cr cash draft only.',
    call: (device) => _repository.prepareSettlement(
      widget.session,
      deviceId: device,
      item: item,
    ),
  );

  Future<void> _postSettlement(AdditionalTaxItem item) async {
    item.requirePostSettlement();
    final key =
        '${item.amendmentEvidenceId}|settlement|${item.paymentEvidenceDigest}|${item.paymentAmount}|${item.settlementFiscalPeriodId}';
    await _itemAction(
      item: item,
      action: 'post-settlement',
      permission: 'accounting.tax.additional_settlement.post',
      status: 'Additional-settlement draft prepared',
      next: 'Post additional settlement',
      consequence:
          'Posts Dr 2100 / Cr exact approved cash with permanent audit evidence.',
      call: (device) => _repository.postSettlement(
        widget.session,
        deviceId: device,
        item: item,
        confirmationToken: _postingTokens.putIfAbsent(key, _token),
      ),
      success: () => _postingTokens.remove(key),
    );
  }

  Future<void> _itemAction({
    required AdditionalTaxItem item,
    required String action,
    required String permission,
    required String status,
    required String next,
    required String consequence,
    required Future<AdditionalTaxItem> Function(String device) call,
    VoidCallback? success,
  }) async {
    if (!_allowed(action, permission)) return;
    if (!await _confirm(
          record: item.amendmentEvidenceId,
          status: status,
          next: next,
          consequence: consequence,
          facts: <ManagementReviewFact>[
            ManagementReviewFact(
              label: 'Additional tax',
              value: item.additionalTaxDue,
            ),
            ManagementReviewFact(
              label: 'Required payment',
              value: item.paymentRequiredAmount,
            ),
            ManagementReviewFact(
              label: 'Current status',
              value: item.amendmentStatus,
            ),
          ],
        ) ||
        !mounted)
      return;
    await _run(item.amendmentEvidenceId, () async {
      final device = await widget.deviceIdentityProvider.load();
      await call(device.installationId);
      success?.call();
      _message('$next completed.');
    });
  }

  Future<void> _run(String key, Future<void> Function() action) async {
    if (_busy != null) return;
    setState(() => _busy = key);
    try {
      await action();
      await _load();
    } on SpinaApiException catch (error) {
      if (mounted && error.code == 'network_unavailable') {
        setState(() => _writeStateUncertain = true);
        _message(
          'The result is uncertain. Refresh authoritative additional-tax state before retrying.',
        );
      } else if (mounted) {
        _message(error.message);
      }
    } on ArgumentError catch (error) {
      if (mounted)
        _message(error.message ?? 'Exact protected fields are required.');
    } on Object {
      if (mounted) {
        setState(() => _writeStateUncertain = true);
        _message(
          'The result is uncertain. Refresh authoritative additional-tax state before retrying.',
        );
      }
    } finally {
      if (mounted) setState(() => _busy = null);
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
      title: const Text('Additional Tax'),
      actions: <Widget>[
        IconButton(
          tooltip: 'Refresh additional tax',
          onPressed: _loading || _busy != null ? null : _load,
          icon: const Icon(Icons.refresh),
        ),
      ],
    ),
    body: SafeArea(child: _body()),
  );

  Widget _body() {
    final overview = _overview;
    if (_loading && overview == null)
      return const Center(child: CircularProgressIndicator());
    if (overview == null)
      return Center(child: Text(_error ?? 'Additional tax is unavailable.'));
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
          _Summary(overview.summary),
          Text(
            'Server-derived upward amendments',
            style: Theme.of(context).textTheme.titleMedium,
          ),
          if (overview.candidates.isEmpty)
            const Card(
              child: Padding(
                padding: EdgeInsets.all(14),
                child: Text(
                  'No exact upward-amendment candidates are eligible.',
                ),
              ),
            )
          else
            ...overview.candidates.map(
              (candidate) => Card(
                child: ListTile(
                  key: Key(
                    'additional-tax-candidate-${candidate.taxLiabilityPostingId}',
                  ),
                  leading: const Icon(Icons.trending_up),
                  title: Text(
                    '${candidate.originalItemTaxDue} → ${candidate.replacementItemTaxDue}',
                  ),
                  subtitle: Text(
                    'Additional ${candidate.additionalTaxDue} • payment ${candidate.paymentRequiredAmount}',
                  ),
                  trailing: FilledButton(
                    onPressed:
                        _busy == null &&
                            _allowed(
                              'evidence',
                              'accounting.tax.additional_amendment_evidence.record',
                            )
                        ? () => _record(candidate)
                        : null,
                    child: const Text('Record'),
                  ),
                ),
              ),
            ),
          const SizedBox(height: 10),
          Text(
            'Additional-tax queue',
            style: Theme.of(context).textTheme.titleMedium,
          ),
          if (overview.items.isEmpty)
            const Card(
              child: Padding(
                padding: EdgeInsets.all(14),
                child: Text('No retained additional-tax amendments yet.'),
              ),
            )
          else
            ...overview.items.map(_row),
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

  Widget _row(AdditionalTaxItem item) => Card(
    child: Padding(
      padding: const EdgeInsets.all(14),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: <Widget>[
          Text(
            'Additional ${item.additionalTaxDue}',
            style: Theme.of(context).textTheme.titleMedium,
          ),
          Text('${item.amendmentDate} • payment ${item.paymentRequiredAmount}'),
          Text(_status(item.amendmentStatus)),
          if (item.amendmentBlocker != null)
            Text(
              item.amendmentBlocker!,
              style: TextStyle(color: Theme.of(context).colorScheme.error),
            ),
          if (item.isEvidenceReady)
            _button(
              'Prepare liability',
              'prepare-additional-liability',
              item,
              () => _prepareLiability(item),
              _allowed(
                'prepare-liability',
                'accounting.tax.additional_amendment.prepare',
              ),
            ),
          if (item.isLiabilityPrepared)
            _button(
              'Post liability',
              'post-additional-liability',
              item,
              () => _postLiability(item),
              _allowed(
                'post-liability',
                'accounting.tax.additional_amendment.post',
              ),
            ),
          if (item.isAwaitingPayment)
            _button(
              'Record payment',
              'record-additional-payment',
              item,
              () => _payment(item),
              _allowed(
                'payment',
                'accounting.tax.additional_payment_evidence.record',
              ),
            ),
          if (item.isPaymentReady)
            _button(
              'Prepare settlement',
              'prepare-additional-settlement',
              item,
              () => _prepareSettlement(item),
              _allowed(
                'prepare-settlement',
                'accounting.tax.additional_settlement.prepare',
              ),
            ),
          if (item.isSettlementPrepared)
            _button(
              'Post settlement',
              'post-additional-settlement',
              item,
              () => _postSettlement(item),
              _allowed(
                'post-settlement',
                'accounting.tax.additional_settlement.post',
              ),
            ),
          if (_busy == item.amendmentEvidenceId)
            const LinearProgressIndicator(),
        ],
      ),
    ),
  );

  Widget _button(
    String label,
    String key,
    AdditionalTaxItem item,
    VoidCallback action,
    bool allowed,
  ) => FilledButton(
    key: Key('$key-${item.amendmentEvidenceId}'),
    onPressed: allowed && _busy == null ? action : null,
    child: Text(label),
  );
}

class _Summary extends StatelessWidget {
  const _Summary(this.value);
  final AdditionalTaxSummary value;
  @override
  Widget build(BuildContext context) => Card(
    key: const Key('additional-tax-summary'),
    child: Padding(
      padding: const EdgeInsets.all(14),
      child: Wrap(
        spacing: 12,
        runSpacing: 8,
        children: <Widget>[
          Text('Evidence: ${value.amendmentEvidenceCount}'),
          Text('Ready: ${value.amendmentReadyCount}'),
          Text('Awaiting payment: ${value.awaitingPaymentCount}'),
          Text('Settled: ${value.settledCount}'),
          Text('Recognized: ${value.recognizedAdditionalTaxTotal}'),
        ],
      ),
    ),
  );
}

class _AmendmentFields {
  const _AmendmentFields(
    this.basis,
    this.date,
    this.reference,
    this.evidenceReference,
    this.digest,
    this.note,
  );
  final String basis, date, reference, evidenceReference, digest, note;
}

class _AmendmentDialog extends StatefulWidget {
  const _AmendmentDialog({required this.candidate});
  final AdditionalTaxCandidate candidate;
  @override
  State<_AmendmentDialog> createState() => _AmendmentDialogState();
}

class _AmendmentDialogState extends State<_AmendmentDialog> {
  String _basis = 'amended_return';
  final _fields = List<TextEditingController>.generate(
    5,
    (_) => TextEditingController(),
  );
  @override
  void initState() {
    super.initState();
    _fields.first.text = widget.candidate.filingDate;
  }

  @override
  void dispose() {
    for (final field in _fields) {
      field.dispose();
    }
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => AlertDialog(
    title: const Text('Retained amendment evidence'),
    content: SingleChildScrollView(
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: <Widget>[
          Text('Additional ${widget.candidate.additionalTaxDue}'),
          DropdownButtonFormField<String>(
            initialValue: _basis,
            items: const <DropdownMenuItem<String>>[
              DropdownMenuItem(
                value: 'amended_return',
                child: Text('Amended return'),
              ),
              DropdownMenuItem(
                value: 'additional_assessment',
                child: Text('Additional assessment'),
              ),
            ],
            onChanged: (value) => setState(() => _basis = value!),
          ),
          ..._textFields(_fields, const <String>[
            'Amendment date (YYYY-MM-DD)',
            'Amendment reference',
            'Evidence reference',
            'Evidence SHA-256',
            'Evidence note',
          ]),
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
          _AmendmentFields(
            _basis,
            _fields[0].text.trim(),
            _fields[1].text.trim(),
            _fields[2].text.trim(),
            _fields[3].text.trim(),
            _fields[4].text.trim(),
          ),
        ),
        child: const Text('Review'),
      ),
    ],
  );
}

class _PaymentFields {
  const _PaymentFields(
    this.date,
    this.cashKey,
    this.reference,
    this.evidenceReference,
    this.digest,
    this.note,
  );
  final String date, cashKey, reference, evidenceReference, digest, note;
}

class _PaymentDialog extends StatefulWidget {
  const _PaymentDialog({required this.item});
  final AdditionalTaxItem item;
  @override
  State<_PaymentDialog> createState() => _PaymentDialogState();
}

class _PaymentDialogState extends State<_PaymentDialog> {
  String _cash = 'cash_office';
  final _fields = List<TextEditingController>.generate(
    5,
    (_) => TextEditingController(),
  );
  @override
  void initState() {
    super.initState();
    _fields.first.text = widget.item.amendmentDate;
  }

  @override
  void dispose() {
    for (final field in _fields) {
      field.dispose();
    }
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => AlertDialog(
    title: const Text('Exact additional payment evidence'),
    content: SingleChildScrollView(
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: <Widget>[
          Text(
            'Required amount (not editable): ${widget.item.paymentRequiredAmount}',
          ),
          DropdownButtonFormField<String>(
            initialValue: _cash,
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
            onChanged: (value) => setState(() => _cash = value!),
          ),
          ..._textFields(_fields, const <String>[
            'Payment date (YYYY-MM-DD)',
            'Payment reference',
            'Evidence reference',
            'Evidence SHA-256',
            'Evidence note',
          ]),
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
          _PaymentFields(
            _fields[0].text.trim(),
            _cash,
            _fields[1].text.trim(),
            _fields[2].text.trim(),
            _fields[3].text.trim(),
            _fields[4].text.trim(),
          ),
        ),
        child: const Text('Review'),
      ),
    ],
  );
}

List<Widget> _textFields(
  List<TextEditingController> fields,
  List<String> labels,
) => List<Widget>.generate(
  fields.length,
  (index) => Padding(
    padding: const EdgeInsets.only(top: 8),
    child: TextField(
      controller: fields[index],
      decoration: InputDecoration(labelText: labels[index]),
      minLines: index == fields.length - 1 ? 2 : 1,
      maxLines: index == fields.length - 1 ? 4 : 1,
    ),
  ),
);

String _status(String value) => value.replaceAll('_', ' ');
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
