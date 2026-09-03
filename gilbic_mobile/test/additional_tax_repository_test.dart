import 'dart:convert';

import 'package:flutter_test/flutter_test.dart';
import 'package:gilbic_mobile/src/core/auth/app_role.dart';
import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/management/additional_tax.dart';
import 'package:gilbic_mobile/src/core/management/additional_tax_repository.dart';
import 'package:gilbic_mobile/src/core/network/spina_api.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

void main() {
  test(
    'loads server-derived additional-tax candidates with device authority',
    () async {
      late http.Request request;
      final repository = SpinaAdditionalTaxRepository(
        client: MockClient((incoming) async {
          request = incoming;
          return _response(_overview());
        }),
      );
      final overview = await repository.load(
        _session,
        deviceId: 'approved-device',
        amendmentStatus: 'ready',
        limit: 25,
        offset: 5,
      );
      expect(
        request.url.path,
        '/api/mobile/v1/management/financial-accounting/tax/additional-amendments',
      );
      expect(request.headers['X-Device-Id'], 'approved-device');
      expect(overview.candidates.single.additionalTaxDue, '25.00');
      expect(overview.candidates.single.paymentRequiredAmount, '25.00');
    },
  );

  test(
    'records evidence only from candidate-derived protected coordinates',
    () async {
      late Map<String, dynamic> body;
      final repository = SpinaAdditionalTaxRepository(
        client: MockClient((incoming) async {
          body = jsonDecode(incoming.body) as Map<String, dynamic>;
          return _response(<String, Object?>{
            'item': _item('amendment_evidence_ready'),
          });
        }),
      );
      await repository.recordAmendmentEvidence(
        _session,
        deviceId: 'approved-device',
        candidate: AdditionalTaxCandidate.fromPayload(_candidate()),
        idempotencyKey: _idempotency,
        amendmentBasis: 'amended_return',
        amendmentDate: '2026-08-30',
        amendmentReference: 'BIR-AMEND-1',
        evidenceReference: 'retained://tax/amendment/1',
        evidenceDigest: _evidenceDigest,
        evidenceNote:
            'Retained exact amended return evidence for this protected item.',
      );
      expect(body['tax_return_id'], _returnId);
      expect(body['tax_liability_posting_id'], _liabilityPostingId);
      expect(body['replacement_evidence_id'], _replacementEvidenceId);
      expect(body['recognition_date'], '2026-08-15');
      expect(body.containsKey('additional_tax_due'), isFalse);
    },
  );

  test('posts exact prepared liability and settlement coordinates', () async {
    final requests = <http.Request>[];
    final repository = SpinaAdditionalTaxRepository(
      client: MockClient((incoming) async {
        requests.add(incoming);
        return _response(<String, Object?>{
          'item': _item(
            incoming.url.path.endsWith('post-settlement')
                ? 'additional_tax_settled'
                : 'additional_liability_posted_awaiting_payment',
          ),
        });
      }),
    );
    await repository.postLiability(
      _session,
      deviceId: 'approved-device',
      item: AdditionalTaxItem.fromPayload(
        _item('additional_liability_prepared'),
      ),
      confirmationToken: _token,
    );
    await repository.postSettlement(
      _session,
      deviceId: 'approved-device',
      item: AdditionalTaxItem.fromPayload(
        _item('additional_settlement_prepared'),
      ),
      confirmationToken: _token,
    );
    final liability = jsonDecode(requests.first.body) as Map<String, dynamic>;
    expect(liability['expected_additional_tax_due'], '25.00');
    expect(liability['expected_tax_payable_account_code'], '2100');
    final settlement = jsonDecode(requests.last.body) as Map<String, dynamic>;
    expect(settlement['expected_payment_amount'], '25.00');
    expect(settlement['expected_cash_account_code'], '1010');
    expect(
      settlement['expected_additional_liability_confirmation_digest'],
      _liabilityDigest,
    );
  });

  test('rejects inconsistent server-derived additional tax', () {
    final malformed = _candidate()..['additional_tax_due'] = '24.99';
    expect(
      () => AdditionalTaxCandidate.fromPayload(malformed),
      throwsA(isA<SpinaApiException>()),
    );
  });
}

http.Response _response(Map<String, Object?> data) => http.Response(
  jsonEncode(<String, Object?>{'success': true, 'data': data}),
  200,
  headers: const <String, String>{'content-type': 'application/json'},
);

