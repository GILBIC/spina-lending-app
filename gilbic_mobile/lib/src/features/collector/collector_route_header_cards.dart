import 'package:flutter/material.dart';
import 'package:gilbic_mobile/src/core/collector/collector_route.dart';
import 'package:gilbic_mobile/src/core/collector/collector_route_loader.dart';

class CollectorRouteHeaderCard extends StatelessWidget {
  const CollectorRouteHeaderCard({
    required this.result,
    required this.route,
    required this.clientCount,
    super.key,
  });

  final CollectorRouteLoadResult result;
  final CollectorRoute route;
  final int clientCount;

  @override
  Widget build(BuildContext context) {
    final recorded = route.entries.where((entry) => entry.processedToday).length;
    final dateText = route.routeDate == null ? 'Saved route' : _longDate(route.routeDate!);
    final activePromiseReminders = route.entries
        .map(_activePromiseReminder)
        .whereType<String>()
        .toSet()
        .toList(growable: false);
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(13),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              'Collector: ${route.collectorName}',
              style: const TextStyle(fontWeight: FontWeight.w900),
            ),
            Text(
              '$dateText • ${result.isFromCache ? 'Offline copy' : 'Online route'}',
            ),
            const SizedBox(height: 7),
            Text(
              '$clientCount clients • ${route.entries.length} loans • '
              '${_money(route.expectedTotal)} expected',
              style: Theme.of(context).textTheme.bodySmall,
            ),
            Text(
              '$recorded recorded • Last sync ${_time(result.syncedAt)}',
              style: Theme.of(context).textTheme.bodySmall,
            ),
            if (activePromiseReminders.length == 1)
              Text(
                activePromiseReminders.single,
                key: const Key('collector-header-active-promise'),
                style: Theme.of(context).textTheme.bodySmall?.copyWith(
                      fontWeight: FontWeight.w700,
                    ),
              )
            else if (activePromiseReminders.length > 1)
              Text(
                '${activePromiseReminders.length} active promises • '
                'Open each client for date, remaining amount, and status',
                key: const Key('collector-header-active-promises'),
                style: Theme.of(context).textTheme.bodySmall?.copyWith(
                      fontWeight: FontWeight.w700,
                    ),
              ),
          ],
        ),
      ),
    );
  }
}

class CollectorAreaArrangementCard extends StatelessWidget {
  const CollectorAreaArrangementCard({required this.areas, super.key});

  final List<String> areas;

  @override
  Widget build(BuildContext context) {
    if (areas.isEmpty) {
      return const SizedBox.shrink();
    }
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text(
              'Area arrangement',
              style: TextStyle(fontWeight: FontWeight.w900),
            ),
            const SizedBox(height: 5),
            for (var index = 0; index < areas.length; index++)
              Text('${index + 1}  ${areas[index].trim().toUpperCase()}'),
          ],
        ),
      ),
    );
  }
}

String? _activePromiseReminder(CollectorRouteEntry entry) {
  const marker = 'Promise: ';
  final index = entry.collectionMessage.indexOf(marker);
  if (index < 0) {
    return null;
  }
  final reminder = entry.collectionMessage.substring(index).trim();
  return reminder.isEmpty ? null : reminder;
}

String _longDate(DateTime value) {
  final local = value.toLocal();
  const months = <String>[
    'January',
    'February',
    'March',
    'April',
    'May',
    'June',
    'July',
    'August',
    'September',
    'October',
    'November',
    'December',
  ];
  return '${months[local.month - 1]} ${local.day}, ${local.year}';
}

String _time(DateTime value) {
  final local = value.toLocal();
  return '${local.hour.toString().padLeft(2, '0')}:'
      '${local.minute.toString().padLeft(2, '0')}';
}

String _money(double value) {
  final fixed = value.toStringAsFixed(2).split('.');
  return '₱${_groupDigits(fixed.first)}.${fixed.last}';
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
