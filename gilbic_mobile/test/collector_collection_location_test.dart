import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gilbic_mobile/src/core/auth/app_role.dart';
import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/collector/collector_collection_location.dart';
import 'package:gilbic_mobile/src/core/collector/collector_collection_location_repository.dart';
import 'package:gilbic_mobile/src/core/collector/collector_route.dart';
import 'package:gilbic_mobile/src/core/collector/collector_route_grouping.dart';
import 'package:gilbic_mobile/src/core/collector/collector_route_loader.dart';
import 'package:gilbic_mobile/src/core/device/device_identity.dart';
import 'package:gilbic_mobile/src/features/collector/collector_client_collection_location_page.dart';
import 'package:gilbic_mobile/src/features/collector/collector_route_page.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

void main() {
  test(
    'Collection Location repository uses the protected Client route endpoint and parses approved verified fields',
    () async {
      final deviceStore = MemoryDeviceIdentityStore()
        ..value = 'collector-location-device';
      final repository = SpinaCollectorCollectionLocationRepository(
        deviceIdentityProvider: DeviceIdentityProvider(
          store: deviceStore,
          platformResolver: () => 'android',
          appVersionResolver: () async => '0.4.0+4',
        ),
        client: MockClient((request) async {
          expect(request.method, 'GET');
          expect(
            request.url.path,
            '/api/mobile/v1/collector/clients/client-location/collection-location',
          );
          expect(request.headers['authorization'], 'Bearer collector-location-token');
          expect(request.headers['x-device-id'], 'collector-location-device');

          return http.Response(
            jsonEncode(<String, Object?>{
              'success': true,
              'data': <String, Object?>{
                'client_id': 'client-location',
                'collection_location_status': 'verified',
                'display_address': '12 Sampaguita Street, Cardona, Rizal',
                'landmark': 'Beside the barangay hall',
                'photo_url': 'https://example.test/verified-location.jpg',
                'verified_at': '2026-09-10T08:30:00+08:00',
                // Fields outside the approved route-detail contract must not
                // become part of the mobile collection-location model.
                'national_id': 'forbidden-national-id',
                'tin': 'forbidden-tin',
                'meralco_account': 'forbidden-meralco',
                'latitude': 14.1,
                'longitude': 121.2,
              },
            }),
            200,
          );
        }),
      );

      final location = await repository.fetchCollectionLocation(
        _session,
        clientId: 'client-location',
      );

      expect(location.clientId, 'client-location');
      expect(location.isVerified, isTrue);
      expect(location.displayAddress, '12 Sampaguita Street, Cardona, Rizal');
      expect(location.landmark, 'Beside the barangay hall');
      expect(location.photoUrl, 'https://example.test/verified-location.jpg');
      expect(
        location.verifiedAt,
        DateTime.parse('2026-09-10T08:30:00+08:00'),
      );
    },
  );

  test(
    'Collection Location model suppresses detail fields unless the server marks the record verified',
    () {
      final location = CollectorCollectionLocation.fromPayload(
        <String, Object?>{
          'client_id': 'client-location',
          'collection_location_status': 'not_verified',
          'display_address': 'Must not leak',
          'landmark': 'Must not leak',
          'photo_url': 'https://example.test/must-not-leak.jpg',
          'verified_at': '2026-09-10T08:30:00+08:00',
        },
      );

      expect(location.isVerified, isFalse);
      expect(location.displayAddress, isNull);
      expect(location.landmark, isNull);
      expect(location.photoUrl, isNull);
      expect(location.verifiedAt, isNull);
    },
  );

  testWidgets(
    'Collection Location page fails closed when no authoritative verified route detail exists',
    (tester) async {
      await _usePhoneSurface(tester);
      final repository = _FakeLocationRepository(
        CollectorCollectionLocation.fromPayload(
          const <String, Object?>{
            'client_id': 'client-location',
            'collection_location_status': 'not_verified',
            'display_address': null,
            'landmark': null,
            'photo_url': null,
            'verified_at': null,
          },
        ),
      );

      await tester.pumpWidget(
        MaterialApp(
          home: CollectorClientCollectionLocationPage(
            session: _session,
            client: _clientGroup,
            repository: repository,
          ),
        ),
      );
      await tester.pumpAndSettle();

      expect(repository.requestedClientIds, <String>['client-location']);
      expect(find.text('Collection Location'), findsOneWidget);
      expect(find.text('Location Client'), findsOneWidget);
      expect(find.text('Not verified'), findsOneWidget);
      expect(
        find.text('No verified collection location is available for this Client.'),
        findsOneWidget,
      );

      // The operational Area is routing scope, not a physical address.
      expect(find.text('Cardona › Calahan'), findsNothing);
      expect(find.textContaining('National ID'), findsNothing);
      expect(find.textContaining('TIN'), findsNothing);
      expect(find.textContaining('Meralco'), findsNothing);
      expect(find.text('Edit'), findsNothing);
      expect(find.text('Save'), findsNothing);
      expect(find.text('Upload'), findsNothing);
      expect(find.text('Take photo'), findsNothing);
    },
  );

  testWidgets(
    'Collection Location page shows only server-approved verified route detail',
    (tester) async {
      await _usePhoneSurface(tester);
      final repository = _FakeLocationRepository(
        CollectorCollectionLocation.fromPayload(
          const <String, Object?>{
            'client_id': 'client-location',
            'collection_location_status': 'verified',
            'display_address': '12 Sampaguita Street, Cardona, Rizal',
            'landmark': 'Beside the barangay hall',
            'photo_url': 'https://example.test/verified-location.jpg',
            'verified_at': '2026-09-10T08:30:00+08:00',
          },
        ),
      );

      await tester.pumpWidget(
        MaterialApp(
          home: CollectorClientCollectionLocationPage(
            session: _session,
            client: _clientGroup,
            repository: repository,
          ),
        ),
      );
      await tester.pump();
      await tester.pump();

      expect(find.text('Verified'), findsOneWidget);
      expect(find.text('12 Sampaguita Street, Cardona, Rizal'), findsOneWidget);
      expect(find.text('Beside the barangay hall'), findsOneWidget);
      expect(find.textContaining('2026-09-10'), findsOneWidget);
      expect(
        find.byKey(const Key('collector-collection-location-photo')),
        findsOneWidget,
      );
      expect(find.text('Cardona › Calahan'), findsNothing);
      expect(find.text('Edit'), findsNothing);
      expect(find.text('Save'), findsNothing);
      expect(find.text('Upload'), findsNothing);
    },
  );

  testWidgets(
    'Client Tools Collection location opens the dedicated protected read-only page',
    (tester) async {
      await _usePhoneSurface(tester);
      final repository = _FakeLocationRepository(
        CollectorCollectionLocation.fromPayload(
          const <String, Object?>{
            'client_id': 'client-location',
            'collection_location_status': 'not_verified',
          },
        ),
      );

      await tester.pumpWidget(
        MaterialApp(
          home: CollectorRoutePage(
            session: _session,
            loader: _LocationRouteLoader(),
            collectionLocationRepository: repository,
          ),
        ),
      );
      await tester.pumpAndSettle();

      await tester.tap(find.byKey(const Key('route-client-client-location')));
      await tester.pumpAndSettle();
      expect(find.text('Client Tools'), findsOneWidget);

      await tester.tap(find.text('Collection location'));
      await tester.pumpAndSettle();

      expect(find.text('Collection Location'), findsOneWidget);
      expect(repository.requestedClientIds, <String>['client-location']);
      expect(
        find.textContaining('connected in the next Area Management step'),
        findsNothing,
      );
      expect(find.text('Edit'), findsNothing);
      expect(find.text('Save'), findsNothing);
      expect(find.text('Upload'), findsNothing);
    },
  );
}

