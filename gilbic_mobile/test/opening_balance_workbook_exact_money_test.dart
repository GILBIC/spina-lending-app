import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gilbic_mobile/src/core/auth/app_role.dart';
import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/device/device_identity.dart';
import 'package:gilbic_mobile/src/core/management/opening_balance_workbook_repository.dart';
import 'package:gilbic_mobile/src/features/management/management_opening_balance_workbook_page.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

const _session = UserSession(
  userId: 'manager',
  username: 'manager',
  displayName: 'Manager',
  role: AppRole.management,
  rawRole: 'Management',
  accessToken: 'test-token',
  permissions: ['accounting.cutover.manage'],
);

void main() {
  testWidgets('workbook credit retains maximum supported cents on the wire', (
    tester,
  ) async {
    final writes = <Map<String, dynamic>>[];
    await _mount(tester, amount: null, writes: writes);
    await tester.tap(find.byKey(const Key('edit-opening-workbook-line-1020')));
    await tester.pumpAndSettle();
    await tester.enterText(
      find.byKey(const Key('opening-line-credit')),
      '9999999999999999.99',
    );
    await tester.tap(find.byKey(const Key('save-opening-workbook-line')));
    await tester.pumpAndSettle();
    expect(find.text('Credit ₱9,999,999,999,999,999.99'), findsOneWidget);
    await tester.tap(find.byKey(const Key('confirm-opening-workbook')));
    await tester.pumpAndSettle();
    expect(writes, [
      {
        'debit': null,
        'credit': '9999999999999999.99',
        'verification_status': 'pending',
        'evidence_note': null,
      },
    ]);
  });
  for (final amount in ['10000000000000000.00', '1.001', '-1.00', 'NaN']) {
    testWidgets(
      'invalid workbook amount $amount cannot reach confirmation or HTTP',
      (tester) async {
        final writes = <Map<String, dynamic>>[];
        await _mount(tester, amount: null, writes: writes);
        await tester.tap(
          find.byKey(const Key('edit-opening-workbook-line-1020')),
        );
        await tester.pumpAndSettle();
        await tester.enterText(
          find.byKey(const Key('opening-line-debit')),
          amount,
        );
        await tester.tap(find.byKey(const Key('save-opening-workbook-line')));
        await tester.pumpAndSettle();
        expect(find.byKey(const Key('opening-line-debit')), findsOneWidget);
        expect(find.byKey(const Key('confirm-opening-workbook')), findsNothing);
        expect(writes, isEmpty);
      },
    );
  }
  for (final amount in [
    '1000000000000000.01',
    '9999999999999999.99',
    '200.01',
    '0.00',
  ]) {
    for (final prefilled in [false, true]) {
      testWidgets(
        'workbook ${prefilled ? "prefill" : "entry"} saves exact $amount on the wire',
        (tester) async {
          final writes = <Map<String, dynamic>>[];
          await _mount(
            tester,
            amount: prefilled ? amount : null,
            writes: writes,
          );
          await tester.tap(
            find.byKey(const Key('edit-opening-workbook-line-1020')),
          );
          await tester.pumpAndSettle();
          final debit = find.byKey(const Key('opening-line-debit'));
          if (prefilled) {
            expect(tester.widget<TextField>(debit).controller!.text, amount);
          } else {
            await tester.enterText(debit, amount);
          }
          await tester.tap(find.byKey(const Key('save-opening-workbook-line')));
          await tester.pumpAndSettle();
          expect(writes, isEmpty);
          await tester.tap(find.byKey(const Key('confirm-opening-workbook')));
          await tester.pumpAndSettle();
          expect(writes, [
            <String, dynamic>{
              'debit': amount,
              'credit': null,
              'verification_status': 'pending',
              'evidence_note': null,
            },
          ]);
        },
      );
    }
  }
  testWidgets(
    'canceled workbook review sends no write and preserves loaded cents',
    (tester) async {
      final writes = <Map<String, dynamic>>[];
      await _mount(tester, amount: '1000000000000000.01', writes: writes);
      for (var attempt = 0; attempt < 2; attempt++) {
        await tester.tap(
          find.byKey(const Key('edit-opening-workbook-line-1020')),
        );
        await tester.pumpAndSettle();
        expect(
          tester
              .widget<TextField>(find.byKey(const Key('opening-line-debit')))
              .controller!
              .text,
          '1000000000000000.01',
        );
        await tester.enterText(
          find.byKey(const Key('opening-line-debit')),
          '200.01',
        );
        await tester.tap(find.byKey(const Key('save-opening-workbook-line')));
        await tester.pumpAndSettle();
        await tester.tap(find.byKey(const Key('cancel-opening-workbook')));
        await tester.pumpAndSettle();
        expect(writes, isEmpty);
      }
    },
  );
}

