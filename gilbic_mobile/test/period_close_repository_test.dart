import 'dart:convert';

import 'package:flutter_test/flutter_test.dart';
import 'package:gilbic_mobile/src/core/auth/app_role.dart';
import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/management/period_close.dart';
import 'package:gilbic_mobile/src/core/management/period_close_repository.dart';
import 'package:gilbic_mobile/src/core/network/spina_api.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

void main() {
  for (final label in ['Empty first period', 'Capital-only first period']) {
    test(
      '$label prepares and closes with audited null journal coordinates',
      () async {
        final requests = <http.Request>[];
        final prepared = <String, Object?>{
          ..._preparedItemPayload,
          'label': label,
          'journal_entry_id': null,
          'temporary_account_count': 0,
          'net_income': '0.00',
          'retained_earnings_balance_before': '0.00',
        };
        final closed = <String, Object?>{
          ...prepared,
          'fiscal_period_status': 'closed',
          'close_status': 'closed_protected',
          'close_posting_id': '55555555-5555-4555-8555-555555555555',
          'retained_earnings_balance_after': '0.00',
          'closed_by_user_id': _session.userId,
          'closed_at': '2026-09-01T08:00:00+08:00',
        };
        final repository = SpinaPeriodCloseRepository(
          client: MockClient((request) async {
            requests.add(request);
            return _response({
              'item': request.url.path.endsWith('/prepare') ? prepared : closed,
            });
          }),
        );
        final item = await repository.prepare(
          _session,
          deviceId: 'management-phone',
          fiscalPeriodId: _periodId,
        );
        expect(item.journalEntryId, isNull);
        expect(item.temporaryAccountCount, 0);
        expect(() => item.requirePostCoordinates(), returnsNormally);
        final result = await repository.post(
          _session,
          deviceId: 'management-phone',
          item: item,
          confirmationToken: 'b' * 64,
        );
        expect(requests.length, 2);
        expect(jsonDecode(requests.first.body), {'confirm': true});
        expect(jsonDecode(requests.last.body), {
          'confirm': true,
          'confirmation_token': 'b' * 64,
          'expected_close_digest': 'a' * 64,
          'expected_net_income': '0.00',
          'expected_retained_earnings_account_code': '3100',
          'expected_period_end_date': '2026-08-31',
        });
        expect(result.closeStatus, 'closed_protected');
        expect(result.journalEntryId, isNull);
        expect(result.closingEntryNumber, isNull);
        expect(result.closePostingId, closed['close_posting_id']);
        expect(result.retainedEarningsBalanceAfter, '0.00');
        expect(() => result.requirePostCoordinates(), throwsArgumentError);
      },
    );
  }
  test(
    'zero-journal close rejects missing or contradictory protected evidence',
    () {
      final prepared = <String, Object?>{
        ..._preparedItemPayload,
        'journal_entry_id': null,
        'temporary_account_count': 0,
        'net_income': '0.00',
      };
      for (final patch in <Map<String, Object?>>[
        {'temporary_account_count': 2},
        {'temporary_account_count': null},
        {'temporary_account_count': -1},
        {'net_income': '0.01'},
        {'journal_entry_id': _periodId},
        {'preparation_id': null},
        {'close_digest': null},
        {'retained_earnings_balance_before': null},
        {'automatic_source_posting': true},
      ]) {
        expect(
          () => PeriodCloseItem.fromPayload({...prepared, ...patch}),
          throwsA(isA<SpinaApiException>()),
        );
      }
      final omitted = {...prepared}..remove('journal_entry_id');
      expect(
        () => PeriodCloseItem.fromPayload(omitted),
        throwsA(isA<SpinaApiException>()),
      );
      final closed = <String, Object?>{
        ...prepared,
        'fiscal_period_status': 'closed',
        'close_status': 'closed_protected',
        'close_posting_id': _periodId,
        'retained_earnings_balance_after': '100.00',
        'closed_by_user_id': _session.userId,
        'closed_at': '2026-09-01T00:00:00Z',
      };
      for (final patch in <Map<String, Object?>>[
        {'closing_entry_number': 'invented'},
        {'close_posting_id': null},
        {'closed_by_user_id': null},
        {'closed_at': null},
        {'retained_earnings_balance_after': null},
        {'fiscal_period_status': 'review'},
        {'temporary_account_count': 2, 'journal_entry_id': _periodId},
      ]) {
        expect(
          () => PeriodCloseItem.fromPayload({...closed, ...patch}),
          throwsA(isA<SpinaApiException>()),
        );
      }
    },
  );
  test(
    'loads exact protected close evidence with device authorization',
    () async {
      late http.Request captured;
      final repository = SpinaPeriodCloseRepository(
        client: MockClient((request) async {
          captured = request;
          return _response(_overviewPayload());
        }),
      );

      final overview = await repository.load(
        _session,
        deviceId: 'management-phone',
        status: 'prepared',
      );

      expect(captured.method, 'GET');
      expect(
        captured.url.path,
        '/api/mobile/v1/management/financial-accounting/period-close',
      );
      expect(captured.url.queryParameters, <String, String>{
        'close_status': 'prepared',
      });
      expect(captured.headers['authorization'], 'Bearer access-token');
      expect(captured.headers['x-device-id'], 'management-phone');
      expect(captured.headers['x-session-id'], isNull);
      expect(overview.summary.preparedCount, 1);
      expect(overview.permissions.closePrepare, isTrue);
      expect(overview.permissions.closePost, isTrue);
      expect(overview.items.single.netIncome, '60.00');
      expect(
        overview.items.single.closeDigest,
        List<String>.filled(64, 'a').join(),
      );
      expect(overview.items.single.automaticSourcePosting, isFalse);
    },
  );

  test(
    'prepares through the protected mobile route with confirmation',
    () async {
      late http.Request captured;
      final repository = SpinaPeriodCloseRepository(
        client: MockClient((request) async {
          captured = request;
          return _response(<String, Object?>{'item': _preparedItemPayload});
        }),
      );

      final item = await repository.prepare(
        _session,
        deviceId: 'management-phone',
        fiscalPeriodId: _periodId,
      );

      expect(captured.method, 'POST');
      expect(
        captured.url.path,
        '/api/mobile/v1/management/financial-accounting/period-close/'
        '$_periodId/prepare',
      );
      expect(jsonDecode(captured.body), <String, Object?>{'confirm': true});
      expect(item.closeStatus, 'prepared_confirmation_required');
    },
  );

  test('posts the exact prepared snapshot and confirmation token', () async {
    late http.Request captured;
    final repository = SpinaPeriodCloseRepository(
      client: MockClient((request) async {
        captured = request;
        return _response(<String, Object?>{
          'item': <String, Object?>{
            ..._preparedItemPayload,
            'fiscal_period_status': 'closed',
            'close_status': 'closed_protected',
            'close_posting_id': '55555555-5555-4555-8555-555555555555',
            'closing_entry_number': 'GJ-2026-0001',
            'retained_earnings_balance_after': '160.00',
            'closed_by_user_id': _session.userId,
            'closed_at': '2026-09-01T08:00:00+08:00',
          },
        });
      }),
    );
    final prepared = PeriodCloseItem.fromPayload(_preparedItemPayload);
    final token = List<String>.filled(64, 'b').join();

    final item = await repository.post(
      _session,
      deviceId: 'management-phone',
      item: prepared,
      confirmationToken: token,
    );

    expect(captured.method, 'POST');
    expect(
      captured.url.path,
      '/api/mobile/v1/management/financial-accounting/period-close/'
      '$_periodId/post',
    );
    expect(jsonDecode(captured.body), <String, Object?>{
      'confirm': true,
      'confirmation_token': token,
      'expected_close_digest': List<String>.filled(64, 'a').join(),
      'expected_net_income': '60.00',
      'expected_retained_earnings_account_code': '3100',
      'expected_period_end_date': '2026-08-31',
    });
    expect(item.closeStatus, 'closed_protected');
    expect(item.retainedEarningsBalanceAfter, '160.00');
  });

  test('rejects a stale incomplete item before post network I/O', () async {
    var requests = 0;
    final repository = SpinaPeriodCloseRepository(
      client: MockClient((request) async {
        requests += 1;
        return _response(const <String, Object?>{});
      }),
    );
    final item = PeriodCloseItem.fromPayload(<String, Object?>{
      ..._preparedItemPayload,
      'close_status': 'ready_to_prepare',
      'preparation_id': null,
      'journal_entry_id': null,
      'temporary_account_count': null,
      'net_income': null,
      'retained_earnings_balance_before': null,
      'close_digest': null,
    });

    await expectLater(
      repository.post(
        _session,
        deviceId: 'management-phone',
        item: item,
        confirmationToken: List<String>.filled(64, 'b').join(),
      ),
      throwsA(isA<ArgumentError>()),
    );
    expect(requests, 0);
  });

  test('preserves safe FastAPI period-close failure details', () async {
    final repository = SpinaPeriodCloseRepository(
      client: MockClient(
        (request) async => http.Response(
          jsonEncode(<String, Object?>{
            'detail': <String, Object?>{
              'code': 'period_close_blocked',
              'message': 'Posted ledger balances changed after preparation.',
            },
          }),
          409,
        ),
      ),
    );

    await expectLater(
      repository.load(_session, deviceId: 'management-phone'),
      throwsA(
        isA<SpinaApiException>()
            .having((error) => error.code, 'code', 'period_close_blocked')
            .having(
              (error) => error.message,
              'message',
              'Posted ledger balances changed after preparation.',
            ),
      ),
    );
  });
}

