import 'support/android_workflow_capture.dart';
import 'package:flutter/material.dart';
import 'package:flutter/rendering.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gilbic_mobile/src/core/auth/app_role.dart';
import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/collector/collector_route.dart';
import 'package:gilbic_mobile/src/core/device/device_identity.dart';
import 'package:gilbic_mobile/src/core/network/spina_api.dart';
import 'package:gilbic_mobile/src/core/payments/collection_device_sequence.dart';
import 'package:gilbic_mobile/src/core/payments/payment_submission.dart';
import 'package:gilbic_mobile/src/core/payments/payment_submission_repository.dart';
import 'package:gilbic_mobile/src/features/collector/collection_entry_page.dart';
import 'support/android_role_fixture.dart';
import 'support/android_readability_capture.dart';

void main() {
  for (final (amount, intent) in [
    ('100.01', PaymentAllocationIntent.scheduled),
    ('300.01', PaymentAllocationIntent.extraAsAdvance),
  ]) {
    testWidgets(
      'A8 single short extra ADV exact $amount with keyboard and Back',
      (tester) async {
        final repository = _CaptureRepository();
        await pumpAndroidRoleFixture(
          tester,
          size: const Size(320, 640),
          textScaler: TextScaler.linear(2),
          viewInsets: const EdgeInsets.only(bottom: 220),
          home: Scaffold(
            body: Builder(
              builder: (context) => FilledButton(
                onPressed: () => Navigator.of(context).push(
                  MaterialPageRoute<void>(
                    builder: (_) => CollectionEntryPage(
                      session: _session,
                      entry: _regularEntry,
                      repository: repository,
                      deviceIdentityProvider: _deviceIdentityProvider(),
                      deviceSequence: MemoryCollectionDeviceSequence(),
                      collectionDate: DateTime(2026, 8, 1),
                    ),
                  ),
                ),
                child: const Text('Open synthetic collection'),
              ),
            ),
          ),
        );
        await tester.pumpAndSettle();
        await tester.tap(find.text('Open synthetic collection'));
        await tester.pumpAndSettle();
        final input = find.byKey(const Key('collection-amount'));
        await tester.scrollUntilVisible(
          input,
          180,
          scrollable: find.byType(Scrollable).last,
        );
        await tester.pumpAndSettle();
        await tester.enterText(input, amount);
        await tester.pumpAndSettle();
        if (intent == PaymentAllocationIntent.scheduled) {
          final reason = find.text('No cash');
          await tester.scrollUntilVisible(
            reason,
            180,
            scrollable: find.byType(Scrollable).first,
          );
          await tester.pumpAndSettle();
          final rendered = find.descendant(
            of: reason,
            matching: find.byType(RichText),
          );
          expect(
            tester.widget<RichText>(rendered).text.style?.fontFamily,
            'Roboto',
            reason: 'Actual Past Due choice must use Android glyphs',
          );
          final promised = find.text('Promised to pay later');
          await tester.scrollUntilVisible(
            promised,
            180,
            scrollable: find.byType(Scrollable).first,
          );
          await tester.pumpAndSettle();
          final label = tester.renderObject<RenderParagraph>(
            find.descendant(of: promised, matching: find.byType(RichText)),
          );
          final last = label
              .getBoxesForSelection(
                const TextSelection(baseOffset: 0, extentOffset: 20),
              )
              .last
              .toRect();
          expect(
            last.right,
            lessThanOrEqualTo(label.size.width + .5),
            reason: 'Full promised-payment choice must fit its painted bounds',
          );
          expect(
            last.bottom,
            lessThanOrEqualTo(label.size.height + .5),
            reason:
                'Full promised-payment choice must wrap inside its painted bounds',
          );
          await captureAndroidWorkflow(tester, 'C1-promised-choice-readable');
        }
        if (intent == PaymentAllocationIntent.extraAsAdvance) {
          final choice = find.byKey(
            const Key('regular-extra-allocation-choice'),
          );
          await tester.scrollUntilVisible(
            choice,
            180,
            scrollable: find.byType(Scrollable).first,
          );
          await tester.pumpAndSettle();
          await tester.tap(choice);
          await tester.pumpAndSettle();
          final semantics = tester.ensureSemantics();
          await captureAndroidWorkflowScroll(
            tester,
            'C1-extra-allocation-menu',
          );
          await checkAndroidWorkflowSemantics(tester);
          semantics.dispose();
          await tester.ensureVisible(find.text('Advance').last);
          await tester.tap(find.text('Advance').last);
          await tester.pumpAndSettle();
        }
        await captureAndroidWorkflowScroll(
          tester,
          'C1-$amount-${intent.name}-keyboard',
        );
        expect(repository.drafts, isEmpty);
        await tester.binding.handlePopRoute();
        await tester.pumpAndSettle();
        expect(find.text('Open synthetic collection'), findsOneWidget);
        expect(repository.drafts, isEmpty);
      },
    );
  }
  testWidgets(
    'keyboard allocation choice exposes full borrower instruction at 320 scale 2.0',
    (tester) async {
      final repository = _CaptureRepository();
      await pumpAndroidRoleFixture(
        tester,
        size: const Size(320, 640),
        textScaler: const TextScaler.linear(2),
        viewInsets: const EdgeInsets.only(bottom: 220),
        home: CollectionEntryPage(
          session: _session,
          entry: _regularEntry,
          repository: repository,
          deviceIdentityProvider: _deviceIdentityProvider(),
          deviceSequence: MemoryCollectionDeviceSequence(),
          collectionDate: DateTime(2026, 8, 1),
        ),
      );
      await tester.pumpAndSettle();
      final choice = find.byKey(const Key('regular-extra-allocation-choice'));
      await tester.scrollUntilVisible(
        choice,
        180,
        scrollable: find.byType(Scrollable).first,
      );
      await tester.pumpAndSettle();
      final selected = find.text('No extra / required only');
      final paragraph = tester.renderObject<RenderParagraph>(selected);
      expect(
        paragraph.didExceedMaxLines,
        isFalse,
        reason:
            'The selected cash allocation must remain readable at OS text scale',
      );
      final fullChoice = TextPainter(
        text: paragraph.text,
        textDirection: paragraph.textDirection,
        textScaler: paragraph.textScaler,
      )..layout(maxWidth: paragraph.size.width);
      final fullChoiceHeight = fullChoice.height;
      fullChoice.dispose();
      expect(
        fullChoiceHeight,
        lessThanOrEqualTo(paragraph.size.height + .5),
        reason: 'The selected allocation must have room for every scaled line',
      );
      final dropdown = find.byType(DropdownButton<PaymentAllocationIntent>);
      expect(
        tester.getRect(selected).bottom,
        lessThanOrEqualTo(tester.getRect(dropdown).bottom + .5),
        reason: 'The dense field must not clip the selected allocation text',
      );
      final instruction = find.text(
        'Choose only when the borrower gives more than required.',
      );
      expect(
        tester.renderObject<RenderParagraph>(instruction).didExceedMaxLines,
        isFalse,
        reason:
            'Borrower choice instruction must not disappear behind an ellipsis',
      );
      await captureAndroidReadability(
        tester,
        'keyboard-allocation-full-320-scale-2.0',
      );
      await tester.tap(choice);
      await tester.pumpAndSettle();
      final advance = find.text('Advance').last;
      await tester.ensureVisible(advance);
      await tester.tap(advance);
      await tester.pumpAndSettle();
      expect(repository.drafts, isEmpty);
      expect(
        tester
            .widget<DropdownButtonFormField<PaymentAllocationIntent>>(choice)
            .initialValue,
        PaymentAllocationIntent.extraAsAdvance,
      );
      expect(tester.takeException(), isNull);
    },
  );
  for (final width in [320.0, 360.0, 412.0]) {
    for (final scale in [1.0, 1.3, 2.0]) {
      testWidgets(
        'keyboard_keeps_action_reachable ${width.toInt()} scale $scale',
        (tester) async {
          final repository = _CaptureRepository();
          final entry = CollectorRouteEntry.fromPayload({
            ..._regularEntry.toJson(),
            'client_name':
                'Synthetic Borrower With A Long Full Name Maria Alexandra Dela Cruz Santos',
            'daily_amount': '123456789.01',
            'balance': '123456789.01',
          })!;
          await pumpAndroidRoleFixture(
            tester,
            size: Size(width, 640),
            textScaler: TextScaler.linear(scale),
            viewInsets: const EdgeInsets.only(bottom: 220),
            home: CollectionEntryPage(
              session: _session,
              entry: entry,
              repository: repository,
              deviceIdentityProvider: _deviceIdentityProvider(),
              deviceSequence: MemoryCollectionDeviceSequence(),
              collectionDate: DateTime(2026, 8, 1),
            ),
          );
          await tester.pumpAndSettle();
          final amount = find.byKey(const Key('collection-amount'));
          await tester.scrollUntilVisible(
            amount,
            180,
            scrollable: find.byType(Scrollable).first,
          );
          expect(
            tester.widget<TextField>(amount).controller!.text,
            '123456789.01',
          );
          await Scrollable.ensureVisible(tester.element(amount), alignment: .5);
          await tester.pumpAndSettle();
          expect(amount.hitTestable(), findsOneWidget);
          await tester.tap(amount);
          await tester.pumpAndSettle();
          final amountContext = tester.element(amount);
          expect(
            MediaQuery.textScalerOf(amountContext).scale(10),
            closeTo(scale * 10, .001),
          );
          expect(
            MediaQuery.viewInsetsOf(
              tester.element(find.byType(Scaffold)),
            ).bottom,
            220,
          );
          await captureAndroidReadability(
            tester,
            'keyboard-entry-${width.toInt()}-scale-$scale',
          );
          final save = find.byKey(const Key('submit-collection-entry'));
          await tester.scrollUntilVisible(
            save,
            180,
            scrollable: find.byType(Scrollable).first,
          );
          await tester.pumpAndSettle();
          expect(save.hitTestable(), findsOneWidget);
          final saveBounds = tester.getRect(save);
          expect(saveBounds.bottom, lessThanOrEqualTo(420));
          expect(saveBounds.width, greaterThanOrEqualTo(48));
          expect(saveBounds.height, greaterThanOrEqualTo(48));
          expect(repository.drafts, isEmpty);
          await captureAndroidReadability(
            tester,
            'keyboard-save-${width.toInt()}-scale-$scale',
          );
          await tester.tap(save);
          await tester.pumpAndSettle();
          expect(repository.drafts, hasLength(1));
          expect(repository.drafts.single.toJson()['amount'], '123456789.01');
          expect(repository.drafts.single.deviceSequence, 1);
          expect(repository.drafts.single.routeEntryId, 'entry-1');
          expect(tester.takeException(), isNull);
        },
      );
    }
  }
  testWidgets(
    'collection form keeps choices and save reachable with large text and keyboard',
    (tester) async {
      final repository = _CaptureRepository();
      await pumpAndroidRoleFixture(
        tester,
        size: const Size(320, 640),
        textScaler: const TextScaler.linear(2),
        viewInsets: const EdgeInsets.only(bottom: 220),
        home: CollectionEntryPage(
          session: _session,
          entry: _regularEntry,
          repository: repository,
          deviceIdentityProvider: _deviceIdentityProvider(),
          deviceSequence: MemoryCollectionDeviceSequence(),
          collectionDate: DateTime(2026, 8, 1),
        ),
      );
      await tester.pumpAndSettle();
      await tester.scrollUntilVisible(
        find.byKey(const Key('submit-collection-entry')),
        180,
        scrollable: find.byType(Scrollable).first,
      );
      await tester.pumpAndSettle();
      expect(tester.takeException(), isNull);
      expect(
        find.byKey(const Key('submit-collection-entry')).hitTestable(),
        findsOneWidget,
      );
      expect(repository.drafts, isEmpty);
    },
  );

  testWidgets('cached route amounts keep exact cents in payment defaults', (
    tester,
  ) async {
    await tester.binding.setSurfaceSize(const Size(800, 1400));
    addTearDown(() => tester.binding.setSurfaceSize(null));
    final entry = CollectorRouteEntry.fromPayload({
      ..._regularEntry.toJson(),
      'daily_amount': '1000000000000000.01',
      'contract_collection_ready': true,
      'contract_today_unpaid_amount': '1000000000000000.02',
      'today_amount': '1000000000000000.03',
    })!;
    final cached = CollectorRouteEntry.fromPayload(entry.toJson())!;
    expect(cached.dailyAmountInput, '1000000000000000.01');
    expect(cached.todayAmountInput, '1000000000000000.03');
    final repository = _CaptureRepository();
    await tester.pumpWidget(
      MaterialApp(
        home: CollectionEntryPage(
          session: _session,
          entry: cached,
          repository: repository,
          deviceIdentityProvider: _deviceIdentityProvider(),
          deviceSequence: MemoryCollectionDeviceSequence(),
          collectionDate: DateTime(2026, 8, 1),
        ),
      ),
    );
    await tester.pumpAndSettle();
    expect(
      tester
          .widget<TextField>(find.byKey(const Key('collection-amount')))
          .controller!
          .text,
      '1000000000000000.02',
    );
    await tester.tap(find.byKey(const Key('submit-collection-entry')));
    await tester.pumpAndSettle();
    expect(repository.drafts.single.toJson()['amount'], '1000000000000000.02');
  });

  testWidgets('entered cents survive the real collection form submission', (
    tester,
  ) async {
    await tester.binding.setSurfaceSize(const Size(800, 1400));
    addTearDown(() => tester.binding.setSurfaceSize(null));
    final repository = _CaptureRepository();
    await tester.pumpWidget(
      MaterialApp(
        home: CollectionEntryPage(
          session: _session,
          entry: _regularEntry,
          repository: repository,
          deviceIdentityProvider: _deviceIdentityProvider(),
          deviceSequence: MemoryCollectionDeviceSequence(),
          collectionDate: DateTime(2026, 8, 1),
        ),
      ),
    );
    await tester.pumpAndSettle();
    await tester.enterText(
      find.byKey(const Key('collection-amount')),
      '1000000000000000.01',
    );
    await tester.tap(find.byKey(const Key('submit-collection-entry')));
    await tester.pumpAndSettle();
    expect(repository.drafts.single.toJson()['amount'], '1000000000000000.01');
  });

  testWidgets('network retry reuses the same idempotency key and sequence', (
    tester,
  ) async {
    final repository = _RetryRepository();
    await pumpAndroidRoleFixture(
      tester,
      size: const Size(320, 640),
      textScaler: TextScaler.linear(2),
      viewInsets: const EdgeInsets.only(bottom: 220),
      home: CollectionEntryPage(
        session: _session,
        entry: _regularEntry,
        repository: repository,
        deviceIdentityProvider: _deviceIdentityProvider(),
        deviceSequence: MemoryCollectionDeviceSequence(),
        collectionDate: DateTime(2026, 8, 1),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.text('200.00'), findsOneWidget);
    await tester.scrollUntilVisible(
      find.byKey(const Key('protected-allocation-card')),
      180,
      scrollable: find.byType(Scrollable).first,
    );
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('protected-allocation-card')), findsOneWidget);
    expect(find.text('Covered dates'), findsNothing);
    expect(find.byKey(const Key('add-covered-date')), findsNothing);

    final submitButton = find.byKey(const Key('submit-collection-entry'));
    await tester.scrollUntilVisible(
      submitButton,
      180,
      scrollable: find.byType(Scrollable).first,
    );
    await tester.pumpAndSettle();
    expect(submitButton, findsOneWidget);
    await tester.tap(submitButton);
    await tester.pumpAndSettle();

    await tester.scrollUntilVisible(
      find.text('Retry same entry'),
      180,
      scrollable: find.byType(Scrollable).first,
    );
    await tester.pumpAndSettle();
    expect(find.text('Retry same entry'), findsOneWidget);
    expect(
      find.text(
        'SPINA could not confirm this collection. Check your connection, then use Retry for the same entry.',
      ),
      findsOneWidget,
    );
    await captureAndroidWorkflowScroll(tester, 'C2-single-uncertain-keyboard');
    await tester.binding.handlePopRoute();
    await tester.pumpAndSettle();
    expect(repository.drafts, hasLength(1));

    await tester.scrollUntilVisible(
      submitButton,
      180,
      scrollable: find.byType(Scrollable).first,
    );
    await tester.pumpAndSettle();
    await tester.tap(submitButton);
    await tester.pumpAndSettle();

    expect(find.text('Payment saved.'), findsOneWidget);
    expect(find.text('Receipt: R-1001'), findsOneWidget);
    expect(find.text('Official balance: ₱4,600.00'), findsOneWidget);
    expect(find.text('Done and refresh route'), findsOneWidget);
    await captureAndroidWorkflowScroll(tester, 'C2-single-reconciled');
    expect(repository.drafts, hasLength(2));
    expect(
      repository.drafts.first.idempotencyKey,
      repository.drafts.last.idempotencyKey,
    );
    expect(repository.drafts.first.deviceSequence, 1);
    expect(repository.drafts.last.deviceSequence, 1);
  });

  testWidgets('stale detailed entry tells the Collector how to recover', (
    tester,
  ) async {
    await tester.binding.setSurfaceSize(const Size(800, 1400));
    addTearDown(() async => tester.binding.setSurfaceSize(null));

    await tester.pumpWidget(
      MaterialApp(
        home: CollectionEntryPage(
          session: _session,
          entry: _regularEntry,
          repository: const _FailureRepository(
            SpinaApiException(
              'Internal route revision conflict.',
              statusCode: 409,
              code: 'route_revision_changed',
            ),
          ),
          deviceIdentityProvider: _deviceIdentityProvider(),
          deviceSequence: MemoryCollectionDeviceSequence(),
          collectionDate: DateTime(2026, 8, 1),
        ),
      ),
    );
    await tester.pumpAndSettle();

    await tester.tap(find.byKey(const Key('submit-collection-entry')));
    await tester.pumpAndSettle();

    expect(
      find.text(
        'This route changed after you opened it. Refresh the route, review the client, then try again.',
      ),
      findsOneWidget,
    );
    expect(find.text('Internal route revision conflict.'), findsNothing);
  });

  testWidgets(
    'regular payment uses simple allocation choice instead of dates',
    (tester) async {
      await tester.binding.setSurfaceSize(const Size(800, 1400));
      addTearDown(() async {
        await tester.binding.setSurfaceSize(null);
      });

      final repository = _CaptureRepository();
      await tester.pumpWidget(
        MaterialApp(
          home: CollectionEntryPage(
            session: _session,
            entry: _regularEntry,
            repository: repository,
            deviceIdentityProvider: _deviceIdentityProvider(),
            deviceSequence: MemoryCollectionDeviceSequence(),
            collectionDate: DateTime(2026, 8, 1),
          ),
        ),
      );
      await tester.pumpAndSettle();

      expect(find.text('Covered dates'), findsNothing);
      expect(find.text('Yesterday'), findsNothing);
      expect(find.text('Today'), findsNothing);
      expect(find.text('Tomorrow'), findsNothing);
      expect(find.text('Open calendar'), findsNothing);
      expect(find.textContaining('oldest Past Due'), findsOneWidget);
      expect(
        find.byKey(const Key('regular-extra-allocation-choice')),
        findsOneWidget,
      );

      await tester.tap(
        find.byKey(const Key('regular-extra-allocation-choice')),
      );
      await tester.pumpAndSettle();
      await tester.tap(find.text('Advance').last);
      await tester.pumpAndSettle();

      await tester.tap(find.byKey(const Key('submit-collection-entry')));
      await tester.pumpAndSettle();

      expect(repository.drafts, hasLength(1));
      expect(
        repository.drafts.single.paymentAllocationIntent,
        PaymentAllocationIntent.extraAsAdvance,
      );
      expect(repository.drafts.single.entryType, CollectionEntryType.payment);
      expect(repository.drafts.single.coveredDates, <DateTime>[
        DateTime(2026, 8, 1),
      ]);
    },
  );

  testWidgets('unable to pay uses approved Past Due reason vocabulary', (
    tester,
  ) async {
    await tester.binding.setSurfaceSize(const Size(800, 1400));
    addTearDown(() async {
      await tester.binding.setSurfaceSize(null);
    });

    await tester.pumpWidget(
      MaterialApp(
        home: CollectionEntryPage(
          session: _session,
          entry: _regularEntry,
          repository: _CaptureRepository(),
          deviceIdentityProvider: _deviceIdentityProvider(),
          deviceSequence: MemoryCollectionDeviceSequence(),
          collectionDate: DateTime(2026, 8, 1),
        ),
      ),
    );
    await tester.pumpAndSettle();

    await tester.tap(find.text('Unable to pay'));
    await tester.pumpAndSettle();

    expect(find.text('Past Due reason'), findsOneWidget);
    expect(find.text('No cash'), findsOneWidget);
    expect(find.text('Client absent'), findsOneWidget);
    expect(find.text('Business slow'), findsOneWidget);
    expect(find.text('Sick/Hospital'), findsOneWidget);
    expect(find.text('Emergency'), findsOneWidget);
    expect(find.text('Promised to pay later'), findsOneWidget);
    expect(find.text('Other'), findsOneWidget);
    expect(find.text('Not home'), findsNothing);
    expect(find.text('Will pay double tomorrow'), findsNothing);
  });

  testWidgets('7x7 collection stays disabled without explicit server gate', (
    tester,
  ) async {
    await tester.pumpWidget(
      MaterialApp(
        home: CollectionEntryPage(
          session: _session,
          entry: const CollectorRouteEntry(
            id: 'entry-7x7',
            clientId: 'client-7x7',
            loanId: 'loan-7x7',
            clientName: 'Seven Client',
            area: 'Cardona',
            loanType: '7x7',
            dailyAmount: 75,
            balance: 2000,
            status: 'Pending',
            passCount: 0,
            routeRevision: 'revision-7x7',
            sevenBySevenMobileEnabled: false,
          ),
          repository: _RetryRepository(),
          deviceIdentityProvider: _deviceIdentityProvider(),
          deviceSequence: MemoryCollectionDeviceSequence(),
        ),
      ),
    );

    expect(
      find.textContaining('7x7 mobile collection is disabled'),
      findsOneWidget,
    );
    expect(find.byKey(const Key('submit-collection-entry')), findsNothing);
  });

  testWidgets(
    'explicit server-enabled 7x7 can submit through the Android form',
    (tester) async {
      await tester.binding.setSurfaceSize(const Size(800, 1400));
      addTearDown(() async {
        await tester.binding.setSurfaceSize(null);
      });

      final repository = _RetryRepository();
      await tester.pumpWidget(
        MaterialApp(
          home: CollectionEntryPage(
            session: _session,
            entry: const CollectorRouteEntry(
              id: 'entry-7x7-enabled',
              clientId: 'client-7x7-enabled',
              loanId: 'loan-7x7-enabled',
              clientName: 'Enabled Seven Client',
              area: 'Cardona',
              loanType: '7x7',
              dailyAmount: 35,
              balance: 5000,
              status: 'Pending',
              passCount: 0,
              routeRevision: 'loan:loan-7x7-enabled:v0',
              canCollectMobile: true,
              canEnterPayment: true,
              sevenBySevenMobileEnabled: true,
            ),
            repository: repository,
            deviceIdentityProvider: _deviceIdentityProvider(),
            deviceSequence: MemoryCollectionDeviceSequence(),
            collectionDate: DateTime(2026, 8, 1),
          ),
        ),
      );
      await tester.pumpAndSettle();

      expect(
        find.textContaining('7x7 mobile collection is disabled'),
        findsNothing,
      );
      expect(find.byKey(const Key('collection-amount')), findsOneWidget);
      expect(find.byKey(const Key('submit-collection-entry')), findsOneWidget);
      expect(
        find.byKey(const Key('regular-extra-allocation-choice')),
        findsNothing,
      );

      await tester.tap(find.byKey(const Key('submit-collection-entry')));
      await tester.pumpAndSettle();

      expect(repository.drafts, hasLength(1));
      expect(repository.drafts.single.entryType, CollectionEntryType.payment);
      expect(repository.drafts.single.toJson()['amount'], '35.00');
      expect(repository.drafts.single.coveredDates, hasLength(1));
      expect(
        repository.drafts.single.routeRevision,
        'loan:loan-7x7-enabled:v0',
      );
      expect(find.text('Retry same entry'), findsOneWidget);
    },
  );
}

