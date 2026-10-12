import 'dart:convert';
import 'dart:math';
import 'package:flutter/material.dart';
import 'package:gilbic_mobile/src/core/auth/app_role.dart';
import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/device/device_identity.dart';
import 'package:gilbic_mobile/src/core/management/accounting_readiness_repository.dart';
import 'package:gilbic_mobile/src/core/management/source_accounting_repository.dart';
import 'package:gilbic_mobile/src/core/management/payout_accounting_evidence.dart';
import 'package:gilbic_mobile/src/core/network/spina_api.dart';
import 'package:gilbic_mobile/src/core/treasury/treasury_models.dart';
import 'package:gilbic_mobile/src/features/management/review/management_review.dart';

class ManagementPayoutAccountingPage extends StatefulWidget {
  const ManagementPayoutAccountingPage({
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
  State<ManagementPayoutAccountingPage> createState() =>
      _ManagementPayoutAccountingPageState();
}

class _PayoutIntent {
  _PayoutIntent({
    required this.path,
    required Map<String, dynamic> body,
    required this.presentation,
    required this.validate,
    this.complete,
  }) : body = accountingObject(immutableTreasury(body));
  final String path;
  final Map<String, dynamic> body;
  final ManagementReviewPresentation presentation;
  final void Function(Map<String, dynamic>) validate;
  final void Function(Map<String, dynamic>)? complete;
}

class _ManagementPayoutAccountingPageState
    extends State<ManagementPayoutAccountingPage> {
  late SourceAccountingRepository _repository;
  late String _sessionScope;
  int _generation = 0;
  bool _busy = true, _denied = false, _rejected = false;
  String _device = '', _account = '', _stage = 'debit', _reference = '';
  String? _error;
  AccountingBookIdentity? _book;
  List<Map<String, dynamic>> _wallets = [];
  Map<String, dynamic>? _source, _prepared, _renewal;
  final Map<String, String> _renewalDraft = {};
  bool _termsReviewed = false, _changeAssessed = false, _signedReviewed = false;
  _PayoutIntent? _review, _pending;
  bool get _can =>
      widget.session.hasRole(AppRole.management) &&
      widget.session.hasPermission('accounting.view') &&
      widget.session.hasPermission('accounting.journal.manage');
  bool get _canRenewal =>
      _can &&
      widget.session.hasPermission(
        'accounting.renewal_treatment_decision.manage',
      );
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
  void didUpdateWidget(covariant ManagementPayoutAccountingPage oldWidget) {
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
    _source = _prepared = _renewal = null;
    _renewalDraft.clear();
    _termsReviewed = false;
    _changeAssessed = false;
    _signedReviewed = false;
    _review = null;
  }

  void _clearPrivate() {
    _clearEvidence();
    _pending = null;
    _book = null;
    _wallets = [];
    _device = _account = _reference = '';
    _stage = 'debit';
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
      'Configure the accounting book before reviewing payouts.',
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
                ['gcash', 'bank'].contains(row['kind']),
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
    String payout,
  ) => validatePayoutAccounting(
    value,
    bookId: _book!.bookId!,
    accountId: _account,
    payoutId: payout,
    stage: _stage,
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
    }, requireTreasuryId(row['payout_id']));
    for (final key in [
      'book_id',
      'payout_id',
      'stage',
      'event_id',
      'treasury_account_id',
      'loan_id',
      'client_id',
      'disbursement_event_id',
    ]) {
      accountingCheck(row[key] == projected[key]);
    }
    if (expected != null) {
      accountingCheck(jsonEncode(projected) == jsonEncode(expected));
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
        'payout_id',
        'stage',
        'event_id',
        'treasury_account_id',
        'loan_id',
        'client_id',
        'disbursement_event_id',
        'source_digest',
      ]) {
        accountingCheck(posted[key] == row[key]);
      }
    }
  }

  Future<void> _lookup({bool recover = false, bool renewal = false}) async {
    accountingCheck(
      _wallets.any((row) => row['id'] == _account) && treasuryUuid(_reference),
      'Choose the authorized funding wallet and an existing payout or preparation reference.',
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
      if (renewal) {
        accountingCheck(
          _canRenewal,
          'Current renewal treatment permission is required.',
        );
        accountingCheck(
          _stage == 'completion',
          'Choose borrower completion to review renewal treatment.',
        );
        final result = await _read(
          '$sourceAccountingBase/treasury/payouts/$_reference/renewal-measurement',
        );
        if (!_current(generation)) return;
        _renewal = validateRenewalCandidate(
          result,
          bookId: _book!.bookId!,
          accountId: _account,
          payoutId: _reference,
        );
      } else if (recover) {
        final result = await _read(
          '$sourceAccountingBase/treasury/payout-preparations/$_reference',
        );
        if (!_current(generation)) return;
        _validatePreparation(result, preparationId: _reference);
        _prepared = result;
        final row = accountingObject(result['preparation']);
        _source = _validateSource({
          ...accountingObject(row['snapshot']),
          'source_digest': row['source_digest'],
        }, row['payout_id'] as String);
      } else {
        final query = Uri(queryParameters: {'stage': _stage}).query;
        final result = await _read(
          '$sourceAccountingBase/treasury/payouts/$_reference/review?$query',
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
    ('Payout reference', '${_source!['payout_id']}'),
    (
      'Actual stage',
      _stage == 'debit' ? 'Verified wallet debit' : 'Borrower completion',
    ),
    (
      'Funding wallet',
      '${_wallets.firstWhere((row) => row['id'] == _account)['alias']}',
    ),
    ('Loan reference', '${_source!['loan_id']}'),
    ('Actual posting date', '${_source!['posting_date']}'),
    ('Principal', 'PHP ${_source!['amount']}'),
    ('Actual wallet fee', 'PHP ${_source!['fee']}'),
    if (_source!['measurement'] != null) ...[
      ('Renewal treatment', '${_source!['renewal_decision']}'),
      ('Old operational loan', '${_source!['old_loan_id']}'),
      ('Accounting asset', '${_source!['accounting_asset_id']}'),
      ('Retained treatment review', '${_source!['renewal_review_id']}'),
      for (final item in accountingObject(_source!['measurement']).entries)
        (item.key, '${item.value is bool ? '' : 'PHP '}${item.value}'),
    ],
    ..._boundaryFacts(_source!),
    for (final row in accountingRows(_source!['lines']))
      (
        '${row['account_code']} · ${row['name']}${row['loan_id'] == null ? '' : ' — loan ${row['loan_id']}'}',
        'Debit PHP ${row['debit']} · Credit PHP ${row['credit']}',
      ),
  ];
  List<(String, String)> _boundaryFacts(Map<String, dynamic> value) {
    if (value['credit_impaired_boundary'] == null) return [];
    final boundary = accountingObject(value['credit_impaired_boundary']);
    return [
      (
        'Allowance before impaired boundary',
        'PHP ${boundary['allowance_before']}',
      ),
      (
        'Gross/net allowance reconciliation',
        'PHP ${boundary['allowance_unwind']}',
      ),
      ('Impairment adjustment', 'PHP ${boundary['impairment_adjustment']}'),
      (
        'Allowance after impaired boundary',
        'PHP ${boundary['allowance_after']}',
      ),
    ];
  }

  List<(String, String)> _renewalFacts(Map<String, dynamic> value) => [
    ..._boundaryFacts(value),
    if (value.containsKey('predecessor_credit_impaired'))
      (
        'Predecessor credit-impaired',
        '${value['predecessor_credit_impaired']}',
      ),
    if (value['derecognition_blocker'] != null)
      (
        'Derecognition unavailable',
        'Supported successor initial credit status and credit-adjusted EIR policy are required. Modification remains subject to explicit review.',
      ),
    ('Renewal effective date', '${value['effective_date']}'),
    ('Signed schedule', '${value['schedule_id']}'),
    if (value['contract_reference'] != null)
      ('Contract reference', '${value['contract_reference']}'),
    if (value['evidence_reference'] != null)
      ('Signed evidence reference', '${value['evidence_reference']}'),
    ('Old operational loan', '${value['old_loan_id']}'),
    ('New operational loan', '${value['new_loan_id']}'),
    ('Existing accounting asset', '${value['accounting_asset_id']}'),
    ('Fresh cash', 'PHP ${value['fresh_cash']}'),
    ('Old gross carrying amount', 'PHP ${value['old_gross_carrying']}'),
    ('Old allowance', 'PHP ${value['old_allowance']}'),
    ('Original daily EIR', '${value['original_daily_eir']}'),
    ('Revised present value at original EIR', 'PHP ${value['revised_pv']}'),
    ('Signed nominal settlement', 'PHP ${value['nominal_settlement']}'),
  ];
  Future<void> _reviewRenewal() async {
    accountingCheck(
      _canRenewal &&
          _renewal != null &&
          _renewal!['retained_review'] == null &&
          _pending == null,
    );
    final held = _renewal!, evidence = _renewalDraft['evidence_id'];
    accountingCheck(
      treasuryUuid(evidence),
      'Supply the uploaded private measurement evidence ID.',
    );
    final inputs = validateRenewalReviewInputs({
      ..._renewalDraft,
      'qualitative_assessment': {
        'signed_contract_reviewed': _signedReviewed,
        'cash_flow_terms_reviewed': _termsReviewed,
        'substantial_change_assessed': _changeAssessed,
        'decision_basis': _renewalDraft['qualitative_basis'],
      },
    }, held);
    final requestId = (widget.uuidGenerator ?? _uuid)();
    const consequence =
        'Retains treatment and evidence only. Journal preparation and posting remain separate confirmations.';
    final facts = [
      ..._renewalFacts(held),
      ('Uploaded evidence', '$evidence'),
      ('Treatment', '${inputs['decision']}'),
      ('Policy reference', '${inputs['accounting_policy_reference']}'),
      (
        'Qualitative assessment',
        '${accountingObject(inputs['qualitative_assessment'])['decision_basis']}',
      ),
      ('Decision rationale', '${inputs['decision_rationale']}'),
      ('Consideration', '${inputs['settlement_consideration']}'),
      ('Rebate', '${inputs['settlement_rebate']}'),
      ('Settlement basis', '${inputs['settlement_basis']}'),
      if (inputs['decision'] == 'derecognition') ...[
        ('New initial fair value', '${inputs['new_initial_fair_value']}'),
        ('Fair value date', '${inputs['fair_value_effective_date']}'),
        ('Fair value basis', '${inputs['fair_value_basis']}'),
        (
          'Day-one difference rationale',
          '${inputs['day_one_difference_rationale']}',
        ),
      ],
    ];
    setState(
      () => _review = _PayoutIntent(
        path:
            '$sourceAccountingBase/treasury/payouts/${held['payout_id']}/renewal-measurement',
        body: {
          'source_digest': held['source_digest'],
          'request_id': requestId,
          'evidence_id': evidence,
          'confirm': true,
          'review': inputs,
        },
        validate: (value) {
          accountingCheck(
            value['payout_id'] == held['payout_id'] &&
                value['book_id'] == held['book_id'] &&
                value['source_digest'] == held['source_digest'] &&
                value['request_id'] == requestId &&
                value['decision'] == inputs['decision'] &&
                treasuryUuid(value['id']) &&
                accountingDigest(value['measurement_digest']),
          );
        },
        complete: (value) {
          _renewal = {
            ...held,
            'retained_review': {
              for (final key in ['id', 'decision', 'measurement_digest'])
                key: value[key],
            },
          };
        },
        presentation: ManagementReviewPresentation.validated(
          binding: ManagementMutationBinding.payoutAccounting,
          recordLabel: 'Renewal treatment evidence',
          recordValue: 'Retain renewal treatment',
          statusLabel: 'Awaiting explicit confirmation',
          facts: facts
              .map((f) => ManagementReviewFact(label: f.$1, value: f.$2))
              .toList(),
          warnings: const [
            ManagementReviewWarning(
              severity: ManagementReviewWarningSeverity.caution,
              message: consequence,
            ),
          ],
          nextActionLabel: 'Retain renewal treatment',
          consequence: consequence,
        ),
      ),
    );
  }

  Widget _renewalInput(String name, String label) => TextFormField(
    key: Key('renewal-$name'),
    initialValue: _renewalDraft[name] ?? '',
    enabled: !_busy,
    maxLength: 2000,
    decoration: InputDecoration(labelText: label),
    onChanged: (value) => _renewalDraft[name] = value.trim(),
  );
  List<Widget> _renewalContent() {
    final value = _renewal!;
    return [
      for (final fact in _renewalFacts(value))
        Padding(
          padding: const EdgeInsets.symmetric(vertical: 3),
          child: Text('${fact.$1}: ${fact.$2}'),
        ),
      if (value['retained_review'] != null) ...[
        const Text('Renewal treatment retained'),
        Text(
          'Treatment: ${accountingObject(value['retained_review'])['decision']}',
        ),
        Text(
          'Review reference: ${accountingObject(value['retained_review'])['id']}',
        ),
        const Text(
          'Load borrower-completion accounting to prepare and separately post the retained treatment.',
        ),
      ] else ...[
        const Text(
          'Use retained contract, settlement and accounting policy evidence. Choose the treatment explicitly; no amount or fair value is inferred.',
        ),
        _renewalInput(
          'evidence_id',
          'Uploaded signed-contract, settlement and measurement bundle ID',
        ),
        DropdownButtonFormField<String>(
          key: const Key('renewal-decision'),
          initialValue: _renewalDraft['decision'],
          decoration: const InputDecoration(labelText: 'Reviewed treatment'),
          items: [
            const DropdownMenuItem(
              value: 'modification_no_derecognition',
              child: Text('Modification — accounting asset continues'),
            ),
            DropdownMenuItem(
              value: 'derecognition',
              enabled: value['derecognition_blocker'] == null,
              child: const Text('Derecognition — new accounting asset'),
            ),
          ],
          isExpanded: true,
          onChanged: _busy
              ? null
              : (v) => setState(() => _renewalDraft['decision'] = v ?? ''),
        ),
        _renewalInput(
          'accounting_policy_reference',
          'Accounting policy reference',
        ),
        CheckboxListTile(
          key: const Key('renewal-signed_contract_reviewed'),
          title: const Text(
            'Uploaded bundle contains the signed renewal contract matching the displayed schedule and references, plus settlement and measurement support',
          ),
          value: _signedReviewed,
          onChanged: _busy
              ? null
              : (v) => setState(() => _signedReviewed = v == true),
        ),
        CheckboxListTile(
          key: const Key('renewal-cash_flow_terms_reviewed'),
          title: const Text('Contractual cash-flow changes reviewed'),
          value: _termsReviewed,
          onChanged: _busy
              ? null
              : (v) => setState(() => _termsReviewed = v == true),
        ),
        CheckboxListTile(
          key: const Key('renewal-substantial_change_assessed'),
          title: const Text('Substantial change assessed against the policy'),
          value: _changeAssessed,
          onChanged: _busy
              ? null
              : (v) => setState(() => _changeAssessed = v == true),
        ),
        _renewalInput(
          'qualitative_basis',
          'Qualitative assessment (at least 20 characters)',
        ),
        _renewalInput(
          'decision_rationale',
          'Treatment rationale (at least 20 characters)',
        ),
        _renewalInput(
          'settlement_consideration',
          'Settlement consideration (exact decimal)',
        ),
        _renewalInput(
          'settlement_rebate',
          'Settlement rebate (0.00 only when evidenced as none)',
        ),
        _renewalInput(
          'settlement_basis',
          'Settlement basis (at least 20 characters)',
        ),
        const Text(
          'For derecognition only, provide all four fair-value fields. For modification, leave them empty.',
        ),
        _renewalInput('new_initial_fair_value', 'New initial fair value'),
        _renewalInput(
          'fair_value_effective_date',
          'Fair value effective date (YYYY-MM-DD)',
        ),
        _renewalInput('fair_value_basis', 'Fair value basis'),
        _renewalInput(
          'day_one_difference_rationale',
          'Day-one difference rationale, including zero difference',
        ),
        _button('renewal-review', 'Review renewal treatment', _reviewRenewal),
      ],
    ];
  }

  Future<void> _reviewAction({required bool posting}) async {
    accountingCheck(_source != null && _pending == null);
    accountingCheck(
      _source!['accounting_policy_version'] !=
              'native_regular_renewal_completion_v1' ||
          _canRenewal,
      'Current renewal treatment permission is required.',
    );
    final expected = _source!, requestId = (widget.uuidGenerator ?? _uuid)();
    final row = posting ? accountingObject(_prepared!['preparation']) : null;
    final title = posting
        ? 'Post payout stage accounting'
        : 'Prepare payout stage accounting';
    final consequence = posting
        ? 'Posts only this actual stage. A debit records cash leaving for loan payout transit; borrower completion moves that same principal into the approved loan receivable without another cash credit.'
        : 'Retains these exact actual-stage coordinates. Posting requires a separate confirmation.';
    setState(() {
      _review = _PayoutIntent(
        path: posting
            ? '$sourceAccountingBase/treasury/payout-preparations/${row!['id']}/post'
            : '$sourceAccountingBase/treasury/payouts/${expected['payout_id']}/prepare',
        body: posting
            ? {
                'source_digest': expected['source_digest'],
                'confirmation_token': row!['confirmation_token'],
                'confirm': true,
              }
            : {
                'stage': _stage,
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
          binding: ManagementMutationBinding.payoutAccounting,
          recordLabel: 'Actual protected payout stage',
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
        if (held.complete != null) {
          held.complete!(result);
        } else {
          _prepared = result;
        }
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
      title: const Text('Payout accounting'),
      actions: [
        IconButton(
          tooltip: 'Refresh payout accounting',
          onPressed: _busy || _pending != null || _denied
              ? null
              : () => _act(_load),
          icon: const Icon(Icons.refresh),
        ),
      ],
    ),
    body: ListView(
      key: ValueKey(
        'payout-$_generation-${_review != null}-${_pending != null}',
      ),
      padding: const EdgeInsets.all(16),
      children: [
        if (_busy) const LinearProgressIndicator(),
        if (_error != null) Text(_error!, key: const Key('payout-error')),
        if (_book != null)
          Text('Book: ${_book!.entityLabel} · ${_book!.kindLabel}'),
        if (_pending != null) ...[
          const Text(
            'The result is not confirmed. Retry the unchanged request to recover it.',
          ),
          ManagementReviewPanel(review: _pending!.presentation, compact: true),
          _button('payout-retry', 'Retry unchanged request', _send),
          if (_rejected)
            _button('payout-reload', 'Reload current evidence', () async {
              setState(() => _pending = null);
              await _load();
            }),
        ] else if (_review != null) ...[
          ManagementReviewPanel(review: _review!.presentation),
          _button(
            'payout-confirm',
            'Confirm: ${_review!.presentation.nextActionLabel}',
            _send,
          ),
          _button('payout-cancel', 'Cancel', () async {
            setState(() => _review = null);
          }),
        ] else if (_book != null && !_denied) ...[
          const Text(
            'Review the actual wallet debit separately from protected borrower completion. Receipt by a Collector leaves the amount in loan payout transit. Overall accounting readiness remains a separate review.',
          ),
          _wallet(
            'payout-account',
            'Funding wallet',
            _account,
            (value) => _account = value,
          ),
          DropdownButtonFormField<String>(
            key: const Key('payout-stage'),
            initialValue: _stage,
            decoration: const InputDecoration(labelText: 'Actual stage'),
            items: const [
              DropdownMenuItem(
                value: 'debit',
                child: Text('Verified wallet debit'),
              ),
              DropdownMenuItem(
                value: 'completion',
                child: Text('Borrower completion'),
              ),
            ],
            onChanged: _busy
                ? null
                : (value) => setState(() {
                    _stage = value ?? 'debit';
                    _clearEvidence();
                  }),
          ),
          TextFormField(
            key: const Key('payout-reference'),
            initialValue: _reference,
            enabled: !_busy,
            maxLength: 36,
            decoration: const InputDecoration(
              labelText: 'Existing payout or saved preparation reference',
            ),
            onChanged: (value) => setState(() {
              _reference = value.trim();
              _clearEvidence();
            }),
          ),
          _button('payout-load', 'Load payout accounting review', _lookup),
          _button(
            'payout-recover',
            'Open saved preparation',
            () => _lookup(recover: true),
          ),
          if (_canRenewal)
            _button(
              'payout-renewal-load',
              'Review renewal treatment',
              () => _lookup(renewal: true),
            ),
          if (_renewal != null) ..._renewalContent(),
          if (_source != null) ...[
            for (final fact in _facts())
              Padding(
                padding: const EdgeInsets.symmetric(vertical: 3),
                child: Text('${fact.$1}: ${fact.$2}'),
              ),
            if (_prepared == null)
              _button(
                'payout-prepare',
                'Prepare payout stage accounting',
                () => _reviewAction(posting: false),
              )
            else ...[
              Text(
                _prepared!['posting'] != null &&
                        accountingObject(
                              _prepared!['posting'],
                            )['exact_posted'] ==
                            true
                    ? 'Payout stage accounting posted'
                    : 'Payout stage prepared for review',
              ),
              Text(
                'Preparation ${accountingObject(_prepared!['preparation'])['id']}',
              ),
              if (_prepared!['posting'] == null)
                _button(
                  'payout-post',
                  'Review payout stage posting',
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
