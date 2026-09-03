import 'package:flutter/material.dart';
import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/device/device_identity.dart';
import 'package:gilbic_mobile/src/core/network/spina_api.dart';
import 'package:gilbic_mobile/src/core/remittance/remittance.dart';
import 'package:gilbic_mobile/src/core/remittance/remittance_repository.dart';

class RemittanceHistoryPage extends StatefulWidget {
  const RemittanceHistoryPage({
    required this.session,
    required this.deviceIdentityProvider,
    this.repository,
    this.focusRemittanceId,
    super.key,
  });

  final UserSession session;
  final DeviceIdentityProvider deviceIdentityProvider;
  final RemittanceRepository? repository;
  final String? focusRemittanceId;

  @override
  State<RemittanceHistoryPage> createState() => _RemittanceHistoryPageState();
}

class _RemittanceHistoryPageState extends State<RemittanceHistoryPage> {
  late final RemittanceRepository _repository;
  List<RemittanceRecord> _records = const <RemittanceRecord>[];
  final Set<String> _reviewed = <String>{};
  String? _deviceId;
  String? _errorMessage;
  bool _loading = true;
  String? _actionId;

  List<RemittanceRecord> get _visibleRecords {
    final focus = widget.focusRemittanceId?.trim();
    if (focus == null || focus.isEmpty) {
      return _records;
    }
    return _records
        .where((record) => record.remittanceId == focus)
        .toList(growable: false);
  }

  @override
  void initState() {
    super.initState();
    _repository = widget.repository ?? SpinaRemittanceRepository();
    _load();
  }

  Future<void> _load() async {
    setState(() {
      _loading = true;
      _errorMessage = null;
    });
    try {
      final identity = await widget.deviceIdentityProvider.load();
      final records = await _repository.loadHistory(
        widget.session,
        deviceId: identity.installationId,
      );
      if (mounted) {
        setState(() {
          _deviceId = identity.installationId;
          _records = records;
          _reviewed.removeWhere(
            (id) => records.every((record) => record.remittanceId != id),
          );
        });
      }
    } on SpinaApiException catch (error) {
      if (mounted) {
        setState(() => _errorMessage = error.message);
      }
    } on Object {
      if (mounted) {
        setState(() => _errorMessage = 'Remittance history could not be loaded.');
      }
    } finally {
      if (mounted) {
        setState(() => _loading = false);
      }
    }
  }

  void _setReviewed(RemittanceRecord record, bool value) {
    setState(() {
      if (value) {
        _reviewed.add(record.remittanceId);
      } else {
        _reviewed.remove(record.remittanceId);
      }
      _errorMessage = null;
    });
  }

