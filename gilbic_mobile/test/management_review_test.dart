import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gilbic_mobile/src/features/management/review/management_review.dart';

void main() {
  group('plainManagementStatus', () {
    const known = <String, String>{'pending': 'Waiting for Management review'};

    test('translates a known server status without changing its meaning', () {
      expect(
        plainManagementStatus(' PENDING ', known),
        'Waiting for Management review',
      );
    });

    test('keeps missing and unknown server status neutral', () {
      expect(plainManagementStatus(null, known), 'Not provided by the server');
      expect(
        plainManagementStatus('future_state', known),
        'Status needs review',
      );
    });
  });

  test('review validation rejects blank facts and enabled blockers', () {
    expect(() => _review(recordValue: '   '), throwsA(isA<ArgumentError>()));
    expect(
      () => _review(
        warnings: const <ManagementReviewWarning>[
          ManagementReviewWarning(
            severity: ManagementReviewWarningSeverity.blocker,
            message: 'The server says this action is unavailable.',
          ),
        ],
      ),
      throwsA(isA<ArgumentError>()),
    );
  });

  testWidgets('panel explains the full review in operational reading order', (
    tester,
  ) async {
    final review = _review();

    await tester.pumpWidget(_app(ManagementReviewPanel(review: review)));

    expect(
      find.byKey(const Key('management-review-collection-void')),
      findsOneWidget,
    );
    const headings = <String>[
      'Reviewing',
      'Current status',
      'Check before continuing',
      'Next action',
      'If confirmed',
    ];
    var previousY = -1.0;
    for (final heading in headings) {
      final finder = find.text(heading);
      expect(finder, findsOneWidget);
      final y = tester.getTopLeft(finder).dy;
      expect(y, greaterThan(previousY), reason: heading);
      previousY = y;
    }

    expect(find.text('OR-2026-0042 • Maria Santos'), findsOneWidget);
    expect(find.text('Eligible for protected correction'), findsOneWidget);
    expect(find.text('Server status: unlocked_unremitted'), findsOneWidget);
    expect(find.text('₱500.00'), findsOneWidget);
    expect(find.text('Transaction reference'), findsOneWidget);
    expect(find.text('txn-42'), findsOneWidget);
    expect(
      find.bySemanticsLabel('Caution: The client balance will be restored.'),
      findsOneWidget,
    );
  });

  testWidgets('panel states when the server supplied no warnings', (
    tester,
  ) async {
    await tester.pumpWidget(
      _app(ManagementReviewPanel(review: _review(warnings: const []))),
    );

    expect(find.text('No server warnings'), findsOneWidget);
  });

  testWidgets('confirmation returns only the explicit Management choice', (
    tester,
  ) async {
    await tester.pumpWidget(_confirmationHarness(_review()));

    await tester.tap(find.text('Open review'));
    await tester.pumpAndSettle();
    expect(find.text('Void this collection'), findsWidgets);
    expect(
      find.text(
        'The receipt will be voided, the client balance will be restored, and permanent audit evidence will remain.',
      ),
      findsOneWidget,
    );

    await tester.tap(find.byKey(const Key('cancel-collection-void')));
    await tester.pumpAndSettle();
    expect(find.text('Result: cancelled'), findsOneWidget);

    await tester.tap(find.text('Open review'));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('confirm-collection-void')));
    await tester.pumpAndSettle();
    expect(find.text('Result: confirmed'), findsOneWidget);
  });

  testWidgets('blocking server warning disables the final confirmation', (
    tester,
  ) async {
    final blocked = _review(
      actionEnabled: false,
      warnings: const <ManagementReviewWarning>[
        ManagementReviewWarning(
          severity: ManagementReviewWarningSeverity.blocker,
          message: 'The collection is already part of a remittance.',
        ),
      ],
    );
    await tester.pumpWidget(_confirmationHarness(blocked));

    await tester.tap(find.text('Open review'));
    await tester.pumpAndSettle();

    final button = tester.widget<FilledButton>(
      find.byKey(const Key('confirm-collection-void')),
    );
    expect(button.onPressed, isNull);
    expect(
      find.bySemanticsLabel(
        'Blocker: The collection is already part of a remittance.',
      ),
      findsOneWidget,
    );
  });

  testWidgets('review stays reachable on a small phone with larger text', (
    tester,
  ) async {
    await tester.binding.setSurfaceSize(const Size(360, 640));
    addTearDown(() async => tester.binding.setSurfaceSize(null));

    await tester.pumpWidget(
      MaterialApp(
        builder: (context, child) => MediaQuery(
          data: MediaQuery.of(
            context,
          ).copyWith(textScaler: const TextScaler.linear(1.3)),
          child: child!,
        ),
        home: Scaffold(
          body: SingleChildScrollView(
            child: ManagementReviewPanel(review: _review()),
          ),
        ),
      ),
    );

    await tester.scrollUntilVisible(
      find.text('If confirmed'),
      200,
      scrollable: find.byType(Scrollable),
    );
    expect(find.text('If confirmed'), findsOneWidget);
    expect(tester.takeException(), isNull);
  });

  testWidgets(
    'confirmation dialog keeps both decisions reachable on a small phone',
    (tester) async {
      await tester.binding.setSurfaceSize(const Size(360, 640));
      addTearDown(() async => tester.binding.setSurfaceSize(null));

      await tester.pumpWidget(
        MaterialApp(
          builder: (context, child) => MediaQuery(
            data: MediaQuery.of(
              context,
            ).copyWith(textScaler: const TextScaler.linear(1.3)),
            child: child!,
          ),
          home: _ConfirmationHarness(review: _review()),
        ),
      );

      await tester.tap(find.text('Open review'));
      await tester.pumpAndSettle();

      expect(find.byKey(const Key('cancel-collection-void')), findsOneWidget);
      expect(find.byKey(const Key('confirm-collection-void')), findsOneWidget);
      expect(tester.takeException(), isNull);
      await tester.tap(find.byKey(const Key('cancel-collection-void')));
      await tester.pumpAndSettle();
      expect(find.text('Result: cancelled'), findsOneWidget);
    },
  );
}