Map<String, Object?> _overview() => <String, Object?>{
  'summary': <String, Object?>{
    'amendment_evidence_count': 1,
    'amendment_ready_count': 1,
    'liability_prepared_count': 0,
    'awaiting_payment_count': 0,
    'payment_ready_count': 0,
    'settlement_prepared_count': 0,
    'settled_count': 0,
    'review_count': 0,
    'blocked_count': 0,
    'recognized_additional_tax_total': '0.00',
    'settled_payment_total': '0.00',
    'tax_additional_amendment_enabled': true,
    'tax_additional_settlement_enabled': true,
    'tax_refund_credit_realization_enabled': false,
    'automatic_source_posting': false,
  },
  'items': <Object?>[],
  'amendment_candidates': <Object?>[_candidate()],
  'permissions': <String, Object?>{
    'amendment_evidence_record': true,
    'additional_liability_prepare': true,
    'additional_liability_post': true,
    'additional_payment_evidence_record': true,
    'additional_settlement_prepare': true,
    'additional_settlement_post': true,
  },
  'amendment_status': 'ready',
  'limit': 25,
  'offset': 5,
  'tax_additional_amendment_enabled': true,
  'tax_additional_settlement_enabled': true,
  'tax_refund_credit_realization_enabled': false,
  'automatic_source_posting': false,
  'notice': 'Original posted history remains immutable.',
};

Map<String, Object?> _candidate() => <String, Object?>{
  'tax_type': 'documentary_stamp_tax',
  'tax_return_id': _returnId,
  'tax_liability_posting_id': _liabilityPostingId,
  'original_evidence_id': _originalEvidenceId,
  'original_evidence_version': 1,
  'replacement_evidence_id': _replacementEvidenceId,
  'replacement_evidence_version': 2,
  'source_id': _sourceId,
  'loan_id': _loanId,
  'client_id': _clientId,
  'original_declared_tax_due': '75.00',
  'revised_declared_tax_due': '100.00',
  'original_item_tax_due': '75.00',
  'replacement_item_tax_due': '100.00',
  'additional_tax_due': '25.00',
  'payment_basis': 'additional_due_after_settlement',
  'payment_required_amount': '25.00',
  'filing_date': '2026-08-20',
  'recognition_date': '2026-08-15',
  'original_evidence_digest': _originalDigest,
  'replacement_evidence_digest': _replacementDigest,
  'original_fiscal_period_id': _periodId,
  'original_fiscal_period_start': '2026-08-01',
  'original_fiscal_period_end': '2026-08-31',
  'original_settlement_posting_id': _originalSettlementId,
};

Map<String, Object?> _item(String status) {
  final liabilityPrepared = status != 'amendment_evidence_ready';
  final liabilityPosted = <String>{
    'additional_liability_posted_awaiting_payment',
    'additional_payment_evidence_ready',
    'additional_settlement_prepared',
    'additional_tax_settled',
  }.contains(status);
  final paid = <String>{
    'additional_payment_evidence_ready',
    'additional_settlement_prepared',
    'additional_tax_settled',
  }.contains(status);
  final settlementPrepared = <String>{
    'additional_settlement_prepared',
    'additional_tax_settled',
  }.contains(status);
  final settled = status == 'additional_tax_settled';
  return <String, Object?>{
    ..._candidate(),
    'amendment_evidence_id': _amendmentId,
    'amendment_basis': 'amended_return',
    'amendment_date': '2026-08-30',
    'amendment_reference': 'BIR-AMEND-1',
    'evidence_reference': 'retained://tax/amendment/1',
    'evidence_digest': _evidenceDigest,
    'original_payment_evidence_id': _originalPaymentId,
    'original_settlement_journal_entry_id': _originalSettlementJournalId,
    'recorded_by_user_id': _actorId,
    'recorded_at': '2026-08-30T01:00:00+00:00',
    'liability_preparation_id': liabilityPrepared
        ? _liabilityPreparationId
        : null,
    'liability_journal_entry_id': liabilityPrepared
        ? _liabilityJournalId
        : null,
    'liability_journal_status': liabilityPrepared
        ? (liabilityPosted ? 'posted' : 'draft')
        : null,
    'liability_entry_number': liabilityPosted ? 'GJ-2026-40' : null,
    'liability_fiscal_period_id': liabilityPrepared ? _periodId : null,
    'expense_account_code': liabilityPrepared ? '5310' : null,
    'tax_payable_account_code': liabilityPrepared ? '2100' : null,
    'liability_prepared_by_user_id': liabilityPrepared ? _actorId : null,
    'liability_prepared_at': liabilityPrepared
        ? '2026-08-30T01:10:00+00:00'
        : null,
    'additional_liability_posting_id': liabilityPosted
        ? _additionalLiabilityPostingId
        : null,
    'liability_confirmation_digest': liabilityPosted ? _liabilityDigest : null,
    'liability_posted_by_user_id': liabilityPosted ? _actorId : null,
    'liability_posted_at': liabilityPosted ? '2026-08-30T01:20:00+00:00' : null,
    'additional_payment_evidence_id': paid ? _additionalPaymentId : null,
    'payment_date': paid ? '2026-08-30' : null,
    'payment_amount': paid ? '25.00' : null,
    'cash_account_system_key': paid ? 'cash_office' : null,
    'payment_cash_account_code': paid ? '1010' : null,
    'payment_cash_account_name': paid ? 'Cash - Office' : null,
    'payment_reference': paid ? 'BIR-PAY-1' : null,
    'payment_evidence_reference': paid ? 'retained://tax/payment/1' : null,
    'payment_evidence_digest': paid ? _paymentDigest : null,
    'payment_recorded_by_user_id': paid ? _actorId : null,
    'payment_recorded_at': paid ? '2026-08-30T01:30:00+00:00' : null,
    'settlement_preparation_id': settlementPrepared
        ? _settlementPreparationId
        : null,
    'settlement_journal_entry_id': settlementPrepared
        ? _settlementJournalId
        : null,
    'settlement_journal_status': settlementPrepared
        ? (settled ? 'posted' : 'draft')
        : null,
    'settlement_entry_number': settled ? 'GJ-2026-41' : null,
    'settlement_fiscal_period_id': settlementPrepared ? _periodId : null,
    'settlement_prepared_by_user_id': settlementPrepared ? _actorId : null,
    'settlement_prepared_at': settlementPrepared
        ? '2026-08-30T01:40:00+00:00'
        : null,
    'additional_settlement_posting_id': settled
        ? _additionalSettlementPostingId
        : null,
    'settlement_confirmation_digest': settled ? _settlementDigest : null,
    'settlement_posted_by_user_id': settled ? _actorId : null,
    'settlement_posted_at': settled ? '2026-08-30T01:50:00+00:00' : null,
    'amendment_status': status,
    'amendment_blocker': null,
    'tax_additional_amendment_enabled': true,
    'tax_additional_settlement_enabled': true,
    'tax_refund_credit_realization_enabled': false,
    'automatic_source_posting': false,
  };
}

