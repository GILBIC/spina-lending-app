import 'package:flutter/material.dart';
import 'package:gilbic_mobile/src/core/collector/collector_route.dart';

class CollectorClientSchedulePage extends StatelessWidget {
  const CollectorClientSchedulePage({
    required this.entry,
    super.key,
  });

  final CollectorRouteEntry entry;

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      key: const Key('collector-client-schedule-page'),
      appBar: AppBar(title: const Text('Client Schedule')),
      body: SafeArea(
        child: ListView(
          padding: const EdgeInsets.all(16),
          children: [
            Text(
              entry.clientName,
              style: Theme.of(context).textTheme.titleLarge?.copyWith(
                    fontWeight: FontWeight.w900,
                  ),
            ),
            const SizedBox(height: 4),
            Text(
              '${_loanLabel(entry.loanType)} • Read-only',
              style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                    fontWeight: FontWeight.w700,
                  ),
            ),
            const SizedBox(height: 12),
            Card(
              margin: EdgeInsets.zero,
              child: Padding(
                padding: const EdgeInsets.all(14),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Row(
                      children: [
                        Icon(Icons.lock_outline, size: 18),
                        SizedBox(width: 8),
                        Expanded(
                          child: Text(
                            'This schedule is view-only on the Collector phone.',
                          ),
                        ),
                      ],
                    ),
                    const SizedBox(height: 12),
                    Text('Current status: ${entry.status}'),
                    const SizedBox(height: 4),
                    Text('Current balance: ${_money(entry.balance)}'),
                  ],
                ),
              ),
            ),
          ],
        ),
      ),
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
