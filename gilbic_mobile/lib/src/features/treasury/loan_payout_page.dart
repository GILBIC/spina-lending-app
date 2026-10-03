import 'dart:typed_data';
import 'package:file_selector/file_selector.dart' as files;
import 'package:flutter/material.dart';
import 'package:image_picker/image_picker.dart';
import 'package:gilbic_mobile/src/core/media/image_recovery_controller.dart';
import 'package:gilbic_mobile/src/features/shared/image_recovery_scope.dart';
import 'package:gilbic_mobile/src/core/treasury/loan_payout_models.dart';
import 'package:gilbic_mobile/src/core/treasury/treasury_models.dart';
import 'package:gilbic_mobile/src/core/treasury/treasury_repository.dart';
import 'package:gilbic_mobile/src/features/treasury/treasury_command_page.dart';
import 'package:gilbic_mobile/src/features/treasury/treasury_workspace_page.dart';

/// A borrowed repository keeps every phase in the existing encrypted journal.
class LoanPayoutPage extends StatefulWidget {
  const LoanPayoutPage({required this.repository, this.accountId, super.key});
  final LoanPayoutRepository repository;
  final String? accountId;
  @override
  State<LoanPayoutPage> createState() => _LoanPayoutPageState();
}

class _LoanPayoutPageState extends State<LoanPayoutPage> {
  final _recipient = TextEditingController(), _note = TextEditingController();
  final _time = TextEditingController(
    text: DateTime.now().toUtc().toIso8601String(),
  );
  Map<String, dynamic>? _page, _preview, _evidence;
  List<Map<String, dynamic>> _sources = [];
  String? _sourceId, _payoutId, _error;
  String _destination = 'collector', _method = 'cash', _stage = 'borrower';
  bool _busy = true, _received = false;
  int _offset = 0;
  TreasuryAccount? get _account =>
      widget.repository.workspace?.account(widget.accountId ?? '');
  bool get _own => widget.accountId == null;
  bool get _locked =>
      _busy ||
      widget.repository.busy ||
      widget.repository.denied ||
      widget.repository.pendingRequestId != null;
  bool get _writable => !_locked && _page?['enabled'] == true;
  List<Map<String, dynamic>> get _rows =>
      ((_page?['items'] as List?) ?? []).map(treasuryObject).toList();
  Map<String, dynamic>? get _row =>
      _rows.where((r) => r['id'] == _payoutId).firstOrNull;
  @override
  void initState() {
    super.initState();
    _refresh();
  }

  @override
  void dispose() {
    for (final c in [_recipient, _note, _time]) {
      c.clear();
      c.dispose();
    }
    super.dispose();
  }

  void _selectRow(String? id) {
    _payoutId = id;
    _evidence = null;
    _note.clear();
    _received = false;
    final row = _row;
    _method = row?['funding_method'] as String? ?? 'cash';
    final stages = (row?['stages'] as List?) ?? [];
    _stage = stages.contains('borrower')
        ? 'borrower'
        : stages.firstOrNull as String? ?? 'borrower';
  }

