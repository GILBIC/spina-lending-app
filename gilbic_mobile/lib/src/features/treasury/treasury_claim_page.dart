import 'package:gilbic_mobile/src/features/treasury/treasury_selectable_text.dart';
import 'dart:typed_data';
import 'package:file_selector/file_selector.dart' as files;
import 'package:flutter/material.dart';
import 'package:gilbic_mobile/src/core/media/image_recovery_controller.dart';
import 'package:gilbic_mobile/src/core/treasury/treasury_models.dart';
import 'package:gilbic_mobile/src/core/treasury/treasury_repository.dart';
import 'package:gilbic_mobile/src/features/shared/image_recovery_scope.dart';
import 'package:gilbic_mobile/src/features/treasury/treasury_workspace_page.dart';
import 'package:image_picker/image_picker.dart';

class TreasuryClaimPage extends StatefulWidget {
  const TreasuryClaimPage({
    required this.repository,
    required this.account,
    required this.borrowerChoices,
    this.claim,
    this.pickFile,
    this.pickCamera,
    super.key,
  });
  final TreasuryRepository repository;
  final TreasuryAccount account;
  final List<Map<String, dynamic>> borrowerChoices;
  final Map<String, dynamic>? claim;
  final Future<XFile?> Function()? pickFile, pickCamera;
  @override
  State<TreasuryClaimPage> createState() => _TreasuryClaimPageState();
}

class _TreasuryClaimPageState extends State<TreasuryClaimPage> {
  final _amount = TextEditingController(),
      _reference = TextEditingController(),
      _note = TextEditingController(),
      _sent = TextEditingController();
  final _loans = <String>{};
  String? _clientId, _error, _media;
  XFile? _file;
  Uint8List? _bytes;
  MemoryImage? _image;
  bool _busy = false, _verified = false;
  int _generation = 0;
  Map<String, dynamic>? get _borrower => widget.borrowerChoices
      .where((row) => row['client_id'] == _clientId)
      .firstOrNull;
  bool get _locked =>
      _busy ||
      widget.repository.busy ||
      widget.repository.denied ||
      widget.repository.pendingRequestId != null;
  @override
  void initState() {
    super.initState();
    final claim = widget.claim;
    final current = claim?['current_version'] as Map?;
    _clientId =
        claim?['client_id'] as String? ??
        (widget.borrowerChoices.length == 1
            ? widget.borrowerChoices.first['client_id'] as String?
            : null);
    _amount.text = current?['amount'] as String? ?? '';
    _reference.text = current?['reference'] as String? ?? '';
    _sent.text = DateTime.now().toUtc().toIso8601String();
    _loans.addAll(((current?['loan_ids'] as List?) ?? []).whereType<String>());
  }

  @override
  void dispose() {
    _generation++;
    for (final c in [_amount, _reference, _note, _sent]) {
      c.clear();
      c.dispose();
    }
    _clearFile();
    super.dispose();
  }

  void _clearFile() {
    _image?.evict();
    _bytes?.fillRange(0, _bytes!.length, 0);
    _bytes = null;
    _image = null;
    _file = null;
    _media = null;
  }

  bool _selecting = false;
  Future<void> _pick({bool camera = false}) async {
    if (_locked) return;
    final generation = ++_generation;
    setState(() {
      _busy = true;
      _selecting = true;
    });
    try {
      final XFile? file;
      if (camera) {
        file = await pickRecoverableImage(
          context,
          recoveryContext: ImagePickContext(
            purpose: 'treasury-claim',
            target:
                '${widget.account.id}:${widget.claim?['id'] ?? _clientId ?? 'new'}',
            label: 'Payment proof',
          ),
          pick:
              widget.pickCamera ??
              (() => ImagePicker().pickImage(source: ImageSource.camera)),
        );
      } else {
        file =
            await (widget.pickFile ??
                (() => files.openFile(
                  acceptedTypeGroups: [
                    const files.XTypeGroup(
                      label: 'Private payment proof',
                      extensions: ['pdf', 'png', 'jpg', 'jpeg'],
                      mimeTypes: ['application/pdf', 'image/png', 'image/jpeg'],
                    ),
                  ],
                )))();
      }
      if (!mounted || generation != _generation || file == null) return;
      final type = await treasuryMediaType(file);
      final bytes = await file.readAsBytes();
      if (!mounted || generation != _generation) return;
      setState(() {
        _clearFile();
        _file = file;
        _media = type;
        _bytes = bytes;
        if (type != 'application/pdf') _image = MemoryImage(bytes);
        _error = null;
        _verified = false;
      });
    } catch (error) {
      if (mounted && generation == _generation) {
        setState(() => _error = error.toString());
      }
    } finally {
      if (mounted && generation == _generation) {
        setState(() {
          _busy = false;
          _selecting = false;
        });
      }
    }
  }

