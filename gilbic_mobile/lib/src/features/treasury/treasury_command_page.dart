import 'package:file_selector/file_selector.dart' as files;
import 'package:flutter/material.dart';
import 'package:gilbic_mobile/src/core/treasury/treasury_models.dart';
import 'package:gilbic_mobile/src/core/treasury/treasury_repository.dart';
import 'package:gilbic_mobile/src/features/treasury/treasury_workspace_page.dart';
import 'package:image_picker/image_picker.dart';

class TreasuryCommandPage extends StatefulWidget {
  const TreasuryCommandPage({
    required this.repository,
    required this.action,
    this.account,
    this.initial = const {},
    this.targetId,
    this.pickEvidence,
    super.key,
  });
  final TreasuryRepository repository;
  final TreasuryAction action;
  final TreasuryAccount? account;
  final Map<String, dynamic> initial;
  final String? targetId;
  final Future<XFile?> Function()? pickEvidence;
  @override
  State<TreasuryCommandPage> createState() => _TreasuryCommandPageState();
}

class _TreasuryCommandPageState extends State<TreasuryCommandPage> {
  final _controllers = <String, TextEditingController>{},
      _values = <String, dynamic>{};
  final _loans = <String>{}, _permissions = <String>{};
  final _observations = <Map<String, TextEditingController>>[];
  final _form = GlobalKey<FormState>();
  Map<String, dynamic>? _preview, _uploadedEvidence;
  TreasuryResult? _result;
  String? _error, _sourceId;
  bool _busy = false, _verified = false, _followup = false;
  int _generation = 0;
  late final String _accountId;
  List<TreasuryField> get _fields => treasuryFields[widget.action]!;
  bool get _locked =>
      _busy ||
      widget.repository.busy ||
      widget.repository.pendingRequestId != null ||
      widget.repository.denied;
  List<Map<String, dynamic>> get _loanChoices =>
      ((widget.initial['loan_choices'] as List?) ?? [])
          .whereType<Map<String, dynamic>>()
          .toList();
  @override
  void initState() {
    super.initState();
    _accountId = widget.account?.id ?? newTreasuryRequestId();
    for (final field in _fields) {
      final value = widget.initial[field.key] ?? field.defaultValue;
      if ([boolKind, choiceKind].contains(field.kind)) {
        _values[field.key] =
            field.kind == boolKind &&
                (field.key == 'confirmed' ||
                    field.key == 'complete_history' ||
                    field.key == 'destination_confirmed' ||
                    field.key == 'private_history')
            ? false
            : value;
      } else if (![
        TreasuryFieldKind.loans,
        TreasuryFieldKind.observations,
        TreasuryFieldKind.permissions,
        TreasuryFieldKind.followup,
      ].contains(field.kind)) {
        _controllers[field.key] = TextEditingController(
          text: value is List ? value.join(', ') : value?.toString() ?? '',
        );
      }
    }
    for (final key in [
      'followup_note',
      'promised_payment_date',
      'promised_amount',
    ]) {
      _controllers[key] = TextEditingController();
    }
    _values['followup_reason'] = 'no_cash';
    if (widget.action == TreasuryAction.receiptApply) {
      _values['mode'] = _loanChoices.length == 1 ? 'single' : null;
    }
  }

  @override
  void dispose() {
    _generation++;
    for (final c in _controllers.values) {
      c.clear();
      c.dispose();
    }
    for (final row in _observations) {
      for (final c in row.values) {
        c.clear();
        c.dispose();
      }
    }
    super.dispose();
  }

  void _changed() {
    setState(() {
      _preview = null;
      _verified = false;
      _result = null;
    });
  }

