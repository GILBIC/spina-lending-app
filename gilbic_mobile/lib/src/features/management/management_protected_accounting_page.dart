import 'dart:convert';
import 'dart:math';
import 'package:flutter/material.dart';
import 'package:gilbic_mobile/src/core/auth/app_role.dart';
import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/device/device_identity.dart';
import 'package:gilbic_mobile/src/core/management/accounting_readiness_repository.dart';
import 'package:gilbic_mobile/src/core/management/protected_accounting_evidence.dart';
import 'package:gilbic_mobile/src/core/management/source_accounting_repository.dart';
import 'package:gilbic_mobile/src/core/network/spina_api.dart';
import 'package:gilbic_mobile/src/core/treasury/treasury_models.dart';
import 'package:gilbic_mobile/src/features/management/review/management_review.dart';

enum ProtectedAccountingMode { applications, assessments }

class ManagementProtectedAccountingPage extends StatefulWidget {
  const ManagementProtectedAccountingPage({
    required this.session,
    required this.deviceIdentityProvider,
    required this.mode,
    this.repository,
    this.uuidGenerator,
    super.key,
  });
  final UserSession session;
  final DeviceIdentityProvider deviceIdentityProvider;
  final ProtectedAccountingMode mode;
  final SourceAccountingRepository? repository;
  final String Function()? uuidGenerator;
  @override
  State<ManagementProtectedAccountingPage> createState() =>
      _ProtectedAccountingPageState();
}

class _Intent {
  _Intent({
    required this.path,
    required this.permission,
    required Map<String, dynamic> body,
    required this.review,
    required this.validate,
    required this.complete,
  }) : body = accountingObject(immutableTreasury(body));
  final String path, permission;
  final Map<String, dynamic> body;
  final ManagementReviewPresentation review;
  final void Function(Map<String, dynamic>) validate, complete;
}