  Future<void> _confirmReceived(RemittanceRecord record) async {
    final deviceId = _deviceId;
    if (deviceId == null || _actionId != null) {
      return;
    }
    if (record.recipientUserId != widget.session.userId) {
      setState(() {
        _errorMessage = 'Only the selected recipient can confirm this remittance.';
      });
      return;
    }
    if (!_reviewed.contains(record.remittanceId)) {
      setState(() {
        _errorMessage = 'Review the full payment list and confirm that you reviewed it first.';
      });
      return;
    }

    final confirmed = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Confirm cash received?'),
        content: Text(
          'You reviewed all ${record.summary.transactionCount} payment records.\n\n'
          'Confirm that you physically received ${_money(record.summary.totalAmount)} '
          'from ${record.collectorName}?\n\n'
          'After confirmation, this cash becomes your responsibility and the '
          'itemized handover stays permanently in Received Remittance History.',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(context).pop(false),
            child: const Text('Cancel'),
          ),
          FilledButton(
            key: Key('confirm-remittance-${record.remittanceId}'),
            onPressed: () => Navigator.of(context).pop(true),
            child: const Text('Confirm received'),
          ),
        ],
      ),
    );
    if (confirmed != true || !mounted) {
      return;
    }

    setState(() {
      _actionId = record.remittanceId;
      _errorMessage = null;
    });
    try {
      final updated = await _repository.confirmReceived(
        widget.session,
        deviceId: deviceId,
        remittanceId: record.remittanceId,
      );
      _replaceRecord(updated);
    } on SpinaApiException catch (error) {
      if (mounted) {
        setState(() => _errorMessage = error.message);
      }
    } on Object {
      if (mounted) {
        setState(() => _errorMessage = 'Receipt confirmation failed.');
      }
    } finally {
      if (mounted) {
        setState(() => _actionId = null);
      }
    }
  }

  Future<void> _reject(RemittanceRecord record) async {
    final deviceId = _deviceId;
    final rejectionRepository = _repository;
    if (deviceId == null || _actionId != null) {
      return;
    }
    if (rejectionRepository is! RemittanceRejectionRepository) {
      setState(() {
        _errorMessage = 'This app build cannot reject remittances yet.';
      });
      return;
    }
    if (!_reviewed.contains(record.remittanceId)) {
      setState(() {
        _errorMessage = 'Review the full payment list before rejecting the handover.';
      });
      return;
    }

    final controller = TextEditingController();
    final reason = await showDialog<String>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Reject remittance?'),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              '${record.collectorName} will remain responsible for '
              '${_money(record.summary.totalAmount)}. The complete rejected '
              'handover stays in history.',
            ),
            const SizedBox(height: 12),
            TextField(
              key: Key('remittance-rejection-reason-${record.remittanceId}'),
              controller: controller,
              autofocus: true,
              maxLength: 500,
              maxLines: 3,
              decoration: const InputDecoration(
                labelText: 'Rejection reason',
                hintText: 'Example: Cash total does not match',
                border: OutlineInputBorder(),
              ),
            ),
          ],
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(context).pop(),
            child: const Text('Cancel'),
          ),
          FilledButton(
            key: Key('confirm-reject-remittance-${record.remittanceId}'),
            onPressed: () {
              final value = controller.text.trim();
              if (value.isNotEmpty) {
                Navigator.of(context).pop(value);
              }
            },
            child: const Text('Reject handover'),
          ),
        ],
      ),
    );
    controller.dispose();
    if (reason == null || !mounted) {
      return;
    }

    setState(() {
      _actionId = record.remittanceId;
      _errorMessage = null;
    });
    try {
      final updated = await rejectionRepository.rejectRemittance(
        widget.session,
        deviceId: deviceId,
        remittanceId: record.remittanceId,
        reason: reason,
      );
      _replaceRecord(updated);
    } on SpinaApiException catch (error) {
      if (mounted) {
        setState(() => _errorMessage = error.message);
      }
    } on Object {
      if (mounted) {
        setState(() => _errorMessage = 'Remittance rejection failed.');
      }
    } finally {
      if (mounted) {
        setState(() => _actionId = null);
      }
    }
  }

  void _replaceRecord(RemittanceRecord updated) {
    if (!mounted) return;
    setState(() {
      _records = _records
          .map((item) => item.remittanceId == updated.remittanceId ? updated : item)
          .toList(growable: false);
      _reviewed.remove(updated.remittanceId);
    });
  }

  @override
  Widget build(BuildContext context) {
    final records = _visibleRecords;
    return Scaffold(
      appBar: AppBar(
        title: Text(
          widget.focusRemittanceId == null
              ? 'Received Remittance History'
              : 'Review Remittance',
        ),
        actions: [
          IconButton(
            tooltip: 'Refresh remittances',
            onPressed: _loading ? null : _load,
            icon: const Icon(Icons.refresh),
          ),
        ],
      ),
      body: SafeArea(
        child: _loading && _records.isEmpty
            ? const Center(child: CircularProgressIndicator())
            : RefreshIndicator(
                onRefresh: _load,
                child: ListView(
                  physics: const AlwaysScrollableScrollPhysics(),
                  padding: const EdgeInsets.all(14),
                  children: [
                    if (_errorMessage != null)
                      Card(
                        child: Padding(
                          padding: const EdgeInsets.all(12),
                          child: Text(_errorMessage!),
                        ),
                      ),
                    if (records.isEmpty)
                      Padding(
                        padding: const EdgeInsets.all(28),
                        child: Text(
                          widget.focusRemittanceId == null
                              ? 'No remittances are assigned to this account yet.'
                              : 'This remittance is not available to this account.',
                          textAlign: TextAlign.center,
                        ),
                      )
                    else
                      for (final record in records)
                        _RemittanceCard(
                          record: record,
                          signedInUserId: widget.session.userId,
                          canReceive: widget.session.hasPermission('remittance.receive'),
                          reviewed: _reviewed.contains(record.remittanceId),
                          acting: _actionId == record.remittanceId,
                          onReviewedChanged: (value) => _setReviewed(record, value),
                          onConfirm: () => _confirmReceived(record),
                          onReject: () => _reject(record),
                          initiallyExpanded: widget.focusRemittanceId == record.remittanceId,
                        ),
                  ],
                ),
              ),
      ),
    );
  }
}

