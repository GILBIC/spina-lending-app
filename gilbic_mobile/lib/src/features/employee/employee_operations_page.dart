import 'dart:async';
import 'package:flutter/material.dart';
import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/device/device_identity.dart';
import 'package:gilbic_mobile/src/core/employee_operations/attendance_outbox.dart';
import 'package:gilbic_mobile/src/core/employee_operations/employee_action_schema.dart';
import 'package:gilbic_mobile/src/core/employee_operations/employee_form_values.dart';
import 'package:gilbic_mobile/src/core/employee_operations/employee_operations_repository.dart';
import 'package:gilbic_mobile/src/core/employee_operations/employee_operations_service.dart';
import 'package:gilbic_mobile/src/core/network/spina_api.dart';
import 'package:gilbic_mobile/src/core/network/staff_operations_client.dart';
import 'package:gilbic_mobile/src/features/employee/employee_command_form.dart';

enum EmployeeSection {
  attendance,
  requests,
  tasks,
  advances,
  payroll,
  shortages,
  accounting,
  setup,
}

class EmployeeOperationsPage extends StatefulWidget {
  const EmployeeOperationsPage({
    required this.session,
    required this.deviceIdentityProvider,
    this.initialSection = EmployeeSection.attendance,
    this.service,
    super.key,
  });
  final UserSession session;
  final DeviceIdentityProvider deviceIdentityProvider;
  final EmployeeSection initialSection;
  final EmployeeOperationsService? service;
  @override
  State<EmployeeOperationsPage> createState() => _EmployeeOperationsPageState();
}

