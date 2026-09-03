import 'package:flutter/material.dart';
import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/device/device_identity.dart';
import 'package:gilbic_mobile/src/core/network/spina_api.dart';
import 'package:gilbic_mobile/src/core/remittance/remittance.dart';
import 'package:gilbic_mobile/src/core/remittance/remittance_repository.dart';
import 'package:gilbic_mobile/src/features/collector/collector_failure_guidance.dart';
import 'package:gilbic_mobile/src/features/collector/remittance_handover_photo_page.dart';

class CollectorRemittancePage extends StatefulWidget {
  const CollectorRemittancePage({
    required this.session,
    required this.deviceIdentityProvider,
    this.repository,
    this.collectionDate,
    super.key,
  });

  final UserSession session;
  final DeviceIdentityProvider deviceIdentityProvider;
  final RemittanceRepository? repository;
  final DateTime? collectionDate;

  @override
  State<CollectorRemittancePage> createState() =>
      _CollectorRemittancePageState();
}

class _CollectorRemittancePageState extends State<CollectorRemittancePage> {
  late final RemittanceRepository _repository;
  late final TextEditingController _noteController;
  late final DateTime _collectionDate;

  List<RemittanceRecipient> _recipients = const <RemittanceRecipient>[];
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
    _repository = widget.repository ?? SpinaRemittanceRepository();
    _noteController = TextEditingController();
    final source = widget.collectionDate ?? DateTime.now();
    _collectionDate = DateTime(source.year, source.month, source.day);
    _load();
  }

  @override
  void dispose() {
    _noteController.dispose();
    super.dispose();
  }

  Future<void> _load() async {
    setState(() {
      _loading = true;
      _errorMessage = null;
    });
    try {
      final identity = await widget.deviceIdentityProvider.load();
      final recipients = await _repository.loadRecipients(
        widget.session,
        deviceId: identity.installationId,
      );
      final summary = await _repository.loadPreview(
        widget.session,
        deviceId: identity.installationId,
        collectionDate: _collectionDate,
      );
      if (!mounted) {
        return;
      }
      setState(() {
        _deviceId = identity.installationId;
        _recipients = recipients;
        _summary = summary;
        if (_selectedRecipientId == null ||
            !recipients.any(
              (recipient) => recipient.userId == _selectedRecipientId,
            )) {
          _selectedRecipientId = recipients.isEmpty
              ? null
              : recipients.first.userId;
        }
      });
    } on SpinaApiException catch (error) {
      if (mounted) {
        setState(() {
          _errorMessage = collectorFailureMessage(
            error,
            task: CollectorFailureTask.loadRemittance,
          );
        });
      }
    } on Object catch (error) {
      if (mounted) {
        setState(() {
          _errorMessage = collectorFailureMessage(
            error,
            task: CollectorFailureTask.loadRemittance,
          );
        });
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
    if (_submitting || summary == null || deviceId == null) {
      return;
    }
    if (summary.items.isEmpty) {
      setState(() {
        _errorMessage = 'There are no unlocked entries available to remit.';
      });
      return;
    }
    if (recipientId == null) {
      setState(() {
        _errorMessage = 'Choose the person receiving the remittance.';
      });
      return;
    }
    final recipient = _recipients.firstWhere(
      (item) => item.userId == recipientId,
    );

    final confirmed = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Submit remittance?'),
        content: Text(
          'Prepare ${_money(summary.totalAmount)} for ${recipient.fullName}?\n\n'
          '${summary.clientCount} clients • ${summary.transactionCount} entries\n\n'
          'After submission, the included entries are permanently locked and '
          '${recipient.fullName} receives an Accept Remittance notification. '
          'The cash remains under your custody until that notification is accepted.',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(context).pop(false),
            child: const Text('Review again'),
          ),
          FilledButton(
            key: const Key('confirm-remittance-submission'),
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
        setState(() {
          _errorMessage = collectorFailureMessage(
            error,
            task: CollectorFailureTask.submitRemittance,
          );
        });
      }
    } on Object catch (error) {
      if (mounted) {
        setState(() {
          _errorMessage = collectorFailureMessage(
            error,
            task: CollectorFailureTask.submitRemittance,
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
      appBar: AppBar(
        title: const Text('Remittance'),
        actions: [
          IconButton(
            tooltip: 'Refresh summary',
            onPressed: _loading || _submitted != null ? null : _load,
            icon: const Icon(Icons.refresh),
          ),
        ],
      ),
      body: SafeArea(
        child: _loading && _summary == null
            ? const Center(child: CircularProgressIndicator())
            : _submitted != null
            ? _SubmittedRemittance(
                record: _submitted!,
                session: widget.session,
                deviceIdentityProvider: widget.deviceIdentityProvider,
              )
            : _buildReview(context),
      ),
    );
  }

  Widget _buildReview(BuildContext context) {
    final summary = _summary;
    if (summary == null) {
      return _ErrorView(message: _errorMessage, onRetry: _load);
    }
    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        _SummaryCard(summary: summary),
        const SizedBox(height: 12),
        DropdownButtonFormField<String>(
          key: const Key('remittance-recipient'),
          initialValue: _selectedRecipientId,
          decoration: const InputDecoration(
            labelText: 'Remit to',
            border: OutlineInputBorder(),
          ),
          items: [
            for (final recipient in _recipients)
              DropdownMenuItem<String>(
                value: recipient.userId,
                child: Text('${recipient.fullName} • ${recipient.roleName}'),
              ),
          ],
          onChanged: _submitting
              ? null
              : (value) => setState(() => _selectedRecipientId = value),
        ),
        if (_recipients.isEmpty) ...[
          const SizedBox(height: 8),
          const Text(
            'No authorized employee or management recipient is available.',
          ),
        ],
        const SizedBox(height: 12),
        TextField(
          key: const Key('remittance-note'),
          controller: _noteController,
          enabled: !_submitting,
          maxLines: 2,
          decoration: const InputDecoration(
            labelText: 'Remittance note (optional)',
            border: OutlineInputBorder(),
          ),
        ),
        const SizedBox(height: 16),
        Text(
          'Included entries',
          style: Theme.of(context).textTheme.titleMedium,
        ),
        const SizedBox(height: 8),
        if (summary.items.isEmpty)
          const Card(
            child: Padding(
              padding: EdgeInsets.all(18),
              child: Text(
                'No unlocked collection entries are available for this date.',
              ),
            ),
          )
        else
          for (final item in summary.items) _RemittanceItemTile(item: item),
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
          key: const Key('submit-remittance'),
          onPressed:
              _submitting ||
                  summary.items.isEmpty ||
                  _selectedRecipientId == null
              ? null
              : _submit,
          icon: _submitting
              ? const SizedBox(
                  width: 18,
                  height: 18,
                  child: CircularProgressIndicator(strokeWidth: 2),
                )
              : const Icon(Icons.notifications_active_outlined),
          label: Text(
            _submitting
                ? 'Submitting...'
                : 'Submit ${_money(summary.totalAmount)} and notify recipient',
          ),
        ),
        const SizedBox(height: 8),
        Text(
          'The server recalculates all totals. Submission locks the entries, but cash custody transfers only after the selected recipient accepts the notification.',
          textAlign: TextAlign.center,
          style: Theme.of(context).textTheme.bodySmall,
        ),
      ],
    );
  }
}

class _SummaryCard extends StatelessWidget {
  const _SummaryCard({required this.summary});

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
              summary.collectorName,
              style: Theme.of(context).textTheme.titleLarge,
            ),
            Text(_date(summary.collectionDate ?? DateTime.now())),
            const Divider(height: 24),
            Text(
              'Cash to remit: ${_money(summary.totalAmount)}',
              style: Theme.of(
                context,
              ).textTheme.titleLarge?.copyWith(fontWeight: FontWeight.w800),
            ),
            const SizedBox(height: 8),
            Wrap(
              spacing: 14,
              runSpacing: 6,
              children: [
                Text('${summary.clientCount} clients'),
                Text('${summary.transactionCount} entries'),
                Text('${summary.paymentCount} payments'),
                Text('${summary.coveredPaymentCount} covered'),
                Text('${summary.unableToPayCount} unable to pay'),
              ],
            ),
          ],
        ),
      ),
    );
  }
}

