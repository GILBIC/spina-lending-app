import 'dart:convert';

import 'package:flutter_test/flutter_test.dart';
import 'package:gilbic_mobile/src/core/auth/app_role.dart';
import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/management/management_employee_activity.dart';
import 'package:gilbic_mobile/src/core/management/management_employee_activity_repository.dart';
import 'package:gilbic_mobile/src/core/network/spina_api.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

void main() {
  test(
    'loads permission-filtered rows with encoded filters and auth',
    () async {
      late http.Request captured;
      final repository = SpinaManagementEmployeeActivityRepository(
        client: MockClient((request) async {
          captured = request;
          return _response(_listPayload());
        }),
      );

      final page = await repository.listEmployees(
        _session,
        deviceId: 'management-phone',
        dateFrom: DateTime.utc(2026, 8, 1),
        dateTo: DateTime.utc(2026, 8, 29),
        query: 'Employee & Name',
        domain: ManagementEmployeeActivityDomain.accounting,
        status: ManagementEmployeeActivityStatus.completed,
        limit: 25,
        offset: 5,
      );

      expect(captured.method, 'GET');
      expect(captured.url.path, '/api/mobile/v1/management/employee-activity');
      expect(captured.url.queryParameters, <String, String>{
        'date_from': '2026-08-01',
        'date_to': '2026-08-29',
        'q': 'Employee & Name',
        'domain': 'accounting',
        'status': 'completed',
        'limit': '25',
        'offset': '5',
      });
      expect(captured.headers['authorization'], 'Bearer access-token');
      expect(captured.headers['x-device-id'], 'management-phone');
      expect(page.availableDomains, <ManagementEmployeeActivityDomain>[
        ManagementEmployeeActivityDomain.accounting,
      ]);
      expect(page.totalCount, 1);
      expect(page.rows.single.employeeName, 'Employee Name');
      expect(page.rows.single.totalVisibleCount, 1);
      expect(page.rows.single.lastActivityAt?.isUtc, isTrue);
    },
  );

  test('omitted domains remain absent and are not synthesized as zero', () {
    final page = ManagementEmployeeActivityPage.fromPayload(
      Map<String, Object?>.from(_listPayload()['data']! as Map),
    );

    expect(page.availableDomains, <ManagementEmployeeActivityDomain>[
      ManagementEmployeeActivityDomain.accounting,
    ]);
    expect(
      page.availableDomains,
      isNot(contains(ManagementEmployeeActivityDomain.payroll)),
    );
    expect(page.rows.single.totalVisibleCount, 1);
  });

  test('loads a strict read-only employee timeline', () async {
    late http.Request captured;
    final repository = SpinaManagementEmployeeActivityRepository(
      client: MockClient((request) async {
        captured = request;
        return _response(_timelinePayload());
      }),
    );

    final timeline = await repository.loadTimeline(
      _session,
      deviceId: 'management-phone',
      employeeUserId: _employeeId,
      dateFrom: DateTime.utc(2026, 8, 29),
      dateTo: DateTime.utc(2026, 8, 29),
    );

    expect(
      captured.url.path,
      '/api/mobile/v1/management/employee-activity/$_employeeId',
    );
    expect(captured.url.queryParameters, <String, String>{
      'date_from': '2026-08-29',
      'date_to': '2026-08-29',
      'limit': '100',
      'offset': '0',
    });
    expect(timeline.employeeUserId, _employeeId);
    expect(timeline.items, hasLength(1));
    expect(
      timeline.items.single.activityCode,
      ManagementEmployeeActivityCode.accountingJournalPrepared,
    );
    expect(
      timeline.items.single.navigationCode,
      ManagementEmployeeActivityNavigationCode.generalJournals,
    );
    expect(timeline.items.single.occurredAt.isUtc, isTrue);
    expect(timeline.items.single.businessDate, DateTime.utc(2026, 8, 29));
  });

  final malformedListCases = <String, void Function(Map<String, Object?>)>{
    'unknown domain': (payload) {
      _data(payload)['available_domains'] = <String>['future_domain'];
    },
    'unknown status': (payload) {
      _row(payload)['status'] = 'future_status';
    },
    'negative count': (payload) {
      _row(payload)['completed_count'] = -1;
    },
    'boolean count': (payload) {
      _row(payload)['completed_count'] = true;
    },
    'naive timestamp': (payload) {
      _row(payload)['last_activity_at'] = '2026-08-29T04:15:30';
    },
    'invalid UUID': (payload) {
      _row(payload)['employee_user_id'] = 'not-a-uuid';
    },
    'invalid calendar date': (payload) {
      _data(payload)['date_to'] = '2026-02-30';
    },
    'overlong employee name': (payload) {
      _row(payload)['employee_name'] = 'x' * 201;
    },
    'missing required field': (payload) {
      _row(payload).remove('status_message');
    },
    'non-list rows': (payload) {
      _data(payload)['rows'] = <String, Object?>{};
    },
  };

  for (final malformedCase in malformedListCases.entries) {
    test('rejects ${malformedCase.key} list data', () async {
      final payload = _listPayload();
      malformedCase.value(payload);
      final repository = _repositoryReturning(payload);

      await expectLater(
        repository.listEmployees(
          _session,
          deviceId: 'management-phone',
          dateFrom: DateTime.utc(2026, 8, 29),
          dateTo: DateTime.utc(2026, 8, 29),
        ),
        throwsA(
          isA<SpinaApiException>().having(
            (error) => error.code,
            'code',
            'invalid_management_employee_activity',
          ),
        ),
      );
    });
  }

  final malformedTimelineCases = <String, void Function(Map<String, Object?>)>{
    'unknown activity code': (payload) {
      _item(payload)['activity_code'] = 'future.activity';
    },
    'unknown navigation code': (payload) {
      _item(payload)['navigation_code'] = 'future.destination';
    },
    'unknown item domain': (payload) {
      _item(payload)['domain'] = 'future_domain';
    },
    'non-list items': (payload) {
      _data(payload)['items'] = <String, Object?>{};
    },
  };

  for (final malformedCase in malformedTimelineCases.entries) {
    test('rejects ${malformedCase.key} timeline data', () async {
      final payload = _timelinePayload();
      malformedCase.value(payload);
      final repository = _repositoryReturning(payload);

      await expectLater(
        repository.loadTimeline(
          _session,
          deviceId: 'management-phone',
          employeeUserId: _employeeId,
          dateFrom: DateTime.utc(2026, 8, 29),
          dateTo: DateTime.utc(2026, 8, 29),
        ),
        throwsA(
          isA<SpinaApiException>().having(
            (error) => error.code,
            'code',
            'invalid_management_employee_activity',
          ),
        ),
      );
    });
  }

  test('rejects malformed success envelopes', () async {
    final repository = _repositoryReturning(<String, Object?>{
      'success': true,
      'data': 'not-an-object',
    });

    await expectLater(
      repository.listEmployees(
        _session,
        deviceId: 'management-phone',
        dateFrom: DateTime.utc(2026, 8, 29),
        dateTo: DateTime.utc(2026, 8, 29),
      ),
      throwsA(
        isA<SpinaApiException>().having(
          (error) => error.code,
          'code',
          'invalid_management_employee_activity',
        ),
      ),
    );
  });

  test('preserves safe FastAPI detail on a denied domain', () async {
    final repository = SpinaManagementEmployeeActivityRepository(
      client: MockClient(
        (request) async => _response(<String, Object?>{
          'detail': <String, Object?>{
            'code': 'employee_activity_domain_forbidden',
            'message': 'The requested domain is not permitted.',
          },
        }, statusCode: 403),
      ),
    );

    await expectLater(
      repository.listEmployees(
        _session,
        deviceId: 'management-phone',
        dateFrom: DateTime.utc(2026, 8, 29),
        dateTo: DateTime.utc(2026, 8, 29),
      ),
      throwsA(
        isA<SpinaApiException>()
            .having((error) => error.statusCode, 'statusCode', 403)
            .having(
              (error) => error.code,
              'code',
              'employee_activity_domain_forbidden',
            )
            .having(
              (error) => error.message,
              'message',
              'The requested domain is not permitted.',
            ),
      ),
    );
  });

  test('converts transport failures to a safe unavailable error', () async {
    final repository = SpinaManagementEmployeeActivityRepository(
      client: MockClient((request) async => throw Exception('socket detail')),
    );

    await expectLater(
      repository.listEmployees(
        _session,
        deviceId: 'management-phone',
        dateFrom: DateTime.utc(2026, 8, 29),
        dateTo: DateTime.utc(2026, 8, 29),
      ),
      throwsA(
        isA<SpinaApiException>()
            .having((error) => error.code, 'code', 'network_unavailable')
            .having(
              (error) => error.message,
              'message',
              isNot(contains('socket detail')),
            ),
      ),
    );
  });

  test('validates request pagination and date ranges locally', () async {
    final repository = _repositoryReturning(_listPayload());

    expect(
      () => repository.listEmployees(
        _session,
        deviceId: 'management-phone',
        dateFrom: DateTime.utc(2026, 8, 30),
        dateTo: DateTime.utc(2026, 8, 29),
      ),
      throwsArgumentError,
    );
    expect(
      () => repository.listEmployees(
        _session,
        deviceId: 'management-phone',
        dateFrom: DateTime.utc(2026, 8, 29),
        dateTo: DateTime.utc(2026, 8, 29),
        limit: 101,
      ),
      throwsArgumentError,
    );
  });
}

