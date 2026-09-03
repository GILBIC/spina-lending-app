import 'dart:convert';

import 'package:flutter_test/flutter_test.dart';
import 'package:gilbic_mobile/src/core/auth/app_role.dart';
import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/management/tax_settlement.dart';
import 'package:gilbic_mobile/src/core/management/tax_settlement_repository.dart';
import 'package:gilbic_mobile/src/core/network/spina_api.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

void main() {
  test(
    'loads settlement queue and exact server-derived return candidates',
    () async {
      late http.Request request;
      final repository = SpinaTaxSettlementRepository(
        client: MockClient((incoming) async {
          request = incoming;
          return _response(_overview());
        }),
      );

      final overview = await repository.load(
        _session,
        deviceId: 'management-device',
        settlementStatus: 'ready',
        limit: 25,
        offset: 5,
      );

      expect(
        request.url.path,
        '/api/mobile/v1/management/financial-accounting/tax/settlements',
      );
      expect(request.url.queryParameters, <String, String>{
        'settlement_status': 'ready',
        'limit': '25',
        'offset': '5',
      });
      expect(overview.returnLiabilityCandidates.single.postingId, _postingId);
      expect(overview.summary.readyToPrepareCount, 1);
    },
  );

  test(
    'records a return from server candidates and derives exact total',
    () async {
      late Map<String, dynamic> body;
      final repository = SpinaTaxSettlementRepository(
        client: MockClient((incoming) async {
          body = jsonDecode(incoming.body) as Map<String, dynamic>;
          return _itemResponse(_item('return_recorded_awaiting_payment'));
        }),
      );
      final candidate = TaxReturnLiabilityCandidate.fromPayload(_candidate());

      await repository.recordReturn(
        _session,
        deviceId: 'management-device',
        candidates: <TaxReturnLiabilityCandidate>[candidate],
        idempotencyKey: _idempotencyId,
        returnPeriodStart: '2026-08-01',
        returnPeriodEnd: '2026-08-31',
        filingDate: '2026-09-01',
        returnReference: 'BIR-RETURN-100',
        evidenceReference: 'retained://returns/100',
        evidenceDigest: _digest,
        evidenceNote: 'Retained filed return evidence for exact liabilities.',
      );

      expect(body['tax_type'], 'documentary_stamp_tax');
      expect(body['declared_tax_due'], '75.00');
      expect(body['liability_posting_ids'], <String>[_postingId]);
    },
  );

  test('posts only exact prepared settlement coordinates', () async {
    late Map<String, dynamic> body;
    final repository = SpinaTaxSettlementRepository(
      client: MockClient((incoming) async {
        body = jsonDecode(incoming.body) as Map<String, dynamic>;
        return _itemResponse(_item('settled'));
      }),
    );
    final item = TaxSettlementItem.fromPayload(_item('settlement_prepared'));

    await repository.post(
      _session,
      deviceId: 'management-device',
      item: item,
      confirmationToken: _token,
    );

    expect(body, <String, Object>{
      'confirm': true,
      'confirmation_token': _token,
      'expected_return_evidence_digest': _digest,
      'expected_payment_evidence_digest': _paymentDigest,
      'expected_payment_amount': '75.00',
      'expected_tax_payable_account_code': '2100',
      'expected_cash_account_code': '1010',
      'expected_posting_date': '2026-09-02',
      'expected_fiscal_period_id': _periodId,
    });
  });

  test(
    'records exact full-payment evidence before separate preparation',
    () async {
      final requests = <http.Request>[];
      final repository = SpinaTaxSettlementRepository(
        client: MockClient((incoming) async {
          requests.add(incoming);
          return requests.length == 1
              ? _itemResponse(_item('payment_evidence_ready'))
              : _itemResponse(_item('settlement_prepared'));
        }),
      );
      final awaiting = TaxSettlementItem.fromPayload(
        _item('return_recorded_awaiting_payment'),
      );
      final ready = await repository.recordPayment(
        _session,
        deviceId: 'management-device',
        item: awaiting,
        idempotencyKey: _idempotencyId,
        paymentDate: '2026-09-02',
        cashAccountSystemKey: 'cash_office',
        paymentReference: 'PAY-100',
        evidenceReference: 'retained://pay/100',
        evidenceDigest: _paymentDigest,
        evidenceNote: 'Retained exact full-payment evidence for this return.',
      );
      await repository.prepare(
        _session,
        deviceId: 'management-device',
        item: ready,
      );

      expect(
        requests.first.url.path,
        '/api/mobile/v1/management/financial-accounting/tax/settlements/'
        'returns/$_returnId/payments',
      );
      expect(
        jsonDecode(requests.first.body),
        containsPair('payment_amount', '75.00'),
      );
      expect(
        requests.last.url.path,
        '/api/mobile/v1/management/financial-accounting/tax/settlements/'
        'payments/$_paymentId/prepare',
      );
      expect(jsonDecode(requests.last.body), <String, Object>{'confirm': true});
    },
  );

  test('rejects invented candidate and unsafe policy before I/O', () async {
    final malformed = _candidate()..['posting_id'] = 'typed-by-user';
    expect(
      () => TaxReturnLiabilityCandidate.fromPayload(malformed),
      throwsA(isA<SpinaApiException>()),
    );
    final unsafe = _overview()..['automatic_source_posting'] = true;
    expect(
      () => TaxSettlementOverview.fromPayload(unsafe),
      throwsA(isA<SpinaApiException>()),
    );
    final missingPayable = _item('payment_evidence_ready')
      ..['tax_payable_account_code'] = null;
    expect(
      () => TaxSettlementItem.fromPayload(missingPayable),
      throwsA(isA<SpinaApiException>()),
    );
  });
}

