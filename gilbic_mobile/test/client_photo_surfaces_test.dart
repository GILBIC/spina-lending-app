import 'dart:convert';
import 'dart:async';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gilbic_mobile/src/core/auth/app_role.dart';
import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/clients/client_photo_repository.dart';
import 'package:gilbic_mobile/src/core/collector/collector_route_grouping.dart';
import 'package:gilbic_mobile/src/core/device/device_identity.dart';
import 'package:gilbic_mobile/src/core/loans/client_loan.dart';
import 'package:gilbic_mobile/src/core/loans/client_loan_repository.dart';
import 'package:gilbic_mobile/src/core/office/office_repository.dart';
import 'package:gilbic_mobile/src/features/client/client_loans_page.dart';
import 'package:gilbic_mobile/src/features/collector/collector_client_tools_sheet.dart';
import 'package:gilbic_mobile/src/features/office/office_cif_page.dart';
import 'package:gilbic_mobile/src/features/office/office_widgets.dart';
import 'package:gilbic_mobile/src/features/shared/client_photo_card.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'client_photo_repository_test.dart'
    show photoEnvelope, photoClient, photoPng;
import 'support/office_ui_fixture.dart' as office;

DeviceIdentityProvider device() => DeviceIdentityProvider(
  store: MemoryDeviceIdentityStore()..value = 'device',
  platformResolver: () => 'android',
  appVersionResolver: () async => '1.0.0',
);
UserSession viewer(AppRole role) => UserSession(
  userId: role.name,
  username: role.name,
  displayName: role.label,
  role: role,
  rawRole: role.name,
  accessToken: '${role.name}-token',
);
ClientPhotoRepository photos() => ClientPhotoRepository(
  client: MockClient((request) async {
    expect(request.url.path, '/api/v1/clients/$photoClient/photo');
    expect(request.headers['X-Device-Id'], 'device');
    return http.Response(jsonEncode(photoEnvelope(missing: true)), 200);
  }),
);

