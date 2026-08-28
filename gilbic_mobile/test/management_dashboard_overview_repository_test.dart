import 'dart:convert';

import 'package:flutter_test/flutter_test.dart';
import 'package:gilbic_mobile/src/core/auth/app_role.dart';
import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/management/management_dashboard_overview.dart';
import 'package:gilbic_mobile/src/core/management/management_dashboard_overview_repository.dart';
import 'package:gilbic_mobile/src/core/network/spina_api.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

void main() {
  test(
    'loads the protected mobile overview with bearer and device headers',
    () async {
      late http.Request captured;
      final repository = SpinaManagementDashboardOverviewRepository(
        client: MockClient((request) async {
          captured = request;
          return _response(_validPayload());
        }),
      );

      final overview = await repository.loadOverview(
        _session,
        deviceId: 'management-phone',
      );

      expect(captured.method, 'GET');
      expect(captured.url.path, '/api/mobile/v1/management/dashboard-overview');
      expect(captured.headers['accept'], 'application/json');
      expect(captured.headers['authorization'], 'Bearer access-token');
      expect(captured.headers['x-device-id'], 'management-phone');
      expect(captured.headers['x-session-id'], isNull);
      expect(overview.currency, 'PHP');
      expect(overview.generatedAt.isUtc, isTrue);
      expect(
        overview
            .metric(ManagementDashboardMetricKey.outstandingBalance)
            ?.amount,
        '987654.32',
      );
      expect(
        overview
            .metric(ManagementDashboardMetricKey.latestCollections)
            ?.asOfDate,
        DateTime.utc(2026, 8, 28),
      );
      expect(overview.ignoredMetricKeys, isEmpty);
    },
  );

  final malformedCases = <String, Map<String, Object?> Function()>{
    'missing timestamp': () {
      final payload = _validPayload();
      _data(payload).remove('generated_at');
      return payload;
    },
    'offset-free timestamp': () {
      final payload = _validPayload();
      _data(payload)['generated_at'] = '2026-08-29T04:15:30';
      return payload;
    },
    'non-PHP currency': () {
      final payload = _validPayload();
      _data(payload)['currency'] = 'USD';
      return payload;
    },
    'non-list metrics': () {
      final payload = _validPayload();
      _data(payload)['metrics'] = <String, Object?>{};
      return payload;
    },
    'duplicate known key': () {
      final payload = _validPayload();
      _metrics(
        payload,
      ).add(<String, Object?>{'key': 'portfolio.active_clients', 'count': 99});
      return payload;
    },
    'negative count': () {
      final payload = _validPayload();
      _metric(payload, 'portfolio.active_clients')['count'] = -1;
      return payload;
    },
    'boolean count': () {
      final payload = _validPayload();
      _metric(payload, 'portfolio.active_clients')['count'] = true;
      return payload;
    },
    'number-valued amount': () {
      final payload = _validPayload();
      _metric(payload, 'portfolio.outstanding_balance')['amount'] = 987654.32;
      return payload;
    },
    'negative amount': () {
      final payload = _validPayload();
      _metric(payload, 'portfolio.outstanding_balance')['amount'] = '-1.00';
      return payload;
    },
    'amount without fixed two decimals': () {
      final payload = _validPayload();
      _metric(payload, 'portfolio.outstanding_balance')['amount'] = '1.0';
      return payload;
    },
    'metric missing both count and amount': () {
      final payload = _validPayload();
      final metric = _metric(payload, 'portfolio.active_clients');
      metric.remove('count');
      return payload;
    },
    'invalid calendar date': () {
      final payload = _validPayload();
      _metric(payload, 'collections.latest_day')['as_of_date'] = '2026-02-30';
      return payload;
    },
    'invalid field combination': () {
      final payload = _validPayload();
      _metric(payload, 'portfolio.active_clients')['amount'] = '1.00';
      return payload;
    },
    'unexpected known-metric field': () {
      final payload = _validPayload();
      _metric(payload, 'portfolio.active_clients')['client_name'] =
          'Hidden PII';
      return payload;
    },
  };

  for (final malformedCase in malformedCases.entries) {
    test(
      'rejects ${malformedCase.key} with the strict overview code',
      () async {
        final repository = _repositoryReturning(malformedCase.value());

        await expectLater(
          repository.loadOverview(_session, deviceId: 'management-phone'),
          throwsA(
            isA<SpinaApiException>().having(
              (error) => error.code,
              'code',
              'invalid_management_dashboard_overview',
            ),
          ),
        );
      },
    );
  }

  test(
    'ignores an unknown server metric key for forward compatibility',
    () async {
      final payload = _validPayload();
      _metrics(payload).insert(1, <String, Object?>{
        'key': 'future.cash_risk',
        'signal': <String, Object?>{'level': 'amber'},
      });
      final repository = _repositoryReturning(payload);

      final overview = await repository.loadOverview(
        _session,
        deviceId: 'management-phone',
      );

      expect(overview.metrics, hasLength(7));
      expect(overview.ignoredMetricKeys, <String>['future.cash_risk']);
      expect(
        ManagementDashboardMetricKey.values
            .map((key) => overview.metric(key))
            .whereType<ManagementDashboardMetric>(),
        hasLength(7),
      );
    },
  );

  test('converts transport failures to network_unavailable', () async {
    final repository = SpinaManagementDashboardOverviewRepository(
      client: MockClient((request) async {
        throw Exception('socket detail');
      }),
    );

    await expectLater(
      repository.loadOverview(_session, deviceId: 'management-phone'),
      throwsA(
        isA<SpinaApiException>().having(
          (error) => error.code,
          'code',
          'network_unavailable',
        ),
      ),
    );
  });

  test('converts unreadable JSON to invalid_server_response', () async {
    final repository = SpinaManagementDashboardOverviewRepository(
      client: MockClient((request) async => http.Response('{broken', 200)),
    );

    await expectLater(
      repository.loadOverview(_session, deviceId: 'management-phone'),
      throwsA(
        isA<SpinaApiException>().having(
          (error) => error.code,
          'code',
          'invalid_server_response',
        ),
      ),
    );
  });

  test('preserves safe FastAPI error detail on non-2xx responses', () async {
    final repository = SpinaManagementDashboardOverviewRepository(
      client: MockClient(
        (request) async => _response(<String, Object?>{
          'detail': <String, Object?>{
            'code': 'management_dashboard_permission_required',
            'message': 'Management dashboard permission is required.',
          },
        }, statusCode: 403),
      ),
    );

    await expectLater(
      repository.loadOverview(_session, deviceId: 'management-phone'),
      throwsA(
        isA<SpinaApiException>()
            .having((error) => error.statusCode, 'statusCode', 403)
            .having(
              (error) => error.code,
              'code',
              'management_dashboard_permission_required',
            )
            .having(
              (error) => error.message,
              'message',
              'Management dashboard permission is required.',
            ),
      ),
    );
  });
}

