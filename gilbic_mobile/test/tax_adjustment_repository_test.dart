import 'dart:convert';

import 'package:flutter_test/flutter_test.dart';
import 'package:gilbic_mobile/src/core/auth/app_role.dart';
import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/management/tax_adjustment.dart';
import 'package:gilbic_mobile/src/core/management/tax_adjustment_repository.dart';
import 'package:gilbic_mobile/src/core/network/spina_api.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

void main() {
  test('loads server-derived protected adjustment candidates', () async {
    late http.Request request;
    final repository = SpinaTaxAdjustmentRepository(
      client: MockClient((incoming) async {
        request = incoming;
        return _response(_overview());
      }),
    );
    final overview = await repository.load(
      _session,
      deviceId: 'management-device',
      adjustmentStatus: 'review',
      limit: 25,
      offset: 5,
    );
    expect(
      request.url.path,
      '/api/mobile/v1/management/financial-accounting/tax/adjustments',
    );
    expect(
      overview.adjustmentCandidates.single.adjustmentKind,
      'recognize_settled_tax_recoverable',
    );
    expect(overview.adjustmentCandidates.single.adjustmentAmount, '25.00');
  });

  test(
    'records evidence using candidate-derived kind and identifiers',
    () async {
      late Map<String, dynamic> body;
      final repository = SpinaTaxAdjustmentRepository(
        client: MockClient((incoming) async {
          body = jsonDecode(incoming.body) as Map<String, dynamic>;
          return _itemResponse(_item('evidence_ready'));
        }),
      );
      final candidate = TaxAdjustmentCandidate.fromPayload(_candidate());

      await repository.recordEvidence(
        _session,
        deviceId: 'management-device',
        candidate: candidate,
        idempotencyKey: _idempotencyId,
        adjustmentDate: '2026-08-30',
        adjustmentReference: 'ADJ-100',
        evidenceReference: 'retained://adjustments/100',
        evidenceDigest: _digest,
        evidenceNote:
            'Retained evidence supports this exact protected correction.',
      );

      expect(body['tax_liability_posting_id'], _liabilityPostingId);
      expect(body['replacement_evidence_id'], _replacementEvidenceId);
      expect(body['adjustment_kind'], 'recognize_settled_tax_recoverable');
    },
  );

  test('posts exact prepared adjustment coordinates', () async {
    late Map<String, dynamic> body;
    final repository = SpinaTaxAdjustmentRepository(
      client: MockClient((incoming) async {
        body = jsonDecode(incoming.body) as Map<String, dynamic>;
        return _itemResponse(_item('posted_settled_tax_recoverable'));
      }),
    );
    final item = TaxAdjustmentItem.fromPayload(_item('prepared_not_posted'));
    await repository.post(
      _session,
      deviceId: 'management-device',
      item: item,
      confirmationToken: _token,
    );
    expect(body, <String, Object>{
      'confirm': true,
      'confirmation_token': _token,
      'expected_evidence_digest': _digest,
      'expected_original_tax_due': '75.00',
      'expected_replacement_tax_due': '50.00',
      'expected_adjustment_amount': '25.00',
      'expected_debit_account_code': '1130',
      'expected_credit_account_code': '5310',
      'expected_posting_date': '2026-08-30',
      'expected_fiscal_period_id': _periodId,
    });
  });

  test(
    'prepares correction evidence through the separate protected action',
    () async {
      late http.Request request;
      late Map<String, dynamic> body;
      final repository = SpinaTaxAdjustmentRepository(
        client: MockClient((incoming) async {
          request = incoming;
          body = jsonDecode(incoming.body) as Map<String, dynamic>;
          return _itemResponse(_item('prepared_not_posted'));
        }),
      );
      await repository.prepare(
        _session,
        deviceId: 'management-device',
        item: TaxAdjustmentItem.fromPayload(_item('evidence_ready')),
      );
      expect(
        request.url.path,
        '/api/mobile/v1/management/financial-accounting/tax/adjustments/'
        '$_adjustmentEvidenceId/prepare',
      );
      expect(body, <String, Object>{'confirm': true});
    },
  );

  test('rejects an unknown server-derived adjustment kind', () {
    final malformed = _candidate()..['adjustment_kind'] = 'manual_override';
    expect(
      () => TaxAdjustmentCandidate.fromPayload(malformed),
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
    'adjustment_evidence_count': 1,
    'ready_to_prepare_count': 1,
    'prepared_count': 0,
    'posted_reversal_count': 0,
    'posted_recoverable_count': 0,
    'further_review_count': 0,
    'blocked_count': 0,
    'posted_adjustment_total': '0.00',
    'tax_settlement_enabled': true,
    'tax_adjustment_reversal_enabled': true,
    'automatic_source_posting': false,
  },
  'items': <Object?>[_item('evidence_ready')],
  'adjustment_candidates': <Object?>[_candidate()],
  'permissions': <String, Object>{
    'adjustment_evidence_record': true,
    'adjustment_prepare': true,
    'adjustment_post': true,
  },
  'adjustment_status': 'review',
  'limit': 25,
  'offset': 5,
  'tax_settlement_enabled': true,
  'tax_adjustment_reversal_enabled': true,
  'automatic_source_posting': false,
  'notice': 'Posted history is immutable.',
};

Map<String, Object?> _candidate() => <String, Object?>{
  'adjustment_kind': 'recognize_settled_tax_recoverable',
  'tax_type': 'documentary_stamp_tax',
  'tax_liability_posting_id': _liabilityPostingId,
  'original_evidence_id': _originalEvidenceId,
  'original_evidence_version': 1,
  'replacement_evidence_id': _replacementEvidenceId,
  'replacement_evidence_version': 2,
  'source_id': _sourceId,
  'loan_id': _loanId,
  'client_id': _clientId,
  'original_tax_due': '75.00',
  'replacement_tax_due': '50.00',
  'adjustment_amount': '25.00',
  'original_evidence_digest': _originalDigest,
  'replacement_evidence_digest': _replacementDigest,
  'fiscal_period_id': _periodId,
  'fiscal_period_start': '2026-08-01',
  'fiscal_period_end': '2026-08-31',
  'settlement_posting_id': _settlementPostingId,
};

Map<String, Object?> _item(String status) {
  final prepared =
      status == 'prepared_not_posted' || status.startsWith('posted_');
  final posted = status.startsWith('posted_');
  return <String, Object?>{
    'adjustment_evidence_id': _adjustmentEvidenceId,
    'adjustment_kind': 'recognize_settled_tax_recoverable',
    'tax_type': 'documentary_stamp_tax',
    'tax_liability_posting_id': _liabilityPostingId,
    'original_evidence_id': _originalEvidenceId,
    'replacement_evidence_id': _replacementEvidenceId,
    'source_id': _sourceId,
    'loan_id': _loanId,
    'client_id': _clientId,
    'original_tax_due': '75.00',
    'replacement_tax_due': '50.00',
    'adjustment_amount': '25.00',
    'adjustment_date': '2026-08-30',
    'adjustment_reference': 'ADJ-100',
    'evidence_reference': 'retained://adjustments/100',
    'evidence_digest': _digest,
    'recorded_by_user_id': _actorId,
    'recorded_at': '2026-08-30T02:00:00+00:00',
    'settlement_posting_id': _settlementPostingId,
    'original_settlement_journal_entry_id': _settlementJournalId,
    'preparation_id': prepared ? _preparationId : null,
    'journal_entry_id': prepared ? _journalId : null,
    'journal_status': prepared ? (posted ? 'posted' : 'draft') : null,
    'entry_number': posted ? 'GJ-2026-0040' : null,
    'fiscal_period_id': prepared ? _periodId : null,
    'debit_account_id': prepared ? _debitAccountId : null,
    'debit_account_code': prepared ? '1130' : null,
    'debit_account_name': prepared ? 'Tax Recoverable' : null,
    'credit_account_id': prepared ? _creditAccountId : null,
    'credit_account_code': prepared ? '5310' : null,
    'credit_account_name': prepared ? 'DST Expense' : null,
    'prepared_by_user_id': prepared ? _actorId : null,
    'prepared_at': prepared ? '2026-08-30T02:10:00+00:00' : null,
    'adjustment_posting_id': posted ? _adjustmentPostingId : null,
    'confirmation_digest': posted ? _confirmationDigest : null,
    'posted_by_user_id': posted ? _actorId : null,
    'posted_at': posted ? '2026-08-30T02:20:00+00:00' : null,
    'adjustment_status': status,
    'adjustment_blocker': null,
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
    'accounting.tax.adjustment_evidence.record',
    'accounting.tax.adjustment.prepare',
    'accounting.tax.adjustment.post',
  ],
);
const _adjustmentEvidenceId = '11111111-1111-4111-8111-111111111111';
const _liabilityPostingId = '22222222-2222-4222-8222-222222222222';
const _originalEvidenceId = '33333333-3333-4333-8333-333333333333';
const _replacementEvidenceId = '44444444-4444-4444-8444-444444444444';
const _sourceId = '55555555-5555-4555-8555-555555555555';
const _loanId = '66666666-6666-4666-8666-666666666666';
const _clientId = '77777777-7777-4777-8777-777777777777';
const _periodId = '88888888-8888-4888-8888-888888888888';
const _settlementPostingId = '99999999-9999-4999-8999-999999999999';
const _settlementJournalId = 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa';
const _preparationId = 'bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb';
const _journalId = 'cccccccc-cccc-4ccc-8ccc-cccccccccccc';
const _debitAccountId = 'dddddddd-dddd-4ddd-8ddd-dddddddddddd';
const _creditAccountId = 'eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee';
const _adjustmentPostingId = 'ffffffff-ffff-4fff-8fff-ffffffffffff';
const _actorId = 'abababab-abab-4bab-8bab-abababababab';
const _idempotencyId = 'cdcdcdcd-cdcd-4dcd-8dcd-cdcdcdcdcdcd';
const _originalDigest =
    '1111111111111111111111111111111111111111111111111111111111111111';
const _replacementDigest =
    '2222222222222222222222222222222222222222222222222222222222222222';
const _digest =
    '3333333333333333333333333333333333333333333333333333333333333333';
const _confirmationDigest =
    '4444444444444444444444444444444444444444444444444444444444444444';
const _token =
    '5555555555555555555555555555555555555555555555555555555555555555';
