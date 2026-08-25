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
  late final TextEditingController _paymentNoteController;
  late final TextEditingController _pastDueNoteController;
  late final TextEditingController _promiseAmountController;
  late final DateTime _collectionDate;
  late DateTime _unableDate;

  CollectionEntryType _entryType = CollectionEntryType.payment;
  PaymentAllocationIntent _paymentAllocationIntent =
      PaymentAllocationIntent.scheduled;
  PaymentSubmissionDraft? _pendingDraft;
  PaymentSubmissionResult? _result;
  String? _errorMessage;
  PastDueReasonCode? _selectedReason;
  DateTime? _promisedPaymentDate;
  bool _forcePastDueFollowup = false;
  bool _submitting = false;

  bool get _sevenBySevenBlocked =>
      _isSevenBySevenLoan(widget.entry.loanType) &&
      !widget.entry.sevenBySevenMobileEnabled;
  bool get _isSevenBySeven => _isSevenBySevenLoan(widget.entry.loanType);
  bool get _isUnableToPay => _entryType == CollectionEntryType.pass;

  double get _suggestedRequiredAmount {
    if (widget.entry.contractCollectionReady &&
        widget.entry.contractTodayUnpaidAmount > 0) {
      return widget.entry.contractTodayUnpaidAmount;
    }
    return widget.entry.dailyAmount;
  }

  double? get _enteredAmount =>
      double.tryParse(_amountController.text.replaceAll(',', '').trim());

  bool get _localPartialPayment {
    final amount = _enteredAmount;
    return !_isUnableToPay &&
        !_isSevenBySeven &&
        amount != null &&
        amount > 0 &&
        _suggestedRequiredAmount > 0 &&
        amount < _suggestedRequiredAmount;
  }

  bool get _showPastDueFollowup =>
      _isUnableToPay || (!_isSevenBySeven && (_localPartialPayment || _forcePastDueFollowup));

  DateTime get _followupDate => _isUnableToPay ? _unableDate : _collectionDate;

  double get _estimatedPastDueRemainder {
    if (_isUnableToPay) return _suggestedRequiredAmount;
    final amount = _enteredAmount ?? 0;
    return (_suggestedRequiredAmount - amount).clamp(0, double.infinity);
  }

  @override
  void initState() {
    super.initState();
    _collectionDate = _dateOnly(widget.collectionDate ?? DateTime.now());
    _unableDate = _collectionDate;
    _amountController = TextEditingController(
      text: _suggestedRequiredAmount > 0
          ? _suggestedRequiredAmount.toStringAsFixed(2)
          : '',
    );
    _paymentNoteController = TextEditingController();
    _pastDueNoteController = TextEditingController();
    _promiseAmountController = TextEditingController();
  }

  @override
  void dispose() {
    _amountController.dispose();
    _paymentNoteController.dispose();
    _pastDueNoteController.dispose();
    _promiseAmountController.dispose();
    super.dispose();
  }

  void _clearSubmissionState() {
    _pendingDraft = null;
    _result = null;
    _errorMessage = null;
  }

  void _invalidatePendingDraft() {
    if (_pendingDraft == null && _result == null && _errorMessage == null) {
      return;
    }
    setState(_clearSubmissionState);
  }

  void _changeEntryType(CollectionEntryType type) {
    setState(() {
      _entryType = type;
      _forcePastDueFollowup = false;
      if (type == CollectionEntryType.pass) {
        _paymentAllocationIntent = PaymentAllocationIntent.scheduled;
      }
      _clearSubmissionState();
    });
  }

  void _changeAllocationIntent(PaymentAllocationIntent? intent) {
    if (intent == null || _submitting) return;
    setState(() {
      _paymentAllocationIntent = intent;
      _clearSubmissionState();
    });
  }

  Future<void> _selectUnableDate() async {
    final selected = await showDatePicker(
      context: context,
      initialDate: _unableDate,
      firstDate: _collectionDate.subtract(const Duration(days: 365)),
      lastDate: _collectionDate,
      helpText: 'Date client could not pay',
    );
    if (selected == null || !mounted) return;
    setState(() {
      _unableDate = _dateOnly(selected);
      if (_promisedPaymentDate != null &&
          _promisedPaymentDate!.isBefore(_unableDate)) {
        _promisedPaymentDate = null;
      }
      _clearSubmissionState();
    });
  }

  Future<void> _selectPromisedPaymentDate() async {
    final firstDate = _followupDate;
    final selected = await showDatePicker(
      context: context,
      initialDate: _promisedPaymentDate ?? firstDate,
      firstDate: firstDate,
      lastDate: firstDate.add(const Duration(days: 365)),
      helpText: 'Promised payment date',
    );
    if (selected == null || !mounted) return;
    setState(() {
      _promisedPaymentDate = _dateOnly(selected);
      _clearSubmissionState();
    });
  }

  void _selectReason(PastDueReasonCode reason) {
    setState(() {
      _selectedReason = reason;
      if (reason != PastDueReasonCode.promisedToPayLater) {
        _promisedPaymentDate = null;
        _promiseAmountController.clear();
      } else if (_promiseAmountController.text.trim().isEmpty &&
          _estimatedPastDueRemainder > 0) {
        _promiseAmountController.text =
            _estimatedPastDueRemainder.toStringAsFixed(2);
      }
      _clearSubmissionState();
    });
  }

  Future<void> _submit() async {
    if (_submitting || _sevenBySevenBlocked) return;

    final amount = _isUnableToPay ? null : _enteredAmount;
    final localError = _validateForm(amount);
    if (localError != null) {
      setState(() {
        _errorMessage = localError;
        _result = null;
      });
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
      if (!mounted) return;
      setState(() {
        _result = result;
        _errorMessage = null;
        if (!result.isFinalSuccess) {
          _pendingDraft = null;
          if (result.code == 'past_due_reason_required') {
            _forcePastDueFollowup = true;
            _errorMessage = result.message;
          }
        }
      });
    } on SpinaApiException catch (error) {
      if (!mounted) return;
      setState(() {
        _errorMessage = error.message;
        _result = null;
        if (error.code == 'extra_allocation_choice_required' ||
            error.code == 'past_due_reason_required') {
          _pendingDraft = null;
        }
        if (error.code == 'past_due_reason_required') {
          _forcePastDueFollowup = true;
        }
      });
    } on Object {
      if (!mounted) return;
      setState(() {
        _errorMessage =
            'The collection could not be completed. Retry the same entry.';
        _result = null;
      });
    } finally {
      if (mounted) setState(() => _submitting = false);
    }
  }

  String? _validateForm(double? amount) {
    if (!_isUnableToPay && (amount == null || amount <= 0)) {
      return 'Enter an amount greater than zero.';
    }
    if (_showPastDueFollowup && _selectedReason == null) {
      return 'Choose a Past Due reason.';
    }
    if (_showPastDueFollowup &&
        _selectedReason == PastDueReasonCode.other &&
        _pastDueNoteController.text.trim().isEmpty) {
      return 'Enter a short explanation for Other.';
    }
    if (_showPastDueFollowup &&
        _selectedReason == PastDueReasonCode.promisedToPayLater) {
      if (_isSevenBySeven) {
        return '7x7 promise tracking is not enabled yet.';
      }
      if (_promisedPaymentDate == null) {
        return 'Choose the promised payment date.';
      }
      final promised = double.tryParse(
        _promiseAmountController.text.replaceAll(',', '').trim(),
      );
      if (promised == null || promised <= 0) {
        return 'Enter the promised amount.';
      }
      final estimated = _estimatedPastDueRemainder;
      if (estimated > 0 && promised > estimated + 0.0001) {
        return 'Promised amount cannot be more than the remaining Past Due amount.';
      }
    }
    return null;
  }

  PastDueFollowupDraft? _buildPastDueFollowup() {
    if (!_showPastDueFollowup || _selectedReason == null) return null;
    final promised = _selectedReason == PastDueReasonCode.promisedToPayLater
        ? double.tryParse(
            _promiseAmountController.text.replaceAll(',', '').trim(),
          )
        : null;
    return PastDueFollowupDraft(
      reasonCode: _selectedReason!,
      note: _pastDueNoteController.text.trim(),
      promisedPaymentDate: _selectedReason == PastDueReasonCode.promisedToPayLater
          ? _promisedPaymentDate
          : null,
      promisedAmount: promised,
    );
  }

  Future<PaymentSubmissionDraft> _buildDraft(double? amount) async {
    final identity = await widget.deviceIdentityProvider.load();
    final sequence = await widget.deviceSequence.next();
    return PaymentSubmissionDraft(
      idempotencyKey: SecureIdempotencyKeyGenerator().generate(),
      routeEntryId: widget.entry.id,
      clientId: widget.entry.clientId,
      loanId: widget.entry.loanId,
      collectionDate: _followupDate,
      entryType:
          _isUnableToPay ? CollectionEntryType.pass : CollectionEntryType.payment,
      amount: amount,
      // Transitional compatibility for non-contract legacy posting. Contract
      // allocation ignores this date for PAYMENT; Collectors no longer choose it.
      coveredDates: _isUnableToPay
          ? const <DateTime>[]
          : <DateTime>[_collectionDate],
      recordedAt: DateTime.now().toUtc(),
      deviceId: identity.installationId,
      deviceSequence: sequence,
      note: _isUnableToPay ? '' : _paymentNoteController.text.trim(),
      routeRevision: widget.entry.routeRevision,
      paymentAllocationIntent: _isSevenBySeven
          ? PaymentAllocationIntent.scheduled
          : _paymentAllocationIntent,
      pastDueFollowup: _buildPastDueFollowup(),
    );
  }

  String _successMessage() =>
      _isUnableToPay ? 'Unable-to-pay reason saved.' : 'Payment saved.';

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Record Collection')),
      body: SafeArea(
        child: ListView(
          padding: const EdgeInsets.fromLTRB(14, 10, 14, 16),
          children: [
            _ClientSummary(entry: widget.entry),
            const SizedBox(height: 12),
            if (_sevenBySevenBlocked)
              const _SafetyNotice(
                icon: Icons.lock_outline,
                message:
                    '7x7 mobile collection is disabled until the protected server allocator explicitly enables this route entry. Use SPINA desktop for this loan.',
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
                    value: CollectionEntryType.pass,
                    label: Text('Unable to pay'),
                    icon: Icon(Icons.event_busy_outlined),
                  ),
                ],
                selected: <CollectionEntryType>{_entryType},
                onSelectionChanged: _submitting
                    ? null
                    : (selection) => _changeEntryType(selection.first),
              ),
              const SizedBox(height: 12),
              if (!_isUnableToPay) ...[
                TextField(
                  key: const Key('collection-amount'),
                  controller: _amountController,
                  enabled: !_submitting,
                  keyboardType:
                      const TextInputType.numberWithOptions(decimal: true),
                  decoration: const InputDecoration(
                    labelText: 'Amount received',
                    prefixText: '₱ ',
                  ),
                  onChanged: (_) {
                    setState(() {
                      _forcePastDueFollowup = false;
                      _clearSubmissionState();
                    });
                  },
                ),
                const SizedBox(height: 10),
                Card(
                  key: const Key('protected-allocation-card'),
                  margin: EdgeInsets.zero,
                  child: Padding(
                    padding: const EdgeInsets.all(12),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Row(
                          children: [
                            const Icon(Icons.account_tree_outlined, size: 20),
                            const SizedBox(width: 8),
                            Text(
                              'Allocation',
                              style: Theme.of(context).textTheme.titleMedium,
                            ),
                          ],
                        ),
                        const SizedBox(height: 5),
                        Text(
                          _isSevenBySeven
                              ? 'SPINA applies this payment using the protected 7x7 order.'
                              : 'SPINA applies required cash automatically: oldest Past Due → Due Today.',
                          style: Theme.of(context).textTheme.bodySmall,
                        ),
                        if (!_isSevenBySeven) ...[
                          const SizedBox(height: 10),
                          DropdownButtonFormField<PaymentAllocationIntent>(
                            key: const Key('regular-extra-allocation-choice'),
                            initialValue: _paymentAllocationIntent,
                            decoration: const InputDecoration(
                              labelText: 'If there is extra cash',
                              helperText:
                                  'Choose only when the borrower gives more than required.',
                              isDense: true,
                            ),
                            items: const [
                              DropdownMenuItem(
                                value: PaymentAllocationIntent.scheduled,
                                child: Text('No extra / required only'),
                              ),
                              DropdownMenuItem(
                                value: PaymentAllocationIntent.extraAsAdvance,
                                child: Text('Advance'),
                              ),
                              DropdownMenuItem(
                                value: PaymentAllocationIntent
                                    .extraAsPrincipalReduction,
                                child: Text('Principal Reduction'),
                              ),
                            ],
                            onChanged:
                                _submitting ? null : _changeAllocationIntent,
                          ),
                        ],
                      ],
                    ),
                  ),
                ),
                const SizedBox(height: 10),
                TextField(
                  key: const Key('collection-note'),
                  controller: _paymentNoteController,
                  enabled: !_submitting,
                  maxLines: 2,
                  decoration: const InputDecoration(
                    labelText: 'Payment note (optional)',
                    alignLabelWithHint: true,
                  ),
                  onChanged: (_) => _invalidatePendingDraft(),
                ),
              ] else ...[
                OutlinedButton.icon(
                  key: const Key('unable-date'),
                  onPressed: _submitting ? null : _selectUnableDate,
                  icon: const Icon(Icons.calendar_today),
                  label: Text('Unable to pay date: ${_date(_unableDate)}'),
                ),
              ],
              if (_showPastDueFollowup) ...[
                const SizedBox(height: 10),
                Card(
                  key: const Key('past-due-followup-card'),
                  margin: EdgeInsets.zero,
                  child: Padding(
                    padding: const EdgeInsets.all(12),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          'Past Due reason',
                          style: Theme.of(context).textTheme.titleMedium,
                        ),
                        if (!_isUnableToPay && _estimatedPastDueRemainder > 0) ...[
                          const SizedBox(height: 3),
                          Text(
                            'Remaining today: ${_money(_estimatedPastDueRemainder)}',
                            style: Theme.of(context).textTheme.bodySmall,
                          ),
                        ],
                        const SizedBox(height: 7),
                        Wrap(
                          spacing: 7,
                          runSpacing: 7,
                          children: [
                            for (final reason in PastDueReasonCode.values)
                              if (!_isSevenBySeven ||
                                  reason !=
                                      PastDueReasonCode.promisedToPayLater)
                                ChoiceChip(
                                  key: Key('past-due-reason-${reason.apiValue}'),
                                  label: Text(reason.label),
                                  selected: _selectedReason == reason,
                                  onSelected: _submitting
                                      ? null
                                      : (_) => _selectReason(reason),
                                ),
                          ],
                        ),
                        const SizedBox(height: 10),
                        TextField(
                          key: const Key('past-due-note'),
                          controller: _pastDueNoteController,
                          enabled: !_submitting,
                          maxLines: 2,
                          decoration: InputDecoration(
                            labelText: _selectedReason == PastDueReasonCode.other
                                ? 'Short explanation (required)'
                                : 'Past Due note (optional)',
                            alignLabelWithHint: true,
                          ),
                          onChanged: (_) => _invalidatePendingDraft(),
                        ),
                        if (_selectedReason ==
                            PastDueReasonCode.promisedToPayLater) ...[
                          const SizedBox(height: 10),
                          OutlinedButton.icon(
                            key: const Key('promised-payment-date'),
                            onPressed:
                                _submitting ? null : _selectPromisedPaymentDate,
                            icon: const Icon(Icons.event_outlined),
                            label: Text(
                              _promisedPaymentDate == null
                                  ? 'Promised payment date'
                                  : 'Promise: ${_date(_promisedPaymentDate!)}',
                            ),
                          ),
                          const SizedBox(height: 10),
                          TextField(
                            key: const Key('promised-amount'),
                            controller: _promiseAmountController,
                            enabled: !_submitting,
                            keyboardType: const TextInputType.numberWithOptions(
                              decimal: true,
                            ),
                            decoration: const InputDecoration(
                              labelText: 'Promised amount',
                              prefixText: '₱ ',
                              helperText: 'May be less than the full Past Due.',
                            ),
                            onChanged: (_) => _invalidatePendingDraft(),
                          ),
                        ],
                      ],
                    ),
                  ),
                ),
              ],
              if (_errorMessage != null) ...[
                const SizedBox(height: 10),
                _SafetyNotice(
                  icon: Icons.info_outline,
                  message: _errorMessage!,
                ),
              ],
              if (_result != null) ...[
                const SizedBox(height: 10),
                _ResultCard(
                  result: _result!,
                  successMessage: _successMessage(),
                ),
              ],
              const SizedBox(height: 12),
              FilledButton.icon(
                key: const Key('submit-collection-entry'),
                onPressed: _submitting || _result?.isFinalSuccess == true
                    ? null
                    : _submit,
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
                          ? (_isUnableToPay
                              ? 'Save unable-to-pay reason'
                              : 'Save payment')
                          : 'Retry same entry',
                ),
              ),
              if (_result?.isFinalSuccess == true) ...[
                const SizedBox(height: 8),
                OutlinedButton(
                  key: const Key('finish-collection-entry'),
                  onPressed: () => Navigator.of(context).pop(true),
                  child: const Text('Done and refresh route'),
                ),
              ],
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
      margin: EdgeInsets.zero,
      child: Padding(
        padding: const EdgeInsets.all(13),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(entry.clientName,
                style: Theme.of(context).textTheme.titleLarge),
            const SizedBox(height: 2),
            Text(
              [entry.area, entry.loanType]
                  .where((value) => value.isNotEmpty)
                  .join(' • '),
            ),
            const SizedBox(height: 7),
            Wrap(
              spacing: 14,
              runSpacing: 3,
              children: [
                Text('Daily ${_money(entry.dailyAmount)}'),
                Text('Balance ${_money(entry.balance)}'),
                if (entry.passCount > 0)
                  Text('Past Due events ${entry.passCount}'),
              ],
            ),
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
      margin: EdgeInsets.zero,
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Icon(icon, size: 20),
            const SizedBox(width: 8),
            Expanded(child: Text(message)),
          ],
        ),
      ),
    );
  }
}

class _ResultCard extends StatelessWidget {
  const _ResultCard({
    required this.result,
    required this.successMessage,
  });

  final PaymentSubmissionResult result;
  final String successMessage;

  @override
  Widget build(BuildContext context) {
    final success = result.isFinalSuccess;
    return Card(
      margin: EdgeInsets.zero,
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Icon(success
                    ? Icons.check_circle_outline
                    : Icons.warning_amber),
                const SizedBox(width: 8),
                Expanded(
                  child: Text(
                    success ? successMessage : result.message,
                    style: Theme.of(context).textTheme.titleSmall,
                  ),
                ),
              ],
            ),
            if (result.receiptNumber != null) ...[
              const SizedBox(height: 5),
              Text('Receipt: ${result.receiptNumber}'),
            ],
            if (result.officialBalance != null)
              Text('Official balance: ${_money(result.officialBalance!)}'),
            if (result.code != null && !success)
              Text('Code: ${result.code}'),
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

DateTime _dateOnly(DateTime value) =>
    DateTime(value.year, value.month, value.day);

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
