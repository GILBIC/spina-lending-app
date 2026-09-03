import 'package:flutter/material.dart';
import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/collector/collector_route.dart';
import 'package:gilbic_mobile/src/core/device/device_identity.dart';
import 'package:gilbic_mobile/src/core/network/spina_api.dart';
import 'package:gilbic_mobile/src/core/payments/collection_correction.dart';
import 'package:gilbic_mobile/src/core/payments/collection_correction_history_repository.dart';
import 'package:gilbic_mobile/src/core/payments/collection_correction_repository.dart';
import 'package:gilbic_mobile/src/features/collector/collector_failure_guidance.dart';

class CollectionCorrectionPage extends StatefulWidget {
  const CollectionCorrectionPage({
    required this.session,
    required this.entry,
    required this.collectionDate,
    required this.repository,
    required this.deviceIdentityProvider,
    this.historyRepository,
    super.key,
  });

  final UserSession session;
  final CollectorRouteEntry entry;
  final DateTime collectionDate;
  final CollectionCorrectionRepository repository;
  final DeviceIdentityProvider deviceIdentityProvider;
  final CollectionCorrectionHistoryRepository? historyRepository;

  @override
  State<CollectionCorrectionPage> createState() =>
      _CollectionCorrectionPageState();
}

class _CollectionCorrectionPageState extends State<CollectionCorrectionPage> {
  late final TextEditingController _amountController;
  late final TextEditingController _noteController;
  late final TextEditingController _reasonController;
  late final DateTime _collectionDate;
  late bool _unableToPay;
  final List<DateTime> _coveredDates = <DateTime>[];

  bool _submitting = false;
  String? _errorMessage;
  bool _historyLoading = false;
  bool _historyLoaded = false;
  String? _historyError;
  List<CollectionCorrectionHistoryEntry> _history =
      const <CollectionCorrectionHistoryEntry>[];

  @override
  void initState() {
    super.initState();
    _collectionDate = _dateOnly(widget.collectionDate);
    _unableToPay = widget.entry.todayEntryType.trim().toLowerCase() == 'pass';
    _coveredDates.addAll(widget.entry.todayCoveredDates.map(_dateOnly).toSet());
    if (!_unableToPay && _coveredDates.isEmpty) {
      _coveredDates.add(_collectionDate);
    }
    _amountController = TextEditingController(
      text: widget.entry.todayAmount > 0
          ? widget.entry.todayAmount.toStringAsFixed(2)
          : widget.entry.dailyAmount.toStringAsFixed(2),
    );
    _noteController = TextEditingController(text: widget.entry.todayNote);
    _reasonController = TextEditingController();
  }

  @override
  void dispose() {
    _amountController.dispose();
    _noteController.dispose();
    _reasonController.dispose();
    super.dispose();
  }

  List<DateTime> get _sortedDates {
    final dates = _coveredDates.map(_dateOnly).toSet().toList(growable: false)
      ..sort((left, right) => left.compareTo(right));
    return dates;
  }

  String get _replacementType {
    if (_unableToPay) {
      return 'pass';
    }
    final existing = widget.entry.todayEntryType.trim().toLowerCase();
    return existing == 'advance' ? 'advance' : 'payment';
  }

  void _changeMode(bool unableToPay) {
    setState(() {
      _unableToPay = unableToPay;
      _errorMessage = null;
      if (!unableToPay && _coveredDates.isEmpty) {
        // Transitional compatibility: exact obligation dates remain protected
        // server/audit evidence until the Allocation preview API replaces the
        // legacy covered_dates correction field. Collectors cannot edit them.
        _coveredDates.add(_collectionDate);
      }
    });
  }

  Future<void> _loadHistory() async {
    if (_historyLoaded || _historyLoading) {
      return;
    }
    final transactionId = widget.entry.todayTransactionId;
    if (transactionId == null || transactionId.trim().isEmpty) {
      setState(() {
        _historyLoaded = true;
        _history = const <CollectionCorrectionHistoryEntry>[];
      });
      return;
    }

    setState(() {
      _historyLoading = true;
      _historyError = null;
    });
    try {
      final identity = await widget.deviceIdentityProvider.load();
      final repository =
          widget.historyRepository ??
          SpinaCollectionCorrectionHistoryRepository();
      final history = await repository.list(
        widget.session,
        deviceId: identity.installationId,
        transactionId: transactionId,
      );
      if (!mounted) {
        return;
      }
      setState(() {
        _history = history;
        _historyLoaded = true;
      });
    } on SpinaApiException catch (error) {
      if (mounted) {
        setState(() {
          _historyError = collectorFailureMessage(
            error,
            task: CollectorFailureTask.loadCorrectionHistory,
          );
        });
      }
    } on Object catch (error) {
      if (mounted) {
        setState(() {
          _historyError = collectorFailureMessage(
            error,
            task: CollectorFailureTask.loadCorrectionHistory,
          );
        });
      }
    } finally {
      if (mounted) {
        setState(() => _historyLoading = false);
      }
    }
  }

