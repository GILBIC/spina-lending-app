import 'package:flutter/material.dart';
import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/employee_operations/attendance_outbox.dart';
import 'package:gilbic_mobile/src/core/employee_operations/employee_action_schema.dart';
import 'package:gilbic_mobile/src/core/employee_operations/employee_form_values.dart';
import 'package:gilbic_mobile/src/core/employee_operations/employee_operations_repository.dart';
import 'package:gilbic_mobile/src/core/network/spina_api.dart';
import 'package:gilbic_mobile/src/core/network/staff_operations_client.dart';

class EmployeeCommandForm extends StatefulWidget {
  const EmployeeCommandForm({
    required this.session,
    required this.workspace,
    required this.repository,
    required this.action,
    this.record,
    super.key,
  });
  final UserSession session;
  final EmployeeWorkspace workspace;
  final EmployeeOperationsRepository repository;
  final String action;
  final Map<String, dynamic>? record;
  @override
  State<EmployeeCommandForm> createState() => _EmployeeCommandFormState();
}

class _EmployeeCommandFormState extends State<EmployeeCommandForm> {
  final _form = GlobalKey<FormState>();
  final _values = <String, dynamic>{};
  final _controllers = <String, TextEditingController>{};
  EmployeeAttempt? _attempt;
  bool _busy = false, _uncertain = false, _denied = false, _stale = false;
  String? _message;
  List<Map<String, Object?>> get _fields =>
      employeeActionFields[widget.action]!;
  bool get _locked => _busy || _uncertain || _denied || _stale;
  static const _selfActions = [
    'correction_request',
    'leave_request',
    'shift_request',
    'overtime_request',
    'leave_conversion_request',
    'advance_request',
    'advance_terms',
    'shortage_respond',
  ];

  @override
  void initState() {
    super.initState();
    final payload = stringMap(widget.record?['payload']);
    final sameFields = const [
      'profile_save',
      'schedule_save',
      'task_save',
      'advance_terms',
      'statutory_month_save',
      'backup_save',
      'calendar_save',
      'accounting_prepare',
    ].contains(widget.action);
    for (final field in _fields) {
      final name = field['name'] as String;
      if (sameFields && payload.containsKey(name)) {
        _values[name] = payload[name];
      } else if (field.containsKey('default')) {
        _values[name] = field['default'];
      }
    }
    if (widget.record?['employee_id'] != null) {
      _values['employee_id'] = widget.record!['employee_id'];
    }
    if (_selfActions.contains(widget.action)) {
      _values['employee_id'] = widget.session.userId;
    }
    if (widget.action == 'payroll_adjustment') {
      _values['original_payroll_id'] = widget.record?['id'];
    }
  }

  @override
  void dispose() {
    for (final controller in _controllers.values) {
      controller.dispose();
    }
    super.dispose();
  }