Future<void> _usePhoneSurface(WidgetTester tester) async {
  await tester.binding.setSurfaceSize(const Size(430, 900));
  addTearDown(() async {
    await tester.binding.setSurfaceSize(null);
  });
}

const UserSession _session = UserSession(
  userId: 'collector-location',
  username: 'collector.location',
  displayName: 'Collector Location',
  role: AppRole.collector,
  rawRole: 'Collector',
  accessToken: 'collector-location-token',
  permissions: <String>['route.view', 'collection.create'],
);

const CollectorRouteEntry _locationEntry = CollectorRouteEntry(
  id: 'location-regular',
  clientId: 'client-location',
  loanId: 'loan-location-regular',
  clientName: 'Location Client',
  area: 'Cardona › Calahan',
  loanType: 'Regular',
  dailyAmount: 100,
  balance: 4200,
  status: 'Pending',
  passCount: 0,
  routeRevision: 'loan:location-regular:v1',
);

const CollectorRouteClientGroup _clientGroup = CollectorRouteClientGroup(
  clientId: 'client-location',
  clientName: 'Location Client',
  area: 'Cardona › Calahan',
  loans: <CollectorRouteEntry>[_locationEntry],
);

class _FakeLocationRepository implements CollectorCollectionLocationRepository {
  _FakeLocationRepository(this.location);

  final CollectorCollectionLocation location;
  final List<String> requestedClientIds = <String>[];

  @override
  Future<CollectorCollectionLocation> fetchCollectionLocation(
    UserSession session, {
    required String clientId,
  }) async {
    requestedClientIds.add(clientId);
    return location;
  }
}

class _LocationRouteLoader implements CollectorRouteLoader {
  @override
  Future<CollectorRouteLoadResult> loadToday(UserSession session) async {
    return CollectorRouteLoadResult(
      route: CollectorRoute(
        routeDate: DateTime(2026, 9, 10),
        collectorName: 'Collector Location',
        areas: const <String>['Cardona › Calahan'],
        entries: const <CollectorRouteEntry>[_locationEntry],
        expectedTotal: 100,
      ),
      syncedAt: DateTime.utc(2026, 9, 10, 0),
      isFromCache: false,
    );
  }
}