class _ProtectedAccountingPageState
    extends State<ManagementProtectedAccountingPage> {
  late SourceAccountingRepository _repository;
  late String _sessionScope;
  String _device = '', _scopeId = '', _reference = '', _rationale = '';
  String _payoffContract = '';
  bool _noRebate = false;
  String? _error;
  int _generation = 0;
  bool _busy = true, _denied = false;
  AccountingBookIdentity? _book;
  List<Map<String, dynamic>> _choices = [];
  Map<String, dynamic>? _source, _prepared, _candidate, _payoff, _closedTerm;
  _Intent? _review, _pending;
  bool get _application => widget.mode == ProtectedAccountingMode.applications;
  bool _can(String permission) =>
      widget.session.hasRole(AppRole.management) &&
      widget.session.hasPermission(permission);
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
  @override
  void initState() {
    super.initState();
    _repository = widget.repository ?? SpinaSourceAccountingRepository();
    _sessionScope = _scope(widget.session);
    _load();
  }

  @override
  void didUpdateWidget(covariant ManagementProtectedAccountingPage oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (_scope(widget.session) != _sessionScope ||
        oldWidget.repository != widget.repository ||
        oldWidget.mode != widget.mode ||
        oldWidget.deviceIdentityProvider != widget.deviceIdentityProvider) {
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

  void _clearEvidence() {
    _source = _prepared = _candidate = _payoff = _closedTerm = null;
    _review = _pending = null;
    _rationale = '';
    _payoffContract = '';
    _noRebate = false;
  }

  void _clearPrivate() {
    _clearEvidence();
    _book = null;
    _choices = [];
    _scopeId = _reference = _device = '';
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
          : 'The accounting evidence could not be confirmed. Retry the unchanged request if submitted.';
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
      accountingCheck(_sessionScope == _scope(widget.session));
      await action();
    } on Object catch (error) {
      _failure(error);
    }
  }

  Future<void> _freshBook(int generation) async {
    final payload = await _read('$sourceAccountingBase/book');
    if (!_current(generation)) return;
    final value = AccountingBookIdentity.fromPayload(
      accountingObject(payload['book']),
    );
    accountingCheck(
      value.configured,
      'Configure the accounting book before reviewing source evidence.',
    );
    if (_book != null && _book!.bookId != value.bookId) {
      throw const SpinaApiException(
        'Accounting book changed. Reopen this task.',
        code: 'accounting_scope_changed',
      );
    }
    _book = value;
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
        _can('accounting.view') &&
            (!_application || _can('accounting.journal.manage')),
        'Current Management accounting permission is required.',
      );
      final identity = await widget.deviceIdentityProvider.load();
      if (!_current(generation)) return;
      _device = identity.installationId;
      await _freshBook(generation);
      if (!_current(generation)) return;
      final result = await _read(
        _application ? '$sourceTreasuryBase/workspace' : sourceAccountingBase,
      );
      if (!_current(generation)) return;
      if (_application) {
        final actor = accountingObject(result['actor']);
        accountingCheck(
          result['contract_version'] == 1 &&
              actor['user_id'] == widget.session.userId &&
              treasuryUuid(actor['device_id']) &&
              result['enabled'] == true &&
              result['owner_configured'] == true,
        );
        _choices = accountingRows(result['accounts'])
            .where(
              (row) =>
                  row['balance'] != null &&
                  row['active'] != false &&
                  ['physical_cash', 'gcash', 'bank'].contains(row['kind']),
            )
            .map((row) => {'id': row['id'], 'label': row['alias']})
            .toList();
      } else {
        _choices = accountingRows(result['fiscal_periods'])
            .map((row) => {'id': row['period_id'], 'label': row['label']})
            .toList();
      }
      accountingCheck(
        _choices.every(
          (row) => treasuryUuid(row['id']) && row['label'] is String,
        ),
      );
      if (!_choices.any((row) => row['id'] == _scopeId)) _scopeId = '';
    } on Object catch (error) {
      if (_current(generation)) _failure(error);
    } finally {
      if (_current(generation)) setState(() => _busy = false);
    }
  }

  Map<String, dynamic> _validateSource(
    Map<String, dynamic> value,
    String applicationId,
  ) => validateApplicationAccounting(
    value,
    bookId: _book!.bookId!,
    accountId: _scopeId,
    applicationId: applicationId,
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
    final source = _validateSource({
      ...accountingObject(row['snapshot']),
      'source_digest': row['source_digest'],
    }, requireTreasuryId(row['application_id']));
    for (final key in [
      'book_id',
      'application_id',
      'transaction_id',
      'receipt_id',
      'treasury_account_id',
      'loan_id',
    ]) {
      accountingCheck(row[key] == source[key]);
    }
    if (expected != null) {
      accountingCheck(jsonEncode(source) == jsonEncode(expected));
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
        'application_id',
        'transaction_id',
        'receipt_id',
        'treasury_account_id',
        'loan_id',
        'source_digest',
      ]) {
        accountingCheck(posted[key] == row[key]);
      }
    }
  }

  Future<void> _lookup({
    bool recover = false,
    bool payoff = false,
    bool closedTerm = false,
  }) async {
    accountingCheck(
      _choices.any((row) => row['id'] == _scopeId) && treasuryUuid(_reference),
      'Choose an authorized scope and an existing source reference.',
    );
    final generation = ++_generation;
    setState(() {
      _clearEvidence();
      _error = null;
      _busy = true;
    });
    try {
      if (_application) {
        if (closedTerm) {
          final result = await _read(
            '$sourceAccountingBase/treasury/applications/$_reference/closed-term-review',
          );
          if (!_current(generation)) return;
          _closedTerm = validateClosedTermCandidate(
            result,
            bookId: _book!.bookId!,
            accountId: _scopeId,
            applicationId: _reference,
          );
          return;
        }
        if (payoff) {
          final result = await _read(
            '$sourceAccountingBase/treasury/applications/$_reference/payoff-review',
          );
          if (!_current(generation)) return;
          _payoff = validatePayoffCandidate(
            result,
            bookId: _book!.bookId!,
            accountId: _scopeId,
            applicationId: _reference,
          );
          return;
        }
        final result = await _read(
          recover
              ? '$sourceAccountingBase/treasury/application-preparations/$_reference'
              : '$sourceAccountingBase/treasury/applications/$_reference/review',
        );
        if (!_current(generation)) return;
        if (recover) {
          _validatePreparation(result, preparationId: _reference);
          _prepared = result;
          final row = accountingObject(result['preparation']);
          _source = _validateSource({
            ...accountingObject(row['snapshot']),
            'source_digest': row['source_digest'],
          }, row['application_id'] as String);
        } else {
          _source = _validateSource(result, _reference);
        }
      } else {
        final result = await _read(
          '$sourceAccountingBase/period-assessments/$_scopeId/loans/$_reference',
        );
        if (!_current(generation)) return;
        _candidate = validateCutoffCandidate(
          result,
          bookId: _book!.bookId!,
          periodId: _scopeId,
          loanId: _reference,
        );
      }
    } on Object catch (error) {
      if (_current(generation)) _failure(error);
    } finally {
      if (_current(generation)) setState(() => _busy = false);
    }
  }

  List<(String, String)> _applicationFacts(Map<String, dynamic> value) => [
    (
      'Loan product',
      value['product_model'] == 'fixed_daily'
          ? 'Regular daily loan'
          : '7×7 loan',
    ),
    (
      'Accounting basis',
      value['payoff'] != null
          ? 'Reviewed full contractual payoff'
          : value['accounting_policy_version'] ==
                'treasury_regular_renewal_chronological_cash_v1'
          ? 'Renewed contract and chronological cash'
          : value['accounting_policy_version'] ==
                'treasury_regular_original_chronological_cash_v1'
          ? 'Original contract and chronological cash'
          : value['product_model'] == 'fixed_daily'
          ? 'Original first cash application (v1)'
          : '7×7 retained-funds application (v1)',
    ),
    ('Application reference', '${value['application_id']}'),
    ('Receipt reference', '${value['receipt_id']}'),
    ('Loan reference', '${value['loan_id']}'),
    ('Posting date', '${value['posting_date']}'),
    ('Applied amount', 'PHP ${value['amount']}'),
    if (value['closed_term'] != null) ...[
      (
        'Closed-term review',
        '${accountingObject(value['closed_term'])['closed_term_review_id']}',
      ),
      ('Original interest treatment', 'Stops at signed maturity; no extension'),
      (
        'Term rationale',
        '${accountingObject(value['closed_term'])['closed_term_rationale']}',
      ),
    ],
    if (value['payoff'] != null) ...[
      (
        'Payoff review',
        '${accountingObject(value['payoff'])['payoff_review_id']}',
      ),
      (
        'Signed contract evidence',
        '${accountingObject(value['payoff'])['contract_evidence_reference']}',
      ),
      (
        'Settlement gain / loss',
        'PHP ${accountingObject(value['payoff'])['settlement_difference']}',
      ),
      (
        'Treatment rationale',
        '${accountingObject(value['payoff'])['payoff_review_rationale']}',
      ),
    ],
    for (final row in accountingRows(value['lines']))
      (
        '${row['account_code']} · ${row['name']}',
        'Debit PHP ${row['debit']} · Credit PHP ${row['credit']}',
      ),
  ];
  List<(String, String)> _assessmentFacts(Map<String, dynamic> value) => [
    ('Loan reference', '${value['loan_id']}'),
    ('Cutoff date', '${value['cutoff_date']}'),
    (
      'Release boundary',
      '${accountingObject(value['boundary'])['anchor_date']}',
    ),
    (
      'Dated ECL measurement',
      '${accountingObject(value['measurement'])['date']}',
    ),
    (
      'Measured allowance',
      'PHP ${accountingObject(value['measurement'])['ecl_amount']}',
    ),
    for (final row in accountingObject(value['balances']).entries)
      ('Posted ${row.key} balance', 'PHP ${row.value}'),
    ('Source evidence fingerprint', '${value['source_digest']}'),
  ];
  void _showReview(
    String title,
    List<(String, String)> facts,
    String consequence, {
    required String path,
    required String permission,
    required Map<String, dynamic> body,
    required void Function(Map<String, dynamic>) validate,
    required void Function(Map<String, dynamic>) complete,
  }) {
    accountingCheck(_can(permission) && _pending == null);
    setState(() {
      _error = null;
      _review = _Intent(
        path: path,
        permission: permission,
        body: body,
        validate: validate,
        complete: complete,
        review: ManagementReviewPresentation.validated(
          binding: _application
              ? ManagementMutationBinding.applicationAccounting
              : ManagementMutationBinding.cutoffAssessment,
          recordLabel: _application
              ? 'Application accounting'
              : 'Dated cutoff proof',
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
      );
    });
  }

  Future<void> _send() async {
    final held = _pending ?? _review;
    accountingCheck(held != null && _can(held.permission));
    final generation = _generation;
    setState(() {
      _pending = held;
      _review = null;
      _busy = true;
      _error = null;
    });
    try {
      await _freshBook(generation);
      if (!_current(generation)) return;
      final value = await _repository.write(
        widget.session,
        deviceId: _device,
        path: held!.path,
        body: held.body,
      );
      if (!_current(generation)) return;
      held.validate(value);
      setState(() {
        _pending = null;
        held.complete(value);
      });
    } on Object catch (error) {
      if (_current(generation)) _failure(error);
    } finally {
      if (_current(generation)) setState(() => _busy = false);
    }
  }

  Future<void> _prepareApplication() async {
    final expected = _source!, requestId = (widget.uuidGenerator ?? _uuid)();
    _showReview(
      'Prepare application accounting',
      _applicationFacts(expected),
      'Retains these exact application and interest coordinates. A separate confirmation is required to post.',
      path:
          '$sourceAccountingBase/treasury/applications/${expected['application_id']}/prepare',
      permission: 'accounting.journal.manage',
      body: {
        'request_id': requestId,
        'source_digest': expected['source_digest'],
      },
      validate: (result) => _validatePreparation(
        result,
        expected: expected,
        requestId: requestId,
      ),
      complete: (result) => _prepared = result,
    );
  }

  List<(String, String)> _payoffFacts(Map<String, dynamic> value) => [
    ('Application reference', '${value['application_id']}'),
    ('Signed contract evidence', '${value['contract_evidence_reference']}'),
    ('Actual contractual payment', 'PHP ${value['amount']}'),
    ('Carrying amount cleared', 'PHP ${value['gross_carrying_before']}'),
    ('Settlement gain / loss', 'PHP ${value['settlement_difference']}'),
  ];

  Future<void> _reviewPayoff() async {
    final held = _payoff!, rationale = _rationale.trim();
    accountingCheck(
      held['review_id'] == null &&
          _noRebate &&
          _payoffContract.trim() == held['contract_evidence_reference'] &&
          rationale.length >= 20 &&
          rationale.length <= 2000,
      'Verify the exact signed-contract reference, no-rebate treatment and substantive rationale.',
    );
    _showReview(
      'Retain full payoff treatment',
      [
        ..._payoffFacts(held),
        ('Treatment', 'Full contractual payoff without rebate'),
        ('Rationale', rationale),
      ],
      'Retains this treatment evidence. Review and post the resulting application accounting separately.',
      path:
          '$sourceAccountingBase/treasury/applications/${held['application_id']}/payoff-review',
      permission: 'accounting.journal.manage',
      body: {
        'source_digest': held['source_digest'],
        'request_id': (widget.uuidGenerator ?? _uuid)(),
        'treatment': 'full_contractual_payoff_no_rebate',
        'contract_evidence_reference': _payoffContract.trim(),
        'review_rationale': rationale,
        'confirm': true,
      },
      validate: (value) {
        final checked = validatePayoffCandidate(
          value,
          bookId: _book!.bookId!,
          accountId: _scopeId,
          applicationId: held['application_id'] as String,
        );
        accountingCheck(
          checked['source_digest'] == held['source_digest'] &&
              treasuryUuid(checked['review_id']),
        );
      },
      complete: (value) => _payoff = validatePayoffCandidate(
        value,
        bookId: _book!.bookId!,
        accountId: _scopeId,
        applicationId: held['application_id'] as String,
      ),
    );
  }

  List<(String, String)> _closedTermFacts(Map<String, dynamic> value) => [
    ('Loan reference', '${value['loan_id']}'),
    ('Signed contract evidence', '${value['contract_evidence_reference']}'),
    ('Original contractual maturity', '${value['contractual_due_date']}'),
    ('Treatment', 'Original EIR through maturity, no extension'),
  ];

  Future<void> _reviewClosedTerm() async {
    final held = _closedTerm!, rationale = _rationale.trim();
    accountingCheck(
      held['review_id'] == null &&
          _noRebate &&
          _payoffContract.trim() == held['contract_evidence_reference'] &&
          rationale.length >= 20 &&
          rationale.length <= 2000,
      'Verify the exact signed maturity, no-extension treatment and substantive rationale.',
    );
    _showReview(
      'Retain closed contractual term',
      [..._closedTermFacts(held), ('Rationale', rationale)],
      'Retains the original term treatment. Review actual cash application accounting separately.',
      path:
          '$sourceAccountingBase/treasury/applications/${held['application_id']}/closed-term-review',
      permission: 'accounting.journal.manage',
      body: {
        'source_digest': held['source_digest'],
        'request_id': (widget.uuidGenerator ?? _uuid)(),
        'treatment': held['treatment'],
        'contract_evidence_reference': _payoffContract.trim(),
        'review_rationale': rationale,
        'confirm': true,
      },
      validate: (value) {
        final checked = validateClosedTermCandidate(
          value,
          bookId: _book!.bookId!,
          accountId: _scopeId,
          applicationId: held['application_id'] as String,
        );
        accountingCheck(
          checked['source_digest'] == held['source_digest'] &&
              treasuryUuid(checked['review_id']),
        );
      },
      complete: (value) => _closedTerm = validateClosedTermCandidate(
        value,
        bookId: _book!.bookId!,
        accountId: _scopeId,
        applicationId: held['application_id'] as String,
      ),
    );
  }

  Future<void> _postApplication() async {
    final expected = _source!,
        row = accountingObject(_prepared!['preparation']);
    _showReview(
      'Post application accounting',
      _applicationFacts(expected),
      'Posts the reviewed consumption of unapplied funds and protected principal and interest entries. No cash is recognized again.',
      path:
          '$sourceAccountingBase/treasury/application-preparations/${row['id']}/post',
      permission: 'accounting.journal.manage',
      body: {
        'source_digest': expected['source_digest'],
        'confirmation_token': row['confirmation_token'],
        'confirm': true,
      },
      validate: (result) {
        _validatePreparation(
          result,
          expected: expected,
          preparationId: row['id'] as String,
        );
        final posted = accountingObject(result['posting']);
        accountingCheck(
          posted['exact_posted'] == true &&
              posted['journal_entry_id'] == result['journal_entry_id'],
        );
      },
      complete: (result) => _prepared = result,
    );
  }

  Future<void> _prepareAssessment() async {
    final expected = _candidate!, rationale = _rationale.trim();
    accountingCheck(
      expected['ready'] == true &&
          rationale.length >= 20 &&
          rationale.length <= 2000,
      'Explain the actual dated proof reviewed in 20–2000 characters.',
    );
    _showReview(
      'Prepare dated cutoff assessment',
      [..._assessmentFacts(expected), ('Review rationale', rationale)],
      'Retains this actual cutoff proof for a separate confirmation. It creates no journal and does not waive any blocker.',
      path:
          '$sourceAccountingBase/period-assessments/$_scopeId/loans/${expected['loan_id']}/prepare',
      permission: 'accounting.period.close.prepare',
      body: {
        'expected_book_id': _book!.bookId,
        'source_digest': expected['source_digest'],
        'review_rationale': rationale,
      },
      validate: (result) =>
          accountingCheck(treasuryUuid(result['preparation_id'])),
      complete: (result) => _candidate = {
        ...expected,
        'preparation_id': result['preparation_id'],
      },
    );
  }

  Future<void> _confirmAssessment() async {
    final expected = _candidate!;
    accountingCheck(
      expected['ready'] == true && treasuryUuid(expected['preparation_id']),
    );
    _showReview(
      'Confirm dated cutoff proof',
      _assessmentFacts(expected),
      'Confirms the retained proof after the server rechecks exact dated evidence. It creates no journal and does not certify complete period readiness.',
      path:
          '$sourceAccountingBase/period-assessments/preparations/${expected['preparation_id']}/confirm',
      permission: 'accounting.period.close.post',
      body: {
        'expected_book_id': _book!.bookId,
        'source_digest': expected['source_digest'],
        'confirm': true,
      },
      validate: (result) =>
          accountingCheck(treasuryUuid(result['confirmation_id'])),
      complete: (result) => _candidate = {
        ...expected,
        'confirmation_id': result['confirmation_id'],
        'current_confirmation': true,
      },
    );
  }

  Widget _button(String key, String text, Future<void> Function() action) =>
      Padding(
        padding: const EdgeInsets.symmetric(vertical: 6),
        child: OutlinedButton(
          key: Key(key),
          onPressed: _busy ? null : () => _act(action),
          child: Text(text),
        ),
      );
  Widget _facts(List<(String, String)> rows) => Column(
    crossAxisAlignment: CrossAxisAlignment.stretch,
    children: rows
        .map(
          (row) => Padding(
            padding: const EdgeInsets.symmetric(vertical: 3),
            child: Text('${row.$1}: ${row.$2}'),
          ),
        )
        .toList(),
  );
  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(
      title: Text(
        _application ? 'Application accounting' : 'Dated cutoff assessments',
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
        'protected-$_generation-${_review != null}-${_pending != null}',
      ),
      padding: const EdgeInsets.all(16),
      children: [
        if (_busy) const LinearProgressIndicator(),
        if (_error != null) Text(_error!, key: const Key('protected-error')),
        if (_book != null) ...[
          Text(
            'Immutable book identity: ${_book!.entityLabel} · ${_book!.kindLabel}',
          ),
          const Text(
            'Posted ledger only. This review does not certify complete accounting readiness.',
          ),
        ],
        if (_pending != null) ...[
          const Text(
            'The result is not confirmed. Retry the unchanged request to recover its result.',
          ),
          ManagementReviewPanel(review: _pending!.review, compact: true),
          _button('protected-retry', 'Retry unchanged request', _send),
        ] else if (_review != null) ...[
          ManagementReviewPanel(review: _review!.review),
          _button(
            'protected-confirm',
            'Confirm: ${_review!.review.nextActionLabel}',
            _send,
          ),
          _button('protected-cancel', 'Cancel', () async {
            setState(() => _review = null);
          }),
        ] else if (_book != null && !_denied) ...[
          Text(
            _application
                ? 'Review an existing Treasury application. Supported Regular payments and single-loan 7×7 applications require posted receipt cash and exact loan evidence. Review the product and accounting basis below.'
                : 'Review actual evidence for the selected cutoff. Only a supported Regular loan release-day boundary with dated allowance proof can proceed.',
          ),
          DropdownButtonFormField<String>(
            key: const Key('protected-scope'),
            initialValue: _scopeId.isEmpty ? null : _scopeId,
            isExpanded: true,
            decoration: InputDecoration(
              labelText: _application
                  ? 'Treasury account'
                  : 'Accounting period',
            ),
            items: _choices
                .map(
                  (row) => DropdownMenuItem(
                    value: row['id'] as String,
                    child: Text(row['label'] as String),
                  ),
                )
                .toList(),
            onChanged: _busy
                ? null
                : (value) {
                    setState(() {
                      _generation++;
                      _scopeId = value ?? '';
                      _clearEvidence();
                    });
                  },
          ),
          TextFormField(
            key: const Key('protected-reference'),
            initialValue: _reference,
            enabled: !_busy,
            decoration: InputDecoration(
              labelText: _application
                  ? 'Existing application reference'
                  : 'Loan reference from the loan register or close review',
            ),
            onChanged: (value) {
              setState(() {
                _reference = value.trim();
                _clearEvidence();
              });
            },
          ),
          _button('protected-load', 'Load accounting review', _lookup),
          if (_application)
            _button(
              'protected-recover',
              'Open saved preparation using this reference',
              () => _lookup(recover: true),
            ),
          if (_application)
            _button(
              'protected-load-payoff',
              'Review full payoff treatment',
              () => _lookup(payoff: true),
            ),
          if (_application)
            _button(
              'protected-load-closed-term',
              'Review closed contractual term',
              () => _lookup(closedTerm: true),
            ),
          if (_application && _closedTerm != null) ...[
            const Text('Closed contractual term'),
            _facts(_closedTermFacts(_closedTerm!)),
            const Text(
              'Review the signed contract and confirm that original interest stops at its maturity. Actual overdue cash reduces existing carrying balances; full settlement differences need the separate payoff review.',
            ),
            if (_closedTerm!['review_id'] != null) ...[
              Text('Retained review: ${_closedTerm!['review_id']}'),
              _button(
                'protected-closed-term-reviewed',
                'Load reviewed application accounting',
                _lookup,
              ),
            ] else ...[
              TextFormField(
                key: const Key('protected-closed-term-contract'),
                enabled: !_busy,
                maxLength: 1000,
                decoration: const InputDecoration(
                  labelText: 'Signed contract evidence reference',
                ),
                onChanged: (value) => _payoffContract = value,
              ),
              TextFormField(
                key: const Key('protected-closed-term-rationale'),
                enabled: !_busy,
                maxLength: 2000,
                minLines: 2,
                maxLines: 5,
                decoration: const InputDecoration(
                  labelText: 'Treatment rationale',
                ),
                onChanged: (value) => _rationale = value,
              ),
              CheckboxListTile(
                key: const Key('protected-closed-term-confirm'),
                value: _noRebate,
                title: const Text(
                  'I verified original interest ends at contractual maturity with no extension.',
                ),
                onChanged: _busy
                    ? null
                    : (value) => setState(() => _noRebate = value == true),
              ),
              _button(
                'protected-closed-term-review',
                'Review closed-term treatment',
                _reviewClosedTerm,
              ),
            ],
          ],
          if (_application && _payoff != null) ...[
            const Text('Full contractual payoff treatment'),
            _facts(_payoffFacts(_payoff!)),
            const Text(
              'Confirm from the signed contract that this payment settles every installment without a rebate. The accounting review clears the carrying amount and separately reports the settlement difference.',
            ),
            if (_payoff!['review_id'] != null) ...[
              Text('Retained review: ${_payoff!['review_id']}'),
              _button(
                'protected-payoff-reviewed',
                'Load reviewed application accounting',
                _lookup,
              ),
            ] else ...[
              TextFormField(
                key: const Key('protected-payoff-contract'),
                enabled: !_busy,
                maxLength: 1000,
                decoration: const InputDecoration(
                  labelText: 'Signed contract evidence reference',
                ),
                onChanged: (value) => _payoffContract = value,
              ),
              TextFormField(
                key: const Key('protected-payoff-rationale'),
                enabled: !_busy,
                maxLength: 2000,
                minLines: 2,
                maxLines: 5,
                decoration: const InputDecoration(
                  labelText: 'Treatment rationale',
                ),
                onChanged: (value) => _rationale = value,
              ),
              CheckboxListTile(
                key: const Key('protected-payoff-no-rebate'),
                value: _noRebate,
                title: const Text(
                  'I verified full contractual payoff without a rebate.',
                ),
                onChanged: _busy
                    ? null
                    : (value) => setState(() => _noRebate = value == true),
              ),
              _button(
                'protected-payoff-review',
                'Review payoff treatment',
                _reviewPayoff,
              ),
            ],
          ],
          if (_application && _source != null) ...[
            _facts(_applicationFacts(_source!)),
            const Text(
              'No cash is recognized again. The original receipt remains the cash entry; this applies retained funds using reviewed principal and interest amounts.',
            ),
            if (_prepared == null)
              _button(
                'protected-prepare-application',
                'Prepare application accounting',
                _prepareApplication,
              )
            else ...[
              Text(
                _prepared!['posting'] != null &&
                        accountingObject(
                              _prepared!['posting'],
                            )['exact_posted'] ==
                            true
                    ? 'Application accounting posted'
                    : 'Application prepared for review',
              ),
              Text(
                'Preparation reference: ${accountingObject(_prepared!['preparation'])['id']}',
              ),
              if (_prepared!['posting'] == null)
                _button(
                  'protected-post-application',
                  'Review application posting',
                  _postApplication,
                )
              else ...[
                Text(
                  'Journal reference: ${accountingObject(_prepared!['posting'])['journal_entry_id']}',
                ),
                Text(
                  accountingObject(
                            _prepared!['posting'],
                          )['correction_pending'] ==
                          true
                      ? 'A later source change requires separate correction review.'
                      : 'Retained posting evidence is available.',
                ),
              ],
            ],
          ],
          if (!_application && _candidate != null) ...[
            Text(
              _candidate!['current_confirmation'] == true
                  ? 'Current cutoff proof confirmed'
                  : _candidate!['ready'] == true
                  ? 'Dated cutoff proof available'
                  : 'Cutoff assessment blocked',
            ),
            const Text(
              'This confirms actual dated proof only. Other sources, elapsed interest, tax and liabilities remain independent checks.',
            ),
            if (_candidate!['ready'] != true) ...[
              for (final code in _candidate!['blockers'] as List)
                Text(cutoffBlockerLabel(code as String)),
              const Text(
                'No waiver or acknowledgement can replace missing dated proof.',
              ),
            ] else ...[
              _facts(_assessmentFacts(_candidate!)),
              if (_candidate!['current_confirmation'] != true) ...[
                if (_candidate!['preparation_id'] != null) ...[
                  if (_can('accounting.period.close.post'))
                    _button(
                      'protected-confirm-assessment',
                      'Review cutoff confirmation',
                      _confirmAssessment,
                    )
                  else
                    const Text(
                      'Period-close posting permission is required to confirm.',
                    ),
                ] else if (_can('accounting.period.close.prepare')) ...[
                  TextFormField(
                    key: const Key('protected-rationale'),
                    initialValue: _rationale,
                    enabled: !_busy,
                    maxLength: 2000,
                    minLines: 2,
                    maxLines: 5,
                    decoration: const InputDecoration(
                      labelText: 'Review rationale',
                    ),
                    onChanged: (value) => _rationale = value,
                  ),
                  _button(
                    'protected-prepare-assessment',
                    'Review assessment preparation',
                    _prepareAssessment,
                  ),
                ] else
                  const Text(
                    'Period-close preparation permission is required.',
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
  bytes[6] = (bytes[6] & 15) | 64;
  bytes[8] = (bytes[8] & 63) | 128;
  final value = bytes.map((v) => v.toRadixString(16).padLeft(2, '0')).join();
  return '${value.substring(0, 8)}-${value.substring(8, 12)}-${value.substring(12, 16)}-${value.substring(16, 20)}-${value.substring(20)}';
}
