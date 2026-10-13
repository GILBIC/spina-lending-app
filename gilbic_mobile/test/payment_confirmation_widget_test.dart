import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gilbic_mobile/src/core/auth/app_role.dart';
import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/collector/collector_route.dart';
import 'package:gilbic_mobile/src/core/collector/collector_route_loader.dart';
import 'package:gilbic_mobile/src/core/device/device_identity.dart';
import 'package:gilbic_mobile/src/core/payments/collection_device_sequence.dart';
import 'package:gilbic_mobile/src/core/payments/payment_submission_repository.dart';
import 'package:gilbic_mobile/src/features/collector/collector_route_page.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

const session = UserSession(
  userId: 'synthetic-collector',
  username: 'synthetic',
  displayName: 'Synthetic Collector',
  role: AppRole.collector,
  rawRole: 'collector',
  accessToken: 'synthetic-token',
  permissions: ['route.view', 'collection.create'],
);

class RouteLoader implements CollectorRouteLoader {
  int loads = 0;
  @override
  Future<CollectorRouteLoadResult> loadToday(UserSession session) async {
    loads++;
    return CollectorRouteLoadResult(
      route: CollectorRoute(
        routeDate: DateTime(2026, 10, 6),
        collectorName: 'Synthetic Collector',
        areas: const ['Synthetic Area'],
        expectedTotal: 200,
        entries: const [
          CollectorRouteEntry(
            id: 'entry-1',
            clientId: 'client-1',
            loanId: 'loan-1',
            clientName: 'Synthetic Borrower',
            area: 'Synthetic Area',
            loanType: 'Regular',
            dailyAmount: 200,
            balance: 4800,
            status: 'Pending',
            passCount: 0,
            routeRevision: 'synthetic-revision',
          ),
        ],
      ),
      syncedAt: DateTime.utc(2026, 10, 6),
      isFromCache: false,
    );
  }
}

void main() {
  testWidgets(
    'empty payment response retains the exact pending command for Retry',
    (tester) async {
      final posts = <Map<String, dynamic>>[], loader = RouteLoader();
      final repository = SpinaPaymentSubmissionRepository(
        submissionUri: Uri.parse('https://synthetic.invalid/collections'),
        client: MockClient((request) async {
          posts.add(jsonDecode(request.body) as Map<String, dynamic>);
          return http.Response('{}', 201);
        }),
      );
      await tester.pumpWidget(
        MaterialApp(
          home: CollectorRoutePage(
            session: session,
            loader: loader,
            paymentRepository: repository,
            deviceIdentityProvider: DeviceIdentityProvider(
              store: MemoryDeviceIdentityStore(),
              platformResolver: () => 'android',
              appVersionResolver: () async => 'synthetic',
              randomByteGenerator: (length) => List<int>.filled(length, 7),
            ),
            deviceSequence: MemoryCollectionDeviceSequence(),
          ),
        ),
      );
      await tester.pumpAndSettle();
      await tester.tap(find.byKey(const Key('record-collection-entry-1')));
      await tester.pumpAndSettle();
      expect(find.text('Payment saved.'), findsNothing);
      expect(find.text('Retry'), findsOneWidget);
      expect(loader.loads, 1);
      expect(posts.length, 1);
      await tester.tap(find.byKey(const Key('record-collection-entry-1')));
      await tester.pumpAndSettle();
      expect(posts.length, 2);
      expect(
        posts[0]['client_transaction_id'],
        posts[1]['client_transaction_id'],
      );
      expect(posts[0]['device_sequence'], posts[1]['device_sequence']);
      expect(posts[0], posts[1]);
    },
  );
}