const _employeeId = '33333333-3333-4333-8333-333333333333';
const _recordId = '44444444-4444-4444-8444-444444444444';

const _session = UserSession(
  userId: '22222222-2222-4222-8222-222222222222',
  username: 'manager',
  displayName: 'Management User',
  role: AppRole.management,
  rawRole: 'management',
  accessToken: 'access-token',
  permissions: <String>['employee.activity.review', 'accounting.view'],
);

SpinaManagementEmployeeActivityRepository _repositoryReturning(
  Map<String, Object?> payload,
) => SpinaManagementEmployeeActivityRepository(
  client: MockClient((request) async => _response(payload)),
);

http.Response _response(Map<String, Object?> payload, {int statusCode = 200}) =>
    http.Response(jsonEncode(payload), statusCode);

Map<String, Object?> _listPayload() => <String, Object?>{
  'success': true,
  'data': <String, Object?>{
    'date_from': '2026-08-29',
    'date_to': '2026-08-29',
    'generated_at': '2026-08-29T04:15:30+00:00',
    'available_domains': <String>['accounting'],
    'total_count': 1,
    'rows': <Object?>[
      <String, Object?>{
        'employee_user_id': _employeeId,
        'employee_name': 'Employee Name',
        'function_labels': <String>[],
        'completed_count': 1,
        'in_progress_count': 0,
        'awaiting_review_count': 0,
        'needs_attention_count': 0,
        'total_visible_count': 1,
        'last_activity_at': '2026-08-29T04:15:30+00:00',
        'last_activity_domain': 'accounting',
        'status': 'completed',
        'status_message': '1 visible item completed.',
      },
    ],
  },
};

