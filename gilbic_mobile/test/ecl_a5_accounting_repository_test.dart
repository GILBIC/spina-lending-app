import 'dart:convert';

import 'package:flutter_test/flutter_test.dart';
import 'package:gilbic_mobile/src/core/auth/app_role.dart';
import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/management/ecl_a5_accounting.dart';
import 'package:gilbic_mobile/src/core/management/ecl_a5_accounting_repository.dart';
import 'package:gilbic_mobile/src/core/network/spina_api.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

void main() {
  test('loads the exact protected A5 queue and permissions', () async {
    late http.Request request;
    final repository = SpinaEclA5AccountingRepository(
      client: MockClient((incoming) async {
        request = incoming;
        return _response(<String, Object?>{
          'items': <Object?>[_item('remeasurement_required')],
          'summary': _summary,
          'filter': 'remeasurement_required',
          'limit': 100,
          'offset': 0,
          'permissions': const <String, Object>{
            'remeasurement_post': true,
            'writeoff_post': false,
            'recovery_review': true,
            'recovery_post': false,
          },
          'notice': 'Exact protected A5 server queue.',
        });
      }),
    );

    final overview = await repository.load(
      _session,
      deviceId: 'management-device',
      status: 'remeasurement_required',
    );

    expect(request.method, 'GET');
    expect(
      request.url.path,
      '/api/mobile/v1/management/financial-accounting/ecl-a5',
    );
    expect(request.url.queryParameters, <String, String>{
      'status': 'remeasurement_required',
      'limit': '100',
      'offset': '0',
    });
    expect(request.headers['Authorization'], 'Bearer management-token');
    expect(request.headers['X-Device-Id'], 'management-device');
    expect(overview.items.single.currentAllowanceBalance, '100.00');
    expect(overview.permissions.remeasurementPost, isTrue);
    expect(overview.summary.recoveryReviewRequiredCount, 1);
  });

  test('remeasurement sends only exact server queue coordinates', () async {
    late http.Request request;
    late Map<String, dynamic> body;
    final repository = SpinaEclA5AccountingRepository(
      client: MockClient((incoming) async {
        request = incoming;
        body = jsonDecode(incoming.body) as Map<String, dynamic>;
        return _receipt('remeasurement_id', _receiptId);
      }),
    );
    final item = EclA5ActionItem.fromPayload(_item('remeasurement_required'));

    final receipt = await repository.postRemeasurement(
      _session,
      deviceId: 'management-device',
      item: item,
      reviewToken: _token,
    );

    expect(
      request.url.path,
      '/api/mobile/v1/management/financial-accounting/ecl-a5/'
      'measurements/22222222-2222-4222-8222-222222222222/remeasure',
    );
    expect(body, <String, Object>{
      'review_token': _token,
      'expected_calculation_digest': _digest,
      'expected_prior_allowance': '100.00',
      'expected_target_allowance': '125.50',
      'expected_posting_date': '2026-08-30',
      'expected_fiscal_period_id': '44444444-4444-4444-8444-444444444444',
      'expected_credit_loss_expense_account_id':
          '55555555-5555-4555-8555-555555555555',
      'expected_allowance_account_id': '66666666-6666-4666-8666-666666666666',
    });
    expect(receipt.id, _receiptId);
    expect(receipt.automaticSourcePosting, isFalse);
  });

  test('write-off sends the exact fully covered carrying snapshot', () async {
    late Map<String, dynamic> body;
    final repository = SpinaEclA5AccountingRepository(
      client: MockClient((incoming) async {
        body = jsonDecode(incoming.body) as Map<String, dynamic>;
        return _receipt('writeoff_id', _receiptId);
      }),
    );
    final item = EclA5ActionItem.fromPayload(_item('writeoff_ready'));

    await repository.postFullWriteoff(
      _session,
      deviceId: 'management-device',
      item: item,
      reviewToken: _token,
    );

    expect(body, <String, Object>{
      'review_token': _token,
      'expected_credit_risk_review_id': 12,
      'expected_measurement_id': '22222222-2222-4222-8222-222222222222',
      'expected_calculation_digest': _digest,
      'expected_loan_component': '100.00',
      'expected_accrued_interest_component': '25.50',
      'expected_gross_carrying_amount': '125.50',
      'expected_allowance_balance': '125.50',
      'expected_loan_receivable_account_id':
          '77777777-7777-4777-8777-777777777777',
      'expected_accrued_interest_account_id':
          '88888888-8888-4888-8888-888888888888',
      'expected_allowance_account_id': '66666666-6666-4666-8666-666666666666',
      'expected_posting_date': '2026-08-30',
      'expected_fiscal_period_id': '44444444-4444-4444-8444-444444444444',
    });
  });

  test('recovery review and posting use separate exact server evidence', () async {
    final bodies = <Map<String, dynamic>>[];
    final paths = <String>[];
    final repository = SpinaEclA5AccountingRepository(
      client: MockClient((incoming) async {
        paths.add(incoming.url.path);
        bodies.add(jsonDecode(incoming.body) as Map<String, dynamic>);
        return paths.length == 1
            ? _intReceipt('credit_risk_review_id', 19)
            : _receipt('recovery_id', _receiptId);
      }),
    );

    await repository.reviewRecovery(
      _session,
      deviceId: 'management-device',
      item: EclA5ActionItem.fromPayload(_item('recovery_review_required')),
      reviewToken: _token,
      evidenceReference: 'OR-2026-0042',
      reviewNote:
          'Management matched the protected receipt to the later cash collection.',
    );
    await repository.postRecovery(
      _session,
      deviceId: 'management-device',
      item: EclA5ActionItem.fromPayload(_item('post_writeoff_recovery_ready')),
      reviewToken: _secondToken,
    );

    expect(
      paths.first,
      endsWith('/loans/11111111-1111-4111-8111-111111111111/recovery-review'),
    );
    expect(bodies.first, <String, Object>{
      'review_token': _token,
      'expected_recovery_transaction_id':
          '99999999-9999-4999-8999-999999999999',
      'expected_recovery_amount': '20.00',
      'evidence_reference': 'OR-2026-0042',
      'review_note':
          'Management matched the protected receipt to the later cash collection.',
    });
    expect(paths.last, endsWith('/reviews/19/recovery'));
    expect(bodies.last, <String, Object>{
      'review_token': _secondToken,
      'expected_recovery_transaction_id':
          '99999999-9999-4999-8999-999999999999',
      'expected_recovery_amount': '20.00',
      'expected_posting_date': '2026-08-30',
      'expected_fiscal_period_id': '44444444-4444-4444-8444-444444444444',
      'expected_cash_account_id': 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa',
      'expected_credit_loss_expense_account_id':
          '55555555-5555-4555-8555-555555555555',
    });
  });

  test(
    'rejects incomplete actionable rows and invalid tokens before I/O',
    () async {
      final incomplete = _item('writeoff_ready')..['fiscal_period_id'] = null;
      expect(
        () => EclA5ActionItem.fromPayload(incomplete),
        throwsA(isA<SpinaApiException>()),
      );
      var calls = 0;
      final repository = SpinaEclA5AccountingRepository(
        client: MockClient((_) async {
          calls += 1;
          return _receipt('writeoff_id', _receiptId);
        }),
      );
      await expectLater(
        repository.postFullWriteoff(
          _session,
          deviceId: 'management-device',
          item: EclA5ActionItem.fromPayload(_item('writeoff_ready')),
          reviewToken: 'invalid',
        ),
        throwsArgumentError,
      );
      expect(calls, 0);
    },
  );

  test(
    'rejects an unsupported returned filter and automatic receipt',
    () async {
      final badFilterRepository = SpinaEclA5AccountingRepository(
        client: MockClient(
          (_) async => _response(<String, Object?>{
            'items': <Object?>[],
            'summary': _summary,
            'filter': 'invented',
            'limit': 100,
            'offset': 0,
            'permissions': const <String, Object>{
              'remeasurement_post': false,
              'writeoff_post': false,
              'recovery_review': false,
              'recovery_post': false,
            },
            'notice': 'Invalid filter.',
          }),
        ),
      );
      await expectLater(
        badFilterRepository.load(_session, deviceId: 'management-device'),
        throwsA(isA<SpinaApiException>()),
      );

      final automaticRepository = SpinaEclA5AccountingRepository(
        client: MockClient(
          (_) async => http.Response(
            jsonEncode(<String, Object>{
              'success': true,
              'data': <String, Object>{
                'remeasurement_id': _receiptId,
                'automatic_source_posting': true,
              },
            }),
            200,
            headers: const <String, String>{'content-type': 'application/json'},
          ),
        ),
      );
      await expectLater(
        automaticRepository.postRemeasurement(
          _session,
          deviceId: 'management-device',
          item: EclA5ActionItem.fromPayload(_item('remeasurement_required')),
          reviewToken: _token,
        ),
        throwsA(isA<SpinaApiException>()),
      );
    },
  );

  test('rejects a filter-only value as an item status', () {
    expect(
      () => EclA5ActionItem.fromPayload(_item('all')),
      throwsA(isA<SpinaApiException>()),
    );
  });

  test('rejects a recovery review receipt for different evidence', () async {
    final repository = SpinaEclA5AccountingRepository(
      client: MockClient(
        (_) async => _response(<String, Object>{
          'credit_risk_review_id': 19,
          'recovery_transaction_id': 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa',
          'automatic_source_posting': false,
        }),
      ),
    );

    await expectLater(
      repository.reviewRecovery(
        _session,
        deviceId: 'management-device',
        item: EclA5ActionItem.fromPayload(_item('recovery_review_required')),
        reviewToken: _token,
        evidenceReference: 'OR-2026-0042',
        reviewNote:
            'Management matched the protected receipt to the later cash collection.',
      ),
      throwsA(
        isA<SpinaApiException>().having(
          (error) => error.code,
          'code',
          'invalid_ecl_a5_payload',
        ),
      ),
    );
  });
}

