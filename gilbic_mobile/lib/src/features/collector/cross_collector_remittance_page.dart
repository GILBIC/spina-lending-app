import 'package:flutter/material.dart';
import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/device/device_identity.dart';
import 'package:gilbic_mobile/src/core/network/spina_api.dart';
import 'package:gilbic_mobile/src/core/remittance/cross_remittance.dart';
import 'package:gilbic_mobile/src/core/remittance/cross_remittance_repository.dart';
import 'package:gilbic_mobile/src/core/remittance/remittance.dart';

class CrossCollectorRemittancePage extends StatefulWidget {
  const CrossCollectorRemittancePage({
    required this.session,
    required this.deviceIdentityProvider,
    this.repository,
    this.collectionDate,
    super.key,
  });

  final UserSession session;
  final DeviceIdentityProvider deviceIdentityProvider;
  final CrossRemittanceRepository? repository;
  final DateTime? collectionDate;

  @override
  State<CrossCollectorRemittancePage> createState() =>
      _CrossCollectorRemittancePageState();
}

class _CrossCollectorRemittancePageState
    extends State<CrossCollectorRemittancePage> {
  late final CrossRemittanceRepository _repository;
  late final TextEditingController _noteController;
  late final DateTime _collectionDate;

  List<CrossRemittanceTarget> _targets = const <CrossRemittanceTarget>[];
  RemittanceSummary? _summary;
  RemittanceRecord? _submitted;
  String? _deviceId;
  String? _selectedRecipientId;
  String? _errorMessage;
  bool _loading = true;
  bool _submitting = false;

  @override
  void initState() {
    super.initState();
    _repository = widget.repository ?? SpinaCrossRemittanceRepository();
    _noteController = TextEditingController();
    final source = widget.collectionDate ?? DateTime.now();
    _collectionDate = DateTime(source.year, source.month, source.day);
    _loadTargets();
  }

  @override
  void dispose() {
    _noteController.dispose();
    super.dispose();
  }

  Future<void> _loadTargets() async {
    setState(() {
      _loading = true;
      _errorMessage = null;
    });
    try {
      final identity = await widget.deviceIdentityProvider.load();
      final targets = await _repository.loadTargets(
        widget.session,
        deviceId: identity.installationId,
        collectionDate: _collectionDate,
      );
      if (!mounted) {
        return;
      }
      final selected = targets.any(
        (target) => target.recipientUserId == _selectedRecipientId,
      )
          ? _selectedRecipientId
          : targets.isEmpty
              ? null
              : targets.first.recipientUserId;
      setState(() {
        _deviceId = identity.installationId;
        _targets = targets;
        _selectedRecipientId = selected;
        _summary = null;
      });
      if (selected != null) {
        await _loadPreview(selected);
      }
    } on SpinaApiException catch (error) {
      if (mounted) {
        setState(() => _errorMessage = error.message);
      }
    } on Object {
      if (mounted) {
        setState(() {
          _errorMessage = 'Assigned-collector remittances could not be loaded.';
        });
      }
    } finally {
      if (mounted) {
        setState(() => _loading = false);
      }
    }
  }

  Future<void> _loadPreview(String recipientUserId) async {
    final deviceId = _deviceId;
    if (deviceId == null) {
      return;
    }
    setState(() {
      _loading = true;
      _errorMessage = null;
      _selectedRecipientId = recipientUserId;
    });
    try {
      final summary = await _repository.loadPreview(
        widget.session,
        deviceId: deviceId,
        recipientUserId: recipientUserId,
        collectionDate: _collectionDate,
      );
      if (mounted) {
        setState(() => _summary = summary);
      }
    } on SpinaApiException catch (error) {
      if (mounted) {
        setState(() => _errorMessage = error.message);
      }
    } finally {
      if (mounted) {
        setState(() => _loading = false);
      }
    }
  }

  Future<void> _submit() async {
    final summary = _summary;
    final deviceId = _deviceId;
    final recipientId = _selectedRecipientId;
    if (_submitting ||
        summary == null ||
        summary.items.isEmpty ||
        deviceId == null ||
        recipientId == null) {
      return;
    }
    final target = _targets.firstWhere(
      (item) => item.recipientUserId == recipientId,
    );

    final confirmed = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Send to assigned collector?'),
        content: Text(
          'Send ${_money(summary.totalAmount)} for '
          '${summary.clientCount} client${summary.clientCount == 1 ? '' : 's'} '
          'to ${target.recipientName}?\n\n'
          'The included payment records will lock immediately. Cash remains under '
          'your custody until ${target.recipientName} reviews and accepts the '
          'remittance. Acceptance adopts the existing records without copying a '
          'second payment.',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(context).pop(false),
            child: const Text('Cancel'),
          ),
          FilledButton(
            key: const Key('confirm-cross-remittance'),
            onPressed: () => Navigator.of(context).pop(true),
            child: const Text('Submit and notify'),
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
      final record = await _repository.submit(
        widget.session,
        deviceId: deviceId,
        recipientUserId: recipientId,
        collectionDate: _collectionDate,
        note: _noteController.text,
      );
      if (mounted) {
        setState(() => _submitted = record);
      }
    } on SpinaApiException catch (error) {
      if (mounted) {
        setState(() => _errorMessage = error.message);
      }
    } on Object {
      if (mounted) {
        setState(() {
          _errorMessage = 'The assigned-collector remittance could not be submitted.';
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
      appBar: AppBar(
        title: const Text('Assigned Collector Remittance'),
        actions: [
          IconButton(
            tooltip: 'Refresh',
            onPressed: _loading || _submitted != null ? null : _loadTargets,
            icon: const Icon(Icons.refresh),
          ),
        ],
      ),
      body: SafeArea(
        child: _submitted != null
            ? _SubmittedCrossRemittance(record: _submitted!)
            : _buildReview(context),
      ),
    );
  }

  Widget _buildReview(BuildContext context) {
    if (_loading && _targets.isEmpty) {
      return const Center(child: CircularProgressIndicator());
    }
    if (_targets.isEmpty) {
      return _EmptyCrossRemittance(
        message: _errorMessage ??
            'No unlocked other-area payment is waiting to be remitted to an assigned collector for this date.',
        onRetry: _loadTargets,
      );
    }

    final summary = _summary;
    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        const Card(
          child: Padding(
            padding: EdgeInsets.all(14),
            child: Text(
              'This list contains only payments you recorded for another collector’s assigned clients. It does not mix your regular route cash.',
            ),
          ),
        ),
        const SizedBox(height: 12),
        DropdownButtonFormField<String>(
          key: const Key('cross-remittance-recipient'),
          initialValue: _selectedRecipientId,
          decoration: const InputDecoration(
            labelText: 'Assigned collector',
            border: OutlineInputBorder(),
          ),
          items: [
            for (final target in _targets)
              DropdownMenuItem<String>(
                value: target.recipientUserId,
                child: Text(
                  '${target.recipientName} • ${_money(target.totalAmount)}',
                ),
              ),
          ],
          onChanged: _submitting
              ? null
              : (value) {
                  if (value != null) {
                    _loadPreview(value);
                  }
                },
        ),
        const SizedBox(height: 12),
        if (_loading && summary == null)
          const Center(child: CircularProgressIndicator())
        else if (summary != null) ...[
          _CrossSummaryCard(summary: summary),
          const SizedBox(height: 12),
          TextField(
            key: const Key('cross-remittance-note'),
            controller: _noteController,
            enabled: !_submitting,
            maxLines: 2,
            decoration: const InputDecoration(
              labelText: 'Handover note (optional)',
              border: OutlineInputBorder(),
            ),
          ),
          const SizedBox(height: 16),
          Text(
            'Payments for review',
            style: Theme.of(context).textTheme.titleMedium,
          ),
          const SizedBox(height: 8),
          for (final item in summary.items)
            Card(
              child: ListTile(
                title: Text(item.clientName),
                subtitle: Text(
                  '${item.receiptNumber}\n'
                  '${item.coveredDates.map(_date).join(', ')}',
                ),
                trailing: Text(
                  _money(item.amount),
                  style: const TextStyle(fontWeight: FontWeight.bold),
                ),
              ),
            ),
          if (_errorMessage != null) ...[
            const SizedBox(height: 8),
            Text(
              _errorMessage!,
              style: TextStyle(color: Theme.of(context).colorScheme.error),
            ),
          ],
          const SizedBox(height: 16),
          FilledButton.icon(
            key: const Key('submit-cross-remittance'),
            onPressed:
                _submitting || summary.items.isEmpty ? null : _submit,
            icon: _submitting
                ? const SizedBox(
                    width: 18,
                    height: 18,
                    child: CircularProgressIndicator(strokeWidth: 2),
                  )
                : const Icon(Icons.send_outlined),
            label: Text(
              _submitting
                  ? 'Submitting...'
                  : 'Send ${_money(summary.totalAmount)} for review',
            ),
          ),
        ],
      ],
    );
  }
}

class _CrossSummaryCard extends StatelessWidget {
  const _CrossSummaryCard({required this.summary});

  final RemittanceSummary summary;

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              'Cash to assigned collector: ${_money(summary.totalAmount)}',
              style: Theme.of(context).textTheme.titleLarge,
            ),
            const SizedBox(height: 6),
            Text('${summary.clientCount} clients'),
            Text('${summary.transactionCount} official payment records'),
          ],
        ),
      ),
    );
  }
}

