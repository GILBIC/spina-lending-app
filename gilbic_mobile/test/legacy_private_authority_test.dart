import 'package:gilbic_mobile/src/features/collector/collector_renewal_requests_page.dart';
import 'package:gilbic_mobile/src/features/client/client_renewal_workflow_page.dart';
import 'package:gilbic_mobile/src/features/notifications/remittance_notifications_page.dart';
import 'package:gilbic_mobile/src/features/remittance/remittance_history_page.dart';
import 'package:gilbic_mobile/src/core/renewals/client_renewal_workflow_repository.dart';
import 'package:gilbic_mobile/src/core/renewals/collector_renewal_workflow_repository.dart';
import 'package:gilbic_mobile/src/core/renewals/collector_renewal_workflow.dart';
import 'package:gilbic_mobile/src/core/notifications/remittance_notification_repository.dart';
import 'package:gilbic_mobile/src/core/notifications/remittance_notification.dart';
import 'package:gilbic_mobile/src/core/remittance/remittance_repository.dart';
import 'package:gilbic_mobile/src/core/remittance/remittance.dart';
import 'dart:async';
import 'dart:convert';
import 'dart:typed_data';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gilbic_mobile/src/core/auth/app_role.dart';
import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/device/device_identity.dart';
import 'package:gilbic_mobile/src/core/network/spina_api.dart';
import 'package:gilbic_mobile/src/core/remittance/remittance_photo_repository.dart';
import 'package:gilbic_mobile/src/core/renewals/renewal_signature_tasks_repository.dart';
import 'package:gilbic_mobile/src/features/remittance/remittance_photo_viewer_page.dart';
import 'package:gilbic_mobile/src/features/renewals/renewal_signature_tasks_page.dart';

const session = UserSession(
  userId: 'synthetic-user',
  username: 'synthetic',
  displayName: 'Synthetic User',
  role: AppRole.client,
  rawRole: 'Client',
  accessToken: 'synthetic-token',
  permissions: ['loan.self.view'],
);
DeviceIdentityProvider device() => DeviceIdentityProvider(
  store: MemoryDeviceIdentityStore()..value = 'synthetic-device',
  platformResolver: () => 'android',
  appVersionResolver: () async => 'test',
);

class SignatureRepo extends Fake implements RenewalSignatureTasksRepository {
  int writes = 0;
  SpinaApiException? writeFailure;
  @override
  Future<void> sign(
    UserSession session, {
    required String deviceId,
    required String requestId,
    required String signerId,
  }) async {
    writes++;
    if (writeFailure != null) throw writeFailure!;
  }

  int? denial;
  final pending = <Completer<void>>[];
  Future<void> beforeRead() async {
    if (pending.isNotEmpty) {
      await pending.removeAt(0).future;
      return;
    }
    if (denial != null) {
      throw SpinaApiException('Access unavailable', statusCode: denial);
    }
  }

  @override
  Future<List<RenewalSignatureTask>> list(
    UserSession session, {
    required String deviceId,
  }) async {
    await beforeRead();
    return const [
      RenewalSignatureTask(
        signerId: 'synthetic-signer',
        requestId: 'synthetic-request',
        partyRole: 'guarantor',
        fullName: 'Synthetic Guarantor',
        governmentIdVerified: true,
        selfieVerified: true,
        signed: false,
        clientDecision: 'accepted',
        status: 'approved',
        borrowerName: 'PRIVATE SYNTHETIC BORROWER',
        loanNumber: 'PRIVATE SYNTHETIC LOAN',
        officeProcessingRequired: false,
      ),
    ];
  }
}

class PhotoRepo extends Fake implements RemittancePhotoRepository {
  int? denial;
  final pending = <Completer<void>>[];
  Future<void> beforeRead() async {
    if (pending.isNotEmpty) {
      await pending.removeAt(0).future;
      return;
    }
    if (denial != null) {
      throw SpinaApiException('Access unavailable', statusCode: denial);
    }
  }

  @override
  Future<Uint8List> loadLatest(
    UserSession session, {
    required String deviceId,
    required String remittanceId,
  }) async {
    await beforeRead();
    return base64Decode(
      'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=',
    );
  }
}

