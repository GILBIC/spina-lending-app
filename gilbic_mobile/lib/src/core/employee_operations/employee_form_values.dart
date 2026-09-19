import 'package:gilbic_mobile/src/core/employee_operations/employee_action_schema.dart';

Map<String, dynamic> buildEmployeeCommand({
  required String action,
  required Map<String, dynamic> values,
  required String requestId,
  required String newRecordId,
  Map<String, dynamic>? record,
}) {
  final fields = employeeActionFields[action];
  if (fields == null || action == 'attendance_record') {
    throw ArgumentError(
      'Use a supported online form; attendance uses its durable outbox.',
    );
  }
  final body = <String, dynamic>{};
  for (final field in fields) {
    final name = field['name'] as String;
    var value = values[name];
    final error = employeeFieldError(field, value);
    if (error != null) throw FormatException('${employeeLabel(name)}: $error');
    if (value == null || value is String && value.trim().isEmpty) {
      if (field['required'] != true) continue;
    }
    if (field['kind'] == 'integer') value = int.parse(value.toString());
    if (value is String) value = value.trim();
    body[name] = value;
  }
  final adjustment = action == 'payroll_adjustment';
  return {
    'action': action,
    'request_id': requestId,
    'id': action == 'profile_save'
        ? body['employee_id']
        : adjustment
        ? newRecordId
        : record?['id'] ?? newRecordId,
    'expected_version': adjustment ? 0 : record?['version'] ?? 0,
    ...body,
  };
}

String employeeLabel(String value) =>
    const <String, String>{
      'profile_save': 'Set up employee',
      'prior_employee_deductions':
          'Contributions already deducted this month before Spina (PHP)',
      'schedule_save': 'Set schedule',
      'backup_save': 'Assign dated backup',
      'payroll_history_import': 'Import verified payroll history',
      'payroll_history': 'Verified historical payroll',
      'ordinary_leave_days_per_year':
          'Existing annual ordinary leave benefit (days)',
      'leave_eligible_from': 'Existing earlier leave eligibility date',
      'calendar_save': 'Review holiday date',
      'statutory_month_save': 'Review monthly contributions',
      'statutory_remittance': 'Record agency remittance',
      'correction_request': 'Request attendance correction',
      'shift_request': 'Request shift change',
      'leave_request': 'Request leave',
      'overtime_request': 'Request overtime review',
      'leave_conversion_request': 'Request leave conversion',
      'leave_balance_adjust': 'Import or correct leave credits',
      'request_decide': 'Review request',
      'task_save': 'Assign task',
      'task_progress': 'Update task',
      'advance_request': 'Request salary advance',
      'advance_terms': 'Change agreed installments',
      'advance_decide': 'Review advance',
      'advance_disburse': 'Record advance disbursement',
      'advance_repay': 'Record actual repayment',
      'shortage_report': 'Report cash discrepancy',
      'shortage_respond': 'Submit my explanation',
      'shortage_decide': 'Decide shortage case',
      'payroll_prepare': 'Prepare payroll',
      'payroll_approve': 'Review payroll',
      'payroll_payment': 'Record salary payment',
      'payroll_adjustment': 'Create linked adjustment',
      'accounting_prepare': 'Prepare accounting draft',
      'employee_id': 'Employee',
      'user_id': 'Backup employee',
      'daily_rate': 'Daily wage (PHP)',
      'gp_partial_day_policy': 'Good Performance Benefit for a partial day',
      'classification_basis': 'Reviewed coverage and classification basis',
      'staff_manager': 'Combined collector and staff manager',
      'hire_date': 'Actual service start date',
      'premium_pay_covered': 'Covered by premium pay',
      'holiday_pay_covered': 'Covered by holiday pay',
      'tax_exempt': 'Reviewed tax exemption',
      'employee_acknowledgment': 'Employee acknowledgment evidence',
      'payroll_authorization': 'My agreed payroll deduction authorization',
      'settlement_evidence': 'Evidence of actual payment completion',
      'response_opportunity': 'Employee response opportunity and evidence',
      'expected_cash': 'Expected cash (PHP)',
      'accounted_cash': 'Counted / accounted cash (PHP)',
      'working_minutes': 'Verified working minutes',
      'unpaid_break_minutes': 'Unpaid break minutes',
      'week_start': 'Payroll week beginning (Sunday)',
      'statutory_months': 'Monthly contributions',
      'statutory_remittances': 'Agency remittances',
      'attendance_days': 'Daily attendance review',
      'leave_balances': 'Leave credits',
      'leave_ledger': 'Leave credit history',
      'accounting_preparations': 'Accounting drafts',
      'thirteenth_month': '13th month',
      'gcash': 'GCash',
      'sss': 'SSS',
      'philhealth': 'PhilHealth',
      'pagibig': 'Pag-IBIG',
      'bir': 'BIR',
      'pending_review': 'Needs review',
      'needs_attention': 'Needs attention',
      'in_progress': 'In progress',
      'clock_in': 'Clock in',
      'clock_out': 'Clock out',
      'break_start': 'Start break',
      'break_end': 'End break',
      'amount': 'Amount (PHP)',
    }[value] ??
    value
        .replaceAll('_', ' ')
        .replaceFirstMapped(RegExp(r'^.'), (match) => match[0]!.toUpperCase());