  Future<void> _submit() async {
    if (_submitting) {
      return;
    }
    final transactionId = widget.entry.todayTransactionId;
    if (!widget.entry.canEditToday || transactionId == null) {
      setState(() {
        _errorMessage = widget.entry.todayIsLocked
            ? 'This collection is already remitted and locked.'
            : 'Only the original collector or assigned collector may edit this unlocked entry.';
      });
      return;
    }

    final amount = _unableToPay
        ? null
        : double.tryParse(_amountController.text.replaceAll(',', '').trim());
    final draft = CollectionCorrectionDraft(
      transactionId: transactionId,
      entryType: _replacementType,
      amount: amount,
      coveredDates: _unableToPay
          ? const <DateTime>[]
          : List<DateTime>.from(_sortedDates),
      note: _noteController.text,
      reason: _reasonController.text,
      expectedRouteRevision: widget.entry.routeRevision ?? '',
    );
    final validationError = draft.validate();
    if (validationError != null) {
      setState(() => _errorMessage = validationError);
      return;
    }

    final confirmed = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Confirm correction'),
        content: Text(
          'Correct the entry recorded by ${widget.entry.todayCollectorName}?\n\n'
          'New type: ${_replacementTypeLabel(_replacementType)}\n'
          '${_unableToPay ? '' : 'New amount: ${_money(amount!)}\n'}'
          'Reason: ${_reasonController.text.trim()}\n\n'
          'The previous values will remain in the audit history.',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(context).pop(false),
            child: const Text('Cancel'),
          ),
          FilledButton(
            key: const Key('confirm-collection-correction'),
            onPressed: () => Navigator.of(context).pop(true),
            child: const Text('Save correction'),
          ),
        ],
      ),
    );
    if (confirmed != true || !mounted) {
      return;
    }

    setState(() {
      _submitting = true;
      _errorMessage = null;
    });
    try {
      final identity = await widget.deviceIdentityProvider.load();
      final result = await widget.repository.correct(
        widget.session,
        deviceId: identity.installationId,
        draft: draft,
      );
      if (!mounted) {
        return;
      }
      await showDialog<void>(
        context: context,
        builder: (context) => AlertDialog(
          title: const Text('Correction saved'),
          content: Text(
            'Receipt: ${result.receiptNumber}\n'
            'Official balance: ${_money(result.officialBalance)}\n'
            'Audit version: ${result.editVersion}',
          ),
          actions: [
            FilledButton(
              onPressed: () => Navigator.of(context).pop(),
              child: const Text('Done'),
            ),
          ],
        ),
      );
      if (mounted) {
        Navigator.of(context).pop(true);
      }
    } on SpinaApiException catch (error) {
      if (mounted) {
        setState(() {
          _errorMessage = collectorFailureMessage(
            error,
            task: CollectorFailureTask.correctCollection,
          );
        });
      }
    } on Object catch (error) {
      if (mounted) {
        setState(() {
          _errorMessage = collectorFailureMessage(
            error,
            task: CollectorFailureTask.correctCollection,
          );
        });
      }
    } finally {
      if (mounted) {
        setState(() => _submitting = false);
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Edit Collection')),
      body: SafeArea(
        child: ListView(
          padding: const EdgeInsets.all(16),
          children: [
            Card(
              child: Padding(
                padding: const EdgeInsets.all(16),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      widget.entry.clientName,
                      style: Theme.of(context).textTheme.titleLarge,
                    ),
                    const SizedBox(height: 4),
                    Text(
                      '${widget.entry.loanType} • ${_date(_collectionDate)}',
                    ),
                    const Divider(height: 24),
                    Text('Recorded by: ${widget.entry.todayCollectorName}'),
                    Text(
                      widget.entry.todayIsLocked
                          ? 'Status: Remitted and locked'
                          : 'Status: Unremitted and editable',
                    ),
                  ],
                ),
              ),
            ),
            const SizedBox(height: 12),
            SegmentedButton<bool>(
              segments: const [
                ButtonSegment<bool>(
                  value: false,
                  label: Text('Payment'),
                  icon: Icon(Icons.payments_outlined),
                ),
                ButtonSegment<bool>(
                  value: true,
                  label: Text('Unable to pay'),
                  icon: Icon(Icons.event_busy_outlined),
                ),
              ],
              selected: <bool>{_unableToPay},
              onSelectionChanged: _submitting
                  ? null
                  : (selection) => _changeMode(selection.first),
            ),
            const SizedBox(height: 14),
            if (!_unableToPay) ...[
              TextField(
                key: const Key('correction-amount'),
                controller: _amountController,
                enabled: !_submitting,
                keyboardType: const TextInputType.numberWithOptions(
                  decimal: true,
                ),
                decoration: const InputDecoration(
                  labelText: 'Corrected cash amount',
                  prefixText: '₱ ',
                ),
              ),
              const SizedBox(height: 14),
              Card(
                child: Padding(
                  padding: const EdgeInsets.all(14),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        'Allocation',
                        style: Theme.of(context).textTheme.titleMedium,
                      ),
                      const SizedBox(height: 6),
                      const Text(
                        'Protected allocation is controlled by SPINA. Collectors do not manually choose covered dates here.',
                      ),
                      const SizedBox(height: 8),
                      Text(
                        'Current classification: ${_replacementTypeLabel(_replacementType)}',
                        style: Theme.of(context).textTheme.bodySmall,
                      ),
                    ],
                  ),
                ),
              ),
              Card(
                child: ExpansionTile(
                  key: const Key('correction-covered-obligations-details'),
                  title: const Text('Details / Audit history'),
                  subtitle: Text(
                    '${_sortedDates.length} protected obligation date${_sortedDates.length == 1 ? '' : 's'}',
                  ),
                  onExpansionChanged: (expanded) {
                    if (expanded) {
                      _loadHistory();
                    }
                  },
                  childrenPadding: const EdgeInsets.fromLTRB(16, 0, 16, 14),
                  children: [
                    const Align(
                      alignment: Alignment.centerLeft,
                      child: Text(
                        'Covered obligations',
                        style: TextStyle(fontWeight: FontWeight.w600),
                      ),
                    ),
                    const SizedBox(height: 6),
                    const Align(
                      alignment: Alignment.centerLeft,
                      child: Text(
                        'Exact dates are kept as server and audit evidence. They are read-only on this screen.',
                      ),
                    ),
                    const SizedBox(height: 8),
                    if (_sortedDates.isEmpty)
                      const Align(
                        alignment: Alignment.centerLeft,
                        child: Text('No covered obligation date is stored.'),
                      )
                    else
                      for (final date in _sortedDates)
                        Align(
                          alignment: Alignment.centerLeft,
                          child: Padding(
                            padding: const EdgeInsets.symmetric(vertical: 2),
                            child: Text('• ${_date(date)}'),
                          ),
                        ),
                    const Divider(height: 24),
                    const Align(
                      alignment: Alignment.centerLeft,
                      child: Text(
                        'Correction history',
                        key: Key('correction-audit-history-title'),
                        style: TextStyle(fontWeight: FontWeight.w600),
                      ),
                    ),
                    const SizedBox(height: 8),
                    if (_historyLoading)
                      const Align(
                        alignment: Alignment.centerLeft,
                        child: SizedBox(
                          width: 18,
                          height: 18,
                          child: CircularProgressIndicator(strokeWidth: 2),
                        ),
                      )
                    else if (_historyError != null)
                      Align(
                        alignment: Alignment.centerLeft,
                        child: Text(_historyError!),
                      )
                    else if (_historyLoaded && _history.isEmpty)
                      const Align(
                        alignment: Alignment.centerLeft,
                        child: Text('No previous corrections.'),
                      )
                    else
                      for (final item in _history) _historyCard(context, item),
                  ],
                ),
              ),
            ],
            const SizedBox(height: 14),
            TextField(
              key: const Key('correction-note'),
              controller: _noteController,
              enabled: !_submitting,
              maxLines: 2,
              decoration: InputDecoration(
                labelText: _unableToPay
                    ? 'Past Due reason / note'
                    : 'Payment note',
              ),
            ),
            const SizedBox(height: 14),
            TextField(
              key: const Key('correction-reason'),
              controller: _reasonController,
              enabled: !_submitting,
              maxLines: 2,
              decoration: const InputDecoration(
                labelText: 'Why are you correcting this? (required)',
                helperText:
                    'This reason is saved permanently in the audit log.',
              ),
            ),
            if (_errorMessage != null) ...[
              const SizedBox(height: 12),
              Card(
                child: Padding(
                  padding: const EdgeInsets.all(12),
                  child: Text(_errorMessage!),
                ),
              ),
            ],
            const SizedBox(height: 16),
            FilledButton.icon(
              key: const Key('submit-collection-correction'),
              onPressed: _submitting ? null : _submit,
              icon: _submitting
                  ? const SizedBox(
                      width: 18,
                      height: 18,
                      child: CircularProgressIndicator(strokeWidth: 2),
                    )
                  : const Icon(Icons.save_outlined),
              label: Text(
                _submitting ? 'Saving...' : 'Save audited correction',
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _historyCard(
    BuildContext context,
    CollectionCorrectionHistoryEntry item,
  ) {
    final before = _snapshotSummary(item.previousSnapshot);
    final after = _snapshotSummary(item.replacementSnapshot);
    return Padding(
      padding: const EdgeInsets.only(bottom: 10),
      child: DecoratedBox(
        decoration: BoxDecoration(
          border: Border.all(color: Theme.of(context).dividerColor),
          borderRadius: BorderRadius.circular(10),
        ),
        child: Padding(
          padding: const EdgeInsets.all(10),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                'Version ${item.editVersion} · ${item.editedByName}',
                style: Theme.of(context).textTheme.labelLarge,
              ),
              if (item.editedAt != null)
                Text(
                  _dateTime(item.editedAt!),
                  style: Theme.of(context).textTheme.bodySmall,
                ),
              const SizedBox(height: 6),
              Text('Reason: ${item.reason}'),
              const SizedBox(height: 4),
              Text('Before: $before'),
              Text('After: $after'),
              if (!_sameDates(
                item.previousCoveredDates,
                item.replacementCoveredDates,
              )) ...[
                const SizedBox(height: 4),
                Text(
                  'Covered obligations: ${_dates(item.previousCoveredDates)} → ${_dates(item.replacementCoveredDates)}',
                  style: Theme.of(context).textTheme.bodySmall,
                ),
              ],
            ],
          ),
        ),
      ),
    );
  }
}

