import 'dart:convert';

import 'package:flutter_test/flutter_test.dart';
import 'package:gilbic_mobile/src/core/auth/app_role.dart';
import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/management/tax_evidence.dart';
import 'package:gilbic_mobile/src/core/management/tax_evidence_repository.dart';
import 'package:gilbic_mobile/src/core/network/spina_api.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

void main() {
  test('loads exact server tax readiness and page coordinates', () async {
    late http.Request request;
    final repository = SpinaTaxEvidenceRepository(
      client: MockClient((incoming) async {
        request = incoming;
        return _response(_overview());
      }),
    );

    final overview = await repository.load(
      _session,
      deviceId: 'management-device',
      readiness: 'blocked',
      limit: 50,
      offset: 10,
    );

    expect(request.method, 'GET');
    expect(
      request.url.path,
      '/api/mobile/v1/management/financial-accounting/tax',
    );
    expect(request.url.queryParameters, <String, String>{
      'readiness': 'blocked',
      'limit': '50',
      'offset': '10',
    });
    expect(request.headers['X-Device-Id'], 'management-device');
    expect(overview.summary.ruleEvidenceCount, 1);
    expect(overview.rules.first.rate, '0.0075000000');
    expect(overview.dst.single.protectedIssuePrice, '10000.00');
    expect(overview.percentageTax.single.sourceCashAmount, '500.00');
    expect(overview.automaticSourcePosting, isFalse);
  });

  test('records exact retained rule evidence with stable UUID', () async {
    late Map<String, dynamic> body;
    final repository = SpinaTaxEvidenceRepository(
      client: MockClient((incoming) async {
        body = jsonDecode(incoming.body) as Map<String, dynamic>;
        return _response(<String, Object>{
          'rule_evidence_id': _ruleId,
          'tax_posting_enabled': false,
          'automatic_source_posting': false,
        }, statusCode: 201);
      }),
    );

    final id = await repository.recordRule(
      _session,
      deviceId: 'management-device',
      draft: const TaxRuleEvidenceDraft(
        taxType: 'documentary_stamp_tax',
        ruleKey: 'dst-current',
        effectiveFrom: '2026-08-30',
        effectiveTo: null,
        treatment: 'taxable',
        rate: '0.0075000000',
        maturityMaxDays: 365,
        legalSource: 'Republic Act 12214',
        legalReference: 'Section 21 amending NIRC Section 179',
        retainedSourceReference: 'legal/dst/2026-08-30.pdf',
        evidenceDigest: _digest,
        managementRationale:
            'Approved current DST rule evidence for protected V1 source review.',
        supersedesRuleId: null,
      ),
      idempotencyKey: _retryId,
    );

    expect(id, _ruleId);
    expect(body['confirm'], isTrue);
    expect(body['idempotency_key'], _retryId);
    expect(body['rate'], '0.0075000000');
    expect(body['evidence_digest'], _digest);
  });

  test('records DST and percentage evidence from exact source rows', () async {
    final bodies = <Map<String, dynamic>>[];
    final repository = SpinaTaxEvidenceRepository(
      client: MockClient((incoming) async {
        bodies.add(jsonDecode(incoming.body) as Map<String, dynamic>);
        final isDst = incoming.url.path.endsWith('/dst-evidence');
        return _response(<String, Object>{
          if (isDst) 'dst_evidence_id': _dstEvidenceId,
          if (!isDst) 'percentage_tax_evidence_id': _percentageEvidenceId,
          'tax_posting_enabled': false,
          'automatic_source_posting': false,
        }, statusCode: 201);
      }),
    );
    final overview = TaxEvidenceOverview.fromPayload(_overview());

    await repository.recordDst(
      _session,
      deviceId: 'management-device',
      source: overview.dst.single,
      draft: const DstEvidenceDraft(
        ruleEvidenceId: _ruleId,
        expectedTaxDue: '75.00',
        instrumentReference: 'Loan instrument 1001',
        instrumentDigest: _digest,
        calculationReference: 'DST worksheet 1001',
        calculationDigest: _otherDigest,
        managementRationale:
            'Reviewed exact issue price, protected term, rule and retained worksheet.',
      ),
      idempotencyKey: _retryId,
    );
    await repository.recordPercentage(
      _session,
      deviceId: 'management-device',
      source: overview.percentageTax.single,
      draft: const PercentageTaxEvidenceDraft(
        ruleEvidenceId: _percentageRuleId,
        taxableLendingReceiptAmount: '100.00',
        principalReceiptAmount: '400.00',
        expectedTaxDue: '5.00',
        allocationReference: 'Receipt allocation 2001',
        allocationDigest: _digest,
        managementRationale:
            'Reviewed the exact protected cash allocation and current tax rule.',
      ),
      idempotencyKey: _secondRetryId,
    );

    expect(bodies.first['loan_id'], _loanId);
    expect(bodies.first['expected_issue_price'], '10000.00');
    expect(bodies.first['expected_term_days'], 90);
    expect(bodies.last['transaction_id'], _transactionId);
    expect(bodies.last['expected_source_cash_amount'], '500.00');
    expect(bodies.last['taxable_lending_receipt_amount'], '100.00');
    expect(bodies.last['principal_receipt_amount'], '400.00');
  });

  test('validates exact bounded tax rates without floating-point math', () {
    expect(
      () => _ruleDraft(rate: '1.0000000001').validate(),
      throwsArgumentError,
    );
    expect(() => _ruleDraft(rate: '0.0000000001').validate(), returnsNormally);
    expect(
      () => _ruleDraft(treatment: 'exempt', rate: '0.0000000000').validate(),
      returnsNormally,
    );
    expect(
      () => _ruleDraft(treatment: 'exempt', rate: '0.0000000001').validate(),
      throwsArgumentError,
    );
  });

  test('rejects unsafe policy and unreconciled percentage before I/O', () async {
    var calls = 0;
    final repository = SpinaTaxEvidenceRepository(
      client: MockClient((_) async {
        calls += 1;
        return _response(_overview());
      }),
    );
    final unsafe = _overview()..['automatic_source_posting'] = true;
    expect(
      () => TaxEvidenceOverview.fromPayload(unsafe),
      throwsA(isA<SpinaApiException>()),
    );
    final unknownStatus = _overview();
    ((unknownStatus['dst'] as List<Object?>).first
            as Map<String, Object?>)['tax_status'] =
        'unexpected_server_status';
    expect(
      () => TaxEvidenceOverview.fromPayload(unknownStatus),
      throwsA(isA<SpinaApiException>()),
    );
    final source = TaxEvidenceOverview.fromPayload(
      _overview(),
    ).percentageTax.single;
    await expectLater(
      repository.recordPercentage(
        _session,
        deviceId: 'management-device',
        source: source,
        draft: const PercentageTaxEvidenceDraft(
          ruleEvidenceId: _percentageRuleId,
          taxableLendingReceiptAmount: '99.00',
          principalReceiptAmount: '400.00',
          expectedTaxDue: '5.00',
          allocationReference: 'Receipt allocation 2001',
          allocationDigest: _digest,
          managementRationale:
              'Reviewed the exact protected cash allocation and current tax rule.',
        ),
        idempotencyKey: _retryId,
      ),
      throwsArgumentError,
    );
    expect(calls, 0);
  });
}

