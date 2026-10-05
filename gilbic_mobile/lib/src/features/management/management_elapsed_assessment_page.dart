import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:gilbic_mobile/src/core/auth/app_role.dart';
import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/device/device_identity.dart';
import 'package:gilbic_mobile/src/core/management/accounting_readiness_repository.dart';
import 'package:gilbic_mobile/src/core/management/elapsed_assessment_evidence.dart';
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
  }) : body = accountingObject(immutableTreasury(body));
  final String title, permission, path;
  final Map<String, dynamic> body;
  final Map<String, dynamic>? reviewInputs, prepared;
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
  String? _error, _posting;
  bool _busy = true, _denied = false, _rejected = false;
  int _generation = 0, _evidenceOffset = 0, _formVersion = 0;
  AccountingBookIdentity? _book;
  List<Map<String, dynamic>> _periods = [], _evidence = [];
  final Map<String, Map<String, dynamic>> _evidenceSeen = {};
  Map<String, dynamic>? _candidate, _prepared;
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
    final inputs = validateElapsedInputs(
      _inputs,
      _candidate!['as_of_date'] as String,
    );
    final body = {
      'expected_book_id': _book!.bookId,
      'source_digest': _candidate!['source_digest'],
      ...inputs,
    };
    setState(
      () => _review = _Intent(
        'Retain historical calculation',
        'accounting.period.close.prepare',
        '$elapsedAssessmentBase/$_period/loans/$_loan/prepare',
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
    ..._facts({
      'Economic cutoff': p['as_of_date'],
      'Calculated at (actual timestamp)': p['calculated_at'],
      'Interest to recognize': p['incremental_interest'],
      'Cumulative interest': p['cumulative_interest'],
      'Expected credit loss': p['ecl_amount'],
      'Prior allowance': p['prior_allowance'],
      'Allowance change': p['allowance_delta'],
      'Scenarios': p['scenario_count'],
      'Preparation reference': p['preparation_id'],
    }),
  ];
  List<Widget> _inputReview(Map<String, dynamic> inputs) {
    final risk = accountingObject(inputs['risk_review']);
    return [
      ..._facts({
        'Economic cutoff': risk['as_of_date'],
        'Risk evidence': risk['evidence_reference'],
        'Risk rationale': risk['review_note'],
        'Assessment rationale': inputs['review_rationale'],
      }),
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
    return [
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
        'Additional interest': eir['incremental_interest'],
        'Prior allowance': c['prior_allowance'],
        'Contractual days past due': c['days_past_due'],
      }),
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
      ] else if (_can('accounting.period.close.prepare'))
        ..._form()
      else
        const Text('Assessment preparation permission is required.'),
    ];
  }

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
            Text(
              shown.prepared == null
                  ? 'This retains a calculation now for the stated historical cutoff. It does not post the journals.'
                  : 'This posts the reviewed incremental interest and allowance change atomically. No cash is recorded.',
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
          ] else if (_book != null) ...[
            const Text(
              'Ordinary active Regular loans with exact original release evidence and no earlier cash collections are supported. Unsupported states remain blocked. This assessment does not establish complete period coverage.',
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
            if (_candidate != null) ..._candidateContent(),
          ],
        ],
      ),
    );
  }
}
