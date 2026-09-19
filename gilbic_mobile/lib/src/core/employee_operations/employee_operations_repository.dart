import 'dart:convert';
import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/network/spina_api.dart';
import 'package:gilbic_mobile/src/core/network/staff_operations_client.dart';

const employeeCollections = [
  'profiles',
  'schedules',
  'backups',
  'calendar',
  'statutory_months',
  'statutory_remittances',
  'attendance',
  'attendance_days',
  'requests',
  'leave_balances',
  'leave_ledger',
  'tasks',
  'advances',
  'shortages',
  'payroll',
  'payments',
  'accounting_preparations',
  'payroll_history',
  'history',
];

class EmployeeWorkspace {
  EmployeeWorkspace._(this.data);
  final Map<String, dynamic> data;
  static EmployeeWorkspace parse(
    Map<String, dynamic> data,
    UserSession session,
  ) {
    if (data['contract_version'] != 1 ||
        stringMap(data['actor'])['user_id'] != session.userId ||
        data['capabilities'] is! Map ||
        data['setup_missing'] is! List ||
        employeeCollections.any(
          (key) =>
              data[key] is! List || (data[key] as List).any((e) => e is! Map),
        )) {
      throw const FormatException(
        'The server returned incomplete employee records.',
      );
    }
    return EmployeeWorkspace._(data);
  }

  Map<String, dynamic> get actor => stringMap(data['actor']);
  bool can(String capability) =>
      stringMap(data['capabilities'])[capability] == true;
  List<Map<String, dynamic>> records(String collection) =>
      (data[collection] as List? ?? []).map(stringMap).toList();
  List<String> get setupMissing => stringList(data['setup_missing']);
  List<Map<String, dynamic>> historyFor(String domain, String recordId) =>
      records('history')
          .where(
            (row) => row['domain'] == domain && row['record_id'] == recordId,
          )
          .toList();
  List<Map<String, dynamic>> get accounts =>
      (data['account_candidates'] as List? ?? []).map(stringMap).toList();
  String employeeName(String? id) {
    for (final account in accounts) {
      if (account['user_id'] == id) {
        return account['full_name'] as String? ??
            account['username'] as String? ??
            'Employee';
      }
    }
    for (final record in records('profiles')) {
      if (record['employee_id'] == id) {
        return stringMap(record['payload'])['full_name'] as String? ??
            'Employee';
      }
    }
    return id == actor['user_id'] ? 'My records' : 'Employee';
  }
}

class EmployeeAttempt {
  EmployeeAttempt(Map<String, dynamic> command) : _json = jsonEncode(command);
  final String _json;
  Map<String, dynamic> get command => jsonDecode(_json) as Map<String, dynamic>;
  String get requestId => command['request_id'] as String;
  String get id => command['id'] as String;
}

class EmployeeUncertain implements Exception {
  const EmployeeUncertain();
  @override
  String toString() =>
      'The server outcome is unconfirmed. Keep this request unchanged and check its status before continuing.';
}

class EmployeeOperationsRepository {
  EmployeeOperationsRepository(this.client);
  final StaffOperationsClient client;
  static const path = '/api/v1/employee-operations';
  Future<EmployeeWorkspace> workspace(
    UserSession session, {
    String? requestId,
  }) async => EmployeeWorkspace.parse(
    await client.request(
      session,
      'GET',
      '$path/workspace',
      query: requestId == null ? null : {'request_id': requestId},
    ),
    session,
  );

  Map<String, dynamic> validateResult(
    Map<String, dynamic> result,
    EmployeeAttempt attempt,
  ) {
    if (result['id'] != attempt.id ||
        result['request_id'] != attempt.requestId ||
        result['version'] is! int ||
        (result['version'] as int) < 1 ||
        !const ['accepted', 'pending_review'].contains(result['status'])) {
      throw const EmployeeUncertain();
    }
    return result;
  }

  Future<Map<String, dynamic>> submit(
    UserSession session,
    EmployeeAttempt attempt,
  ) async {
    try {
      return validateResult(
        await client.request(
          session,
          'POST',
          '$path/actions',
          body: attempt.command,
        ),
        attempt,
      );
    } on SpinaApiException catch (error) {
      if (error.statusCode != null &&
          error.statusCode! >= 400 &&
          error.statusCode! < 500) {
        rethrow;
      }
      throw const EmployeeUncertain();
    } on Exception {
      throw const EmployeeUncertain();
    }
  }

  Future<Map<String, dynamic>?> check(
    UserSession session,
    EmployeeAttempt attempt,
  ) async {
    final data = await workspace(session, requestId: attempt.requestId);
    if (data.data['last_result'] == null) return null;
    return validateResult(stringMap(data.data['last_result']), attempt);
  }

  void close() => client.close();
}