  Future<void> _submit() async {
    if (_locked) return;
    try {
      if (_file == null || !_verified) {
        throw const FormatException(
          'Select and review the private proof before submission.',
        );
      }
      if (_borrower == null || _loans.isEmpty || _loans.length > 2) {
        throw const FormatException(
          'Choose the current borrower and one or two loans.',
        );
      }
      TreasuryMoney(_amount.text, positive: true);
      const TreasuryField(
        'reference',
        'Reference',
        textKind,
        maxLength: 200,
      ).parse(_reference.text);
      const TreasuryField('time', 'Sent time', timeKind).parse(_sent.text);
      final metadata = <String, dynamic>{
        'request_id': newTreasuryRequestId(),
        'account_id': widget.account.id,
        'account_version': widget.account.version,
        'client_id': _clientId,
        'loan_ids': _loans.toList(),
        'amount': _amount.text,
        'reference': _reference.text.trim(),
        'claimed_at': _sent.text,
        'sender_note': _note.text,
        if (widget.claim != null) 'expected_version': widget.claim!['version'],
      };
      // Submit the immutable bytes the user actually reviewed, rather than
      // rereading a mutable picker path after the confirmation dialog.
      final reviewedProof = XFile.fromData(
        Uint8List.fromList(_bytes!),
        name: _file!.name,
        mimeType: _media,
      );
      final confirm = await showDialog<bool>(
        context: context,
        builder: (c) => AlertDialog(
          title: const Text('Submit payment evidence?'),
          content: SingleChildScrollView(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              mainAxisSize: MainAxisSize.min,
              children: [
                Text(widget.account.alias),
                TreasurySelectableText('PHP ${_amount.text}'),
                Text(_reference.text),
                const Text(
                  'This sends evidence for verification. It does not mark a loan paid or prove that the recipient received funds.',
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
              child: const Text('Submit proof'),
            ),
          ],
        ),
      );
      if (confirm != true || !mounted) return;
      setState(() => _busy = true);
      final generation = ++_generation;
      try {
        final result = await widget.repository.uploadClaim(
          metadata,
          reviewedProof,
          claimId: widget.claim?['id'] as String?,
        );
        if (mounted && generation == _generation) {
          setState(() {
            _error = result.status == 'saved'
                ? 'Payment proof saved for verification. No official loan payment was recorded.'
                : 'The server blocked this proof. ${result.result['message'] ?? result.result['blockers'] ?? ''}';
            if (result.status == 'saved') {
              _clearFile();
              _verified = false;
            }
          });
        }
      } catch (error) {
        if (mounted && generation == _generation) {
          setState(() {
            _error = error.toString();
            if (widget.repository.denied) {
              _clearFile();
              _amount.clear();
              _reference.clear();
              _note.clear();
              _loans.clear();
            }
          });
        }
      } finally {
        if (mounted && generation == _generation) setState(() => _busy = false);
      }
    } catch (error) {
      if (mounted) setState(() => _error = error.toString());
    }
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(
      toolbarHeight: MediaQuery.textScalerOf(
        context,
      ).scale(56).clamp(56, 112).toDouble(),
      title: Text(
        widget.claim == null ? 'Submit payment proof' : 'Correct payment proof',
      ),
    ),
    body: SafeArea(
      child: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          Text(
            widget.account.alias,
            style: Theme.of(context).textTheme.titleMedium,
          ),
          if (widget.account.instructions.isNotEmpty)
            TreasurySelectableText(widget.account.instructions),
          const Text(
            'Send only your own payment proof or an assigned borrower’s authorized proof. Recipient statements remain private.',
          ),
          const SizedBox(height: 16),
          if (_busy)
            if (_selecting)
              const Text('Selecting private proof')
            else
              const LinearProgressIndicator(),
          if (_error != null) Text(_error!),
          if (widget.repository.pendingRequestId != null) ...[
            const Text(
              'Submission unconfirmed. Return to Cash and GCash Control to check the exact request. Do not submit another proof.',
            ),
            TreasurySelectableText(widget.repository.pendingRequestId!),
          ],
          if (widget.borrowerChoices.isEmpty)
            const Text(
              'No current authorized borrower choices were returned. Refresh your assigned route or own loan portfolio before submitting.',
            ),
          DropdownButtonFormField<String>(
            key: ValueKey(_clientId),
            initialValue: _clientId,
            isExpanded: true,
            decoration: const InputDecoration(labelText: 'Current borrower'),
            items: [
              for (final row in {
                for (final row in widget.borrowerChoices) row['client_id']: row,
              }.values)
                DropdownMenuItem(
                  value: row['client_id'] as String,
                  child: Text(
                    row['name'] as String? ?? 'Current borrower',
                    overflow: TextOverflow.ellipsis,
                  ),
                ),
            ],
            onChanged: _locked || widget.claim != null
                ? null
                : (id) => setState(() {
                    _clientId = id;
                    _loans.clear();
                    _verified = false;
                  }),
          ),
          for (final loan
              in ((_borrower?['loans'] as List?) ?? [])
                  .whereType<Map<String, dynamic>>())
            CheckboxListTile(
              contentPadding: EdgeInsets.zero,
              value: _loans.contains(loan['loan_id']),
              title: Text(loan['loan_number'] as String? ?? 'Current loan'),
              subtitle: loan['loan_type'] == null
                  ? null
                  : Text(loan['loan_type'].toString()),
              onChanged: _locked
                  ? null
                  : (selected) => setState(() {
                      if (selected == true) {
                        _loans.add(requireTreasuryId(loan['loan_id']));
                      } else {
                        _loans.remove(loan['loan_id']);
                      }
                      _verified = false;
                    }),
            ),
          TextField(
            controller: _amount,
            enabled: !_locked,
            keyboardType: const TextInputType.numberWithOptions(decimal: true),
            decoration: const InputDecoration(
              labelText: 'Amount (PHP)',
              hintText: '0.00',
            ),
            onChanged: (_) => setState(() => _verified = false),
          ),
          TextField(
            controller: _reference,
            enabled: !_locked,
            maxLength: 200,
            decoration: const InputDecoration(
              labelText: 'Transaction reference',
            ),
            onChanged: (_) => setState(() => _verified = false),
          ),
          TextField(
            controller: _sent,
            enabled: !_locked,
            decoration: const InputDecoration(
              labelText: 'Actual sent time with timezone',
              hintText: '2026-10-02T10:30:00+08:00',
            ),
            onChanged: (_) => setState(() => _verified = false),
          ),
          TextField(
            controller: _note,
            enabled: !_locked,
            maxLength: 1000,
            maxLines: 3,
            decoration: const InputDecoration(
              labelText: 'Sender note (optional)',
            ),
          ),
          Wrap(
            spacing: 8,
            runSpacing: 8,
            children: [
              OutlinedButton.icon(
                onPressed: _locked ? null : () => _pick(),
                icon: const Icon(Icons.attach_file),
                label: const Text('Choose PDF or image'),
              ),
              OutlinedButton.icon(
                onPressed: _locked ? null : () => _pick(camera: true),
                icon: const Icon(Icons.camera_alt),
                label: const Text('Take proof photo'),
              ),
              if (_file != null)
                TextButton(
                  onPressed: _locked
                      ? null
                      : () => setState(() {
                          _clearFile();
                          _verified = false;
                        }),
                  child: const Text('Remove selected proof'),
                ),
            ],
          ),
          if (_file != null) ...[
            Text(
              'Selected private file: ${_file!.name} ($_media, ${_bytes!.length} bytes)',
            ),
            if (_image != null)
              Image(
                image: _image!,
                height: 180,
                fit: BoxFit.contain,
                errorBuilder: (_, __, ___) => const Text(
                  'Image preview unavailable. Choose a valid image if needed.',
                ),
              )
            else
              const Text(
                'Private PDF selected. PDF pages cannot be previewed here.',
              ),
            CheckboxListTile(
              contentPadding: EdgeInsets.zero,
              value: _verified,
              title: const Text(
                'I checked the amount, reference, borrower, loans and selected proof.',
              ),
              onChanged: _locked
                  ? null
                  : (v) => setState(() => _verified = v == true),
            ),
          ],
          const SizedBox(height: 12),
          FilledButton(
            onPressed: _locked ? null : _submit,
            child: const Text('Review submission'),
          ),
        ],
      ),
    ),
  );
}
