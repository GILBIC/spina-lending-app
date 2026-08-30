import 'dart:convert';

import 'package:flutter_test/flutter_test.dart';
import 'package:gilbic_mobile/src/core/auth/app_role.dart';
import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/management/tax_liability.dart';
import 'package:gilbic_mobile/src/core/management/tax_liability_repository.dart';
import 'package:gilbic_mobile/src/core/network/spina_api.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

void main() {
  test('loads exact protected tax-liability queue and coordinates', () async {
    late http.Request request;
    final repository = SpinaTaxLiabilityRepository(
      client: MockClient((incoming) async {
        request = incoming;
        return _response(_overview(items: <Object?>[_item('evidence_ready')]));
      }),
    );

    final overview = await repository.load(
      _session,
      deviceId: 'management-device',
      accountingStatus: 'ready',
      limit: 25,
      offset: 5,
    );

    expect(
      request.url.path,
      '/api/mobile/v1/management/financial-accounting/tax/liabilities',
    );
    expect(request.url.queryParameters, <String, String>{
      'accounting_status': 'ready',
      'limit': '25',
      'offset': '5',
    });
    expect(overview.summary.readyToPrepareCount, 1);
    expect(overview.items.single.taxDue, '75.00');
    expect(overview.protectedTaxLiabilityPostingEnabled, isTrue);
  });

  test('prepares only exact evidence-ready liability', () async {
    late http.Request request;
    late Map<String, dynamic> body;
    final repository = SpinaTaxLiabilityRepository(
      client: MockClient((incoming) async {
        request = incoming;
        body = jsonDecode(incoming.body) as Map<String, dynamic>;
        return _itemResponse(_item('prepared_not_posted'));
      }),
    );
    final item = TaxLiabilityItem.fromPayload(_item('evidence_ready'));

    final result = await repository.prepare(
      _session,
      deviceId: 'management-device',
      item: item,
    );

    expect(
      request.url.path,
      '/api/mobile/v1/management/financial-accounting/tax/liabilities/'
      'documentary_stamp_tax/22222222-2222-4222-8222-222222222222/prepare',
    );
    expect(body, <String, Object>{'confirm': true});
    expect(result.accountingStatus, 'prepared_not_posted');
  });

  test('posts exact prepared tax-liability coordinates', () async {
    late Map<String, dynamic> body;
    final repository = SpinaTaxLiabilityRepository(
      client: MockClient((incoming) async {
        body = jsonDecode(incoming.body) as Map<String, dynamic>;
        return _itemResponse(_item('posted'));
      }),
    );
    final item = TaxLiabilityItem.fromPayload(_item('prepared_not_posted'));

    final result = await repository.post(
      _session,
      deviceId: 'management-device',
      item: item,
      confirmationToken: _token,
    );

    expect(body, <String, Object>{
      'confirm': true,
      'confirmation_token': _token,
      'expected_evidence_digest': _digest,
      'expected_tax_due': '75.00',
      'expected_expense_account_code': '5310',
      'expected_tax_payable_account_code': '2100',
      'expected_posting_date': '2026-08-30',
      'expected_fiscal_period_id': _periodId,
    });
    expect(result.entryNumber, 'GJ-2026-0020');
  });

  test('rejects incomplete coordinates and unsafe policy before I/O', () async {
    var calls = 0;
    final repository = SpinaTaxLiabilityRepository(
      client: MockClient((_) async {
        calls += 1;
        return _itemResponse(_item('posted'));
      }),
    );
    final incomplete = _item('prepared_not_posted')
      ..['fiscal_period_id'] = null;
    final unsafe = _overview(items: const <Object?>[])
      ..['automatic_source_posting'] = true;
    expect(
      () => TaxLiabilityItem.fromPayload(incomplete),
      throwsA(isA<SpinaApiException>()),
    );
    expect(
      () => TaxLiabilityOverview.fromPayload(unsafe),
      throwsA(isA<SpinaApiException>()),
    );
    final unknownStatus = _item('unexpected_server_status');
    expect(
      () => TaxLiabilityItem.fromPayload(unknownStatus),
      throwsA(isA<SpinaApiException>()),
    );
    await expectLater(
      repository.post(
        _session,
        deviceId: 'management-device',
        item: TaxLiabilityItem.fromPayload(_item('prepared_not_posted')),
        confirmationToken: 'bad-token',
      ),
      throwsArgumentError,
    );
    expect(calls, 0);
  });
}