SpinaManagementDashboardOverviewRepository _repositoryReturning(
  Map<String, Object?> payload,
) {
  return SpinaManagementDashboardOverviewRepository(
    client: MockClient((request) async => _response(payload)),
  );
}

http.Response _response(Map<String, Object?> payload, {int statusCode = 200}) {
  return http.Response(
    jsonEncode(payload),
    statusCode,
    headers: const <String, String>{'content-type': 'application/json'},
  );
}

Map<String, Object?> _validPayload() {
  return <String, Object?>{
    'success': true,
    'data': <String, Object?>{
      'generated_at': '2026-08-29T04:15:30+00:00',
      'currency': 'PHP',
      'metrics': <Object?>[
        <String, Object?>{'key': 'portfolio.active_clients', 'count': 41},
        <String, Object?>{'key': 'portfolio.active_loans', 'count': 48},
        <String, Object?>{'key': 'portfolio.overdue_loans', 'count': 7},
        <String, Object?>{
          'key': 'portfolio.outstanding_balance',
          'amount': '987654.32',
        },
        <String, Object?>{
          'key': 'collections.latest_day',
          'count': 32,
          'amount': '18450.00',
          'as_of_date': '2026-08-28',
        },
        <String, Object?>{
          'key': 'collections.unremitted',
          'count': 6,
          'amount': '3750.50',
        },
        <String, Object?>{'key': 'activity.unread', 'count': 9},
      ],
    },
  };
}

Map<String, Object?> _data(Map<String, Object?> payload) {
  return payload['data']! as Map<String, Object?>;
}

List<Object?> _metrics(Map<String, Object?> payload) {
  return _data(payload)['metrics']! as List<Object?>;
}

Map<String, Object?> _metric(Map<String, Object?> payload, String key) {
  return _metrics(payload).whereType<Map<String, Object?>>().singleWhere(
    (metric) => metric['key'] == key,
  );
}

const _session = UserSession(
  userId: '99999999-9999-4999-8999-999999999999',
  username: 'manager.one',
  displayName: 'Manager One',
  role: AppRole.management,
  rawRole: 'management',
  accessToken: 'access-token',
  permissions: <String>['management.dashboard.view'],
);