void photoAndSignatureTests() {
  for (final boundary in [
    '401',
    '403',
    '426',
    'scope',
    'dispose',
    'transient',
  ]) {
    testWidgets('photo cache generations respect $boundary boundary', (
      tester,
    ) async {
      final repo = PhotoRepo(), identity = device();
      final cache = PaintingBinding.instance.imageCache;
      Widget page(UserSession s) => MaterialApp(
        home: RemittancePhotoViewerPage(
          session: s,
          deviceIdentityProvider: identity,
          remittanceId: 'synthetic-remittance',
          remittanceNumber: 'PRIVATE SYNTHETIC REMITTANCE',
          repository: repo,
        ),
      );
      Future<MemoryImage> decodedPhoto() async {
        final image =
            tester.widget<Image>(find.byType(Image)).image as MemoryImage;
        await tester.runAsync(
          () => precacheImage(image, tester.element(find.byType(Image))),
        );
        await tester.pumpAndSettle();
        expect(tester.widget<RawImage>(find.byType(RawImage)).image, isNotNull);
        expect(cache.statusForKey(image).keepAlive, isTrue);
        return image;
      }

      await tester.pumpWidget(page(session));
      await tester.pumpAndSettle();
      final first = await decodedPhoto();
      final unrelated = MemoryImage(Uint8List.fromList(first.bytes));
      addTearDown(unrelated.evict);
      await tester.runAsync(
        () => precacheImage(unrelated, tester.element(find.byType(Image))),
      );
      await tester.pumpAndSettle();
      await tester.tap(find.byTooltip('Reload photo'));
      await tester.pumpAndSettle();
      final second = await decodedPhoto();
      expect(identical(first.bytes, second.bytes), isFalse);
      expect(first, isNot(second));
      expect(cache.statusForKey(unrelated).keepAlive, isTrue);

      Completer<void>? pending;
      try {
        if (boundary == 'scope') {
          pending = Completer<void>();
          repo.pending.add(pending);
          await tester.pumpWidget(page(changedSession()));
          await tester.pump();
        } else if (boundary == 'dispose') {
          await tester.pumpWidget(const MaterialApp(home: Text('Signed out')));
          await tester.pumpAndSettle();
        } else {
          repo.denial = boundary == 'transient' ? 503 : int.parse(boundary);
          await tester.tap(find.byTooltip('Reload photo'));
          await tester.pumpAndSettle();
        }
        expect(
          cache.statusForKey(first).tracked,
          isFalse,
          reason: 'Superseded private buffer must not outlive its owner',
        );
        expect(cache.statusForKey(second).tracked, boundary == 'transient');
        expect(cache.statusForKey(unrelated).keepAlive, isTrue);
        if (boundary == 'transient') {
          expect(tester.widget<Image>(find.byType(Image)).image, second);
          expect(
            tester.widget<RawImage>(find.byType(RawImage)).image,
            isNotNull,
          );
        }
        expect(tester.takeException(), isNull);
      } finally {
        pending?.complete();
      }
    });
  }
  for (final status in [401, 403, 426]) {
    testWidgets(
      'renewal signature $status clears private borrower and action',
      (tester) async {
        final repo = SignatureRepo();
        await tester.binding.setSurfaceSize(const Size(900, 1200));
        addTearDown(() => tester.binding.setSurfaceSize(null));
        await tester.pumpWidget(
          MaterialApp(
            home: RenewalSignatureTasksPage(
              session: session,
              deviceIdentityProvider: device(),
              repository: repo,
            ),
          ),
        );
        await tester.pumpAndSettle();
        expect(find.text('PRIVATE SYNTHETIC BORROWER'), findsOneWidget);
        repo.denial = status;
        await tester.tap(find.byTooltip('Refresh signatures'));
        await tester.pumpAndSettle();
        expect(
          find.text('PRIVATE SYNTHETIC BORROWER'),
          findsNothing,
          reason:
              'Authoritative denial must clear the previous protected snapshot',
        );
        expect(
          find.byKey(const Key('sign-renewal-synthetic-signer')),
          findsNothing,
        );
      },
    );
    testWidgets('remittance photo $status clears previously loaded bytes', (
      tester,
    ) async {
      final repo = PhotoRepo();
      await tester.pumpWidget(
        MaterialApp(
          home: RemittancePhotoViewerPage(
            session: session,
            deviceIdentityProvider: device(),
            remittanceId: 'synthetic-remittance',
            remittanceNumber: 'PRIVATE SYNTHETIC REMITTANCE',
            repository: repo,
          ),
        ),
      );
      await tester.pumpAndSettle();
      expect(find.byType(Image), findsOneWidget);
      repo.denial = status;
      await tester.tap(find.byTooltip('Reload photo'));
      await tester.pumpAndSettle();
      expect(
        find.byType(Image),
        findsNothing,
        reason: 'Authoritative denial must clear the retained private photo',
      );
    });
  }
}

