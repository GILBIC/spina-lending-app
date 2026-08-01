import 'package:flutter/material.dart';
import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/collector/collector_route.dart';
import 'package:gilbic_mobile/src/core/device/device_identity.dart';
import 'package:gilbic_mobile/src/core/network/spina_api.dart';
import 'package:gilbic_mobile/src/core/payments/collection_device_sequence.dart';
import 'package:gilbic_mobile/src/core/payments/payment_submission.dart';
import 'package:gilbic_mobile/src/core/payments/payment_submission_repository.dart';

class CollectionEntryPage extends StatefulWidget {
  const CollectionEntryPage({
    required this.session,
    required this.entry,
    required this.repository,
    required this.deviceIdentityProvider,
    required this.deviceSequence,
    this.collectionDate,
    super.key,
  });

  final UserSession session;
  final CollectorRouteEntry entry;
  final PaymentSubmissionRepository repository;
  final DeviceIdentityProvider deviceIdentityProvider;
  final CollectionDeviceSequence deviceSequence;
  final DateTime? collectionDate;

  @override
  State<CollectionEntryPage> createState() => _CollectionEntryPageState();
}

class _CollectionEntryPageState extends State<CollectionEntryPage> {
  late final TextEditingController _amountController;
  late final TextEditingController _noteController;
  late final DateTime _collectionDate;
  late DateTime _advanceFrom;
  late DateTime _advanceUntil;

  CollectionEntryType _entryType = CollectionEntryType.payment;
  PaymentSubmissionDraft? _pendingDraft;
  PaymentSubmissionResult? _result;
  String? _errorMessage;
  bool _submitting = false;

  bool get _isSevenBySeven => _isSevenBySevenLoan(widget.entry.loanType);

  @override
  void initState() {
    super.initState();
    _collectionDate = _dateOnly(widget.collectionDate ?? DateTime.now());
    _advanceFrom = _collectionDate;
    _advanceUntil = _collectionDate;
    _amountController = TextEditingController(
      text: widget.entry.dailyAmount > 0
          ? widget.entry.dailyAmount.toStringAsFixed(2)
          : '',
    );
    _noteController = TextEditingController();
  }

  @override
  void dispose() {
    _amountController.dispose();
    _noteController.dispose();
    super.dispose();
  }

  void _invalidatePendingDraft() {
    if (_pendingDraft == null && _result == null && _errorMessage == null) {
      return;
    }
    setState(() {
      _pendingDraft = null;
      _result = null;
      _errorMessage = null;
    });
  }

  void _changeEntryType(CollectionEntryType type) {
    setState(() {
      _entryType = type;
      _pendingDraft = null;
      _result = null;
      _errorMessage = null;
    });
  }

  Future<void> _selectAdvanceDate({required bool isStart}) async {
    final current = isStart ? _advanceFrom : _advanceUntil;
    final selected = await showDatePicker(
      context: context,
      initialDate: current,
      firstDate: _collectionDate.subtract(const Duration(days: 365)),
      lastDate: _collectionDate.add(const Duration(days: 730)),
    );
    if (selected == null || !mounted) {
      return;
    }
    setState(() {
      if (isStart) {
        _advanceFrom = _dateOnly(selected);
        if (_advanceUntil.isBefore(_advanceFrom)) {
          _advanceUntil = _advanceFrom;
        }
      } else {
        _advanceUntil = _dateOnly(selected);
      }
      _pendingDraft = null;
      _result = null;
      _errorMessage = null;
    });
  }

  Future<void> _submit() async {
    if (_submitting || _isSevenBySeven) {
      return;
    }

    final amount = _entryType == CollectionEntryType.pass
        ? null
        : double.tryParse(_amountController.text.replaceAll(',', '').trim());
    final localError = _validateForm(amount);
    if (localError != null) {
      setState(() {
        _errorMessage = localError;
        _result = null;
      });
      return;
    }

    final confirmed = await _confirmSubmission(amount);
    if (confirmed != true || !mounted) {
      return;
    }

    setState(() {
      _submitting = true;
      _errorMessage = null;
      _result = null;
    });

    try {
      final draft = _pendingDraft ?? await _buildDraft(amount);
      _pendingDraft = draft;
      final result = await widget.repository.submit(widget.session, draft);
      if (!mounted) {
        return;
      }
      setState(() {
        _result = result;
        _errorMessage = null;
        if (!result.isFinalSuccess) {
          _pendingDraft = null;
        }
      });
    } on SpinaApiException catch (error) {
      if (!mounted) {
        return;
      }
      setState(() {
        _errorMessage = error.message;
        _result = null;
      });
    } on Object {
      if (!mounted) {
        return;
      }
      setState(() {
        _errorMessage =
            'The collection could not be completed. Retry the same entry.';
        _result = null;
      });
    } finally {
      if (mounted) {
        setState(() => _submitting = false);
      }
    }
  }

