import 'dart:async';

import 'package:flutter/material.dart';
import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/device/device_identity.dart';
import 'package:gilbic_mobile/src/core/management/management_employee_activity.dart'
    hide ManagementEmployeeActivityPage;
import 'package:gilbic_mobile/src/core/management/management_employee_activity.dart'
    as activity
    show ManagementEmployeeActivityPage;
import 'package:gilbic_mobile/src/core/management/management_employee_activity_repository.dart';
import 'package:gilbic_mobile/src/core/network/spina_api.dart';
import 'package:gilbic_mobile/src/features/management/management_employee_activity_detail_page.dart';

class ManagementEmployeeActivityPage extends StatefulWidget {
  const ManagementEmployeeActivityPage({
    required this.session,
    required this.deviceIdentityProvider,
    this.repository,
    this.initialDateFrom,
    this.initialDateTo,
    super.key,
  });

  final UserSession session;
  final DeviceIdentityProvider deviceIdentityProvider;
  final ManagementEmployeeActivityRepository? repository;
  final DateTime? initialDateFrom;
  final DateTime? initialDateTo;

  @override
  State<ManagementEmployeeActivityPage> createState() =>
      _ManagementEmployeeActivityPageState();
}

class _ManagementEmployeeActivityPageState
    extends State<ManagementEmployeeActivityPage> {
  late final ManagementEmployeeActivityRepository _repository;
  late final TextEditingController _searchController;
  late DateTime _dateFrom;
  late DateTime _dateTo;
  activity.ManagementEmployeeActivityPage? _page;
  ManagementEmployeeActivityDomain? _domain;
  ManagementEmployeeActivityStatus? _status;
  String? _deviceId;
  Future<String>? _deviceIdLoad;
  bool _loading = true;
  String? _error;
  int? _statusCode;
  int _generation = 0;

  @override
  void initState() {
    super.initState();
    _repository =
        widget.repository ?? SpinaManagementEmployeeActivityRepository();
    _searchController = TextEditingController();
    final today = DateTime.now();
    _dateFrom = _dateOnly(widget.initialDateFrom ?? today);
    _dateTo = _dateOnly(widget.initialDateTo ?? today);
    unawaited(_load());
  }

  @override
  void dispose() {
    _generation += 1;
    _searchController.dispose();
    super.dispose();
  }

  Future<String> _loadDeviceId() {
    final cached = _deviceId;
    if (cached != null) return Future<String>.value(cached);
    return _deviceIdLoad ??= _loadAndCacheDeviceId();
  }

  Future<String> _loadAndCacheDeviceId() async {
    try {
      final identity = await widget.deviceIdentityProvider.load();
      _deviceId = identity.installationId;
      return identity.installationId;
    } finally {
      _deviceIdLoad = null;
    }
  }

  Future<void> _load() async {
    final generation = ++_generation;
    setState(() {
      _loading = true;
      _error = null;
      _statusCode = null;
    });
    try {
      final deviceId = await _loadDeviceId();
      final page = await _repository.listEmployees(
        widget.session,
        deviceId: deviceId,
        dateFrom: _dateFrom,
        dateTo: _dateTo,
        query: _searchController.text,
        domain: _domain,
        status: _status,
      );
      if (!mounted || generation != _generation) return;
      setState(() => _page = page);
    } on Object catch (error) {
      if (!mounted || generation != _generation) return;
      setState(() {
        _error = error is SpinaApiException
            ? error.message
            : 'Employee Activity could not be loaded.';
        _statusCode = error is SpinaApiException ? error.statusCode : null;
      });
    } finally {
      if (mounted && generation == _generation) {
        setState(() => _loading = false);
      }
    }
  }

  Future<void> _pickDates() async {
    final selected = await showDateRangePicker(
      context: context,
      initialDateRange: DateTimeRange(start: _dateFrom, end: _dateTo),
      firstDate: DateTime(2020),
      lastDate: DateTime.now().add(const Duration(days: 365)),
      helpText: 'Employee Activity date range (up to 31 days)',
    );
    if (selected == null || !mounted) return;
    if (selected.duration.inDays >= 31) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Choose a range of 31 days or less.')),
      );
      return;
    }
    setState(() {
      _dateFrom = _dateOnly(selected.start);
      _dateTo = _dateOnly(selected.end);
    });
    unawaited(_load());
  }

  void _openEmployee(ManagementEmployeeActivityRow row) {
    final deviceId = _deviceId;
    if (deviceId == null) return;
    Navigator.of(context).push(
      MaterialPageRoute<void>(
        builder: (context) => ManagementEmployeeActivityDetailPage(
          session: widget.session,
          deviceId: deviceId,
          repository: _repository,
          employeeUserId: row.employeeUserId,
          employeeName: row.employeeName,
          dateFrom: _dateFrom,
          dateTo: _dateTo,
          deviceIdentityProvider: widget.deviceIdentityProvider,
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final page = _page;
    return Scaffold(
      appBar: AppBar(
        title: const Text('Employee Activity'),
        actions: [
          IconButton(
            key: const Key('employee-activity-refresh'),
            tooltip: 'Refresh Employee Activity',
            onPressed: _loading ? null : _load,
            icon: const Icon(Icons.refresh),
          ),
        ],
      ),
      body: SafeArea(
        child: RefreshIndicator(
          onRefresh: _load,
          child: ListView(
            physics: const AlwaysScrollableScrollPhysics(),
            padding: const EdgeInsets.fromLTRB(12, 12, 12, 28),
            children: [
              Text(
                'Review authorized Employee work, approvals, and exceptions. Activity is read-only here.',
                style: Theme.of(context).textTheme.bodyMedium,
              ),
              const SizedBox(height: 12),
              TextField(
                key: const Key('employee-activity-search'),
                controller: _searchController,
                textInputAction: TextInputAction.search,
                decoration: const InputDecoration(
                  labelText: 'Search Employee',
                  prefixIcon: Icon(Icons.search),
                ),
                onSubmitted: (_) => unawaited(_load()),
              ),
              const SizedBox(height: 10),
              OutlinedButton.icon(
                key: const Key('employee-activity-date-filter'),
                onPressed: _loading ? null : _pickDates,
                icon: const Icon(Icons.date_range_outlined),
                label: Text('${_date(_dateFrom)} to ${_date(_dateTo)}'),
              ),
              const SizedBox(height: 10),
              LayoutBuilder(
                builder: (context, constraints) {
                  final fieldWidth = constraints.maxWidth >= 560
                      ? (constraints.maxWidth - 10) / 2
                      : constraints.maxWidth;
                  return Wrap(
                    spacing: 10,
                    runSpacing: 10,
                    children: [
                      SizedBox(
                        width: fieldWidth,
                        child:
                            DropdownButtonFormField<
                              ManagementEmployeeActivityDomain?
                            >(
                              key: const Key('employee-activity-domain-filter'),
                              initialValue: _domain,
                              isExpanded: true,
                              decoration: const InputDecoration(
                                labelText: 'Function',
                              ),
                              items:
                                  <
                                    DropdownMenuItem<
                                      ManagementEmployeeActivityDomain?
                                    >
                                  >[
                                    const DropdownMenuItem<
                                      ManagementEmployeeActivityDomain?
                                    >(
                                      value: null,
                                      child: Text('All authorized functions'),
                                    ),
                                    for (final domain
                                        in page?.availableDomains ??
                                            const <
                                              ManagementEmployeeActivityDomain
                                            >[])
                                      DropdownMenuItem<
                                        ManagementEmployeeActivityDomain?
                                      >(
                                        value: domain,
                                        child: Text(_domainLabel(domain)),
                                      ),
                                  ],
                              onChanged: _loading
                                  ? null
                                  : (value) {
                                      setState(() => _domain = value);
                                      unawaited(_load());
                                    },
                            ),
                      ),
                      SizedBox(
                        width: fieldWidth,
                        child:
                            DropdownButtonFormField<
                              ManagementEmployeeActivityStatus?
                            >(
                              key: const Key('employee-activity-status-filter'),
                              initialValue: _status,
                              isExpanded: true,
                              decoration: const InputDecoration(
                                labelText: 'Status',
                              ),
                              items:
                                  <
                                    DropdownMenuItem<
                                      ManagementEmployeeActivityStatus?
                                    >
                                  >[
                                    const DropdownMenuItem<
                                      ManagementEmployeeActivityStatus?
                                    >(value: null, child: Text('All statuses')),
                                    for (final status
                                        in ManagementEmployeeActivityStatus
                                            .values)
                                      DropdownMenuItem<
                                        ManagementEmployeeActivityStatus?
                                      >(
                                        value: status,
                                        child: Text(_statusLabel(status)),
                                      ),
                                  ],
                              onChanged: _loading
                                  ? null
                                  : (value) {
                                      setState(() => _status = value);
                                      unawaited(_load());
                                    },
                            ),
                      ),
                    ],
                  );
                },
              ),
              if (_loading) ...[
                const SizedBox(height: 12),
                const LinearProgressIndicator(
                  key: Key('employee-activity-loading'),
                ),
              ],
              const SizedBox(height: 12),
              if (_error != null && page == null)
                _ActivityError(
                  message: _error!,
                  statusCode: _statusCode,
                  onRetry: _load,
                )
              else if (page != null) ...[
                if (page.availableDomains.isEmpty)
                  const Card(
                    child: Padding(
                      padding: EdgeInsets.all(14),
                      child: Text(
                        'No Employee Activity domains are available under your current permissions.',
                      ),
                    ),
                  ),
                if (page.rows.isEmpty)
                  const Card(
                    child: Padding(
                      padding: EdgeInsets.all(20),
                      child: Text(
                        'No Employees matched the current authorized filters.',
                        textAlign: TextAlign.center,
                      ),
                    ),
                  )
                else
                  for (final row in page.rows) ...[
                    _EmployeeActivityRowCard(
                      row: row,
                      onTap: () => _openEmployee(row),
                    ),
                    const SizedBox(height: 8),
                  ],
              ],
            ],
          ),
        ),
      ),
    );
  }
}

class _EmployeeActivityRowCard extends StatelessWidget {
  const _EmployeeActivityRowCard({required this.row, required this.onTap});

  final ManagementEmployeeActivityRow row;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final functions = row.functionLabels.isEmpty
        ? 'Authorized Employee'
        : row.functionLabels.join(', ');
    final counts = <String>[
      '${row.completedCount} completed',
      '${row.inProgressCount} in progress',
      '${row.awaitingReviewCount} awaiting Management',
      '${row.needsAttentionCount} needs attention',
    ];
    return Card(
      key: Key('employee-activity-row-${row.employeeUserId}'),
      clipBehavior: Clip.antiAlias,
      child: InkWell(
        onTap: onTap,
        child: ConstrainedBox(
          constraints: const BoxConstraints(minHeight: 56),
          child: Padding(
            padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    const Icon(Icons.person_search_outlined, size: 22),
                    const SizedBox(width: 8),
                    Expanded(
                      child: Text(
                        '${row.employeeName} · $functions',
                        maxLines: 2,
                        overflow: TextOverflow.ellipsis,
                        style: Theme.of(context).textTheme.titleSmall,
                      ),
                    ),
                    const Icon(Icons.chevron_right),
                  ],
                ),
                const SizedBox(height: 6),
                Text(counts.join(' · ')),
                const SizedBox(height: 3),
                Text(
                  row.status == ManagementEmployeeActivityStatus.noActivity
                      ? 'No permitted activity in this range'
                      : row.statusMessage,
                ),
                if (row.lastActivityAt != null) ...[
                  const SizedBox(height: 3),
                  Text(
                    'Last visible: ${_dateTime(row.lastActivityAt!)} · '
                    '${_domainLabel(row.lastActivityDomain!)}',
                    style: Theme.of(context).textTheme.bodySmall,
                  ),
                ],
              ],
            ),
          ),
        ),
      ),
    );
  }
}