String? employeeFieldError(Map<String, Object?> field, Object? value) {
  final required = field['required'] == true;
  final kind = field['kind'];
  if (value == null ||
      value is String && value.trim().isEmpty ||
      value is List && value.isEmpty) {
    return required ? 'Required' : null;
  }
  if (kind == 'money') {
    final pattern = field['signed'] == true
        ? r'^-?\d{1,12}(\.\d{1,2})?$'
        : r'^\d{1,12}(\.\d{1,2})?$';
    if (value is! String || !RegExp(pattern).hasMatch(value.trim())) {
      return 'Enter pesos with at most two decimal places.';
    }
  } else if (kind == 'integer') {
    final number = value is int ? value : int.tryParse(value.toString());
    if (number == null ||
        field['minimum'] is int && number < (field['minimum'] as int) ||
        field['maximum'] is int && number > (field['maximum'] as int)) {
      return 'Enter a whole number within the allowed range.';
    }
  } else if (kind == 'bool' && value is! bool) {
    return 'Choose Yes or No.';
  } else if (kind == 'choice' && !(field['options'] as List).contains(value)) {
    return 'Choose an available option.';
  } else if (kind == 'date') {
    final text = value.toString();
    final date = DateTime.tryParse(text);
    if (!RegExp(r'^\d{4}-\d{2}-\d{2}$').hasMatch(text) ||
        date == null ||
        date.toIso8601String().substring(0, 10) != text) {
      return 'Choose a valid date.';
    }
  } else if (kind == 'timestamp' &&
      (DateTime.tryParse(value.toString()) == null ||
          !RegExp(r'(Z|[+-]\d{2}:\d{2})$').hasMatch(value.toString()))) {
    return 'Choose a date and time.';
  } else if (kind == 'time' &&
      !RegExp(
        r'^(?:[01][0-9]|2[0-3]):[0-5][0-9]$',
      ).hasMatch(value.toString())) {
    return 'Choose a valid time.';
  } else if ((kind == 'record' || kind == 'employee') &&
      !RegExp(
        r'^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$',
      ).hasMatch(value.toString())) {
    return 'Select a valid saved record.';
  }
  if (value is String &&
      field['maxLength'] is int &&
      value.length > (field['maxLength'] as int)) {
    return 'This text is too long.';
  }
  if (value is List &&
      field['maxItems'] is int &&
      value.length > (field['maxItems'] as int)) {
    return 'Too many entries.';
  }
  return null;
}
