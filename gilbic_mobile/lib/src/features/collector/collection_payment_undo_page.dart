import 'package:flutter/material.dart';
import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/collector/collector_route.dart';
import 'package:gilbic_mobile/src/core/device/device_identity.dart';
import 'package:gilbic_mobile/src/core/network/spina_api.dart';
import 'package:gilbic_mobile/src/core/payments/collection_payment_undo_repository.dart';
import 'package:gilbic_mobile/src/features/collector/collector_failure_guidance.dart';

class CollectionPaymentUndoPage extends StatefulWidget {
  const CollectionPaymentUndoPage({
    required this.session,
    required this.entry,
    required this.repository,
    required this.deviceIdentityProvider,
    this.returnToOtherArea = false,
    super.key,
  });
  final UserSession session;
  final CollectorRouteEntry entry;
  final CollectionPaymentUndoRepository repository;
  final DeviceIdentityProvider deviceIdentityProvider;
  final bool returnToOtherArea;

  @override
  State<CollectionPaymentUndoPage> createState() =>
      _CollectionPaymentUndoPageState();
}

class _CollectionPaymentUndoPageState extends State<CollectionPaymentUndoPage> {
  final _reason = TextEditingController();
  bool _busy = false;
  bool _saved = false;
  String? _pendingReason;
  String? _error;

  @override
  void dispose() {
    _reason.dispose();
    super.dispose();
  }

  Future<void> _undo() async {
    if (_busy || _saved) return;
    final entry = widget.entry;
    final reason = _pendingReason ?? _reason.text.trim();
    if (!entry.canUndoToday ||
        entry.todayIsLocked ||
        entry.todayTransactionId == null ||
        entry.routeRevision == null ||
        !widget.session.permissions.contains(
          'collection.correct.own_unremitted',
        )) {
      setState(
        () => _error = 'Refresh the route before correcting this receipt.',
      );
      return;
    }
    if (reason.length < 3) {
      setState(() => _error = 'Enter a reason for undoing this payment.');
      return;
    }
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      if (_pendingReason == null) {
        final confirmed = await showDialog<bool>(
          context: context,
          builder: (context) => AlertDialog(
            title: const Text('Undo this payment?'),
            content: Text(
              '${entry.clientName} • ${entry.loanType}\nThis removes this receipt from collected cash and restores the loan. The original receipt remains in the audit history.',
            ),
            actions: [
              TextButton(
                onPressed: () => Navigator.pop(context, false),
                child: const Text('Keep payment'),
              ),
              FilledButton(
                key: const Key('confirm-payment-undo'),
                onPressed: () => Navigator.pop(context, true),
                child: const Text('Undo payment'),
              ),
            ],
          ),
        );
        if (confirmed != true || !mounted) return;
        _pendingReason = reason;
      }
      final device = await widget.deviceIdentityProvider.load();
      await widget.repository.undo(
        widget.session,
        deviceId: device.installationId,
        transactionId: entry.todayTransactionId!,
        loanId: entry.loanId,
        expectedRouteRevision: entry.routeRevision!,
        reason: reason,
      );
      if (mounted) {
        setState(() {
          _saved = true;
          _pendingReason = null;
        });
      }
    } on Object catch (error) {
      if (!mounted) return;
      final uncertain =
          error is! SpinaApiException ||
          error.code == 'undo_unconfirmed' ||
          error.statusCode == null ||
          error.statusCode == 429 ||
          error.statusCode! >= 500;
      setState(() {
        if (!uncertain) _pendingReason = null;
        _error = uncertain
            ? 'Undo result is not confirmed. Retry the same undo or return to refresh the route.'
            : collectorFailureMessage(
                error,
                task: CollectorFailureTask.correctCollection,
              );
      });
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) => PopScope(
    canPop: !_busy,
    child: Scaffold(
      appBar: AppBar(title: const Text('Correct mistaken Pay')),
      body: ListView(
        padding: const EdgeInsets.all(20),
        children: [
          Text(
            widget.entry.clientName,
            style: Theme.of(context).textTheme.titleLarge,
          ),
          Text(widget.entry.loanType),
          Text('Payment: ₱${widget.entry.todayAmountInput ?? 'Unavailable'}'),
          for (final receipt in widget.entry.todayReceipts)
            if (receipt.transactionId == widget.entry.todayTransactionId)
              Text('Receipt: ${receipt.receiptNumber}'),
          const SizedBox(height: 16),
          if (_saved) ...[
            const Text('Payment undone', key: Key('payment-undo-saved')),
            const SizedBox(height: 12),
            Text(
              widget.returnToOtherArea
                  ? 'Return to Other Area Payment. If the borrower did not pay, open Record payment and select Unable to pay to record one missed-payment event (+1).'
                  : 'Return to the route. If the borrower did not pay, open Payment details / other amount and select Unable to pay to record one missed-payment event (+1).',
            ),
            const SizedBox(height: 16),
            FilledButton(
              onPressed: () => Navigator.pop(context, true),
              child: Text(
                widget.returnToOtherArea
                    ? 'Return to Other Area Payment'
                    : 'Return to route',
              ),
            ),
          ] else ...[
            const Text(
              'Undo only if this payment was recorded by mistake. The loan balance and collected cash will be restored. This alone does not add a missed-payment event.',
            ),
            const SizedBox(height: 16),
            TextField(
              key: const Key('payment-undo-reason'),
              controller: _reason,
              enabled: !_busy && _pendingReason == null,
              maxLength: 500,
              decoration: const InputDecoration(
                labelText: 'Reason for correction',
              ),
            ),
            if (_error != null)
              Text(_error!, key: const Key('payment-undo-error')),
            const SizedBox(height: 16),
            FilledButton.icon(
              key: const Key('submit-payment-undo'),
              onPressed: _busy ? null : _undo,
              icon: const Icon(Icons.undo),
              label: Text(
                _busy
                    ? 'Checking…'
                    : _pendingReason != null
                    ? 'Retry same undo'
                    : 'Undo mistaken Pay',
              ),
            ),
          ],
        ],
      ),
    ),
  );
}