const UserSession _session = UserSession(
  userId: 'collector-1',
  username: 'collector.one',
  displayName: 'Test Collector',
  role: AppRole.collector,
  rawRole: 'Collector',
  accessToken: 'test-token',
  permissions: <String>['route.view', 'collection.create'],
);

const CollectorRouteEntry _regularEntry = CollectorRouteEntry(
  id: 'entry-1',
  clientId: 'client-1',
  loanId: 'loan-1',
  clientName: 'Ana Client',
  area: 'Cardona',
  loanType: 'Regular',
  dailyAmount: 200,
  balance: 4800,
  status: 'Pending',
  passCount: 0,
  routeRevision: 'revision-1',
);

DeviceIdentityProvider _deviceIdentityProvider() {
  return DeviceIdentityProvider(
    store: MemoryDeviceIdentityStore(),
    platformResolver: () => 'android',
    appVersionResolver: () async => '1.0.0',
    randomByteGenerator: (length) => List<int>.filled(length, 7),
  );
}

class _RetryRepository implements PaymentSubmissionRepository {
  final List<PaymentSubmissionDraft> drafts = <PaymentSubmissionDraft>[];

  @override
  Future<PaymentSubmissionResult> submit(
    UserSession session,
    PaymentSubmissionDraft draft,
  ) async {
    drafts.add(draft);
    if (drafts.length == 1) {
      throw const SpinaApiException(
        'The collection could not reach the SPINA server. Retry with the same transaction key.',
        code: 'network_unavailable',
      );
    }
    return PaymentSubmissionResult(
      disposition: PaymentSubmissionDisposition.duplicate,
      idempotencyKey: draft.idempotencyKey,
      message: 'Already recorded',
      receiptNumber: 'R-1001',
      officialBalance: 4600,
    );
  }
}

class _CaptureRepository implements PaymentSubmissionRepository {
  final List<PaymentSubmissionDraft> drafts = <PaymentSubmissionDraft>[];

  @override
  Future<PaymentSubmissionResult> submit(
    UserSession session,
    PaymentSubmissionDraft draft,
  ) async {
    drafts.add(draft);
    return PaymentSubmissionResult(
      disposition: PaymentSubmissionDisposition.accepted,
      idempotencyKey: draft.idempotencyKey,
      message: 'Payment saved',
      receiptNumber: 'R-2001',
      officialBalance: 4600,
    );
  }
}

class _FailureRepository implements PaymentSubmissionRepository {
  const _FailureRepository(this.error);

  final SpinaApiException error;

  @override
  Future<PaymentSubmissionResult> submit(
    UserSession session,
    PaymentSubmissionDraft draft,
  ) {
    throw error;
  }
}