final renewal = CollectorRenewalRequest.fromPayload({
  'request_id': 'request',
  'client_id': 'client',
  'client_code': 'PRIVATE CODE',
  'client_name': 'PRIVATE BORROWER',
  'area': 'PRIVATE AREA',
  'loan_id': 'loan',
  'loan_number': 'PRIVATE LOAN',
  'loan_type_name': 'Regular',
  'current_principal': 5000,
  'remaining_balance': 4900,
  'contractual_total': 6000,
  'paid_cash': 100,
  'paid_percent': 1.7,
  'requested_amount': '5000.00',
  'status': 'approved',
  'submitted_at': '2026-10-09T00:00:00Z',
  'cash_released_to_collector_at': '2026-10-09T01:00:00Z',
  'signer_readiness_status': 'ready',
  'handover_proof_status': 'pending',
  'activation_status': 'pending',
  'signers': [],
});
final remittance = RemittanceRecord.fromPayload({
  'remittance_id': 'remittance',
  'remittance_number': 'PRIVATE REMITTANCE',
  'collector_user_id': 'collector',
  'collector_name': 'PRIVATE COLLECTOR',
  'recipient_user_id': 'synthetic-user',
  'recipient_name': 'PRIVATE RECIPIENT',
  'status': 'pending',
  'summary': {
    'collector_name': 'PRIVATE COLLECTOR',
    'transaction_count': 1,
    'payment_count': 1,
    'total_amount': 100,
    'items': [],
  },
});
final notification = RemittanceNotification.fromPayload({
  'notification_id': 'notification',
  'remittance_id': 'remittance',
  'remittance_number': 'PRIVATE REMITTANCE',
  'title': 'PRIVATE NOTIFICATION',
  'collector_name': 'PRIVATE COLLECTOR',
  'status': 'pending',
  'total_amount': 100,
});

class Reads {
  SpinaApiException? failure;
  final pending = <Completer<void>>[];
  Future<void> read() async {
    if (pending.isNotEmpty) {
      await pending.removeAt(0).future;
      return;
    }
    if (failure != null) throw failure!;
  }
}

class HistoryRepo extends Fake
    implements RemittanceRepository, RemittanceRejectionRepository {
  SpinaApiException? writeFailure;
  int writes = 0;
  @override
  Future<RemittanceRecord> rejectRemittance(
    UserSession session, {
    required String deviceId,
    required String remittanceId,
    required String reason,
  }) async {
    writes++;
    if (writeFailure != null) throw writeFailure!;
    final original = remittance!;
    return RemittanceRecord(
      remittanceId: original.remittanceId,
      remittanceNumber: original.remittanceNumber,
      collectorUserId: original.collectorUserId,
      collectorName: original.collectorName,
      recipientUserId: original.recipientUserId,
      recipientName: original.recipientName,
      status: 'rejected',
      summary: original.summary,
      note: original.note,
      submittedAt: original.submittedAt,
      receivedAt: null,
      rejectionReason: reason,
      rejectedAt: DateTime.utc(2026, 10, 9),
    );
  }

  final reads = Reads();
  @override
  Future<List<RemittanceRecord>> loadHistory(
    UserSession session, {
    required String deviceId,
  }) async {
    await reads.read();
    return [remittance!];
  }
}

class NotificationsRepo extends Fake
    implements RemittanceNotificationRepository {
  SpinaApiException? writeFailure;
  int writes = 0;
  @override
  Future<RemittanceNotification> markRead(
    UserSession session, {
    required String deviceId,
    required String notificationId,
  }) async {
    writes++;
    if (writeFailure != null) throw writeFailure!;
    return notification!;
  }

  final reads = Reads();
  @override
  Future<List<RemittanceNotification>> loadNotifications(
    UserSession session, {
    required String deviceId,
  }) async {
    await reads.read();
    return [notification!];
  }
}

