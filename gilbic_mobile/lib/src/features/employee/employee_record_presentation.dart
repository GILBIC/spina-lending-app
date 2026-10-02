import 'package:gilbic_mobile/src/core/employee_operations/employee_form_values.dart';
import 'package:gilbic_mobile/src/core/formatting/spina_display.dart';
import 'package:gilbic_mobile/src/core/network/spina_api.dart';

const employeeHiddenDetailKeys = {
  'employee_id', 'device_id', 'request_id', 'action', 'expected_version',
  'is_self', 'can_review', 'can_approve_payroll', 'can_approve_advance',
};

class EmployeeRecordPresentation {
  const EmployeeRecordPresentation({required this.title, required this.status,
    required this.summaryFields, required this.detailKeys});
  final String title;
  final String status;
  final Map<String, String> summaryFields;
  final List<String> detailKeys;
}

/// Consumes authorized records only; it never computes pay or allowed actions.
EmployeeRecordPresentation presentEmployeeRecord(String collection,
    Map<String, dynamic> record, String employeeName) {
  final payload = record['payload'] is Map ? stringMap(record['payload']) : record;
  final known = const {'attendance', 'attendance_days', 'requests', 'tasks',
    'advances', 'payroll', 'shortages', 'accounting_preparations'}.contains(collection);
  final rawStatus = record['status']?.toString().trim() ?? '';
  final status = collection == 'payroll' && rawStatus == 'approved'
      ? 'Payroll approved · payment not confirmed'
      : rawStatus.isEmpty ? 'Status unavailable' : employeeLabel(rawStatus);
  final fields = <String, String>{};
  if (known) {
    for (final key in ['description', 'event_type', 'request_type', 'work_date',
      'week_start', 'week_end', 'period_start', 'period_end', 'captured_at']) {
      final value = payload[key];
      if (value == null || value is Map || value is List) continue;
      final text = value.toString();
      fields[key] = key.endsWith('_at')
          ? formatSpinaInstant(DateTime.tryParse(text))
          : key.contains('date') || key.contains('start') || key.contains('end')
          ? formatSpinaCalendarDate(text) : text;
    }
    for (final key in ['amount', 'gross_pay', 'net_pay', 'deductions',
      'paid_amount', 'outstanding_amount']) {
      if (payload[key] != null) fields[key] = formatSpinaMoney(payload[key].toString());
    }
  }
  return EmployeeRecordPresentation(title: employeeName, status: status,
    summaryFields: fields,
    detailKeys: [for (final key in payload.keys) if (!employeeHiddenDetailKeys.contains(key)) key],
  );
}

