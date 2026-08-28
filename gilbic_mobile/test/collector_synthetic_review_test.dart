import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gilbic_mobile/src/features/collector/collector_synthetic_review_page.dart';
import 'package:gilbic_mobile/src/theme/spina_theme.dart';

void main() {
  testWidgets(
    'CA4 review keeps area ledger combined payment and all-area master review',
    (tester) async {
      await tester.binding.setSurfaceSize(const Size(430, 1100));
      addTearDown(() => tester.binding.setSurfaceSize(null));

      await tester.pumpWidget(
        MaterialApp(
          theme: SpinaTheme.light,
          home: const CollectorSyntheticReviewPage(),
        ),
      );
      await tester.pumpAndSettle();

      expect(find.text('Daily Collection'), findsOneWidget);
      expect(find.text('Area arrangement'), findsOneWidget);
      expect(find.text('1  BALAYONG'), findsOneWidget);
      expect(find.text('2  CALAHAN'), findsOneWidget);
      expect(find.text('3  SAN ROQUE'), findsOneWidget);
      expect(find.text('AREA: BALAYONG'), findsOneWidget);
      expect(find.text('Ana Dela Cruz'), findsOneWidget);
      expect(find.text('MISSED 1'), findsOneWidget);

      await tester.tap(find.byKey(const Key('synthetic-client-bal-ana')));
      await tester.pumpAndSettle();
      expect(find.textContaining('Pays at 5:30 PM'), findsOneWidget);
      expect(find.textContaining('Usually sends exact'), findsOneWidget);

      await tester.tap(find.byKey(const Key('synthetic-collect-bal-ana')));
      await tester.pumpAndSettle();
      expect(
        find.byKey(const Key('synthetic-client-payment-amount')),
        findsOneWidget,
      );
      expect(find.text('Automatic split preview'), findsOneWidget);
      expect(find.textContaining('Regular due ₱100.00'), findsOneWidget);
      expect(find.textContaining('7x7 due ₱50.00'), findsOneWidget);
      expect(find.textContaining('₱150.00'), findsWidgets);
      expect(
        tester.getTopLeft(find.text('7x7 due ₱50.00')).dy,
        lessThan(tester.getTopLeft(find.text('Regular due ₱100.00')).dy),
      );

      await tester.enterText(
        find.byKey(const Key('synthetic-client-payment-amount')),
        '30',
      );
      await tester.pump();
      expect(find.text('₱30.00'), findsWidgets);
      expect(find.text('₱0.00'), findsOneWidget);

      await tester.enterText(
        find.byKey(const Key('synthetic-client-payment-amount')),
        '150',
      );
      await tester.pump();

      await tester.tap(find.byKey(const Key('synthetic-confirm-payment')));
      await tester.pumpAndSettle();
      expect(find.textContaining('no payment was saved'), findsOneWidget);

      await tester.tap(find.text('Master review'));
      await tester.pumpAndSettle();
      expect(find.text('Master Review'), findsOneWidget);
      expect(find.text('All-area collection check'), findsOneWidget);
      expect(find.text('Area completion'), findsOneWidget);
      expect(find.text('Who still needs action'), findsOneWidget);
      expect(find.text('Maria Lopez'), findsOneWidget);
      expect(find.textContaining('Missed 1 payment'), findsOneWidget);
      expect(find.text('Joy Villanueva'), findsOneWidget);
      expect(find.textContaining('Missed 2 payments'), findsOneWidget);
      expect(find.text('Cora Garcia'), findsOneWidget);
      expect(
        find.text('GCash: Pays every collection day by GCash.'),
        findsOneWidget,
      );
    },
  );
}