  Object? _value(TreasuryField f) {
    switch (f.kind) {
      case TreasuryFieldKind.boolean:
      case TreasuryFieldKind.choice:
        return _values[f.key];
      case TreasuryFieldKind.integer:
        return int.tryParse(_controllers[f.key]!.text.trim());
      case TreasuryFieldKind.permissions:
        return _permissions.toList();
      case TreasuryFieldKind.loans:
        return [
          for (final loan in _loanChoices.where(
            (v) => _loans.contains(v['loan_id']),
          ))
            {
              'loan_id': loan['loan_id'],
              'expected_version': loan['expected_version'],
            },
        ];
      case TreasuryFieldKind.observations:
        return [
          for (final row in _observations)
            {
              for (final field in observationFields)
                field.key: row[field.key]!.text,
            },
        ];
      case TreasuryFieldKind.dates:
        final text = _controllers[f.key]!.text.trim();
        return text.isEmpty
            ? <String>[]
            : text.split(',').map((v) => v.trim()).toList();
      case TreasuryFieldKind.ids:
        return _controllers[f.key]!.text
            .split(',')
            .map((v) => v.trim())
            .toList();
      case TreasuryFieldKind.followup:
        return !_followup
            ? null
            : {
                'reason_code': _values['followup_reason'],
                'note': _controllers['followup_note']!.text,
                if (_values['followup_reason'] == 'promised_to_pay_later')
                  'promised_payment_date':
                      _controllers['promised_payment_date']!.text,
                if (_values['followup_reason'] == 'promised_to_pay_later')
                  'promised_amount': _controllers['promised_amount']!.text,
              };
      default:
        return _controllers[f.key]?.text.trim();
    }
  }

  Map<String, dynamic> _draft({bool preview = false}) {
    final fields = <String, dynamic>{};
    for (final f in _fields) {
      if (preview && ['receipt_id', 'digest'].contains(f.key)) continue;
      final parsed = f.parse(_value(f));
      if (parsed != null) fields[f.key] = parsed;
    }
    return fields;
  }

  int get _expectedVersion =>
      [
        TreasuryAction.receiptApply,
        TreasuryAction.receiptApplicationReverse,
      ].contains(widget.action)
      ? widget.initial['expected_version'] as int? ?? 0
      : widget.account?.version ?? 0;
  Future<void> _preparePreview() async {
    if (_locked) return;
    setState(() => _error = null);
    try {
      final body = _draft(preview: true);
      body['expected_version'] = _expectedVersion;
      final receipt = requireTreasuryId(_controllers['receipt_id']!.text);
      setState(() => _busy = true);
      final generation = ++_generation;
      try {
        final value = await widget.repository.preview(receipt, body);
        if (mounted && generation == _generation) {
          setState(() {
            _preview = value;
            _controllers['digest']!.text = value['digest'] as String? ?? '';
            _verified = false;
          });
        }
      } finally {
        if (mounted && generation == _generation) setState(() => _busy = false);
      }
    } catch (error) {
      if (mounted) setState(() => _error = error.toString());
    }
  }

  Future<void> _upload() async {
    if (_locked) return;
    setState(() => _busy = true);
    final g = ++_generation;
    try {
      final file =
          await (widget.pickEvidence ??
              (() => files.openFile(
                acceptedTypeGroups: [
                  const files.XTypeGroup(
                    label: 'Private evidence',
                    extensions: ['pdf', 'png', 'jpg', 'jpeg'],
                    mimeTypes: ['application/pdf', 'image/png', 'image/jpeg'],
                  ),
                ],
              )))();
      if (file == null || !mounted || g != _generation) return;
      final purpose = widget.action == TreasuryAction.openingPrepare
          ? 'opening'
          : widget.action == TreasuryAction.reconciliationObserve
          ? 'statement'
          : widget.action == TreasuryAction.movementCorrect
          ? 'correction'
          : 'recipient';
      final result = await widget.repository.uploadEvidence(
        requestId: newTreasuryRequestId(),
        accountId: _accountId,
        purpose: purpose,
        file: file,
      );
      if (mounted && g == _generation) {
        setState(() {
          if (result.status == 'saved') {
            _uploadedEvidence = treasuryObject(result.result['evidence']);
            _controllers['evidence_id']!.text = result.targetId;
            _error =
                'Private evidence saved. Review the command separately; no funds or loan payment were recorded.';
          } else {
            _error = 'Evidence was blocked by the server.';
          }
          _verified = false;
        });
      }
    } catch (error) {
      if (mounted && g == _generation) {
        setState(() => _error = error.toString());
      }
    } finally {
      if (mounted && g == _generation) setState(() => _busy = false);
    }
  }

