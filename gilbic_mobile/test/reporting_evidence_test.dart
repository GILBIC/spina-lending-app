import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gilbic_mobile/src/core/management/reporting_evidence.dart';
import 'package:gilbic_mobile/src/features/management/reporting_supplement_card.dart';
import 'support/reporting_fixture.dart';
import 'journal_disclosure_evidence_test.dart' show disclosureContract;

void main() {
  testWidgets('full mixed disclosure replaces the old cashless inventory', (
    tester,
  ) async {
    final data = reportingTestSupplement()
      ..['journal_disclosures'] = disclosureContract();
    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: SingleChildScrollView(
            child: ReportingSupplementCard(supplement: data),
          ),
        ),
      ),
    );
    expect(find.text('Cash and noncash disclosure review'), findsOneWidget);
    expect(find.text('Journals with no cash movement'), findsNothing);
  });
  test(
    'cash allocations retain signed cents and must cover the exact line',
    () {
      final splits = [
        {'category': 'operating', 'amount': '-40.00'},
        {'category': 'financing', 'amount': '-60.00'},
      ];
      expect(validateCashAllocations(splits, '-100.00'), splits);
      expect(
        () => validateCashAllocations([
          {'category': 'operating', 'amount': '100.00'},
        ], '-100.00'),
        throwsFormatException,
      );
      expect(
        () => validateCashAllocations([
          {'category': 'operating', 'amount': '-99.99'},
        ], '-100.00'),
        throwsFormatException,
      );
      expect(
        () => validateCashAllocations([
          {'category': 'operating', 'amount': '-100.001'},
        ], '-100.00'),
        throwsFormatException,
      );
    },
  );
  testWidgets(
    'unknown cash remains unavailable and exact equity is preserved',
    (tester) async {
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: SingleChildScrollView(
              child: ReportingSupplementCard(
                supplement: reportingTestSupplement(),
              ),
            ),
          ),
        ),
      );
      expect(find.text('Statement of Changes in Equity'), findsOneWidget);
      expect(
        find.text('Opening equity: PHP 90071992547409.93'),
        findsOneWidget,
      );
      expect(find.text('Opening cash: Unavailable'), findsOneWidget);
      expect(find.text('Net cash flow: Unavailable'), findsOneWidget);
      expect(find.text('Net cash flow: PHP 0.00'), findsNothing);
      expect(find.text('No comparative period returned.'), findsOneWidget);
    },
  );
  test('missing supplemental fields fail closed', () {
    expect(() => validateReportingSupplement({}), throwsFormatException);
  });
  testWidgets('changed cash definition never displays invented cash totals', (
    tester,
  ) async {
    final data = reportingTestSupplement(withPolicy: true);
    final cash = data['cash_flows'] as Map<String, dynamic>;
    (cash['policy'] as Map<String, dynamic>)['cash_definition_valid'] = false;
    cash['status'] = 'cash_definition_changed';
    for (final key in [
      'opening_cash',
      'closing_cash',
      'net_cash_flow',
      'reconciliation_difference',
      'opening_balance_adjustments',
    ]) {
      cash[key] = null;
    }
    cash['categories'] = <String, dynamic>{};
    cash['cash_lines'] = <Map<String, dynamic>>[];
    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: SingleChildScrollView(
            child: ReportingSupplementCard(
              supplement: validateReportingSupplement(data),
            ),
          ),
        ),
      ),
    );
    expect(
      find.text('Cash definition changed; review a new policy.'),
      findsOneWidget,
    );
    expect(find.text('Opening cash: Unavailable'), findsOneWidget);
    expect(find.text('Net cash flow: Unavailable'), findsOneWidget);
    expect(find.text('Net cash flow: PHP 0.00'), findsNothing);
    cash['net_cash_flow'] = '0.00';
    expect(() => validateReportingSupplement(data), throwsFormatException);
  });
}