class _ActivityError extends StatelessWidget {
  const _ActivityError({
    required this.message,
    required this.statusCode,
    required this.onRetry,
  });

  final String message;
  final int? statusCode;
  final Future<void> Function() onRetry;

  @override
  Widget build(BuildContext context) {
    final title = switch (statusCode) {
      401 => 'Employee Activity session expired',
      403 => 'Employee Activity access unavailable',
      _ => 'Employee Activity unavailable',
    };
    return Card(
      color: Theme.of(context).colorScheme.errorContainer,
      child: Padding(
        padding: const EdgeInsets.all(20),
        child: Column(
          children: [
            Text(title, style: Theme.of(context).textTheme.titleMedium),
            const SizedBox(height: 8),
            Text(message, textAlign: TextAlign.center),
            const SizedBox(height: 12),
            FilledButton.icon(
              key: const Key('employee-activity-retry'),
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

DateTime _dateOnly(DateTime value) =>
    DateTime.utc(value.year, value.month, value.day);

String _domainLabel(ManagementEmployeeActivityDomain domain) {
  return switch (domain) {
    ManagementEmployeeActivityDomain.accounting => 'Accounting',
    ManagementEmployeeActivityDomain.hr => 'HR',
    ManagementEmployeeActivityDomain.payroll => 'Payroll',
    ManagementEmployeeActivityDomain.crmSupport => 'Client support',
    ManagementEmployeeActivityDomain.remittanceOperations =>
      'Remittance operations',
    ManagementEmployeeActivityDomain.administration => 'Administration',
  };
}

String _statusLabel(ManagementEmployeeActivityStatus status) {
  return switch (status) {
    ManagementEmployeeActivityStatus.noActivity => 'No permitted activity',
    ManagementEmployeeActivityStatus.inProgress => 'In progress',
    ManagementEmployeeActivityStatus.awaitingReview => 'Awaiting Management',
    ManagementEmployeeActivityStatus.completed => 'Completed',
    ManagementEmployeeActivityStatus.needsAttention => 'Needs attention',
  };
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
