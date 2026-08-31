import 'dart:math';

import 'package:flutter/material.dart';
import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/device/device_identity.dart';
import 'package:gilbic_mobile/src/core/management/tax_recoverable.dart';
import 'package:gilbic_mobile/src/core/management/tax_recoverable_repository.dart';
import 'package:gilbic_mobile/src/core/network/spina_api.dart';
import 'package:gilbic_mobile/src/features/management/review/management_review.dart';

class ManagementTaxRecoverablePage extends StatefulWidget {
  const ManagementTaxRecoverablePage({
    required this.session,
    required this.deviceIdentityProvider,
    this.repository,
    this.confirmationTokenGenerator,
    this.idempotencyKeyGenerator,
    super.key,
  });
  final UserSession session;
  final DeviceIdentityProvider deviceIdentityProvider;
  final TaxRecoverableRepository? repository;
  final String Function()? confirmationTokenGenerator;
  final String Function()? idempotencyKeyGenerator;

  @override
  State<ManagementTaxRecoverablePage> createState() =>
      _ManagementTaxRecoverablePageState();
}

class _ManagementTaxRecoverablePageState
    extends State<ManagementTaxRecoverablePage> {
  late final TaxRecoverableRepository _repository;
  late final String Function() _token;
  late final String Function() _idempotency;
  final Map<String, String> _postingTokens = <String, String>{};
  TaxRecoverableWorkspace? _workspace;
  String? _error;
  String? _busy;
  bool _loading = true;
  bool _writeStateUncertain = false;

  @override
  void initState() {
    super.initState();
    _repository = widget.repository ?? SpinaTaxRecoverableRepository();
    _token = widget.confirmationTokenGenerator ?? _newDigest;
    _idempotency = widget.idempotencyKeyGenerator ?? _newUuid;
    _load();
  }

  Future<bool> _load() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final device = await widget.deviceIdentityProvider.load();
      final result = await _repository.load(
        widget.session,
        deviceId: device.installationId,
      );
      if (mounted) {
        setState(() {
          _workspace = result;
          _writeStateUncertain = false;
        });
      }
      return true;
    } on SpinaApiException catch (error) {
      if (mounted) setState(() => _error = error.message);
    } on Object {
      if (mounted) {
        setState(() => _error = 'Tax Recoverable could not be loaded.');
      }
    } finally {
      if (mounted) setState(() => _loading = false);
    }
    return false;
  }

  bool _refundAllowed(String action, String permission) {
    final value = _workspace?.refunds.permissions;
    if (value == null || _writeStateUncertain) return false;
    final server = switch (action) {
      'evidence' => value.evidenceRecord,
      'prepare' => value.prepare,
      'post' => value.post,
      _ => false,
    };
    return server && widget.session.hasPermission(permission);
  }

  bool _creditAllowed(String action, String permission) {
    final value = _workspace?.credits.permissions;
    if (value == null || _writeStateUncertain) return false;
    final server = switch (action) {
      'evidence' => value.evidenceRecord,
      'prepare' => value.prepare,
      'post' => value.post,
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
      binding: ManagementMutationBinding.taxRecoverable,
      recordLabel: 'Protected Tax Recoverable workflow',
      recordValue: record,
      statusLabel: status,
      facts: facts,
      warnings: const <ManagementReviewWarning>[
        ManagementReviewWarning(
          severity: ManagementReviewWarningSeverity.caution,
          message:
              'Refund and credit are mutually exclusive full-realization paths. The protected server revalidates every coordinate.',
        ),
      ],
      nextActionLabel: next,
      consequence: consequence,
    ),
  );

  Future<void> _recordRefund(TaxRecoverableRefundCandidate candidate) async {
    const permission = 'accounting.tax.recoverable_refund_evidence.record';
    if (!_refundAllowed('evidence', permission)) return;
    final fields = await showDialog<_RefundFields>(
      context: context,
      builder: (_) => _RefundDialog(candidate: candidate),
    );
    if (fields == null || !mounted) return;
    if (!await _confirm(
          record: candidate.adjustmentPostingId,
          status: 'Exact unreserved 1130 Tax Recoverable',
          next: 'Record cash-refund evidence',
          consequence:
              'Records immutable refund evidence only; cash and 1130 do not change yet.',
          facts: <ManagementReviewFact>[
            ManagementReviewFact(
              label: 'Exact refund',
              value: candidate.recoverableAmount,
            ),
            ManagementReviewFact(label: 'Refund date', value: fields.date),
            ManagementReviewFact(
              label: 'Cash account',
              value: fields.cashAccountCode,
            ),
          ],
        ) ||
        !mounted) {
      return;
    }
    await _run(candidate.adjustmentPostingId, () async {
      final device = await widget.deviceIdentityProvider.load();
      await _repository.recordRefundEvidence(
        widget.session,
        deviceId: device.installationId,
        candidate: candidate,
        idempotencyKey: _idempotency(),
        refundDate: fields.date,
        cashAccountCode: fields.cashAccountCode,
        refundReference: fields.reference,
        authorityReference: fields.authority,
        evidenceDigest: fields.digest,
        evidenceNote: fields.note,
      );
      _message('Immutable cash-refund evidence recorded.');
    });
  }

  Future<void> _recordCredit(TaxRecoverableCreditCandidate candidate) async {
    const permission = 'accounting.tax.recoverable_credit_evidence.record';
    if (!_creditAllowed('evidence', permission)) return;
    final fields = await showDialog<_CreditFields>(
      context: context,
      builder: (_) => _CreditDialog(candidate: candidate),
    );
    if (fields == null || !mounted) return;
    if (!await _confirm(
          record: candidate.adjustmentPostingId,
          status: 'Exact recoverable and unpaid same-tax return',
          next: 'Record tax-credit evidence',
          consequence:
              'Records immutable credit evidence only; 2100 and 1130 do not change yet.',
          facts: <ManagementReviewFact>[
            ManagementReviewFact(
              label: 'Exact credit',
              value: candidate.creditAmount,
            ),
            ManagementReviewFact(
              label: 'Target return',
              value: candidate.targetReturnReference,
            ),
            ManagementReviewFact(label: 'Application date', value: fields.date),
          ],
        ) ||
        !mounted) {
      return;
    }
    await _run(candidate.adjustmentPostingId, () async {
      final device = await widget.deviceIdentityProvider.load();
      await _repository.recordCreditEvidence(
        widget.session,
        deviceId: device.installationId,
        candidate: candidate,
        idempotencyKey: _idempotency(),
        applicationDate: fields.date,
        applicationReference: fields.reference,
        authorityReference: fields.authority,
        evidenceDigest: fields.digest,
        evidenceNote: fields.note,
      );
      _message('Immutable tax-credit evidence recorded.');
    });
  }

  Future<void> _prepareRefund(TaxRecoverableRefundItem item) => _refundAction(
    item: item,
    action: 'prepare',
    permission: 'accounting.tax.recoverable_refund.prepare',
    status: 'Cash-refund evidence ready',
    next: 'Prepare refund journal',
    consequence: 'Creates a protected Dr cash / Cr 1130 draft only.',
    call: (device) =>
        _repository.prepareRefund(widget.session, deviceId: device, item: item),
  );

  Future<void> _postRefund(TaxRecoverableRefundItem item) async {
    item.requirePost();
    final key =
        '${item.refundEvidenceId}|${item.evidenceDigest}|${item.refundAmount}|${item.fiscalPeriodId}';
    await _refundAction(
      item: item,
      action: 'post',
      permission: 'accounting.tax.recoverable_refund.post',
      status: 'Cash-refund journal prepared',
      next: 'Post cash refund',
      consequence:
          'Posts Dr exact approved cash / Cr 1130 with permanent audit evidence.',
      call: (device) => _repository.postRefund(
        widget.session,
        deviceId: device,
        item: item,
        confirmationToken: _postingTokens.putIfAbsent(key, _token),
      ),
      success: () => _postingTokens.remove(key),
    );
  }

  Future<void> _prepareCredit(TaxRecoverableCreditItem item) => _creditAction(
    item: item,
    action: 'prepare',
    permission: 'accounting.tax.recoverable_credit.prepare',
    status: 'Tax-credit evidence ready',
    next: 'Prepare credit journal',
    consequence: 'Creates a protected Dr 2100 / Cr 1130 draft only.',
    call: (device) =>
        _repository.prepareCredit(widget.session, deviceId: device, item: item),
  );

  Future<void> _postCredit(TaxRecoverableCreditItem item) async {
    item.requirePost();
    final key =
        '${item.creditEvidenceId}|${item.evidenceDigest}|${item.creditAmount}|${item.fiscalPeriodId}';
    await _creditAction(
      item: item,
      action: 'post',
      permission: 'accounting.tax.recoverable_credit.post',
      status: 'Tax-credit journal prepared',
      next: 'Post tax credit',
      consequence:
          'Posts Dr 2100 / Cr 1130 for the exact full credit with permanent audit evidence.',
      call: (device) => _repository.postCredit(
        widget.session,
        deviceId: device,
        item: item,
        confirmationToken: _postingTokens.putIfAbsent(key, _token),
      ),
      success: () => _postingTokens.remove(key),
    );
  }

  Future<void> _refundAction({
    required TaxRecoverableRefundItem item,
    required String action,
    required String permission,
    required String status,
    required String next,
    required String consequence,
    required Future<TaxRecoverableRefundItem> Function(String device) call,
    VoidCallback? success,
  }) async {
    if (!_refundAllowed(action, permission)) return;
    if (!await _confirm(
          record: item.refundEvidenceId,
          status: status,
          next: next,
          consequence: consequence,
          facts: <ManagementReviewFact>[
            ManagementReviewFact(
              label: 'Exact amount',
              value: item.refundAmount,
            ),
            ManagementReviewFact(
              label: 'Cash account',
              value: item.cashAccountCode,
            ),
            ManagementReviewFact(label: 'Status', value: item.refundStatus),
          ],
        ) ||
        !mounted) {
      return;
    }
    await _run(item.refundEvidenceId, () async {
      final device = await widget.deviceIdentityProvider.load();
      await call(device.installationId);
      success?.call();
      _message('$next completed.');
    });
  }

  Future<void> _creditAction({
    required TaxRecoverableCreditItem item,
    required String action,
    required String permission,
    required String status,
    required String next,
    required String consequence,
    required Future<TaxRecoverableCreditItem> Function(String device) call,
    VoidCallback? success,
  }) async {
    if (!_creditAllowed(action, permission)) return;
    if (!await _confirm(
          record: item.creditEvidenceId,
          status: status,
          next: next,
          consequence: consequence,
          facts: <ManagementReviewFact>[
            ManagementReviewFact(
              label: 'Exact amount',
              value: item.creditAmount,
            ),
            ManagementReviewFact(
              label: 'Target return',
              value: item.targetTaxReturnId,
            ),
            ManagementReviewFact(label: 'Status', value: item.creditStatus),
          ],
        ) ||
        !mounted) {
      return;
    }
    await _run(item.creditEvidenceId, () async {
      final device = await widget.deviceIdentityProvider.load();
      await call(device.installationId);
      success?.call();
      _message('$next completed.');
    });
  }

  Future<void> _run(String key, Future<void> Function() action) async {
    if (_busy != null || _writeStateUncertain) return;
    setState(() => _busy = key);
    try {
      await action();
      final refreshed = await _load();
      if (!refreshed && mounted) {
        setState(() => _writeStateUncertain = true);
        _message(
          'The write succeeded but authoritative refresh failed. All actions stay locked until refresh succeeds.',
        );
      }
    } on SpinaApiException catch (error) {
      if (mounted && _isAmbiguousWrite(error)) {
        setState(() => _writeStateUncertain = true);
        _message(
          'The result is uncertain. Refresh authoritative Tax Recoverable state before retrying.',
        );
      } else if (mounted) {
        _message(error.message);
      }
    } on ArgumentError catch (error) {
      if (mounted) {
        _message(error.message ?? 'Exact protected fields are required.');
      }
    } on Object {
      if (mounted) {
        setState(() => _writeStateUncertain = true);
        _message(
          'The result is uncertain. Refresh authoritative Tax Recoverable state before retrying.',
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
      title: const Text('Tax Recoverable'),
      actions: <Widget>[
        IconButton(
          tooltip: 'Refresh Tax Recoverable',
          onPressed: _loading || _busy != null ? null : _load,
          icon: const Icon(Icons.refresh),
        ),
      ],
    ),
    body: SafeArea(child: _body()),
  );

  Widget _body() {
    final value = _workspace;
    if (_loading && value == null) {
      return const Center(child: CircularProgressIndicator());
    }
    if (value == null) {
      return Center(child: Text(_error ?? 'Tax Recoverable is unavailable.'));
    }
    return RefreshIndicator(
      onRefresh: () async {
        await _load();
      },
      child: ListView(
        physics: const AlwaysScrollableScrollPhysics(),
        padding: const EdgeInsets.all(16),
        children: <Widget>[
          if (_writeStateUncertain)
            const Card(
              child: Padding(
                padding: EdgeInsets.all(14),
                child: Text(
                  'A write result is uncertain. All actions stay locked until refresh succeeds.',
                ),
              ),
            ),
          Text('Cash refund', style: Theme.of(context).textTheme.titleLarge),
          Text(value.refunds.notice),
          _summary(
            key: const Key('recoverable-refund-summary'),
            value: value.refunds.summary,
            completedLabel: 'Realized',
          ),
          _refundCandidates(value.refunds),
          ...value.refunds.items.map(_refundRow),
          const SizedBox(height: 24),
          Text('Tax credit', style: Theme.of(context).textTheme.titleLarge),
          Text(value.credits.notice),
          _summary(
            key: const Key('recoverable-credit-summary'),
            value: value.credits.summary,
            completedLabel: 'Applied',
          ),
          _creditCandidates(value.credits),
          ...value.credits.items.map(_creditRow),
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

  Widget _summary({
    required Key key,
    required TaxRecoverableSummary value,
    required String completedLabel,
  }) => Card(
    key: key,
    child: Padding(
      padding: const EdgeInsets.all(14),
      child: Wrap(
        spacing: 12,
        runSpacing: 8,
        children: <Widget>[
          Text('Evidence: ${value.evidenceCount}'),
          Text('Ready: ${value.readyCount}'),
          Text('Prepared: ${value.preparedCount}'),
          Text('$completedLabel: ${value.completedCount}'),
          Text('Total: ${value.completedTotal}'),
        ],
      ),
    ),
  );

  Widget _refundCandidates(TaxRecoverableRefundOverview value) {
    if (value.candidates.isEmpty) {
      return const Card(
        child: Padding(
          padding: EdgeInsets.all(14),
          child: Text('No exact cash-refund candidates are eligible.'),
        ),
      );
    }
    return Column(
      children: value.candidates
          .map(
            (candidate) => Card(
              child: ListTile(
                key: Key('refund-candidate-${candidate.adjustmentPostingId}'),
                leading: const Icon(Icons.payments_outlined),
                title: Text('Refund ${candidate.recoverableAmount}'),
                subtitle: Text(
                  '${candidate.taxType} • from ${candidate.minimumRefundDate}',
                ),
                trailing: FilledButton(
                  onPressed:
                      _busy == null &&
                          _refundAllowed(
                            'evidence',
                            'accounting.tax.recoverable_refund_evidence.record',
                          )
                      ? () => _recordRefund(candidate)
                      : null,
                  child: const Text('Record'),
                ),
              ),
            ),
          )
          .toList(growable: false),
    );
  }

  Widget _creditCandidates(TaxRecoverableCreditOverview value) {
    if (value.candidates.isEmpty) {
      return const Card(
        child: Padding(
          padding: EdgeInsets.all(14),
          child: Text('No exact tax-credit candidates are eligible.'),
        ),
      );
    }
    return Column(
      children: value.candidates
          .map(
            (candidate) => Card(
              child: ListTile(
                key: Key('credit-candidate-${candidate.targetTaxReturnId}'),
                leading: const Icon(Icons.swap_horiz),
                title: Text('Apply ${candidate.creditAmount}'),
                subtitle: Text(candidate.targetReturnReference),
                trailing: FilledButton(
                  onPressed:
                      _busy == null &&
                          _creditAllowed(
                            'evidence',
                            'accounting.tax.recoverable_credit_evidence.record',
                          )
                      ? () => _recordCredit(candidate)
                      : null,
                  child: const Text('Record'),
                ),
              ),
            ),
          )
          .toList(growable: false),
    );
  }

  Widget _refundRow(TaxRecoverableRefundItem item) => Card(
    child: Padding(
      padding: const EdgeInsets.all(14),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: <Widget>[
          Text('Refund ${item.refundAmount} • ${item.cashAccountCode}'),
          Text(item.refundStatus.replaceAll('_', ' ')),
          if (item.refundBlocker != null) Text(item.refundBlocker!),
          if (item.isEvidenceReady)
            FilledButton(
              onPressed:
                  _busy == null &&
                      _refundAllowed(
                        'prepare',
                        'accounting.tax.recoverable_refund.prepare',
                      )
                  ? () => _prepareRefund(item)
                  : null,
              child: const Text('Prepare refund'),
            ),
          if (item.isPrepared)
            FilledButton(
              onPressed:
                  _busy == null &&
                      _refundAllowed(
                        'post',
                        'accounting.tax.recoverable_refund.post',
                      )
                  ? () => _postRefund(item)
                  : null,
              child: const Text('Post refund'),
            ),
          if (_busy == item.refundEvidenceId) const LinearProgressIndicator(),
        ],
      ),
    ),
  );

  Widget _creditRow(TaxRecoverableCreditItem item) => Card(
    child: Padding(
      padding: const EdgeInsets.all(14),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: <Widget>[
          Text('Credit ${item.creditAmount} • ${item.applicationReference}'),
          Text(item.creditStatus.replaceAll('_', ' ')),
          if (item.creditBlocker != null) Text(item.creditBlocker!),
          if (item.isEvidenceReady)
            FilledButton(
              onPressed:
                  _busy == null &&
                      _creditAllowed(
                        'prepare',
                        'accounting.tax.recoverable_credit.prepare',
                      )
                  ? () => _prepareCredit(item)
                  : null,
              child: const Text('Prepare credit'),
            ),
          if (item.isPrepared)
            FilledButton(
              onPressed:
                  _busy == null &&
                      _creditAllowed(
                        'post',
                        'accounting.tax.recoverable_credit.post',
                      )
                  ? () => _postCredit(item)
                  : null,
              child: const Text('Post credit'),
            ),
          if (_busy == item.creditEvidenceId) const LinearProgressIndicator(),
        ],
      ),
    ),
  );
}

class _RefundFields {
  const _RefundFields(
    this.date,
    this.cashAccountCode,
    this.reference,
    this.authority,
    this.digest,
    this.note,
  );
  final String date, cashAccountCode, reference, authority, digest, note;
}

class _CreditFields {
  const _CreditFields(
    this.date,
    this.reference,
    this.authority,
    this.digest,
    this.note,
  );
  final String date, reference, authority, digest, note;
}

class _RefundDialog extends StatefulWidget {
  const _RefundDialog({required this.candidate});
  final TaxRecoverableRefundCandidate candidate;
  @override
  State<_RefundDialog> createState() => _RefundDialogState();
}

class _RefundDialogState extends State<_RefundDialog> {
  String _cash = '1010';
  final _fields = List<TextEditingController>.generate(
    5,
    (_) => TextEditingController(),
  );

  @override
  void initState() {
    super.initState();
    _fields.first.text = widget.candidate.minimumRefundDate;
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
    title: const Text('Retained cash-refund evidence'),
    content: SingleChildScrollView(
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: <Widget>[
          Text(
            'Exact amount (not editable): ${widget.candidate.recoverableAmount}',
          ),
          DropdownButtonFormField<String>(
            initialValue: _cash,
            isExpanded: true,
            items: const <DropdownMenuItem<String>>[
              DropdownMenuItem(
                value: '1010',
                child: Text('1010 Cash - Office'),
              ),
              DropdownMenuItem(
                value: '1030',
                child: Text('1030 Cash - Bank / GCash'),
              ),
            ],
            onChanged: (value) => setState(() => _cash = value!),
          ),
          ..._fieldsFor(_fields, const <String>[
            'Refund date (YYYY-MM-DD)',
            'Refund reference',
            'Authority reference',
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
          _RefundFields(
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

class _CreditDialog extends StatefulWidget {
  const _CreditDialog({required this.candidate});
  final TaxRecoverableCreditCandidate candidate;
  @override
  State<_CreditDialog> createState() => _CreditDialogState();
}

class _CreditDialogState extends State<_CreditDialog> {
  final _fields = List<TextEditingController>.generate(
    5,
    (_) => TextEditingController(),
  );

  @override
  void initState() {
    super.initState();
    _fields.first.text = widget.candidate.minimumApplicationDate;
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
    title: const Text('Retained tax-credit evidence'),
    content: SingleChildScrollView(
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: <Widget>[
          Text('Exact amount (not editable): ${widget.candidate.creditAmount}'),
          Text('Target return: ${widget.candidate.targetReturnReference}'),
          ..._fieldsFor(_fields, const <String>[
            'Application date (YYYY-MM-DD)',
            'Application reference',
            'Authority reference',
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
          _CreditFields(
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

List<Widget> _fieldsFor(
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

String _newDigest() => List<int>.generate(
  32,
  (_) => Random.secure().nextInt(256),
).map((value) => value.toRadixString(16).padLeft(2, '0')).join();

bool _isAmbiguousWrite(SpinaApiException error) =>
    const <String>{
      'network_unavailable',
      'invalid_server_response',
      'invalid_tax_payload',
    }.contains(error.code) ||
    (error.statusCode ?? 0) >= 500;

String _newUuid() {
  final bytes = List<int>.generate(16, (_) => Random.secure().nextInt(256));
  bytes[6] = (bytes[6] & 0x0f) | 0x40;
  bytes[8] = (bytes[8] & 0x3f) | 0x80;
  final hex = bytes
      .map((value) => value.toRadixString(16).padLeft(2, '0'))
      .join();
  return '${hex.substring(0, 8)}-${hex.substring(8, 12)}-${hex.substring(12, 16)}-${hex.substring(16, 20)}-${hex.substring(20)}';
}
