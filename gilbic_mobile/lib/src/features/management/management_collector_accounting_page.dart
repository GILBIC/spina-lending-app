import 'dart:convert';
import 'dart:math';
import 'package:flutter/material.dart';
import 'package:gilbic_mobile/src/core/auth/app_role.dart';
import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/device/device_identity.dart';
import 'package:gilbic_mobile/src/core/management/accounting_readiness_repository.dart';
import 'package:gilbic_mobile/src/core/management/source_accounting_repository.dart';
import 'package:gilbic_mobile/src/core/management/collector_accounting_evidence.dart';
import 'package:gilbic_mobile/src/core/network/spina_api.dart';
import 'package:gilbic_mobile/src/core/treasury/treasury_models.dart';
import 'package:gilbic_mobile/src/features/management/review/management_review.dart';

class ManagementCollectorAccountingPage extends StatefulWidget {
  const ManagementCollectorAccountingPage({
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
  State<ManagementCollectorAccountingPage> createState() =>
      _ManagementCollectorAccountingPageState();
}

class _CollectorIntent {
  _CollectorIntent({
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

class _ManagementCollectorAccountingPageState
    extends State<ManagementCollectorAccountingPage> {
  late SourceAccountingRepository _repository;
  late String _sessionScope;
  int _generation = 0;
  bool _busy = true, _denied = false, _rejected = false;
  String _device = '', _account = '', _stage = 'settlement', _reference = '';
  String? _error;
  AccountingBookIdentity? _book;
  List<Map<String, dynamic>> _wallets = [];
  Map<String, dynamic>? _source, _prepared;
  _CollectorIntent? _review, _pending;
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
  void didUpdateWidget(covariant ManagementCollectorAccountingPage oldWidget) {
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
    _source = _prepared = null;
    _review = null;
  }

  void _clearPrivate() {
    _clearEvidence();
    _pending = null;
    _book = null;
    _wallets = [];
    _device = _account = _reference = '';
    _stage = 'settlement';
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
      'Configure the accounting book before reviewing collectors.',
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
      if (!_wallets.any((row) => row['id'] == _account)) {
        _account = '';
      }
    } on Object catch (error) {
      if (_current(generation)) _failure(error);
    } finally {
      if (_current(generation)) setState(() => _busy = false);
    }
  }

  Map<String, dynamic> _validateSource(
    Map<String, dynamic> value,
    String source,
  ) => validateCollectorAccounting(
    value,
    bookId: _book!.bookId!,
    accountId: _account,
    sourceId: source,
    sourceKind: _stage,
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
          (preparationId == null || row['id'] == preparationId),
    );
    final projected = _validateSource({
      ...accountingObject(row['snapshot']),
      'source_digest': row['source_digest'],
    }, requireTreasuryId(row['source_id']));
    for (final key in ['book_id', 'source_kind', 'source_id']) {
      accountingCheck(row[key] == projected[key]);
    }
    if (expected != null) {
      accountingCheck(_coordinates(projected) == _coordinates(expected));
    }
    if (value['posting'] != null) {
      final posted = accountingObject(value['posting']);
      accountingCheck(
        posted['preparation_id'] == row['id'] &&
            treasuryUuid(posted['journal_entry_id']) &&
            posted['exact_posted'] is bool &&
            posted['correction_pending'] is bool &&
            posted['posting_date'] == projected['posting_date'] &&
            posted['amount'] == projected['amount'],
      );
      for (final key in ['book_id', 'source_kind', 'source_id']) {
        accountingCheck(posted[key] == row[key]);
      }
    }
  }

  Future<void> _lookup({bool recover = false}) async {
    accountingCheck(
      _wallets.any((row) => row['id'] == _account) && treasuryUuid(_reference),
      'Choose an authorized Treasury account, accounting step and existing source or preparation reference.',
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
          '$sourceAccountingBase/collector/preparations/$_reference',
        );
        if (!_current(generation)) return;
        _validatePreparation(result, preparationId: _reference);
        _prepared = result;
        final row = accountingObject(result['preparation']);
        _source = _validateSource({
          ...accountingObject(row['snapshot']),
          'source_digest': row['source_digest'],
        }, row['source_id'] as String);
      } else {
        final result = await _read(
          '$sourceAccountingBase/collector/$_stage/$_reference/review',
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

  String _coordinates(Map<String, dynamic> source) => jsonEncode({
    ...source,
    'lines': [
      for (final row in accountingRows(source['lines']))
        {
          for (final key in ['line_number', 'account_code', 'debit', 'credit'])
            key: row[key],
        },
    ],
  });
  List<(String, String)> _facts() => [
    ('Accounting step', collectorAccountingStages[_stage]!.$1),
    ('Source reference', '${_source!['source_id']}'),
    (
      'Treasury account',
      '${_wallets.firstWhere((row) => row['id'] == _account)['alias']}',
    ),
    ('Actual posting date', '${_source!['posting_date']}'),
    ('Source amount', 'PHP ${_source!['amount']}'),
    ('Actual transaction fee', 'PHP ${_source!['fee']}'),
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
        ? 'Post Collector accounting'
        : 'Prepare Collector accounting';
    final consequence = posting
        ? 'Posts this exact reviewed source to the General Ledger. It does not approve, initiate or transfer operational money.'
        : 'Retains these exact actual-stage coordinates. Posting requires a separate confirmation.';
    setState(() {
      _review = _CollectorIntent(
        path: posting
            ? '$sourceAccountingBase/collector/preparations/${row!['id']}/post'
            : '$sourceAccountingBase/collector/${expected['source_kind']}/${expected['source_id']}/prepare',
        body: posting
            ? {
                'source_digest': expected['source_digest'],
                'confirmation_token': row!['confirmation_token'],
                'confirm': true,
              }
            : {
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
          binding: ManagementMutationBinding.collectorAccounting,
          recordLabel: 'Actual Collector accounting step',
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
              message: '${collectorAccountingStages[_stage]!.$2} $consequence',
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
        final row = accountingObject(result['preparation']);
        _source = _validateSource({
          ...accountingObject(row['snapshot']),
          'source_digest': row['source_digest'],
        }, row['source_id'] as String);
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
      title: const Text('Collector accounting'),
      actions: [
        IconButton(
          tooltip: 'Refresh collector accounting',
          onPressed: _busy || _pending != null || _denied
              ? null
              : () => _act(_load),
          icon: const Icon(Icons.refresh),
        ),
      ],
    ),
    body: ListView(
      key: ValueKey(
        'collector-$_generation-${_review != null}-${_pending != null}',
      ),
      padding: const EdgeInsets.all(16),
      children: [
        if (_busy) const LinearProgressIndicator(),
        if (_error != null) Text(_error!, key: const Key('collector-error')),
        if (_book != null)
          Text('Book: ${_book!.entityLabel} · ${_book!.kindLabel}'),
        if (_pending != null) ...[
          const Text(
            'The result is not confirmed. Retry the unchanged request to recover it.',
          ),
          ManagementReviewPanel(review: _pending!.presentation, compact: true),
          _button('collector-retry', 'Retry unchanged request', _send),
          if (_rejected)
            _button('collector-reload', 'Reload current evidence', () async {
              setState(() => _pending = null);
              await _load();
            }),
        ] else if (_review != null) ...[
          ManagementReviewPanel(review: _review!.presentation),
          _button(
            'collector-confirm',
            'Confirm: ${_review!.presentation.nextActionLabel}',
            _send,
          ),
          _button('collector-cancel', 'Cancel', () async {
            setState(() => _review = null);
          }),
        ] else if (_book != null && !_denied) ...[
          const Text(
            'Review accepted cash counts, recognized credits and actual return steps. A reservation does not create another liability. Balanced lines alone do not establish accounting readiness.',
          ),
          _wallet(
            'collector-account',
            'Treasury account for this step',
            _account,
            (value) => _account = value,
          ),
          DropdownButtonFormField<String>(
            key: const Key('collector-stage'),
            initialValue: _stage,
            isExpanded: true,
            decoration: const InputDecoration(labelText: 'Accounting step'),
            items: [
              for (final entry in collectorAccountingStages.entries)
                DropdownMenuItem(value: entry.key, child: Text(entry.value.$1)),
            ],
            onChanged: _busy
                ? null
                : (value) => setState(() {
                    _stage = value ?? 'settlement';
                    _clearEvidence();
                  }),
          ),
          TextFormField(
            key: const Key('collector-reference'),
            initialValue: _reference,
            enabled: !_busy,
            maxLength: 36,
            decoration: const InputDecoration(
              labelText: 'Existing source or saved preparation reference',
            ),
            onChanged: (value) => setState(() {
              _reference = value.trim();
              _clearEvidence();
            }),
          ),
          _button(
            'collector-load',
            'Load Collector accounting review',
            _lookup,
          ),
          _button(
            'collector-recover',
            'Open saved preparation',
            () => _lookup(recover: true),
          ),
          const Text(
            'Opening balances, historical corrections, credit applications and disputed custody need separate reviewed evidence. Return reviews require both origin and paying account permissions.',
          ),
          if (_source != null) ...[
            Text(collectorAccountingStages[_stage]!.$2),
            const Text(
              'These are exact journal movements, not current liability balances.',
            ),
            for (final fact in _facts())
              Padding(
                padding: const EdgeInsets.symmetric(vertical: 3),
                child: Text('${fact.$1}: ${fact.$2}'),
              ),
            if (_prepared == null)
              _button(
                'collector-prepare',
                'Prepare Collector accounting',
                () => _reviewAction(posting: false),
              )
            else ...[
              Text(
                _prepared!['posting'] != null &&
                        accountingObject(
                              _prepared!['posting'],
                            )['exact_posted'] ==
                            true
                    ? 'Collector accounting posted'
                    : 'Collector accounting prepared for review',
              ),
              Text(
                'Preparation ${accountingObject(_prepared!['preparation'])['id']}',
              ),
              if (_prepared!['posting'] == null)
                _button(
                  'collector-post',
                  'Review Collector posting',
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
