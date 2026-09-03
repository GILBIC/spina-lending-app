import 'dart:convert';

import 'package:flutter_test/flutter_test.dart';
import 'package:gilbic_mobile/src/core/auth/app_role.dart';
import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/management/tax_recoverable.dart';
import 'package:gilbic_mobile/src/core/management/tax_recoverable_repository.dart';
import 'package:gilbic_mobile/src/core/network/spina_api.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

void main() {
  test('loads exact refund and credit candidates through Mobile aliases', () async {
    final requests = <http.Request>[];
    final repository = SpinaTaxRecoverableRepository(
      client: MockClient((request) async {
        requests.add(request);
        return _response(
          request.url.path.endsWith('recoverable-refunds')
              ? _refundOverview()
              : _creditOverview(),
        );
      }),
    );

    final result = await repository.load(_session, deviceId: 'approved-device');

    expect(requests, hasLength(2));
    expect(
      requests.map((request) => request.url.path),
      containsAll(<String>[
        '/api/mobile/v1/management/financial-accounting/tax/recoverable-refunds',
        '/api/mobile/v1/management/financial-accounting/tax/recoverable-credits',
      ]),
    );
    expect(
      requests.every(
        (request) => request.headers['X-Device-Id'] == 'approved-device',
      ),
      isTrue,
    );
    expect(result.refunds.candidates.single.recoverableAmount, '75.00');
    expect(result.credits.candidates.single.targetDeclaredTaxDue, '75.00');
  });

  test(
    'records evidence only from server-derived relationship coordinates',
    () async {
      final bodies = <Map<String, dynamic>>[];
      final repository = SpinaTaxRecoverableRepository(
        client: MockClient((request) async {
          bodies.add(jsonDecode(request.body) as Map<String, dynamic>);
          return _response(<String, Object?>{
            'item': request.url.path.contains('recoverable-refunds')
                ? _refundItem('refund_evidence_ready')
                : _creditItem('credit_evidence_ready'),
          });
        }),
      );

      await repository.recordRefundEvidence(
        _session,
        deviceId: 'approved-device',
        candidate: TaxRecoverableRefundCandidate.fromPayload(
          _refundCandidate(),
        ),
        idempotencyKey: _idempotency,
        refundDate: '2026-08-30',
        cashAccountCode: '1010',
        refundReference: 'BIR-REFUND-1',
        authorityReference: 'BIR authority retained',
        evidenceDigest: _evidenceDigest,
        evidenceNote:
            'Retained exact cash refund authority and receipt evidence.',
      );
      await repository.recordCreditEvidence(
        _session,
        deviceId: 'approved-device',
        candidate: TaxRecoverableCreditCandidate.fromPayload(
          _creditCandidate(),
        ),
        idempotencyKey: _idempotency,
        applicationDate: '2026-08-30',
        applicationReference: 'BIR-CREDIT-1',
        authorityReference: 'BIR credit authority retained',
        evidenceDigest: _evidenceDigest,
        evidenceNote:
            'Retained exact tax credit application authority evidence.',
      );

      expect(bodies.first['adjustment_posting_id'], _adjustmentPostingId);
      expect(bodies.first.containsKey('refund_amount'), isFalse);
      expect(bodies.last['adjustment_posting_id'], _adjustmentPostingId);
      expect(bodies.last['target_tax_return_id'], _returnId);
      expect(bodies.last.containsKey('credit_amount'), isFalse);
    },
  );

  test('posts only exact prepared refund and credit coordinates', () async {
    final bodies = <Map<String, dynamic>>[];
    final repository = SpinaTaxRecoverableRepository(
      client: MockClient((request) async {
        bodies.add(jsonDecode(request.body) as Map<String, dynamic>);
        return _response(<String, Object?>{
          'item': request.url.path.contains('recoverable-refunds')
              ? _refundItem('refund_realized')
              : _creditItem('credit_applied'),
        });
      }),
    );

    await repository.postRefund(
      _session,
      deviceId: 'approved-device',
      item: TaxRecoverableRefundItem.fromPayload(
        _refundItem('refund_prepared'),
      ),
      confirmationToken: _token,
    );
    await repository.postCredit(
      _session,
      deviceId: 'approved-device',
      item: TaxRecoverableCreditItem.fromPayload(
        _creditItem('credit_prepared'),
      ),
      confirmationToken: _token,
    );

    expect(bodies.first['expected_refund_amount'], '75.00');
    expect(bodies.first['expected_cash_account_code'], '1010');
    expect(bodies.first['expected_tax_recoverable_account_code'], '1130');
    expect(bodies.last['expected_credit_amount'], '75.00');
    expect(bodies.last['expected_tax_payable_account_code'], '2100');
    expect(bodies.last['expected_tax_recoverable_account_code'], '1130');
  });

  test('rejects inconsistent or weakened recoverable policy payloads', () {
    final amountMismatch = _creditCandidate()
      ..['target_declared_tax_due'] = '74.99';
    expect(
      () => TaxRecoverableCreditCandidate.fromPayload(amountMismatch),
      throwsA(isA<SpinaApiException>()),
    );
    final disabled = _refundOverview()
      ..['tax_recoverable_refund_realization_enabled'] = false;
    expect(
      () => TaxRecoverableRefundOverview.fromPayload(disabled),
      throwsA(isA<SpinaApiException>()),
    );
  });
}

