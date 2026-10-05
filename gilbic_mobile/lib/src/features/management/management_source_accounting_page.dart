import 'dart:convert';
import 'dart:math';

import 'package:flutter/material.dart';
import 'package:gilbic_mobile/src/core/auth/app_role.dart';
import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/device/device_identity.dart';
import 'package:gilbic_mobile/src/core/management/accounting_readiness_repository.dart';
import 'package:gilbic_mobile/src/core/management/source_accounting_repository.dart';
import 'package:gilbic_mobile/src/core/management/reporting_evidence.dart';
import 'package:gilbic_mobile/src/core/network/spina_api.dart';
import 'package:gilbic_mobile/src/core/treasury/treasury_models.dart';
import 'package:gilbic_mobile/src/features/management/accounting_readiness_card.dart';
import 'package:gilbic_mobile/src/features/management/review/management_review.dart';
import 'package:gilbic_mobile/src/features/management/reporting_supplement_card.dart';

enum SourceAccountingMode { book, reporting, receipts, liabilities }

class ManagementSourceAccountingPage extends StatefulWidget {
  const ManagementSourceAccountingPage({
    required this.session,
    required this.deviceIdentityProvider,
    required this.mode,
    this.repository,
    this.uuidGenerator,
    super.key,
  });
  final UserSession session;
  final DeviceIdentityProvider deviceIdentityProvider;
  final SourceAccountingMode mode;
  final SourceAccountingRepository? repository;
  final String Function()? uuidGenerator;
  @override
  State<ManagementSourceAccountingPage> createState() =>
      _ManagementSourceAccountingPageState();
}

class _ReviewedAction {
  _ReviewedAction({
    required this.path,
    required Map<String, dynamic> body,
    required this.presentation,
    required this.validate,
    required this.complete,
  }) : body = accountingObject(immutableTreasury(body));
  final String path;
  final Map<String, dynamic> body;
  final ManagementReviewPresentation presentation;
  final void Function(Map<String, dynamic>) validate;
  final Future<void> Function(Map<String, dynamic>) complete;
}

