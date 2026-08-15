import 'package:flutter/material.dart';
import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/device/device_identity.dart';
import 'package:gilbic_mobile/src/core/network/spina_api.dart';
import 'package:gilbic_mobile/src/core/payments/client_payment.dart';
import 'package:gilbic_mobile/src/core/payments/client_payment_repository.dart';
import 'package:gilbic_mobile/src/features/client/client_gcash_payment_page.dart';
import 'package:gilbic_mobile/src/theme/spina_theme.dart';

class ClientPaymentsPage extends StatefulWidget {
  const ClientPaymentsPage({
    required this.session,
    required this.deviceIdentityProvider,
    this.repository,
    super.key,
  });

  final UserSession session;
  final DeviceIdentityProvider deviceIdentityProvider;
  final ClientPaymentRepository? repository;

  @override
  State<ClientPaymentsPage> createState() => _ClientPaymentsPageState();
}

class _ClientPaymentsPageState extends State<ClientPaymentsPage> {
  late final ClientPaymentRepository _repository;
  ClientPaymentTimeline? _timeline;
  String? _errorMessage;
  bool _loading = true;

  @override
  void initState() {
    super.initState();
    _repository = widget.repository ?? SpinaClientPaymentRepository();
    _load();
  }

  Future<void> _load() async {
    setState(() {
      _loading = true;
      _errorMessage = null;
    });
    try {
      final identity = await widget.deviceIdentityProvider.load();
      final timeline = await _repository.loadTimeline(
        widget.session,
        deviceId: identity.installationId,
      );
      if (!mounted) {
        return;
      }
      setState(() => _timeline = timeline);
    } on SpinaApiException catch (error) {
      if (mounted) {
        setState(() => _errorMessage = error.message);
      }
    } on Object {
      if (mounted) {
        setState(() => _errorMessage = 'Payments could not be loaded.');
      }
    } finally {
      if (mounted) {
        setState(() => _loading = false);
      }
    }
  }

  void _openGcash() {
    Navigator.of(context).push<void>(
      MaterialPageRoute<void>(
        builder: (_) => ClientGcashPaymentPage(
          session: widget.session,
          deviceIdentityProvider: widget.deviceIdentityProvider,
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Payments'),
        actions: [
          IconButton(
            tooltip: 'Refresh',
            onPressed: _loading ? null : _load,
            icon: const Icon(Icons.refresh),
          ),
        ],
      ),
      body: SafeArea(child: _buildBody(context)),
    );
  }

  Widget _buildBody(BuildContext context) {
    final timeline = _timeline;
    if (_loading && timeline == null) {
      return const Center(child: CircularProgressIndicator());
    }
    if (_errorMessage != null && timeline == null) {
      return Center(
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              const Icon(Icons.receipt_long_outlined, size: 48),
              const SizedBox(height: 12),
              Text(_errorMessage!, textAlign: TextAlign.center),
              const SizedBox(height: 16),
              FilledButton.icon(
                onPressed: _load,
                icon: const Icon(Icons.refresh),
                label: const Text('Try again'),
              ),
            ],
          ),
        ),
      );
    }
    if (timeline == null) {
      return const SizedBox.shrink();
    }

    final voidedCount =
        timeline.payments.where((payment) => payment.isVoided).length;
    return RefreshIndicator(
      onRefresh: _load,
      child: ListView(
        physics: const AlwaysScrollableScrollPhysics(),
        padding: const EdgeInsets.fromLTRB(16, 16, 16, 28),
        children: [
          if (_errorMessage != null)
            Card(
              child: Padding(
                padding: const EdgeInsets.all(12),
                child: Text(_errorMessage!),
              ),
            ),
          Card(
            child: Padding(
              padding: const EdgeInsets.all(16),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    timeline.clientName,
                    style: Theme.of(context).textTheme.titleLarge,
                  ),
                  const SizedBox(height: 2),
                  Text(timeline.clientCode),
                  const Divider(height: 24),
                  _SummaryRow(
                    label: 'Valid payments',
                    value: '${timeline.validPayments.length}',
                  ),
                  _SummaryRow(
                    label: 'Total recorded',
                    value: _money(timeline.validTotal),
                  ),
                  if (voidedCount > 0)
                    _SummaryRow(
                      label: 'Voided receipts',
                      value: '$voidedCount',
                    ),
                ],
              ),
            ),
          ),
          const SizedBox(height: 12),
          Container(
            key: const Key('client-gcash-entry-card'),
            padding: const EdgeInsets.all(16),
            decoration: BoxDecoration(
              gradient: const LinearGradient(
                colors: <Color>[Color(0xFFFFFBFD), Color(0xFFFFEEF5)],
              ),
              borderRadius: BorderRadius.circular(20),
              border: Border.all(color: const Color(0xFFF0D6E1)),
            ),
            child: Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Container(
                  width: 44,
                  height: 44,
                  decoration: BoxDecoration(
                    color: Colors.white,
                    borderRadius: BorderRadius.circular(14),
                  ),
                  child: const Icon(
                    Icons.account_balance_wallet_rounded,
                    color: SpinaTheme.brandPinkDark,
                  ),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        'Pay directly with GCash',
                        style: Theme.of(context).textTheme.titleMedium,
                      ),
                      const SizedBox(height: 4),
                      const Text(
                        'Choose your active loan, review the amount, then continue to the connected GCash business checkout.',
                      ),
                      const SizedBox(height: 10),
                      FilledButton.tonalIcon(
                        key: const Key('open-client-gcash-payment'),
                        onPressed: _openGcash,
                        icon: const Icon(Icons.arrow_forward_rounded),
                        label: const Text('Open GCash payment'),
                      ),
                    ],
                  ),
                ),
              ],
            ),
          ),
          const SizedBox(height: 12),
          Card(
            child: Padding(
              padding: const EdgeInsets.all(14),
              child: Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Icon(
                    timeline.proofUploadAvailable
                        ? Icons.upload_file_outlined
                        : Icons.verified_user_outlined,
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          'Payment proof',
                          style: Theme.of(context).textTheme.titleSmall,
                        ),
                        const SizedBox(height: 4),
                        Text(timeline.proofMessage),
                      ],
                    ),
                  ),
                ],
              ),
            ),
          ),
          const SizedBox(height: 18),
          Row(
            children: [
              Text(
                'Payment timeline',
                style: Theme.of(context).textTheme.titleMedium,
              ),
              const Spacer(),
              Text('${timeline.payments.length} receipts'),
            ],
          ),
          const SizedBox(height: 8),
          if (timeline.payments.isEmpty)
            const Card(
              child: Padding(
                padding: EdgeInsets.all(24),
                child: Text(
                  'No recorded payments yet.',
                  textAlign: TextAlign.center,
                ),
              ),
            )
          else
            for (final payment in timeline.payments) ...[
              _PaymentCard(payment: payment),
              const SizedBox(height: 10),
            ],
        ],
      ),
    );
  }
}