  String? _validateForm(double? amount) {
    if (_entryType != CollectionEntryType.pass &&
        (amount == null || amount <= 0)) {
      return 'Enter an amount greater than zero.';
    }
    if (_entryType == CollectionEntryType.advance &&
        _advanceUntil.isBefore(_advanceFrom)) {
      return 'ADV coverage cannot end before it starts.';
    }
    return null;
  }

  Future<PaymentSubmissionDraft> _buildDraft(double? amount) async {
    final identity = await widget.deviceIdentityProvider.load();
    final sequence = await widget.deviceSequence.next();
    return PaymentSubmissionDraft(
      idempotencyKey: SecureIdempotencyKeyGenerator().generate(),
      routeEntryId: widget.entry.id,
      clientId: widget.entry.clientId,
      loanId: widget.entry.loanId,
      collectionDate: _collectionDate,
      entryType: _entryType,
      amount: amount,
      advanceFrom:
          _entryType == CollectionEntryType.advance ? _advanceFrom : null,
      advanceUntil:
          _entryType == CollectionEntryType.advance ? _advanceUntil : null,
      recordedAt: DateTime.now().toUtc(),
      deviceId: identity.installationId,
      deviceSequence: sequence,
      note: _noteController.text,
      routeRevision: widget.entry.routeRevision,
    );
  }

  Future<bool?> _confirmSubmission(double? amount) {
    final action = switch (_entryType) {
      CollectionEntryType.payment => 'save this payment',
      CollectionEntryType.advance => 'save this ADV entry',
      CollectionEntryType.pass => 'record PASS for this client',
    };
    final amountText = amount == null ? null : _money(amount);

    return showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Confirm collection entry'),
        content: Text(
          'Do you want to $action for ${widget.entry.clientName}'
          '${amountText == null ? '' : ' in the amount of $amountText'}?',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(context).pop(false),
            child: const Text('Cancel'),
          ),
          FilledButton(
            key: const Key('confirm-collection-entry'),
            onPressed: () => Navigator.of(context).pop(true),
            child: const Text('Confirm'),
          ),
        ],
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Record Collection')),
      body: SafeArea(
        child: ListView(
          padding: const EdgeInsets.all(16),
          children: [
            _ClientSummary(entry: widget.entry),
            const SizedBox(height: 16),
            if (_isSevenBySeven)
              const _SafetyNotice(
                icon: Icons.lock_outline,
                message:
                    '7x7 mobile collection is disabled until its dedicated allocator is verified. Use SPINA desktop for this loan.',
              )
            else ...[
              SegmentedButton<CollectionEntryType>(
                segments: const [
                  ButtonSegment(
                    value: CollectionEntryType.payment,
                    label: Text('Payment'),
                    icon: Icon(Icons.payments_outlined),
                  ),
                  ButtonSegment(
                    value: CollectionEntryType.advance,
                    label: Text('ADV'),
                    icon: Icon(Icons.fast_forward),
                  ),
                  ButtonSegment(
                    value: CollectionEntryType.pass,
                    label: Text('PASS'),
                    icon: Icon(Icons.skip_next),
                  ),
                ],
                selected: <CollectionEntryType>{_entryType},
                onSelectionChanged: _submitting
                    ? null
                    : (selection) => _changeEntryType(selection.first),
              ),
              const SizedBox(height: 16),
              if (_entryType != CollectionEntryType.pass)
                TextField(
                  key: const Key('collection-amount'),
                  controller: _amountController,
                  enabled: !_submitting,
                  keyboardType: const TextInputType.numberWithOptions(
                    decimal: true,
                  ),
                  decoration: const InputDecoration(
                    labelText: 'Amount',
                    prefixText: '₱ ',
                  ),
                  onChanged: (_) => _invalidatePendingDraft(),
                ),
              if (_entryType == CollectionEntryType.advance) ...[
                const SizedBox(height: 12),
                Row(
                  children: [
                    Expanded(
                      child: OutlinedButton.icon(
                        key: const Key('advance-from'),
                        onPressed: _submitting
                            ? null
                            : () => _selectAdvanceDate(isStart: true),
                        icon: const Icon(Icons.calendar_today),
                        label: Text('From ${_date(_advanceFrom)}'),
                      ),
                    ),
                    const SizedBox(width: 10),
                    Expanded(
                      child: OutlinedButton.icon(
                        key: const Key('advance-until'),
                        onPressed: _submitting
                            ? null
                            : () => _selectAdvanceDate(isStart: false),
                        icon: const Icon(Icons.event_available),
                        label: Text('Until ${_date(_advanceUntil)}'),
                      ),
                    ),
                  ],
                ),
              ],
              const SizedBox(height: 12),
              TextField(
                key: const Key('collection-note'),
                controller: _noteController,
                enabled: !_submitting,
                maxLines: 3,
                decoration: const InputDecoration(
                  labelText: 'Note (optional)',
                  alignLabelWithHint: true,
                ),
                onChanged: (_) => _invalidatePendingDraft(),
              ),
              const SizedBox(height: 16),
              if (_errorMessage != null)
                _SafetyNotice(
                  icon: Icons.info_outline,
                  message: _errorMessage!,
                ),
              if (_result != null) ...[
                _ResultCard(result: _result!),
                const SizedBox(height: 12),
              ],
              FilledButton.icon(
                key: const Key('submit-collection-entry'),
                onPressed:
                    _submitting || _result?.isFinalSuccess == true ? null : _submit,
                icon: _submitting
                    ? const SizedBox(
                        width: 18,
                        height: 18,
                        child: CircularProgressIndicator(strokeWidth: 2),
                      )
                    : const Icon(Icons.cloud_upload_outlined),
                label: Text(
                  _submitting
                      ? 'Saving...'
                      : _pendingDraft == null
                          ? _submitLabel(_entryType)
                          : 'Retry same entry',
                ),
              ),
              if (_result?.isFinalSuccess == true) ...[
                const SizedBox(height: 10),
                OutlinedButton(
                  key: const Key('finish-collection-entry'),
                  onPressed: () => Navigator.of(context).pop(true),
                  child: const Text('Done and refresh route'),
                ),
              ],
              const SizedBox(height: 10),
              Text(
                'Official balance, receipt, and acceptance time come only from the SPINA server. Offline payment sync remains disabled.',
                textAlign: TextAlign.center,
                style: Theme.of(context).textTheme.bodySmall,
              ),
            ],
          ],
        ),
      ),
    );
  }
}