http.Response _response(Map<String, Object?> data) => http.Response(
  jsonEncode(<String, Object?>{'success': true, 'data': data}),
  200,
  headers: const <String, String>{'content-type': 'application/json'},
);
http.Response _itemResponse(Map<String, Object?> item) =>
    _response(<String, Object?>{'item': item});

Map<String, Object?> _overview() => <String, Object?>{
  'summary': <String, Object>{
    'return_count': 1,
    'awaiting_payment_evidence_count': 0,
    'ready_to_prepare_count': 1,
    'prepared_count': 0,
    'settled_count': 0,
    'settled_adjustment_review_count': 0,
    'settled_adjustment_in_progress_count': 0,
    'settled_adjustment_recorded_count': 0,
    'blocked_count': 0,
    'settled_tax_total': '0.00',
    'tax_settlement_enabled': true,
    'tax_adjustment_reversal_enabled': true,
    'automatic_source_posting': false,
  },
  'items': <Object?>[_item('payment_evidence_ready')],
  'return_liability_candidates': <Object?>[_candidate()],
  'permissions': <String, Object>{
    'return_evidence_record': true,
    'payment_evidence_record': true,
    'settlement_prepare': true,
    'settlement_post': true,
  },
  'settlement_status': 'ready',
  'limit': 25,
  'offset': 5,
  'tax_settlement_enabled': true,
  'tax_adjustment_reversal_enabled': true,
  'automatic_source_posting': false,
  'notice': 'Exact return and payment evidence are required.',
};

Map<String, Object?> _candidate() => <String, Object?>{
  'tax_type': 'documentary_stamp_tax',
  'posting_id': _postingId,
  'evidence_id': _evidenceId,
  'evidence_version': 1,
  'source_id': _sourceId,
  'loan_id': _loanId,
  'client_id': _clientId,
  'recognition_date': '2026-08-30',
  'tax_due': '75.00',
  'evidence_digest': _digest,
  'entry_number': 'GJ-2026-0020',
  'fiscal_period_id': _periodId,
};

