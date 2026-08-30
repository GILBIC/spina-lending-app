import 'dart:convert';

import 'package:flutter_test/flutter_test.dart';
import 'package:gilbic_mobile/src/core/auth/app_role.dart';
import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/management/management_alerts_audit.dart';
import 'package:gilbic_mobile/src/core/management/management_alerts_audit_repository.dart';
import 'package:gilbic_mobile/src/core/network/spina_api.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

void main() {
  test(
    'loads the read-only permission-filtered Management projection',
    () async {
      late http.Request captured;
      final repository = SpinaManagementAlertsAuditRepository(
        client: MockClient((request) async {
          captured = request;
          return _response(_validPayload());
        }),
      );

      final snapshot = await repository.loadSnapshot(
        _session,
        deviceId: 'management-phone',
        windowDays: 14,
        limit: 25,
      );

      expect(captured.method, 'GET');
      expect(captured.url.path, '/api/mobile/v1/management/alerts-audit');
      expect(captured.url.queryParameters, <String, String>{
        'window_days': '14',
        'limit': '25',
      });
      expect(captured.headers['authorization'], 'Bearer access-token');
      expect(captured.headers['x-device-id'], 'management-phone');
      expect(snapshot.generatedAt.isUtc, isTrue);
      expect(snapshot.visibleDomains, <ManagementAlertsAuditDomain>[
        ManagementAlertsAuditDomain.paymentUpdates,
        ManagementAlertsAuditDomain.remittanceCustody,
        ManagementAlertsAuditDomain.financial,
      ]);
      expect(snapshot.alerts.single.amount, '1450.00');
      expect(snapshot.events.last.sourceLabel, 'Tax Recoverable refund');
    },
  );

  final malformedCases = <String, void Function(Map<String, Object?>)>{
    'unknown alert code': (payload) =>
        _alerts(payload).single['code'] = 'future.alert',
    'mismatched alert domain': (payload) =>
        _alerts(payload).single['domain'] = 'financial',
    'unknown event action': (payload) =>
        _events(payload).single['action_code'] = 'financial.unknown',
    'unreviewed financial source': (payload) =>
        _events(payload).single['source_type'] = 'future_source',
    'offset-free timestamp': (payload) =>
        _data(payload)['generated_at'] = '2026-08-30T03:05:00',
    'duplicate visible domain': (payload) =>
        (_data(payload)['visible_domains']! as List<Object?>).add('financial'),
    'boolean total': (payload) => _data(payload)['event_total_count'] = true,
    'unexpected private field': (payload) =>
        _events(payload).single['details'] = <String, Object?>{
          'phone': 'must not pass',
        },
  };
  for (final malformedCase in malformedCases.entries) {
    test('rejects ${malformedCase.key}', () async {
      final payload = _validPayload();
      malformedCase.value(payload);
      final repository = SpinaManagementAlertsAuditRepository(
        client: MockClient((request) async => _response(payload)),
      );

      await expectLater(
        repository.loadSnapshot(_session, deviceId: 'management-phone'),
        throwsA(
          isA<SpinaApiException>().having(
            (error) => error.code,
            'code',
            'invalid_management_alerts_audit',
          ),
        ),
      );
    });
  }

  test('preserves a safe FastAPI error without leaking transport detail', () {
    final repository = SpinaManagementAlertsAuditRepository(
      client: MockClient(
        (request) async => _response(<String, Object?>{
          'detail': <String, Object?>{
            'code': 'management_alerts_audit_unavailable',
            'message': 'Management alerts are temporarily unavailable.',
          },
        }, statusCode: 503),
      ),
    );

    expect(
      repository.loadSnapshot(_session, deviceId: 'management-phone'),
      throwsA(
        isA<SpinaApiException>()
            .having((error) => error.statusCode, 'statusCode', 503)
            .having(
              (error) => error.code,
              'code',
              'management_alerts_audit_unavailable',
            ),
      ),
    );
  });
}

http.Response _response(Map<String, Object?> payload, {int statusCode = 200}) {
  return http.Response(
    jsonEncode(payload),
    statusCode,
    headers: const <String, String>{'content-type': 'application/json'},
  );
}

Map<String, Object?> _validPayload() => <String, Object?>{
  'success': true,
  'data': <String, Object?>{
    'generated_at': '2026-08-30T03:05:00+00:00',
    'window_days': 14,
    'limit': 25,
    'currency': 'PHP',
    'visible_domains': <Object?>[
      'payment_updates',
      'remittance_custody',
      'financial',
    ],
    'alerts': <Object?>[
      <String, Object?>{
        'code': 'assigned_remittances',
        'domain': 'remittance_custody',
        'title': 'Remittances assigned for review',
        'count': 3,
        'amount': '1450.00',
        'severity': 'review',
        'navigation_code': 'remittance_review',
      },
    ],
    'events': <Object?>[
      <String, Object?>{
        'event_key': 'financial:91',
        'domain': 'financial',
        'action_code': 'financial.posted',
        'title': 'Protected journal posted',
        'severity': 'attention',
        'navigation_code': 'financial_accounting',
        'occurred_at': '2026-08-30T03:00:00+00:00',
        'business_date': '2026-08-30',
        'record_id': '44444444-4444-4444-8444-444444444444',
        'reference': 'GJ-2026-00000091',
        'current_state': 'posted',
        'actor_name': 'Accounting Manager',
        'checker_name': 'Accounting Manager',
        'source_type': 'v1_tax_recoverable_refund',
        'source_label': 'Tax Recoverable refund',
        'reason': null,
      },
    ],
    'event_total_count': 1,
    'notice': 'Read-only visibility.',
  },
};

Map<String, Object?> _data(Map<String, Object?> payload) =>
    payload['data']! as Map<String, Object?>;

List<Map<String, Object?>> _alerts(Map<String, Object?> payload) =>
    (_data(payload)['alerts']! as List<Object?>).cast<Map<String, Object?>>();

List<Map<String, Object?>> _events(Map<String, Object?> payload) =>
    (_data(payload)['events']! as List<Object?>).cast<Map<String, Object?>>();

const _session = UserSession(
  userId: '22222222-2222-4222-8222-222222222222',
  username: 'manager',
  displayName: 'Management User',
  role: AppRole.management,
  rawRole: 'Management',
  accessToken: 'access-token',
  permissions: <String>['management.dashboard.view'],
);