TaxRuleEvidenceDraft _ruleDraft({
  String treatment = 'taxable',
  required String rate,
}) => TaxRuleEvidenceDraft(
  taxType: 'documentary_stamp_tax',
  ruleKey: 'dst-current',
  effectiveFrom: '2026-08-30',
  effectiveTo: null,
  treatment: treatment,
  rate: rate,
  maturityMaxDays: 365,
  legalSource: 'Current retained legal source',
  legalReference: 'Current retained legal reference',
  retainedSourceReference: 'legal/dst/2026-08-30.pdf',
  evidenceDigest: _digest,
  managementRationale:
      'Reviewed the exact retained tax rule and current legal evidence.',
  supersedesRuleId: null,
);

http.Response _response(Map<String, Object?> data, {int statusCode = 200}) =>
    http.Response(
      jsonEncode(<String, Object?>{'success': true, 'data': data}),
      statusCode,
      headers: const <String, String>{'content-type': 'application/json'},
    );

Map<String, Object?> _overview() => <String, Object?>{
  'summary': <String, Object>{
    'rule_evidence_count': 1,
    'dst_source_count': 1,
    'dst_ready_count': 0,
    'dst_blocked_count': 1,
    'dst_evidence_tax_total': '0.00',
    'percentage_source_count': 1,
    'percentage_ready_count': 0,
    'percentage_blocked_count': 1,
    'percentage_taxable_receipt_total': '0.00',
    'percentage_evidence_tax_total': '0.00',
    'evidence_backed_tax_readiness_enabled': true,
    'tax_posting_enabled': false,
    'automatic_source_posting': false,
  },
  'rules': <Object?>[
    <String, Object?>{
      'id': _ruleId,
      'tax_type': 'documentary_stamp_tax',
      'rule_key': 'dst-current',
      'rule_version': 1,
      'effective_from': '2026-08-30',
      'effective_to': null,
      'treatment': 'taxable',
      'rate': '0.0075000000',
      'maturity_max_days': 365,
      'legal_source': 'Republic Act 12214',
      'legal_reference': 'Section 21',
      'retained_source_reference': 'legal/dst.pdf',
      'evidence_digest': _digest,
      'management_rationale': 'Approved current retained legal evidence.',
      'supersedes_rule_id': null,
      'recorded_by_user_id': _actorId,
      'recorded_at': '2026-08-30T01:00:00+00:00',
    },
    <String, Object?>{
      'id': _percentageRuleId,
      'tax_type': 'percentage_tax_lending',
      'rule_key': 'percentage-current',
      'rule_version': 1,
      'effective_from': '2026-08-30',
      'effective_to': null,
      'treatment': 'taxable',
      'rate': '0.0500000000',
      'maturity_max_days': null,
      'legal_source': 'BIR guidance',
      'legal_reference': 'Percentage tax guidance',
      'retained_source_reference': 'legal/percentage.pdf',
      'evidence_digest': _otherDigest,
      'management_rationale': 'Approved current retained legal evidence.',
      'supersedes_rule_id': null,
      'recorded_by_user_id': _actorId,
      'recorded_at': '2026-08-30T01:00:00+00:00',
    },
  ],
  'dst': <Object?>[
    <String, Object?>{
      'loan_id': _loanId,
      'client_id': _clientId,
      'disbursement_event_id': _disbursementId,
      'issue_date': '2026-08-30',
      'protected_issue_price': '10000.00',
      'protected_term_days': 90,
      'evidence_id': null,
      'evidence_version': null,
      'rule_evidence_id': null,
      'tax_due': null,
      'calculation_digest': null,
      'tax_status': 'evidence_required',
      'tax_blocker': 'Retained DST evidence is required.',
      'tax_posting_enabled': false,
      'automatic_source_posting': false,
    },
  ],
  'percentage_tax': <Object?>[
    <String, Object?>{
      'transaction_id': _transactionId,
      'loan_id': _loanId,
      'client_id': _clientId,
      'collection_date': '2026-08-30',
      'entry_type': 'payment',
      'source_cash_amount': '500.00',
      'is_voided': false,
      'evidence_id': null,
      'evidence_version': null,
      'rule_evidence_id': null,
      'taxable_lending_receipt_amount': null,
      'principal_receipt_amount': null,
      'tax_due': null,
      'allocation_digest': null,
      'tax_status': 'allocation_evidence_required',
      'tax_blocker': 'Retained allocation evidence is required.',
      'tax_posting_enabled': false,
      'automatic_source_posting': false,
    },
  ],
  'permissions': <String, Object>{
    'rule_evidence_record': true,
    'dst_evidence_record': true,
    'percentage_evidence_record': true,
  },
  'readiness': 'blocked',
  'limit': 50,
  'offset': 10,
  'evidence_backed_tax_readiness_enabled': true,
  'tax_posting_enabled': false,
  'automatic_source_posting': false,
  'notice': 'Exact retained tax evidence is required.',
};

const _session = UserSession(
  userId: 'management-1',
  username: 'manager',
  displayName: 'Management',
  role: AppRole.management,
  rawRole: 'Management',
  accessToken: 'management-token',
  permissions: <String>[
    'accounting.tax.rule_evidence.record',
    'accounting.tax.dst_evidence.record',
    'accounting.tax.percentage_evidence.record',
  ],
);
const _retryId = '11111111-1111-4111-8111-111111111111';
const _secondRetryId = '11111111-1111-4111-8111-111111111112';
const _ruleId = '22222222-2222-4222-8222-222222222222';
const _percentageRuleId = '22222222-2222-4222-8222-222222222223';
const _dstEvidenceId = '33333333-3333-4333-8333-333333333333';
const _percentageEvidenceId = '33333333-3333-4333-8333-333333333334';
const _loanId = '44444444-4444-4444-8444-444444444444';
const _clientId = '55555555-5555-4555-8555-555555555555';
const _disbursementId = '66666666-6666-4666-8666-666666666666';
const _transactionId = '77777777-7777-4777-8777-777777777777';
const _actorId = '88888888-8888-4888-8888-888888888888';
const _digest =
    'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa';
const _otherDigest =
    'bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb';