http.Response _response(Map<String, Object?> data) => http.Response(
  jsonEncode(<String, Object?>{'success': true, 'data': data}),
  200,
  headers: const <String, String>{'content-type': 'application/json'},
);

http.Response _itemResponse(Map<String, Object?> item) =>
    _response(<String, Object?>{'item': item});

Map<String, Object?> _overview({required List<Object?> items}) =>
    <String, Object?>{
      'summary': <String, Object>{
        'evidence_item_count': items.length,
        'ready_to_prepare_count': items
            .where(
              (item) =>
                  (item as Map<String, Object?>)['accounting_status'] ==
                  'evidence_ready',
            )
            .length,
        'prepared_count': 0,
        'posted_count': 0,
        'no_liability_required_count': 0,
        'adjusted_posting_count': 0,
        'covered_replacement_count': 0,
        'blocked_or_adjustment_review_count': 0,
        'posted_tax_liability_total': '0.00',
        'protected_tax_liability_posting_enabled': true,
        'tax_settlement_enabled': true,
        'tax_adjustment_reversal_enabled': true,
        'automatic_source_posting': false,
      },
      'items': items,
      'permissions': <String, Object>{
        'liability_prepare': true,
        'liability_post': true,
      },
      'accounting_status': 'ready',
      'limit': 25,
      'offset': 5,
      'protected_tax_liability_posting_enabled': true,
      'tax_settlement_enabled': true,
      'tax_adjustment_reversal_enabled': true,
      'automatic_source_posting': false,
      'notice': 'Exact current tax evidence and confirmation are required.',
    };

Map<String, Object?> _item(String status) {
  final prepared = status == 'prepared_not_posted' || status == 'posted';
  final posted = status == 'posted';
  return <String, Object?>{
    'tax_type': 'documentary_stamp_tax',
    'evidence_id': _evidenceId,
    'evidence_version': 1,
    'source_id': _sourceId,
    'loan_id': _loanId,
    'client_id': _clientId,
    'recognition_date': '2026-08-30',
    'tax_due': '75.00',
    'evidence_digest': _digest,
    'evidence_status': 'evidence_ready',
    'evidence_blocker': null,
    'expense_account_code': '5310',
    'expense_account_name': 'Documentary Stamp Tax Expense',
    'tax_payable_account_code': '2100',
    'tax_payable_account_name': 'Tax Payables',
    'preparation_id': prepared ? _preparationId : null,
    'journal_entry_id': prepared ? _journalId : null,
    'journal_status': prepared ? (posted ? 'posted' : 'draft') : null,
    'entry_number': posted ? 'GJ-2026-0020' : null,
    'fiscal_period_id': prepared ? _periodId : null,
    'prepared_by_user_id': prepared ? _actorId : null,
    'prepared_at': prepared ? '2026-08-30T02:00:00+00:00' : null,
    'posting_id': posted ? _postingId : null,
    'confirmation_digest': posted ? _confirmationDigest : null,
    'posted_by_user_id': posted ? _actorId : null,
    'posted_at': posted ? '2026-08-30T02:10:00+00:00' : null,
    'accounting_status': status,
    'accounting_blocker': null,
    'protected_tax_liability_posting_enabled': true,
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
    'accounting.tax.liability.prepare',
    'accounting.tax.liability.post',
  ],
);
const _evidenceId = '22222222-2222-4222-8222-222222222222';
const _sourceId = '33333333-3333-4333-8333-333333333333';
const _loanId = '44444444-4444-4444-8444-444444444444';
const _clientId = '55555555-5555-4555-8555-555555555555';
const _preparationId = '66666666-6666-4666-8666-666666666666';
const _journalId = '77777777-7777-4777-8777-777777777777';
const _periodId = '88888888-8888-4888-8888-888888888888';
const _postingId = '99999999-9999-4999-8999-999999999999';
const _actorId = 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa';
const _digest =
    'bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb';
const _confirmationDigest =
    'cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc';
const _token =
    'dddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd';
