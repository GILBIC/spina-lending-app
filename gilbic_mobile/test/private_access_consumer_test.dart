import 'dart:async';
import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gilbic_mobile/src/core/auth/app_role.dart';
import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/collector/collector_route.dart';
import 'package:gilbic_mobile/src/core/collector/collector_route_loader.dart';
import 'package:gilbic_mobile/src/core/device/device_identity.dart';
import 'package:gilbic_mobile/src/core/network/spina_api.dart';
import 'package:gilbic_mobile/src/core/notifications/activity_notification_repository.dart';
import 'package:gilbic_mobile/src/core/payments/client_payment_proof_repository.dart';
import 'package:gilbic_mobile/src/features/collector/collector_master_review_page.dart';
import 'package:gilbic_mobile/src/features/notifications/activity_notifications_page.dart';
import 'package:gilbic_mobile/src/features/client/client_payment_proofs_page.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'client_payment_proof_repository_test.dart' as fixture;

const actor = UserSession(
  userId: 'synthetic',
  username: 'synthetic',
  displayName: 'Synthetic',
  role: AppRole.collector,
  rawRole: 'Collector',
  accessToken: 'synthetic',
);
DeviceIdentityProvider device() => DeviceIdentityProvider(
  store: MemoryDeviceIdentityStore()..value = 'synthetic',
  platformResolver: () => 'android',
  appVersionResolver: () async => 'test',
);

