import 'dart:convert';
import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:gilbic_mobile/src/core/auth/app_role.dart';
import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/renewals/renewal_repository.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

void main() {
  test('Client renewal repository preserves requested amount as exact text', () async {
    late http.Request captured;
    final repository = SpinaRenewalRepository(
      client: MockClient((request) async {
        captured = request;
        return http.Response(
          jsonEncode(<String, Object?>{
            'success': true,
            'data': <String, Object?>{
              'request': <String, Object?>{
                'request_id': '00000000-0000-4000-8000-000000000001',
                'client_id': '00000000-0000-4000-8000-000000000002',
                'client_code': 'CLIENT-001',
                'client_name': 'Test Client',
                'loan_id': '00000000-0000-4000-8000-000000000003',
                'loan_number': 'REG-001',
                'loan_type_name': 'Regular',
                'current_principal': '5000.00',
                'remaining_balance': '1000.00',
                'requested_amount': '9999999.99',
                'client_message': '',
                'status': 'pending',
                'submitted_at': '2026-09-13T02:00:00+00:00',
                'reviewed_at': null,
                'reviewed_by_name': null,
                'review_note': '',
                'cancelled_at': null,
              },
            },
          }),
          201,
          headers: const <String, String>{'content-type': 'application/json'},
        );
      }),
    );
    final dynamic dynamicRepository = repository;

    await dynamicRepository.submit(
      _session,
      deviceId: 'client-device',
      loanId: '00000000-0000-4000-8000-000000000003',
      requestedAmount: '9999999.99',
      message: '',
    );

    final body = jsonDecode(captured.body) as Map<String, dynamic>;
    expect(body['requested_amount'], '9999999.99');
  });

  test('Client renewal page does not parse requested money through double', () async {
    final source = await File(
      'lib/src/features/client/client_renewal_page.dart',
    ).readAsString();

    expect(source, isNot(contains('double.tryParse(')));
    expect(source, isNot(contains('final double amount;')));
  });
}

const UserSession _session = UserSession(
  userId: 'client-user',
  username: 'client',
  displayName: 'Test Client',
  role: AppRole.client,
  rawRole: 'Client',
  accessToken: 'client-token',
  permissions: <String>[],
);