class _EmployeeOperationsPageState extends State<EmployeeOperationsPage> {
  EmployeeOperationsService? _service;
  bool _ownsService = false,
      _loading = true,
      _capturing = false,
      _offline = false,
      _denied = false;
  int _epoch = 0;
  EmployeeWorkspace? _workspace;
  List<AttendanceEntry> _events = [];
  String? _message;
  late EmployeeSection _section = widget.initialSection;
  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    if (_service != null) return;
    _service = widget.service ?? EmployeeOperationsScope.maybeOf(context);
    if (_service == null) {
      _ownsService = true;
      _service = EmployeeOperationsService(
        deviceIdentityProvider: widget.deviceIdentityProvider,
      );
    }
    _service!.attach(widget.session);
    _service!.addListener(_queueChanged);
    unawaited(_load());
  }

  @override
  void dispose() {
    _epoch++;
    _service?.removeListener(_queueChanged);
    if (_ownsService) _service?.dispose();
    super.dispose();
  }

  void _queueChanged() {
    if (_service?.accessDenied == true && mounted) {
      setState(() {
        _denied = true;
        _workspace = null;
        _events = [];
        _message =
            'Employee access is no longer authorized. Sign in again or contact the owner.';
      });
    }
    unawaited(_readQueue());
  }

  Future<void> _readQueue() async {
    final bound = _service?.binding;
    if (bound == null) {
      if (mounted) setState(() => _events = []);
      return;
    }
    try {
      final events = await _service!.outbox.entries(bound);
      if (mounted &&
          bound.userId == widget.session.userId &&
          identical(bound, _service!.binding)) {
        setState(() => _events = events);
      }
    } on Object {
      if (mounted) {
        setState(() {
          _events = [];
          _message =
              'Protected attendance storage could not be read. Reconnect this account and device before recording more events.';
        });
      }
    }
  }

  Future<void> _load() async {
    final epoch = ++_epoch;
    setState(() {
      _loading = true;
      _workspace = null;
      _message = null;
    });
    try {
      final workspace = await _service!.repository.workspace(widget.session);
      if (!mounted || epoch != _epoch) return;
      try {
        await _service!.acceptWorkspace(widget.session, workspace);
      } on Object {
        _message =
            'Protected attendance storage is unavailable. No attendance was saved. Other connected workflows remain available.';
      }
      if (!mounted || epoch != _epoch) return;
      setState(() {
        _workspace = workspace;
        _offline = false;
        _denied = false;
      });
      await _service!.sync();
    } on Object catch (error) {
      if (!mounted || epoch != _epoch) return;
      final denied = staffAccessRejected(error);
      if (denied) {
        await _service!.denyAttendance();
      } else {
        try {
          await _service!.restoreBinding();
        } on Object {
          /* Fail closed when protected storage is unavailable. */
        }
      }
      if (!mounted || epoch != _epoch) return;
      setState(() {
        _workspace = null;
        _offline = !denied;
        _denied = denied;
        _message = staffError(error);
      });
    } finally {
      if (mounted && epoch == _epoch) {
        setState(() => _loading = false);
        await _readQueue();
      }
    }
  }

  Future<void> _capture(String type) async {
    final binding = _service!.binding;
    if (_capturing || binding == null || _denied) return;
    setState(() => _capturing = true);
    try {
      await _service!.outbox.capture(binding, type, offline: _offline);
      await _readQueue();
      await _service!.sync();
      if (mounted) {
        setState(
          () => _message =
              'Attendance saved securely. The status below shows whether the server has received it.',
        );
      }
    } on Object {
      if (mounted) {
        setState(
          () => _message =
              'Attendance was not saved. Reconnect this account and device, then try again.',
        );
      }
    } finally {
      if (mounted) setState(() => _capturing = false);
    }
  }

  Future<void> _command(String action, {Map<String, dynamic>? record}) async {
    final workspace = _workspace;
    if (workspace == null || _loading || _denied) return;
    if (record != null &&
        !stringList(record['allowed_actions']).contains(action)) {
      return;
    }
    if (record == null && !_creationActions(workspace).contains(action)) return;
    await Navigator.push<bool>(
      context,
      MaterialPageRoute(
        builder: (_) => EmployeeCommandForm(
          session: widget.session,
          workspace: workspace,
          repository: _service!.repository,
          action: action,
          record: record,
        ),
      ),
    );
    if (mounted) await _load();
  }

  List<String> _creationActions(EmployeeWorkspace workspace) => [
    if (workspace.can('can_self_service')) ...[
      'correction_request',
      'leave_request',
      'shift_request',
      'overtime_request',
      'leave_conversion_request',
      'advance_request',
    ],
    if (workspace.can('can_assign_tasks')) 'task_save',
    if (workspace.can('can_prepare_payroll')) 'payroll_prepare',
    if (workspace.can('can_report_shortage')) 'shortage_report',
    if (workspace.can('can_prepare_accounting')) 'accounting_prepare',
    if (workspace.can('can_configure')) ...[
      'profile_save',
      'schedule_save',
      'backup_save',
      'calendar_save',
      'statutory_month_save',
      'statutory_remittance',
      'leave_balance_adjust',
      'payroll_history_import',
    ],
  ];
  static const _sectionActions = {
    EmployeeSection.attendance: [
      'correction_request',
      'shift_request',
      'overtime_request',
    ],
    EmployeeSection.requests: ['leave_request', 'leave_conversion_request'],
    EmployeeSection.tasks: ['task_save'],
    EmployeeSection.advances: ['advance_request'],
    EmployeeSection.payroll: ['payroll_prepare'],
    EmployeeSection.shortages: ['shortage_report'],
    EmployeeSection.accounting: ['accounting_prepare'],
    EmployeeSection.setup: [
      'profile_save',
      'schedule_save',
      'backup_save',
      'calendar_save',
      'statutory_month_save',
      'statutory_remittance',
      'leave_balance_adjust',
      'payroll_history_import',
    ],
  };
  static const _sectionCollections = {
    EmployeeSection.attendance: ['attendance_days', 'attendance', 'schedules'],
    EmployeeSection.requests: ['requests', 'leave_balances', 'leave_ledger'],
    EmployeeSection.tasks: ['tasks'],
    EmployeeSection.advances: ['advances'],
    EmployeeSection.payroll: ['payroll', 'payments'],
    EmployeeSection.shortages: ['shortages'],
    EmployeeSection.accounting: ['accounting_preparations'],
    EmployeeSection.setup: [
      'profiles',
      'schedules',
      'backups',
      'calendar',
      'statutory_months',
      'statutory_remittances',
      'payroll_history',
    ],
  };
  String _sectionName(EmployeeSection section) => switch (section) {
    EmployeeSection.requests => 'Leave & requests',
    EmployeeSection.setup => 'Staff setup',
    EmployeeSection.accounting => 'Accounting preparation',
    _ => employeeLabel(section.name),
  };

  Widget _attendance() => Column(
    crossAxisAlignment: CrossAxisAlignment.stretch,
    children: [
      const Text(
        'Clock and break events are saved on this device before syncing. Device capture time and server receipt time remain separate. Payroll uses reviewed server records.',
      ),
      const SizedBox(height: 12),
      Wrap(
        spacing: 10,
        runSpacing: 10,
        children: [
          for (final type in [
            'clock_in',
            'break_start',
            'break_end',
            'clock_out',
          ])
            FilledButton.tonal(
              key: Key('employee-$type'),
              onPressed:
                  _service?.binding == null || _capturing || _loading || _denied
                  ? null
                  : () => _capture(type),
              child: Text(employeeLabel(type)),
            ),
        ],
      ),
      if (_service?.binding == null && !_loading)
        const Padding(
          padding: EdgeInsets.symmetric(vertical: 12),
          child: Text(
            'Attendance needs an active staff profile and protected device setup. Connect once to initialize it.',
          ),
        ),
      if (_events.isNotEmpty) ...[
        const SizedBox(height: 16),
        Text(
          'Saved on this device',
          style: Theme.of(context).textTheme.titleMedium,
        ),
        for (final event in _events.reversed.take(40))
          ListTile(
            contentPadding: EdgeInsets.zero,
            leading: Icon(
              event.state == 'accepted'
                  ? Icons.cloud_done_outlined
                  : event.state == 'pending'
                  ? Icons.cloud_upload_outlined
                  : Icons.rate_review_outlined,
            ),
            title: Text(
              '${employeeLabel(event.command['event_type'] as String)} · ${employeeLabel(event.state)}',
            ),
            subtitle: Text(
              '${_format(event.command['captured_at'])}\n${event.message}',
            ),
            isThreeLine: true,
          ),
        OutlinedButton(
          onPressed: () async {
            await _service!.sync();
            await _readQueue();
          },
          child: const Text('Sync saved attendance'),
        ),
      ],
    ],
  );
  String _format(Object? value) {
    if (value == null) return 'Not supplied';
    if (value is bool) return value ? 'Yes' : 'No';
    if (value is String) {
      if (RegExp(r'^\d{4}-\d{2}-\d{2}T').hasMatch(value)) {
        return DateTime.tryParse(
              value,
            )?.toLocal().toString().replaceFirst(RegExp(r'\.\d+.*$'), '') ??
            value;
      }
      return value;
    }
    return value.toString();
  }

  Widget _value(String key, Object? value) {
    if (value is List) {
      return Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            employeeLabel(key),
            style: const TextStyle(fontWeight: FontWeight.w600),
          ),
          if (value.isEmpty) const Text('None'),
          for (final entry in value)
            Padding(
              padding: const EdgeInsets.only(left: 12, top: 4),
              child: entry is Map
                  ? Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        for (final pair in entry.entries)
                          _value(pair.key.toString(), pair.value),
                      ],
                    )
                  : Text(_format(entry)),
            ),
        ],
      );
    }
    if (value is Map) {
      return Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            employeeLabel(key),
            style: const TextStyle(fontWeight: FontWeight.w600),
          ),
          for (final pair in value.entries)
            Padding(
              padding: const EdgeInsets.only(left: 12),
              child: _value(pair.key.toString(), pair.value),
            ),
        ],
      );
    }
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 3),
      child: SelectableText('${employeeLabel(key)}: ${_format(value)}'),
    );
  }

  Widget _record(String collection, Map<String, dynamic> record) {
    final historyRows = _workspace!.historyFor(
      collection,
      record['id']?.toString() ?? '',
    );
    final payload = record['payload'] is Map
        ? stringMap(record['payload'])
        : record;
    final title = collection == 'tasks'
        ? payload['description']?.toString()
        : collection == 'payroll'
        ? '${employeeLabel(payload['payroll_kind']?.toString() ?? 'payroll')} · ${payload['week_start'] ?? ''}'
        : null;
    final id = record['employee_id'] as String?;
    final actions = stringList(
      record['allowed_actions'],
    ).where(employeeActionFields.containsKey).toList();
    return Card(
      child: ExpansionTile(
        key: ValueKey(
          '$collection-${record['id'] ?? '$id-${record['work_date']}'}',
        ),
        title: Text(title ?? _workspace!.employeeName(id)),
        subtitle: Text(
          [
            if (title != null) _workspace!.employeeName(id),
            if (record['status'] != null)
              employeeLabel(record['status'].toString()),
            if (payload['net_pay'] != null) 'Net pay PHP ${payload['net_pay']}',
            if (payload['outstanding_amount'] != null)
              'Outstanding PHP ${payload['outstanding_amount']}',
            if (payload['work_date'] != null) payload['work_date'].toString(),
          ].join(' · '),
        ),
        childrenPadding: const EdgeInsets.all(14),
        expandedCrossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          for (final pair in payload.entries.where(
            (entry) => !const [
              'employee_id',
              'device_id',
              'request_id',
              'action',
              'expected_version',
              'is_self',
              'can_review',
              'can_approve_payroll',
              'can_approve_advance',
            ].contains(entry.key),
          ))
            _value(pair.key, pair.value),
          if (record['version'] != null) _value('version', record['version']),
          if (record['updated_at'] != null)
            _value('updated_at', record['updated_at']),
          if (record['id'] != null) _value('record_id', record['id']),
          if (historyRows.isNotEmpty)
            ExpansionTile(
              title: const Text('Record history'),
              children: [
                for (final history in historyRows)
                  Padding(
                    padding: const EdgeInsets.all(10),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.stretch,
                      children: [
                        Text(
                          'Version ${history['version']} · ${employeeLabel(history['action']?.toString() ?? 'update')}',
                          style: const TextStyle(fontWeight: FontWeight.w700),
                        ),
                        _value('created_at', history['created_at']),
                        _value('status', history['status']),
                        for (final pair in stringMap(
                          history['payload'],
                        ).entries)
                          _value(pair.key, pair.value),
                      ],
                    ),
                  ),
              ],
            ),
          Wrap(
            spacing: 10,
            runSpacing: 6,
            children: [
              for (final action in actions)
                OutlinedButton(
                  key: Key('employee-action-$action-${record['id']}'),
                  onPressed: () => _command(action, record: record),
                  child: Text(employeeLabel(action)),
                ),
            ],
          ),
        ],
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final workspace = _workspace;
    final sections = EmployeeSection.values
        .where(
          (section) =>
              section != EmployeeSection.setup ||
              workspace?.can('can_configure') == true,
        )
        .toList();
    final selected = sections.contains(_section)
        ? _section
        : EmployeeSection.attendance;
    return Scaffold(
      appBar: AppBar(
        title: const Text('Employee operations'),
        actions: [
          IconButton(
            key: const Key('employee-refresh'),
            tooltip: 'Refresh employee records',
            onPressed: _loading ? null : _load,
            icon: const Icon(Icons.refresh),
          ),
        ],
      ),
      body: SafeArea(
        child: ListView(
          key: const Key('employee-operations-list'),
          padding: const EdgeInsets.all(16),
          children: [
            DropdownButtonFormField<EmployeeSection>(
              key: ValueKey('employee-section-$selected'),
              initialValue: selected,
              isExpanded: true,
              decoration: const InputDecoration(labelText: 'Workspace'),
              items: sections
                  .map(
                    (section) => DropdownMenuItem(
                      value: section,
                      child: Text(_sectionName(section)),
                    ),
                  )
                  .toList(),
              onChanged: (section) {
                if (section != null) setState(() => _section = section);
              },
            ),
            const SizedBox(height: 18),
            if (_loading) const LinearProgressIndicator(),
            if (_message != null)
              Padding(
                padding: const EdgeInsets.only(bottom: 14),
                child: Text(
                  _message!,
                  key: const Key('employee-workspace-message'),
                ),
              ),
            if (workspace != null && workspace.setupMissing.isNotEmpty)
              Card(
                child: Padding(
                  padding: const EdgeInsets.all(14),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      const Text(
                        'Setup needed',
                        style: TextStyle(fontWeight: FontWeight.w700),
                      ),
                      for (final missing in workspace.setupMissing)
                        Text('• $missing'),
                    ],
                  ),
                ),
              ),
            if (selected == EmployeeSection.attendance && !_denied)
              _attendance(),
            if (workspace != null) ...[
              Wrap(
                spacing: 10,
                runSpacing: 6,
                children: [
                  for (final action in _sectionActions[selected]!.where(
                    _creationActions(workspace).contains,
                  ))
                    OutlinedButton(
                      key: Key('employee-create-$action'),
                      onPressed: () => _command(action),
                      child: Text(employeeLabel(action)),
                    ),
                ],
              ),
              for (final collection in _sectionCollections[selected]!) ...[
                const SizedBox(height: 20),
                Text(
                  employeeLabel(collection),
                  style: Theme.of(context).textTheme.titleLarge,
                ),
                if (workspace.records(collection).isEmpty)
                  const Padding(
                    padding: EdgeInsets.symmetric(vertical: 12),
                    child: Text('No records available for your access.'),
                  ),
                for (final record in workspace.records(collection))
                  _record(collection, record),
              ],
            ] else if (!_loading)
              const Padding(
                padding: EdgeInsets.symmetric(vertical: 20),
                child: Text(
                  'Connect and refresh to view authoritative employee records. Reviews, requests and financial actions require the live server.',
                ),
              ),
          ],
        ),
      ),
    );
  }
}
