import 'dart:convert';

import 'package:flutter_test/flutter_test.dart';
import 'package:gilbic_mobile/src/core/auth/app_role.dart';
import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/management/initial_capital_funding.dart';
import 'package:gilbic_mobile/src/core/management/initial_capital_funding_repository.dart';
import 'package:gilbic_mobile/src/core/network/spina_api.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

void main() {
  test(
    'loads exact server queue, summary, permissions, and cash choices',
    () async {
      late http.Request request;
      final repository = SpinaInitialCapitalFundingRepository(
        client: MockClient((incoming) async {
          request = incoming;
          return _overviewResponse(
            items: <Object?>[_item(status: 'evidence_ready')],
          );
        }),
      );

      final overview = await repository.load(
        _session,
        deviceId: 'management-device',
      );

      expect(request.method, 'GET');
      expect(
        request.url.path,
        '/api/mobile/v1/management/financial-accounting/initial-capital-funding',
      );
      expect(request.url.queryParameters, <String, String>{
        'limit': '100',
        'offset': '0',
      });
      expect(request.headers['Authorization'], 'Bearer management-token');
      expect(request.headers['X-Device-Id'], 'management-device');
      expect(overview.summary.evidenceReadyCount, 1);
      expect(overview.cashAccounts.single.code, '1000');
      expect(overview.permissions.evidenceRecord, isTrue);
      expect(overview.items.single.amount, '250000.00');
      expect(overview.automaticSourcePosting, isFalse);
    },
  );

  test('records only exact retained evidence with the stable retry UUID', () async {
    late http.Request request;
    late Map<String, dynamic> body;
    final repository = SpinaInitialCapitalFundingRepository(
      client: MockClient((incoming) async {
        request = incoming;
        body = jsonDecode(incoming.body) as Map<String, dynamic>;
        return _itemResponse(_item(status: 'evidence_ready'));
      }),
    );

    final item = await repository.recordEvidence(
      _session,
      deviceId: 'management-device',
      draft: const InitialCapitalEvidenceDraft(
        fundingDate: '2026-08-30',
        amount: '250000.00',
        cashAccountCode: '1000',
        evidenceSource: 'Bank deposit slip',
        evidenceReference: 'BPI-2026-0001',
        evidenceDigest: _evidenceDigest,
        evidenceNote:
            'Verified owner funding deposited into the selected company account.',
      ),
      idempotencyKey: '11111111-1111-4111-8111-111111111111',
    );

    expect(request.method, 'POST');
    expect(
      request.url.path,
      '/api/mobile/v1/management/financial-accounting/initial-capital-funding/evidence',
    );
    expect(body, <String, Object>{
      'idempotency_key': '11111111-1111-4111-8111-111111111111',
      'funding_date': '2026-08-30',
      'amount': '250000.00',
      'cash_account_code': '1000',
      'evidence_source': 'Bank deposit slip',
      'evidence_reference': 'BPI-2026-0001',
      'evidence_digest': _evidenceDigest,
      'evidence_note':
          'Verified owner funding deposited into the selected company account.',
    });
    expect(item.accountingStatus, 'evidence_ready');
  });

  test('prepares only an exact evidence-ready item', () async {
    late Map<String, dynamic> body;
    late http.Request request;
    final item = InitialCapitalFundingItem.fromPayload(
      _item(status: 'evidence_ready'),
    );
    final repository = SpinaInitialCapitalFundingRepository(
      client: MockClient((incoming) async {
        request = incoming;
        body = jsonDecode(incoming.body) as Map<String, dynamic>;
        return _itemResponse(_item(status: 'prepared_not_posted'));
      }),
    );

    final prepared = await repository.prepare(
      _session,
      deviceId: 'management-device',
      item: item,
    );

    expect(
      request.url.path,
      '/api/mobile/v1/management/financial-accounting/initial-capital-funding/'
      '22222222-2222-4222-8222-222222222222/prepare',
    );
    expect(body, <String, Object>{'confirm': true});
    expect(prepared.accountingStatus, 'prepared_not_posted');
  });

  test(
    'posts exact prepared coordinates with a stable confirmation token',
    () async {
      late Map<String, dynamic> body;
      final item = InitialCapitalFundingItem.fromPayload(
        _item(status: 'prepared_not_posted'),
      );
      final repository = SpinaInitialCapitalFundingRepository(
        client: MockClient((incoming) async {
          body = jsonDecode(incoming.body) as Map<String, dynamic>;
          return _itemResponse(_item(status: 'posted'));
        }),
      );

      final posted = await repository.post(
        _session,
        deviceId: 'management-device',
        item: item,
        confirmationToken: _confirmationToken,
      );

      expect(body, <String, Object>{
        'confirm': true,
        'confirmation_token': _confirmationToken,
        'expected_evidence_digest': _evidenceDigest,
        'expected_amount': '250000.00',
        'expected_cash_account_code': '1000',
        'expected_posting_date': '2026-08-30',
        'expected_fiscal_period_id': '33333333-3333-4333-8333-333333333333',
      });
      expect(posted.entryNumber, 'GJ-2026-0010');
    },
  );

  test('rejects malformed retry identities before network I/O', () async {
    var calls = 0;
    final repository = SpinaInitialCapitalFundingRepository(
      client: MockClient((_) async {
        calls += 1;
        return _itemResponse(_item(status: 'evidence_ready'));
      }),
    );
    const draft = InitialCapitalEvidenceDraft(
      fundingDate: '2026-08-30',
      amount: '250000.00',
      cashAccountCode: '1000',
      evidenceSource: 'Bank deposit slip',
      evidenceReference: 'BPI-2026-0001',
      evidenceDigest: _evidenceDigest,
      evidenceNote:
          'Verified owner funding deposited into the selected company account.',
    );

    await expectLater(
      repository.recordEvidence(
        _session,
        deviceId: 'management-device',
        draft: draft,
        idempotencyKey: 'not-a-uuid',
      ),
      throwsArgumentError,
    );
    await expectLater(
      repository.post(
        _session,
        deviceId: 'management-device',
        item: InitialCapitalFundingItem.fromPayload(
          _item(status: 'prepared_not_posted'),
        ),
        confirmationToken: 'not-a-token',
      ),
      throwsArgumentError,
    );
    expect(calls, 0);
  });

  test('rejects incomplete actionable items and unsafe policy flags', () async {
    final incomplete = _item(status: 'prepared_not_posted')
      ..['fiscal_period_id'] = null;
    final unsafe = _overviewPayload(items: <Object?>[])
      ..['automatic_source_posting'] = true;

    expect(
      () => InitialCapitalFundingItem.fromPayload(incomplete),
      throwsA(isA<SpinaApiException>()),
    );
    expect(
      () => InitialCapitalFundingOverview.fromPayload(unsafe),
      throwsA(
        isA<SpinaApiException>().having(
          (error) => error.code,
          'code',
          'invalid_initial_capital_payload',
        ),
      ),
    );
  });

  test('preserves safe FastAPI initial-capital detail and code', () async {
    final repository = SpinaInitialCapitalFundingRepository(
      client: MockClient(
        (_) async => http.Response(
          jsonEncode(<String, Object>{
            'detail': <String, Object>{
              'code': 'initial_capital_funding_blocked',
              'message': 'Refresh the retained funding evidence.',
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
              'Refresh the retained funding evidence.',
            )
            .having(
              (error) => error.code,
              'code',
              'initial_capital_funding_blocked',
            ),
      ),
    );
  });
}

http.Response _overviewResponse({required List<Object?> items}) =>
    http.Response(
      jsonEncode(<String, Object?>{
        'success': true,
        'data': _overviewPayload(items: items),
      }),
      200,
      headers: const <String, String>{'content-type': 'application/json'},
    );

http.Response _itemResponse(Map<String, Object?> item) => http.Response(
  jsonEncode(<String, Object?>{
    'success': true,
    'data': <String, Object?>{'item': item},
  }),
  200,
  headers: const <String, String>{'content-type': 'application/json'},
);

Map<String, Object?> _overviewPayload({required List<Object?> items}) =>
    <String, Object?>{
      'items': items,
      'summary': <String, Object>{
        'evidence_count': 1,
        'evidence_ready_count': 1,
        'prepared_not_posted_count': 0,
        'posted_count': 0,
        'blocked_no_open_period_count': 0,
        'total_amount': '250000.00',
        'posted_amount': '0.00',
      },
      'cash_accounts': <Object?>[
        <String, Object>{'code': '1000', 'name': 'Cash - Office'},
      ],
      'permissions': <String, Object>{
        'evidence_record': true,
        'prepare': true,
        'post': true,
      },
      'limit': 100,
      'offset': 0,
      'protected_initial_capital_funding_enabled': true,
      'synthetic_opening_balance_required': false,
      'automatic_source_posting': false,
      'notice': 'Exact retained evidence is required.',
    };

Map<String, Object?> _item({required String status}) {
  final prepared = status == 'prepared_not_posted' || status == 'posted';
  final posted = status == 'posted';
  return <String, Object?>{
    'evidence_id': '22222222-2222-4222-8222-222222222222',
    'funding_date': '2026-08-30',
    'amount': '250000.00',
    'cash_account_code': '1000',
    'cash_account_name': 'Cash - Office',
    'capital_account_code': '3000',
    'evidence_source': 'Bank deposit slip',
    'evidence_reference': 'BPI-2026-0001',
    'evidence_digest': _evidenceDigest,
    'evidence_note':
        'Verified owner funding deposited into the selected company account.',
    'recorded_by_user_id': '44444444-4444-4444-8444-444444444444',
    'recorded_at': '2026-08-30T02:00:00+00:00',
    'journal_entry_id': prepared
        ? '55555555-5555-4555-8555-555555555555'
        : null,
    'journal_status': prepared ? (posted ? 'posted' : 'draft') : null,
    'entry_number': posted ? 'GJ-2026-0010' : null,
    'fiscal_period_id': prepared
        ? '33333333-3333-4333-8333-333333333333'
        : null,
    'prepared_by_user_id': prepared
        ? '66666666-6666-4666-8666-666666666666'
        : null,
    'prepared_at': prepared ? '2026-08-30T02:10:00+00:00' : null,
    'confirmation_digest': posted ? _confirmationDigest : null,
    'posted_by_user_id': posted ? '77777777-7777-4777-8777-777777777777' : null,
    'posted_at': posted ? '2026-08-30T02:20:00+00:00' : null,
    'accounting_status': status,
    'accounting_blocker': status == 'blocked_no_open_period'
        ? 'Funding date is not inside an open accounting period.'
        : null,
    'protected_initial_capital_funding_enabled': true,
    'synthetic_opening_balance_required': false,
    'automatic_source_posting': false,
  };
}

const _evidenceDigest =
    'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa';
const _confirmationToken =
    'bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb';
const _confirmationDigest =
    'cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc';

const _session = UserSession(
  userId: 'management-1',
  username: 'manager',
  displayName: 'Management',
  role: AppRole.management,
  rawRole: 'Management',
  accessToken: 'management-token',
  permissions: <String>[
    'accounting.initial_capital.evidence.record',
    'accounting.initial_capital.prepare',
    'accounting.initial_capital.post',
  ],
);