class _SubmittedCrossRemittance extends StatelessWidget {
  const _SubmittedCrossRemittance({required this.record});

  final RemittanceRecord record;

  @override
  Widget build(BuildContext context) {
    return ListView(
      padding: const EdgeInsets.all(24),
      children: [
        const Icon(Icons.mark_email_unread_outlined, size: 60),
        const SizedBox(height: 12),
        Text(
          'Assigned collector notified',
          textAlign: TextAlign.center,
          style: Theme.of(context).textTheme.headlineSmall,
        ),
        const SizedBox(height: 8),
        Text(
          record.remittanceNumber,
          textAlign: TextAlign.center,
          style: Theme.of(context).textTheme.titleMedium,
        ),
        const SizedBox(height: 18),
        Card(
          child: Padding(
            padding: const EdgeInsets.all(16),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text('Assigned collector: ${record.recipientName}'),
                Text('Total: ${_money(record.summary.totalAmount)}'),
                Text('Clients: ${record.summary.clientCount}'),
                const Text('Status: Awaiting review and acceptance'),
              ],
            ),
          ),
        ),
        const SizedBox(height: 12),
        const Text(
          'The payments are locked. Cash stays under your custody until the assigned collector accepts the remittance. Acceptance uses the same official payment records and creates no duplicate.',
          textAlign: TextAlign.center,
        ),
        const SizedBox(height: 18),
        FilledButton(
          onPressed: () => Navigator.of(context).pop(true),
          child: const Text('Done'),
        ),
      ],
    );
  }
}

class _EmptyCrossRemittance extends StatelessWidget {
  const _EmptyCrossRemittance({required this.message, required this.onRetry});

  final String message;
  final VoidCallback onRetry;

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(24),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const Icon(Icons.inbox_outlined, size: 48),
            const SizedBox(height: 12),
            Text(message, textAlign: TextAlign.center),
            const SizedBox(height: 16),
            FilledButton.icon(
              onPressed: onRetry,
              icon: const Icon(Icons.refresh),
              label: const Text('Refresh'),
            ),
          ],
        ),
      ),
    );
  }
}

String _date(DateTime value) {
  return '${value.year.toString().padLeft(4, '0')}-'
      '${value.month.toString().padLeft(2, '0')}-'
      '${value.day.toString().padLeft(2, '0')}';
}

String _money(double value) => '₱${value.toStringAsFixed(2)}';
