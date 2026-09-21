import 'dart:convert';

import 'package:flutter_test/flutter_test.dart';
import 'package:gilbic_mobile/src/core/auth/app_role.dart';
import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/network/spina_api.dart';
import 'package:gilbic_mobile/src/core/remittance/collector_cash_accountability_repository.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

void main() {
  test('loads authoritative cash totals using the approved-device request',
      () async {
    final repository = SpinaCollectorCashAccountabilityRepository(
      client: MockClient((request) async {
        expect(request.method, 'GET');
        expect(request.url.path, '/api/mobile/v1/collector/cash-accountability');
        expect(request.headers['Authorization'], 'Bearer test-token');
        expect(request.headers['X-Device-Id'], 'cash-test-device');
        return _response(_payload());
      }),
    );
    final result = await repository.load(_session, deviceId: 'cash-test-device');
    expect(result.totalCashHeld, 555);
    expect(result.assignedAreaCashHeld, 505);
    expect(result.otherAreaCashHeld, 50);
    expect(result.otherAreaByCollector.single.amount, 50);
  });

  for (final total in <Object>['0.00', 0, 0.0, '-25.50', -25.5]) {
    test('accepts legitimate finite cash total $total (${total.runtimeType})',
        () {
      final payload = _payload()
        ..['total_cash_held'] = total
        ..['assigned_area_cash_held'] = total
        ..['other_area_cash_held'] = total;
      final result = CollectorCashAccountability.fromPayload(payload);
      final expected = total.toString().startsWith('-') ? -25.5 : 0.0;
      expect(result.totalCashHeld, expected);
      expect(result.assignedAreaCashHeld, expected);
      expect(result.otherAreaCashHeld, expected);
    });
  }

  for (final field in <String>[
    'total_cash_held',
    'assigned_area_cash_held',
    'other_area_cash_held',
  ]) {
    test('rejects missing $field instead of displaying zero', () async {
      final payload = _payload()..remove(field);
      await _expectInvalid(payload);
    });

    for (final invalid in <Object?>[
      null,
      '',
      'unavailable',
      'NaN',
      'Infinity',
      '-Infinity',
      true,
      <String, Object?>{},
    ]) {
      test('rejects invalid $field value $invalid instead of a cash amount',
          () async {
        await _expectInvalid(_payload()..[field] = invalid);
      });
    }

    test('rejects nonfinite numeric $field before it reaches the card', () {
      for (final value in <double>[double.nan, double.infinity]) {
        expect(
          () => CollectorCashAccountability.fromPayload(
            _payload()..[field] = value,
          ),
          throwsA(isA<SpinaApiException>().having(
            (error) => error.code,
            'code',
            'invalid_server_response',
          )),
        );
      }
    });
  }
}

Future<void> _expectInvalid(Map<String, Object?> payload) async {
  final repository = SpinaCollectorCashAccountabilityRepository(
    client: MockClient((request) async => _response(payload)),
  );
  await expectLater(
    repository.load(_session, deviceId: 'cash-test-device'),
    throwsA(isA<SpinaApiException>().having(
      (error) => error.code,
      'code',
      'invalid_server_response',
    )),
  );
}

http.Response _response(Map<String, Object?> payload) => http.Response(
      jsonEncode(<String, Object?>{'success': true, 'data': payload}),
      200,
      headers: const <String, String>{'content-type': 'application/json'},
    );

Map<String, Object?> _payload() => <String, Object?>{
      'total_cash_held': '555.00',
      'assigned_area_cash_held': '505.00',
      'other_area_cash_held': '50.00',
      'other_area_by_collector': <Object?>[
        <String, Object?>{
          'collector_user_id': 'other-collector',
          'collector_name': 'Another Collector',
          'amount': '50.00',
        },
      ],
      'ready_to_remit_amount': '455.00',
      'ready_to_remit_count': 3,
      'awaiting_acceptance_amount': '100.00',
      'awaiting_acceptance_count': 1,
    };

const _session = UserSession(
  userId: 'cash-test-collector',
  username: 'cash.test.collector',
  displayName: 'Cash Test Collector',
  role: AppRole.collector,
  rawRole: 'Collector',
  accessToken: 'test-token',
  permissions: <String>['remittance.view'],
);
