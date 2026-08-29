import 'package:flutter/material.dart';
import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/device/device_identity.dart';
import 'package:gilbic_mobile/src/core/management/collection_void.dart';
import 'package:gilbic_mobile/src/core/management/collection_void_repository.dart';
import 'package:gilbic_mobile/src/core/network/spina_api.dart';
import 'package:gilbic_mobile/src/features/management/review/management_review.dart';

class ManagementCollectionVoidPage extends StatefulWidget {
  const ManagementCollectionVoidPage({
    required this.session,
    required this.deviceIdentityProvider,
    this.repository,
    super.key,
  });

  final UserSession session;
  final DeviceIdentityProvider deviceIdentityProvider;
  final ManagementCollectionVoidRepository? repository;

  @override
  State<ManagementCollectionVoidPage> createState() =>
      _ManagementCollectionVoidPageState();
}

class _ManagementCollectionVoidPageState
    extends State<ManagementCollectionVoidPage> {
  late final ManagementCollectionVoidRepository _repository;
  final TextEditingController _receiptController = TextEditingController();
  final TextEditingController _reasonController = TextEditingController();

  String? _deviceId;
  String? _errorMessage;
  ManagementCollectionVoidCandidate? _candidate;
  ManagementCollectionVoidResult? _result;
  bool _searching = false;
  bool _submitting = false;

  @override
  void initState() {
    super.initState();
    _repository =
        widget.repository ?? SpinaManagementCollectionVoidRepository();
    _loadDevice();
  }

  @override
  void dispose() {
    _receiptController.dispose();
    _reasonController.dispose();
    super.dispose();
  }

  Future<void> _loadDevice() async {
    try {
      final identity = await widget.deviceIdentityProvider.load();
      if (mounted) {
        setState(() => _deviceId = identity.installationId);
      }
    } on Object {
      if (mounted) {
        setState(() {
          _errorMessage = 'This device could not be verified. Sign in again.';
        });
      }
    }
  }

  Future<void> _search() async {
    if (_searching || _submitting) {
      return;
    }
    final receipt = _receiptController.text.trim().toUpperCase();
    if (receipt.isEmpty) {
      setState(() => _errorMessage = 'Enter the receipt number to review.');
      return;
    }
    var deviceId = _deviceId;
    if (deviceId == null) {
      await _loadDevice();
      deviceId = _deviceId;
    }
    if (deviceId == null || !mounted) {
      return;
    }

    setState(() {
      _searching = true;
      _errorMessage = null;
      _candidate = null;
      _result = null;
    });
    try {
      final candidate = await _repository.findByReceipt(
        widget.session,
        deviceId: deviceId,
        receiptNumber: receipt,
      );
      if (mounted) {
        setState(() => _candidate = candidate);
      }
    } on SpinaApiException catch (error) {
      if (mounted) {
        setState(() => _errorMessage = error.message);
      }
    } on Object {
      if (mounted) {
        setState(() {
          _errorMessage =
              'The receipt could not be loaded. Refresh and try again.';
        });
      }
    } finally {
      if (mounted) {
        setState(() => _searching = false);
      }
    }
  }

  Future<void> _voidCollection() async {
    final candidate = _candidate;
    final deviceId = _deviceId;
    final reason = _reasonController.text.trim();
    if (candidate == null || deviceId == null || _submitting) {
      return;
    }
    if (reason.length < 3) {
      setState(() {
        _errorMessage = 'Enter a clear reason for voiding this collection.';
      });
      return;
    }

    final review = ManagementReviewPresentation.validated(
      surface: ManagementMutationSurface.collectionVoid,
      recordLabel: 'Official receipt',
      recordValue: '${candidate.receiptNumber} • ${candidate.clientName}',
      statusLabel: 'Eligible unlocked and unremitted collection',
      statusDetail:
          'The server returned this collection as eligible for a protected void.',
      facts: <ManagementReviewFact>[
        ManagementReviewFact(label: 'Amount', value: _money(candidate.amount)),
        ManagementReviewFact(
          label: 'Collector',
          value: candidate.collectorName,
        ),
        ManagementReviewFact(
          label: 'Collection date',
          value: candidate.collectionDate == null
              ? 'Not recorded by the server'
              : _date(candidate.collectionDate!),
        ),
        ManagementReviewFact(
          label: 'Current official balance',
          value: _money(candidate.officialBalance),
        ),
      ],
      nextActionLabel: 'Void collection',
      consequence:
          'The receipt will be voided, the official balance will be restored, '
          'and permanent audit evidence will be retained.',
      risk: ManagementReviewRisk.protectedFinancial,
      secondaryReferences: <ManagementReviewFact>[
        ManagementReviewFact(
          label: 'Transaction ID',
          value: candidate.transactionId,
        ),
      ],
    );
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Void this collection?'),
        content: SingleChildScrollView(
          child: ManagementReviewPanel(review: review, compact: true),
        ),
        actions: [
          TextButton(
            key: const Key('cancel-collection-void'),
            onPressed: () => Navigator.of(context).pop(false),
            child: const Text('Cancel'),
          ),
          FilledButton(
            key: const Key('confirm-management-collection-void'),
            onPressed: () => Navigator.of(context).pop(true),
            child: const Text('Void collection'),
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
      final result = await _repository.voidCollection(
        widget.session,
        deviceId: deviceId,
        transactionId: candidate.transactionId,
        reason: reason,
      );
      if (!mounted) {
        return;
      }
      setState(() {
        _result = result;
        _candidate = null;
        _reasonController.clear();
      });
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(
            '${result.receiptNumber} was voided. Balance restored to '
            '${_money(result.restoredBalance)}.',
          ),
        ),
      );
    } on SpinaApiException catch (error) {
      if (mounted) {
        setState(() => _errorMessage = error.message);
      }
    } on Object {
      if (mounted) {
        setState(() {
          _errorMessage =
              'The collection could not be voided. Refresh and try again.';
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
    final candidate = _candidate;
    final result = _result;
    return Scaffold(
      appBar: AppBar(title: const Text('Void Incorrect Payment')),
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
                      'Management-only audited correction',
                      style: Theme.of(context).textTheme.titleMedium,
                    ),
                    const SizedBox(height: 6),
                    const Text(
                      'Use this only when an unlocked payment was posted to the '
                      'wrong borrower or should not have been recorded. Remitted '
                      'entries cannot be voided here.',
                    ),
                  ],
                ),
              ),
            ),
            const SizedBox(height: 12),
            TextField(
              key: const Key('management-void-receipt'),
              controller: _receiptController,
              enabled: !_searching && !_submitting,
              textCapitalization: TextCapitalization.characters,
              textInputAction: TextInputAction.search,
              onSubmitted: (_) => _search(),
              decoration: InputDecoration(
                labelText: 'Receipt number',
                hintText: 'GBC-YYYYMMDD-00000000',
                border: const OutlineInputBorder(),
                prefixIcon: const Icon(Icons.receipt_long),
                suffixIcon: IconButton(
                  key: const Key('management-void-search'),
                  tooltip: 'Find receipt',
                  onPressed: _searching || _submitting ? null : _search,
                  icon: _searching
                      ? const SizedBox.square(
                          dimension: 20,
                          child: CircularProgressIndicator(strokeWidth: 2),
                        )
                      : const Icon(Icons.search),
                ),
              ),
            ),
            if (_errorMessage != null) ...[
              const SizedBox(height: 12),
              Card(
                child: Padding(
                  padding: const EdgeInsets.all(12),
                  child: Text(
                    _errorMessage!,
                    key: const Key('management-void-error'),
                    style: TextStyle(
                      color: Theme.of(context).colorScheme.error,
                    ),
                  ),
                ),
              ),
            ],
            if (result != null) ...[
              const SizedBox(height: 12),
              Card(
                key: const Key('management-void-success'),
                child: Padding(
                  padding: const EdgeInsets.all(16),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Row(
                        children: [
                          const Icon(Icons.check_circle_outline),
                          const SizedBox(width: 8),
                          Text(
                            'Collection voided',
                            style: Theme.of(context).textTheme.titleMedium,
                          ),
                        ],
                      ),
                      const SizedBox(height: 8),
                      Text('Receipt: ${result.receiptNumber}'),
                      Text('Client: ${result.clientName}'),
                      Text(
                        'Restored balance: ${_money(result.restoredBalance)}',
                      ),
                      Text('Audit state version: ${result.stateVersion}'),
                    ],
                  ),
                ),
              ),
            ],
            if (candidate != null) ...[
              const SizedBox(height: 12),
              _CandidateCard(candidate: candidate),
              const SizedBox(height: 12),
              TextField(
                key: const Key('management-void-reason'),
                controller: _reasonController,
                enabled: !_submitting,
                minLines: 2,
                maxLines: 4,
                maxLength: 500,
                decoration: const InputDecoration(
                  labelText: 'Required void reason',
                  hintText: 'Example: Payment posted to the wrong borrower',
                  helperText:
                      'This reason is saved permanently in the audit log.',
                  border: OutlineInputBorder(),
                ),
              ),
              const SizedBox(height: 8),
              FilledButton.icon(
                key: const Key('submit-management-collection-void'),
                onPressed: _submitting ? null : _voidCollection,
                icon: _submitting
                    ? const SizedBox.square(
                        dimension: 18,
                        child: CircularProgressIndicator(strokeWidth: 2),
                      )
                    : const Icon(Icons.block),
                label: Text(
                  _submitting ? 'Voiding...' : 'Void incorrect collection',
                ),
              ),
            ],
          ],
        ),
      ),
    );
  }
}