class _PaymentCard extends StatelessWidget {
  const _PaymentCard({required this.payment});

  final ClientPayment payment;

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    final statusColor = switch (payment.status.toLowerCase()) {
      'accepted' => scheme.primaryContainer,
      'remitted' => scheme.secondaryContainer,
      'voided' => scheme.errorContainer,
      _ => scheme.surfaceContainerHighest,
    };
    return Card(
      key: Key('client-payment-${payment.transactionId}'),
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Icon(Icons.receipt_long_outlined),
                const SizedBox(width: 10),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        payment.loanTypeName,
                        style: Theme.of(context).textTheme.titleMedium,
                      ),
                      Text(payment.loanNumber),
                    ],
                  ),
                ),
                Container(
                  padding:
                      const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
                  decoration: BoxDecoration(
                    color: statusColor,
                    borderRadius: BorderRadius.circular(10),
                  ),
                  child: Text(payment.statusLabel),
                ),
              ],
            ),
            const SizedBox(height: 12),
            Text(
              _money(payment.amount),
              style: Theme.of(context).textTheme.headlineSmall,
            ),
            const SizedBox(height: 6),
            Text('Receipt: ${payment.receiptNumber}'),
            Text('Collection date: ${_date(payment.collectionDate)}'),
            Text('Recorded by: ${payment.collectorName}'),
            Text('Recorded at: ${_dateTime(payment.recordedAt)}'),
            if (payment.coveredDates.isNotEmpty)
              Text(
                'Covered dates: '
                '${payment.coveredDates.map(_date).join(', ')}',
              ),
            if (payment.previousBalance != null)
              Text('Balance before: ${_money(payment.previousBalance!)}'),
            if (payment.officialBalance != null)
              Text('Balance after: ${_money(payment.officialBalance!)}'),
            if (payment.editVersion > 0)
              Text('Corrected ${payment.editVersion} time(s)'),
            if (payment.remittanceNumber != null) ...[
              const Divider(height: 22),
              Text('Remittance: ${payment.remittanceNumber}'),
              if (payment.remittanceSubmittedAt != null)
                Text(
                  'Remitted at: ${_dateTime(payment.remittanceSubmittedAt!)}',
                ),
              if (payment.remittanceReceivedAt != null)
                Text(
                  'Cash accepted at: '
                  '${_dateTime(payment.remittanceReceivedAt!)}',
                ),
            ],
            if (payment.note != null && payment.note!.isNotEmpty) ...[
              const Divider(height: 22),
              Text('Note: ${payment.note}'),
            ],
            if (payment.isVoided) ...[
              const Divider(height: 22),
              Text(
                'This receipt was voided and does not reduce your balance.',
                style: TextStyle(
                  color: scheme.error,
                  fontWeight: FontWeight.w700,
                ),
              ),
              if (payment.voidReason != null)
                Text('Reason: ${payment.voidReason}'),
              if (payment.voidedAt != null)
                Text('Voided at: ${_dateTime(payment.voidedAt!)}'),
            ],
          ],
        ),
      ),
    );
  }
}

class _SummaryRow extends StatelessWidget {
  const _SummaryRow({required this.label, required this.value});

  final String label;
  final String value;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 3),
      child: Row(
        children: [
          Expanded(child: Text(label)),
          Text(
            value,
            style: const TextStyle(fontWeight: FontWeight.w700),
          ),
        ],
      ),
    );
  }
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
  return '₱$buffer.${parts.last}';
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
