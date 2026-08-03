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
  late DateTime _unableDate;
  final List<DateTime> _coveredDates = <DateTime>[];

  CollectionEntryType _entryType = CollectionEntryType.payment;
  PaymentSubmissionDraft? _pendingDraft;
  PaymentSubmissionResult? _result;
  String? _errorMessage;
  String? _selectedReason;
  bool _submitting = false;

  bool get _isSevenBySeven => _isSevenBySevenLoan(widget.entry.loanType);
  bool get _isUnableToPay => _entryType == CollectionEntryType.pass;

  List<DateTime> get _sortedCoveredDates {
    final result = _coveredDates.map(_dateOnly).toSet().toList(growable: false)
      ..sort((left, right) => left.compareTo(right));
    return result;
  }

  int get _coveredDays => _sortedCoveredDates.length;

  double get _suggestedAmount => widget.entry.dailyAmount * _coveredDays;

  bool get _isSingleToday {
    final dates = _sortedCoveredDates;
    return dates.length == 1 && _sameDate(dates.single, _collectionDate);
  }

  CollectionEntryType get _submissionEntryType {
    if (_isUnableToPay) {
      return CollectionEntryType.pass;
    }
    return _isSingleToday
        ? CollectionEntryType.payment
        : CollectionEntryType.advance;
  }

  @override
  void initState() {
    super.initState();
    _collectionDate = _dateOnly(widget.collectionDate ?? DateTime.now());
    _unableDate = _collectionDate;
    _coveredDates.add(_collectionDate);
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
      _clearSubmissionState();
    });
  }

  void _setCoveredDates(Iterable<DateTime> values) {
    final normalized = values.map(_dateOnly).toSet().toList(growable: false)
      ..sort((left, right) => left.compareTo(right));
    setState(() {
      _coveredDates
        ..clear()
        ..addAll(normalized);
      _amountController.text = _suggestedAmount.toStringAsFixed(2);
      _clearSubmissionState();
    });
  }

  void _toggleCoveredDate(DateTime value) {
    final normalized = _dateOnly(value);
    final updated = _sortedCoveredDates;
    final index = updated.indexWhere((date) => _sameDate(date, normalized));
    if (index >= 0) {
      updated.removeAt(index);
    } else {
      updated.add(normalized);
    }
    _setCoveredDates(updated);
  }

  void _removeCoveredDate(DateTime value) {
    _setCoveredDates(
      _sortedCoveredDates.where((date) => !_sameDate(date, value)),
    );
  }

  Future<void> _selectCoveredDate() async {
    final existingDates = _sortedCoveredDates;
    final firstDate = _collectionDate.subtract(const Duration(days: 365));
    final lastDate = _collectionDate.add(const Duration(days: 730));
    final initialDate = existingDates.isEmpty ? _collectionDate : existingDates.last;

    final selectedDates = await showDialog<List<DateTime>>(
      context: context,
      builder: (dialogContext) {
        final workingDates = existingDates.map(_dateOnly).toSet();
        var focusedDate = initialDate;

        return StatefulBuilder(
          builder: (context, setDialogState) {
            final sortedDates = workingDates.toList(growable: false)
              ..sort((left, right) => left.compareTo(right));

            void toggleDate(DateTime value) {
              final normalized = _dateOnly(value);
              setDialogState(() {
                focusedDate = normalized;
                if (workingDates.contains(normalized)) {
                  workingDates.remove(normalized);
                } else {
                  workingDates.add(normalized);
                }
              });
            }

            return AlertDialog(
              title: const Text('Choose covered dates'),
              content: SizedBox(
                width: 380,
                child: SingleChildScrollView(
                  child: Column(
                    mainAxisSize: MainAxisSize.min,
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        'Tap every date this payment covers. The calendar stays open until you press Done.',
                        style: Theme.of(context).textTheme.bodySmall,
                      ),
                      const SizedBox(height: 8),
                      CalendarDatePicker(
                        initialDate: focusedDate,
                        firstDate: firstDate,
                        lastDate: lastDate,
                        onDateChanged: toggleDate,
                      ),
                      const Divider(),
                      Text(
                        '${sortedDates.length} selected day${sortedDates.length == 1 ? '' : 's'}',
                        style: Theme.of(context).textTheme.titleSmall,
                      ),
                      const SizedBox(height: 8),
                      if (sortedDates.isEmpty)
                        const Text('No covered date selected.')
                      else
                        Wrap(
                          spacing: 6,
                          runSpacing: 6,
                          children: [
                            for (final value in sortedDates)
                              InputChip(
                                key: Key('calendar-selected-${_date(value)}'),
                                label: Text(_date(value)),
                                avatar: const Icon(
                                  Icons.event_available,
                                  size: 16,
                                ),
                                onDeleted: () => toggleDate(value),
                              ),
                          ],
                        ),
                    ],
                  ),
                ),
              ),
              actions: [
                TextButton(
                  onPressed: workingDates.isEmpty
                      ? null
                      : () => setDialogState(workingDates.clear),
                  child: const Text('Clear'),
                ),
                TextButton(
                  onPressed: () => Navigator.of(dialogContext).pop(),
                  child: const Text('Cancel'),
                ),
                FilledButton(
                  key: const Key('confirm-covered-dates'),
                  onPressed: workingDates.isEmpty
                      ? null
                      : () => Navigator.of(dialogContext).pop(sortedDates),
                  child: const Text('Done'),
                ),
              ],
            );
          },
        );
      },
    );

    if (selectedDates == null || !mounted) {
      return;
    }
    _setCoveredDates(selectedDates);
  }

  Future<void> _selectUnableDate() async {
    final selected = await showDatePicker(
      context: context,
      initialDate: _unableDate,
      firstDate: _collectionDate.subtract(const Duration(days: 365)),
      lastDate: _collectionDate,
      helpText: 'Date client could not pay',
    );
    if (selected == null || !mounted) {
      return;
    }
    setState(() {
      _unableDate = _dateOnly(selected);
      _clearSubmissionState();
    });
  }

  void _selectReason(String reason) {
    setState(() {
      _selectedReason = reason;
      if (reason == 'Other') {
        _noteController.clear();
      } else {
        _noteController.text = reason;
      }
      _clearSubmissionState();
    });
  }

  Future<void> _submit() async {
    if (_submitting || _isSevenBySeven) {
      return;
    }

    final amount = _isUnableToPay
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
    if (!_isUnableToPay && (amount == null || amount <= 0)) {
      return 'Enter an amount greater than zero.';
    }
    if (!_isUnableToPay && _coveredDates.isEmpty) {
      return 'Choose at least one covered date.';
    }
    if (_isUnableToPay && _noteController.text.trim().isEmpty) {
      return 'Enter the reason the client could not pay.';
    }
    return null;
  }

  Future<PaymentSubmissionDraft> _buildDraft(double? amount) async {
    final identity = await widget.deviceIdentityProvider.load();
    final sequence = await widget.deviceSequence.next();
    final submissionType = _submissionEntryType;
    final selectedDates = _sortedCoveredDates;
    return PaymentSubmissionDraft(
      idempotencyKey: SecureIdempotencyKeyGenerator().generate(),
      routeEntryId: widget.entry.id,
      clientId: widget.entry.clientId,
      loanId: widget.entry.loanId,
      collectionDate: _isUnableToPay ? _unableDate : _collectionDate,
      entryType: submissionType,
      amount: amount,
      advanceFrom: submissionType == CollectionEntryType.advance
          ? selectedDates.first
          : null,
      advanceUntil: submissionType == CollectionEntryType.advance
          ? selectedDates.last
          : null,
      coveredDates:
          _isUnableToPay ? const <DateTime>[] : List<DateTime>.from(selectedDates),
      recordedAt: DateTime.now().toUtc(),
      deviceId: identity.installationId,
      deviceSequence: sequence,
      note: _noteController.text.trim(),
      routeRevision: widget.entry.routeRevision,
    );
  }

  Future<bool?> _confirmSubmission(double? amount) {
    final amountText = amount == null ? null : _money(amount);
    final message = _isUnableToPay
        ? 'Record that ${widget.entry.clientName} could not pay on '
            '${_date(_unableDate)}?\n\nReason: ${_noteController.text.trim()}'
        : 'Save ${amountText ?? 'this payment'} for '
            '${widget.entry.clientName}?\n\nCovered dates:\n${_coverageLabel()}';

    return showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Confirm collection entry'),
        content: Text(message),
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

  String _coverageLabel() =>
      _sortedCoveredDates.map(_date).map((value) => '• $value').join('\n');

  String _successMessage() {
    if (_isUnableToPay) {
      return 'Unable-to-pay reason saved.';
    }
    if (_submissionEntryType == CollectionEntryType.advance) {
      return 'Covered-date payment saved.';
    }
    return 'Payment saved.';
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
              const SizedBox(height: 16),
              if (!_isUnableToPay) ...[
                TextField(
                  key: const Key('collection-amount'),
                  controller: _amountController,
                  enabled: !_submitting,
                  keyboardType: const TextInputType.numberWithOptions(
                    decimal: true,
                  ),
                  decoration: const InputDecoration(
                    labelText: 'Amount received',
                    prefixText: '₱ ',
                  ),
                  onChanged: (_) => _invalidatePendingDraft(),
                ),
                const SizedBox(height: 14),
                Text(
                  'Covered dates',
                  style: Theme.of(context).textTheme.titleMedium,
                ),
                const SizedBox(height: 4),
                Text(
                  'Tap several dates in one calendar. Only the selected dates are covered.',
                  style: Theme.of(context).textTheme.bodySmall,
                ),
                const SizedBox(height: 8),
                Wrap(
                  spacing: 8,
                  runSpacing: 8,
                  children: [
                    ChoiceChip(
                      label: const Text('Yesterday'),
                      selected: _containsCoveredDate(
                        _coveredDates,
                        _collectionDate.subtract(const Duration(days: 1)),
                      ),
                      onSelected: _submitting
                          ? null
                          : (_) => _toggleCoveredDate(
                                _collectionDate.subtract(
                                  const Duration(days: 1),
                                ),
                              ),
                    ),
                    ChoiceChip(
                      label: const Text('Today'),
                      selected:
                          _containsCoveredDate(_coveredDates, _collectionDate),
                      onSelected: _submitting
                          ? null
                          : (_) => _toggleCoveredDate(_collectionDate),
                    ),
                    ChoiceChip(
                      label: const Text('Tomorrow'),
                      selected: _containsCoveredDate(
                        _coveredDates,
                        _collectionDate.add(const Duration(days: 1)),
                      ),
                      onSelected: _submitting
                          ? null
                          : (_) => _toggleCoveredDate(
                                _collectionDate.add(const Duration(days: 1)),
                              ),
                    ),
                    ActionChip(
                      key: const Key('add-covered-date'),
                      avatar: const Icon(Icons.calendar_month, size: 18),
                      label: const Text('Open calendar'),
                      onPressed: _submitting ? null : _selectCoveredDate,
                    ),
                  ],
                ),
                const SizedBox(height: 10),
                if (_sortedCoveredDates.isEmpty)
                  const _SafetyNotice(
                    icon: Icons.calendar_month_outlined,
                    message: 'No covered date selected.',
                  )
                else
                  Wrap(
                    spacing: 8,
                    runSpacing: 8,
                    children: [
                      for (final coveredDate in _sortedCoveredDates)
                        InputChip(
                          key: Key('covered-date-${_date(coveredDate)}'),
                          label: Text(_date(coveredDate)),
                          avatar: const Icon(Icons.event_available, size: 18),
                          onDeleted: _submitting
                              ? null
                              : () => _removeCoveredDate(coveredDate),
                        ),
                    ],
                  ),
                const SizedBox(height: 8),
                Text(
                  '$_coveredDays selected day${_coveredDays == 1 ? '' : 's'} • '
                  'Suggested amount ${_money(_suggestedAmount)}',
                  style: Theme.of(context).textTheme.bodySmall,
                ),
                const SizedBox(height: 12),
                TextField(
                  key: const Key('collection-note'),
                  controller: _noteController,
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
                const SizedBox(height: 12),
                Text(
                  'Reason',
                  style: Theme.of(context).textTheme.titleMedium,
                ),
                const SizedBox(height: 8),
                Wrap(
                  spacing: 8,
                  runSpacing: 8,
                  children: [
                    for (final reason in const [
                      'No cash',
                      'Not home',
                      'Sick',
                      'Emergency',
                      'Will pay tomorrow',
                      'Will pay double tomorrow',
                      'Other',
                    ])
                      ChoiceChip(
                        label: Text(reason),
                        selected: _selectedReason == reason,
                        onSelected:
                            _submitting ? null : (_) => _selectReason(reason),
                      ),
                  ],
                ),
                const SizedBox(height: 12),
                TextField(
                  key: const Key('collection-note'),
                  controller: _noteController,
                  enabled: !_submitting,
                  maxLines: 3,
                  decoration: const InputDecoration(
                    labelText: 'Reason client cannot pay (required)',
                    alignLabelWithHint: true,
                  ),
                  onChanged: (_) {
                    setState(() {
                      _selectedReason = null;
                      _clearSubmissionState();
                    });
                  },
                ),
              ],
              const SizedBox(height: 16),
              if (_errorMessage != null)
                _SafetyNotice(
                  icon: Icons.info_outline,
                  message: _errorMessage!,
                ),
              if (_result != null) ...[
                _ResultCard(
                  result: _result!,
                  successMessage: _successMessage(),
                ),
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
                          ? _submitLabel(
                              unableToPay: _isUnableToPay,
                              coveredMultipleDates: !_isSingleToday,
                            )
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
                'Official balance, receipt, exact covered dates, and acceptance time come from the SPINA server. Offline collection remains read-only.',
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
            Text(
              [entry.area, entry.loanType]
                  .where((value) => value.isNotEmpty)
                  .join(' • '),
            ),
            const Divider(height: 24),
            Text('Daily amount: ${_money(entry.dailyAmount)}'),
            Text('Server balance: ${_money(entry.balance)}'),
            Text('Unable-to-pay count: ${entry.passCount}'),
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
                    success ? successMessage : result.message,
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

String _submitLabel({
  required bool unableToPay,
  required bool coveredMultipleDates,
}) {
  if (unableToPay) {
    return 'Save unable-to-pay reason';
  }
  if (coveredMultipleDates) {
    return 'Save covered-date payment';
  }
  return 'Save payment';
}

DateTime _dateOnly(DateTime value) =>
    DateTime(value.year, value.month, value.day);

bool _sameDate(DateTime first, DateTime second) =>
    first.year == second.year &&
    first.month == second.month &&
    first.day == second.day;

bool _containsCoveredDate(Iterable<DateTime> values, DateTime target) =>
    values.any((value) => _sameDate(value, target));

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