  Future<void> _refresh() async {
    setState(() {
      _busy = true;
      _error = null;
      _preview = null;
    });
    try {
      await widget.repository.loadWorkspace();
      final page = await widget.repository.loadLoanPayouts(
        mode: _own ? 'own' : 'staff',
        accountId: widget.accountId,
        offset: _offset,
      );
      final sources =
          !_own &&
              page['enabled'] == true &&
              _account?.permits('loan_payout_prepare') == true
          ? (await widget.repository.loanPayoutSources(
                  widget.accountId!,
                ))['items']
                as List
          : <dynamic>[];
      if (!mounted) return;
      setState(() {
        _page = page;
        _sources = sources.map(treasuryObject).toList();
        if (!_sources.any((s) => s['source_id'] == _sourceId)) {
          _sourceId = _sources.firstOrNull?['source_id'] as String?;
        }
        if (!_rows.any((r) => r['id'] == _payoutId)) {
          _selectRow(_rows.firstOrNull?['id'] as String?);
        }
      });
    } catch (e) {
      if (mounted) {
        setState(() {
          _error = e.toString();
          if (widget.repository.denied) {
            _page = null;
            _sources = [];
            _recipient.clear();
            _note.clear();
            _evidence = null;
          }
        });
      }
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _run(Future<void> Function() work) async {
    if (_locked) return;
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      await work();
    } catch (e) {
      if (mounted) setState(() => _error = e.toString());
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<bool> _review(String title, String detail) async =>
      await showDialog<bool>(
        context: context,
        builder: (c) => AlertDialog(
          title: Text(title),
          content: SingleChildScrollView(child: Text(detail)),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(c, false),
              child: const Text('Cancel'),
            ),
            FilledButton(
              onPressed: () => Navigator.pop(c, true),
              child: const Text('Confirm reviewed record'),
            ),
          ],
        ),
      ) ??
      false;
  Future<void> _previewSource() => _run(() async {
    final source = _sources
        .where((s) => s['source_id'] == _sourceId)
        .firstOrNull;
    if (source == null || _account == null) {
      throw const FormatException('Select a current approved source.');
    }
    final p = await widget.repository.loanPayoutPreview(
      loanPayoutPreparation(
        _account!,
        source,
        _recipient.text,
        destination: _destination,
      ),
    );
    if (mounted) setState(() => _preview = p);
  });
  Future<void> _prepare() => _run(() async {
    final p = _preview;
    if (p == null || _account == null) return;
    final source = _sources.firstWhere((s) => s['source_id'] == _sourceId);
    final input = loanPayoutPreparation(
      _account!,
      source,
      _recipient.text,
      destination: _destination,
    );
    if (!await _review(
      'Prepare loan payout',
      '${p['label'] ?? source['label']}\nPHP ${p['amount']}\nTo ${p['payee_name']} ($_destination)\n${_recipient.text}\nPreparation records no payment.',
    )) {
      return;
    }
    final fields = {...input, 'source_digest': p['source_digest']}
      ..remove('account_id')
      ..remove('expected_version');
    final result = await widget.repository.execute(
      TreasuryCommand(
        TreasuryAction.loanPayoutPrepare,
        requestId: newTreasuryRequestId(),
        accountId: _account!.id,
        expectedVersion: _account!.version,
        fields: fields,
      ),
    );
    if (!mounted) return;
    _preview = null;
    await _refresh();
    if (mounted) {
      setState(
        () => _error = result.status == 'saved'
            ? 'Preparation saved. Record the actual debit separately.'
            : 'The preparation was blocked.',
      );
    }
  });
  Future<void> _pick({bool camera = false}) => _run(() async {
    final row = _row;
    if (row == null || _account == null) return;
    Uint8List? bytes;
    MemoryImage? image;
    try {
      final file = camera
          ? await pickRecoverableImage(
              context,
              recoveryContext: ImagePickContext(
                purpose: 'loan-payout-receipt',
                target: '${_account!.id}:${row['id']}',
                label: 'Private loan payout evidence',
              ),
              pick: () => ImagePicker().pickImage(source: ImageSource.camera),
            )
          : await files.openFile(
              acceptedTypeGroups: [
                const files.XTypeGroup(
                  label: 'Private receipt',
                  extensions: ['png', 'jpg', 'jpeg', 'pdf'],
                ),
              ],
            );
      if (file == null || !mounted) return;
      final media = await treasuryMediaType(file);
      bytes = await file.readAsBytes();
      if (!mounted) return;
      image = MemoryImage(bytes);
      final accepted = await showDialog<bool>(
        context: context,
        builder: (c) => AlertDialog(
          title: const Text('Review private receipt'),
          content: SingleChildScrollView(
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                Text(file.name),
                if (media != 'application/pdf')
                  Image(image: image!)
                else
                  const Text(
                    'Review the selected PDF in its source before confirming.',
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
              child: const Text('Upload reviewed evidence'),
            ),
          ],
        ),
      );
      if (accepted != true || !mounted) return;
      final result = await widget.repository.uploadEvidence(
        requestId: newTreasuryRequestId(),
        accountId: _account!.id,
        purpose: 'recipient',
        file: XFile.fromData(bytes, name: file.name, mimeType: media),
      );
      if (mounted) {
        setState(() => _evidence = treasuryObject(result.result['evidence']));
      }
    } finally {
      await image?.evict();
      bytes?.fillRange(0, bytes.length, 0);
    }
  });
  Future<void> _submit(TreasuryAction action) => _run(() async {
    final row = _row;
    if (row == null) return;
    final fields = <String, dynamic>{
      'payout_id': row['id'],
      'payout_version': row['version'],
    };
    if (action == TreasuryAction.loanPayoutCancel) {
      fields['reason'] = _note.text.trim();
    } else {
      fields['reviewed_amount'] = row['amount'];
      if (action != TreasuryAction.loanPayoutAcknowledge) {
        if (_evidence == null) {
          throw const FormatException(
            'Upload and review the private evidence first.',
          );
        }
        fields['evidence_id'] = _evidence!['id'];
      }
      if (action == TreasuryAction.loanPayoutRenewalComplete) {
        if (!_received) {
          throw const FormatException(
            'Confirm the independent borrower receipt and reviewed proof.',
          );
        }
        fields.addAll({
          'proof_review_confirmed': true,
          'reason': _note.text.trim(),
        });
      } else {
        fields['acknowledged_at'] = _time.text.trim();
        if (action == TreasuryAction.loanPayoutRecipientConfirm) {
          fields.addAll({
            'received': _received,
            'recipient_attestation': _note.text.trim(),
          });
        } else if (action == TreasuryAction.loanPayoutFirstLoanComplete) {
          if (!_received) {
            throw const FormatException(
              'Actual borrower receipt is required to complete this loan.',
            );
          }
          fields.addAll({
            'borrower_confirmed': true,
            'receipt_method': _method,
            'borrower_attestation': _note.text.trim(),
          });
        } else {
          fields.addAll({
            'stage': _stage,
            'received': _received,
            'receipt_method': _method,
            'attestation': _note.text.trim(),
          });
        }
      }
    }
    final command = TreasuryCommand(
      action,
      requestId: newTreasuryRequestId(),
      accountId: action == TreasuryAction.loanPayoutAcknowledge
          ? null
          : row['account_id'] as String,
      expectedVersion: action == TreasuryAction.loanPayoutAcknowledge
          ? null
          : _account?.version ?? 0,
      fields: fields,
    );
    command.toJson();
    if (!await _review(
      action.label,
      '${row['label'] ?? row['source_snapshot']?['source']?['label'] ?? 'Reviewed loan'}\nPHP ${row['amount']} · ${row['destination']}\n${_own ? _stage : action.label}\n${action == TreasuryAction.loanPayoutCancel
          ? 'Cancel unfunded preparation'
          : _received
          ? 'Confirmed received / proof reviewed'
          : 'Not received'}\n${_note.text}',
    )) {
      return;
    }
    final result = await widget.repository.execute(
      command,
      targetId: row['id'] as String,
    );
    if (!mounted) return;
    _evidence = null;
    _note.clear();
    _received = false;
    await _refresh();
    if (mounted) {
      setState(
        () => _error = result.status == 'saved'
            ? 'This stage is saved. Review the next separate step.'
            : 'The stage was blocked.',
      );
    }
  });
  Future<void> _recover({bool retry = false}) async {
    if (_busy || widget.repository.busy) return;
    if (retry &&
        !await _review(
          'Retry unchanged request',
          'Resend the exact saved request and file only after checking for its outcome.',
        )) {
      return;
    }
    if (!mounted) return;
    setState(() => _busy = true);
    try {
      final result = retry
          ? await widget.repository.retrySame()
          : await widget.repository.recover();
      if (!mounted) return;
      final recoveredUpload =
          result?.status == 'saved' &&
          result!.raw['action'] == 'evidence_upload';
      // The generic upload journal binds the account, not a payout selection.
      // Recovery must never attach its file to whichever payout opened first.
      if (recoveredUpload) _evidence = null;
      if (result != null) await _refresh();
      if (mounted) {
        setState(
          () => _error = result == null
              ? 'Outcome still unconfirmed. Keep this request.'
              : recoveredUpload
              ? 'Upload recovered without assigning it to a payout. Choose and review the receipt again for the selected payout.'
              : 'Outcome recovered. Review the separate next step before submitting.',
        );
      }
    } catch (e) {
      if (mounted) setState(() => _error = e.toString());
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _debit() async {
    if (!_writable || _account == null || _row == null) return;
    await Navigator.of(context).push<void>(
      MaterialPageRoute(
        builder: (_) => TreasuryCommandPage(
          repository: widget.repository,
          account: _account,
          action: TreasuryAction.disbursementRecord,
        ),
      ),
    );
    if (mounted) await _refresh();
  }

  Widget _choice(
    String label,
    String? value,
    List<(String, String)> choices,
    ValueChanged<String?> change,
  ) => Padding(
    padding: const EdgeInsets.only(bottom: 12),
    child: DropdownButtonFormField<String>(
      key: ValueKey('$label:$value'),
      initialValue: value,
      isExpanded: true,
      decoration: InputDecoration(labelText: label),
      items: [
        for (final item in choices)
          DropdownMenuItem(
            value: item.$1,
            child: Text(item.$2, overflow: TextOverflow.ellipsis),
          ),
      ],
      onChanged: _locked ? null : change,
    ),
  );
  @override
  Widget build(BuildContext context) {
    final row = _row,
        ack =
            row?['acknowledgments'] ??
            row?['payload']?['acknowledgments'] ??
            <String, dynamic>{};
    final available = _writable && row != null && row['blocker'] == null;
    return Scaffold(
      appBar: AppBar(
        title: const Text('Loan payouts'),
        actions: [
          IconButton(
            tooltip: 'Refresh payouts',
            onPressed: _locked ? null : _refresh,
            icon: const Icon(Icons.refresh),
          ),
        ],
      ),
      body: SafeArea(
        child: ListView(
          padding: const EdgeInsets.all(16),
          children: [
            const Text(
              'Payment to the recipient, borrower handover and loan completion are separate records.',
            ),
            if (_busy) const LinearProgressIndicator(),
            if (_error != null) Text(_error!, semanticsLabel: _error),
            if (widget.repository.pendingRequestId != null) ...[
              const Text(
                'Submission unconfirmed. Recover this exact request before another action.',
              ),
              Wrap(
                spacing: 8,
                children: [
                  TextButton(
                    onPressed: _busy ? null : () => _recover(),
                    child: const Text('Check saved request'),
                  ),
                  TextButton(
                    onPressed: _busy ? null : () => _recover(retry: true),
                    child: const Text('Retry unchanged'),
                  ),
                ],
              ),
            ],
            if (_page?['enabled'] == false)
              const Text(
                'Entry is disabled. Existing payout history remains available.',
              ),
            if (!_own && _sources.isNotEmpty) ...[
              const SizedBox(height: 16),
              _choice(
                'Approved source',
                _sourceId,
                [
                  for (final s in _sources)
                    (
                      s['source_id'] as String,
                      '${s['label']} · PHP ${s['amount']}',
                    ),
                ],
                (id) => setState(() {
                  _sourceId = id;
                  _preview = null;
                }),
              ),
              _choice(
                'Pay proceeds to',
                _destination,
                const [
                  ('collector', 'Assigned Collector (default)'),
                  ('borrower', 'Named borrower directly'),
                ],
                (v) => setState(() {
                  _destination = v!;
                  _preview = null;
                }),
              ),
              TextField(
                key: const Key('payout-recipient'),
                controller: _recipient,
                enabled: !_locked,
                maxLength: 200,
                decoration: const InputDecoration(
                  labelText: 'Reviewed recipient wallet or bank reference',
                ),
                onChanged: (_) => setState(() => _preview = null),
              ),
              OutlinedButton(
                onPressed: _writable ? _previewSource : null,
                child: const Text('Review payout'),
              ),
              if (_preview != null) ...[
                Text(
                  'PHP ${_preview!['amount']} to ${_preview!['payee_name']}',
                ),
                FilledButton(
                  onPressed: _writable ? _prepare : null,
                  child: const Text('Prepare payout'),
                ),
              ],
            ],
            const SizedBox(height: 16),
            if (_rows.isEmpty)
              const Text('No payouts on this page.')
            else ...[
              _choice('Recorded payout', _payoutId, [
                for (final r in _rows)
                  (
                    r['id'] as String,
                    '${r['label'] ?? r['source_snapshot']?['source']?['label'] ?? 'Loan payout'} · PHP ${r['amount']} · ${r['status']}',
                  ),
              ], (id) => setState(() => _selectRow(id))),
              if (row != null) ...[
                Text(
                  'PHP ${row['amount']} · ${row['destination']} · ${row['status'].toString().replaceAll('_', ' ')}',
                ),
                if (row['blocker'] != null) Text(row['blocker'].toString()),
                for (final stage in [
                  'recipient',
                  'borrower_handover',
                  'borrower',
                ])
                  if (ack[stage] != null)
                    Text(
                      '${stage.replaceAll('_', ' ')}: ${ack[stage]['received'] == true ? 'received' : 'not received'}',
                    ),
                if (!_own && row['status'] == 'prepared')
                  OutlinedButton(
                    onPressed: available ? _debit : null,
                    child: const Text('Record actual debit'),
                  ),
                if (!['completed', 'cancelled'].contains(row['status'])) ...[
                  if (_own)
                    _choice('My acknowledgment', _stage, [
                      for (final s in (row['stages'] as List))
                        (s as String, s.replaceAll('_', ' ')),
                    ], (v) => setState(() => _stage = v!)),
                  if (!_own &&
                      [
                        'debited',
                        'recipient_confirmed',
                      ].contains(row['status']))
                    Wrap(
                      spacing: 8,
                      children: [
                        OutlinedButton(
                          onPressed: available ? () => _pick() : null,
                          child: const Text('Upload private receipt'),
                        ),
                        OutlinedButton(
                          onPressed: available
                              ? () => _pick(camera: true)
                              : null,
                          child: const Text('Photograph receipt'),
                        ),
                        if (_evidence != null)
                          const Text('Reviewed evidence uploaded'),
                      ],
                    ),
                  if (row['status'] != 'prepared') ...[
                    CheckboxListTile(
                      contentPadding: EdgeInsets.zero,
                      title: Text(
                        _own
                            ? 'I confirm this actual receipt or handover'
                            : row['status'] == 'debited'
                            ? 'Recipient received the exact proceeds'
                            : row['source_kind'] == 'renewal'
                            ? 'Independent borrower receipt and proof reviewed'
                            : 'Borrower received the exact proceeds',
                      ),
                      value: _received,
                      onChanged: available
                          ? (v) => setState(() => _received = v == true)
                          : null,
                    ),
                    if (_own ||
                        row['source_kind'] == 'first_loan' &&
                            row['status'] == 'recipient_confirmed')
                      _choice(
                        'Actual receipt method',
                        _method,
                        const [
                          ('cash', 'Cash'),
                          ('gcash', 'GCash'),
                          ('bank', 'Bank'),
                        ],
                        (v) => setState(() => _method = v!),
                      ),
                    TextField(
                      controller: _time,
                      enabled: available,
                      decoration: const InputDecoration(
                        labelText: 'Actual receipt time with time zone',
                        hintText: '2026-10-03T10:30:00+08:00',
                      ),
                    ),
                  ],
                  TextField(
                    controller: _note,
                    enabled:
                        available ||
                        (!_own && _writable && row['status'] == 'prepared'),
                    maxLength: 1000,
                    maxLines: 3,
                    decoration: const InputDecoration(
                      labelText: 'Receipt statement or reason',
                    ),
                  ),
                  if (_own)
                    FilledButton(
                      onPressed:
                          available && row['status'] == 'recipient_confirmed'
                          ? () => _submit(TreasuryAction.loanPayoutAcknowledge)
                          : null,
                      child: const Text('Record my acknowledgment'),
                    )
                  else if (row['status'] == 'prepared')
                    TextButton(
                      onPressed: _writable
                          ? () => _submit(TreasuryAction.loanPayoutCancel)
                          : null,
                      child: const Text('Cancel unfunded preparation'),
                    )
                  else if (row['status'] == 'debited')
                    FilledButton(
                      onPressed: available
                          ? () => _submit(
                              TreasuryAction.loanPayoutRecipientConfirm,
                            )
                          : null,
                      child: const Text('Record recipient receipt'),
                    )
                  else if (row['status'] == 'recipient_confirmed')
                    FilledButton(
                      onPressed: available
                          ? () => _submit(
                              row['source_kind'] == 'first_loan'
                                  ? TreasuryAction.loanPayoutFirstLoanComplete
                                  : TreasuryAction.loanPayoutRenewalComplete,
                            )
                          : null,
                      child: Text(
                        row['source_kind'] == 'first_loan'
                            ? 'Complete borrower release'
                            : 'Complete renewal after proof review',
                      ),
                    ),
                ],
              ],
            ],
            Wrap(
              spacing: 8,
              children: [
                if (_offset > 0)
                  TextButton(
                    onPressed: _locked
                        ? null
                        : () {
                            _offset -= 50;
                            _refresh();
                          },
                    child: const Text('Previous'),
                  ),
                if (_page?['has_more'] == true)
                  TextButton(
                    onPressed: _locked
                        ? null
                        : () {
                            _offset += 50;
                            _refresh();
                          },
                    child: const Text('Next'),
                  ),
              ],
            ),
          ],
        ),
      ),
    );
  }
}