const _session = UserSession(
  userId: 'm1',
  username: 'manager',
  displayName: 'Management',
  role: AppRole.management,
  rawRole: 'Management',
  accessToken: 'token',
  permissions: <String>[],
);
const _returnId = '11111111-1111-4111-8111-111111111111';
const _liabilityPostingId = '22222222-2222-4222-8222-222222222222';
const _originalEvidenceId = '33333333-3333-4333-8333-333333333333';
const _replacementEvidenceId = '44444444-4444-4444-8444-444444444444';
const _sourceId = '55555555-5555-4555-8555-555555555555';
const _loanId = '66666666-6666-4666-8666-666666666666';
const _clientId = '77777777-7777-4777-8777-777777777777';
const _periodId = '88888888-8888-4888-8888-888888888888';
const _originalSettlementId = '99999999-9999-4999-8999-999999999999';
const _originalPaymentId = 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa';
const _originalSettlementJournalId = 'bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb';
const _actorId = 'cccccccc-cccc-4ccc-8ccc-cccccccccccc';
const _amendmentId = 'dddddddd-dddd-4ddd-8ddd-dddddddddddd';
const _liabilityPreparationId = 'eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee';
const _liabilityJournalId = 'ffffffff-ffff-4fff-8fff-ffffffffffff';
const _additionalLiabilityPostingId = '12121212-1212-4212-8212-121212121212';
const _additionalPaymentId = '13131313-1313-4313-8313-131313131313';
const _settlementPreparationId = '14141414-1414-4414-8414-141414141414';
const _settlementJournalId = '15151515-1515-4515-8515-151515151515';
const _additionalSettlementPostingId = '16161616-1616-4616-8616-161616161616';
const _idempotency = '17171717-1717-4717-8717-171717171717';
const _originalDigest =
    '1111111111111111111111111111111111111111111111111111111111111111';
const _replacementDigest =
    '2222222222222222222222222222222222222222222222222222222222222222';
const _evidenceDigest =
    '3333333333333333333333333333333333333333333333333333333333333333';
const _liabilityDigest =
    '4444444444444444444444444444444444444444444444444444444444444444';
const _paymentDigest =
    '5555555555555555555555555555555555555555555555555555555555555555';
const _settlementDigest =
    '6666666666666666666666666666666666666666666666666666666666666666';
const _token =
    '7777777777777777777777777777777777777777777777777777777777777777';