Map<String, Object?> _item(String status) {
  final hasPayment = status != 'return_recorded_awaiting_payment';
  final prepared = status == 'settlement_prepared' || status == 'settled';
  final posted = status == 'settled';
  return <String, Object?>{
    'tax_return_id': _returnId,
    'tax_type': 'documentary_stamp_tax',
    'return_period_start': '2026-08-01',
    'return_period_end': '2026-08-31',
    'filing_date': '2026-09-01',
    'declared_tax_due': '75.00',
    'return_reference': 'BIR-RETURN-100',
    'return_evidence_reference': 'retained://returns/100',
    'return_evidence_digest': _digest,
    'return_recorded_by_user_id': _actorId,
    'return_recorded_at': '2026-09-01T02:00:00+00:00',
    'liability_count': 1,
    'current_exact_count': 1,
    'liability_total': '75.00',
    'payment_evidence_id': hasPayment ? _paymentId : null,
    'payment_date': hasPayment ? '2026-09-02' : null,
    'payment_amount': hasPayment ? '75.00' : null,
    'cash_account_system_key': hasPayment ? 'cash_office' : null,
    'cash_account_code': hasPayment ? '1010' : null,
    'cash_account_name': hasPayment ? 'Cash - Office' : null,
    'tax_payable_account_code': '2100',
    'tax_payable_account_name': 'Tax Payables',
    'payment_reference': hasPayment ? 'PAY-100' : null,
    'payment_evidence_reference': hasPayment ? 'retained://pay/100' : null,
    'payment_evidence_digest': hasPayment ? _paymentDigest : null,
    'payment_recorded_by_user_id': hasPayment ? _actorId : null,
    'payment_recorded_at': hasPayment ? '2026-09-02T02:00:00+00:00' : null,
    'preparation_id': prepared ? _preparationId : null,
    'journal_entry_id': prepared ? _journalId : null,
    'journal_status': prepared ? (posted ? 'posted' : 'draft') : null,
    'entry_number': posted ? 'GJ-2026-0030' : null,
    'fiscal_period_id': prepared ? _periodId : null,
    'prepared_by_user_id': prepared ? _actorId : null,
    'prepared_at': prepared ? '2026-09-02T03:00:00+00:00' : null,
    'settlement_posting_id': posted ? _settlementId : null,
    'confirmation_digest': posted ? _confirmationDigest : null,
    'posted_by_user_id': posted ? _actorId : null,
    'posted_at': posted ? '2026-09-02T03:10:00+00:00' : null,
    'settlement_status': status,
    'settlement_blocker': null,
    'tax_settlement_enabled': true,
    'tax_adjustment_reversal_enabled': true,
    'automatic_source_posting': false,
  };
}

const _session = UserSession(
  userId: 'management-1',
  username: 'manager',
  displayName: 'Management',
  role: AppRole.management,
  rawRole: 'Management',
  accessToken: 'management-token',
  permissions: <String>[
    'accounting.tax.return_evidence.record',
    'accounting.tax.payment_evidence.record',
    'accounting.tax.settlement.prepare',
    'accounting.tax.settlement.post',
  ],
);
const _returnId = '11111111-1111-4111-8111-111111111111';
const _postingId = '22222222-2222-4222-8222-222222222222';
const _evidenceId = '33333333-3333-4333-8333-333333333333';
const _sourceId = '44444444-4444-4444-8444-444444444444';
const _loanId = '55555555-5555-4555-8555-555555555555';
const _clientId = '66666666-6666-4666-8666-666666666666';
const _periodId = '77777777-7777-4777-8777-777777777777';
const _paymentId = '88888888-8888-4888-8888-888888888888';
const _preparationId = '99999999-9999-4999-8999-999999999999';
const _journalId = 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa';
const _settlementId = 'bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb';
const _actorId = 'cccccccc-cccc-4ccc-8ccc-cccccccccccc';
const _idempotencyId = 'dddddddd-dddd-4ddd-8ddd-dddddddddddd';
const _digest =
    'eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee';
const _paymentDigest =
    'ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff';
const _confirmationDigest =
    'abababababababababababababababababababababababababababababababab';
const _token =
    'cdcdcdcdcdcdcdcdcdcdcdcdcdcdcdcdcdcdcdcdcdcdcdcdcdcdcdcdcdcdcdcd';