class _CandidateCard extends StatelessWidget {
  const _CandidateCard({required this.candidate});

  final ManagementCollectionVoidCandidate candidate;

  @override
  Widget build(BuildContext context) {
    final date = candidate.collectionDate;
    final dateText = date == null
        ? ''
        : '${date.year.toString().padLeft(4, '0')}-'
              '${date.month.toString().padLeft(2, '0')}-'
              '${date.day.toString().padLeft(2, '0')}';
    return Card(
      key: const Key('management-void-candidate'),
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              candidate.clientName,
              style: Theme.of(context).textTheme.titleLarge,
            ),
            Text('${candidate.clientCode} • ${candidate.loanType}'),
            const Divider(height: 24),
            Text('Receipt: ${candidate.receiptNumber}'),
            Text('Recorded by: ${candidate.collectorName}'),
            if (dateText.isNotEmpty) Text('Collection date: $dateText'),
            Text('Type: ${_entryType(candidate.entryType)}'),
            Text('Amount: ${_money(candidate.amount)}'),
            if (candidate.coveredDates.isNotEmpty)
              Text('Covered dates: ${candidate.coveredDates.join(', ')}'),
            const SizedBox(height: 8),
            Text('Balance before entry: ${_money(candidate.previousBalance)}'),
            Text('Balance after entry: ${_money(candidate.officialBalance)}'),
          ],
        ),
      ),
    );
  }
}

String _entryType(String value) {
  return switch (value.trim().toLowerCase()) {
    'advance' => 'Covered-date payment',
    'pass' => 'Unable to pay',
    _ => 'Payment',
  };
}

String _money(double value) => '₱${value.toStringAsFixed(2)}';

String _date(DateTime value) {
  return '${value.year.toString().padLeft(4, '0')}-'
      '${value.month.toString().padLeft(2, '0')}-'
      '${value.day.toString().padLeft(2, '0')}';
}