http.Response _response(Map<String, Object?> data) {
  return http.Response(
    jsonEncode(<String, Object?>{'success': true, 'data': data}),
    200,
    headers: const <String, String>{'content-type': 'application/json'},
  );
}

Map<String, Object?> _overviewPayload() {
  return <String, Object?>{
    'summary': <String, Object?>{
      'period_count': 1,
      'ready_for_review_count': 0,
      'ready_to_prepare_count': 0,
      'prepared_count': 1,
      'protected_closed_count': 0,
      'blocked_count': 0,
      'closed_net_income_total': '0.00',
      'protected_period_close_enabled': true,
      'retained_earnings_close_enabled': true,
      'closed_period_posting_protection_enabled': true,
      'period_reopen_enabled': false,
      'automatic_source_posting': false,
    },
    'items': <Object?>[_preparedItemPayload],
    'permissions': <String, Object?>{'close_prepare': true, 'close_post': true},
    'notice': 'Protected close notice.',
  };
}

const _preparedItemPayload = <String, Object?>{
  'fiscal_period_id': _periodId,
  'label': 'August 2026',
  'start_date': '2026-08-01',
  'end_date': '2026-08-31',
  'fiscal_period_status': 'review',
  'closed_by_user_id': null,
  'closed_at': null,
  'preparation_id': '22222222-2222-4222-8222-222222222222',
  'journal_entry_id': '33333333-3333-4333-8333-333333333333',
  'temporary_account_count': 2,
  'net_income': '60.00',
  'retained_earnings_balance_before': '100.00',
  'close_digest':
      'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa',
  'close_posting_id': null,
  'closing_entry_number': null,
  'retained_earnings_balance_after': null,
  'close_status': 'prepared_confirmation_required',
  'close_blocker': null,
  'protected_period_close_enabled': true,
  'retained_earnings_close_enabled': true,
  'closed_period_posting_protection_enabled': true,
  'period_reopen_enabled': false,
  'automatic_source_posting': false,
};

const _periodId = '11111111-1111-4111-8111-111111111111';

const _session = UserSession(
  userId: '99999999-9999-4999-8999-999999999999',
  username: 'manager.one',
  displayName: 'Manager One',
  role: AppRole.management,
  rawRole: 'management',
  accessToken: 'access-token',
  permissions: <String>[
    'accounting.view',
    'accounting.period.close.prepare',
    'accounting.period.close.post',
  ],
);