class _RemittanceItemTile extends StatelessWidget {
  const _RemittanceItemTile({required this.item});

  final RemittanceItem item;

  @override
  Widget build(BuildContext context) {
    final unable = item.entryType == 'pass';
    return Card(
      child: ListTile(
        dense: true,
        title: Text(item.clientName),
        subtitle: Text(
          '${item.loanType} • ${_entryLabel(item.entryType)}'
          '${item.coveredDates.isEmpty ? '' : '\nDates: ${item.coveredDates.map(_date).join(', ')}'}'
          '${item.note.isEmpty ? '' : '\nNote: ${item.note}'}',
        ),
        trailing: Text(
          unable ? '₱0.00' : _money(item.amount),
          style: Theme.of(
            context,
          ).textTheme.labelLarge?.copyWith(fontWeight: FontWeight.w800),
        ),
      ),
    );
  }
}

class _SubmittedRemittance extends StatelessWidget {
  const _SubmittedRemittance({
    required this.record,
    required this.session,
    required this.deviceIdentityProvider,
  });

  final RemittanceRecord record;
  final UserSession session;
  final DeviceIdentityProvider deviceIdentityProvider;

  Future<void> _openPhoto(BuildContext context) async {
    final saved = await Navigator.of(context).push<bool>(
      MaterialPageRoute<bool>(
        builder: (context) => RemittanceHandoverPhotoPage(
          session: session,
          remittance: record,
          deviceIdentityProvider: deviceIdentityProvider,
        ),
      ),
    );
    if (saved == true && context.mounted) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text(
            'Handover photo saved. The recipient can view it before accepting.',
          ),
        ),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    return ListView(
      padding: const EdgeInsets.all(20),
      children: [
        const Icon(Icons.notifications_active, size: 58),
        const SizedBox(height: 12),
        Text(
          'Remittance notification sent',
          textAlign: TextAlign.center,
          style: Theme.of(context).textTheme.headlineSmall,
        ),
        const SizedBox(height: 8),
        Text(
          record.remittanceNumber,
          textAlign: TextAlign.center,
          style: Theme.of(context).textTheme.titleMedium,
        ),
        const SizedBox(height: 20),
        Card(
          child: Padding(
            padding: const EdgeInsets.all(16),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text('Recipient: ${record.recipientName}'),
                Text('Total: ${_money(record.summary.totalAmount)}'),
                Text('Clients: ${record.summary.clientCount}'),
                Text('Entries: ${record.summary.transactionCount}'),
                Text('Status: Waiting for ${record.recipientName} to accept'),
              ],
            ),
          ),
        ),
        const SizedBox(height: 12),
        const Text(
          'The collection entries are locked, but the cash is still under your custody. Custody transfers to the selected recipient only after they tap Accept Remittance.',
          textAlign: TextAlign.center,
        ),
        const SizedBox(height: 18),
        OutlinedButton.icon(
          key: const Key('add-handover-photo'),
          onPressed: () => _openPhoto(context),
          icon: const Icon(Icons.add_a_photo_outlined),
          label: const Text('Add Handover Photo'),
        ),
        const SizedBox(height: 10),
        FilledButton(
          onPressed: () => Navigator.of(context).pop(true),
          child: const Text('Done'),
        ),
      ],
    );
  }
}

class _ErrorView extends StatelessWidget {
  const _ErrorView({required this.message, required this.onRetry});

  final String? message;
  final VoidCallback onRetry;

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(24),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const Icon(Icons.error_outline, size: 48),
            const SizedBox(height: 12),
            Text(message ?? 'The remittance could not be loaded.'),
            const SizedBox(height: 16),
            FilledButton.icon(
              onPressed: onRetry,
              icon: const Icon(Icons.refresh),
              label: const Text('Try again'),
            ),
          ],
        ),
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

String _money(double value) => '₱${value.toStringAsFixed(2)}';
