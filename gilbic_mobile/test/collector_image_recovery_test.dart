import 'dart:convert';
import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gilbic_mobile/src/core/auth/app_role.dart';
import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/collector/collector_route.dart';
import 'package:gilbic_mobile/src/core/collector/collector_route_repository.dart';
import 'package:gilbic_mobile/src/core/device/device_identity.dart';
import 'package:gilbic_mobile/src/core/media/image_recovery_controller.dart';
import 'package:gilbic_mobile/src/core/remittance/remittance.dart';
import 'package:gilbic_mobile/src/core/remittance/remittance_photo_repository.dart';
import 'package:gilbic_mobile/src/core/renewals/collector_renewal_workflow.dart';
import 'package:gilbic_mobile/src/core/renewals/collector_renewal_workflow_repository.dart';
import 'package:gilbic_mobile/src/features/collector/collector_cash_to_client_page.dart';
import 'package:gilbic_mobile/src/features/collector/collector_handover_image_context.dart';
import 'package:gilbic_mobile/src/features/collector/collector_renewal_requests_page.dart';
import 'package:gilbic_mobile/src/features/collector/remittance_handover_photo_page.dart';
import 'package:gilbic_mobile/src/features/shared/image_recovery_scope.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:image_picker/image_picker.dart';

const _session = UserSession(
  userId: 'collector',
  username: 'collector',
  displayName: 'Collector',
  role: AppRole.collector,
  rawRole: 'collector',
  accessToken: 'token',
);
final _png = base64Decode(
  'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=',
);
final _request = <String, dynamic>{
  'request_id': 'renewal-1',
  'client_id': 'client-1',
  'client_code': 'C1',
  'client_name': 'Borrower',
  'area': 'Area',
  'loan_id': 'loan-1',
  'loan_number': 'LN-1',
  'loan_type_name': 'Regular',
  'current_principal': 1000,
  'remaining_balance': 100,
  'contractual_total': 1100,
  'paid_cash': 1000,
  'paid_percent': 90,
  'requested_amount': 1000,
  'status': 'approved',
  'submitted_at': '2026-09-20T00:00:00Z',
  'signer_readiness_status': 'ready',
  'handover_proof_status': 'missing',
  'activation_status': 'pending',
  'amount_locked_at': '2026-09-20T01:00:00Z',
  'net_release_amount': 900,
  'cash_released_to_collector_at': '2026-09-20T02:00:00Z',
  'collector_cash_received_at': '2026-09-20T03:00:00Z',
  'cash_given_to_client_at': '2026-09-20T04:00:00Z',
};
DeviceIdentityProvider _device() => DeviceIdentityProvider(
  store: MemoryDeviceIdentityStore()..value = 'device',
  platformResolver: () => 'android',
  appVersionResolver: () async => 'test',
);
http.Response _json(Object value) => http.Response(
  jsonEncode(value),
  200,
  headers: {'content-type': 'application/json'},
);

class _Store implements ImageRecoveryStore {
  String? value;
  @override
  Future<String?> read() async => value;
  @override
  Future<void> write(String value) async {
    this.value = value;
  }

  @override
  Future<void> delete() async {
    value = null;
  }
}

class _UnusedPicker extends ImagePicker {
  int calls = 0;
  @override
  Future<XFile?> pickImage({
    required ImageSource source,
    double? maxWidth,
    double? maxHeight,
    int? imageQuality,
    CameraDevice preferredCameraDevice = CameraDevice.rear,
    bool requestFullMetadata = true,
  }) async {
    calls++;
    return null;
  }
}

class _NoRoute implements CollectorRouteRepository {
  @override
  Future<CollectorRoute> fetchToday(UserSession session) async =>
      throw StateError('No route');
}

Future<ImageRecoveryController> _recovered(ImagePickContext context) async {
  final directory = Directory.systemTemp.createTempSync(
    'spina-collector-recovery-',
  );
  addTearDown(() => directory.deleteSync(recursive: true));
  final file = File('${directory.path}/recovered.png')..writeAsBytesSync(_png);
  final store = _Store()
    ..value = jsonEncode({
      'version': 1,
      'owner': 'collector-device',
      'purpose': context.purpose,
      'target': context.target,
      'label': context.label,
      'createdAt': DateTime.now().toUtc().toIso8601String(),
      'path': null,
    });
  final controller = ImageRecoveryController(
    store: store,
    enabled: true,
    retrieveLostData: () async => LostDataResponse(
      type: RetrieveType.image,
      files: [XFile.fromData(_png, path: file.path, mimeType: 'image/png')],
    ),
  );
  await controller.initialize('collector-device');
  addTearDown(controller.dispose);
  return controller;
}

Future<void> _show(WidgetTester tester, Finder finder) async {
  await tester.scrollUntilVisible(
    finder,
    250,
    scrollable: find.byType(Scrollable).first,
  );
  await tester.pumpAndSettle();
}

Future<void> _openRecovery(WidgetTester tester, Finder finder) async {
  await tester.tap(finder);
  await tester.pump();
  await tester.pump(const Duration(milliseconds: 300));
}

