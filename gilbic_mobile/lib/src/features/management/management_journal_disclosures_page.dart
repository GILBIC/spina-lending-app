import 'dart:convert';
import 'dart:math';
import 'package:flutter/material.dart';
import 'package:gilbic_mobile/src/core/auth/app_role.dart';
import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/device/device_identity.dart';
import 'package:gilbic_mobile/src/core/management/journal_disclosure_evidence.dart';
import 'package:gilbic_mobile/src/core/management/source_accounting_repository.dart';
import 'package:gilbic_mobile/src/core/network/spina_api.dart';
import 'package:gilbic_mobile/src/core/treasury/treasury_models.dart';
import 'package:gilbic_mobile/src/features/management/journal_disclosure_card.dart';

class ManagementJournalDisclosuresPage extends StatefulWidget {
  const ManagementJournalDisclosuresPage({
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
  State<ManagementJournalDisclosuresPage> createState() =>
      _JournalDisclosuresState();
}

class _JournalDisclosuresState extends State<ManagementJournalDisclosuresPage> {
  late SourceAccountingRepository _repository;
  late String _scope;
  int _generation = 0;
  bool _busy = true, _denied = false, _editingPolicy = false;
  String _device = '',
      _periodId = '',
      _debit = '',
      _credit = '',
      _category = '';
  String? _error, _pendingPath, _resultKey;
  Map<String, dynamic>? _report, _journal, _review, _pending;
  List<Map<String, dynamic>> _periods = [], _components = [];
  final _financing = <String>{};
  final _fields = <String, TextEditingController>{
    for (final key in [
      'reason',
      'reference',
      'digest',
      'part-amount',
      'part-reference',
      'part-digest',
    ])
      key: TextEditingController(),
  };
  String _scopeOf(UserSession user) => jsonEncode([
    user.userId,
    user.accessToken,
    user.rawRole,
    user.roles,
    user.permissions,
  ]);
  bool get _canRead =>
      widget.session.hasRole(AppRole.management) &&
      widget.session.hasPermission('accounting.view');
  bool get _canManage =>
      _canRead && widget.session.hasPermission('accounting.journal.manage');
  bool _current(int version) =>
      mounted && version == _generation && _scope == _scopeOf(widget.session);
  @override
  void initState() {
    super.initState();
    _repository = widget.repository ?? SpinaSourceAccountingRepository();
    _scope = _scopeOf(widget.session);
    _load();
  }

  @override
  void didUpdateWidget(covariant ManagementJournalDisclosuresPage oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (_scope != _scopeOf(widget.session) ||
        oldWidget.repository != widget.repository ||
        oldWidget.deviceIdentityProvider != widget.deviceIdentityProvider) {
      _generation++;
      _clear();
      _scope = _scopeOf(widget.session);
      _repository = widget.repository ?? SpinaSourceAccountingRepository();
      _denied = false;
      _load();
    }
  }

  void _clear() {
    _report = _journal = _review = _pending = null;
    _pendingPath = _resultKey = null;
    _periods = [];
    _components = [];
    _financing.clear();
    _device = _periodId = _debit = _credit = _category = '';
    _editingPolicy = false;
    for (final controller in _fields.values) {
      controller.clear();
    }
  }

  @override
  void dispose() {
    _generation++;
    for (final controller in _fields.values) {
      controller.dispose();
    }
    super.dispose();
  }

  Future<Map<String, dynamic>> _read(String suffix) => _repository.read(
    widget.session,
    deviceId: _device,
    path: '$sourceAccountingBase$suffix',
  );
  void _failure(Object error) {
    if (!mounted) return;
    setState(() {
      _busy = false;
      _error = error is FormatException
          ? error.message
          : error is SpinaApiException
          ? error.message
          : 'Disclosure evidence could not be confirmed. Retry the unchanged request if submitted.';
      if (error is SpinaApiException &&
          [401, 403, 426].contains(error.statusCode)) {
        _generation++;
        _clear();
        _denied = true;
      }
    });
  }

  Future<void> _load() async {
    final version = ++_generation;
    if (!_canRead) {
      setState(() {
        _clear();
        _busy = false;
        _denied = true;
      });
      return;
    }
    setState(() {
      _busy = true;
      _error = null;
      _journal = _review = null;
      _editingPolicy = false;
    });
    try {
      final identity = await widget.deviceIdentityProvider.load();
      if (!_current(version)) return;
      _device = identity.installationId;
      if (_periods.isEmpty) {
        final data = await _read('');
        if (!_current(version)) return;
        _periods = accountingRows(data['fiscal_periods']);
      }
      if (_periods.isEmpty) {
        setState(() => _busy = false);
        return;
      }
      _periodId = _periodId.isEmpty
          ? _periods.first['period_id'] as String
          : _periodId;
      final data = await _read(
        '/statements/disclosures?period_id=${Uri.encodeComponent(_periodId)}',
      );
      if (!_current(version)) return;
      final report = validateJournalDisclosures(
        accountingObject(data['disclosures']),
      );
      accountingCheck(
        accountingObject(report['period'])['id'] == _periodId,
        'Disclosure report does not match the selected period.',
      );
      setState(() {
        _report = report;
        _busy = false;
      });
    } on Object catch (error) {
      if (_current(version)) _failure(error);
    }
  }

  void _act(VoidCallback action) {
    if (_busy || _denied || !mounted) return;
    if (_scope != _scopeOf(widget.session) || !_canManage) {
      setState(() {
        _generation++;
        _clear();
        _denied = true;
      });
      return;
    }
    try {
      action();
    } on Object catch (error) {
      _failure(error);
    }
  }

  String _value(String key) => _fields[key]!.text.trim();
  Map<String, dynamic> _evidence() {
    final reference = _value('reference'), digest = _value('digest');
    accountingCheck(
      reference.isNotEmpty && accountingDigest(digest),
      'Retain an evidence reference and SHA-256 fingerprint.',
    );
    return {
      'evidence_reference': reference,
      'evidence_digest': digest,
      'reviewed': true,
    };
  }

  void _editJournal(Map<String, dynamic> journal) {
    setState(() {
      _journal = journal;
      _components = journal['components'] == null
          ? []
          : accountingRows(
              journal['components'],
            ).map((row) => Map<String, dynamic>.from(row)).toList();
      _review = null;
      _error = null;
      _editingPolicy = false;
      _debit = _credit = _category = '';
      for (final field in _fields.values) {
        field.clear();
      }
      _fields['reason']!.text = journal['reason'] as String? ?? '';
    });
  }

  void _policyForm() {
    setState(() {
      _editingPolicy = true;
      _journal = _review = null;
      _error = null;
      _financing.clear();
      final policy = _report!['policy'];
      if (policy != null) {
        _financing.addAll(
          (accountingObject(policy)['financing_account_codes'] as List)
              .cast<String>(),
        );
      }
      _fields['reference']!.clear();
      _fields['digest']!.clear();
    });
  }

  void _addPart() {
    final part = <String, dynamic>{
      'debit_line_id': _debit,
      'credit_line_id': _credit,
      'classification': _category,
      'amount': TreasuryMoney(_value('part-amount'), positive: true).text,
      'evidence_reference': _value('part-reference'),
      'evidence_digest': _value('part-digest'),
    };
    accountingCheck(
      _debit.isNotEmpty &&
          _credit.isNotEmpty &&
          journalDisclosureLabels.containsKey(_category) &&
          (part['evidence_reference'] as String).isNotEmpty &&
          accountingDigest(part['evidence_digest']),
      'Choose debit, credit, disclosure and retained evidence.',
    );
    final remaining = journalDisclosureRemaining(
      accountingRows(_journal!['lines']),
      [..._components, part],
    );
    accountingCheck(
      remaining.values.every((amount) => !amount.startsWith('-')),
      'This portion exceeds a remaining line amount.',
    );
    setState(() {
      _components.add(part);
      _fields['part-amount']!.clear();
      _error = null;
    });
  }

  void _prepareReview() {
    FocusScope.of(context).unfocus();
    final body = <String, dynamic>{
      'request_id': (widget.uuidGenerator ?? _uuid)(),
      'book_id': _report!['book_id'],
      ..._evidence(),
    };
    if (_editingPolicy) {
      final policy = _report!['policy'];
      body.addAll({
        'reporting_policy_id': _report!['reporting_policy_id'],
        'expected_version': policy == null
            ? 0
            : accountingObject(policy)['version'],
        'financing_account_codes': _financing.toList()..sort(),
      });
    } else {
      final reason = _value('reason');
      accountingCheck(
        reason.isNotEmpty,
        'Retain the reason for this disclosure.',
      );
      final parts = journalDisclosureComponents(
        accountingRows(_journal!['lines']),
        _components,
        _report!['cash_account_codes'] as List,
      );
      body.addAll({
        'disclosure_policy_id': accountingObject(_report!['policy'])['id'],
        'journal_entry_id': _journal!['journal_entry_id'],
        'expected_version': _journal!['review_version'],
        'source_digest': _journal!['source_digest'],
        'components': parts,
        'reason': reason,
      });
    }
    setState(() {
      _review = accountingObject(immutableTreasury(body));
      _error = null;
    });
  }

  Future<void> _save({bool retry = false}) async {
    if (_busy || _denied || !_canManage) return;
    if (_scope != _scopeOf(widget.session)) {
      setState(() {
        _generation++;
        _clear();
        _denied = true;
      });
      return;
    }
    final version = _generation;
    if (!retry) {
      accountingCheck(_pending == null && _review != null);
      _pending = _review;
      _pendingPath = _editingPolicy
          ? '/statements/disclosure-policy'
          : '/statements/disclosure-reviews';
      _resultKey = _editingPolicy ? 'policy_id' : 'review_id';
    }
    if (_pending == null) return;
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      final held = _pending!;
      final data = await _repository.write(
        widget.session,
        deviceId: _device,
        path: '$sourceAccountingBase$_pendingPath',
        body: held,
      );
      if (!_current(version)) return;
      accountingCheck(
        data[_resultKey] == held['request_id'],
        'The saved record could not be verified. Retry the unchanged request.',
      );
      _pending = _review = null;
      await _load();
    } on Object catch (error) {
      if (_current(version)) _failure(error);
    }
  }

  Widget _button(String key, String text, VoidCallback action) => Padding(
    padding: const EdgeInsets.symmetric(vertical: 6),
    child: OutlinedButton(
      key: Key(key),
      onPressed: _busy ? null : action,
      child: Text(text),
    ),
  );
  Widget _input(String key, String label, {int maxLength = 1000}) => Padding(
    padding: const EdgeInsets.symmetric(vertical: 8),
    child: TextField(
      key: Key('disclosure-$key'),
      controller: _fields[key],
      enabled: !_busy && _pending == null,
      maxLength: maxLength,
      decoration: InputDecoration(labelText: label),
    ),
  );
  Widget _choice(
    String key,
    String label,
    String selected,
    List<(String, String)> options,
    void Function(String) update,
  ) => Padding(
    padding: const EdgeInsets.symmetric(vertical: 8),
    child: DropdownButtonFormField<String>(
      key: Key(key),
      initialValue: selected.isEmpty ? null : selected,
      isExpanded: true,
      decoration: InputDecoration(labelText: label),
      items: [
        for (final option in options)
          DropdownMenuItem(
            value: option.$1,
            child: Text(
              option.$2,
              maxLines: 2,
              overflow: TextOverflow.ellipsis,
            ),
          ),
      ],
      onChanged: _busy
          ? null
          : (value) {
              if (value != null) setState(() => update(value));
            },
    ),
  );
  List<Widget> _parts({bool editable = true}) => [
    for (var index = 0; index < _components.length; index++) ...[
      Text(
        '${accountingRows(_journal!['lines']).firstWhere((line) => line['id'] == _components[index]['debit_line_id'])['account_name']} → ${accountingRows(_journal!['lines']).firstWhere((line) => line['id'] == _components[index]['credit_line_id'])['account_name']} · ${journalDisclosureLabels[_components[index]['classification']]} · PHP ${_components[index]['amount']}',
      ),
      Text(_components[index]['evidence_reference'] as String),
      if (editable)
        _button(
          'disclosure-remove-$index',
          'Remove portion',
          () => _act(() => setState(() => _components.removeAt(index))),
        ),
    ],
  ];
  @override
  Widget build(BuildContext context) {
    final report = _report;
    final editable =
        _canManage &&
        report != null &&
        accountingObject(report['period'])['status'] == 'open';
    return Scaffold(
      appBar: AppBar(title: const Text('Cash and noncash disclosures')),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          if (_busy) const LinearProgressIndicator(),
          if (_error != null) Text(_error!, key: const Key('disclosure-error')),
          if (_denied)
            const Text('Current Management accounting access is required.')
          else if (_pending != null) ...[
            const Text(
              'The submitted result has not been confirmed. Recover the unchanged request before another action.',
            ),
            _button(
              'disclosure-retry',
              'Retry unchanged request',
              () => _save(retry: true),
            ),
            _button('disclosure-restart', 'Refresh and start a new review', () {
              _pending = _review = null;
              _load();
            }),
          ] else if (_review != null) ...[
            const Text(
              'Review before retaining',
              style: TextStyle(fontWeight: FontWeight.bold),
            ),
            if (_editingPolicy)
              Text(
                'Financing accounts: ${_financing.isEmpty ? 'None' : _financing.join(', ')}',
              )
            else ...[
              Text(_review!['reason'] as String),
              ..._parts(editable: false),
            ],
            Text('Evidence: ${_review!['evidence_reference']}'),
            const Text(
              'The current book, period, source and review version will be checked when saved.',
            ),
            _button('disclosure-save', 'Retain reviewed evidence', _save),
            _button(
              'disclosure-edit',
              'Back to edit',
              () => setState(() => _review = null),
            ),
          ] else if (_editingPolicy && report != null) ...[
            const Text(
              'Select every liability whose cash flows are financing activities. An empty selection records that none apply.',
            ),
            for (final row in accountingRows(
              report['financing_account_options'],
            ))
              CheckboxListTile(
                title: Text('${row['code']} · ${row['name']}'),
                value: _financing.contains(row['code']),
                onChanged: _busy
                    ? null
                    : (value) => setState(() {
                        if (value == true) {
                          _financing.add(row['code'] as String);
                        } else {
                          _financing.remove(row['code']);
                        }
                      }),
              ),
            _input('reference', 'Retained evidence reference'),
            _input('digest', 'Evidence fingerprint (SHA-256)', maxLength: 64),
            _button(
              'disclosure-review',
              'Review financing policy',
              () => _act(_prepareReview),
            ),
            _button(
              'disclosure-back',
              'Back',
              () => setState(() => _editingPolicy = false),
            ),
          ] else if (_journal != null && report != null) ...[
            Text(
              '${_journal!['entry_number']} · ${_journal!['posting_date']}',
              style: const TextStyle(fontWeight: FontWeight.bold),
            ),
            if (_journal!['reversal_of_entry_id'] != null)
              const Text(
                'This reverses an earlier journal. Review the reversal separately.',
              ),
            for (final line in accountingRows(_journal!['lines']))
              Text(
                '${line['account_code']} · ${line['account_name']} · Debit PHP ${line['debit']} · Credit PHP ${line['credit']} · Remaining PHP ${journalDisclosureRemaining(accountingRows(_journal!['lines']), _components)[line['id']]}',
              ),
            ..._parts(),
            _choice('disclosure-debit', 'Debit account', _debit, [
              for (final line in accountingRows(_journal!['lines']))
                if (line['debit'] != '0.00')
                  (
                    line['id'] as String,
                    '${line['account_code']} · ${line['account_name']}',
                  ),
            ], (value) => _debit = value),
            _choice(
              'disclosure-credit',
              'Credit account',
              _credit,
              [
                for (final line in accountingRows(_journal!['lines']))
                  if (line['credit'] != '0.00')
                    (
                      line['id'] as String,
                      '${line['account_code']} · ${line['account_name']}',
                    ),
              ],
              (value) => _credit = value,
            ),
            _input('part-amount', 'Portion amount (PHP, two decimals)'),
            _choice(
              'disclosure-classification',
              'Disclosure classification',
              _category,
              journalDisclosureLabels.entries
                  .map((entry) => (entry.key, entry.value))
                  .toList(),
              (value) => _category = value,
            ),
            _input('part-reference', 'Portion evidence reference'),
            _input(
              'part-digest',
              'Portion fingerprint (SHA-256)',
              maxLength: 64,
            ),
            _button('disclosure-add', 'Add portion', () => _act(_addPart)),
            _input('reason', 'Reason for this disclosure', maxLength: 4000),
            _input('reference', 'Retained evidence reference'),
            _input('digest', 'Evidence fingerprint (SHA-256)', maxLength: 64),
            _button(
              'disclosure-review',
              'Review complete journal',
              () => _act(_prepareReview),
            ),
            _button(
              'disclosure-back',
              'Back',
              () => setState(() => _journal = null),
            ),
          ] else if (report != null) ...[
            _choice(
              'disclosure-period',
              'Accounting period',
              _periodId,
              [
                for (final row in _periods)
                  (row['period_id'] as String, row['label'] as String),
              ],
              (value) {
                _periodId = value;
                _load();
              },
            ),
            JournalDisclosureCard(disclosures: report),
            if (editable && report['reporting_policy_id'] != null)
              _button(
                'disclosure-policy',
                'Review financing accounts',
                () => _act(_policyForm),
              ),
            for (
              var index = 0;
              index < accountingRows(report['journals']).length;
              index++
            ) ...[
              Text(
                '${accountingRows(report['journals'])[index]['entry_number']} · ${accountingRows(report['journals'])[index]['posting_date']}',
              ),
              if (editable &&
                  report['policy'] != null &&
                  accountingObject(report['policy'])['definition_valid'] ==
                      true &&
                  accountingRows(report['journals'])[index]['protected_kind'] ==
                      null &&
                  accountingRows(report['journals'])[index]['source_status'] ==
                      'current')
                _button(
                  'disclosure-journal-$index',
                  'Review components',
                  () => _act(
                    () =>
                        _editJournal(accountingRows(report['journals'])[index]),
                  ),
                ),
            ],
          ] else if (!_busy) ...[
            const Text('Disclosure evidence is unavailable.'),
            _button('disclosure-reload', 'Reload disclosures', _load),
          ],
        ],
      ),
    );
  }
}

String _uuid() {
  final random = Random.secure();
  final bytes = List<int>.generate(16, (_) => random.nextInt(256));
  bytes[6] = (bytes[6] & 15) | 64;
  bytes[8] = (bytes[8] & 63) | 128;
  final text = bytes
      .map((value) => value.toRadixString(16).padLeft(2, '0'))
      .join();
  return '${text.substring(0, 8)}-${text.substring(8, 12)}-${text.substring(12, 16)}-${text.substring(16, 20)}-${text.substring(20)}';
}