class _ClientSummary extends StatelessWidget {
  const _ClientSummary({required this.entry});

  final CollectorRouteEntry entry;

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              entry.clientName,
              style: Theme.of(context).textTheme.titleLarge,
            ),
            const SizedBox(height: 4),
            Text([entry.area, entry.loanType]
                .where((value) => value.isNotEmpty)
                .join(' • ')),
            const Divider(height: 24),
            Text('Daily amount: ${_money(entry.dailyAmount)}'),
            Text('Server balance: ${_money(entry.balance)}'),
            Text('PASS count: ${entry.passCount}'),
          ],
        ),
      ),
    );
  }
}

class _SafetyNotice extends StatelessWidget {
  const _SafetyNotice({required this.icon, required this.message});

  final IconData icon;
  final String message;

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(14),
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Icon(icon),
            const SizedBox(width: 10),
            Expanded(child: Text(message)),
          ],
        ),
      ),
    );
  }
}

class _ResultCard extends StatelessWidget {
  const _ResultCard({required this.result});

  final PaymentSubmissionResult result;

  @override
  Widget build(BuildContext context) {
    final success = result.isFinalSuccess;
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(14),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Icon(success ? Icons.check_circle_outline : Icons.warning_amber),
                const SizedBox(width: 8),
                Expanded(
                  child: Text(
                    result.message,
                    style: Theme.of(context).textTheme.titleSmall,
                  ),
                ),
              ],
            ),
            if (result.receiptNumber != null) ...[
              const SizedBox(height: 6),
              Text('Receipt: ${result.receiptNumber}'),
            ],
            if (result.officialBalance != null) ...[
              const SizedBox(height: 2),
              Text('Official balance: ${_money(result.officialBalance!)}'),
            ],
            if (result.code != null && !success) ...[
              const SizedBox(height: 2),
              Text('Code: ${result.code}'),
            ],
          ],
        ),
      ),
    );
  }
}

bool _isSevenBySevenLoan(String value) {
  final normalized = value.toLowerCase().replaceAll(' ', '');
  return normalized.contains('7x7') || normalized.contains('7×7');
}

String _submitLabel(CollectionEntryType type) {
  return switch (type) {
    CollectionEntryType.payment => 'Save payment',
    CollectionEntryType.advance => 'Save ADV',
    CollectionEntryType.pass => 'Save PASS',
  };
}

DateTime _dateOnly(DateTime value) => DateTime(value.year, value.month, value.day);

String _date(DateTime value) {
  return '${value.year.toString().padLeft(4, '0')}-'
      '${value.month.toString().padLeft(2, '0')}-'
      '${value.day.toString().padLeft(2, '0')}';
}

String _money(double value) {
  final fixed = value.toStringAsFixed(2);
  final parts = fixed.split('.');
  final digits = parts.first;
  final buffer = StringBuffer();
  for (var index = 0; index < digits.length; index += 1) {
    if (index > 0 && (digits.length - index) % 3 == 0) {
      buffer.write(',');
    }
    buffer.write(digits[index]);
  }
  return '₱${buffer.toString()}.${parts.last}';
}
