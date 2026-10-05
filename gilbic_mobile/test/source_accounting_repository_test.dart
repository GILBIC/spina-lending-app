import 'dart:convert';
import 'package:flutter_test/flutter_test.dart';
import 'package:gilbic_mobile/src/core/auth/app_role.dart';
import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/management/source_accounting_repository.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

void main() {
  test(
    'read and explicit write retain device scope and exact submitted evidence',
    () async {
      const session = UserSession(
        userId: 'manager',
        username: 'manager',
        displayName: 'Manager',
        role: AppRole.management,
        rawRole: 'Management',
        accessToken: 'private',
      );
      final requests = <http.Request>[];
      final repository = SpinaSourceAccountingRepository(
        client: MockClient((request) async {
          requests.add(request);
          return http.Response(
            jsonEncode({
              'success': true,
              'data': {'saved': true},
            }),
            200,
          );
        }),
      );
      final body = {
        'request_id': 'unchanged',
        'expected_amount': '90071992547409.93',
        'evidence_reference': 'Agreement A',
      };
      await repository.read(
        session,
        deviceId: 'phone',
        path: '$sourceAccountingBase/liabilities',
      );
      await repository.write(
        session,
        deviceId: 'phone',
        path: '$sourceAccountingBase/liabilities',
        body: body,
      );
      expect(requests.map((request) => request.method), ['GET', 'POST']);
      expect(jsonDecode(requests.last.body), body);
      for (final request in requests) {
        expect(request.headers['Authorization'], 'Bearer private');
        expect(request.headers['X-Device-Id'], 'phone');
      }
    },
  );
  test('liability schedule does not accept absent inventory as complete', () {
    expect(
      () => validateLiabilitySchedule({
        'book': {'book_id': 'book'},
        'as_of': '2026-09-30',
        'comprehensive_source_coverage': false,
        'registered_controls_reconciled': true,
      }, 'book'),
      throwsFormatException,
    );
  });
  test('calendar dates and fingerprints reject malformed evidence', () {
    expect(accountingDate('2026-02-30'), isFalse);
    expect(accountingDigest('test'), isFalse);
    expect(accountingDigest('a' * 64), isTrue);
  });
}
