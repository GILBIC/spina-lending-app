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
  testWidgets('failed collector write waits for explicit retry and never auto replays', (
    tester,
  ) async {
    await tester.binding.setSurfaceSize(const Size(800, 1400));
    addTearDown(() async {
      await tester.binding.setSurfaceSize(null);
    });

    final repository = _AlwaysOfflineRepository();
    await tester.pumpWidget(
      MaterialApp(
        home: CollectionEntryPage(
          session: _session,
          entry: _entry,
          repository: repository,
          deviceIdentityProvider: DeviceIdentityProvider(
            store: MemoryDeviceIdentityStore(),
            platformResolver: () => 'android',
            appVersionResolver: () async => '1.0.0',
            randomByteGenerator: (length) => List<int>.filled(length, 7),
          ),
          deviceSequence: MemoryCollectionDeviceSequence(),
          collectionDate: DateTime(2026, 8, 15),
        ),
      ),
    );
    await tester.pumpAndSettle();

    await tester.tap(find.byKey(const Key('submit-collection-entry')));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('confirm-collection-entry')));
    await tester.pumpAndSettle();

    expect(repository.calls, 1);
    expect(find.text('Retry same entry'), findsOneWidget);
    final originalKey = repository.drafts.single.idempotencyKey;
    final originalSequence = repository.drafts.single.deviceSequence;

    await tester.pump(const Duration(minutes: 5));
    await tester.pumpAndSettle();

    expect(
      repository.calls,
      1,
      reason: 'No timer or background task may replay a financial write.',
    );

    await tester.tap(find.byKey(const Key('submit-collection-entry')));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('confirm-collection-entry')));
    await tester.pumpAndSettle();

    expect(repository.calls, 2);
    expect(repository.drafts.last.idempotencyKey, originalKey);
    expect(repository.drafts.last.deviceSequence, originalSequence);
  });
}

const _session = UserSession(
  userId: 'collector-no-replay',
  username: 'collector.one',
  displayName: 'Collector One',
  role: AppRole.collector,
  rawRole: 'Collector',
  accessToken: 'token',
  permissions: <String>['route.view', 'collection.create'],
);

const _entry = CollectorRouteEntry(
  id: 'entry-no-replay',
  clientId: 'client-no-replay',
  loanId: 'loan-no-replay',
  clientName: 'No Replay Client',
  area: 'Cardona',
  loanType: 'Regular',
  dailyAmount: 200,
  balance: 4800,
  status: 'Pending',
  passCount: 0,
  routeRevision: 'revision-no-replay',
);

class _AlwaysOfflineRepository implements PaymentSubmissionRepository {
  int calls = 0;
  final List<PaymentSubmissionDraft> drafts = <PaymentSubmissionDraft>[];

  @override
  Future<PaymentSubmissionResult> submit(
    UserSession session,
    PaymentSubmissionDraft draft,
  ) async {
    calls += 1;
    drafts.add(draft);
    throw const SpinaApiException(
      'The collection could not reach the SPINA server. Retry with the same transaction key.',
      code: 'network_unavailable',
    );
  }
}
