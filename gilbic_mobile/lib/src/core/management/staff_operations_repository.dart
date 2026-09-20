import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/device/device_identity.dart';
import 'package:gilbic_mobile/src/core/network/spina_api.dart';
import 'package:gilbic_mobile/src/core/network/staff_operations_client.dart';
import 'package:http/http.dart' as http;

String _money(Map<String, dynamic> data, String key) {
  final value = data[key];
  if (value is! String || !RegExp(r'^-?\d+(?:\.\d{1,2})?$').hasMatch(value)) {
    throw const SpinaApiException(
      'The server returned an invalid financial amount.',
    );
  }
  return value;
}

class PastDueReasonRow {
  PastDueReasonRow.fromJson(Map<String, dynamic> data)
    : client = requiredStaffText(data, 'client_name'),
      collector = data['collector_name']?.toString() ?? 'Unassigned',
      area = data['area']?.toString() ?? 'Unassigned',
      reason = requiredStaffText(data, 'reason_label'),
      event = requiredStaffText(data, 'event_kind_label'),
      count = data['event_count'] as int,
      total = _money(data, 'total_past_due_amount'),
      remaining = _money(data, 'remaining_past_due_amount');
  final String client, collector, area, reason, event, total, remaining;
  final int count;
}

class PastDueReport {
  PastDueReport.fromJson(Map<String, dynamic> data)
    : available = data['schema_available'] == true,
      count = stringMap(data['summary'])['event_count'] as int,
      total = _money(stringMap(data['summary']), 'total_past_due_amount'),
      remaining = _money(
        stringMap(data['summary']),
        'remaining_past_due_amount',
      ),
      rows = staffRecords(data, 'rows').map(PastDueReasonRow.fromJson).toList();
  final bool available;
  final int count;
  final String total, remaining;
  final List<PastDueReasonRow> rows;
}

class ManagedClientCredentials {
  ManagedClientCredentials.fromJson(Map<String, dynamic> data)
    : username = requiredStaffText(stringMap(data['credentials']), 'username'),
      password = requiredStaffText(stringMap(data['credentials']), 'password'),
      deliverySent = stringMap(data['delivery'])['sent'] as bool,
      deliveryDetail = requiredStaffText(
        stringMap(data['delivery']),
        'detail',
      ) {
    if (stringMap(data['account'])['username'] != username) {
      throw const SpinaApiException(
        'The server returned mismatched account credentials.',
      );
    }
  }
  final String username, password, deliveryDetail;
  final bool deliverySent;
}

class StaffOperationsRepository {
  StaffOperationsRepository({
    required DeviceIdentityProvider deviceIdentityProvider,
    http.Client? client,
  }) : _api = StaffOperationsClient(
         deviceIdentityProvider: deviceIdentityProvider,
         client: client,
       );
  final StaffOperationsClient _api;
  void close() => _api.close();

  Future<PastDueReport> pastDue(
    UserSession s,
    Map<String, String> filters,
  ) async {
    requireStaffPermission(s, [
      'management.dashboard.view',
    ], managementOnly: true);
    return PastDueReport.fromJson(
      await _api.request(
        s,
        'GET',
        '/api/v1/management/past-due/reasons',
        query: {...filters, 'limit': '500'},
      ),
    );
  }

  Future<List<Map<String, dynamic>>> candidates(
    UserSession s,
    String query,
  ) async {
    requireStaffPermission(s, ['account.manage'], managementOnly: true);
    final records = staffRecords(
      await _api.request(
        s,
        'GET',
        '/api/v1/management/client-link-candidates',
        query: {'q': query, 'limit': '50'},
      ),
      'clients',
    );
    for (final row in records) {
      requiredStaffText(row, 'id');
      requiredStaffText(row, 'full_name');
    }
    return records;
  }

  Future<ManagedClientCredentials> createAccount(
    UserSession s,
    String clientId,
    String email,
  ) async {
    requireStaffPermission(s, ['account.manage'], managementOnly: true);
    return ManagedClientCredentials.fromJson(
      await _api.request(
        s,
        'POST',
        '/api/v1/management/client-accounts',
        body: {'client_id': clientId, 'email': email.trim().toLowerCase()},
      ),
    );
  }
}