String _replacementTypeLabel(String value) {
  return switch (value) {
    'pass' => 'Unable to pay',
    'advance' => 'Advance',
    _ => 'Scheduled payment',
  };
}

String _snapshotSummary(Map<String, dynamic> snapshot) {
  final type = _replacementTypeLabel(
    snapshot['entry_type']?.toString().trim().toLowerCase() ?? 'payment',
  );
  final amount = double.tryParse(snapshot['amount']?.toString() ?? '');
  if (type == 'Unable to pay') {
    return type;
  }
  return amount == null ? type : '$type · ${_money(amount)}';
}

bool _sameDates(List<DateTime> left, List<DateTime> right) {
  if (left.length != right.length) {
    return false;
  }
  for (var index = 0; index < left.length; index++) {
    if (_dateOnly(left[index]) != _dateOnly(right[index])) {
      return false;
    }
  }
  return true;
}

String _dates(List<DateTime> values) {
  if (values.isEmpty) {
    return 'none';
  }
  return values.map(_date).join(', ');
}

DateTime _dateOnly(DateTime value) =>
    DateTime(value.year, value.month, value.day);

String _date(DateTime value) {
  return '${value.year.toString().padLeft(4, '0')}-'
      '${value.month.toString().padLeft(2, '0')}-'
      '${value.day.toString().padLeft(2, '0')}';
}

String _dateTime(DateTime value) {
  final local = value.toLocal();
  return '${_date(local)} '
      '${local.hour.toString().padLeft(2, '0')}:'
      '${local.minute.toString().padLeft(2, '0')}';
}

String _money(double value) => '₱${value.toStringAsFixed(2)}';
