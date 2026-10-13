import 'dart:convert';
import 'dart:math';
import 'package:flutter/material.dart';
import 'package:gilbic_mobile/src/core/auth/app_role.dart';
import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/device/device_identity.dart';
import 'package:gilbic_mobile/src/core/management/accounting_readiness_repository.dart';
import 'package:gilbic_mobile/src/core/management/source_accounting_repository.dart';
import 'package:gilbic_mobile/src/core/management/transfer_accounting_evidence.dart';
import 'package:gilbic_mobile/src/core/network/spina_api.dart';
import 'package:gilbic_mobile/src/core/treasury/treasury_models.dart';
import 'package:gilbic_mobile/src/features/management/review/management_review.dart';

class ManagementTransferAccountingPage extends StatefulWidget {
  const ManagementTransferAccountingPage({
    required this.session,
    required this.deviceIdentityProvider,
    this.repository,
    this.uuidGenerator,
    super.key,
  });
  final UserSession session;
  final DeviceIdentityProvider deviceIdentityProvider;
  final SourceAccountingRepository? repository;
  final String Function()? uuidGenerator;
  @override
  State<ManagementTransferAccountingPage> createState() =>
      _ManagementTransferAccountingPageState();
}

class _TransferIntent {
  _TransferIntent({
    required this.path,
    required Map<String, dynamic> body,
    required this.presentation,
    required this.validate,
  }) : body = accountingObject(immutableTreasury(body));
  final String path;
  final Map<String, dynamic> body;
  final ManagementReviewPresentation presentation;
  final void Function(Map<String, dynamic>) validate;
}