class _RemittanceCard extends StatelessWidget {
  const _RemittanceCard({
    required this.record,
    required this.signedInUserId,
    required this.canReceive,
    required this.reviewed,
    required this.acting,
    required this.onReviewedChanged,
    required this.onConfirm,
    required this.onReject,
    required this.initiallyExpanded,
  });

  final RemittanceRecord record;
  final String signedInUserId;
  final bool canReceive;
  final bool reviewed;
  final bool acting;
  final ValueChanged<bool> onReviewedChanged;
  final VoidCallback onConfirm;
  final VoidCallback onReject;
  final bool initiallyExpanded;

  @override
  Widget build(BuildContext context) {
    final isRecipient = record.recipientUserId == signedInUserId;
    final statusLabel = record.isReceived
        ? 'Accepted'
        : record.isRejected
            ? 'Rejected'
            : 'Pending';
    final statusIcon = record.isReceived
        ? Icons.verified
        : record.isRejected
            ? Icons.cancel_outlined
            : Icons.lock_clock;

    return Card(
      child: ExpansionTile(
        key: Key('remittance-${record.remittanceId}'),
        initiallyExpanded: initiallyExpanded,
        leading: Icon(statusIcon),
        title: Text(record.remittanceNumber),
        subtitle: Text(
          '${isRecipient ? 'Received from' : 'Sent by'} ${record.collectorName}\n'
          '${_money(record.summary.totalAmount)} • '
          '${record.summary.clientCount} clients • $statusLabel',
        ),
        childrenPadding: const EdgeInsets.fromLTRB(16, 0, 16, 16),
        children: [
          Align(
            alignment: Alignment.centerLeft,
            child: Text(
              isRecipient
                  ? 'Sender: ${record.collectorName}'
                  : 'Recipient: ${record.recipientName}',
              style: Theme.of(context).textTheme.titleSmall,
            ),
          ),
          const SizedBox(height: 4),
          Align(
            alignment: Alignment.centerLeft,
            child: Text(
              'Submitted: ${record.submittedAt == null ? 'Unknown' : _dateTime(record.submittedAt!)}',
            ),
          ),
          const SizedBox(height: 8),
          Align(
            alignment: Alignment.centerLeft,
            child: Wrap(
              spacing: 12,
              runSpacing: 4,
              children: [
                Text('${record.summary.clientCount} clients'),
                Text('${record.summary.paymentCount} payments'),
                Text('${record.summary.coveredPaymentCount} covered'),
                Text('${record.summary.unableToPayCount} unable'),
              ],
            ),
          ),
          const Divider(height: 24),
          Align(
            alignment: Alignment.centerLeft,
            child: Text(
              'Full payment list',
              style: Theme.of(context).textTheme.titleSmall,
            ),
          ),
          const SizedBox(height: 4),
          for (final item in record.summary.items)
            ListTile(
              dense: true,
              contentPadding: EdgeInsets.zero,
              title: Text(item.clientName),
              subtitle: Text(
                '${item.receiptNumber}\n'
                '${item.loanType} • ${_entryLabel(item.entryType)}'
                '${item.coveredDates.isEmpty ? '' : '\n${item.coveredDates.map(_date).join(', ')}'}',
              ),
              trailing: Text(
                _money(item.amount),
                style: const TextStyle(fontWeight: FontWeight.bold),
              ),
            ),
          if (record.note.isNotEmpty) ...[
            const Divider(),
            Align(
              alignment: Alignment.centerLeft,
              child: Text('Handover note: ${record.note}'),
            ),
          ],
          if (record.isRejected) ...[
            const SizedBox(height: 10),
            Align(
              alignment: Alignment.centerLeft,
              child: Text(
                'Rejected: ${record.rejectedAt == null ? 'Recorded' : _dateTime(record.rejectedAt!)}',
                style: Theme.of(context).textTheme.titleSmall,
              ),
            ),
            const SizedBox(height: 4),
            Align(
              alignment: Alignment.centerLeft,
              child: Text('Reason: ${record.rejectionReason}'),
            ),
            const SizedBox(height: 4),
            Align(
              alignment: Alignment.centerLeft,
              child: Text(
                'Cash responsibility stayed with ${record.collectorName}.',
              ),
            ),
          ],
          if (record.isPending && isRecipient && canReceive) ...[
            const Divider(height: 24),
            CheckboxListTile(
              key: Key('review-remittance-${record.remittanceId}'),
              contentPadding: EdgeInsets.zero,
              value: reviewed,
              onChanged: acting
                  ? null
                  : (value) => onReviewedChanged(value ?? false),
              title: const Text('I reviewed all payments'),
              subtitle: const Text(
                'Confirm that you checked the complete client, receipt, date and amount list above.',
              ),
            ),
            const SizedBox(height: 8),
            Row(
              children: [
                Expanded(
                  child: OutlinedButton.icon(
                    key: Key('reject-remittance-${record.remittanceId}'),
                    onPressed: acting || !reviewed ? null : onReject,
                    icon: const Icon(Icons.close),
                    label: const Text('Reject'),
                  ),
                ),
                const SizedBox(width: 8),
                Expanded(
                  child: FilledButton.icon(
                    key: Key('receive-remittance-${record.remittanceId}'),
                    onPressed: acting || !reviewed ? null : onConfirm,
                    icon: acting
                        ? const SizedBox(
                            width: 18,
                            height: 18,
                            child: CircularProgressIndicator(strokeWidth: 2),
                          )
                        : const Icon(Icons.verified_outlined),
                    label: Text(acting ? 'Saving...' : 'Accept'),
                  ),
                ),
              ],
            ),
          ] else if (record.isPending && isRecipient) ...[
            const SizedBox(height: 12),
            const Align(
              alignment: Alignment.centerLeft,
              child: Text('View only — remittance receiving permission is required.'),
            ),
          ],
          if (record.isReceived && record.receivedAt != null) ...[
            const SizedBox(height: 10),
            Align(
              alignment: Alignment.centerLeft,
              child: Text(
                'Accepted: ${_dateTime(record.receivedAt!)}',
                style: Theme.of(context).textTheme.titleSmall,
              ),
            ),
            const SizedBox(height: 4),
            const Align(
              alignment: Alignment.centerLeft,
              child: Text('This accepted handover is permanent and read-only.'),
            ),
          ],
        ],
      ),
    );
  }
}

String _entryLabel(String value) {
  return switch (value) {
    'pass' => 'Unable to pay',
    'advance' => 'Covered-date payment',
    _ => 'Payment',
  };
}

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
