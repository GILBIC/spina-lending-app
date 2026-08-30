import 'dart:convert';

import 'package:flutter_test/flutter_test.dart';
import 'package:gilbic_mobile/src/core/auth/app_role.dart';
import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/management/ecl_allowance_posting.dart';
import 'package:gilbic_mobile/src/core/management/ecl_allowance_posting_repository.dart';
import 'package:gilbic_mobile/src/core/network/spina_api.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

void main() {
  test(
    'loads exact server allowance coordinates with device authorization',
    () async {
      late http.Request request;
      final repository = SpinaEclAllowancePostingRepository(
        client: MockClient((incoming) async {
          request = incoming;
          return http.Response(
            jsonEncode(<String, Object?>{
              'success': true,
              'data': <String, Object?>{
                'items': <Object?>[_queueItemPayload(status: 'posting_ready')],
                'summary': _summaryPayload,
                'filter': 'posting_ready',
                'limit': 100,
                'offset': 0,
                'prepare_permission': true,
                'post_permission': true,
                'notice': 'Exact A4 server queue.',
              },
            }),
            200,
            headers: const <String, String>{'content-type': 'application/json'},
          );
        }),
      );

      final overview = await repository.load(
        _session,
        deviceId: 'management-device',
        status: 'posting_ready',
      );

      expect(request.method, 'GET');
      expect(
        request.url.path,
        '/api/mobile/v1/management/financial-accounting/ecl-allowance-posting',
      );
      expect(request.url.queryParameters, <String, String>{
        'status': 'posting_ready',
        'limit': '100',
        'offset': '0',
      });
      expect(request.headers['Authorization'], 'Bearer management-token');
      expect(request.headers['X-Device-Id'], 'management-device');
      final item = overview.items.single;
      expect(item.allowancePostingStatus, 'posting_ready');
      expect(item.authoritativeEclAmount, '125.50');
      expect(item.priorAllowanceBalance, '0.00');
      expect(item.preparationDigest, _preparationDigest);
      expect(overview.summary.postingReadyCount, 1);
      expect(overview.permissions.post, isTrue);
    },
  );

  test('prepare sends only the exact authoritative queue snapshot', () async {
    late Map<String, dynamic> body;
    late http.Request request;
    final repository = SpinaEclAllowancePostingRepository(
      client: MockClient((incoming) async {
        request = incoming;
        body = jsonDecode(incoming.body) as Map<String, dynamic>;
        return _actionResponse('aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa');
      }),
    );
    final item = EclAllowancePostingItem.fromPayload(
      _queueItemPayload(status: 'preparation_required'),
    );

    final receipt = await repository.prepare(
      _session,
      deviceId: 'management-device',
      item: item,
      reviewToken: _prepareToken,
    );

    expect(
      request.url.path,
      '/api/mobile/v1/management/financial-accounting/ecl-allowance-posting/'
      '22222222-2222-4222-8222-222222222222/prepare',
    );
    expect(body, <String, Object>{
      'preparation_review_token': _prepareToken,
      'expected_calculation_digest': _calculationDigest,
      'expected_ecl_amount': '125.50',
      'expected_posting_date': '2026-08-31',
      'expected_fiscal_period_id': '44444444-4444-4444-8444-444444444444',
      'expected_credit_loss_expense_account_id':
          '55555555-5555-4555-8555-555555555555',
      'expected_allowance_account_id': '66666666-6666-4666-8666-666666666666',
      'expected_prior_allowance_balance': '0.00',
    });
    expect(receipt.id, 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa');
    expect(receipt.automaticSourcePosting, isFalse);
  });

  test('post sends the exact prepared journal and snapshot', () async {
    late Map<String, dynamic> body;
    late http.Request request;
    final repository = SpinaEclAllowancePostingRepository(
      client: MockClient((incoming) async {
        request = incoming;
        body = jsonDecode(incoming.body) as Map<String, dynamic>;
        return _actionResponse('bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb');
      }),
    );
    final item = EclAllowancePostingItem.fromPayload(
      _queueItemPayload(status: 'posting_ready'),
    );

    await repository.post(
      _session,
      deviceId: 'management-device',
      item: item,
      reviewToken: _postToken,
    );

    expect(
      request.url.path,
      '/api/mobile/v1/management/financial-accounting/ecl-allowance-posting/'
      'preparations/77777777-7777-4777-8777-777777777777/post',
    );
    expect(body, <String, Object>{
      'posting_review_token': _postToken,
      'expected_measurement_id': '22222222-2222-4222-8222-222222222222',
      'expected_calculation_digest': _calculationDigest,
      'expected_journal_entry_id': '88888888-8888-4888-8888-888888888888',
      'expected_source_event_key':
          'ecl_allowance:22222222-2222-4222-8222-222222222222',
      'expected_preparation_digest': _preparationDigest,
      'expected_posting_date': '2026-08-31',
      'expected_fiscal_period_id': '44444444-4444-4444-8444-444444444444',
      'expected_credit_loss_expense_account_id':
          '55555555-5555-4555-8555-555555555555',
      'expected_allowance_account_id': '66666666-6666-4666-8666-666666666666',
      'expected_allowance_amount': '125.50',
      'expected_prior_allowance_balance': '0.00',
    });
  });

  test(
    'rejects a non-posting snapshot and invalid token before network I/O',
    () async {
      var calls = 0;
      final repository = SpinaEclAllowancePostingRepository(
        client: MockClient((_) async {
          calls += 1;
          return _actionResponse('aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa');
        }),
      );
      final item = EclAllowancePostingItem.fromPayload(
        _queueItemPayload(status: 'preparation_required'),
      );

      await expectLater(
        repository.post(
          _session,
          deviceId: 'management-device',
          item: item,
          reviewToken: _postToken,
        ),
        throwsArgumentError,
      );
      await expectLater(
        repository.prepare(
          _session,
          deviceId: 'management-device',
          item: item,
          reviewToken: 'not-a-token',
        ),
        throwsArgumentError,
      );
      expect(calls, 0);
    },
  );

  test(
    'rejects incomplete actionable server rows as safe API errors',
    () async {
      final incomplete = _queueItemPayload(status: 'preparation_required')
        ..['posting_date'] = null;
      final repository = SpinaEclAllowancePostingRepository(
        client: MockClient(
          (_) async => http.Response(
            jsonEncode(<String, Object?>{
              'success': true,
              'data': <String, Object?>{
                'items': <Object?>[incomplete],
                'summary': _summaryPayload,
                'filter': 'all',
                'limit': 100,
                'offset': 0,
                'prepare_permission': true,
                'post_permission': true,
                'notice': 'Exact A4 server queue.',
              },
            }),
            200,
            headers: const <String, String>{'content-type': 'application/json'},
          ),
        ),
      );

      await expectLater(
        repository.load(_session, deviceId: 'management-device'),
        throwsA(
          isA<SpinaApiException>()
              .having(
                (error) => error.message,
                'message',
                contains('incomplete ECL allowance'),
              )
              .having(
                (error) => error.code,
                'code',
                'invalid_ecl_allowance_payload',
              ),
        ),
      );
    },
  );

  test('preserves safe FastAPI ECL allowance detail and code', () async {
    final repository = SpinaEclAllowancePostingRepository(
      client: MockClient(
        (_) async => http.Response(
          jsonEncode(<String, Object>{
            'detail': <String, Object>{
              'code': 'ecl_allowance_posting_blocked',
              'message': 'Refresh the authoritative allowance evidence.',
            },
          }),
          409,
          headers: const <String, String>{'content-type': 'application/json'},
        ),
      ),
    );

    await expectLater(
      repository.load(_session, deviceId: 'management-device'),
      throwsA(
        isA<SpinaApiException>()
            .having(
              (error) => error.message,
              'message',
              'Refresh the authoritative allowance evidence.',
            )
            .having(
              (error) => error.code,
              'code',
              'ecl_allowance_posting_blocked',
            ),
      ),
    );
  });
}

http.Response _actionResponse(String id) {
  return http.Response(
    jsonEncode(<String, Object>{
      'success': true,
      'data': <String, Object>{'id': id, 'automatic_source_posting': false},
    }),
    200,
    headers: const <String, String>{'content-type': 'application/json'},
  );
}

Map<String, Object?> _queueItemPayload({required String status}) {
  final prepared = status == 'posting_ready' || status == 'posted_current';
  final posted = status == 'posted_current';
  return <String, Object?>{
    'loan_id': '11111111-1111-4111-8111-111111111111',
    'loan_number': 'LN-2026-0001',
    'loan_status': 'active',
    'loan_type_code': 'regular',
    'loan_type_name': 'Regular',
    'calculation_mode': 'fixed_daily',
    'measurement_id': '22222222-2222-4222-8222-222222222222',
    'measurement_version': 3,
    'measurement_date': '2026-08-31',
    'loss_horizon': 'lifetime',
    'calculation_digest': _calculationDigest,
    'measurement_status': 'measured_read_only',
    'authoritative_ecl_amount': '125.50',
    'preparation_id': prepared ? '77777777-7777-4777-8777-777777777777' : null,
    'journal_entry_id': prepared
        ? '88888888-8888-4888-8888-888888888888'
        : null,
    'source_event_key': 'ecl_allowance:22222222-2222-4222-8222-222222222222',
    'posting_date': '2026-08-31',
    'fiscal_period_id': '44444444-4444-4444-8444-444444444444',
    'credit_loss_expense_account_id': '55555555-5555-4555-8555-555555555555',
    'allowance_account_id': '66666666-6666-4666-8666-666666666666',
    'allowance_amount': '125.50',
    'prior_allowance_balance': '0.00',
    'preparation_review_token': prepared ? _prepareToken : null,
    'preparation_digest': prepared ? _preparationDigest : null,
    'draft_policy_version': 'ecl_allowance_initial_journal_draft_v1',
    'journal_status': prepared ? (posted ? 'posted' : 'draft') : null,
    'entry_number': posted ? 'GJ-2026-0012' : null,
    'posting_id': posted ? '99999999-9999-4999-8999-999999999999' : null,
    'posting_review_token': posted ? _postToken : null,
    'posting_policy_version': posted
        ? 'ecl_allowance_initial_journal_posting_v1'
        : null,
    'current_allowance_balance': posted ? '125.50' : '0.00',
    'allowance_posting_status': status,
    'protected_allowance_action_ready':
        status == 'preparation_required' || status == 'posting_ready',
    'account_1190_posting_enabled': true,
    'automatic_source_posting': false,
  };
}

const _summaryPayload = <String, Object>{
  'loan_count': 1,
  'measurement_not_authoritative_count': 0,
  'no_allowance_required_count': 0,
  'preparation_required_count': 0,
  'posting_ready_count': 1,
  'posted_current_count': 0,
  'a5_remeasurement_required_count': 0,
  'posting_audit_incomplete_count': 0,
  'protected_allowance_balance_total': '0.00',
  'account_1190_posting_enabled': true,
  'automatic_source_posting': false,
};

const _calculationDigest =
    'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa';
const _preparationDigest =
    'bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb';
const _prepareToken =
    'cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc';
const _postToken =
    'dddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd';

const _session = UserSession(
  userId: 'management-1',
  username: 'manager',
  displayName: 'Management',
  role: AppRole.management,
  rawRole: 'Management',
  accessToken: 'management-token',
  permissions: <String>[
    'accounting.ecl.allowance.prepare',
    'accounting.ecl.allowance.post',
  ],
);
