import 'package:flutter/material.dart';
import 'package:gilbic_mobile/src/core/collector/collector_route.dart';
import 'package:gilbic_mobile/src/core/collector/collector_route_grouping.dart';

typedef CollectorClientToolReason = String? Function(CollectorRouteEntry entry);

enum CollectorClientToolKind {
  paymentDetails,
  correction,
  schedule,
  collectionLocation,
}

class CollectorClientToolSelection {
  const CollectorClientToolSelection(this.kind, {this.entry});

  final CollectorClientToolKind kind;
  final CollectorRouteEntry? entry;
}

class CollectorClientToolsSheet extends StatelessWidget {
  const CollectorClientToolsSheet({
    required this.client,
    required this.directPayBlockedReasonFor,
    required this.detailsBlockedReasonFor,
    required this.correctionBlockedReasonFor,
    super.key,
  });

  final CollectorRouteClientGroup client;
  final CollectorClientToolReason directPayBlockedReasonFor;
  final CollectorClientToolReason detailsBlockedReasonFor;
  final CollectorClientToolReason correctionBlockedReasonFor;

  @override
  Widget build(BuildContext context) {
    return SafeArea(
      child: SingleChildScrollView(
        padding: const EdgeInsets.fromLTRB(16, 10, 16, 20),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Center(
              child: Container(
                width: 42,
                height: 4,
                decoration: BoxDecoration(
                  color: Theme.of(context).colorScheme.outlineVariant,
                  borderRadius: BorderRadius.circular(999),
                ),
              ),
            ),
            const SizedBox(height: 12),
            Text(
              'Client Tools',
              style: Theme.of(context).textTheme.titleLarge?.copyWith(
                    fontWeight: FontWeight.w900,
                  ),
            ),
            const SizedBox(height: 2),
            Text(
              client.clientName,
              style: Theme.of(context).textTheme.bodyLarge?.copyWith(
                    fontWeight: FontWeight.w700,
                  ),
            ),
            const SizedBox(height: 4),
            Text(
              'Only route and collection tools are shown here. Identity, address-source, and photo evidence stay out of the normal Collector ledger.',
              style: Theme.of(context).textTheme.bodySmall,
            ),
            const SizedBox(height: 12),
            for (final entry in client.loans) ...[
              _LoanToolsCard(
                entry: entry,
                directPayBlockedReason: directPayBlockedReasonFor(entry),
                detailsBlockedReason: detailsBlockedReasonFor(entry),
                correctionBlockedReason: correctionBlockedReasonFor(entry),
              ),
              const SizedBox(height: 10),
            ],
            Card(
              margin: EdgeInsets.zero,
              child: ListTile(
                leading: const Icon(Icons.location_on_outlined),
                title: const Text('Collection location'),
                subtitle: const Text('Read-only verified route detail'),
                trailing: const Icon(Icons.chevron_right),
                onTap: () => Navigator.of(context).pop(
                  const CollectorClientToolSelection(
                    CollectorClientToolKind.collectionLocation,
                  ),
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _LoanToolsCard extends StatelessWidget {
  const _LoanToolsCard({
    required this.entry,
    required this.directPayBlockedReason,
    required this.detailsBlockedReason,
    required this.correctionBlockedReason,
  });

  final CollectorRouteEntry entry;
  final String? directPayBlockedReason;
  final String? detailsBlockedReason;
  final String? correctionBlockedReason;

  @override
  Widget build(BuildContext context) {
    final directReason = directPayBlockedReason?.trim();
    final collectionMessage = entry.collectionMessage.trim();
    final readinessMessage = entry.contractReadinessMessage.trim();
    final operationalMessage = directReason?.isNotEmpty == true
        ? directReason
        : collectionMessage.isNotEmpty
            ? collectionMessage
            : readinessMessage.isNotEmpty
                ? readinessMessage
                : null;
    final detailsReason = detailsBlockedReason?.trim();
    final detailsSubtitle = detailsReason == null || detailsReason.isEmpty
        ? '${_loanLabel(entry.loanType)} payment flow'
        : detailsReason == operationalMessage
            ? 'Payment details unavailable until this route is eligible.'
            : detailsReason;

    return Card(
      margin: EdgeInsets.zero,
      child: Padding(
        padding: const EdgeInsets.fromLTRB(12, 10, 12, 8),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Row(
              children: [
                Expanded(
                  child: Text(
                    _loanLabel(entry.loanType),
                    style: Theme.of(context).textTheme.titleSmall?.copyWith(
                          fontWeight: FontWeight.w900,
                        ),
                  ),
                ),
                Text(
                  'Balance ${_money(entry.balance)}',
                  style: Theme.of(context).textTheme.bodySmall?.copyWith(
                        fontWeight: FontWeight.w700,
                      ),
                ),
              ],
            ),
            const SizedBox(height: 5),
            Text(
              'Status: ${entry.status}',
              style: Theme.of(context).textTheme.bodySmall,
            ),
            if (entry.contractCollectionReady &&
                entry.contractTodayScheduledAmount > 0) ...[
              const SizedBox(height: 3),
              Text(
                'Scheduled today: ${_money(entry.contractTodayScheduledAmount)}',
                style: Theme.of(context).textTheme.bodySmall,
              ),
              const SizedBox(height: 3),
              Text(
                'Still due today: ${_money(entry.contractTodayUnpaidAmount)}',
                style: Theme.of(context).textTheme.bodySmall,
              ),
            ],
            if (entry.lastPaymentDate != null) ...[
              const SizedBox(height: 3),
              Text(
                'Last payment: ${_date(entry.lastPaymentDate!)}',
                style: Theme.of(context).textTheme.bodySmall,
              ),
            ],
            if (entry.processedToday && entry.todayCollectorName.isNotEmpty) ...[
              const SizedBox(height: 3),
              Text(
                'Latest receipt recorded by: ${entry.todayCollectorName}',
                style: Theme.of(context).textTheme.bodySmall,
              ),
            ],
            if (entry.processedToday && entry.todayNote.isNotEmpty) ...[
              const SizedBox(height: 3),
              Text(
                'Latest receipt note: ${entry.todayNote}',
                style: Theme.of(context).textTheme.bodySmall,
              ),
            ],
            if (entry.processedToday && entry.todayIsLocked) ...[
              const SizedBox(height: 3),
              Text(
                'Latest receipt remittance status: Locked',
                style: Theme.of(context).textTheme.bodySmall,
              ),
            ],
            if (operationalMessage != null) ...[
              const SizedBox(height: 3),
              Text(
                operationalMessage,
                style: Theme.of(context).textTheme.bodySmall,
              ),
            ],
            if (entry.todayReceipts.isNotEmpty) ...[
              const SizedBox(height: 8),
              _ReceiptHistory(receipts: entry.todayReceipts),
            ],
            const Divider(height: 18),
            ListTile(
              key: Key('collection-details-${entry.id}'),
              contentPadding: EdgeInsets.zero,
              leading: const Icon(Icons.tune),
              title: const Text('Payment details / other amount'),
              subtitle: Text(detailsSubtitle),
              trailing: detailsBlockedReason == null
                  ? const Icon(Icons.chevron_right)
                  : const Icon(Icons.lock_outline),
              enabled: detailsBlockedReason == null,
              onTap: detailsBlockedReason == null
                  ? () => Navigator.of(context).pop(
                        CollectorClientToolSelection(
                          CollectorClientToolKind.paymentDetails,
                          entry: entry,
                        ),
                      )
                  : null,
            ),
            if (correctionBlockedReason == null)
              ListTile(
                contentPadding: EdgeInsets.zero,
                leading: const Icon(Icons.edit_outlined),
                title: const Text('Correction'),
                subtitle: const Text('Own unremitted collection only'),
                trailing: const Icon(Icons.chevron_right),
                onTap: () => Navigator.of(context).pop(
                  CollectorClientToolSelection(
                    CollectorClientToolKind.correction,
                    entry: entry,
                  ),
                ),
              ),
            ListTile(
              contentPadding: EdgeInsets.zero,
              leading: const Icon(Icons.calendar_month_outlined),
              title: const Text('Schedule'),
              subtitle: Text(
                'Read-only ${_loanLabel(entry.loanType)} schedule',
              ),
              trailing: const Icon(Icons.chevron_right),
              onTap: () => Navigator.of(context).pop(
                CollectorClientToolSelection(
                  CollectorClientToolKind.schedule,
                  entry: entry,
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _ReceiptHistory extends StatelessWidget {
  const _ReceiptHistory({required this.receipts});

  final List<CollectorRouteReceipt> receipts;

  @override
  Widget build(BuildContext context) {
    final total = receipts.fold<double>(
      0,
      (sum, receipt) => sum + receipt.amount,
    );
    return Column(
      key: const Key('today-receipts'),
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          "Today's receipts • ${receipts.length} • ${_money(total)}",
          style: Theme.of(context).textTheme.labelMedium?.copyWith(
                fontWeight: FontWeight.w800,
              ),
        ),
        const SizedBox(height: 5),
        for (final receipt in receipts) ...[
          Container(
            key: Key('today-receipt-${receipt.transactionId}'),
            width: double.infinity,
            padding: const EdgeInsets.symmetric(vertical: 4),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  'Receipt ${receipt.receiptNumber} • '
                  '${_money(receipt.amount)} • '
                  '${receipt.collectorName}'
                  '${receipt.isLocked ? ' • Locked' : ''}',
                  style: Theme.of(context).textTheme.bodySmall?.copyWith(
                        fontWeight: FontWeight.w700,
                      ),
                ),
                if (receipt.coveredDates.isNotEmpty)
                  Text(
                    'Covered: ${receipt.coveredDates.map(_date).join(', ')}',
                    style: Theme.of(context).textTheme.bodySmall,
                  ),
                if (receipt.note.isNotEmpty)
                  Text(
                    'Note: ${receipt.note}',
                    style: Theme.of(context).textTheme.bodySmall,
                  ),
              ],
            ),
          ),
        ],
      ],
    );
  }
}

String _loanLabel(String value) {
  final normalized = value.toLowerCase().replaceAll(' ', '');
  if (normalized.contains('7x7') || normalized.contains('7×7')) {
    return '7x7';
  }
  if (normalized.contains('regular')) return 'Regular';
  return value.trim().isEmpty ? 'Loan' : value.trim();
}

String _date(DateTime value) {
  final local = value.toLocal();
  return '${local.year.toString().padLeft(4, '0')}-'
      '${local.month.toString().padLeft(2, '0')}-'
      '${local.day.toString().padLeft(2, '0')}';
}

String _money(double value) {
  final fixed = value.toStringAsFixed(2);
  final parts = fixed.split('.');
  return '₱${_groupDigits(parts.first)}.${parts.last}';
}

String _groupDigits(String digits) {
  final buffer = StringBuffer();
  for (var index = 0; index < digits.length; index += 1) {
    if (index > 0 && (digits.length - index) % 3 == 0) {
      buffer.write(',');
    }
    buffer.write(digits[index]);
  }
  return buffer.toString();
}
