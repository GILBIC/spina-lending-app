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
  for (final edit in [false, true]) {
    testWidgets(
      'uncertain payment exact identity preserved after note edit=$edit',
      (tester) async {
        await tester.binding.setSurfaceSize(const Size(800, 1400));
        addTearDown(() => tester.binding.setSurfaceSize(null));
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
        final button = find.byKey(const Key('submit-collection-entry'));
        await tester.tap(button);
        await tester.pumpAndSettle();
        expect(find.text('Retry same entry'), findsOneWidget);
        if (edit) {
          expect(
            tester
                .widget<TextField>(find.byKey(const Key('collection-note')))
                .enabled,
            isFalse,
          );
          expect(
            tester
                .widget<TextField>(find.byKey(const Key('collection-amount')))
                .enabled,
            isFalse,
          );
        }
        await tester.tap(button);
        await tester.pumpAndSettle();
        expect(repository.drafts, hasLength(2));
        expect(
          repository.drafts.last.idempotencyKey,
          repository.drafts.first.idempotencyKey,
          reason: 'Unconfirmed command must keep its original UUID',
        );
        expect(
          repository.drafts.last.deviceSequence,
          repository.drafts.first.deviceSequence,
        );
      },
    );
  }
  testWidgets('uncertain payment exact identity survives Back and reopen', (
    tester,
  ) async {
    await tester.binding.setSurfaceSize(const Size(800, 1400));
    addTearDown(() => tester.binding.setSurfaceSize(null));
    final repository = _RetryRepository();
    final sequence = MemoryCollectionDeviceSequence();
    PaymentSubmissionDraft? pending;
    await tester.pumpWidget(
      MaterialApp(
        home: Builder(
          builder: (context) => Scaffold(
            body: TextButton(
              onPressed: () => Navigator.push(
                context,
                MaterialPageRoute<void>(
                  builder: (_) => CollectionEntryPage(
                    session: _session,
                    entry: _regularEntry,
                    repository: repository,
                    deviceIdentityProvider: _deviceIdentityProvider(),
                    deviceSequence: sequence,
                    collectionDate: DateTime(2026, 8, 1),
                    pendingDraft: pending,
                    onPendingDraftChanged: (draft) => pending = draft,
                  ),
                ),
              ),
              child: const Text('Open collection'),
            ),
          ),
        ),
      ),
    );
    await tester.tap(find.text('Open collection'));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('submit-collection-entry')));
    await tester.pumpAndSettle();
    expect(find.text('Retry same entry'), findsOneWidget);
    await tester.pageBack();
    await tester.pumpAndSettle();
    await tester.tap(find.text('Open collection'));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('submit-collection-entry')));
    await tester.pumpAndSettle();
    expect(
      repository.drafts.last.idempotencyKey,
      repository.drafts.first.idempotencyKey,
      reason: 'Back must retain unresolved payment identity',
    );
    expect(repository.drafts.last.toJson(), repository.drafts.first.toJson());
    expect(pending, isNull);
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
