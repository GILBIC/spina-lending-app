import 'package:flutter/material.dart';
import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/collector/collector_route_grouping.dart';
import 'package:gilbic_mobile/src/core/collector/collector_schedule.dart';
import 'package:gilbic_mobile/src/core/collector/collector_schedule_repository.dart';

class CollectorClientSchedulePage extends StatefulWidget {
  const CollectorClientSchedulePage({
    required this.session,
    required this.client,
    this.repository,
    super.key,
  });

  final UserSession session;
  final CollectorRouteClientGroup client;
  final CollectorScheduleRepository? repository;

  @override
  State<CollectorClientSchedulePage> createState() =>
      _CollectorClientSchedulePageState();
}

class _CollectorClientSchedulePageState
    extends State<CollectorClientSchedulePage> {
  late final CollectorScheduleRepository _repository;
  List<CollectorSchedule>? _schedules;
  Object? _error;
  bool _loading = true;

  @override
  void initState() {
    super.initState();
    _repository = widget.repository ?? SpinaCollectorScheduleRepository();
    _load();
  }

  Future<void> _load() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final schedules = <CollectorSchedule>[];
      for (final loan in widget.client.loans) {
        final loanId = loan.loanId.trim();
        if (loanId.isEmpty) continue;
        schedules.add(
          await _repository.fetchSchedule(
            widget.session,
            loanId: loanId,
          ),
        );
      }
      if (mounted) {
        setState(() => _schedules = schedules);
      }
    } on Object catch (error) {
      if (mounted) {
        setState(() => _error = error);
      }
    } finally {
      if (mounted) {
        setState(() => _loading = false);
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      key: const Key('collector-client-schedule-page'),
      appBar: AppBar(title: const Text('Client Schedule')),
      body: SafeArea(child: _buildBody(context)),
    );
  }

  Widget _buildBody(BuildContext context) {
    if (_loading && _schedules == null) {
      return const Center(child: CircularProgressIndicator());
    }

    if (_error != null && _schedules == null) {
      return Center(
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              const Icon(Icons.cloud_off_outlined, size: 42),
              const SizedBox(height: 10),
              const Text(
                'The Client schedule could not be loaded. Check the connection and try again.',
                textAlign: TextAlign.center,
              ),
              const SizedBox(height: 14),
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

    final schedules = _schedules ?? const <CollectorSchedule>[];
    return RefreshIndicator(
      onRefresh: _load,
      child: ListView(
        physics: const AlwaysScrollableScrollPhysics(),
        padding: const EdgeInsets.fromLTRB(12, 10, 12, 20),
        children: [
          Text(
            widget.client.clientName,
            style: Theme.of(context).textTheme.titleLarge?.copyWith(
                  fontWeight: FontWeight.w900,
                ),
          ),
          const SizedBox(height: 4),
          const Row(
            children: [
              Icon(Icons.lock_outline, size: 18),
              SizedBox(width: 7),
              Expanded(
                child: Text(
                  'Read-only • schedule rows come from the SPINA server.',
                ),
              ),
            ],
          ),
          const SizedBox(height: 12),
          if (_error != null)
            const Padding(
              padding: EdgeInsets.only(bottom: 10),
              child: Text(
                'Refresh did not complete. The last loaded schedule remains shown.',
              ),
            ),
          if (schedules.isEmpty)
            const Card(
              child: Padding(
                padding: EdgeInsets.all(16),
                child: Text('No schedule is available for this Client.'),
              ),
            )
          else
            for (final schedule in schedules) ...[
              _ScheduleSection(schedule: schedule),
              const SizedBox(height: 10),
            ],
        ],
      ),
    );
  }
}

class _ScheduleSection extends StatelessWidget {
  const _ScheduleSection({required this.schedule});

  final CollectorSchedule schedule;

  @override
  Widget build(BuildContext context) {
    return Card(
      key: Key('schedule-section-${schedule.loanId}'),
      margin: EdgeInsets.zero,
      child: Padding(
        padding: const EdgeInsets.fromLTRB(12, 12, 12, 8),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Text(
              _loanLabel(schedule),
              style: Theme.of(context).textTheme.titleMedium?.copyWith(
                    fontWeight: FontWeight.w900,
                  ),
            ),
            if (schedule.loanNumber.trim().isNotEmpty) ...[
              const SizedBox(height: 2),
              Text(
                schedule.loanNumber,
                style: Theme.of(context).textTheme.bodySmall,
              ),
            ],
            if (schedule.baseMaturity != null ||
                schedule.updatedMaturity != null) ...[
              const SizedBox(height: 5),
              Text(
                'Maturity: ${_dateOrDash(schedule.baseMaturity)}'
                '${schedule.maturityExtended ? ' → ${_dateOrDash(schedule.updatedMaturity)}' : ''}',
                style: Theme.of(context).textTheme.bodySmall,
              ),
            ],
            if (schedule.scheduleExtensionSlots > 0) ...[
              const SizedBox(height: 2),
              Text(
                'Schedule extension: ${schedule.scheduleExtensionSlots} slot${schedule.scheduleExtensionSlots == 1 ? '' : 's'}',
                style: Theme.of(context).textTheme.bodySmall,
              ),
            ],
            const Divider(height: 18),
            if (schedule.rows.isEmpty)
              const Padding(
                padding: EdgeInsets.symmetric(vertical: 8),
                child: Text('No schedule rows returned.'),
              )
            else
              for (var index = 0; index < schedule.rows.length; index++)
                _ScheduleRowTile(
                  schedule: schedule,
                  row: schedule.rows[index],
                  index: index,
                ),
          ],
        ),
      ),
    );
  }
}