http.Response _response(Map<String, Object?> data) => http.Response(
  jsonEncode(<String, Object?>{'success': true, 'data': data}),
  200,
  headers: const <String, String>{'content-type': 'application/json'},
);

Map<String, Object?> _refundOverview() => <String, Object?>{
  'summary': <String, Object?>{
    'refund_evidence_count': 0,
    'ready_to_prepare_count': 0,
    'prepared_count': 0,
    'realized_count': 0,
    'blocked_count': 0,
    'realized_refund_total': '0.00',
    ..._policy,
  },
  'items': <Object?>[],
  'refund_candidates': <Object?>[_refundCandidate()],
  'permissions': <String, Object?>{
    'refund_evidence_record': true,
    'refund_prepare': true,
    'refund_post': true,
  },
  'refund_status': 'all',
  'limit': 100,
  'offset': 0,
  ..._policy,
  'notice': 'Exact full-only cash refund realization.',
};

Map<String, Object?> _creditOverview() => <String, Object?>{
  'summary': <String, Object?>{
    'credit_evidence_count': 0,
    'ready_to_prepare_count': 0,
    'prepared_count': 0,
    'applied_count': 0,
    'blocked_count': 0,
    'applied_credit_total': '0.00',
    ..._policy,
  },
  'items': <Object?>[],
  'credit_candidates': <Object?>[_creditCandidate()],
  'permissions': <String, Object?>{
    'credit_evidence_record': true,
    'credit_prepare': true,
    'credit_post': true,
  },
  'credit_status': 'all',
  'limit': 100,
  'offset': 0,
  ..._policy,
  'notice': 'Exact full-only same-tax-type credit application.',
};

Map<String, Object?> _refundCandidate() => <String, Object?>{
  'adjustment_posting_id': _adjustmentPostingId,
  'adjustment_evidence_id': _adjustmentEvidenceId,
  'tax_type': 'documentary_stamp_tax',
  'source_id': _sourceId,
  'loan_id': _loanId,
  'client_id': _clientId,
  'recoverable_amount': '75.00',
  'minimum_refund_date': '2026-08-20',
  'adjustment_evidence_digest': _adjustmentDigest,
  'entry_number': 'GJ-2026-50',
  'fiscal_period_id': _periodId,
};

Map<String, Object?> _creditCandidate() => <String, Object?>{
  ..._refundCandidate(),
  'credit_amount': '75.00',
  'target_tax_return_id': _returnId,
  'target_return_period_start': '2026-08-01',
  'target_return_period_end': '2026-08-31',
  'target_filing_date': '2026-08-25',
  'target_declared_tax_due': '75.00',
  'target_return_reference': 'BIR-RETURN-1',
  'target_return_evidence_digest': _returnDigest,
  'minimum_application_date': '2026-08-25',
};

Map<String, Object?> _refundItem(String status) {
  final prepared = status != 'refund_evidence_ready';
  final posted = status == 'refund_realized';
  return <String, Object?>{
    'refund_evidence_id': _refundEvidenceId,
    'adjustment_posting_id': _adjustmentPostingId,
    'adjustment_evidence_id': _adjustmentEvidenceId,
    'tax_type': 'documentary_stamp_tax',
    'source_id': _sourceId,
    'loan_id': _loanId,
    'client_id': _clientId,
    'refund_amount': '75.00',
    'refund_date': '2026-08-30',
    'cash_account_id': _cashAccountId,
    'cash_account_code': '1010',
    'cash_account_name': 'Cash - Office',
    'refund_reference': 'BIR-REFUND-1',
    'authority_reference': 'BIR authority retained',
    'evidence_digest': _evidenceDigest,
    'recorded_by_user_id': _actorId,
    'recorded_at': '2026-08-30T01:00:00+00:00',
    'preparation_id': prepared ? _preparationId : null,
    'journal_entry_id': prepared ? _journalId : null,
    'journal_status': prepared ? (posted ? 'posted' : 'draft') : null,
    'entry_number': posted ? 'GJ-2026-51' : null,
    'fiscal_period_id': prepared ? _periodId : null,
    'tax_recoverable_account_id': prepared ? _recoverableAccountId : null,
    'tax_recoverable_account_code': prepared ? '1130' : null,
    'tax_recoverable_account_name': prepared ? 'Tax Recoverable' : null,
    'prepared_by_user_id': prepared ? _actorId : null,
    'prepared_at': prepared ? '2026-08-30T01:10:00+00:00' : null,
    'refund_posting_id': posted ? _refundPostingId : null,
    'confirmation_digest': posted ? _confirmationDigest : null,
    'posted_by_user_id': posted ? _actorId : null,
    'posted_at': posted ? '2026-08-30T01:20:00+00:00' : null,
    'refund_status': status,
    'refund_blocker': null,
    'tax_recoverable_refund_realization_enabled': true,
    'tax_recoverable_credit_application_enabled': true,
    'automatic_source_posting': false,
  };
}

