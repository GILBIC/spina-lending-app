import 'package:flutter/material.dart';
import 'package:gilbic_mobile/src/core/auth/app_role.dart';
import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/device/device_identity.dart';
import 'package:gilbic_mobile/src/core/management/staff_operations_repository.dart';
import 'package:gilbic_mobile/src/core/network/staff_operations_client.dart';

class ManagementPastDueReasonsPage extends StatefulWidget {
  const ManagementPastDueReasonsPage({
    required this.session,
    required this.deviceIdentityProvider,
    this.repository,
    super.key,
  });
  final UserSession session;
  final DeviceIdentityProvider deviceIdentityProvider;
  final StaffOperationsRepository? repository;
  @override
  State<ManagementPastDueReasonsPage> createState() =>
      _ManagementPastDueReasonsPageState();
}

class _ManagementPastDueReasonsPageState
    extends State<ManagementPastDueReasonsPage> {
  late final _repository =
      widget.repository ??
      StaffOperationsRepository(
        deviceIdentityProvider: widget.deviceIdentityProvider,
      );
  final _start = TextEditingController(),
      _end = TextEditingController(),
      _area = TextEditingController();
  PastDueReport? _report;
  String? _error;
  String _reason = '', _event = '';
  bool _busy = false;
  bool get _allowed =>
      widget.session.role == AppRole.management &&
      widget.session.hasPermission('management.dashboard.view');
  @override
  void initState() {
    super.initState();
    if (_allowed) _load();
  }

  @override
  void dispose() {
    _report = null;
    _start.dispose();
    _end.dispose();
    _area.dispose();
    if (widget.repository == null) _repository.close();
    super.dispose();
  }

  bool _validDate(String input) {
    if (input.isEmpty) return true;
    final date = DateTime.tryParse(input);
    return RegExp(r'^\d{4}-\d{2}-\d{2}$').hasMatch(input) &&
        date != null &&
        date.toIso8601String().startsWith(input);
  }

  Future<void> _load() async {
    if (_busy || !_allowed) return;
    final start = _start.text.trim(), end = _end.text.trim();
    setState(() {
      _report = null;
      _error = null;
    });
    if (!_validDate(start) ||
        !_validDate(end) ||
        (start.isNotEmpty && end.isNotEmpty && start.compareTo(end) > 0)) {
      setState(() {
        _error =
            'Enter valid dates as YYYY-MM-DD, with the start on or before the end.';
      });
      return;
    }
    setState(() {
      _busy = true;
    });
    try {
      final report = await _repository.pastDue(widget.session, {
        if (start.isNotEmpty) 'start_date': start,
        if (end.isNotEmpty) 'end_date': end,
        if (_area.text.trim().isNotEmpty) 'area': _area.text.trim(),
        if (_reason.isNotEmpty) 'reason_code': _reason,
        if (_event.isNotEmpty) 'event_kind': _event,
      });
      if (mounted) {
        setState(() {
          _report = report;
        });
      }
    } catch (error) {
      if (mounted) {
        setState(() {
          _error = staffError(error);
          _report = null;
        });
      }
    } finally {
      if (mounted) {
        setState(() {
          _busy = false;
        });
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final report = _report;
    return Scaffold(
      appBar: AppBar(title: const Text('Past-due reasons')),
      body: SafeArea(
        child: !_allowed
            ? const Center(
                child: Text('Management reporting permission is required.'),
              )
            : ListView(
                padding: const EdgeInsets.all(16),
                children: [
                  const Text(
                    'Reasons recorded for missed and partial payments. Amounts come from the server; this report does not change balances.',
                  ),
                  TextField(
                    key: const Key('past-due-start'),
                    controller: _start,
                    enabled: !_busy,
                    decoration: const InputDecoration(
                      labelText: 'From date (YYYY-MM-DD)',
                    ),
                  ),
                  TextField(
                    key: const Key('past-due-end'),
                    controller: _end,
                    enabled: !_busy,
                    decoration: const InputDecoration(
                      labelText: 'Through date (YYYY-MM-DD)',
                    ),
                  ),
                  TextField(
                    controller: _area,
                    enabled: !_busy,
                    maxLength: 200,
                    decoration: const InputDecoration(
                      labelText: 'Area (optional)',
                    ),
                  ),
                  DropdownButtonFormField<String>(
                    initialValue: _reason,
                    isExpanded: true,
                    decoration: const InputDecoration(labelText: 'Reason'),
                    items:
                        const {
                              '': 'All reasons',
                              'no_cash': 'No cash',
                              'client_absent': 'Client absent',
                              'business_slow': 'Business slow',
                              'sick_hospital': 'Sick / hospital',
                              'emergency': 'Emergency',
                              'promised_to_pay_later': 'Promised to pay later',
                              'other': 'Other',
                            }.entries
                            .map(
                              (e) => DropdownMenuItem(
                                value: e.key,
                                child: Text(e.value),
                              ),
                            )
                            .toList(),
                    onChanged: _busy
                        ? null
                        : (value) => setState(() {
                            _reason = value ?? '';
                            _report = null;
                          }),
                  ),
                  DropdownButtonFormField<String>(
                    initialValue: _event,
                    isExpanded: true,
                    decoration: const InputDecoration(labelText: 'Event'),
                    items:
                        const {
                              '': 'All events',
                              'unable_to_pay': 'Unable to pay',
                              'partial_payment': 'Partial payment',
                            }.entries
                            .map(
                              (e) => DropdownMenuItem(
                                value: e.key,
                                child: Text(e.value),
                              ),
                            )
                            .toList(),
                    onChanged: _busy
                        ? null
                        : (value) => setState(() {
                            _event = value ?? '';
                            _report = null;
                          }),
                  ),
                  const SizedBox(height: 12),
                  FilledButton(
                    key: const Key('past-due-load'),
                    onPressed: _busy ? null : _load,
                    child: const Text('Load report'),
                  ),
                  if (_busy) const LinearProgressIndicator(),
                  if (_error != null)
                    Text(
                      _error!,
                      style: TextStyle(
                        color: Theme.of(context).colorScheme.error,
                      ),
                    ),
                  if (report != null && !report.available)
                    const Text(
                      'Past-due reason reporting is not available on this server yet.',
                    ),
                  if (report != null && report.available) ...[
                    Card(
                      child: Padding(
                        padding: const EdgeInsets.all(16),
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(
                              'Summary of returned rows',
                              style: Theme.of(context).textTheme.titleMedium,
                            ),
                            Text('Events: ${report.count}'),
                            Text('Past due: ₱${report.total}'),
                            Text('Remaining: ₱${report.remaining}'),
                          ],
                        ),
                      ),
                    ),
                    if (report.rows.isEmpty)
                      const Text('No matching past-due events.'),
                    for (final row in report.rows)
                      Card(
                        child: Padding(
                          padding: const EdgeInsets.all(12),
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Text(
                                row.client,
                                style: Theme.of(context).textTheme.titleMedium,
                              ),
                              Text('${row.area} · ${row.collector}'),
                              Text(
                                '${row.reason} · ${row.event} · ${row.count} events',
                              ),
                              Text(
                                'Past due: ₱${row.total}\nRemaining: ₱${row.remaining}',
                              ),
                            ],
                          ),
                        ),
                      ),
                    if (report.rows.length >= 500)
                      const Text(
                        'The server returned the first 500 groups. Narrow the filters for a complete smaller report.',
                      ),
                  ],
                ],
              ),
      ),
    );
  }
}