  Future<void> _submit({bool checkOnly = false}) async {
    if (_busy || _denied || _stale) return;
    if (_attempt == null) {
      if (!_form.currentState!.validate()) return;
      _attempt = EmployeeAttempt(
        buildEmployeeCommand(
          action: widget.action,
          values: _values,
          requestId: employeeRequestId(),
          newRecordId: employeeRequestId(),
          record: widget.record,
        ),
      );
    }
    setState(() {
      _busy = true;
      _message = null;
    });
    try {
      final result = checkOnly
          ? await widget.repository.check(widget.session, _attempt!)
          : await widget.repository.submit(widget.session, _attempt!);
      if (!mounted) return;
      if (result == null) {
        setState(() {
          _uncertain = true;
          _message =
              'No confirmation is available yet. Retry this exact request when connected; its identity and values are preserved.';
        });
      } else {
        setState(() {
          _busy = false;
          _uncertain = false;
        });
        Navigator.pop(context, true);
      }
    } on EmployeeUncertain catch (error) {
      if (mounted) {
        setState(() {
          _uncertain = true;
          _message = error.toString();
        });
      }
    } on Object catch (error) {
      if (!mounted) return;
      setState(() {
        _message = staffError(error);
        _denied = staffAccessRejected(error);
        _stale = error is SpinaApiException && error.statusCode == 409;
        if (_denied || _stale) _uncertain = false;
        if (!_uncertain) _attempt = null;
      });
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _pickDate(
    Map<String, Object?> field,
    Map<String, dynamic> target,
    String path,
  ) async {
    final name = field['name'] as String, kind = field['kind'];
    DateTime selected =
        DateTime.tryParse(target[name]?.toString() ?? '')?.toLocal() ??
        DateTime.now();
    if (kind != 'time') {
      final date = await showDatePicker(
        context: context,
        initialDate: selected,
        firstDate: DateTime(1950),
        lastDate: DateTime(2100),
      );
      if (date == null || !mounted) return;
      selected = date;
    }
    if (kind == 'timestamp' || kind == 'time') {
      final time = await showTimePicker(
        context: context,
        initialTime: TimeOfDay.fromDateTime(selected),
      );
      if (time == null || !mounted) return;
      selected = DateTime(
        selected.year,
        selected.month,
        selected.day,
        time.hour,
        time.minute,
      );
    }
    final value = kind == 'date'
        ? selected.toIso8601String().substring(0, 10)
        : kind == 'time'
        ? '${selected.hour.toString().padLeft(2, '0')}:${selected.minute.toString().padLeft(2, '0')}'
        : selected.toUtc().toIso8601String();
    setState(() {
      target[name] = value;
      _controllers[path]?.text = _displayDate(value, kind);
    });
  }

  String _displayDate(String value, Object? kind) {
    if (kind != 'timestamp') return value;
    final date = DateTime.tryParse(value)?.toLocal();
    return date == null ? value : date.toString().substring(0, 16);
  }

  List<DropdownMenuItem<String>> _employees() {
    final ids = <String, String>{};
    for (final row in widget.workspace.records('profiles')) {
      ids[row['employee_id'] as String] = widget.workspace.employeeName(
        row['employee_id'] as String,
      );
    }
    for (final row in widget.workspace.accounts) {
      ids[row['user_id'] as String] =
          row['full_name'] as String? ?? row['username'] as String;
    }
    if (widget.workspace.can('can_self_service')) {
      ids.putIfAbsent(widget.session.userId, () => widget.session.displayName);
    }
    return ids.entries
        .map(
          (entry) => DropdownMenuItem(
            value: entry.key,
            child: Text(entry.value, overflow: TextOverflow.ellipsis),
          ),
        )
        .toList();
  }

  Widget _field(
    Map<String, Object?> field,
    Map<String, dynamic> target,
    String prefix,
  ) {
    final name = field['name'] as String, kind = field['kind'] as String;
    final path = '$prefix$name';
    final label =
        '${employeeLabel(name)}${field['required'] == true ? '' : ' (optional)'}';
    final value = target[name];
    final fixed =
        name == 'employee_id' &&
            (widget.record != null || _selfActions.contains(widget.action)) ||
        name == 'original_payroll_id' && widget.record != null;
    if (fixed) {
      return Padding(
        padding: const EdgeInsets.symmetric(vertical: 8),
        child: Text(
          name == 'employee_id'
              ? 'Employee: ${widget.workspace.employeeName(value as String?)}'
              : 'Adjustment linked to the selected paid payroll.',
        ),
      );
    }
    if (kind == 'employee' || kind == 'choice' || kind == 'bool') {
      final items = kind == 'employee'
          ? _employees()
          : (kind == 'bool'
                    ? ['true', 'false']
                    : (field['options'] as List).cast<String>())
                .map(
                  (option) => DropdownMenuItem(
                    value: option,
                    child: Text(
                      kind == 'bool'
                          ? option == 'true'
                                ? 'Yes'
                                : 'No'
                          : employeeLabel(option),
                    ),
                  ),
                )
                .toList();
      return DropdownButtonFormField<String>(
        key: Key('employee-field-$path'),
        initialValue: value?.toString(),
        isExpanded: true,
        decoration: InputDecoration(labelText: label),
        items: items,
        onChanged: _locked
            ? null
            : (selected) => setState(
                () => target[name] = kind == 'bool'
                    ? selected == 'true'
                    : selected,
              ),
        validator: (_) => employeeFieldError(field, target[name]),
      );
    }
    if (kind == 'days' || kind == 'duties') {
      final options = kind == 'days'
          ? [1, 2, 3, 4, 5, 6, 7]
          : field['options'] as List;
      return FormField<List>(
        validator: (_) => employeeFieldError(field, target[name]),
        builder: (state) => Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(label),
            Wrap(
              spacing: 8,
              children: options
                  .map(
                    (option) => FilterChip(
                      label: Text(
                        kind == 'days'
                            ? [
                                'Mon',
                                'Tue',
                                'Wed',
                                'Thu',
                                'Fri',
                                'Sat',
                                'Sun',
                              ][(option as int) - 1]
                            : employeeLabel(option.toString()),
                      ),
                      selected: (target[name] as List? ?? []).contains(option),
                      onSelected: _locked
                          ? null
                          : (selected) => setState(() {
                              final values = List.of(
                                target[name] as List? ?? [],
                              );
                              selected
                                  ? values.add(option)
                                  : values.remove(option);
                              target[name] = values;
                              state.didChange(values);
                            }),
                    ),
                  )
                  .toList(),
            ),
            if (state.hasError)
              Text(
                state.errorText!,
                style: TextStyle(color: Theme.of(context).colorScheme.error),
              ),
          ],
        ),
      );
    }
    if (const ['installments', 'lines', 'dates'].contains(kind)) {
      return _rows(field, target, path, label);
    }
    final date = const ['date', 'timestamp', 'time'].contains(kind);
    final controller = _controllers.putIfAbsent(
      path,
      () => TextEditingController(
        text: date
            ? _displayDate(value?.toString() ?? '', kind)
            : value?.toString() ?? '',
      ),
    );
    return TextFormField(
      key: Key('employee-field-$path'),
      controller: controller,
      enabled: !_locked,
      readOnly: date,
      onTap: date ? () => _pickDate(field, target, path) : null,
      minLines: kind == 'text' ? 2 : 1,
      maxLines: kind == 'text' ? 4 : 1,
      keyboardType: const ['money', 'integer'].contains(kind)
          ? const TextInputType.numberWithOptions(decimal: true, signed: true)
          : TextInputType.text,
      decoration: InputDecoration(
        labelText: label,
        alignLabelWithHint: true,
        suffixIcon: date ? const Icon(Icons.calendar_today_outlined) : null,
        helperText: name == 'minutes'
            ? '480 minutes = one eight-hour day; 240 = half a day.'
            : kind == 'record'
            ? 'Use the identifier from the saved record.'
            : null,
      ),
      onChanged: (text) => target[name] = text,
      validator: (_) => employeeFieldError(field, target[name]),
    );
  }