Map<String, Object?> _creditItem(String status) {
  final prepared = status != 'credit_evidence_ready';
  final posted = status == 'credit_applied';
  return <String, Object?>{
    'credit_evidence_id': _creditEvidenceId,
    'adjustment_posting_id': _adjustmentPostingId,
    'adjustment_evidence_id': _adjustmentEvidenceId,
    'tax_type': 'documentary_stamp_tax',
    'source_id': _sourceId,
    'loan_id': _loanId,
    'client_id': _clientId,
    'target_tax_return_id': _returnId,
    'target_return_period_start': '2026-08-01',
    'target_return_period_end': '2026-08-31',
    'target_filing_date': '2026-08-25',
    'target_declared_tax_due': '75.00',
    'target_return_reference': 'BIR-RETURN-1',
    'target_return_evidence_digest': _returnDigest,
    'credit_amount': '75.00',
    'application_date': '2026-08-30',
    'application_reference': 'BIR-CREDIT-1',
    'authority_reference': 'BIR credit authority retained',
    'evidence_digest': _evidenceDigest,
    'recorded_by_user_id': _actorId,
    'recorded_at': '2026-08-30T01:00:00+00:00',
    'preparation_id': prepared ? _preparationId : null,
    'journal_entry_id': prepared ? _journalId : null,
    'journal_status': prepared ? (posted ? 'posted' : 'draft') : null,
    'entry_number': posted ? 'GJ-2026-52' : null,
    'fiscal_period_id': prepared ? _periodId : null,
    'tax_payable_account_id': prepared ? _payableAccountId : null,
    'tax_payable_account_code': prepared ? '2100' : null,
    'tax_payable_account_name': prepared ? 'Tax Payables' : null,
    'tax_recoverable_account_id': prepared ? _recoverableAccountId : null,
    'tax_recoverable_account_code': prepared ? '1130' : null,
    'tax_recoverable_account_name': prepared ? 'Tax Recoverable' : null,
    'prepared_by_user_id': prepared ? _actorId : null,
    'prepared_at': prepared ? '2026-08-30T01:10:00+00:00' : null,
    'credit_posting_id': posted ? _creditPostingId : null,
    'confirmation_digest': posted ? _confirmationDigest : null,
    'posted_by_user_id': posted ? _actorId : null,
    'posted_at': posted ? '2026-08-30T01:20:00+00:00' : null,
    'credit_status': status,
    'credit_blocker': null,
    ..._policy,
  };
}

const _policy = <String, Object?>{
  'tax_recoverable_refund_realization_enabled': true,
  'tax_recoverable_credit_application_enabled': true,
  'partial_tax_recoverable_realization_enabled': false,
  'automatic_source_posting': false,
};
const _session = UserSession(
  userId: 'm1',
  username: 'manager',
  displayName: 'Management',
  role: AppRole.management,
  rawRole: 'Management',
  accessToken: 'token',
  permissions: <String>[],
);
const _adjustmentPostingId = '11111111-1111-4111-8111-111111111111';
const _adjustmentEvidenceId = '22222222-2222-4222-8222-222222222222';
const _sourceId = '33333333-3333-4333-8333-333333333333';
const _loanId = '44444444-4444-4444-8444-444444444444';
const _clientId = '55555555-5555-4555-8555-555555555555';
const _periodId = '66666666-6666-4666-8666-666666666666';
const _returnId = '77777777-7777-4777-8777-777777777777';
const _refundEvidenceId = '88888888-8888-4888-8888-888888888888';
const _creditEvidenceId = '99999999-9999-4999-8999-999999999999';
const _cashAccountId = 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa';
const _recoverableAccountId = 'bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb';
const _payableAccountId = 'cccccccc-cccc-4ccc-8ccc-cccccccccccc';
const _actorId = 'dddddddd-dddd-4ddd-8ddd-dddddddddddd';
const _preparationId = 'eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee';
const _journalId = 'ffffffff-ffff-4fff-8fff-ffffffffffff';
const _refundPostingId = '12121212-1212-4212-8212-121212121212';
const _creditPostingId = '13131313-1313-4313-8313-131313131313';
const _idempotency = '14141414-1414-4414-8414-141414141414';
const _adjustmentDigest =
    '1111111111111111111111111111111111111111111111111111111111111111';
const _returnDigest =
    '2222222222222222222222222222222222222222222222222222222222222222';
const _evidenceDigest =
    '3333333333333333333333333333333333333333333333333333333333333333';
const _confirmationDigest =
    '4444444444444444444444444444444444444444444444444444444444444444';
const _token =
    '5555555555555555555555555555555555555555555555555555555555555555';