Map<String, Object?> _timelinePayload() => <String, Object?>{
  'success': true,
  'data': <String, Object?>{
    'employee_user_id': _employeeId,
    'employee_name': 'Employee Name',
    'function_labels': <String>[],
    'date_from': '2026-08-29',
    'date_to': '2026-08-29',
    'generated_at': '2026-08-29T04:15:30+00:00',
    'available_domains': <String>['accounting'],
    'total_count': 1,
    'items': <Object?>[
      <String, Object?>{
        'activity_code': 'accounting.journal.prepared',
        'domain': 'accounting',
        'occurred_at': '2026-08-29T04:15:30+00:00',
        'business_date': '2026-08-29',
        'record_type': 'journal_entry',
        'record_id': _recordId,
        'display_reference': 'Journal draft',
        'summary': 'Prepared journal entry',
        'workflow_state': 'draft',
        'status': 'in_progress',
        'maker_name': 'Employee Name',
        'checker_name': null,
        'navigation_code': 'management.general_journals',
      },
    ],
  },
};

Map<String, Object?> _data(Map<String, Object?> payload) =>
    payload['data']! as Map<String, Object?>;

Map<String, Object?> _row(Map<String, Object?> payload) =>
    (_data(payload)['rows']! as List).single as Map<String, Object?>;

Map<String, Object?> _item(Map<String, Object?> payload) =>
    (_data(payload)['items']! as List).single as Map<String, Object?>;
