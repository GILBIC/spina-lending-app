import 'dart:convert';
import 'dart:typed_data';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:gilbic_mobile/src/core/mirror/mirror_repository.dart';
import 'mirror_controller_test.dart' show manager, grant;

void main() {
  test(
    'device header is raw installation identity, request target is core device UUID',
    () async {
      final api = SpinaMirrorRepository(
        session: () => manager,
        deviceId: () async => 'raw-installation',
        client: MockClient((request) async {
          expect(request.url.path, '/api/v1/screen-shares');
          expect(request.headers['X-Device-Id'], 'raw-installation');
          expect(request.headers['Authorization'], 'Bearer synthetic');
          expect(jsonDecode(request.body), {
            'holder_user_id': 'holder',
            'holder_device_id': 'core-device-uuid',
          });
          return http.Response(
            jsonEncode({
              'id': 'share',
              'state': 'pending',
              'generation': 1,
              'viewer_user_id': 'viewer',
              'holder_user_id': 'holder',
              'viewer_name': 'Viewer',
              'holder_name': 'Holder',
              'expires_at': '2030-01-01T00:00:00Z',
            }),
            201,
            headers: {'cache-control': 'no-store'},
          );
        }),
      );
      expect(
        (await api.request(
          const MirrorTarget(
            userId: 'holder',
            deviceId: 'core-device-uuid',
            name: 'Holder',
            deviceName: 'Phone',
          ),
        )).state,
        'pending',
      );
      api.close();
    },
  );

  test(
    'readiness uses ready endpoint and old accept action is rejected',
    () async {
      final api = SpinaMirrorRepository(
        session: () => manager,
        deviceId: () async => 'raw',
        client: MockClient((request) async {
          expect(request.method, 'POST');
          expect(request.url.path, '/api/v1/screen-shares/share/ready');
          expect(jsonDecode(request.body), {'generation': 1});
          return http.Response(
            jsonEncode({
              'id': 'share',
              'state': 'active',
              'generation': 1,
              'viewer_user_id': 'viewer',
              'holder_user_id': 'holder',
              'viewer_name': 'Viewer',
              'holder_name': 'Holder',
              'expires_at': '2030-01-01T00:00:00Z',
            }),
            200,
            headers: {'cache-control': 'no-store'},
          );
        }),
      );
      expect((await api.action(grant('pending'), 'ready')).state, 'active');
      expect(() => api.action(grant('pending'), 'accept'), throwsArgumentError);
      api.close();
    },
  );

  for (final fault in ['cache', 'generation', 'size', 'dimensions', 'mime']) {
    test('viewer rejects $fault protocol violation before decode', () async {
      final bytes = Uint8List(fault == 'size' ? 524289 : 24);
      bytes.setRange(0, 8, [137, 80, 78, 71, 13, 10, 26, 10]);
      final data = ByteData.sublistView(bytes)
        ..setUint32(16, fault == 'dimensions' ? 2048 : 2)
        ..setUint32(20, 2);
      expect(data.lengthInBytes, bytes.length);
      final api = SpinaMirrorRepository(
        session: () => manager,
        deviceId: () async => 'raw',
        client: MockClient(
          (_) async => http.Response.bytes(
            bytes,
            200,
            headers: {
              'cache-control': fault == 'cache' ? 'public' : 'no-store',
              'content-type': fault == 'mime' ? 'text/plain' : 'image/png',
              'x-screen-share-generation': fault == 'generation' ? '2' : '1',
              'x-screen-share-sequence': '1',
            },
          ),
        ),
      );
      await expectLater(api.frame(grant('active')), throwsFormatException);
      api.close();
    });
  }
}