class _ManagementSourceAccountingPageState
    extends State<ManagementSourceAccountingPage> {
  late SourceAccountingRepository _repository;
  late String _sessionScope;
  int _generation = 0, _offset = 0;
  bool _busy = true, _denied = false, _canConfigureBook = false;
  String? _error, _accountId, _editor;
  String _deviceId = '', _asOf = '';
  AccountingBookIdentity? _book;
  List<Map<String, dynamic>> _wallets = [];
  Map<String, dynamic>? _mapping, _receipts, _schedule, _prepared, _line;
  _ReviewedAction? _review, _pending;
  final Map<String, String> _fields = {};
  List<Map<String, dynamic>> _reportPeriods = [];
  String? _reportPeriodId;
  Map<String, dynamic>? _report, _reportPolicy, _cashLine;
  int _noteCount = 1, _allocationCount = 1;
  bool get _receiptMode => widget.mode == SourceAccountingMode.receipts;
  bool get _bookMode => widget.mode == SourceAccountingMode.book;
  bool get _reportMode => widget.mode == SourceAccountingMode.reporting;
  bool get _canView =>
      widget.session.hasRole(AppRole.management) &&
      widget.session.hasPermission('accounting.view');
  bool get _canManage =>
      _canView && widget.session.hasPermission('accounting.journal.manage');
  Map<String, dynamic> get _account =>
      _wallets.firstWhere((row) => row['id'] == _accountId);
  String _scope(UserSession session) => jsonEncode([
    session.userId,
    session.accessToken,
    session.roles,
    session.rawRole,
    session.permissions,
  ]);
  bool _current(int generation) =>
      mounted &&
      generation == _generation &&
      _sessionScope == _scope(widget.session);
  String _uuid() => (widget.uuidGenerator ?? _newUuid)();

  @override
  void initState() {
    super.initState();
    _repository = widget.repository ?? SpinaSourceAccountingRepository();
    _sessionScope = _scope(widget.session);
    _load();
  }

  @override
  void didUpdateWidget(covariant ManagementSourceAccountingPage oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (_scope(widget.session) != _sessionScope ||
        oldWidget.deviceIdentityProvider != widget.deviceIdentityProvider ||
        oldWidget.repository != widget.repository ||
        oldWidget.mode != widget.mode) {
      _sessionScope = _scope(widget.session);
      _generation++;
      _clearPrivate();
      _denied = false;
      _repository = widget.repository ?? SpinaSourceAccountingRepository();
      _load();
    }
  }

  @override
  void dispose() {
    _generation++;
    _clearPrivate();
    super.dispose();
  }

  void _clearPrivate() {
    _book = null;
    _wallets = [];
    _accountId = null;
    _mapping = _receipts = _schedule = _prepared = _line = null;
    _pending = _review = null;
    _editor = null;
    _fields.clear();
    _offset = 0;
    _deviceId = '';
    _canConfigureBook = false;
    _reportPeriods = [];
    _reportPeriodId = null;
    _report = _reportPolicy = _cashLine = null;
  }

  Future<Map<String, dynamic>> _read(String path) =>
      _repository.read(widget.session, deviceId: _deviceId, path: path);
  void _failure(Object error) {
    if (!mounted) return;
    setState(() {
      _busy = false;
      _error = error is SpinaApiException
          ? error.message
          : error is FormatException
          ? error.message
          : 'Accounting records could not be confirmed. Retry the unchanged request if it was submitted.';
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
    if (_scope(widget.session) != _sessionScope) {
      _failure(
        const SpinaApiException(
          'Access changed. Reopen this accounting task.',
          code: 'accounting_scope_changed',
        ),
      );
      return;
    }
    try {
      await action();
    } on Object catch (error) {
      _failure(error);
    }
  }

  Future<void> _load() async {
    if (_pending != null) return;
    final generation = ++_generation;
    setState(() {
      _busy = true;
      _error = null;
      _mapping = _receipts = _schedule = _prepared = null;
      _report = _reportPolicy = _cashLine = null;
      _review = null;
      _editor = null;
      _fields.clear();
    });
    try {
      accountingCheck(
        _canView && (!_receiptMode || _canManage),
        'Current Management accounting permission is required.',
      );
      final identity = await widget.deviceIdentityProvider.load();
      if (!_current(generation)) return;
      _deviceId = identity.installationId;
      final payload = await _read('$sourceAccountingBase/book');
      if (!_current(generation)) return;
      final book = AccountingBookIdentity.fromPayload(
        accountingObject(payload['book']),
      );
      accountingCheck(
        _bookMode || book.bookId != null,
        'Configure the immutable accounting book before using this workflow.',
      );
      if (_book?.bookId != null && _book!.bookId != book.bookId) {
        throw const SpinaApiException(
          'Accounting book changed. Reopen this task.',
          code: 'accounting_scope_changed',
        );
      }
      _book = book;
      _canConfigureBook = payload['can_configure'] == true;
      if (_bookMode) return;
      if (_reportMode) {
        final overview = await _read(sourceAccountingBase);
        if (!_current(generation)) return;
        _reportPeriods = accountingRows(overview['fiscal_periods']);
        accountingCheck(
          _reportPeriods.every(
            (row) => treasuryUuid(row['period_id']) && row['label'] is String,
          ),
        );
        if (!_reportPeriods.any((row) => row['period_id'] == _reportPeriodId)) {
          _reportPeriodId = _reportPeriods.firstOrNull?['period_id'] as String?;
        }
        if (_reportPeriodId != null) await _loadReport();
        return;
      }
      if (_receiptMode) {
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
                  ['physical_cash', 'gcash', 'bank'].contains(row['kind']) &&
                  row['active'] != false,
            )
            .toList();
        accountingCheck(
          _wallets.every(
            (row) =>
                treasuryUuid(row['id']) &&
                row['alias'] is String &&
                ['physical_cash', 'gcash', 'bank'].contains(row['kind']),
          ),
        );
        if (!_wallets.any((row) => row['id'] == _accountId)) _accountId = null;
        if (_accountId != null) await _loadAccount();
      } else {
        final schedule = await _read(
          '$sourceAccountingBase/liabilities${_asOf.isEmpty ? '' : '?as_of=$_asOf'}',
        );
        if (!_current(generation)) return;
        _schedule = validateLiabilitySchedule(schedule, book.bookId!);
      }
    } on Object catch (error) {
      if (_current(generation)) _failure(error);
    } finally {
      if (_current(generation)) setState(() => _busy = false);
    }
  }

  Future<void> _loadAccount() async {
    final generation = ++_generation, accountId = _accountId;
    setState(() {
      _busy = true;
      _error = null;
      _mapping = _receipts = _prepared = null;
      _review = null;
      _editor = null;
      _fields.clear();
    });
    if (accountId == null) {
      setState(() => _busy = false);
      return;
    }
    try {
      final result = await _read(
        '$sourceAccountingBase/treasury/accounts/$accountId/cash-mapping',
      );
      if (!_current(generation)) return;
      accountingCheck(
        result['book_id'] == _book!.bookId &&
            result['treasury_account_id'] == accountId,
      );
      if (result['mapping'] != null) {
        final mapping = accountingObject(result['mapping']);
        accountingCheck(
          treasuryUuid(mapping['id']) &&
              mapping['book_id'] == _book!.bookId &&
              mapping['treasury_account_id'] == accountId &&
              mapping['version'] is int &&
              (mapping['version'] as int) > 0,
        );
        _mapping = mapping;
      }
      final page = await _read(
        '$sourceTreasuryBase/accounts/$accountId/receipts?limit=50&offset=$_offset',
      );
      if (!_current(generation)) return;
      final rows = accountingRows(page['items']);
      accountingCheck(
        page['limit'] == 50 &&
            page['offset'] == _offset &&
            page['total_count'] is int &&
            (page['total_count'] as int) >= rows.length &&
            page['has_more'] is bool,
      );
      for (final row in rows) {
        accountingCheck(
          treasuryUuid(row['id']) && row['account_id'] == accountId,
        );
        TreasuryMoney(row['amount']);
      }
      setState(() => _receipts = page);
    } on Object catch (error) {
      if (_current(generation)) {
        _mapping = _receipts = null;
        _failure(error);
      }
    } finally {
      if (_current(generation)) setState(() => _busy = false);
    }
  }

  Future<void> _loadReport() async {
    final generation = ++_generation;
    setState(() {
      _report = _reportPolicy = _cashLine = null;
      _review = null;
      _editor = null;
      _fields.clear();
      _error = null;
      _busy = true;
    });
    try {
      final policy = await _read(
        '$sourceAccountingBase/statements/reporting-policy?period_id=$_reportPeriodId',
      );
      if (!_current(generation)) return;
      if (policy['policy'] != null) {
        final row = accountingObject(policy['policy']);
        accountingCheck(
          treasuryUuid(row['id']) &&
              row['book_id'] == _book!.bookId &&
              row['fiscal_period_id'] == _reportPeriodId &&
              row['version'] is int &&
              (row['version'] as int) > 0,
        );
      }
      final payload = await _read(
        '$sourceAccountingBase/statements?period_id=$_reportPeriodId',
      );
      if (!_current(generation)) return;
      final statements = accountingObject(payload['statements']);
      accountingCheck(
        accountingObject(statements['period'])['period_id'] == _reportPeriodId,
      );
      final report = validateReportingSupplement(
        accountingObject(statements['reporting_supplement']),
      );
      final cashPolicy = accountingObject(report['cash_flows'])['policy'];
      accountingCheck(
        (cashPolicy == null ? null : accountingObject(cashPolicy)['id']) ==
            (policy['policy'] == null
                ? null
                : accountingObject(policy['policy'])['id']),
      );
      setState(() {
        _report = report;
        _reportPolicy = policy['policy'] == null
            ? null
            : accountingObject(policy['policy']);
      });
    } on Object catch (error) {
      if (_current(generation)) _failure(error);
    } finally {
      if (_current(generation)) setState(() => _busy = false);
    }
  }

  void _editReportingPolicy() {
    _edit('reporting-policy');
    setState(() {
      for (final key in [
        'framework_label',
        'evidence_reference',
        'evidence_digest',
      ]) {
        _fields[key] = '${_reportPolicy?[key] ?? ''}';
      }
      for (final code in ['1010', '1020', '1030']) {
        _fields['cash_$code'] =
            (_reportPolicy?['cash_account_codes'] as List?)?.contains(code) ==
                true
            ? 'yes'
            : 'no';
      }
      final notes = _reportPolicy == null
          ? <Map<String, dynamic>>[{}]
          : accountingRows(_reportPolicy!['notes']);
      _noteCount = notes.length;
      for (var index = 0; index < notes.length; index++) {
        for (final key in [
          'title',
          'text',
          'evidence_reference',
          'evidence_digest',
        ]) {
          _fields['note_${index}_$key'] = '${notes[index][key] ?? ''}';
        }
      }
    });
  }

  Future<void> _saveReportingPolicy() async {
    final notes = <Map<String, dynamic>>[];
    for (var index = 0; index < _noteCount; index++) {
      final note = {
        for (final key in [
          'title',
          'text',
          'evidence_reference',
          'evidence_digest',
        ])
          key: (_fields['note_${index}_$key'] ?? '').trim(),
      };
      accountingCheck(
        note['title']!.isNotEmpty &&
            note['title']!.length <= 200 &&
            note['text']!.isNotEmpty &&
            note['text']!.length <= 20000 &&
            note['evidence_reference']!.isNotEmpty &&
            note['evidence_reference']!.length <= 1000 &&
            accountingDigest(note['evidence_digest']),
        'Complete every retained note and its evidence.',
      );
      notes.add(note);
    }
    final codes = [
          '1010',
          '1020',
          '1030',
        ].where((code) => _fields['cash_$code'] == 'yes').toList(),
        framework = (_fields['framework_label'] ?? '').trim();
    accountingCheck(
      codes.isNotEmpty &&
          framework.isNotEmpty &&
          framework.length <= 200 &&
          notes.isNotEmpty &&
          notes.length <= 50,
      'Choose cash accounts and enter the actual reporting framework or basis.',
    );
    final body = <String, dynamic>{
      'request_id': _uuid(),
      'book_id': _book!.bookId,
      'period_id': _reportPeriodId,
      'expected_version': _reportPolicy?['version'] ?? 0,
      'cash_account_codes': codes,
      'framework_label': framework,
      'notes': notes,
      ..._evidence(),
      'reviewed': true,
    };
    _reviewAction(
      'Retain reporting policy',
      [
        (
          'Period',
          '${_reportPeriods.firstWhere((row) => row['period_id'] == _reportPeriodId)['label']}',
        ),
        ('Reporting basis', framework),
        ('Cash accounts', codes.join(', ')),
        ('Evidence reference', body['evidence_reference'] as String),
        ('Evidence fingerprint', body['evidence_digest'] as String),
        for (final note in notes) ...[
          (note['title'] as String, note['text'] as String),
          ('Note evidence reference', note['evidence_reference'] as String),
          ('Note evidence fingerprint', note['evidence_digest'] as String),
        ],
      ],
      'Retains a new policy version and reviewed notes. Existing cash lines require classifications for this policy. No journal or cash movement is created.',
      path: '$sourceAccountingBase/statements/reporting-policy',
      body: body,
      validate: (result) => accountingCheck(treasuryUuid(result['policy_id'])),
      complete: (_) => _loadReport(),
    );
  }

  void _editCashClassification(Map<String, dynamic> line) {
    accountingCheck(
      line['source_type'] != 'opening_balance' &&
          line['is_opening_adjustment'] == false &&
          _reportPolicy?['cash_definition_valid'] == true &&
          accountingObject(_report!['cash_flows'])['status'] !=
              'cash_definition_changed',
    );
    _edit('cash-classification');
    setState(() {
      _cashLine = line;
      final allocations =
          line['allocations'] == null || (line['allocations'] as List).isEmpty
          ? <Map<String, dynamic>>[
              {'category': '', 'amount': line['amount']},
            ]
          : accountingRows(line['allocations']);
      _allocationCount = allocations.length;
      for (var index = 0; index < allocations.length; index++) {
        _fields['allocation_${index}_category'] =
            '${allocations[index]['category']}';
        _fields['allocation_${index}_amount'] =
            '${allocations[index]['amount']}';
      }
    });
  }

  Future<void> _saveCashClassification() async {
    final line = _cashLine!,
        allocations = validateCashAllocations(
          List.generate(
            _allocationCount,
            (index) => <String, dynamic>{
              'category': _fields['allocation_${index}_category'],
              'amount': (_fields['allocation_${index}_amount'] ?? '').trim(),
            },
          ),
          _cashLine!['amount'] as String,
        );
    final body = <String, dynamic>{
      'request_id': _uuid(),
      'book_id': _book!.bookId,
      'policy_id': _reportPolicy!['id'],
      'journal_line_id': line['journal_line_id'],
      'expected_version': line['classification_version'],
      'expected_amount': line['amount'],
      'allocations': allocations,
      ..._evidence(),
      'reviewed': true,
    };
    _reviewAction(
      'Retain cash flow classification',
      [
        ('Journal', '${line['entry_number']}'),
        ('Cash account', '${line['account_code']}'),
        ('Signed cash amount', 'PHP ${line['amount']}'),
        for (final allocation in allocations)
          (
            allocation['category'] == 'internal'
                ? 'Internal transfer'
                : '${allocation['category']}',
            'PHP ${allocation['amount']}',
          ),
        ('Evidence reference', body['evidence_reference'] as String),
        ('Evidence fingerprint', body['evidence_digest'] as String),
      ],
      'Retains classification evidence for the exact posted cash line. It does not post or move cash. Unmatched internal transfers remain incomplete.',
      path: '$sourceAccountingBase/statements/cash-flow-classifications',
      body: body,
      validate: (result) =>
          accountingCheck(treasuryUuid(result['classification_id'])),
      complete: (_) => _loadReport(),
    );
  }

  Map<String, dynamic> _source(
    Map<String, dynamic> value,
    String receiptId,
    String mappingId,
  ) => validateReceiptReview(
    value,
    bookId: _book!.bookId!,
    accountId: _accountId!,
    receiptId: receiptId,
    mappingId: mappingId,
  );
  void _validatePreparation(
    Map<String, dynamic> result, {
    Map<String, dynamic>? expected,
    String? requestId,
    String? preparationId,
  }) {
    final row = accountingObject(result['preparation']);
    accountingCheck(
      treasuryUuid(row['id']) &&
          row['book_id'] == _book!.bookId &&
          row['treasury_account_id'] == _accountId &&
          row['actor_user_id'] == widget.session.userId &&
          accountingDigest(row['confirmation_token']) &&
          accountingDigest(row['source_digest']) &&
          (requestId == null || row['request_id'] == requestId) &&
          (preparationId == null || row['id'] == preparationId),
    );
    final snapshot = _source(
      {
        ...accountingObject(row['snapshot']),
        'source_digest': row['source_digest'],
      },
      requireTreasuryId(row['receipt_id']),
      requireTreasuryId(row['mapping_id']),
    );
    accountingCheck(snapshot['event_id'] == row['event_id']);
    if (expected != null) {
      for (final key in [
        'receipt_id',
        'event_id',
        'mapping_id',
        'source_digest',
        'amount',
      ]) {
        accountingCheck(snapshot[key] == expected[key]);
      }
    }
    if (result['posting'] != null) {
      final posted = accountingObject(result['posting']);
      accountingCheck(
        posted['preparation_id'] == row['id'] &&
            posted['book_id'] == row['book_id'] &&
            posted['receipt_id'] == row['receipt_id'] &&
            posted['treasury_account_id'] == _accountId &&
            posted['event_id'] == row['event_id'] &&
            posted['source_digest'] == row['source_digest'] &&
            treasuryUuid(posted['journal_entry_id']) &&
            posted['exact_posted'] is bool &&
            posted['correction_pending'] is bool,
      );
    }
  }

  List<(String, String)> _receiptFacts(Map<String, dynamic> source) {
    final cash = accountingObject(
      accountingObject(source['mapping'])['cash_snapshot'],
    );
    return [
      (
        'Receipt',
        '${accountingObject(source['receipt'])['reference'] ?? source['receipt_id']}',
      ),
      ('Posting date', source['posting_date'] as String),
      ('Verified amount', 'PHP ${source['amount']}'),
      ('Debit', '${cash['code']} · ${cash['name']}'),
      ('Credit', '2200 · Unapplied Borrower Funds'),
      (
        'Recipient evidence fingerprint',
        '${accountingObject(source['evidence'])['sha256']}',
      ),
    ];
  }

  void _reviewAction(
    String title,
    List<(String, String)> facts,
    String consequence, {
    required String path,
    required Map<String, dynamic> body,
    required void Function(Map<String, dynamic>) validate,
    required Future<void> Function(Map<String, dynamic>) complete,
  }) {
    accountingCheck(_canManage && _pending == null);
    setState(() {
      _error = null;
      _editor = null;
      _review = _ReviewedAction(
        path: path,
        body: body,
        presentation: ManagementReviewPresentation.validated(
          binding: _reportMode
              ? ManagementMutationBinding.reportingEvidence
              : _bookMode
              ? ManagementMutationBinding.accountingBook
              : _receiptMode
              ? ManagementMutationBinding.receiptAccounting
              : ManagementMutationBinding.liabilitySchedule,
          recordLabel: _reportMode
              ? 'Reporting evidence'
              : _bookMode
              ? 'Accounting book identity'
              : _receiptMode
              ? 'Receipt accounting'
              : 'Liability evidence',
          recordValue: title,
          statusLabel: 'Awaiting explicit confirmation',
          facts: facts
              .map((row) => ManagementReviewFact(label: row.$1, value: row.$2))
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
        validate: validate,
        complete: complete,
      );
    });
  }

  Future<void> _send() async {
    accountingCheck(_canManage);
    final action = _pending ?? _review;
    accountingCheck(action != null);
    final generation = _generation;
    setState(() {
      _pending = action;
      _review = null;
      _busy = true;
      _error = null;
    });
    try {
      final currentBook = await _read('$sourceAccountingBase/book');
      if (!_current(generation)) return;
      if (_book!.bookId != null &&
          accountingObject(currentBook['book'])['book_id'] != _book!.bookId) {
        throw const SpinaApiException(
          'Accounting book changed. Reopen this task.',
          code: 'accounting_scope_changed',
        );
      }
      final result = await _repository.write(
        widget.session,
        deviceId: _deviceId,
        path: action!.path,
        body: action.body,
      );
      if (!_current(generation)) return;
      action.validate(result);
      setState(() {
        _pending = null;
        _busy = false;
      });
      await action.complete(result);
    } on Object catch (error) {
      if (_current(generation)) _failure(error);
    } finally {
      if (_current(generation)) setState(() => _busy = false);
    }
  }

  Future<void> _reviewReceipt(Map<String, dynamic> receipt) async {
    final generation = _generation;
    setState(() {
      _busy = true;
      _prepared = null;
      _error = null;
    });
    try {
      final value = await _read(
        '$sourceAccountingBase/treasury/receipts/${receipt['id']}/review?mapping_id=${_mapping!['id']}',
      );
      if (!_current(generation)) return;
      final source = _source(
            value,
            receipt['id'] as String,
            _mapping!['id'] as String,
          ),
          requestId = _uuid();
      _reviewAction(
        'Prepare receipt accounting',
        _receiptFacts(source),
        'Saves this reviewed receipt for a separate posting confirmation. Preparation does not post a journal.',
        path:
            '$sourceAccountingBase/treasury/receipts/${receipt['id']}/prepare',
        body: {
          'mapping_id': source['mapping_id'],
          'source_digest': source['source_digest'],
          'request_id': requestId,
        },
        validate: (result) => _validatePreparation(
          result,
          expected: source,
          requestId: requestId,
        ),
        complete: (result) async {
          setState(() => _prepared = result);
        },
      );
    } finally {
      if (_current(generation)) setState(() => _busy = false);
    }
  }

  Future<void> _postReceipt() async {
    final row = accountingObject(_prepared!['preparation']),
        source = {
          ...accountingObject(
            accountingObject(_prepared!['preparation'])['snapshot'],
          ),
          'source_digest': rowDigest(_prepared!),
        };
    _reviewAction(
      'Post receipt cash journal',
      _receiptFacts(source),
      'Posts verified cash received and the matching unapplied borrower liability. It does not apply a loan payment or recognize interest.',
      path:
          '$sourceAccountingBase/treasury/receipt-preparations/${row['id']}/post',
      body: {
        'source_digest': row['source_digest'],
        'confirmation_token': row['confirmation_token'],
        'confirm': true,
      },
      validate: (result) {
        _validatePreparation(
          result,
          expected: source,
          preparationId: row['id'] as String,
        );
        final posted = accountingObject(result['posting']);
        accountingCheck(
          posted['exact_posted'] == true &&
              posted['journal_entry_id'] == result['journal_entry_id'],
        );
      },
      complete: (result) async {
        setState(() => _prepared = result);
      },
    );
  }

  Map<String, dynamic> _evidence() {
    final reference = (_fields['evidence_reference'] ?? '').trim(),
        digest = (_fields['evidence_digest'] ?? '').trim().toLowerCase();
    accountingCheck(
      reference.isNotEmpty &&
          reference.length <= 1000 &&
          accountingDigest(digest),
      'Supply the retained evidence reference and its 64-character SHA-256 fingerprint.',
    );
    return {'evidence_reference': reference, 'evidence_digest': digest};
  }

  Future<void> _saveBook() async {
    final body = <String, dynamic>{
      'kind': _fields['kind'],
      'entity_label': (_fields['entity_label'] ?? '').trim(),
      ..._evidence(),
      'confirm': true,
    };
    accountingCheck(
      _canConfigureBook &&
          ['owner_operations', 'corporate_legal'].contains(body['kind']) &&
          (body['entity_label'] as String).isNotEmpty &&
          (body['entity_label'] as String).length <= 200,
      'Choose owner operations or corporate legal and enter the exact entity name.',
    );
    _reviewAction(
      'Set permanent book identity',
      [
        ('Entity name', body['entity_label'] as String),
        (
          'Book kind',
          body['kind'] == 'owner_operations'
              ? 'Owner operations'
              : 'Corporate legal',
        ),
        ('Evidence reference', body['evidence_reference'] as String),
        ('Evidence fingerprint', body['evidence_digest'] as String),
      ],
      'This permanently binds this ledger to the named entity and book kind. It cannot be changed. Keep owner and corporate records in separate books.',
      path: '$sourceAccountingBase/book',
      body: body,
      validate: (result) {
        final row = accountingObject(result['book']);
        accountingCheck(
          row['status'] == 'configured' &&
              treasuryUuid(row['book_id']) &&
              [
                'kind',
                'entity_label',
                'evidence_reference',
                'evidence_digest',
              ].every((key) => row[key] == body[key]),
        );
      },
      complete: (result) async {
        setState(
          () => _book = AccountingBookIdentity.fromPayload(
            accountingObject(result['book']),
          ),
        );
      },
    );
  }

  Future<void> _saveMapping() async {
    final body = {
      'cash_code': _account['kind'] == 'physical_cash' ? '1010' : '1030',
      'expected_version': _mapping?['version'] ?? 0,
      'request_id': _uuid(),
      ..._evidence(),
      'confirm': true,
    };
    _reviewAction(
      'Save cash account mapping',
      [
        ('Treasury account', _account['alias'] as String),
        ('Cash account', body['cash_code'] as String),
        ('Evidence reference', body['evidence_reference'] as String),
        ('Evidence fingerprint', body['evidence_digest'] as String),
      ],
      'Retains a new mapping version for this book. It does not post money.',
      path: '$sourceAccountingBase/treasury/accounts/$_accountId/cash-mapping',
      body: body,
      validate: (result) {
        final row = accountingObject(result['mapping']);
        accountingCheck(
          treasuryUuid(row['id']) &&
              row['request_id'] == body['request_id'] &&
              row['book_id'] == _book!.bookId &&
              row['treasury_account_id'] == _accountId &&
              row['version'] == (body['expected_version'] as int) + 1 &&
              accountingObject(row['cash_snapshot'])['code'] ==
                  body['cash_code'] &&
              row['evidence_reference'] == body['evidence_reference'] &&
              row['evidence_digest'] == body['evidence_digest'],
        );
      },
      complete: (_) => _loadAccount(),
    );
  }

  Future<void> _openPreparation() async {
    final id = (_fields['preparation_id'] ?? '').trim();
    accountingCheck(treasuryUuid(id), 'Enter a valid preparation reference.');
    final generation = _generation;
    setState(() {
      _busy = true;
      _prepared = null;
    });
    try {
      final result = await _read(
        '$sourceAccountingBase/treasury/receipt-preparations/$id',
      );
      if (!_current(generation)) return;
      _validatePreparation(result, preparationId: id);
      setState(() {
        _prepared = result;
        _editor = null;
        _fields.clear();
      });
    } finally {
      if (_current(generation)) setState(() => _busy = false);
    }
  }

  List<Map<String, dynamic>> _obligationsForLine() => accountingRows(
    _schedule!['obligations'],
  ).where((row) => row['account_code'] == _line!['account_code']).toList();
  List<Map<String, dynamic>> _claimsForLine() {
    final movements = accountingRows(_schedule!['movements']),
        obligations = _obligationsForLine();
    return movements
        .where(
          (claim) =>
              obligations.any(
                (row) => row['obligation_id'] == claim['obligation_id'],
              ) &&
              !movements.any(
                (row) => row['reverses_claim_id'] == claim['claim_id'],
              ),
        )
        .toList();
  }

  Future<void> _saveLiability() async {
    final line = _line!,
        registration = _editor == 'registration',
        reversal = _line!['source_type'] == 'reversal';
    final amount = line['credit'] != '0.00' ? line['credit'] : line['debit'];
    final body = <String, dynamic>{
      'request_id': _uuid(),
      'expected_book_id': _book!.bookId,
      'journal_line_id': line['journal_line_id'],
      'expected_account_code': line['account_code'],
      'expected_amount': amount,
      'expected_posting_date': line['posting_date'],
      'expected_source_type': line['source_type'],
      'expected_source_reference': line['source_reference'],
      ..._evidence(),
      'reviewed': true,
    };
    Map<String, dynamic>? obligation;
    if (registration) {
      body['kind'] = liabilityKinds[line['account_code']]!.$1;
      body['counterparty'] = (_fields['counterparty'] ?? '').trim();
      body['due_date'] = (_fields['due_date'] ?? '').isEmpty
          ? null
          : _fields['due_date'];
      accountingCheck(
        (body['counterparty'] as String).isNotEmpty &&
            (body['counterparty'] as String).length <= 200 &&
            (body['due_date'] == null || accountingDate(body['due_date'])),
        'Enter the actual counterparty and a valid optional due date.',
      );
    } else {
      obligation = _obligationsForLine()
          .where((row) => row['obligation_id'] == _fields['obligation_id'])
          .firstOrNull;
      accountingCheck(
        obligation != null,
        'Choose an existing obligation for this account.',
      );
      body['kind'] = reversal ? 'reversal' : 'settlement';
      body['reverses_claim_id'] = reversal
          ? _fields['reverses_claim_id']
          : null;
      if (reversal) {
        accountingCheck(
          _claimsForLine().any(
            (row) =>
                row['claim_id'] == body['reverses_claim_id'] &&
                row['obligation_id'] == obligation!['obligation_id'],
          ),
          'Choose the exact original movement for this obligation.',
        );
      }
    }
    _reviewAction(
      registration
          ? 'Register liability evidence'
          : reversal
          ? 'Record liability correction'
          : 'Record liability settlement',
      [
        (
          'Counterparty',
          '${body['counterparty'] ?? obligation!['counterparty']}',
        ),
        (
          'Liability account',
          '${line['account_code']} · ${liabilityKinds[line['account_code']]!.$2}',
        ),
        ('Posted amount', 'PHP $amount'),
        ('Posting date', line['posting_date'] as String),
        (
          'Due date',
          '${body['due_date'] ?? obligation?['due_date'] ?? 'Not supplied'}',
        ),
        ('Evidence reference', body['evidence_reference'] as String),
        ('Evidence fingerprint', body['evidence_digest'] as String),
      ],
      'Links evidence to the exact posted liability line. It does not post a journal or transfer money. The server rechecks any linked correction.',
      path:
          '$sourceAccountingBase/liabilities${registration ? '' : '/${obligation!['obligation_id']}/movements'}',
      body: body,
      validate: (result) => accountingCheck(
        treasuryUuid(result[registration ? 'obligation_id' : 'claim_id']),
      ),
      complete: (_) => _load(),
    );
  }

  void _edit(String kind, [Map<String, dynamic>? line]) {
    setState(() {
      _editor = kind;
      _line = line;
      _review = null;
      _fields.clear();
      _error = null;
    });
  }

  Widget _button(String key, String text, Future<void> Function() action) =>
      OutlinedButton(
        key: Key(key),
        onPressed: _busy ? null : () => _act(action),
        child: Text(text),
      );
  Widget _fact(String label, Object? value) => Padding(
    padding: const EdgeInsets.symmetric(vertical: 3),
    child: Text('$label: ${value ?? 'Not supplied'}'),
  );
  Widget _card(List<Widget> children) => Card(
    child: Padding(
      padding: const EdgeInsets.all(14),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: children,
      ),
    ),
  );
  Widget _field(String name, String label) => Padding(
    padding: const EdgeInsets.symmetric(vertical: 6),
    child: TextFormField(
      key: Key('source-$name'),
      initialValue: _fields[name] ?? '',
      decoration: InputDecoration(
        labelText: label,
        border: const OutlineInputBorder(),
      ),
      enabled: !_busy,
      maxLines: name.endsWith('_text') ? 5 : 1,
      maxLength: name.endsWith('_text')
          ? 20000
          : name.endsWith('evidence_digest')
          ? 64
          : name == 'counterparty'
          ? 200
          : 1000,
      onChanged: (value) => _fields[name] = value,
    ),
  );
  Widget _choice(String name, String label, List<(String, String)> choices) =>
      Padding(
        padding: const EdgeInsets.symmetric(vertical: 6),
        child: DropdownButtonFormField<String>(
          key: Key('source-$name'),
          initialValue: choices.any((row) => row.$1 == _fields[name])
              ? _fields[name]
              : null,
          isExpanded: true,
          decoration: InputDecoration(
            labelText: label,
            border: const OutlineInputBorder(),
          ),
          items: choices
              .map(
                (row) => DropdownMenuItem(value: row.$1, child: Text(row.$2)),
              )
              .toList(),
          onChanged: _busy
              ? null
              : (value) => setState(() {
                  if (value == null) {
                    _fields.remove(name);
                  } else {
                    _fields[name] = value;
                  }
                }),
        ),
      );
  List<Widget> _evidenceInputs() => [
    _field('evidence_reference', 'Retained evidence reference'),
    _field('evidence_digest', 'Evidence fingerprint (SHA-256)'),
  ];
  List<Widget> _editorWidgets() {
    if (_editor == 'reporting-policy') {
      return [
        _field('framework_label', 'Reporting framework or basis'),
        for (final code in ['1010', '1020', '1030'])
          _choice('cash_$code', 'Include $code in cash', [
            ('yes', 'Include'),
            ('no', 'Exclude'),
          ]),
        ..._evidenceInputs(),
        for (var index = 0; index < _noteCount; index++) ...[
          Text('Note ${index + 1}'),
          _field('note_${index}_title', 'Note title'),
          _field('note_${index}_text', 'Note text'),
          _field('note_${index}_evidence_reference', 'Note evidence reference'),
          _field(
            'note_${index}_evidence_digest',
            'Note evidence fingerprint (SHA-256)',
          ),
        ],
        if (_noteCount < 50)
          _button('source-add-note', 'Add note', () async {
            setState(() => _noteCount++);
          }),
        if (_noteCount > 1)
          _button('source-remove-note', 'Remove last note', () async {
            setState(() => _noteCount--);
          }),
        _button(
          'source-review-editor',
          'Review reporting policy',
          _saveReportingPolicy,
        ),
      ];
    }
    if (_editor == 'cash-classification') {
      return [
        _fact('Journal', _cashLine!['entry_number']),
        _fact('Cash account', _cashLine!['account_code']),
        _fact('Signed cash amount', 'PHP ${_cashLine!['amount']}'),
        const Text(
          'Use signed exact amounts. Splits must equal this cash line. Internal transfers must offset within one journal or match both protected cash legs of one owned transfer in this period. Fees remain separate.',
        ),
        for (var index = 0; index < _allocationCount; index++) ...[
          Text('Allocation ${index + 1}'),
          _choice(
            'allocation_${index}_category',
            'Cash flow category',
            cashFlowCategories
                .map(
                  (category) => (
                    category,
                    category == 'internal'
                        ? 'Internal transfer'
                        : '${category[0].toUpperCase()}${category.substring(1)}',
                  ),
                )
                .toList(),
          ),
          _field(
            'allocation_${index}_amount',
            'Signed amount (two decimal places)',
          ),
        ],
        ..._evidenceInputs(),
        if (_allocationCount < 20)
          _button('source-add-allocation', 'Add allocation', () async {
            setState(() => _allocationCount++);
          }),
        if (_allocationCount > 1)
          _button(
            'source-remove-allocation',
            'Remove last allocation',
            () async {
              setState(() => _allocationCount--);
            },
          ),
        _button(
          'source-review-editor',
          'Review cash flow classification',
          _saveCashClassification,
        ),
      ];
    }
    if (_editor == 'book') {
      return [
        _choice('kind', 'Book kind', [
          ('owner_operations', 'Owner operations'),
          ('corporate_legal', 'Corporate legal'),
        ]),
        _field('entity_label', 'Exact entity name'),
        ..._evidenceInputs(),
        _button(
          'source-review-editor',
          'Review permanent book identity',
          _saveBook,
        ),
      ];
    }
    if (_editor == 'mapping') {
      return [
        _fact('Treasury account', _account['alias']),
        _fact(
          'Cash account',
          _account['kind'] == 'physical_cash'
              ? '1010 · Cash - Office'
              : '1030 · Cash - Bank / GCash',
        ),
        ..._evidenceInputs(),
        _button(
          'source-review-editor',
          'Review cash account mapping',
          _saveMapping,
        ),
      ];
    }
    if (_editor == 'preparation') {
      return [
        _field('preparation_id', 'Saved preparation reference'),
        _button(
          'source-open-preparation',
          'Open preparation',
          _openPreparation,
        ),
      ];
    }
    final line = _line!,
        registration = _editor == 'registration',
        reversal = _line!['source_type'] == 'reversal';
    return [
      _fact('Journal', line['entry_number'] ?? line['journal_entry_id']),
      _fact('Posting date', line['posting_date']),
      _fact('Account', line['account_code']),
      _fact(
        'Posted amount',
        'PHP ${line['credit'] != '0.00' ? line['credit'] : line['debit']}',
      ),
      if (registration) ...[
        _field('counterparty', 'Counterparty'),
        _field('due_date', 'Contractual due date (YYYY-MM-DD, optional)'),
      ] else
        _choice(
          'obligation_id',
          'Obligation',
          _obligationsForLine()
              .map(
                (row) => (
                  row['obligation_id'] as String,
                  '${row['counterparty']} · PHP ${row['outstanding_amount']}',
                ),
              )
              .toList(),
        ),
      if (reversal)
        _choice(
          'reverses_claim_id',
          'Original recorded movement',
          _claimsForLine()
              .map(
                (row) => (
                  row['claim_id'] as String,
                  '${row['posting_date']} · ${row['kind']} · PHP ${row['signed_amount']}',
                ),
              )
              .toList(),
        ),
      ..._evidenceInputs(),
      _button(
        'source-review-editor',
        'Review liability evidence',
        _saveLiability,
      ),
    ];
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(
      title: Text(
        _reportMode
            ? 'Reporting evidence'
            : _bookMode
            ? 'Accounting book'
            : _receiptMode
            ? 'Receipt accounting'
            : 'Liability schedule',
      ),
      actions: [
        IconButton(
          tooltip: 'Refresh accounting sources',
          onPressed: _busy || _pending != null || _denied
              ? null
              : () => _act(_load),
          icon: const Icon(Icons.refresh),
        ),
      ],
    ),
    body: ListView(
      key: ValueKey(
        'source-$_generation-${_editor ?? ''}-${_review != null}-${_pending != null}',
      ),
      padding: const EdgeInsets.all(16),
      children: [
        if (_busy) const LinearProgressIndicator(),
        if (_error != null)
          _card([Text(_error!, key: const Key('source-error'))]),
        if (_book != null)
          _card([
            Text(
              _book!.configured
                  ? 'Immutable book identity: ${_book!.entityLabel} · ${_book!.kindLabel}'
                  : 'Book identity is unconfigured.',
            ),
            const Text(postedLedgerScopeNotice),
          ]),
        if (_pending != null) ...[
          _card([
            Text(
              _busy
                  ? 'Sending the reviewed request…'
                  : 'The action outcome is uncertain. Retry this unchanged request to recover its result.',
            ),
            ManagementReviewPanel(
              review: _pending!.presentation,
              compact: true,
            ),
            _button('source-retry', 'Retry unchanged request', _send),
          ]),
        ] else if (_review != null) ...[
          ManagementReviewPanel(review: _review!.presentation),
          _button(
            'source-confirm',
            'Confirm: ${_review!.presentation.nextActionLabel}',
            _send,
          ),
          _button('source-cancel-review', 'Cancel', () async {
            setState(() => _review = null);
          }),
        ] else if (_editor != null) ...[
          _card(_editorWidgets()),
          _button('source-cancel-editor', 'Cancel', () async {
            setState(() {
              _editor = null;
              _fields.clear();
            });
          }),
        ] else if (_book != null && !_denied)
          ...(_reportMode
              ? _reportWidgets()
              : _bookMode
              ? _bookWidgets()
              : _receiptMode
              ? _receiptWidgets()
              : _liabilityWidgets()),
      ],
    ),
  );

  List<Widget> _reportWidgets() => [
    if (_reportPeriods.isEmpty)
      const Text('No accounting periods are available.')
    else
      DropdownButtonFormField<String>(
        key: ValueKey('source-report-period-$_reportPeriodId'),
        initialValue: _reportPeriodId,
        isExpanded: true,
        decoration: const InputDecoration(labelText: 'Accounting period'),
        items: _reportPeriods
            .map(
              (row) => DropdownMenuItem(
                value: row['period_id'] as String,
                child: Text(row['label'] as String),
              ),
            )
            .toList(),
        onChanged: _busy
            ? null
            : (value) => _act(() async {
                _reportPeriodId = value;
                await _loadReport();
              }),
      ),
    if (_report != null) ...[
      if (_canManage)
        _button(
          'source-report-policy',
          _reportPolicy == null
              ? 'Define reporting basis and cash accounts'
              : 'Review a new reporting policy version',
          () async => _editReportingPolicy(),
        ),
      const Text('Posted cash lines'),
      for (final row in accountingRows(
        accountingObject(_report!['cash_flows'])['cash_lines'],
      ))
        _card([
          Text('${row['entry_number']} · ${row['account_code']}'),
          _fact('Signed cash amount', 'PHP ${row['amount']}'),
          Text(
            row['classification_version'] == 0
                ? 'Classification required'
                : 'Classification version ${row['classification_version']}',
          ),
          if (row['is_opening_adjustment'] == true)
            const Text(
              'Opening balance adjustment — separate from cash flow classification.',
            )
          else if (_canManage &&
              _reportPolicy?['cash_definition_valid'] == true &&
              accountingObject(_report!['cash_flows'])['status'] !=
                  'cash_definition_changed')
            _button(
              'source-classify-${row['journal_line_id']}',
              'Review cash flow classification',
              () async => _editCashClassification(row),
            ),
        ]),
      ReportingSupplementCard(supplement: _report),
    ] else if (_reportPeriodId != null && !_busy)
      _button('source-report-retry', 'Retry reporting read', _loadReport),
  ];

  List<Widget> _bookWidgets() => [
    if (_book!.configured) ...[
      _fact('Book reference', _book!.bookId),
      const Text(
        'This identity is permanent. Keep owner and corporate accounting in separate books.',
      ),
    ] else ...[
      const Text(
        'Choose the actual entity for this ledger. Owner operations and corporate legal records require separate books.',
      ),
      if (_canManage && _canConfigureBook)
        _button(
          'source-configure-book',
          'Configure accounting book',
          () async => _edit('book'),
        )
      else
        const Text(
          'Current journal management permission is required to configure the book.',
        ),
    ],
  ];

  List<Widget> _receiptWidgets() {
    if (_prepared != null) {
      final row = accountingObject(_prepared!['preparation']),
          snapshot = accountingObject(row['snapshot']),
          posted = _prepared!['posting'] == null
              ? null
              : accountingObject(_prepared!['posting']);
      return [
        _card([
          Text(
            posted?['exact_posted'] == true
                ? 'Receipt cash recognized'
                : 'Receipt prepared for review',
          ),
          _fact('Preparation reference', row['id']),
          ..._receiptFacts(snapshot).map((fact) => _fact(fact.$1, fact.$2)),
          if (posted != null) ...[
            _fact('Journal reference', posted['journal_entry_id']),
            Text(
              posted['exact_posted'] == true
                  ? 'The exact receipt cash journal is posted.'
                  : 'Posting evidence needs investigation.',
            ),
            if (posted['correction_pending'] == true)
              const Text(
                'A later correction needs separate accounting review.',
              ),
          ] else
            _button(
              'source-review-post',
              'Review receipt posting',
              _postReceipt,
            ),
          _button('source-back-receipts', 'Back to receipts', () async {
            setState(() => _prepared = null);
          }),
        ]),
      ];
    }
    return [
      const Text(
        'Recognize verified borrower cash as cash received and unapplied borrower funds. Loan payments, interest and fees remain separate.',
      ),
      DropdownButtonFormField<String>(
        key: ValueKey('source-wallet-$_accountId'),
        initialValue: _accountId,
        isExpanded: true,
        decoration: const InputDecoration(labelText: 'Treasury account'),
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
            : (value) => _act(() async {
                _accountId = value;
                _offset = 0;
                await _loadAccount();
              }),
      ),
      if (_accountId == null)
        const Text('Choose an authorized private Treasury account.')
      else if (_receipts == null) ...[
        const Text('Selected account records are unavailable.'),
        _button('source-retry-account', 'Retry account read', _loadAccount),
      ] else ...[
        _card([
          const Text('Cash account mapping'),
          Text(
            _mapping == null
                ? 'No cash account mapping is configured.'
                : '${accountingObject(_mapping!['cash_snapshot'])['code']} · ${accountingObject(_mapping!['cash_snapshot'])['name']} · Version ${_mapping!['version']}',
          ),
          if (widget.session.hasPermission('treasury.account.manage'))
            _button(
              'source-edit-mapping',
              'Review cash account mapping',
              () async => _edit('mapping'),
            ),
        ]),
        if (_receipts != null) ...[
          Text(
            'Showing ${accountingRows(_receipts!['items']).isEmpty ? 0 : _offset + 1}–${_offset + accountingRows(_receipts!['items']).length} of ${_receipts!['total_count']} receipts.',
          ),
          for (final row in accountingRows(_receipts!['items']))
            _card([
              Text('${row['reference'] ?? row['id']}'),
              _fact('Verified amount', 'PHP ${row['amount']}'),
              _fact('Effective date', row['effective_at']),
              if (_mapping != null)
                _button(
                  'source-review-${row['id']}',
                  'Review receipt accounting',
                  () => _reviewReceipt(row),
                )
              else
                const Text(
                  'Configure this account mapping before reviewing receipt accounting.',
                ),
            ]),
          if (_offset > 0)
            _button('source-previous', 'Previous receipts', () async {
              _offset -= 50;
              await _loadAccount();
            }),
          if (_receipts!['has_more'] == true)
            _button('source-next', 'Next receipts', () async {
              _offset += 50;
              await _loadAccount();
            }),
        ],
        _button(
          'source-recover-preparation',
          'Open a saved receipt preparation',
          () async => _edit('preparation'),
        ),
      ],
    ];
  }

  List<Widget> _liabilityWidgets() {
    final schedule = _schedule;
    if (schedule == null) return [];
    return [
      const Text(
        'This schedule links evidence to posted liability lines. It does not create cash or journal entries. Unpaid obligations can remain valid. Treasury, Collector and tax have separate schedules.',
      ),
      _field('as_of', 'As of date (YYYY-MM-DD)'),
      _button('source-as-of', 'Load date', () async {
        final value = (_fields['as_of'] ?? '').trim();
        accountingCheck(accountingDate(value), 'Choose a valid date.');
        _asOf = value;
        await _load();
      }),
      Text(
        'As of ${schedule['as_of']} · ${schedule['registered_controls_reconciled'] == true ? 'Registered liability controls reconciled' : 'Liability reconciliation needs review'}. This does not certify complete accounting readiness.',
      ),
      const Text('Control reconciliation'),
      for (final row in accountingRows(schedule['reconciliation']))
        _card([
          Text(
            '${row['account_code']} · ${liabilityKinds[row['account_code']]!.$2}',
          ),
          _fact('Posted ledger', 'PHP ${row['ledger_balance']}'),
          _fact('Liability schedule', 'PHP ${row['schedule_balance']}'),
          _fact('Difference', 'PHP ${row['difference']}'),
          _fact('Unregistered posted lines', row['unregistered_line_count']),
        ]),
      const Text('Obligations'),
      if (accountingRows(schedule['obligations']).isEmpty)
        const Text('No obligations registered as of this date.'),
      for (final row in accountingRows(schedule['obligations']))
        _card([
          Text(
            '${row['counterparty']} · ${liabilityKinds[row['account_code']]!.$2}',
          ),
          _fact('Outstanding', 'PHP ${row['outstanding_amount']}'),
          _fact('Due date', row['due_date']),
          _fact('Evidence reference', row['evidence_reference']),
          ExpansionTile(
            title: const Text('Recorded movements'),
            children: [
              for (final movement
                  in accountingRows(schedule['movements']).where(
                    (movement) =>
                        movement['obligation_id'] == row['obligation_id'],
                  ))
                ListTile(
                  title: Text(
                    '${movement['posting_date']} · ${movement['kind']} · PHP ${movement['signed_amount']}',
                  ),
                  subtitle: Text('${movement['claim_id']}'),
                ),
            ],
          ),
        ]),
      const Text('Unregistered posted liability lines'),
      if (accountingRows(schedule['unregistered_lines']).isEmpty)
        const Text('No unregistered posted lines as of this date.'),
      for (final row in accountingRows(schedule['unregistered_lines']))
        _card([
          Text(
            '${row['entry_number'] ?? row['journal_entry_id']} · ${row['account_code']}',
          ),
          _fact('Posting date', row['posting_date']),
          _fact('Debit', 'PHP ${row['debit']}'),
          _fact('Credit', 'PHP ${row['credit']}'),
          if (_canManage &&
              ['manual', 'opening_balance'].contains(row['source_type']) &&
              row['credit'] != '0.00' &&
              row['debit'] == '0.00')
            _button(
              'source-register-${row['journal_line_id']}',
              'Register obligation',
              () async => _edit('registration', row),
            ),
          if (_canManage &&
              ((row['source_type'] == 'manual' &&
                      row['debit'] != '0.00' &&
                      row['credit'] == '0.00') ||
                  row['source_type'] == 'reversal'))
            _button(
              'source-movement-${row['journal_line_id']}',
              row['source_type'] == 'reversal'
                  ? 'Record linked correction'
                  : 'Record settlement',
              () async => _edit('movement', row),
            ),
        ]),
    ];
  }
}

Object? rowDigest(Map<String, dynamic> prepared) =>
    accountingObject(prepared['preparation'])['source_digest'];
String _newUuid() {
  final random = Random.secure();
  final bytes = List<int>.generate(16, (_) => random.nextInt(256));
  bytes[6] = (bytes[6] & 0x0f) | 0x40;
  bytes[8] = (bytes[8] & 0x3f) | 0x80;
  final hex = bytes
      .map((value) => value.toRadixString(16).padLeft(2, '0'))
      .join();
  return '${hex.substring(0, 8)}-${hex.substring(8, 12)}-${hex.substring(12, 16)}-${hex.substring(16, 20)}-${hex.substring(20)}';
}