http.Response _response(Map<String, Object?> data) => http.Response(
  jsonEncode(<String, Object?>{'success': true, 'data': data}),
  200,
  headers: const <String, String>{'content-type': 'application/json'},
);

http.Response _receipt(String key, String id) =>
    _response(<String, Object>{key: id, 'automatic_source_posting': false});

http.Response _intReceipt(String key, int id) => _response(<String, Object>{
  key: id,
  'recovery_transaction_id': '99999999-9999-4999-8999-999999999999',
  'automatic_source_posting': false,
});

Map<String, Object?> _item(String status) {
  final recoveryReview = status == 'recovery_review_required';
  final recoveryPost = status == 'post_writeoff_recovery_ready';
  return <String, Object?>{
    'loan_id': '11111111-1111-4111-8111-111111111111',
    'loan_number': 'LN-2026-0001',
    'loan_status': 'active',
    'calculation_mode': 'fixed_daily',
    'credit_risk_review_id': recoveryPost ? 19 : 12,
    'stage_label': 'stage_3_credit_impaired',
    'default_label': true,
    'write_off_label': 'supported_no_reasonable_expectation_of_recovery',
    'recovery_label': recoveryPost ? 'cash_recovery_observed' : 'none',
    'measurement_id': '22222222-2222-4222-8222-222222222222',
    'measurement_version': 3,
    'measurement_date': '2026-08-30',
    'calculation_digest': _digest,
    'measurement_status': 'measured_read_only',
    'authoritative_ecl_amount': '125.50',
    'current_allowance_balance': recoveryReview || recoveryPost
        ? '0.00'
        : status == 'writeoff_ready'
        ? '125.50'
        : '100.00',
    'loan_receivable_account_id': '77777777-7777-4777-8777-777777777777',
    'loan_receivable_system_key': 'loans_receivable_regular',
    'accrued_interest_account_id': '88888888-8888-4888-8888-888888888888',
    'loan_component': recoveryReview || recoveryPost ? '0.00' : '100.00',
    'accrued_interest_component': recoveryReview || recoveryPost
        ? '0.00'
        : '25.50',
    'gross_carrying_amount': recoveryReview || recoveryPost ? '0.00' : '125.50',
    'writeoff_id': recoveryReview || recoveryPost
        ? 'bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb'
        : null,
    'recovery_transaction_id': recoveryPost
        ? '99999999-9999-4999-8999-999999999999'
        : null,
    'recovery_amount': recoveryPost ? '20.00' : null,
    'recovery_candidate_transaction_id': recoveryReview
        ? '99999999-9999-4999-8999-999999999999'
        : null,
    'recovery_candidate_amount': recoveryReview ? '20.00' : null,
    'recovery_candidate_collection_date': recoveryReview ? '2026-08-30' : null,
    'posting_date': recoveryReview ? null : '2026-08-30',
    'fiscal_period_id': recoveryReview
        ? null
        : '44444444-4444-4444-8444-444444444444',
    'credit_loss_expense_account_id': recoveryReview
        ? null
        : '55555555-5555-4555-8555-555555555555',
    'allowance_account_id': recoveryPost || recoveryReview
        ? null
        : '66666666-6666-4666-8666-666666666666',
    'cash_account_id': recoveryPost
        ? 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa'
        : null,
    'a5_status': status,
    'protected_a5_accounting_enabled': true,
    'automatic_source_posting': false,
  };
}

const _summary = <String, Object>{
  'loan_count': 6,
  'remeasurement_required_count': 1,
  'allowance_current_count': 1,
  'writeoff_ready_count': 1,
  'written_off_count': 1,
  'recovery_ready_count': 1,
  'recovery_review_required_count': 1,
  'blocked_count': 1,
  'remeasurement_posting_count': 2,
  'writeoff_posting_count': 1,
  'post_writeoff_recovery_count': 0,
  'protected_a5_accounting_enabled': true,
  'automatic_source_posting': false,
};

const _digest =
    'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa';
const _token =
    'cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc';
const _secondToken =
    'dddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd';
const _receiptId = 'eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee';

const _session = UserSession(
  userId: 'management-1',
  username: 'manager',
  displayName: 'Management',
  role: AppRole.management,
  rawRole: 'Management',
  accessToken: 'management-token',
  permissions: <String>[
    'accounting.ecl.remeasurement.post',
    'accounting.ecl.writeoff.post',
    'accounting.ecl.recovery.review',
    'accounting.ecl.recovery.post',
  ],
);