void main() {
  testWidgets('CIF shows optional client photo without completing liveness', (
    tester,
  ) async {
    await tester.pumpWidget(
      MaterialApp(
        home: OfficeCifPage(
          actor: office.actor(),
          clientId: photoClient,
          repository: OfficeRepository(
            client: MockClient((_) async => office.response(office.cif)),
          ),
          photoRepository: photos(),
        ),
      ),
    );
    await tester.pumpAndSettle();
    expect(find.text('Add photo'), findsOneWidget);
    expect(
      find.descendant(
        of: find.byType(ClientPhotoCard),
        matching: find.text('Sample Applicant'),
      ),
      findsOneWidget,
    );
    await office.reveal(tester, '4. Identity verification');
    await tester.tap(find.text('4. Identity verification'));
    await tester.pumpAndSettle();
    final baseline = find.widgetWithText(
      CheckboxListTile,
      'Baseline face and liveness verification passed.',
    );
    expect(tester.widget<CheckboxListTile>(baseline).value, isFalse);
  });

  testWidgets('switching selected CIF reloads name before showing its photo', (
    tester,
  ) async {
    const nextId = '55555555-5555-4555-8555-555555555555';
    final actor = office.actor();
    final repository = OfficeRepository(
      client: MockClient(
        (request) async => office.response({
          ...office.cif,
          'client_id': request.url.path.contains(nextId) ? nextId : photoClient,
          'full_name': request.url.path.contains(nextId)
              ? 'Juan Reyes'
              : 'Maria Santos',
        }),
      ),
    );
    final photoRepository = ClientPhotoRepository(
      client: MockClient(
        (request) async => http.Response(
          jsonEncode(
            photoEnvelope(
              client: request.url.path.contains(nextId) ? nextId : photoClient,
              missing: true,
            ),
          ),
          200,
        ),
      ),
    );
    Widget page(String id) => MaterialApp(
      home: OfficeCifPage(
        actor: actor,
        clientId: id,
        repository: repository,
        photoRepository: photoRepository,
      ),
    );
    await tester.pumpWidget(page(photoClient));
    await tester.pumpAndSettle();
    await tester.pumpWidget(page(nextId));
    await tester.pumpAndSettle();
    expect(
      find.descendant(
        of: find.byType(ClientPhotoCard),
        matching: find.text('Juan Reyes'),
      ),
      findsOneWidget,
    );
    expect(find.text('Maria Santos'), findsNothing);
  });

  testWidgets('CIF refresh retains an in-progress photo selection', (
    tester,
  ) async {
    final pending = Completer<http.Response>();
    var reads = 0;
    final repository = OfficeRepository(
      client: MockClient(
        (_) async =>
            ++reads == 1 ? office.response(office.cif) : pending.future,
      ),
    );
    await tester.pumpWidget(
      MaterialApp(
        home: OfficeCifPage(
          actor: office.actor(),
          clientId: photoClient,
          repository: repository,
          photoRepository: photos(),
        ),
      ),
    );
    await tester.pumpAndSettle();
    await tester.tap(find.text('Add photo'));
    await tester.pumpAndSettle();
    await tester.tap(find.byTooltip('Reload saved record'));
    await tester.pump();
    expect(find.text('Gallery'), findsOneWidget);
    pending.complete(office.response(office.cif));
    await tester.pumpAndSettle();
    expect(find.text('Gallery'), findsOneWidget);
  });

  testWidgets('collector client tools show photo placeholder with no editor', (
    tester,
  ) async {
    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: CollectorClientToolsSheet(
            client: const CollectorRouteClientGroup(
              clientId: photoClient,
              clientName: 'Maria Santos',
              area: 'Area',
              loans: [],
            ),
            session: viewer(AppRole.collector),
            deviceIdentityProvider: device(),
            photoRepository: photos(),
            directPayBlockedReasonFor: (_) => null,
            detailsBlockedReasonFor: (_) => null,
            correctionBlockedReasonFor: (_) => null,
          ),
        ),
      ),
    );
    await tester.pumpAndSettle();
    expect(find.text('Maria Santos'), findsOneWidget);
    expect(find.text('No client photo'), findsOneWidget);
    expect(find.text('Add photo'), findsNothing);
    expect(find.text('Collection location'), findsOneWidget);
  });

  testWidgets(
    'CIF scrolling preserves uncertain upload bytes and request identity',
    (tester) async {
      final posts = <http.Request>[];
      final photoRepository = ClientPhotoRepository(
        client: MockClient((request) async {
          if (request.method == 'POST') {
            posts.add(request);
            throw http.ClientException('lost response');
          }
          return http.Response(jsonEncode(photoEnvelope(missing: true)), 200);
        }),
      );
      await tester.pumpWidget(
        MaterialApp(
          home: OfficeCifPage(
            actor: office.actor(),
            clientId: photoClient,
            repository: OfficeRepository(
              client: MockClient((_) async => office.response(office.cif)),
            ),
            photoRepository: photoRepository,
            photoPicker: (_) async => OfficePhoto(photoPng, 'image/png'),
          ),
        ),
      );
      await tester.pumpAndSettle();
      await tester.tap(find.text('Add photo'));
      await tester.pumpAndSettle();
      await tester.tap(find.text('Gallery'));
      await tester.runAsync(
        () => Future<void>.delayed(const Duration(milliseconds: 80)),
      );
      await tester.pumpAndSettle();
      await tester.tap(find.text('Save photo'));
      await tester.pumpAndSettle();
      expect(find.text('Retry same upload'), findsOneWidget);
      final position = tester
          .state<ScrollableState>(find.byType(Scrollable).first)
          .position;
      position.jumpTo(position.maxScrollExtent);
      await tester.pumpAndSettle();
      position.jumpTo(0);
      await tester.pumpAndSettle();
      expect(find.text('Retry same upload'), findsOneWidget);
      await tester.tap(find.text('Retry same upload'));
      await tester.pumpAndSettle();
      expect(posts, hasLength(2));
      expect(posts[0].url, posts[1].url);
      expect(posts[0].bodyBytes, photoPng);
      expect(posts[1].bodyBytes, photoPng);
    },
  );

  testWidgets('own portfolio displays photo while empty loans remain usable', (
    tester,
  ) async {
    await tester.pumpWidget(
      MaterialApp(
        home: ClientLoansPage(
          session: viewer(AppRole.client),
          deviceIdentityProvider: device(),
          repository: _Loans(),
          photoRepository: photos(),
        ),
      ),
    );
    await tester.pumpAndSettle();
    expect(find.text('Maria Santos'), findsOneWidget);
    expect(find.text('No client photo'), findsOneWidget);
    expect(find.text('Add photo'), findsNothing);
    expect(find.text('No active loans were found.'), findsOneWidget);
  });
}

class _Loans implements ClientLoanRepository {
  @override
  Future<ClientLoanPortfolio> loadPortfolio(
    UserSession session, {
    required String deviceId,
  }) async => const ClientLoanPortfolio(
    clientId: photoClient,
    clientCode: 'C001',
    clientName: 'Maria Santos',
    clientStatus: 'active',
    loans: [],
  );
}