class _ScheduleRowTile extends StatelessWidget {
  const _ScheduleRowTile({
    required this.schedule,
    required this.row,
    required this.index,
  });

  final CollectorSchedule schedule;
  final CollectorScheduleRow row;
  final int index;

  @override
  Widget build(BuildContext context) {
    return ListTile(
      key: Key('schedule-row-${schedule.loanId}-$index'),
      contentPadding: EdgeInsets.zero,
      title: Row(
        children: [
          Expanded(child: Text(_dateOrDash(row.date))),
          const SizedBox(width: 10),
          Text(
            _money(row.amount),
            style: const TextStyle(fontWeight: FontWeight.w800),
          ),
        ],
      ),
      subtitle: Text(row.status),
      trailing: const Icon(Icons.chevron_right),
      onTap: () => _showRowDetails(context, row),
    );
  }
}

Future<void> _showRowDetails(
  BuildContext context,
  CollectorScheduleRow row,
) {
  final lines = <String>[
    'Date: ${_dateOrDash(row.date)}',
    'Status: ${row.status}',
    'Scheduled amount: ${_money(row.amount)}',
    'Paid amount: ${_money(row.paidAmount)}',
    'Prepaid amount: ${_money(row.prepaidAmount)}',
    'Remaining amount: ${_money(row.remainingAmount)}',
    if (row.pastDueReasonCode != null)
      'Past Due reason: ${row.pastDueReasonCode}',
    if (row.pastDueReasonNote != null)
      'Past Due note: ${row.pastDueReasonNote}',
    if (row.promisedForDate != null)
      'Promised for: ${_dateOrDash(row.promisedForDate)}',
    if (row.promiseStatus != null) 'Promise status: ${row.promiseStatus}',
    if (row.noCollectionReason != null)
      'No Collection reason: ${row.noCollectionReason}',
    if (row.principalComponent != null)
      'Principal component: ${_money(row.principalComponent!)}',
    if (row.interestComponent != null)
      'Interest component: ${_money(row.interestComponent!)}',
    if (row.principalReductionAmount > 0)
      'Principal reduction: ${_money(row.principalReductionAmount)}',
  ];

  return showModalBottomSheet<void>(
    context: context,
    useSafeArea: true,
    isScrollControlled: true,
    builder: (context) => SingleChildScrollView(
      padding: const EdgeInsets.fromLTRB(16, 14, 16, 24),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Text(
            'Schedule row details',
            style: Theme.of(context).textTheme.titleLarge?.copyWith(
                  fontWeight: FontWeight.w900,
                ),
          ),
          const SizedBox(height: 12),
          for (var index = 0; index < lines.length; index++) ...[
            if (index > 0) const SizedBox(height: 5),
            Text(lines[index]),
          ],
        ],
      ),
    ),
  );
}

String _loanLabel(CollectorSchedule schedule) {
  if (schedule.isSevenBySeven) return '7x7';
  final normalized = schedule.loanType.toLowerCase().replaceAll(' ', '');
  if (normalized.contains('7x7') || normalized.contains('7×7')) return '7x7';
  if (normalized.contains('regular')) return 'Regular';
  return schedule.loanType.trim().isEmpty ? 'Loan' : schedule.loanType.trim();
}

String _dateOrDash(DateTime? value) {
  if (value == null) return '—';
  return '${value.year.toString().padLeft(4, '0')}-'
      '${value.month.toString().padLeft(2, '0')}-'
      '${value.day.toString().padLeft(2, '0')}';
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