Future<void> _acceptRecovery(WidgetTester tester, String label) async {
  await tester.tap(find.text(label));
  await tester.pumpAndSettle();
}

void main() {
  test('renewal context changes with the locked handover and target', () {
    final original = renewalHandoverImageContext(
      CollectorRenewalRequest.fromPayload(_request),
    );
    for (final change in [
      {'request_id': 'renewal-2'},
      {'client_id': 'client-2'},
      {'loan_id': 'loan-2'},
      {'amount_locked_at': '2026-09-20T05:00:00Z'},
      {'net_release_amount': 901},
      {'cash_given_to_client_at': '2026-09-20T06:00:00Z'},
    ]) {
      expect(
        renewalHandoverImageContext(
          CollectorRenewalRequest.fromPayload({..._request, ...change}),
        ).target,
        isNot(original.target),
      );
    }
  });
  for (final cashQueue in [false, true]) {
    testWidgets(
      '${cashQueue ? 'cash queue' : 'renewals'} uploads recovered photo only after explicit upload',
      (tester) async {
        final requests = <http.Request>[];
        final repository = SpinaCollectorRenewalWorkflowRepository(
          client: MockClient((request) async {
            if (request.method == 'GET') {
              return _json({
                'requests': [_request],
              });
            }
            requests.add(request);
            return _json({'status': 'under_review'});
          }),
        );
        final picker = _UnusedPicker();
        final controller = await _recovered(
          renewalHandoverImageContext(
            CollectorRenewalRequest.fromPayload(_request),
          ),
        );
        await tester.pumpWidget(
          ImageRecoveryScope(
            controller: controller,
            child: MaterialApp(
              home: cashQueue
                  ? CollectorCashToClientPage(
                      session: _session,
                      deviceIdentityProvider: _device(),
                      repository: repository,
                      routeRepository: _NoRoute(),
                      imagePicker: picker,
                    )
                  : CollectorRenewalRequestsPage(
                      session: _session,
                      deviceIdentityProvider: _device(),
                      repository: repository,
                      imagePicker: picker,
                    ),
            ),
          ),
        );
        await tester.pumpAndSettle();
        expect(requests, isEmpty);
        final button = find.byKey(
          Key('${cashQueue ? 'cash-to-client' : 'renewal'}-proof-renewal-1'),
        );
        await _show(tester, button);
        await tester.tap(button);
        await tester.pumpAndSettle();
        await _openRecovery(tester, find.text('Choose from gallery'));
        expect(requests, isEmpty);
        expect(picker.calls, 0);
        expect(find.text('Upload recovered photo'), findsOneWidget);
        await _acceptRecovery(tester, 'Upload recovered photo');
        expect(requests, hasLength(1));
        expect(requests.single.url.path, endsWith('/renewal-1/handover-photo'));
        expect(requests.single.bodyBytes, orderedEquals(_png));
        expect(requests.single.headers['content-type'], 'image/png');
        expect(controller.recovered, isNull);
        expect(picker.calls, 0);
        expect(tester.takeException(), isNull);
      },
    );
  }
  testWidgets(
    'recovered remittance photo stays a draft until Save Handover Photo',
    (tester) async {
      final remittance = RemittanceRecord.fromPayload({
        'remittance_id': 'remittance-1',
        'remittance_number': 'R-1',
        'collector_user_id': 'collector',
        'recipient_user_id': 'recipient',
        'submitted_at': '2026-09-20T01:00:00Z',
      })!;
      final controller = await _recovered(
        remittanceHandoverImageContext(remittance),
      );
      final picker = _UnusedPicker();
      final requests = <http.Request>[];
      final repository = SpinaRemittancePhotoRepository(
        client: MockClient((request) async {
          requests.add(request);
          return _json({
            'photo_id': 'photo-1',
            'remittance_id': 'remittance-1',
          });
        }),
      );
      await tester.pumpWidget(
        ImageRecoveryScope(
          controller: controller,
          child: MaterialApp(
            home: RemittanceHandoverPhotoPage(
              session: _session,
              remittance: remittance,
              deviceIdentityProvider: _device(),
              repository: repository,
              imagePicker: picker,
            ),
          ),
        ),
      );
      await tester.pumpAndSettle();
      await _openRecovery(
        tester,
        find.byKey(const Key('choose-handover-photo')),
      );
      expect(requests, isEmpty);
      expect(picker.calls, 0);
      await _acceptRecovery(tester, 'Use photo');
      expect(requests, isEmpty);
      final save = find.byKey(const Key('upload-handover-photo'));
      await _show(tester, save);
      await tester.tap(save);
      await tester.pumpAndSettle();
      expect(requests, hasLength(1));
      expect(
        requests.single.url.path,
        endsWith('/remittance-1/handover-photo'),
      );
      expect(requests.single.bodyBytes, orderedEquals(_png));
      expect(picker.calls, 0);
      expect(tester.takeException(), isNull);
    },
  );
}