  Future<void> _submit() async {
    if (_locked) return;
    try {
      if (!_verified) {
        throw const FormatException(
          'Verify the current account, source and evidence before confirming.',
        );
      }
      if (widget.action == TreasuryAction.receiptApply &&
          _preview?['can_apply'] != true) {
        throw const FormatException(
          'Review a current server allocation with no blockers.',
        );
      }
      final fields = _draft();
      final command = TreasuryCommand(
        widget.action,
        requestId: newTreasuryRequestId(),
        accountId: _accountId,
        expectedVersion: _expectedVersion,
        fields: fields,
      );
      final confirmed = await showDialog<bool>(
        context: context,
        builder: (c) => AlertDialog(
          title: Text('Confirm ${widget.action.label.toLowerCase()}?'),
          content: SingleChildScrollView(
            child: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(widget.account?.alias ?? 'New account'),
                for (final f in _fields.where(
                  (f) => ![
                    TreasuryFieldKind.digest,
                    TreasuryFieldKind.loans,
                    TreasuryFieldKind.observations,
                  ].contains(f.kind),
                ))
                  if (fields[f.key] != null)
                    Text('${f.label}: ${fields[f.key]}'),
                if (widget.action == TreasuryAction.receiptVerify)
                  const Text(
                    'This records received funds. Loan allocation is a separate action.',
                  ),
                if (widget.action == TreasuryAction.disbursementRecord ||
                    widget.action == TreasuryAction.transferRecord)
                  const Text(
                    'This records an actual observed transaction. It does not send money or complete an unverified destination.',
                  ),
                if (widget.action == TreasuryAction.receiptApply)
                  const Text(
                    'Only the exact server allocation shown will be recorded.',
                  ),
              ],
            ),
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(c, false),
              child: const Text('Cancel'),
            ),
            FilledButton(
              onPressed: () => Navigator.pop(c, true),
              child: const Text('Confirm once'),
            ),
          ],
        ),
      );
      if (confirmed != true || !mounted) return;
      setState(() => _busy = true);
      final g = ++_generation;
      try {
        if (_uploadedEvidence != null &&
            fields['evidence_id'] == _uploadedEvidence!['id']) {
          await widget.repository.content(
            evidenceId: _uploadedEvidence!['id'] as String,
            mediaType: _uploadedEvidence!['media_type'] as String,
            digest: _uploadedEvidence!['sha256'] as String,
            byteCount: _uploadedEvidence!['byte_count'] as int,
          );
          if (!mounted || g != _generation) return;
        }
        final result = await widget.repository.execute(
          command,
          targetId: widget.targetId,
        );
        if (mounted && g == _generation) {
          setState(() {
            _result = result;
            _error = result.status == 'saved'
                ? 'Saved result confirmed. ${widget.action == TreasuryAction.receiptVerify ? 'Funds received; loan recording remains separate.' : ''}'
                : 'The server blocked this action. Review its stated reason.';
            _verified = false;
          });
        }
      } catch (error) {
        if (mounted && g == _generation) {
          setState(() {
            _error = error.toString();
            if (widget.repository.denied) {
              for (final c in _controllers.values) {
                c.clear();
              }
              _uploadedEvidence = null;
              _preview = null;
            }
          });
        }
      } finally {
        if (mounted && g == _generation) setState(() => _busy = false);
      }
    } catch (error) {
      if (mounted) setState(() => _error = error.toString());
    }
  }

  Widget _field(TreasuryField f) {
    if (f.kind == TreasuryFieldKind.digest) return const SizedBox.shrink();
    if ([
          'custodian_user_id',
          'user_id',
          'other_account_id',
          'client_id',
        ].contains(f.key) &&
        widget.initial[f.key] == null) {
      final workspace = widget.repository.workspace;
      final rows = f.key == 'other_account_id'
          ? [
              for (final a in workspace?.accounts ?? <TreasuryAccount>[])
                if (a.id != widget.account?.id &&
                    a.ledgerContextId == widget.account?.ledgerContextId &&
                    a.permits('transfer_record'))
                  {'id': a.id, 'name': a.alias, 'version': a.version},
            ]
          : f.key == 'client_id'
          ? [
              for (final row
                  in ((workspace?.raw['borrower_choices'] as List?) ?? [])
                      .whereType<Map<String, dynamic>>())
                if ((row['allowed_account_ids'] as List? ?? []).contains(
                  _accountId,
                ))
                  {'id': row['client_id'], 'name': row['name']},
            ]
          : ((workspace?.raw['staff_choices'] as List?) ?? [])
                .whereType<Map<String, dynamic>>()
                .map((row) => {'id': row['user_id'], 'name': row['name']})
                .toList();
      final selected = _controllers[f.key]!.text;
      return Padding(
        padding: const EdgeInsets.only(bottom: 12),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            if (rows.isEmpty)
              Text('${f.label}: no current authorized choices are available.'),
            DropdownButtonFormField<String>(
              key: ValueKey('${f.key}:$selected'),
              initialValue: rows.any((r) => r['id'] == selected)
                  ? selected
                  : null,
              isExpanded: true,
              decoration: InputDecoration(labelText: f.label),
              items: [
                for (final row in rows)
                  DropdownMenuItem(
                    value: row['id'] as String,
                    child: Text(
                      row['name'] as String? ?? 'Current authorized account',
                      overflow: TextOverflow.ellipsis,
                    ),
                  ),
              ],
              onChanged: _locked || rows.isEmpty
                  ? null
                  : (id) {
                      _controllers[f.key]!.text = id ?? '';
                      if (f.key == 'other_account_id' && id != null) {
                        _controllers['other_account_version']!.text = rows
                            .firstWhere((r) => r['id'] == id)['version']
                            .toString();
                      }
                      _changed();
                    },
            ),
          ],
        ),
      );
    }
    if (f.kind == boolKind) {
      return CheckboxListTile(
        contentPadding: EdgeInsets.zero,
        title: Text(f.label),
        value: _values[f.key] == true,
        onChanged: _locked
            ? null
            : (v) {
                _values[f.key] = v == true;
                _changed();
              },
      );
    }
    if (f.kind == choiceKind) {
      return Padding(
        padding: const EdgeInsets.only(bottom: 12),
        child: DropdownButtonFormField<String>(
          key: ValueKey('${f.key}:${_values[f.key]}'),
          initialValue: _values[f.key] as String?,
          isExpanded: true,
          decoration: InputDecoration(labelText: f.label),
          items: [
            if (!f.required)
              const DropdownMenuItem<String>(value: null, child: Text('None')),
            for (final choice in f.choices)
              DropdownMenuItem(
                value: choice,
                child: Text(
                  choice.replaceAll('_', ' '),
                  overflow: TextOverflow.ellipsis,
                ),
              ),
          ],
          onChanged: _locked
              ? null
              : (v) {
                  _values[f.key] = v;
                  _changed();
                },
        ),
      );
    }
    if (f.kind == TreasuryFieldKind.permissions) {
      return Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(f.label),
          for (final code in treasuryPermissionCodes)
            CheckboxListTile(
              contentPadding: EdgeInsets.zero,
              title: Text(
                code.replaceAll('treasury.', '').replaceAll('.', ' '),
              ),
              value: _permissions.contains(code),
              onChanged: _locked
                  ? null
                  : (v) {
                      if (v == true) {
                        _permissions.add(code);
                      } else {
                        _permissions.remove(code);
                      }
                      _changed();
                    },
            ),
        ],
      );
    }
    if (f.kind == TreasuryFieldKind.loans) {
      return Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text('Current authorized loans'),
          if (_loanChoices.isEmpty)
            const Text(
              'No current loan choices were returned. Refresh the selected receipt before applying.',
            ),
          for (final loan in _loanChoices)
            CheckboxListTile(
              contentPadding: EdgeInsets.zero,
              title: Text(
                '${loan['loan_number'] ?? 'Current loan'} (${loan['loan_type'] ?? ''})',
              ),
              value: _loans.contains(loan['loan_id']),
              onChanged: _locked
                  ? null
                  : (v) {
                      if (v == true) {
                        _loans.add(requireTreasuryId(loan['loan_id']));
                      } else {
                        _loans.remove(loan['loan_id']);
                      }
                      _values['mode'] = _loans.length == 2
                          ? 'combined'
                          : _loans.length == 1
                          ? 'single'
                          : null;
                      _changed();
                    },
            ),
        ],
      );
    }
    if (f.kind == TreasuryFieldKind.followup) {
      return Column(
        children: [
          CheckboxListTile(
            contentPadding: EdgeInsets.zero,
            value: _followup,
            title: const Text('Regular past due follow-up'),
            onChanged: _locked
                ? null
                : (v) {
                    _followup = v == true;
                    _changed();
                  },
          ),
          if (_followup) ...[
            DropdownButtonFormField<String>(
              initialValue: _values['followup_reason'] as String,
              isExpanded: true,
              decoration: const InputDecoration(labelText: 'Past due reason'),
              items: [
                for (final code in [
                  'no_cash',
                  'client_absent',
                  'business_slow',
                  'sick_hospital',
                  'emergency',
                  'promised_to_pay_later',
                  'other',
                ])
                  DropdownMenuItem(
                    value: code,
                    child: Text(code.replaceAll('_', ' ')),
                  ),
              ],
              onChanged: _locked
                  ? null
                  : (v) {
                      _values['followup_reason'] = v;
                      _changed();
                    },
            ),
            TextField(
              controller: _controllers['followup_note'],
              enabled: !_locked,
              maxLength: 500,
              decoration: const InputDecoration(labelText: 'Follow-up note'),
              onChanged: (_) => _changed(),
            ),
            if (_values['followup_reason'] == 'promised_to_pay_later') ...[
              _plainField(
                'promised_payment_date',
                'Promised date (YYYY-MM-DD)',
              ),
              _plainField('promised_amount', 'Promised amount (PHP)'),
            ],
          ],
        ],
      );
    }
    if (f.kind == TreasuryFieldKind.observations) {
      return Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text('Statement transactions (full declared coverage)'),
          for (var i = 0; i < _observations.length; i++)
            Card(
              child: Padding(
                padding: const EdgeInsets.all(12),
                child: Column(
                  children: [
                    Text('Transaction ${i + 1}'),
                    for (final field in observationFields)
                      TextField(
                        controller: _observations[i][field.key],
                        enabled: !_locked,
                        decoration: InputDecoration(
                          labelText: field.label,
                          hintText: field.key == 'direction'
                              ? 'credit or debit'
                              : null,
                        ),
                        onChanged: (_) => _changed(),
                      ),
                    TextButton(
                      onPressed: _locked
                          ? null
                          : () {
                              final row = _observations.removeAt(i);
                              for (final c in row.values) {
                                c.dispose();
                              }
                              _changed();
                            },
                      child: const Text('Remove transaction'),
                    ),
                  ],
                ),
              ),
            ),
          OutlinedButton(
            onPressed: _locked || _observations.length >= 500
                ? null
                : () {
                    _observations.add({
                      for (final field in observationFields)
                        field.key: TextEditingController(
                          text: field.key == 'id' ? newTreasuryRequestId() : '',
                        ),
                    });
                    _changed();
                  },
            child: const Text('Add statement transaction'),
          ),
        ],
      );
    }
    return Padding(
      padding: const EdgeInsets.only(bottom: 12),
      child: TextFormField(
        controller: _controllers[f.key],
        enabled: !_locked,
        readOnly:
            widget.initial[f.key] != null &&
                (f.kind == idKind || f.kind == intKind) ||
            f.key == 'other_account_version' ||
            _sourceId != null &&
                ['source_id', 'source_version', 'payee_id'].contains(f.key) ||
            _sourceId != null &&
                f.key == 'amount' &&
                (((widget.repository.workspace?.raw['source_choices']
                                as List?) ??
                            [])
                        .whereType<Map<String, dynamic>>()
                        .firstWhere(
                          (r) => r['id'] == _sourceId,
                        )['partial_supported'] !=
                    true),
        keyboardType: [moneyKind, positiveKind].contains(f.kind)
            ? const TextInputType.numberWithOptions(decimal: true)
            : f.kind == intKind
            ? TextInputType.number
            : TextInputType.text,
        maxLines: f.key == 'reason' || f.key == 'recipient_attestation' ? 3 : 1,
        maxLength: f.kind == textKind ? f.maxLength : null,
        decoration: InputDecoration(
          labelText: f.label,
          hintText: [moneyKind, positiveKind].contains(f.kind)
              ? '0.00'
              : f.kind == timeKind
              ? '2026-10-02T10:30:00+08:00'
              : f.kind == TreasuryFieldKind.dates
              ? 'YYYY-MM-DD, YYYY-MM-DD'
              : f.kind == TreasuryFieldKind.date
              ? 'YYYY-MM-DD'
              : null,
        ),
        onChanged: (_) => _changed(),
      ),
    );
  }

  Widget _plainField(String key, String label) => TextField(
    controller: _controllers[key],
    enabled: !_locked,
    decoration: InputDecoration(labelText: label),
    onChanged: (_) => _changed(),
  );
  Widget _sourcePicker() {
    final choices =
        ((widget.repository.workspace?.raw['source_choices'] as List?) ?? [])
            .whereType<Map<String, dynamic>>()
            .where(
              (row) =>
                  row['account_id'] == null ||
                  row['account_id'] == widget.account?.id,
            )
            .toList();
    if (widget.action != TreasuryAction.disbursementRecord || choices.isEmpty) {
      return const SizedBox.shrink();
    }
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        for (final row in choices.where((r) => r['supported'] != true))
          Text(
            '${row['payee_name'] ?? row['label'] ?? row['kind']}: ${row['blocker'] ?? 'This existing source cannot be executed through this account.'}',
          ),
        DropdownButtonFormField<String>(
          initialValue: _sourceId,
          isExpanded: true,
          decoration: const InputDecoration(
            labelText: 'Approved payable source',
          ),
          items: [
            for (final row in choices)
              DropdownMenuItem(
                value: row['id'] as String,
                enabled: row['supported'] == true,
                child: Text(
                  '${row['payee_name'] ?? row['kind']} · PHP ${row['amount']} · ${row['status']}',
                  overflow: TextOverflow.ellipsis,
                ),
              ),
          ],
          onChanged: _locked
              ? null
              : (id) {
                  final row = choices.firstWhere((r) => r['id'] == id);
                  _sourceId = id;
                  _controllers['source_id']!.text = row['id'] as String;
                  _controllers['source_version']!.text = row['version']
                      .toString();
                  _controllers['amount']!.text = row['amount'] as String;
                  _controllers['payee_id']!.text =
                      row['payee_id'] as String? ?? '';
                  _values['purpose'] = row['kind'];
                  if (row['provider'] != null) {
                    _controllers['provider']!.text = row['provider'] as String;
                  }
                  _values['direction'] = 'debit';
                  _changed();
                },
        ),
      ],
    );
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(
      toolbarHeight: MediaQuery.textScalerOf(
        context,
      ).scale(56).clamp(56, 112).toDouble(),
      title: Text(widget.action.label),
    ),
    body: SafeArea(
      child: Form(
        key: _form,
        child: ListView(
          padding: const EdgeInsets.all(16),
          children: [
            Text(
              widget.account?.alias ?? 'New scoped account',
              style: Theme.of(context).textTheme.titleMedium,
            ),
            const Text(
              'Current permissions, account versions and server rules apply. Record observed facts only; this form does not send provider funds.',
            ),
            if (_busy) const LinearProgressIndicator(),
            if (_error != null) Text(_error!),
            if (widget.repository.pendingRequestId != null) ...[
              const Text(
                'Result unconfirmed. Return to Cash and GCash Control to check this exact request before another action.',
              ),
              SelectableText(widget.repository.pendingRequestId!),
            ],
            const SizedBox(height: 16),
            _sourcePicker(),
            for (final f in _fields) _field(f),
            if (_controllers.containsKey('evidence_id') &&
                widget.repository.workspace?.capability('evidence_upload') ==
                    true &&
                widget.account?.permits('evidence_upload') == true)
              OutlinedButton.icon(
                onPressed: _locked ? null : _upload,
                icon: const Icon(Icons.attach_file),
                label: const Text(
                  'Upload private recipient or statement evidence',
                ),
              ),
            if (widget.action == TreasuryAction.receiptApply) ...[
              OutlinedButton(
                onPressed: _locked ? null : _preparePreview,
                child: const Text('Prepare server allocation'),
              ),
              if (_preview != null) ...[
                TreasuryRecordSummary(
                  record: _preview!,
                  label: 'Current server allocation',
                ),
                for (final row
                    in (_preview!['allocations'] as List)
                        .whereType<Map<String, dynamic>>())
                  TreasuryRecordSummary(
                    record: row,
                    label: 'Server loan allocation',
                  ),
                Text(
                  _preview!['can_apply'] == true
                      ? 'This unchanged allocation can be recorded.'
                      : 'Allocation is blocked. Received funds remain unapplied.',
                ),
              ],
            ],
            CheckboxListTile(
              contentPadding: EdgeInsets.zero,
              value: _verified,
              title: const Text(
                'I verified the current account, identities, source and evidence.',
              ),
              onChanged: _locked
                  ? null
                  : (v) => setState(() => _verified = v == true),
            ),
            FilledButton(
              onPressed:
                  _locked ||
                      widget.action == TreasuryAction.receiptApply &&
                          _preview?['can_apply'] != true
                  ? null
                  : _submit,
              child: const Text('Review and confirm'),
            ),
            if (_result != null) ...[
              TreasuryRecordSummary(
                record: _result!.result,
                label: 'Verified server result',
              ),
              for (final key in [
                'account',
                'claim',
                'receipt',
                'event',
                'opening',
                'reconciliation',
                'transfer',
                'evidence',
              ])
                if (_result!.result[key] is Map)
                  TreasuryRecordSummary(
                    record: treasuryObject(_result!.result[key]),
                    label: key.replaceAll('_', ' '),
                  ),
              if (widget.action == TreasuryAction.openingPrepare &&
                  _result!.status == 'saved' &&
                  _result!.result['opening'] is Map)
                OutlinedButton(
                  onPressed: () => Navigator.push<void>(
                    context,
                    MaterialPageRoute(
                      builder: (_) => TreasuryCommandPage(
                        repository: widget.repository,
                        account: widget.account,
                        action: TreasuryAction.openingActivate,
                        initial: {
                          'opening_id': _result!.targetId,
                          'opening_version': _result!.version,
                        },
                        targetId: _result!.targetId,
                      ),
                    ),
                  ),
                  child: const Text('Review prepared opening activation'),
                ),
            ],
          ],
        ),
      ),
    ),
  );
}