Future<void> _mount(
  WidgetTester tester, {
  required String? amount,
  required List<Map<String, dynamic>> writes,
}) async {
  await tester.binding.setSurfaceSize(const Size(900, 1600));
  addTearDown(() async => tester.binding.setSurfaceSize(null));
  final client = MockClient((request) async {
    if (request.method == 'PUT') {
      writes.add(jsonDecode(request.body) as Map<String, dynamic>);
    }
    return http.Response(jsonEncode(_payload(amount)), 200);
  });
  addTearDown(client.close);
  await tester.pumpWidget(
    MaterialApp(
      home: ManagementOpeningBalanceWorkbookPage(
        session: _session,
        repository: SpinaOpeningBalanceWorkbookRepository(client: client),
        deviceIdentityProvider: DeviceIdentityProvider(
          store: MemoryDeviceIdentityStore()..value = 'device',
          platformResolver: () => 'android',
          appVersionResolver: () async => 'test',
        ),
      ),
    ),
  );
  await tester.pumpAndSettle();
}

Map<String, dynamic> _payload(String? debit) => {
  'management_enabled': true,
  'notice': 'Workbook does not post.',
  'summary': {
    'workbook_id': 'workbook-1',
    'cutover_date': '2026-08-08',
    'status': 'draft',
    'line_count': 1,
    'source_reference_count': 1,
    'verified_line_count': 0,
    'pending_line_count': 1,
    'profit_loss_policy_confirmed': false,
    'profit_loss_policy_note': null,
    'total_debit': debit ?? '0.00',
    'total_credit': '0.00',
    'balance_variance': debit ?? '0.00',
    'worksheet_balanced': false,
    'ready_for_review': false,
    'ready_to_post': false,
    'opening_balance_posting_enabled': false,
    'automatic_source_posting_enabled': false,
  },
  'lines': [
    {
      'workbook_id': 'workbook-1',
      'account_code': '1020',
      'system_key': 'cash_collector_custody',
      'account_name': 'Cash - Collector Custody',
      'account_type': 'asset',
      'normal_balance': 'debit',
      'source_reference_amount': '200.00',
      'source_basis': 'collection_custody_reference',
      'requirement_type': 'reconciliation_required',
      'guidance': 'Reconcile to physical collector cash.',
      'proposed_debit': debit,
      'proposed_credit': null,
      'verification_status': 'pending',
      'evidence_note': null,
      'measurement_reference_amount': null,
      'measurement_status': null,
      'measurement_note': null,
    },
  ],
  'measurement': {
    'notice': 'Reference only.',
    'loans': [],
    'summary': {
      'active_loan_count': 0,
      'measured_loan_count': 0,
      'review_required_count': 0,
      'actual_cash_received': '0.00',
      'effective_interest_income': '0.00',
      'regular_loan_component': '0.00',
      'seven_by_seven_loan_component': '0.00',
      'accrued_interest_component': '0.00',
      'gross_carrying_amount': '0.00',
      'measurement_status': 'measured',
      'measurement_policy_version': 'eir_cutover_v1',
      'ecl_included': false,
      'ready_to_post': false,
    },
  },
};
