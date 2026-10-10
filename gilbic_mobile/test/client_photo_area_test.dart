import 'dart:convert';
import 'dart:typed_data';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gilbic_mobile/src/core/areas/area_repository.dart';
import 'package:gilbic_mobile/src/core/auth/app_role.dart';
import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/clients/client_photo_repository.dart';
import 'package:gilbic_mobile/src/core/device/device_identity.dart';
import 'package:gilbic_mobile/src/features/areas/area_management_page.dart';
import 'package:gilbic_mobile/src/features/office/office_widgets.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'client_photo_repository_test.dart'
    show photoClient, photoEnvelope, photoPng;

void main() {
  for (final canUpload in [true, false]) {
    testWidgets(
      'area search client without loan or intake has photo access $canUpload',
      (tester) async {
        final session = UserSession(
          userId: 'office',
          username: 'office',
          displayName: 'Office Staff',
          role: AppRole.employee,
          rawRole: 'employee',
          accessToken: 'token',
          permissions: [
            'area.client.assign',
            if (canUpload) 'client_onboarding.requirement.review',
          ],
        );
        final device = DeviceIdentityProvider(
          store: MemoryDeviceIdentityStore()..value = 'device',
          platformResolver: () => 'android',
          appVersionResolver: () async => '1.0.0',
        );
        final areaRequests = <http.Request>[];
        final repository = AreaRepository(
          deviceIdentityProvider: device,
          client: MockClient((request) async {
            areaRequests.add(request);
            if (request.url.path == '/api/v1/areas') {
              return http.Response('{"areas":[]}', 200);
            }
            expect(request.url.path, '/api/v1/areas/clients');
            expect(request.url.queryParameters['q'], 'Maria');
            return http.Response(
              jsonEncode({
                'clients': [
                  {
                    'client_id': photoClient,
                    'full_name': 'Maria Santos',
                    'client_code': 'C001',
                    'area_path': null,
                  },
                ],
              }),
              200,
            );
          }),
        );
        final photoRequests = <http.Request>[];
        final photos = ClientPhotoRepository(
          client: MockClient((request) async {
            photoRequests.add(request);
            expect(
              request.url.path.startsWith('/api/v1/clients/$photoClient/photo'),
              isTrue,
            );
            return request.url.path.endsWith('/content')
                ? http.Response.bytes(
                    Uint8List.fromList(photoPng),
                    200,
                    headers: {'content-type': 'image/png'},
                  )
                : http.Response(
                    jsonEncode(
                      photoEnvelope(missing: request.method != 'POST'),
                    ),
                    200,
                  );
          }),
        );
        await tester.pumpWidget(
          MaterialApp(
            home: AreaManagementPage(
              session: session,
              deviceIdentityProvider: device,
              repository: repository,
              photoRepository: photos,
              photoPicker: (_) async => OfficePhoto(photoPng, 'image/png'),
            ),
          ),
        );
        await tester.pumpAndSettle();
        await tester.enterText(
          find.widgetWithText(TextField, 'Borrower name or code'),
          'Maria',
        );
        await tester.tap(find.text('Search borrowers'));
        await tester.pumpAndSettle();
        expect(find.text('Maria Santos'), findsOneWidget);
        expect(areaRequests, hasLength(2));
        if (!canUpload) {
          expect(find.text('Client photo'), findsNothing);
          expect(find.text('Transfer'), findsOneWidget);
          expect(photoRequests, isEmpty);
          return;
        }
        await tester.ensureVisible(find.text('Client photo'));
        await tester.tap(find.text('Client photo'));
        await tester.pumpAndSettle();
        expect(find.text('Maria Santos'), findsOneWidget);
        await tester.tap(find.text('Add photo'));
        await tester.pumpAndSettle();
        await tester.tap(find.text('Gallery'));
        await tester.runAsync(
          () => Future<void>.delayed(const Duration(milliseconds: 80)),
        );
        await tester.pumpAndSettle();
        expect(find.byKey(const Key('client-photo-preview')), findsOneWidget);
        await tester.tap(find.text('Save photo'));
        await tester.runAsync(
          () => Future<void>.delayed(const Duration(milliseconds: 80)),
        );
        await tester.pumpAndSettle();
        expect(find.text('Photo saved.'), findsOneWidget);
        expect(photoRequests.where((r) => r.method == 'POST'), hasLength(1));
        expect(
          photoRequests.where((r) => r.method == 'POST').single.bodyBytes,
          photoPng,
        );
        expect(areaRequests, hasLength(2));
      },
    );
  }
}