class RenewalRepo extends Fake
    implements
        ClientRenewalWorkflowRepository,
        CollectorRenewalWorkflowRepository {
  SpinaApiException? writeFailure;
  int writes = 0;
  Future<CollectorRenewalRequest> write() async {
    writes++;
    if (writeFailure != null) throw writeFailure!;
    return renewal;
  }

  @override
  Future<CollectorRenewalRequest> decide(
    UserSession session, {
    required String deviceId,
    required String requestId,
    required String decision,
  }) => write();
  @override
  Future<CollectorRenewalRequest> confirmCashReceived(
    UserSession session, {
    required String deviceId,
    required String requestId,
  }) => write();

  final reads = Reads();
  @override
  Future<List<CollectorRenewalRequest>> list(
    UserSession session, {
    required String deviceId,
  }) async {
    await reads.read();
    return [renewal];
  }
}

class PageCase {
  PageCase(this.refresh, this.privateFinder, this.build, this.reads);
  final String refresh;
  final Finder Function() privateFinder;
  final Widget Function(UserSession, DeviceIdentityProvider) build;
  final Reads reads;
}

List<PageCase> cases() {
  final h = HistoryRepo(),
      n = NotificationsRepo(),
      c = RenewalRepo(),
      r = RenewalRepo();
  return [
    PageCase(
      'Refresh remittances',
      () => find.textContaining('PRIVATE COLLECTOR'),
      (s, d) => RemittanceHistoryPage(
        session: s,
        deviceIdentityProvider: d,
        repository: h,
      ),
      h.reads,
    ),
    PageCase(
      'Refresh remittance requests',
      () => find.text('PRIVATE NOTIFICATION'),
      (s, d) => RemittanceNotificationsPage(
        session: s,
        deviceIdentityProvider: d,
        repository: n,
      ),
      n.reads,
    ),
    PageCase(
      'Refresh renewal progress',
      () => find.textContaining('PRIVATE LOAN'),
      (s, d) => ClientRenewalWorkflowPage(
        session: s,
        deviceIdentityProvider: d,
        repository: c,
      ),
      c.reads,
    ),
    PageCase(
      'Refresh renewals',
      () => find.textContaining('PRIVATE BORROWER'),
      (s, d) => CollectorRenewalRequestsPage(
        session: s,
        deviceIdentityProvider: d,
        repository: r,
      ),
      r.reads,
    ),
  ];
}

UserSession changedSession({String id = 'other', String token = 'token'}) =>
    UserSession(
      userId: id,
      username: 'synthetic',
      displayName: 'Synthetic User',
      role: AppRole.client,
      rawRole: 'Client',
      accessToken: token,
      permissions: const ['loan.self.view'],
    );
Finder refreshButton(String tooltip) =>
    find.byWidgetPredicate((w) => w is IconButton && w.tooltip == tooltip);