  Widget _rows(
    Map<String, Object?> field,
    Map<String, dynamic> target,
    String path,
    String label,
  ) {
    final name = field['name'] as String, kind = field['kind'];
    final rows = target.putIfAbsent(name, () => <dynamic>[]) as List;
    return FormField<List>(
      validator: (_) => employeeFieldError(field, rows),
      builder: (state) => Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(label, style: Theme.of(context).textTheme.titleMedium),
          for (var index = 0; index < rows.length; index++)
            Card(
              key: ObjectKey(rows[index]),
              child: Padding(
                padding: const EdgeInsets.all(12),
                child: Column(
                  children: [
                    if (kind == 'dates')
                      _dateRow(rows, index, path)
                    else ...[
                      for (final subfield
                          in kind == 'installments'
                              ? const [
                                  {
                                    'name': 'due_date',
                                    'kind': 'date',
                                    'required': true,
                                  },
                                  {
                                    'name': 'amount',
                                    'kind': 'money',
                                    'required': true,
                                  },
                                ]
                              : const [
                                  {
                                    'name': 'account_code',
                                    'kind': 'text',
                                    'required': true,
                                    'maxLength': 100,
                                  },
                                  {
                                    'name': 'debit',
                                    'kind': 'money',
                                    'required': true,
                                  },
                                  {
                                    'name': 'credit',
                                    'kind': 'money',
                                    'required': true,
                                  },
                                ])
                        Padding(
                          padding: const EdgeInsets.only(bottom: 10),
                          child: _field(
                            subfield,
                            rows[index] as Map<String, dynamic>,
                            '$path-${identityHashCode(rows[index])}-',
                          ),
                        ),
                    ],
                    TextButton.icon(
                      onPressed: _locked
                          ? null
                          : () => setState(() {
                              rows.removeAt(index);
                              state.didChange(rows);
                            }),
                      icon: const Icon(Icons.remove_circle_outline),
                      label: const Text('Remove entry'),
                    ),
                  ],
                ),
              ),
            ),
          TextButton.icon(
            key: Key('employee-add-$name'),
            onPressed: _locked
                ? null
                : () async {
                    if (kind == 'dates') {
                      final date = await showDatePicker(
                        context: context,
                        firstDate: DateTime(2000),
                        lastDate: DateTime(2100),
                        initialDate: DateTime.now(),
                      );
                      if (date != null && mounted) {
                        setState(() {
                          rows.add(date.toIso8601String().substring(0, 10));
                          state.didChange(rows);
                        });
                      }
                    } else {
                      setState(() {
                        rows.add(<String, dynamic>{});
                        state.didChange(rows);
                      });
                    }
                  },
            icon: const Icon(Icons.add),
            label: Text(
              kind == 'installments'
                  ? 'Add agreed installment'
                  : kind == 'lines'
                  ? 'Add journal line'
                  : 'Add reviewed holiday',
            ),
          ),
          if (state.hasError)
            Text(
              state.errorText!,
              style: TextStyle(color: Theme.of(context).colorScheme.error),
            ),
        ],
      ),
    );
  }

  Widget _dateRow(List rows, int index, String path) =>
      Text(rows[index].toString());

  @override
  Widget build(BuildContext context) => PopScope(
    canPop: !_busy && !_uncertain,
    child: Scaffold(
      appBar: AppBar(title: Text(employeeLabel(widget.action))),
      body: SafeArea(
        child: Form(
          key: _form,
          child: ListView(
            padding: const EdgeInsets.all(16),
            children: [
              if (const [
                'payroll_payment',
                'advance_disburse',
                'advance_repay',
                'statutory_remittance',
              ].contains(widget.action))
                const Padding(
                  padding: EdgeInsets.only(bottom: 16),
                  child: Text(
                    'Record an actual payment outcome. This does not send money through GCash or a bank. Completion requires the stated evidence.',
                  ),
                ),
              if (widget.action == 'accounting_prepare')
                const Text(
                  'This prepares a draft for owner review. It does not post a journal or confirm a payment.',
                ),
              if (widget.action == 'shortage_decide')
                const Text(
                  'An evidence-based shortage decision is separate from lawful payroll recovery. This action does not deduct wages.',
                ),
              if (!_denied)
                for (final field in _fields)
                  Padding(
                    padding: const EdgeInsets.only(bottom: 18),
                    child: _field(field, _values, ''),
                  ),
              if (_message != null)
                Padding(
                  padding: const EdgeInsets.symmetric(vertical: 14),
                  child: Text(
                    _message!,
                    key: const Key('employee-command-message'),
                    style: TextStyle(
                      color: Theme.of(context).colorScheme.error,
                    ),
                  ),
                ),
              if (_stale)
                const Text(
                  'This record changed or has unresolved inputs. Return to the workspace and refresh before preparing a new request.',
                ),
              if (_uncertain)
                OutlinedButton(
                  onPressed: _busy ? null : () => _submit(checkOnly: true),
                  child: const Text('Check server confirmation'),
                ),
              if (!_denied && !_stale)
                FilledButton(
                  key: const Key('employee-submit'),
                  onPressed: _busy ? null : _submit,
                  child: Text(
                    _busy
                        ? 'Checking…'
                        : _uncertain
                        ? 'Retry unchanged request'
                        : 'Submit for server validation',
                  ),
                ),
              if (_denied)
                TextButton(
                  onPressed: () => Navigator.pop(context, false),
                  child: const Text('Return to sign-in or refresh access'),
                ),
            ],
          ),
        ),
      ),
    ),
  );
}