void main() {
  for (final status in [401, 403, 426, 503]) {
    testWidgets('notification read receipt $status honors access denial', (
      tester,
    ) async {
      final repository = SpinaActivityNotificationRepository(
        client: MockClient(
          (request) async => request.method == 'POST'
              ? http.Response(jsonEncode({'detail': 'Denied'}), status)
              : http.Response(
                  jsonEncode({
                    'success': true,
                    'data': [
                      {
                        'id': 'private',
                        'title': 'PRIVATE NOTIFICATION',
                        'message': 'Private receipt',
                      },
                    ],
                  }),
                  200,
                ),
        ),
      );
      await tester.pumpWidget(
        MaterialApp(
          home: ActivityNotificationsPage(
            session: actor,
            deviceIdentityProvider: device(),
            repository: repository,
          ),
        ),
      );
      await tester.pumpAndSettle();
      await tester.tap(find.text('PRIVATE NOTIFICATION'));
      await tester.pumpAndSettle();
      expect(
        find.text('PRIVATE NOTIFICATION'),
        status == 503 ? findsOneWidget : findsNothing,
      );
    });
  }
  for (final status in [401, 403, 426, 503]) {
    for (final consumer in [
      'master review',
      'notifications',
      'payment proofs',
      'proof history',
    ]) {
      testWidgets(
        '$consumer refresh $status revokes private records only on denial',
        (tester) async {
          await tester.binding.setSurfaceSize(const Size(1000, 1700));
          addTearDown(() => tester.binding.setSurfaceSize(null));
          var denied = false;
          final client = MockClient(
            (_) async => denied
                ? http.Response(
                    jsonEncode({'detail': 'Synthetic denial'}),
                    status,
                  )
                : http.Response(
                    jsonEncode({
                      'success': true,
                      'data': consumer == 'notifications'
                          ? [
                              {
                                'id': 'private',
                                'title': 'PRIVATE NOTIFICATION',
                                'message': 'Private receipt',
                                'sender_name': 'Synthetic',
                              },
                            ]
                          : consumer == 'proof history'
                          ? fixture.detail
                          : {
                              'proofs': [fixture.proof],
                              'has_more': false,
                              'upload_available': true,
                            },
                    }),
                    200,
                  ),
          );
          final proofRepository = SpinaClientPaymentProofRepository(
            client: client,
          );
          final loader = _Loader(() => denied ? status : null);
          final Widget page = switch (consumer) {
            'master review' => CollectorMasterReviewPage(
              session: actor,
              loader: loader,
            ),
            'notifications' => ActivityNotificationsPage(
              session: actor,
              deviceIdentityProvider: device(),
              repository: SpinaActivityNotificationRepository(client: client),
            ),
            'payment proofs' => ClientPaymentProofsPage(
              session: actor,
              deviceIdentityProvider: device(),
              repository: proofRepository,
            ),
            _ => ClientPaymentProofDetailPage(
              session: actor,
              deviceIdentityProvider: device(),
              proofId: 'proof-1',
              repository: proofRepository,
              capability: PaymentProofList.fromPayload({
                'proofs': [],
                'upload_available': true,
              }),
            ),
          };
          await tester.pumpWidget(MaterialApp(home: page));
          await tester.pumpAndSettle();
          final privateText = switch (consumer) {
            'master review' => 'PRIVATE BORROWER',
            'notifications' => 'PRIVATE NOTIFICATION',
            _ => 'LN-1',
          };
          expect(find.textContaining(privateText), findsWidgets);
          denied = true;
          final refresh = find.widgetWithIcon(IconButton, Icons.refresh);
          if (refresh.evaluate().isNotEmpty) {
            await tester.tap(refresh.first);
          } else {
            unawaited(
              tester
                  .widget<RefreshIndicator>(find.byType(RefreshIndicator))
                  .onRefresh(),
            );
          }
          await tester.pumpAndSettle();
          expect(
            find.textContaining(privateText),
            status == 503 ? findsWidgets : findsNothing,
          );
          if (status != 503) {
            expect(find.byType(RefreshIndicator), findsNothing);
            expect(
              find.widgetWithIcon(IconButton, Icons.refresh),
              findsNothing,
            );
          }
        },
      );
    }
  }

  testWidgets(
    'older successful read cannot restore denied Master Review data',
    (tester) async {
      final pending = Completer<CollectorRouteLoadResult>();
      final denied = Completer<CollectorRouteLoadResult>();
      var calls = 0;
      final loader = _FunctionLoader(
        () => switch (++calls) {
          1 => Future.value(_route),
          2 => pending.future,
          _ => denied.future,
        },
      );
      await tester.pumpWidget(
        MaterialApp(
          home: CollectorMasterReviewPage(session: actor, loader: loader),
        ),
      );
      await tester.pumpAndSettle();
      final refresh = tester
          .widget<RefreshIndicator>(find.byType(RefreshIndicator))
          .onRefresh;
      unawaited(refresh());
      unawaited(refresh());
      await tester.pump();
      denied.completeError(const SpinaApiException('Denied', statusCode: 401));
      await tester.pumpAndSettle();
      pending.complete(_route);
      await tester.pumpAndSettle();
      expect(find.text('PRIVATE BORROWER'), findsNothing);
      expect(find.text('Denied'), findsOneWidget);
    },
  );
}

final _route = CollectorRouteLoadResult(
  route: CollectorRoute(
    routeDate: DateTime(2026, 10, 9),
    collectorName: 'Synthetic',
    areas: const ['AREA'],
    expectedTotal: 100,
    entries: const [
      CollectorRouteEntry(
        id: 'entry',
        clientId: 'client',
        loanId: 'loan',
        clientName: 'PRIVATE BORROWER',
        area: 'AREA',
        loanType: 'Regular',
        dailyAmount: 100,
        balance: 1000,
        status: 'Pending',
        passCount: 0,
      ),
    ],
  ),
  syncedAt: DateTime(2026, 10, 9),
  isFromCache: false,
);

class _Loader implements CollectorRouteLoader {
  _Loader(this.denial);
  final int? Function() denial;
  @override
  Future<CollectorRouteLoadResult> loadToday(UserSession session) async {
    final status = denial();
    if (status != null) {
      throw SpinaApiException('Synthetic denial', statusCode: status);
    }
    return _route;
  }
}

class _FunctionLoader implements CollectorRouteLoader {
  _FunctionLoader(this.load);
  final Future<CollectorRouteLoadResult> Function() load;
  @override
  Future<CollectorRouteLoadResult> loadToday(UserSession session) => load();
}