ManagementReviewPresentation _review({
  String recordValue = 'OR-2026-0042 • Maria Santos',
  List<ManagementReviewWarning> warnings = const <ManagementReviewWarning>[
    ManagementReviewWarning(
      severity: ManagementReviewWarningSeverity.caution,
      message: 'The client balance will be restored.',
    ),
  ],
  bool actionEnabled = true,
}) {
  return ManagementReviewPresentation.validated(
    surface: ManagementMutationSurface.collectionVoid,
    recordLabel: 'Official receipt',
    recordValue: recordValue,
    statusLabel: 'Eligible for protected correction',
    statusDetail: 'Server status: unlocked_unremitted',
    facts: const <ManagementReviewFact>[
      ManagementReviewFact(label: 'Amount', value: '₱500.00'),
    ],
    warnings: warnings,
    nextActionLabel: 'Void this collection',
    consequence:
        'The receipt will be voided, the client balance will be restored, and permanent audit evidence will remain.',
    risk: ManagementReviewRisk.protectedFinancial,
    secondaryReferences: const <ManagementReviewFact>[
      ManagementReviewFact(label: 'Transaction reference', value: 'txn-42'),
    ],
    actionEnabled: actionEnabled,
  );
}

Widget _app(Widget child) {
  return MaterialApp(
    home: Scaffold(body: SingleChildScrollView(child: child)),
  );
}

Widget _confirmationHarness(ManagementReviewPresentation review) {
  return MaterialApp(home: _ConfirmationHarness(review: review));
}

class _ConfirmationHarness extends StatefulWidget {
  const _ConfirmationHarness({required this.review});

  final ManagementReviewPresentation review;

  @override
  State<_ConfirmationHarness> createState() => _ConfirmationHarnessState();
}

class _ConfirmationHarnessState extends State<_ConfirmationHarness> {
  String? _result;

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: Column(
        children: <Widget>[
          FilledButton(
            onPressed: () async {
              final confirmed = await showManagementReviewConfirmation(
                context,
                widget.review,
              );
              if (!mounted) return;
              setState(() => _result = confirmed ? 'confirmed' : 'cancelled');
            },
            child: const Text('Open review'),
          ),
          if (_result != null) Text('Result: $_result'),
        ],
      ),
    );
  }
}
