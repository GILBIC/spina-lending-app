import 'package:flutter/material.dart';
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

void main() {
  testWidgets('network retry reuses the same idempotency key and sequence', (
    tester,
  ) async {
    await tester.binding.setSurfaceSize(const Size(800, 1400));
    addTearDown(() async {
      await tester.binding.setSurfaceSize(null);
    });

    final repository = _RetryRepository();
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

    expect(find.text('200.00'), findsOneWidget);
    expect(find.text('Covered dates'), findsOneWidget);
    expect(find.byKey(const Key('confirm-collection-entry')), findsNothing);

    final submitButton = find.byKey(const Key('submit-collection-entry'));
    expect(submitButton, findsOneWidget);
    await tester.tap(submitButton);
    await tester.pumpAndSettle();

    expect(find.text('Retry same entry'), findsOneWidget);
    expect(find.textContaining('could not reach'), findsOneWidget);
    expect(repository.drafts, hasLength(1));

    await tester.tap(submitButton);
    await tester.pumpAndSettle();

    expect(find.text('Payment saved.'), findsOneWidget);
    expect(find.text('Receipt: R-1001'), findsOneWidget);
    expect(find.text('Official balance: ₱4,600.00'), findsOneWidget);
    expect(find.text('Done and refresh route'), findsOneWidget);
    expect(find.byKey(const Key('confirm-collection-entry')), findsNothing);
    expect(repository.drafts, hasLength(2));
    expect(
      repository.drafts.first.idempotencyKey,
      repository.drafts.last.idempotencyKey,
    );
    expect(repository.drafts.first.deviceSequence, 1);
    expect(repository.drafts.last.deviceSequence, 1);
  });

  testWidgets('covered-date calendar keeps every selected date circled', (
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
          repository: _RetryRepository(),
          deviceIdentityProvider: _deviceIdentityProvider(),
          deviceSequence: MemoryCollectionDeviceSequence(),
          collectionDate: DateTime(2026, 8, 1),
        ),
      ),
    );
    await tester.pumpAndSettle();

    await tester.tap(find.byKey(const Key('add-covered-date')));
    await tester.pumpAndSettle();

    final dialog = find.byType(AlertDialog);
    expect(find.text('Choose covered dates'), findsOneWidget);
    expect(find.byType(CalendarDatePicker), findsNothing);
    expect(find.byKey(const Key('covered-date-calendar')), findsOneWidget);
    expect(
      find.byKey(const Key('selected-covered-date-2026-08-01')),
      findsOneWidget,
    );
    expect(
      find.descendant(
        of: dialog,
        matching: find.textContaining('selected day'),
      ),
      findsNothing,
    );
    expect(
      find.byKey(const Key('calendar-selected-2026-08-01')),
      findsNothing,
    );

    await tester.tap(
      find.byKey(const Key('covered-calendar-day-2026-08-02')),
    );
    await tester.pumpAndSettle();
    expect(
      find.byKey(const Key('selected-covered-date-2026-08-01')),
      findsOneWidget,
    );
    expect(
      find.byKey(const Key('selected-covered-date-2026-08-02')),
      findsOneWidget,
    );

    await tester.tap(
      find.byKey(const Key('covered-calendar-day-2026-08-03')),
    );
    await tester.pumpAndSettle();
    expect(
      find.byKey(const Key('selected-covered-date-2026-08-01')),
      findsOneWidget,
    );
    expect(
      find.byKey(const Key('selected-covered-date-2026-08-02')),
      findsOneWidget,
    );
    expect(
      find.byKey(const Key('selected-covered-date-2026-08-03')),
      findsOneWidget,
    );
    expect(find.text('Choose covered dates'), findsOneWidget);

    await tester.tap(find.byKey(const Key('confirm-covered-dates')));
    await tester.pumpAndSettle();

    expect(find.text('2026-08-01'), findsOneWidget);
    expect(find.text('2026-08-02'), findsOneWidget);
    expect(find.text('2026-08-03'), findsOneWidget);
    expect(find.text('600.00'), findsOneWidget);
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

  testWidgets('explicit server-enabled 7x7 can submit through the Android form', (
    tester,
  ) async {
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

    expect(find.textContaining('7x7 mobile collection is disabled'), findsNothing);
    expect(find.byKey(const Key('collection-amount')), findsOneWidget);
    expect(find.byKey(const Key('submit-collection-entry')), findsOneWidget);
    expect(find.byKey(const Key('confirm-collection-entry')), findsNothing);

    await tester.tap(find.byKey(const Key('submit-collection-entry')));
    await tester.pumpAndSettle();

    expect(repository.drafts, hasLength(1));
    expect(repository.drafts.single.entryType, CollectionEntryType.payment);
    expect(repository.drafts.single.amount, 35);
    expect(repository.drafts.single.coveredDates, hasLength(1));
    expect(repository.drafts.single.routeRevision, 'loan:loan-7x7-enabled:v0');
    expect(find.text('Retry same entry'), findsOneWidget);
  });
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