class _ManagementTransferAccountingPageState
    extends State<ManagementTransferAccountingPage> {
  late SourceAccountingRepository _repository;
  late String _sessionScope;
  int _generation = 0;
  bool _busy = true, _denied = false, _rejected = false;
  String _device = '',
      _sourceAccount = '',
      _destinationAccount = '',
      _leg = 'source',
      _reference = '';
  String? _error;
  AccountingBookIdentity? _book;
  List<Map<String, dynamic>> _wallets = [];
  Map<String, dynamic>? _source, _prepared, _mappings;
  _TransferIntent? _review, _pending;
  bool get _can =>
      widget.session.hasRole(AppRole.management) &&
      widget.session.hasPermission('accounting.view') &&
      widget.session.hasPermission('accounting.journal.manage');
  String _scope(UserSession user) => jsonEncode([
    user.userId,
    user.accessToken,
    user.roles,
    user.rawRole,
    user.permissions,
  ]);
  bool _current(int generation) =>
      mounted &&
      generation == _generation &&
      _sessionScope == _scope(widget.session);
  @override
  void initState() {
    super.initState();
    _repository = widget.repository ?? SpinaSourceAccountingRepository();
    _sessionScope = _scope(widget.session);
    _load();
  }

  @override
  void didUpdateWidget(covariant ManagementTransferAccountingPage oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (_scope(widget.session) != _sessionScope ||
        oldWidget.deviceIdentityProvider != widget.deviceIdentityProvider ||
        oldWidget.repository != widget.repository) {
      _generation++;
      _clearPrivate();
      _sessionScope = _scope(widget.session);
      _repository = widget.repository ?? SpinaSourceAccountingRepository();
      _denied = false;
      _load();
    }
  }

  @override
  void dispose() {
    _generation++;
    _clearPrivate();
    super.dispose();
  }

  void _clearEvidence() {
    _source = _prepared = _mappings = null;
    _review = null;
  }

  void _clearPrivate() {
    _clearEvidence();
    _pending = null;
    _book = null;
    _wallets = [];
    _device = _sourceAccount = _destinationAccount = _reference = '';
    _leg = 'source';
  }

  Future<Map<String, dynamic>> _read(String path) =>
      _repository.read(widget.session, deviceId: _device, path: path);
  void _failure(Object error) {
    if (!mounted) return;
    setState(() {
      _busy = false;
      _error = error is SpinaApiException
          ? error.message
          : error is FormatException
          ? error.message
          : 'Accounting evidence could not be confirmed. Retry the unchanged request if submitted.';
      _rejected =
          error is SpinaApiException && [409, 422].contains(error.statusCode);
      if (error is SpinaApiException &&
          ([401, 403, 426].contains(error.statusCode) ||
              error.code == 'accounting_scope_changed')) {
        _generation++;
        _clearPrivate();
        _denied = true;
      }
    });
  }

  Future<void> _act(Future<void> Function() action) async {
    if (_busy || _denied) return;
    try {
      accountingCheck(
        _can && _sessionScope == _scope(widget.session),
        'Current Management journal permission is required.',
      );
      await action();
    } on Object catch (error) {
      _failure(error);
    }
  }

  Future<void> _freshBook(int generation) async {
    final payload = await _read('$sourceAccountingBase/book');
    if (!_current(generation)) return;
    final book = AccountingBookIdentity.fromPayload(
      accountingObject(payload['book']),
    );
    accountingCheck(
      book.configured,
      'Configure the accounting book before reviewing transfers.',
    );
    if (_book != null && _book!.bookId != book.bookId) {
      throw const SpinaApiException(
        'Accounting book changed. Reopen this task.',
        code: 'accounting_scope_changed',
      );
    }
    _book = book;
  }

  Future<void> _load() async {
    if (_pending != null) return;
    final generation = ++_generation;
    setState(() {
      _busy = true;
      _error = null;
      _clearEvidence();
    });
    try {
      accountingCheck(
        _can,
        'Current Management journal permission is required.',
      );
      final identity = await widget.deviceIdentityProvider.load();
      if (!_current(generation)) return;
      _device = identity.installationId;
      await _freshBook(generation);
      if (!_current(generation)) return;
      final workspace = await _read('$sourceTreasuryBase/workspace');
      if (!_current(generation)) return;
      final actor = accountingObject(workspace['actor']);
      accountingCheck(
        workspace['contract_version'] == 1 &&
            actor['user_id'] == widget.session.userId &&
            treasuryUuid(actor['device_id']) &&
            workspace['enabled'] == true &&
            workspace['owner_configured'] == true,
      );
      _wallets = accountingRows(workspace['accounts'])
          .where(
            (row) =>
                row['balance'] != null &&
                row['active'] != false &&
                ['physical_cash', 'gcash', 'bank'].contains(row['kind']),
          )
          .toList();
      accountingCheck(
        _wallets.every(
          (row) => treasuryUuid(row['id']) && row['alias'] is String,
        ),
      );
      if (!_wallets.any((row) => row['id'] == _sourceAccount)) {
        _sourceAccount = '';
      }
      if (!_wallets.any((row) => row['id'] == _destinationAccount)) {
        _destinationAccount = '';
      }
    } on Object catch (error) {
      if (_current(generation)) _failure(error);
    } finally {
      if (_current(generation)) setState(() => _busy = false);
    }
  }

  Map<String, dynamic> _validateSource(
    Map<String, dynamic> value,
    String transfer,
  ) => validateTransferAccounting(
    value,
    bookId: _book!.bookId!,
    sourceAccountId: _sourceAccount,
    destinationAccountId: _destinationAccount,
    transferId: transfer,
    leg: _leg,
  );
  void _validatePreparation(
    Map<String, dynamic> value, {
    Map<String, dynamic>? expected,
    String? requestId,
    String? preparationId,
  }) {
    final row = accountingObject(value['preparation']);
    accountingCheck(
      treasuryUuid(row['id']) &&
          row['actor_user_id'] == widget.session.userId &&
          accountingDigest(row['confirmation_token']) &&
          (requestId == null || row['request_id'] == requestId) &&
          (preparationId == null || row['id'] == preparationId) &&
          treasuryUuid(row['source_mapping_id']) &&
          treasuryUuid(row['destination_mapping_id']),
    );
    final projected = _validateSource({
      ...accountingObject(row['snapshot']),
      'source_digest': row['source_digest'],
    }, requireTreasuryId(row['transfer_id']));
    for (final key in [
      'book_id',
      'transfer_id',
      'leg',
      'event_id',
      'source_account_id',
      'destination_account_id',
    ]) {
      accountingCheck(row[key] == projected[key]);
    }
    if (expected != null) {
      accountingCheck(
        jsonEncode(projected) == jsonEncode(expected) &&
            row['source_mapping_id'] == _mappings!['source_mapping_id'] &&
            row['destination_mapping_id'] ==
                _mappings!['destination_mapping_id'],
      );
    }
    if (value['posting'] != null) {
      final posted = accountingObject(value['posting']);
      accountingCheck(
        posted['preparation_id'] == row['id'] &&
            treasuryUuid(posted['journal_entry_id']) &&
            posted['exact_posted'] is bool &&
            posted['correction_pending'] is bool,
      );
      for (final key in [
        'book_id',
        'transfer_id',
        'leg',
        'event_id',
        'source_account_id',
        'destination_account_id',
        'source_digest',
      ]) {
        accountingCheck(posted[key] == row[key]);
      }
    }
  }

  Future<void> _lookup({bool recover = false}) async {
    accountingCheck(
      _wallets.any((row) => row['id'] == _sourceAccount) &&
          _wallets.any((row) => row['id'] == _destinationAccount) &&
          _sourceAccount != _destinationAccount &&
          treasuryUuid(_reference),
      'Choose two authorized wallets and an existing transfer or preparation reference.',
    );
    final generation = ++_generation;
    setState(() {
      _clearEvidence();
      _busy = true;
      _error = null;
    });
    try {
      await _freshBook(generation);
      if (!_current(generation)) return;
      if (recover) {
        final result = await _read(
          '$sourceAccountingBase/treasury/transfer-preparations/$_reference',
        );
        if (!_current(generation)) return;
        _validatePreparation(result, preparationId: _reference);
        _prepared = result;
        final row = accountingObject(result['preparation']);
        _mappings = {
          'source_mapping_id': row['source_mapping_id'],
          'destination_mapping_id': row['destination_mapping_id'],
        };
        _source = _validateSource({
          ...accountingObject(row['snapshot']),
          'source_digest': row['source_digest'],
        }, row['transfer_id'] as String);
      } else {
        final mappings = <String, dynamic>{};
        for (final pair in [
          ('source_mapping_id', _sourceAccount),
          ('destination_mapping_id', _destinationAccount),
        ]) {
          final result = await _read(
            '$sourceAccountingBase/treasury/accounts/${pair.$2}/cash-mapping',
          );
          if (!_current(generation)) return;
          final mapping = accountingObject(result['mapping']);
          accountingCheck(
            result['book_id'] == _book!.bookId &&
                result['treasury_account_id'] == pair.$2 &&
                treasuryUuid(mapping['id']) &&
                mapping['book_id'] == _book!.bookId &&
                mapping['treasury_account_id'] == pair.$2,
            'Both wallets need an explicit cash mapping before review.',
          );
          mappings[pair.$1] = mapping['id'];
        }
        _mappings = mappings;
        final query = Uri(
          queryParameters: {
            'leg': _leg,
            for (final entry in mappings.entries)
              entry.key: entry.value as String,
          },
        ).query;
        final result = await _read(
          '$sourceAccountingBase/treasury/transfers/$_reference/review?$query',
        );
        if (!_current(generation)) return;
        _source = _validateSource(result, _reference);
      }
    } on Object catch (error) {
      if (_current(generation)) {
        _clearEvidence();
        _failure(error);
      }
    } finally {
      if (_current(generation)) setState(() => _busy = false);
    }
  }

  List<(String, String)> _facts() => [
    ('Transfer reference', '${_source!['transfer_id']}'),
    ('Actual leg', _leg == 'source' ? 'Source debit' : 'Destination credit'),
    (
      'Source wallet',
      '${_wallets.firstWhere((row) => row['id'] == _sourceAccount)['alias']}',
    ),
    (
      'Destination wallet',
      '${_wallets.firstWhere((row) => row['id'] == _destinationAccount)['alias']}',
    ),
    ('Actual posting date', '${_source!['posting_date']}'),
    ('Principal', 'PHP ${_source!['amount']}'),
    ('Source transaction fee', 'PHP ${_source!['fee']}'),
    for (final row in accountingRows(_source!['lines']))
      (
        '${row['account_code']} · ${row['name']}',
        'Debit PHP ${row['debit']} · Credit PHP ${row['credit']}',
      ),
  ];
  Future<void> _reviewAction({required bool posting}) async {
    accountingCheck(_source != null && _pending == null);
    final expected = _source!, requestId = (widget.uuidGenerator ?? _uuid)();
    final row = posting ? accountingObject(_prepared!['preparation']) : null;
    final title = posting
        ? 'Post transfer leg accounting'
        : 'Prepare transfer leg accounting';
    final consequence = posting
        ? 'Posts only this verified actual leg to cash and transfer funds in transit, including its actual source fee. This does not initiate or record a bank transfer.'
        : 'Retains these exact actual-leg coordinates. Posting requires a separate confirmation.';
    setState(() {
      _review = _TransferIntent(
        path: posting
            ? '$sourceAccountingBase/treasury/transfer-preparations/${row!['id']}/post'
            : '$sourceAccountingBase/treasury/transfers/${expected['transfer_id']}/prepare',
        body: posting
            ? {
                'source_digest': expected['source_digest'],
                'confirmation_token': row!['confirmation_token'],
                'confirm': true,
              }
            : {
                'leg': _leg,
                ..._mappings!,
                'source_digest': expected['source_digest'],
                'request_id': requestId,
              },
        validate: (result) {
          _validatePreparation(
            result,
            expected: expected,
            requestId: posting ? null : requestId,
            preparationId: posting ? row!['id'] as String : null,
          );
          if (posting) {
            final posted = accountingObject(result['posting']);
            accountingCheck(
              posted['exact_posted'] == true &&
                  posted['journal_entry_id'] == result['journal_entry_id'],
            );
          }
        },
        presentation: ManagementReviewPresentation.validated(
          binding: ManagementMutationBinding.transferAccounting,
          recordLabel: 'Actual owned-wallet leg',
          recordValue: title,
          statusLabel: 'Awaiting explicit confirmation',
          facts: _facts()
              .map(
                (fact) => ManagementReviewFact(label: fact.$1, value: fact.$2),
              )
              .toList(),
          warnings: [
            ManagementReviewWarning(
              severity: ManagementReviewWarningSeverity.caution,
              message: consequence,
            ),
          ],
          nextActionLabel: title,
          consequence: consequence,
        ),
      );
    });
  }

  Future<void> _send() async {
    final held = _pending ?? _review;
    accountingCheck(_can && held != null);
    final generation = _generation;
    setState(() {
      _pending = held;
      _review = null;
      _busy = true;
      _error = null;
      _rejected = false;
    });
    try {
      await _freshBook(generation);
      if (!_current(generation)) return;
      final result = await _repository.write(
        widget.session,
        deviceId: _device,
        path: held!.path,
        body: held.body,
      );
      if (!_current(generation)) return;
      held.validate(result);
      setState(() {
        _pending = null;
        _prepared = result;
      });
    } on Object catch (error) {
      if (_current(generation)) _failure(error);
    } finally {
      if (_current(generation)) setState(() => _busy = false);
    }
  }

  Widget _button(String key, String label, Future<void> Function() action) =>
      Padding(
        padding: const EdgeInsets.symmetric(vertical: 6),
        child: OutlinedButton(
          key: Key(key),
          onPressed: _busy ? null : () => _act(action),
          child: Text(label),
        ),
      );
  Widget _wallet(
    String key,
    String label,
    String value,
    void Function(String) change,
  ) => DropdownButtonFormField<String>(
    key: Key(key),
    initialValue: value.isEmpty ? null : value,
    isExpanded: true,
    decoration: InputDecoration(labelText: label),
    items: _wallets
        .map(
          (row) => DropdownMenuItem(
            value: row['id'] as String,
            child: Text(row['alias'] as String),
          ),
        )
        .toList(),
    onChanged: _busy
        ? null
        : (value) => setState(() {
            change(value ?? '');
            _clearEvidence();
          }),
  );
  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(
      title: const Text('Transfer accounting'),
      actions: [
        IconButton(
          tooltip: 'Refresh transfer accounting',
          onPressed: _busy || _pending != null || _denied
              ? null
              : () => _act(_load),
          icon: const Icon(Icons.refresh),
        ),
      ],
    ),
    body: ListView(
      key: ValueKey(
        'transfer-$_generation-${_review != null}-${_pending != null}',
      ),
      padding: const EdgeInsets.all(16),
      children: [
        if (_busy) const LinearProgressIndicator(),
        if (_error != null) Text(_error!, key: const Key('transfer-error')),
        if (_book != null)
          Text('Book: ${_book!.entityLabel} · ${_book!.kindLabel}'),
        if (_pending != null) ...[
          const Text(
            'The result is not confirmed. Retry the unchanged request to recover it.',
          ),
          ManagementReviewPanel(review: _pending!.presentation, compact: true),
          _button('transfer-retry', 'Retry unchanged request', _send),
          if (_rejected)
            _button('transfer-reload', 'Reload current evidence', () async {
              setState(() => _pending = null);
              await _load();
            }),
        ] else if (_review != null) ...[
          ManagementReviewPanel(review: _review!.presentation),
          _button(
            'transfer-confirm',
            'Confirm: ${_review!.presentation.nextActionLabel}',
            _send,
          ),
          _button('transfer-cancel', 'Cancel', () async {
            setState(() => _review = null);
          }),
        ] else if (_book != null && !_denied) ...[
          const Text(
            'Review each independently verified transfer leg on its actual date. Funds may remain in transit until arrival. Overall accounting readiness remains a separate review.',
          ),
          _wallet(
            'transfer-source',
            'Source wallet',
            _sourceAccount,
            (value) => _sourceAccount = value,
          ),
          _wallet(
            'transfer-destination',
            'Destination wallet',
            _destinationAccount,
            (value) => _destinationAccount = value,
          ),
          DropdownButtonFormField<String>(
            key: const Key('transfer-leg'),
            initialValue: _leg,
            decoration: const InputDecoration(labelText: 'Actual leg'),
            items: const [
              DropdownMenuItem(value: 'source', child: Text('Source debit')),
              DropdownMenuItem(
                value: 'destination',
                child: Text('Destination credit'),
              ),
            ],
            onChanged: _busy
                ? null
                : (value) => setState(() {
                    _leg = value ?? 'source';
                    _clearEvidence();
                  }),
          ),
          TextFormField(
            key: const Key('transfer-reference'),
            initialValue: _reference,
            enabled: !_busy,
            maxLength: 36,
            decoration: const InputDecoration(
              labelText: 'Existing transfer or saved preparation reference',
            ),
            onChanged: (value) => setState(() {
              _reference = value.trim();
              _clearEvidence();
            }),
          ),
          _button('transfer-load', 'Load transfer accounting review', _lookup),
          _button(
            'transfer-recover',
            'Open saved preparation',
            () => _lookup(recover: true),
          ),
          if (_source != null) ...[
            for (final fact in _facts())
              Padding(
                padding: const EdgeInsets.symmetric(vertical: 3),
                child: Text('${fact.$1}: ${fact.$2}'),
              ),
            if (_prepared == null)
              _button(
                'transfer-prepare',
                'Prepare transfer leg accounting',
                () => _reviewAction(posting: false),
              )
            else ...[
              Text(
                _prepared!['posting'] != null &&
                        accountingObject(
                              _prepared!['posting'],
                            )['exact_posted'] ==
                            true
                    ? 'Transfer leg accounting posted'
                    : 'Transfer leg prepared for review',
              ),
              Text(
                'Preparation ${accountingObject(_prepared!['preparation'])['id']}',
              ),
              if (_prepared!['posting'] == null)
                _button(
                  'transfer-post',
                  'Review transfer leg posting',
                  () => _reviewAction(posting: true),
                )
              else ...[
                Text(
                  'Journal ${accountingObject(_prepared!['posting'])['journal_entry_id']}',
                ),
                Text(
                  accountingObject(
                            _prepared!['posting'],
                          )['correction_pending'] ==
                          true
                      ? 'A later source change requires correction review.'
                      : 'Retained exact posting evidence is available.',
                ),
              ],
            ],
          ],
        ],
      ],
    ),
  );
}

String _uuid() {
  final random = Random.secure(),
      bytes = List<int>.generate(16, (_) => random.nextInt(256));
  bytes[6] = (bytes[6] & 0x0f) | 0x40;
  bytes[8] = (bytes[8] & 0x3f) | 0x80;
  final text = bytes.map((b) => b.toRadixString(16).padLeft(2, '0')).join();
  return '${text.substring(0, 8)}-${text.substring(8, 12)}-${text.substring(12, 16)}-${text.substring(16, 20)}-${text.substring(20)}';
}