UserSession mutationSession() => UserSession(
  userId: 'synthetic-user',
  username: 'synthetic',
  displayName: 'Synthetic User',
  role: AppRole.client,
  rawRole: 'Client',
  accessToken: 'synthetic-token',
  permissions: const [
    'loan.self.view',
    'remittance.receive',
    'renewal.cash_custody.assigned',
  ],
);
void main() {
  testWidgets(
    'history successful rejection updates authoritative record and removes receiving actions',
    (tester) async {
      final repo = HistoryRepo(), d = device();
      await tester.binding.setSurfaceSize(const Size(1000, 1800));
      addTearDown(() => tester.binding.setSurfaceSize(null));
      await tester.pumpWidget(
        MaterialApp(
          home: RemittanceHistoryPage(
            session: mutationSession(),
            deviceIdentityProvider: d,
            repository: repo,
            focusRemittanceId: 'remittance',
          ),
        ),
      );
      await tester.pumpAndSettle();
      await tester.tap(find.byKey(const Key('review-remittance-remittance')));
      await tester.pumpAndSettle();
      await tester.tap(find.byKey(const Key('reject-remittance-remittance')));
      await tester.pumpAndSettle();
      await tester.enterText(
        find.byKey(const Key('remittance-rejection-reason-remittance')),
        'Synthetic mismatch',
      );
      await tester.tap(
        find.byKey(const Key('confirm-reject-remittance-remittance')),
      );
      await tester.pumpAndSettle();
      expect(repo.writes, 1);
      expect(find.text('Reason: Synthetic mismatch'), findsOneWidget);
      expect(
        find.byKey(const Key('receive-remittance-remittance')),
        findsNothing,
      );
      expect(tester.takeException(), isNull);
    },
  );

  testWidgets(
    'history denial dismisses its live rejection dialog without a stale write',
    (tester) async {
      final repo = HistoryRepo(), d = device();
      await tester.binding.setSurfaceSize(const Size(1000, 1800));
      addTearDown(() => tester.binding.setSurfaceSize(null));
      await tester.pumpWidget(
        MaterialApp(
          home: RemittanceHistoryPage(
            session: mutationSession(),
            deviceIdentityProvider: d,
            repository: repo,
            focusRemittanceId: 'remittance',
          ),
        ),
      );
      await tester.pumpAndSettle();
      final refresh = tester
          .widget<IconButton>(refreshButton('Refresh remittances'))
          .onPressed!;
      await tester.tap(find.byKey(const Key('review-remittance-remittance')));
      await tester.pumpAndSettle();
      await tester.tap(find.byKey(const Key('reject-remittance-remittance')));
      await tester.pumpAndSettle();
      await tester.enterText(
        find.byKey(const Key('remittance-rejection-reason-remittance')),
        'Private draft reason',
      );
      repo.reads.failure = const SpinaApiException(
        'Access unavailable',
        statusCode: 403,
      );
      refresh();
      await tester.pumpAndSettle();
      expect(find.byType(AlertDialog), findsNothing);
      expect(find.textContaining('PRIVATE COLLECTOR'), findsNothing);
      expect(repo.writes, 0);
      expect(tester.takeException(), isNull);
    },
  );

  for (final status in [401, 403, 426]) {
    for (final kind in ['history', 'notifications', 'client', 'collector']) {
      testWidgets('$kind mutation denial $status removes protected state', (
        tester,
      ) async {
        final h = HistoryRepo()
          ..writeFailure = SpinaApiException(
            'Access unavailable',
            statusCode: status,
          );
        final n = NotificationsRepo()
          ..writeFailure = SpinaApiException(
            'Access unavailable',
            statusCode: status,
          );
        final r = RenewalRepo()
          ..writeFailure = SpinaApiException(
            'Access unavailable',
            statusCode: status,
          );
        final d = device(), s = mutationSession();
        await tester.binding.setSurfaceSize(const Size(1000, 1800));
        addTearDown(() => tester.binding.setSurfaceSize(null));
        final page = switch (kind) {
          'history' => RemittanceHistoryPage(
            session: s,
            deviceIdentityProvider: d,
            repository: h,
            focusRemittanceId: 'remittance',
          ),
          'notifications' => RemittanceNotificationsPage(
            session: s,
            deviceIdentityProvider: d,
            repository: n,
          ),
          'client' => ClientRenewalWorkflowPage(
            session: s,
            deviceIdentityProvider: d,
            repository: r,
          ),
          _ => CollectorRenewalRequestsPage(
            session: s,
            deviceIdentityProvider: d,
            repository: r,
          ),
        };
        await tester.pumpWidget(MaterialApp(home: page));
        await tester.pumpAndSettle();
        if (kind == 'notifications') {
          await tester.tap(find.byKey(const Key('notification-notification')));
          await tester.pumpAndSettle();
          expect(n.writes, 1);
          expect(find.text('PRIVATE NOTIFICATION'), findsNothing);
        } else {
          if (kind == 'history') {
            await tester.tap(
              find.byKey(const Key('review-remittance-remittance')),
            );
            await tester.pumpAndSettle();
            await tester.tap(
              find.byKey(const Key('reject-remittance-remittance')),
            );
            await tester.pumpAndSettle();
            await tester.enterText(
              find.byKey(const Key('remittance-rejection-reason-remittance')),
              'Synthetic mismatch',
            );
            await tester.tap(
              find.byKey(const Key('confirm-reject-remittance-remittance')),
            );
          } else if (kind == 'client') {
            await tester.tap(
              find.byKey(const Key('client-renewal-accept-request')),
            );
            await tester.pumpAndSettle();
            await tester.tap(
              find.descendant(
                of: find.byType(AlertDialog),
                matching: find.widgetWithText(
                  FilledButton,
                  'Accept & Continue',
                ),
              ),
            );
          } else {
            final button = find.byKey(
              const Key('renewal-cash-received-request'),
            );
            await tester.ensureVisible(button);
            await tester.tap(button);
            await tester.pumpAndSettle();
            await tester.tap(
              find.widgetWithText(FilledButton, 'Confirm Received'),
            );
          }
          await tester.pumpAndSettle();
          expect(kind == 'history' ? h.writes : r.writes, 1);
          expect(
            find.textContaining(
              kind == 'history' ? 'PRIVATE COLLECTOR' : 'PRIVATE LOAN',
            ),
            findsNothing,
          );
        }
      });
    }
  }

  for (final photo in [false, true]) {
    testWidgets(
      'private ${photo ? 'photo' : 'signature'} fences late reads and authority replacement',
      (tester) async {
        final sig = SignatureRepo(), img = PhotoRepo(), d = device();
        await tester.binding.setSurfaceSize(const Size(1000, 1800));
        addTearDown(() => tester.binding.setSurfaceSize(null));
        Widget page(UserSession s) => MaterialApp(
          home: photo
              ? RemittancePhotoViewerPage(
                  session: s,
                  deviceIdentityProvider: d,
                  repository: img,
                  remittanceId: 'remittance',
                  remittanceNumber: 'PRIVATE NUMBER',
                )
              : RenewalSignatureTasksPage(
                  session: s,
                  deviceIdentityProvider: d,
                  repository: sig,
                ),
        );
        Finder private() => photo
            ? find.byType(Image)
            : find.text('PRIVATE SYNTHETIC BORROWER');
        final queue = photo ? img.pending : sig.pending;
        await tester.pumpWidget(page(session));
        await tester.pumpAndSettle();
        expect(private(), findsWidgets);
        final late = Completer<void>();
        queue.add(late);
        final refresh = tester
            .widget<IconButton>(
              refreshButton(photo ? 'Reload photo' : 'Refresh signatures'),
            )
            .onPressed!;
        refresh();
        await tester.pump();
        if (photo) {
          img.denial = 403;
        } else {
          sig.denial = 403;
        }
        refresh();
        await tester.pumpAndSettle();
        expect(private(), findsNothing);
        late.complete();
        await tester.pumpAndSettle();
        expect(private(), findsNothing);
        if (photo) {
          img.denial = null;
        } else {
          sig.denial = null;
        }
        await tester.pumpWidget(
          page(changedSession(id: 'synthetic-user', token: 'rotated')),
        );
        await tester.pumpAndSettle();
        expect(private(), findsNothing);
        final fresh = Completer<void>();
        queue.add(fresh);
        await tester.pumpWidget(page(changedSession()));
        await tester.pump();
        expect(private(), findsNothing);
        fresh.complete();
        await tester.pumpAndSettle();
        expect(private(), findsWidgets);
      },
    );
  }
  for (final status in [401, 403, 426]) {
    testWidgets('signature mutation denial $status revokes tasks', (
      tester,
    ) async {
      final repo = SignatureRepo()
        ..writeFailure = SpinaApiException(
          'Access unavailable',
          statusCode: status,
        );
      await tester.binding.setSurfaceSize(const Size(1000, 1800));
      addTearDown(() => tester.binding.setSurfaceSize(null));
      await tester.pumpWidget(
        MaterialApp(
          home: RenewalSignatureTasksPage(
            session: session,
            deviceIdentityProvider: device(),
            repository: repo,
          ),
        ),
      );
      await tester.pumpAndSettle();
      await tester.tap(find.byKey(const Key('sign-renewal-synthetic-signer')));
      await tester.pumpAndSettle();
      await tester.tap(find.byKey(const Key('confirm-renewal-signature')));
      await tester.pumpAndSettle();
      expect(repo.writes, 1);
      expect(find.text('PRIVATE SYNTHETIC BORROWER'), findsNothing);
    });
  }
  testWidgets('signature open dialog cannot sign after scope replacement', (
    tester,
  ) async {
    final repo = SignatureRepo(), d = device();
    await tester.binding.setSurfaceSize(const Size(1000, 1800));
    addTearDown(() => tester.binding.setSurfaceSize(null));
    Widget page(UserSession s) => MaterialApp(
      home: RenewalSignatureTasksPage(
        session: s,
        deviceIdentityProvider: d,
        repository: repo,
      ),
    );
    await tester.pumpWidget(page(session));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('sign-renewal-synthetic-signer')));
    await tester.pumpAndSettle();
    await tester.pumpWidget(page(changedSession()));
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('confirm-renewal-signature')), findsNothing);
    expect(repo.writes, 0);
  });

  photoAndSignatureTests();
  for (var index = 0; index < 4; index++) {
    for (final status in [401, 403, 426]) {
      testWidgets(
        'legacy owner $index clears private state on $status and latches scope',
        (tester) async {
          final c = cases()[index], d = device();
          await tester.binding.setSurfaceSize(const Size(1000, 1800));
          addTearDown(() => tester.binding.setSurfaceSize(null));
          await tester.pumpWidget(MaterialApp(home: c.build(session, d)));
          await tester.pumpAndSettle();
          expect(c.privateFinder(), findsWidgets);
          c.reads.failure = SpinaApiException(
            'Access unavailable',
            statusCode: status,
          );
          await tester.tap(find.byTooltip(c.refresh));
          await tester.pumpAndSettle();
          expect(c.privateFinder(), findsNothing);
          c.reads.failure = null;
          expect(
            tester.widget<IconButton>(refreshButton(c.refresh)).onPressed,
            isNull,
          );
        },
      );
    }
    testWidgets('legacy owner $index fences late read after denial', (
      tester,
    ) async {
      final c = cases()[index], d = device();
      await tester.binding.setSurfaceSize(const Size(1000, 1800));
      addTearDown(() => tester.binding.setSurfaceSize(null));
      await tester.pumpWidget(MaterialApp(home: c.build(session, d)));
      await tester.pumpAndSettle();
      final late = Completer<void>();
      c.reads.pending.add(late);
      final pending = tester
          .widget<RefreshIndicator>(find.byType(RefreshIndicator))
          .onRefresh();
      await tester.pump();
      c.reads.failure = const SpinaApiException(
        'Access unavailable',
        statusCode: 403,
      );
      await tester
          .widget<RefreshIndicator>(find.byType(RefreshIndicator))
          .onRefresh();
      await tester.pump();
      late.complete();
      await pending;
      await tester.pumpAndSettle();
      expect(c.privateFinder(), findsNothing);
    });
    testWidgets(
      'legacy owner $index retains transient snapshot and fences scope replacement',
      (tester) async {
        final c = cases()[index], d = device();
        await tester.binding.setSurfaceSize(const Size(1000, 1800));
        addTearDown(() => tester.binding.setSurfaceSize(null));
        await tester.pumpWidget(MaterialApp(home: c.build(session, d)));
        await tester.pumpAndSettle();
        c.reads.failure = const SpinaApiException(
          'Temporary unavailable',
          statusCode: 503,
        );
        await tester.tap(find.byTooltip(c.refresh));
        await tester.pumpAndSettle();
        expect(c.privateFinder(), findsWidgets);
        await tester.pumpWidget(
          MaterialApp(
            home: c.build(
              changedSession(id: 'synthetic-user', token: 'rotated'),
              d,
            ),
          ),
        );
        await tester.pumpAndSettle();
        expect(c.privateFinder(), findsWidgets);
        final old = Completer<void>();
        c.reads.pending.add(old);
        final pending = tester
            .widget<RefreshIndicator>(find.byType(RefreshIndicator))
            .onRefresh();
        await tester.pump();
        final newer = Completer<void>();
        c.reads.pending.add(newer);
        await tester.pumpWidget(
          MaterialApp(home: c.build(changedSession(), d)),
        );
        await tester.pump();
        expect(c.privateFinder(), findsNothing);
        old.complete();
        await pending;
        await tester.pump();
        expect(c.privateFinder(), findsNothing);
        newer.complete();
        await tester.pumpAndSettle();
        expect(c.privateFinder(), findsWidgets);
      },
    );
  }
}
