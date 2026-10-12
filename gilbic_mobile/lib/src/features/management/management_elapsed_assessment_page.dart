import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:gilbic_mobile/src/core/auth/app_role.dart';
import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/device/device_identity.dart';
import 'package:gilbic_mobile/src/core/management/accounting_readiness_repository.dart';
import 'package:gilbic_mobile/src/core/management/elapsed_assessment_evidence.dart';
import 'package:gilbic_mobile/src/core/management/current_risk_review.dart';
import 'package:gilbic_mobile/src/core/management/source_accounting_repository.dart';
import 'package:gilbic_mobile/src/core/network/spina_api.dart';
import 'package:gilbic_mobile/src/core/treasury/treasury_models.dart';

class ManagementElapsedAssessmentPage extends StatefulWidget {
  const ManagementElapsedAssessmentPage({
    required this.session,
    required this.deviceIdentityProvider,
    this.repository,
    super.key,
  });
  final UserSession session;
  final DeviceIdentityProvider deviceIdentityProvider;
  final SourceAccountingRepository? repository;
  @override
  State<ManagementElapsedAssessmentPage> createState() =>
      _ElapsedAssessmentState();
}

class _Intent {
  _Intent(
    this.title,
    this.permission,
    this.path,
    Map<String, dynamic> body,
    this.validate,
    this.complete, {
    this.reviewInputs,
    this.prepared,
    this.details,
    this.notice,
  }) : body = accountingObject(immutableTreasury(body));
  final String title, permission, path;
  final Map<String, dynamic> body;
  final Map<String, dynamic>? reviewInputs, prepared;
  final Map<String, dynamic>? details;
  final String? notice;
  final void Function(Map<String, dynamic>) validate, complete;
}

Map<String, dynamic> _scenario() => {
  'scenario_key': '',
  'probability': '',
  'evidence_reference': '',
  'management_rationale': '',
  'forward_evidence_ids': <String>[],
  'expected_cash_flows': <Map<String, dynamic>>[
    {'cash_date': '', 'amount': ''},
  ],
};
Map<String, dynamic> _draft() => {
  'evidence_reference': '',
  'review_note': '',
  'review_rationale': '',
  'scenarios': <Map<String, dynamic>>[_scenario(), _scenario()],
};

class _ElapsedAssessmentState extends State<ManagementElapsedAssessmentPage> {
  late SourceAccountingRepository _repository;
  late String _sessionScope;
  String _device = '', _period = '', _loan = '';
  String? _error, _posting, _notice;
  bool _busy = true, _denied = false, _rejected = false;
  int _generation = 0, _evidenceOffset = 0, _formVersion = 0;
  AccountingBookIdentity? _book;
  List<Map<String, dynamic>> _periods = [], _evidence = [];
  final Map<String, Map<String, dynamic>> _evidenceSeen = {};
  Map<String, dynamic>? _candidate, _prepared, _riskContext, _cashReview;
  Map<String, dynamic>? _retainedMeasurement;
  Map<String, dynamic> _riskInputs = {};
  Map<String, dynamic> _inputs = _draft();
  _Intent? _review, _pending;
  String _scope(UserSession s) =>
      jsonEncode([s.userId, s.accessToken, s.roles, s.rawRole, s.permissions]);
  bool _can(String permission) =>
      widget.session.hasRole(AppRole.management) &&
      widget.session.hasPermission(permission);
  bool _current(int generation) =>
      mounted &&
      generation == _generation &&
      _scope(widget.session) == _sessionScope;
  @override
  void initState() {
    super.initState();
    _repository = widget.repository ?? SpinaSourceAccountingRepository();
    _sessionScope = _scope(widget.session);
    _load();
  }

