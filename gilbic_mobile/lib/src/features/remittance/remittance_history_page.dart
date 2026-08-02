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
    super.key,
  });

  final UserSession session;
  final DeviceIdentityProvider deviceIdentityProvider;
  final RemittanceRepository? repository;

  @override
  State<RemittanceHistoryPage> createState() => _RemittanceHistoryPageState();
}

class _RemittanceHistoryPageState extends State<RemittanceHistoryPage> {
  late final RemittanceRepository _repository;
  List<RemittanceRecord> _records = const <RemittanceRecord>[];
  String? _deviceId;
  String? _errorMessage;
  bool _loading = true;
  String? _confirmingId;

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

  Future<void> _confirmReceived(RemittanceRecord record) async {
    final deviceId = _deviceId;
    if (deviceId == null || _confirmingId != null) {
      return;
    }
    if (record.recipientUserId != widget.session.userId) {
      setState(() {
        _errorMessage = 'Only the selected recipient can confirm this remittance.';
      });
      return;
    }

    final confirmed = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Confirm cash received?'),
        content: Text(
          'Confirm that you received ${_money(record.summary.totalAmount)} '
          'from ${record.collectorName}?\n\n'
          '${record.summary.clientCount} clients • '
          '${record.summary.transactionCount} entries',
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
      _confirmingId = record.remittanceId;
      _errorMessage = null;
    });
    try {
      final updated = await _repository.confirmReceived(
        widget.session,
        deviceId: deviceId,
        remittanceId: record.remittanceId,
      );
      if (mounted) {
        setState(() {
          _records = _records
              .map((item) => item.remittanceId == updated.remittanceId
                  ? updated
                  : item)
              .toList(growable: false);
        });
      }
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
        setState(() => _confirmingId = null);
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Remittances'),
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
                    if (_records.isEmpty)
                      const Padding(
                        padding: EdgeInsets.all(28),
                        child: Text(
                          'No remittances are assigned to this account yet.',
                          textAlign: TextAlign.center,
                        ),
                      )
                    else
                      for (final record in _records)
                        _RemittanceCard(
                          record: record,
                          signedInUserId: widget.session.userId,
                          confirming: _confirmingId == record.remittanceId,
                          onConfirm: () => _confirmReceived(record),
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
    required this.confirming,
    required this.onConfirm,
  });

  final RemittanceRecord record;
  final String signedInUserId;
  final bool confirming;
  final VoidCallback onConfirm;

  @override
  Widget build(BuildContext context) {
    final isRecipient = record.recipientUserId == signedInUserId;
    return Card(
      child: ExpansionTile(
        key: Key('remittance-${record.remittanceId}'),
        leading: Icon(record.isReceived ? Icons.verified : Icons.lock_clock),
        title: Text(record.remittanceNumber),
        subtitle: Text(
          '${record.collectorName} → ${record.recipientName}\n'
          '${_money(record.summary.totalAmount)} • '
          '${record.summary.transactionCount} entries • '
          '${record.isReceived ? 'Received' : 'Submitted'}',
        ),
        childrenPadding: const EdgeInsets.fromLTRB(16, 0, 16, 16),
        children: [
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
          const SizedBox(height: 10),
          for (final item in record.summary.items)
            ListTile(
              dense: true,
              contentPadding: EdgeInsets.zero,
              title: Text(item.clientName),
              subtitle: Text(
                '${item.loanType} • ${_entryLabel(item.entryType)}'
                '${item.coveredDates.isEmpty ? '' : '\n${item.coveredDates.map(_date).join(', ')}'}',
              ),
              trailing: Text(_money(item.amount)),
            ),
          if (record.note.isNotEmpty) ...[
            const Divider(),
            Align(
              alignment: Alignment.centerLeft,
              child: Text('Note: ${record.note}'),
            ),
          ],
          if (!record.isReceived && isRecipient) ...[
            const SizedBox(height: 12),
            SizedBox(
              width: double.infinity,
              child: FilledButton.icon(
                onPressed: confirming ? null : onConfirm,
                icon: confirming
                    ? const SizedBox(
                        width: 18,
                        height: 18,
                        child: CircularProgressIndicator(strokeWidth: 2),
                      )
                    : const Icon(Icons.verified_outlined),
                label: Text(
                  confirming ? 'Confirming...' : 'Confirm cash received',
                ),
              ),
            ),
          ],
          if (record.isReceived && record.receivedAt != null) ...[
            const SizedBox(height: 10),
            Align(
              alignment: Alignment.centerLeft,
              child: Text('Received: ${_dateTime(record.receivedAt!)}'),
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