  @override
  void didUpdateWidget(covariant ManagementElapsedAssessmentPage oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (_scope(widget.session) != _sessionScope ||
        oldWidget.repository != widget.repository ||
        oldWidget.deviceIdentityProvider != widget.deviceIdentityProvider) {
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
    _candidate = _prepared = null;
    _riskContext = _cashReview = null;
    _retainedMeasurement = null;
    _riskInputs = {};
    _notice = null;
    _review = _pending = null;
    _inputs = _draft();
    _posting = null;
    _error = null;
    _rejected = false;
  }

  void _clearPrivate() {
    _clearEvidence();
    _book = null;
    _periods = [];
    _evidence = [];
    _evidenceSeen.clear();
    _evidenceOffset = 0;
    _period = _loan = _device = '';
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
          : 'The result could not be verified. Retry the unchanged request if submitted.';
      _rejected =
          error is SpinaApiException && [409, 422].contains(error.statusCode);
      if (error is SpinaApiException &&
          ([401, 403, 426].contains(error.statusCode) ||
              error.code == 'accounting_scope_changed')) {
        _generation++;
        _clearPrivate();
        _denied = true;
        _error = 'Accounting access changed. Reopen this task.';
      }
    });
  }

  Future<void> _act(Future<void> Function() action) async {
    if (_busy || _denied) return;
    try {
      accountingCheck(_scope(widget.session) == _sessionScope);
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
      'Configure the accounting book before reviewing historical sources.',
    );
    if (_book != null && _book!.bookId != value.bookId) {
      throw const SpinaApiException(
        'Accounting book changed.',
        code: 'accounting_scope_changed',
      );
    }
    _book = value;
  }

  Future<void> _readEvidence(int offset, int generation) async {
    final payload = await _read(
      '$sourceAccountingBase/ecl-forward-looking-evidence?status=all&limit=100&offset=$offset',
    );
    if (!_current(generation)) return;
    final rows = accountingRows(payload['items']);
    accountingCheck(rows.length <= 100);
    final projected = rows.map((r) {
      accountingCheck(
        treasuryUuid(r['id']) &&
            r['source_name'] is String &&
            r['source_reference'] is String &&
            accountingDate(r['effective_date']) &&
            accountingDate(r['forecast_period_start']) &&
            accountingDate(r['forecast_period_end']) &&
            r['evidence_status'] is String,
      );
      return <String, dynamic>{
        for (final key in [
          'id',
          'source_name',
          'source_reference',
          'effective_date',
          'forecast_period_start',
          'forecast_period_end',
          'evidence_status',
        ])
          key: r[key],
      };
    }).toList();
    _evidence = projected;
    _evidenceOffset = offset;
    for (final row in projected) {
      _evidenceSeen[row['id'] as String] = row;
    }
  }

  Future<void> _load() async {
    final generation = ++_generation;
    setState(() {
      _busy = true;
      _clearEvidence();
    });
    try {
      accountingCheck(
        _can('accounting.view'),
        'Current Management accounting access is required.',
      );
      final device = await widget.deviceIdentityProvider.load();
      if (!_current(generation)) return;
      _device = device.installationId;
      await _freshBook(generation);
      if (!_current(generation)) return;
      final overview = await _read(sourceAccountingBase);
      if (!_current(generation)) return;
      final periods = accountingRows(overview['fiscal_periods']);
      accountingCheck(
        periods.every(
          (p) => treasuryUuid(p['period_id']) && p['label'] is String,
        ),
      );
      _periods = periods
          .map(
            (p) => <String, dynamic>{
              'period_id': p['period_id'],
              'label': p['label'],
            },
          )
          .toList();
      await _readEvidence(0, generation);
      if (_current(generation)) setState(() => _busy = false);
    } on Object catch (error) {
      if (_current(generation)) _failure(error);
    }
  }

  Future<void> _lookup() async {
    accountingCheck(
      _periods.any((p) => p['period_id'] == _period) && treasuryUuid(_loan),
      'Choose a fiscal period and enter its loan ID.',
    );
    final generation = ++_generation;
    setState(() {
      _clearEvidence();
      _busy = true;
    });
    try {
      await _freshBook(generation);
      if (!_current(generation)) return;
      final value = await _read('$elapsedAssessmentBase/$_period/loans/$_loan');
      if (!_current(generation)) return;
      final result = validateElapsedCandidate(
        value,
        bookId: _book!.bookId!,
        periodId: _period,
        loanId: _loan,
      );
      setState(() {
        _candidate = result;
        _prepared = result['preparation'] == null
            ? null
            : accountingObject(result['preparation']);
        _busy = false;
      });
    } on Object catch (error) {
      if (_current(generation)) _failure(error);
    }
  }

  Map<String, dynamic> _validatedPreparation(Map<String, dynamic> v) =>
      validateElapsedPreparation(
        v,
        bookId: _book!.bookId!,
        periodId: _period,
        loanId: _loan,
        candidate: _candidate,
      );
  void _prepare() {
    accountingCheck(_can('accounting.period.close.prepare'));
    if (_cashReview != null) {
      _prepareCash();
      return;
    }
    final lifetime = _candidate!['eligible_credit_risk_review'] != null;
    final inputs = lifetime
        ? validateElapsedRiskInputs(_inputs, _candidate!)
        : validateElapsedInputs(_inputs, _candidate!['as_of_date'] as String);
    final body = {
      'expected_book_id': _book!.bookId,
      'source_digest': _candidate!['source_digest'],
      ...inputs,
      if (lifetime) 'confirm': true,
    };
    setState(
      () => _review = _Intent(
        lifetime
            ? 'Retain ${_riskLabel(accountingObject(_candidate!['eligible_credit_risk_review']))} calculation'
            : 'Retain historical calculation',
        'accounting.period.close.prepare',
        '$elapsedAssessmentBase/$_period/loans/$_loan/${lifetime ? 'prepare-risk' : 'prepare'}',
        body,
        (v) {
          final result = _validatedPreparation(v);
          accountingCheck(
            canonicalTreasury(result['review_inputs']) ==
                canonicalTreasury(inputs),
            'The returned calculation inputs differ from the reviewed request.',
          );
        },
        (v) {
          _prepared = _validatedPreparation(v);
        },
        reviewInputs: inputs,
      ),
    );
  }

  void _prepareSettled({bool renewed = false}) {
    final flag = renewed
        ? 'settled_by_exact_renewal'
        : 'settled_by_exact_payoff';
    final key = renewed ? 'renewal_review_id' : 'payoff_review_id';
    accountingCheck(
      _can('accounting.period.close.prepare') && _candidate![flag] == true,
    );
    final raw = {
      key: _candidate![key],
      'review_rationale': _inputs['review_rationale'],
    };
    final inputs = renewed
        ? validateElapsedRenewedInputs(raw)
        : validateElapsedSettledInputs(raw);
    setState(
      () => _review = _Intent(
        renewed
            ? 'Retain renewed loan zero assessment'
            : 'Retain settled payoff assessment',
        'accounting.period.close.prepare',
        '$elapsedAssessmentBase/$_period/loans/$_loan/${renewed ? 'prepare-renewed' : 'prepare-settled'}',
        {
          'expected_book_id': _book!.bookId,
          'source_digest': _candidate!['source_digest'],
          ...inputs,
          'confirm': true,
        },
        (v) {
          final result = _validatedPreparation(v);
          accountingCheck(
            canonicalTreasury(result['review_inputs']) ==
                canonicalTreasury(inputs),
            'The returned settlement review differs from the reviewed request.',
          );
        },
        (v) => _prepared = _validatedPreparation(v),
        reviewInputs: inputs,
      ),
    );
  }

  void _post() {
    accountingCheck(_can('accounting.period.close.post'));
    final p = _prepared!;
    setState(
      () => _review = _Intent(
        'Post historical assessment',
        'accounting.period.close.post',
        '$elapsedAssessmentBase/preparations/${p['preparation_id']}/confirm',
        {
          'expected_book_id': _book!.bookId,
          'confirmation_digest': p['confirmation_digest'],
          'confirm': true,
        },
        (v) {
          accountingCheck(treasuryUuid(v['posting_id']));
        },
        (v) {
          _posting = v['posting_id'] as String;
        },
        prepared: p,
      ),
    );
  }

  Future<void> _send() async {
    final held = _pending ?? _review;
    accountingCheck(held != null && _can(held.permission));
    final intent = held!;
    final generation = _generation;
    setState(() {
      _busy = true;
      _error = null;
      _rejected = false;
    });
    try {
      await _freshBook(generation);
      if (!_current(generation)) return;
      _pending = intent;
      _review = null;
      final value = await _repository.write(
        widget.session,
        deviceId: _device,
        path: intent.path,
        body: accountingObject(immutableTreasury(intent.body)),
      );
      if (!_current(generation)) return;
      intent.validate(value);
      setState(() {
        _pending = null;
        _busy = false;
        intent.complete(value);
      });
    } on Object catch (error) {
      if (_current(generation)) _failure(error);
    }
  }

  Future<void> _pageEvidence(int offset) async {
    final generation = _generation;
    setState(() => _busy = true);
    try {
      await _readEvidence(offset, generation);
      if (_current(generation)) setState(() => _busy = false);
    } on Object catch (error) {
      if (_current(generation)) _failure(error);
    }
  }

  Widget _button(String key, String label, Future<void> Function() action) =>
      Padding(
        padding: const EdgeInsets.symmetric(vertical: 6),
        child: FilledButton(
          key: Key(key),
          onPressed: _busy ? null : () => _act(action),
          child: Text(label),
        ),
      );
  Widget _field(
    String key,
    String label,
    String value,
    void Function(String) changed, {
    int max = 2000,
  }) => Padding(
    padding: const EdgeInsets.symmetric(vertical: 6),
    child: TextFormField(
      key: Key(key),
      initialValue: value,
      maxLength: max,
      enabled: !_busy,
      decoration: InputDecoration(
        labelText: label,
        border: const OutlineInputBorder(),
      ),
      onChanged: changed,
    ),
  );
  List<Widget> _facts(Map<String, dynamic> rows) => rows.entries
      .map(
        (e) => Padding(
          padding: const EdgeInsets.symmetric(vertical: 4),
          child: Text('${e.key}: ${e.value}'),
        ),
      )
      .toList();
  List<Widget> _preparationFacts(Map<String, dynamic> p) => [
    ..._inputReview(accountingObject(p['review_inputs'])),
    ..._impairedFacts(p),
    ..._facts({
      'Economic cutoff': p['as_of_date'],
      'Calculated at (actual timestamp)': p['calculated_at'],
      p['credit_impaired_interest'] != null
              ? 'Unposted gross interest tail'
              : 'Interest to recognize':
          p['incremental_interest'],
      'Cumulative gross interest': p['cumulative_interest'],
      if (p['loss_basis'] == 'gross_carrying_less_expected_pv') ...{
        'Loss measurement basis':
            'Gross carrying less expected cash present value',
        'Verified gross carrying': p['gross_carrying_amount'],
        'Expected cash present value': p['expected_cash_present_value'],
        'Unrounded weighted expected cash present value':
            p['weighted_expected_cash_present_value_raw'],
        'Currency rounding adjustment': p['currency_rounding_adjustment'],
      },
      'Expected credit loss': p['ecl_amount'],
      'Prior posted allowance': p['prior_allowance'],
      p['credit_impaired_interest'] != null
              ? 'Impairment adjustment'
              : 'Allowance change':
          p['allowance_delta'],
      if (p['credit_impaired_interest'] != null)
        'Total allowance balance change': _allowanceChange(p),
      'Scenarios': p['scenario_count'],
      'Preparation reference': p['preparation_id'],
    }),
  ];
  String _riskLabel(Map<String, dynamic> risk) =>
      risk['stage_label'] == 'stage_1_12_month'
      ? 'Stage 1 reviewed 12-month'
      : risk['stage_label'] == 'stage_3_credit_impaired'
      ? 'Stage 3 credit-impaired'
      : 'Stage 2 lifetime';
  String _allowanceChange(Map<String, dynamic> p) {
    final n =
        BigInt.parse((p['ecl_amount'] as String).replaceAll('.', '')) -
        BigInt.parse((p['prior_allowance'] as String).replaceAll('.', ''));
    final digits = n.abs().toString().padLeft(3, '0');
    return '${n.isNegative ? '-' : ''}${digits.substring(0, digits.length - 2)}.${digits.substring(digits.length - 2)}';
  }

  Future<void> _loadRisk() async {
    accountingCheck(_can('accounting.ecl.credit_risk_label.review'));
    final generation = _generation;
    setState(() => _busy = true);
    try {
      await _freshBook(generation);
      if (!_current(generation)) return;
      final v = await _read(
        '$elapsedAssessmentBase/$_period/loans/$_loan/risk-review',
      );
      if (!_current(generation)) return;
      final c = validateCurrentRiskContext(
        v,
        bookId: _book!.bookId!,
        periodId: _period,
        loanId: _loan,
      );
      setState(() {
        _riskContext = c;
        _riskInputs = {};
        _busy = false;
        _error = null;
      });
    } on Object catch (error) {
      if (_current(generation)) _failure(error);
    }
  }

  Map<String, dynamic> _riskFacts(Map<String, dynamic> c) {
    final inherited = c['prior_review'] == null && c['inherited_review'] != null
        ? accountingObject(c['inherited_review'])
        : null;
    return {
      'Economic cutoff': c['as_of_date'],
      'Schedule reference': c['schedule_id'],
      'Schedule version': c['schedule_version'],
      'Contractual days past due': c['days_past_due'],
      'Due unpaid amount': c['due_unpaid_amount'],
      if (inherited != null) ...{
        'Inherited credit-risk review': inherited['id'],
        'Predecessor loan': inherited['loan_id'],
        'Predecessor review version': inherited['review_version'],
        'Inherited stage': inherited['stage_label'],
        'Inherited default label': inherited['default_label'],
        'Inherited write-off support label': inherited['write_off_label'],
        'Inherited recovery label': inherited['recovery_label'],
        'Predecessor review recorded at': inherited['reviewed_at'],
      },
    };
  }

  void _prepareRiskReview() {
    accountingCheck(_can('accounting.ecl.credit_risk_label.review'));
    final c = _riskContext!, inputs = validateCurrentRiskInputs(_riskInputs, c);
    setState(
      () => _review = _Intent(
        'Retain current-cutoff credit-risk review',
        'accounting.ecl.credit_risk_label.review',
        '$elapsedAssessmentBase/$_period/loans/$_loan/risk-review',
        {
          'expected_book_id': _book!.bookId,
          'source_digest': c['source_digest'],
          'confirm': true,
          'review': inputs,
        },
        (v) => validateCurrentRiskReceipt(v, c, inputs),
        (v) {
          _clearEvidence();
          _notice =
              'Credit-risk review retained: ${v['review_id']}. Load the cutoff candidate to continue.';
        },
        details: {..._riskFacts(c), ...inputs},
        notice:
            'No financial journal is posted. Reload the cutoff candidate after retaining this dated risk review.',
      ),
    );
  }

  Future<void> _loadCash(String applicationId) async {
    accountingCheck(_can('accounting.period.close.prepare'));
    final generation = _generation;
    setState(() => _busy = true);
    try {
      await _freshBook(generation);
      if (!_current(generation)) return;
      final v = await _read(
        '$elapsedAssessmentBase/$_period/loans/$_loan/impaired-cash/$applicationId',
      );
      if (!_current(generation)) return;
      final c = validateImpairedCashCandidate(
        v,
        bookId: _book!.bookId!,
        periodId: _period,
        loanId: _loan,
        applicationId: applicationId,
      );
      setState(() {
        _cashReview = c;
        _inputs = _draft();
        _busy = false;
        _error = null;
        _formVersion++;
      });
    } on Object catch (error) {
      if (_current(generation)) _failure(error);
    }
  }

  Map<String, dynamic> _cashFacts(Map<String, dynamic> c) => {
    'Cash application reference': c['application_id'],
    'Cash measurement date': c['as_of_date'],
    if (c['opening_renewal_review_id'] != null)
      'Opening renewal review': c['opening_renewal_review_id']
    else
      'Opening impaired assessment': c['opening_assessment_id'],
    'Opening cutoff': c['opening_cutoff_date'],
    'Verified gross carrying after cash': c['gross_carrying_amount'],
  };
  void _prepareCash() {
    final c = _cashReview!, inputs = validateImpairedCashInputs(_inputs, c);
    setState(
      () => _review = _Intent(
        'Retain dated impaired-cash measurement',
        'accounting.period.close.prepare',
        '$elapsedAssessmentBase/$_period/loans/$_loan/impaired-cash/${c['application_id']}/review',
        {
          'expected_book_id': _book!.bookId,
          'source_digest': c['source_digest'],
          ...inputs,
          'confirm': true,
        },
        (v) {
          final p = validateImpairedCashReview(
            v,
            bookId: _book!.bookId!,
            periodId: _period,
            loanId: _loan,
            applicationId: c['application_id'] as String,
            candidate: c,
          );
          accountingCheck(
            canonicalTreasury(p['review_inputs']) == canonicalTreasury(inputs),
            'The returned cash-date measurement inputs differ from the reviewed request.',
          );
        },
        (v) {
          _clearEvidence();
          _notice =
              'Cash-date measurement retained: ${v['review_id']}. Load the cutoff candidate to continue.';
          _retainedMeasurement = validateImpairedCashReview(
            v,
            bookId: _book!.bookId!,
            periodId: _period,
            loanId: _loan,
            applicationId: c['application_id'] as String,
            candidate: c,
          );
        },
        reviewInputs: inputs,
        details: _cashFacts(c),
        notice:
            'This retains measurement evidence only. No cash or allowance journal is posted. Reload the fiscal candidate for its separate assessment.',
      ),
    );
  }

  List<Widget> _cashMeasurementFacts(Map<String, dynamic> c) => _facts({
    'Retained measurement reference': c['review_id'],
    'Cash measurement date': c['as_of_date'],
    'Calculated at': c['calculated_at'],
    'Verified gross carrying': c['gross_carrying_amount'],
    'Expected cash present value': c['expected_cash_present_value'],
    'Unrounded weighted expected cash present value':
        c['weighted_expected_cash_present_value_raw'],
    'Currency rounding adjustment': c['currency_rounding_adjustment'],
    'Expected credit loss': c['ecl_amount'],
  });
  List<Widget> _impairedFacts(Map<String, dynamic> p) {
    if (p['credit_impaired_interest'] == null) return [];
    final v = accountingObject(p['credit_impaired_interest']);
    return _facts({
      'Interest basis': v['basis'] == 'gross_before_initial_impaired_cutoff'
          ? 'Gross interest before initial impaired cutoff'
          : 'Original EIR on reviewed net carrying',
      'Impairment measurement boundary': v['impairment_boundary_date'],
      if (v['opening_renewal_review_id'] != null) ...{
        'Opening renewal review': v['opening_renewal_review_id'],
        'Opening cutoff': v['opening_cutoff_date'],
      } else if (v['opening_assessment_id'] != null) ...{
        'Opening assessment reference': v['opening_assessment_id'],
        'Opening cutoff': v['opening_cutoff_date'],
      },
      'Period gross interest': v['gross_interest'],
      'Period net interest revenue': v['net_interest'],
      'Gross/net allowance reconciliation': v['allowance_unwind'],
      if (v.containsKey('currency_rounding_adjustment'))
        'Interest currency rounding adjustment':
            v['currency_rounding_adjustment'],
    });
  }

  List<Widget> _inputReview(Map<String, dynamic> inputs) {
    if (inputs['renewal_review_id'] != null) {
      return [
        ..._facts({
          'Exact posted renewal review': inputs['renewal_review_id'],
          'Renewal settlement rationale': inputs['review_rationale'],
        }),
        const Text(
          'Zero old-segment exposure is proved by the retained renewal completion. The new operational loan is assessed separately. No cash is recorded.',
        ),
      ];
    }
    if (inputs['payoff_review_id'] != null) {
      return [
        ..._facts({
          'Exact posted payoff review': inputs['payoff_review_id'],
          'Settlement review rationale': inputs['review_rationale'],
        }),
        const Text(
          'Zero carrying amount and no remaining contractual claim are proved by the posted payoff. The assessment releases the retained allowance without recording cash.',
        ),
      ];
    }
    final retained = inputs['credit_risk_review_id'] != null;
    final cash = _cashReview != null;
    final risk = cash
        ? <String, dynamic>{}
        : accountingObject(
            retained
                ? _candidate!['eligible_credit_risk_review']
                : inputs['risk_review'],
          );
    return [
      ..._facts(
        cash
            ? {
                'Cash measurement date': _cashReview!['as_of_date'],
                'Measurement rationale': inputs['review_rationale'],
              }
            : {
                'Economic cutoff': risk['as_of_date'],
                'Risk evidence': risk['evidence_reference'],
                if (!retained) 'Risk rationale': risk['review_note'],
                if (retained) ...{
                  'Retained credit-risk review':
                      inputs['credit_risk_review_id'],
                  'Treatment': _riskLabel(risk),
                  'Retained default label': risk['default_label'],
                  'Retained recovery label': risk['recovery_label'],
                  'Retained write-off support label':
                      risk['write_off_label'] ?? 'Not provided',
                },
                'Assessment rationale': inputs['review_rationale'],
              },
      ),
      for (final s in accountingRows(inputs['scenarios'])) ...[
        Text(
          s['scenario_key'] as String,
          style: Theme.of(context).textTheme.titleMedium,
        ),
        ..._facts({
          'Probability': s['probability'],
          'Forecast reference': s['evidence_reference'],
          'Rationale': s['management_rationale'],
          'Retained evidence references': (s['forward_evidence_ids'] as List)
              .join(', '),
        }),
        if ((s['expected_cash_flows'] as List).isEmpty)
          const Text('No expected receipts in this scenario.'),
        for (final f in accountingRows(s['expected_cash_flows']))
          Text('${f['cash_date']}: ${f['amount']}'),
      ],
    ];
  }

  List<Widget> _form() {
    final scenarios = _inputs['scenarios'] as List<Map<String, dynamic>>;
    final risk = _candidate!['eligible_credit_risk_review'] == null
        ? null
        : accountingObject(_candidate!['eligible_credit_risk_review']);
    return [
      if (_cashReview != null) ...[
        const Text('Dated expected receipts after actual cash'),
        const Text(
          'Supply forecast evidence valid on the cash measurement date. This retains measurement evidence only; fiscal assessment recognizes the resulting interest and allowance changes.',
        ),
      ] else if (risk != null) ...[
        const Text('Retained credit-risk review at the cutoff'),
        ..._facts({
          'Risk evidence': risk['evidence_reference'],
          'Evidence basis': risk['primary_evidence_basis'],
          'Review recorded at': risk['reviewed_at'],
          'Retained default label': risk['default_label'],
          'Retained recovery label': risk['recovery_label'],
          'Retained write-off support label':
              risk['write_off_label'] ?? 'Not provided',
        }),
        const Text(
          'Select the exact dated review explicitly. A current label cannot replace evidence for another cutoff.',
        ),
        DropdownButtonFormField<int>(
          key: const Key('elapsed-risk-review'),
          initialValue: _inputs['credit_risk_review_id'] as int?,
          decoration: const InputDecoration(
            labelText: 'Retained credit-risk review',
          ),
          items: [
            DropdownMenuItem(
              value: risk['id'] as int,
              child: Text(
                '${_riskLabel(risk)} · ${risk['evidence_reference']}',
              ),
            ),
          ],
          onChanged: _busy ? null : (v) => _inputs['credit_risk_review_id'] = v,
        ),
      ] else ...[
        const Text('Risk review at the cutoff'),
        const Text(
          'This bounded policy supports stage 1, nondefault loans with no write-off or recovery, based on contractual days past due. Supply evidence valid at the economic cutoff.',
        ),
        for (final field in <(String, String)>[
          ('evidence_reference', 'Risk evidence reference'),
          ('review_note', 'Risk review rationale (20–2000 characters)'),
        ])
          _field(
            'elapsed-${field.$1}',
            field.$2,
            _inputs[field.$1] as String,
            (v) => _inputs[field.$1] = v,
          ),
      ],
      const Text('Expected receipt scenarios'),
      const Text(
        'Enter probabilities as decimals totalling exactly 1. Select retained forecast evidence by its reference. Historical eligibility is checked against the cutoff, independently of its current listing status. Removing all receipts explicitly forecasts no cash receipts.',
      ),
      Row(
        children: [
          if (_evidenceOffset > 0)
            Expanded(
              child: _button(
                'elapsed-evidence-prev',
                'Previous evidence',
                () async => _pageEvidence(_evidenceOffset - 100),
              ),
            ),
          if (_evidence.length == 100)
            Expanded(
              child: _button(
                'elapsed-evidence-next',
                'More evidence',
                () async => _pageEvidence(_evidenceOffset + 100),
              ),
            ),
        ],
      ),
      for (var i = 0; i < scenarios.length; i++)
        ..._scenarioFields(scenarios, i),
      if (scenarios.length < 20)
        _button('elapsed-add-scenario', 'Add scenario', () async {
          setState(() {
            _formVersion++;
            scenarios.add(_scenario());
          });
        }),
      _field(
        'elapsed-review_rationale',
        'Overall assessment rationale (20–2000 characters)',
        _inputs['review_rationale'] as String,
        (v) => _inputs['review_rationale'] = v,
      ),
      _button(
        'elapsed-prepare',
        'Review calculation inputs',
        () async => _prepare(),
      ),
    ];
  }

  List<Widget> _scenarioFields(List<Map<String, dynamic>> scenarios, int i) {
    final s = scenarios[i],
        receipts = s['expected_cash_flows'] as List<Map<String, dynamic>>,
        ids = s['forward_evidence_ids'] as List<String>;
    return [
      const Divider(),
      Text('Scenario ${i + 1}', style: Theme.of(context).textTheme.titleMedium),
      for (final field in <(String, String)>[
        ('scenario_key', 'Scenario name'),
        ('probability', 'Probability (0–1)'),
        ('evidence_reference', 'Forecast evidence reference'),
        ('management_rationale', 'Scenario rationale (20–2000 characters)'),
      ])
        _field(
          'elapsed-s$i-${field.$1}',
          field.$2,
          s[field.$1] as String,
          (v) => s[field.$1] = v,
        ),
      DropdownButton<String>(
        key: Key('elapsed-s$i-evidence'),
        isExpanded: true,
        value: null,
        hint: const Text('Add retained forecast evidence'),
        items: _evidence
            .where((e) => !ids.contains(e['id']))
            .map(
              (e) => DropdownMenuItem(
                value: e['id'] as String,
                child: Text(
                  '${e['source_name']} · ${e['source_reference']}',
                  overflow: TextOverflow.ellipsis,
                ),
              ),
            )
            .toList(),
        onChanged: _busy
            ? null
            : (v) {
                if (v != null) setState(() => ids.add(v));
              },
      ),
      for (final evidenceId in ids) ...[
        Text(
          '${_evidenceSeen[evidenceId]?['source_reference'] ?? evidenceId} · Effective ${_evidenceSeen[evidenceId]?['effective_date'] ?? 'retained'} · Forecast through ${_evidenceSeen[evidenceId]?['forecast_period_end'] ?? 'retained'}',
        ),
        _button(
          'elapsed-s$i-remove-$evidenceId',
          'Remove forecast evidence',
          () async {
            setState(() => ids.remove(evidenceId));
          },
        ),
      ],
      for (var j = 0; j < receipts.length; j++) ...[
        _field(
          'elapsed-s$i-c$j-date',
          'Expected receipt date (YYYY-MM-DD)',
          receipts[j]['cash_date'] as String,
          (v) => receipts[j]['cash_date'] = v,
        ),
        _field(
          'elapsed-s$i-c$j-amount',
          'Expected receipt amount (two decimals)',
          receipts[j]['amount'] as String,
          (v) => receipts[j]['amount'] = v,
        ),
        _button('elapsed-s$i-remove-c$j', 'Remove receipt', () async {
          setState(() {
            _formVersion++;
            receipts.removeAt(j);
          });
        }),
      ],
      _button('elapsed-s$i-add-cash', 'Add expected receipt', () async {
        setState(() {
          _formVersion++;
          receipts.add({'cash_date': '', 'amount': ''});
        });
      }),
      if (scenarios.length > 2)
        _button('elapsed-remove-s$i', 'Remove scenario', () async {
          setState(() {
            _formVersion++;
            scenarios.removeAt(i);
          });
        }),
    ];
  }

  List<Widget> _candidateContent() {
    final c = _candidate!;
    if (c['ready'] != true) {
      return [
        Text(
          'Additional accounting support is required: ${(c['blockers'] as List).map((b) => b.toString().replaceAll('_', ' ')).join('; ')}',
          key: const Key('elapsed-blocked'),
        ),
      ];
    }
    final eir = accountingObject(c['eir']);
    return [
      ..._facts({
        'Economic cutoff': c['as_of_date'],
        'Gross carrying amount': c['gross_carrying_amount'],
        'Interest already recognized': eir['prior_recognized_interest'],
        c['credit_impaired_interest'] != null
                ? 'Unposted gross interest tail'
                : 'Additional interest':
            eir['incremental_interest'],
        'Prior allowance': c['prior_allowance'],
        'Contractual days past due': c['days_past_due'],
      }),
      ..._impairedFacts(c),
      if (_prepared != null) ...[
        ..._preparationFacts(_prepared!),
        if (c['current_confirmation'] == true)
          const Text(
            'Current confirmed assessment matches the source evidence.',
          )
        else if (_can('accounting.period.close.post'))
          _button(
            'elapsed-post',
            'Review posting confirmation',
            () async => _post(),
          )
        else
          const Text('Posting permission is required.'),
      ] else if (_can('accounting.period.close.prepare')) ...[
        if (c['settled_by_exact_payoff'] == true) ...[
          const Text(
            'Exact posted payoff proves zero carrying amount and no remaining contractual claim. The server derives zero expected credit loss and releases only the retained allowance. No receipt forecast is needed.',
          ),
          ..._facts({'Payoff review reference': c['payoff_review_id']}),
          _field(
            'elapsed-settled-rationale',
            'Settlement review rationale (20–2000 characters)',
            _inputs['review_rationale'] as String,
            (v) => _inputs['review_rationale'] = v,
            max: 2000,
          ),
          _button(
            'elapsed-prepare-settled',
            'Review settled payoff assessment',
            () async => _prepareSettled(),
          ),
        ] else if (c['settled_by_exact_renewal'] == true) ...[
          const Text(
            'Zero old-segment exposure is proved by the retained renewal completion. The new operational loan retains its own accounting assessment.',
          ),
          ..._facts({'Renewal review reference': c['renewal_review_id']}),
          _field(
            'elapsed-renewed-rationale',
            'Renewal settlement rationale (20–2000 characters)',
            _inputs['review_rationale'] as String,
            (v) => _inputs['review_rationale'] = v,
          ),
          _button(
            'elapsed-prepare-renewed',
            'Review renewed loan zero assessment',
            () async => _prepareSettled(renewed: true),
          ),
        ] else
          ..._form(),
      ] else
        const Text('Assessment preparation permission is required.'),
    ];
  }

  List<Widget> _riskForm() {
    final c = _riskContext!;
    return [
      const Text('Current-cutoff credit-risk review'),
      ..._facts(_riskFacts(c)),
      if (c['prior_review'] == null && c['inherited_review'] != null)
        Text(
          c['inherited_review']['stage_label'] == 'stage_3_credit_impaired'
              ? 'Impairment continues from the predecessor. A cure requires an explicit current review and supporting evidence.'
              : 'The predecessor credit-risk history continues. Retain an explicit current review with supporting evidence to update the labels.',
        ),
      if (c['ready'] != true)
        Text((c['blockers'] as List).join('; '))
      else ...[
        const Text(
          'The server permits this review only on the actual Manila cutoff date. Select every label explicitly and supply dated supporting evidence. No financial journal is posted.',
        ),
        for (final row in <(String, String, List<String>)>[
          ('stage_label', 'Stage', currentRiskStages),
          ('default_label', 'Default label', ['false', 'true']),
          ('write_off_label', 'Write-off label', currentRiskWriteOffs),
          ('recovery_label', 'Recovery label', currentRiskRecoveries),
          (
            'primary_evidence_basis',
            'Primary evidence basis',
            currentRiskBases,
          ),
          (
            'sicr_backstop_rebutted',
            'SICR backstop rebutted',
            ['false', 'true'],
          ),
          (
            'default_backstop_rebutted',
            'Default backstop rebutted',
            ['false', 'true'],
          ),
        ])
          DropdownButtonFormField<String>(
            key: Key('elapsed-current-risk-${row.$1}'),
            initialValue: _riskInputs[row.$1]?.toString(),
            isExpanded: true,
            decoration: InputDecoration(labelText: row.$2),
            items: row.$3
                .map(
                  (v) => DropdownMenuItem(
                    value: v,
                    child: Text(
                      v.replaceAll('_', ' '),
                      overflow: TextOverflow.ellipsis,
                    ),
                  ),
                )
                .toList(),
            onChanged: _busy
                ? null
                : (v) => _riskInputs[row.$1] =
                      [
                        'default_label',
                        'sicr_backstop_rebutted',
                        'default_backstop_rebutted',
                      ].contains(row.$1)
                      ? (v == null ? null : v == 'true')
                      : v,
          ),
        for (final row in <(String, String)>[
          ('evidence_reference', 'Evidence reference'),
          ('review_note', 'Review rationale'),
          (
            'rebuttal_evidence_reference',
            'Separate rebuttal evidence, if applicable',
          ),
          ('rebuttal_note', 'Separate rebuttal rationale, if applicable'),
          (
            'write_off_evidence_reference',
            'Separate write-off evidence, if applicable',
          ),
          ('write_off_note', 'Separate write-off rationale, if applicable'),
          (
            'recovery_transaction_id',
            'Protected recovery transaction ID, if applicable',
          ),
        ])
          _field(
            'elapsed-current-risk-${row.$1}',
            row.$2,
            (_riskInputs[row.$1] ?? '') as String,
            (v) => _riskInputs[row.$1] = v,
            max: row.$1.endsWith('note') ? 1200 : 300,
          ),
        _button(
          'elapsed-current-risk-review',
          'Review credit-risk labels',
          () async => _prepareRiskReview(),
        ),
      ],
      _button('elapsed-risk-back', 'Back to fiscal assessment', () async {
        setState(() {
          _riskContext = null;
          _riskInputs = {};
        });
      }),
    ];
  }

  List<Widget> _cashRows() => [
    if (_can('accounting.period.close.prepare'))
      for (final c in accountingRows(_candidate!['impaired_cash_reviews'])) ...[
        ..._facts(_cashFacts(c)),
        if (c['current_confirmation'] == true)
          const Text('Current retained measurement matches this cash event.'),
        _button(
          'elapsed-cash-${c['application_id']}',
          'Review cash-date expected receipts',
          () async => _loadCash(c['application_id'] as String),
        ),
      ],
  ];

  @override
  Widget build(BuildContext context) {
    final shown = _pending ?? _review;
    return Scaffold(
      appBar: AppBar(title: const Text('Historical loan assessment')),
      body: ListView(
        key: ValueKey(
          'elapsed-$_generation-$_formVersion-${shown != null}-${_prepared != null}',
        ),
        padding: const EdgeInsets.all(16),
        children: [
          if (_busy) const LinearProgressIndicator(),
          if (_error != null) Text(_error!, key: const Key('elapsed-error')),
          if (_notice != null) Text(_notice!, key: const Key('elapsed-notice')),
          if (_retainedMeasurement != null)
            ..._cashMeasurementFacts(_retainedMeasurement!),
          if (_book != null) Text('Accounting book: ${_book!.entityLabel}'),
          if (_denied)
            const Text('Reopen with current Management accounting access.')
          else if (_posting != null) ...[
            Text('Assessment posted. Retained posting reference: $_posting'),
            const Text(
              'Reload the cutoff candidate to check whether its evidence remains current.',
            ),
            _button('elapsed-reload', 'Reload candidate', _lookup),
          ] else if (shown != null) ...[
            Text(shown.title, style: Theme.of(context).textTheme.titleLarge),
            if (shown.reviewInputs != null)
              ..._inputReview(shown.reviewInputs!),
            if (shown.prepared != null) ..._preparationFacts(shown.prepared!),
            if (shown.details != null) ..._facts(shown.details!),
            Text(
              shown.notice ??
                  (shown.prepared == null
                      ? 'This retains a calculation now for the stated historical cutoff. It does not post the journals.'
                      : 'This posts the reviewed incremental interest and allowance change atomically. No cash is recorded.'),
            ),
            if (_pending != null) ...[
              const Text(
                'The result is unconfirmed. Retry the unchanged request to recover it.',
              ),
              _button('elapsed-retry', 'Retry unchanged request', _send),
              if (_rejected)
                _button(
                  'elapsed-discard',
                  'Discard rejected request and reload',
                  () async {
                    _clearEvidence();
                    await _lookup();
                  },
                ),
            ] else ...[
              _button('elapsed-confirm', 'Confirm: ${shown.title}', _send),
              _button('elapsed-cancel', 'Cancel', () async {
                setState(() => _review = null);
              }),
            ],
          ] else if (_riskContext != null)
            ..._riskForm()
          else if (_cashReview != null) ...[
            ..._facts(_cashFacts(_cashReview!)),
            if (_cashReview!['review'] != null)
              ..._cashMeasurementFacts(
                accountingObject(_cashReview!['review']),
              ),
            if (_cashReview!['ready'] == true)
              ..._form()
            else
              Text((_cashReview!['blockers'] as List).join('; ')),
            _button('elapsed-cash-back', 'Back to fiscal assessment', () async {
              setState(() {
                _cashReview = null;
                _inputs = _draft();
                _formVersion++;
              });
            }),
          ] else if (_book != null) ...[
            const Text(
              'Supported Regular loan sources include exact original releases, chronological payments and reviewed posted payoffs. Unsupported states remain blocked. This assessment does not establish complete period coverage.',
            ),
            DropdownButtonFormField<String>(
              key: const Key('elapsed-period'),
              initialValue: _period.isEmpty ? null : _period,
              decoration: const InputDecoration(labelText: 'Fiscal period'),
              items: _periods
                  .map(
                    (p) => DropdownMenuItem(
                      value: p['period_id'] as String,
                      child: Text(p['label'] as String),
                    ),
                  )
                  .toList(),
              onChanged: _busy
                  ? null
                  : (v) {
                      setState(() {
                        _period = v ?? '';
                        _clearEvidence();
                      });
                    },
            ),
            _field('elapsed-loan', 'Loan ID', _loan, (v) {
              if (_candidate != null) {
                setState(() {
                  _loan = v.trim();
                  _clearEvidence();
                });
              } else {
                _loan = v.trim();
              }
            }, max: 36),
            _button('elapsed-lookup', 'Load cutoff candidate', _lookup),
            if (_candidate != null) ...[
              ..._candidateContent(),
              ..._cashRows(),
              if (_can('accounting.ecl.credit_risk_label.review'))
                _button(
                  'elapsed-current-risk',
                  'Review current-cutoff credit-risk labels',
                  _loadRisk,
                ),
            ],
          ],
        ],
      ),
    );
  }
}
