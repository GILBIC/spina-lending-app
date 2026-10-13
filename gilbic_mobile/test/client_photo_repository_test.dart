import 'dart:convert';
import 'dart:typed_data';
import 'dart:async';
import 'package:flutter_test/flutter_test.dart';
import 'package:gilbic_mobile/src/core/auth/app_role.dart';
import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/clients/client_photo_repository.dart';
import 'package:gilbic_mobile/src/core/network/spina_api.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

const photoClient = '11111111-1111-4111-8111-111111111111';
const photoId = '22222222-2222-4222-8222-222222222222';
const photoRequest = '33333333-3333-4333-8333-333333333333';
const photoStaff = UserSession(
  userId: 'staff',
  username: 'staff',
  displayName: 'Staff',
  role: AppRole.employee,
  rawRole: 'employee',
  accessToken: 'private-token',
  permissions: ['client_onboarding.requirement.review'],
);
final photoPng = base64Decode(
  'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=',
);
Map<String, dynamic> photoEnvelope({
  String client = photoClient,
  bool missing = false,
  bool canUpload = true,
  int version = 1,
}) => {
  'success': true,
  'data': {
    'client_id': client,
    'can_upload': canUpload,
    'photo': missing
        ? null
        : {
            'photo_id': photoId,
            'version': version,
            'content_type': 'image/png',
            'byte_size': photoPng.length,
            'uploaded_at': '2026-10-10T01:00:00Z',
            'uploaded_by_user_id': '44444444-4444-4444-8444-444444444444',
            'content_url':
                '/api/v1/clients/$client/photo/content?photo_id=$photoId',
          },
  },
};

void main() {
  test(
    'upload requires a saved successor but accepts a newer current photo on retry',
    () async {
      for (final envelope in [
        photoEnvelope(missing: true),
        photoEnvelope(version: 1),
      ]) {
        final repository = ClientPhotoRepository(
          client: MockClient(
            (_) async => http.Response(jsonEncode(envelope), 200),
          ),
        );
        await expectLater(
          repository.upload(
            photoStaff,
            'device',
            photoClient,
            requestId: photoRequest,
            expectedVersion: 1,
            bytes: photoPng,
            contentType: 'image/png',
          ),
          throwsA(isA<SpinaApiException>()),
        );
      }
      final repository = ClientPhotoRepository(
        client: MockClient(
          (_) async =>
              http.Response(jsonEncode(photoEnvelope(version: 4)), 200),
        ),
      );
      final saved = await repository.upload(
        photoStaff,
        'device',
        photoClient,
        requestId: photoRequest,
        expectedVersion: 1,
        bytes: photoPng,
        contentType: 'image/png',
      );
      expect(saved.version, 4);
    },
  );
  testWidgets('request deadline includes waiting for response headers', (
    tester,
  ) async {
    final pending = Completer<http.Response>();
    final repository = ClientPhotoRepository(
      client: MockClient((_) => pending.future),
    );
    var timedOut = false;
    repository
        .load(photoStaff, 'device', photoClient)
        .then<void>(
          (_) {},
          onError: (Object error) {
            timedOut =
                error is SpinaApiException &&
                error.code == 'network_unavailable';
          },
        );
    await tester.pump();
    await tester.pump(const Duration(seconds: 46));
    expect(timedOut, isTrue);
  });
  test(
    'private content uses device authentication and no-store, pinned to current photo ID',
    () async {
      final requests = <http.Request>[];
      final repository = ClientPhotoRepository(
        client: MockClient((request) async {
          requests.add(request);
          return request.url.path.endsWith('/content')
              ? http.Response.bytes(
                  photoPng,
                  200,
                  headers: {'content-type': 'image/png'},
                )
              : http.Response(jsonEncode(photoEnvelope()), 200);
        }),
      );
      final record = await repository.load(photoStaff, 'device', photoClient);
      expect(await repository.content(photoStaff, 'device', record), photoPng);
      expect(requests.map((r) => r.url.path), [
        '/api/v1/clients/$photoClient/photo',
        '/api/v1/clients/$photoClient/photo/content',
      ]);
      expect(requests.last.url.queryParameters, {'photo_id': photoId});
      for (final request in requests) {
        expect(request.headers['Authorization'], 'Bearer private-token');
        expect(request.headers['X-Device-Id'], 'device');
        expect(request.headers['Cache-Control'], 'no-store');
      }
    },
  );

  test(
    'missing photo remains an authorized record with upload capability',
    () async {
      final repository = ClientPhotoRepository(
        client: MockClient(
          (_) async =>
              http.Response(jsonEncode(photoEnvelope(missing: true)), 200),
        ),
      );
      final record = await repository.load(photoStaff, 'device', photoClient);
      expect(record.version, 0);
      expect(record.photoId, isNull);
      expect(record.canUpload, isTrue);
    },
  );

  test(
    'cross-client metadata and arbitrary content URLs are rejected',
    () async {
      for (final envelope in [
        photoEnvelope(client: photoId),
        photoEnvelope()
          ..['data']['photo']['content_url'] = 'https://evil.test/photo',
      ]) {
        final repository = ClientPhotoRepository(
          client: MockClient(
            (_) async => http.Response(jsonEncode(envelope), 200),
          ),
        );
        await expectLater(
          repository.load(photoStaff, 'device', photoClient),
          throwsA(isA<SpinaApiException>()),
        );
      }
    },
  );

  test('upload preserves raw bytes, request ID and expected version', () async {
    final repository = ClientPhotoRepository(
      client: MockClient((request) async {
        expect(request.method, 'POST');
        expect(request.bodyBytes, photoPng);
        expect(request.headers['Content-Type'], 'image/png');
        expect(request.url.queryParameters, {
          'request_id': photoRequest,
          'expected_version': '0',
        });
        return http.Response(jsonEncode(photoEnvelope()), 200);
      }),
    );
    final record = await repository.upload(
      photoStaff,
      'device',
      photoClient,
      requestId: photoRequest,
      expectedVersion: 0,
      bytes: photoPng,
      contentType: 'image/png',
    );
    expect(record.version, 1);
  });

  test(
    'oversized, unsupported and role-forbidden uploads do not send bytes',
    () async {
      var calls = 0;
      final repository = ClientPhotoRepository(
        client: MockClient((_) async {
          calls++;
          return http.Response('{}', 200);
        }),
      );
      for (final bytes in [
        Uint8List(5 * 1024 * 1024 + 1),
        Uint8List.fromList([71, 73, 70]),
      ]) {
        await expectLater(
          repository.upload(
            photoStaff,
            'device',
            photoClient,
            requestId: photoRequest,
            expectedVersion: 0,
            bytes: bytes,
            contentType: 'image/png',
          ),
          throwsA(isA<SpinaApiException>()),
        );
      }
      const collector = UserSession(
        userId: 'c',
        username: 'c',
        displayName: 'Collector',
        role: AppRole.collector,
        rawRole: 'collector',
        accessToken: 'token',
      );
      await expectLater(
        repository.upload(
          collector,
          'device',
          photoClient,
          requestId: photoRequest,
          expectedVersion: 0,
          bytes: photoPng,
          contentType: 'image/png',
        ),
        throwsA(isA<SpinaApiException>()),
      );
      expect(calls, 0);
    },
  );

  test('conflicts preserve the HTTP status for safe reconciliation', () async {
    final repository = ClientPhotoRepository(
      client: MockClient(
        (_) async => http.Response('{"detail":"Photo changed"}', 409),
      ),
    );
    await expectLater(
      repository.upload(
        photoStaff,
        'device',
        photoClient,
        requestId: photoRequest,
        expectedVersion: 0,
        bytes: photoPng,
        contentType: 'image/png',
      ),
      throwsA(
        isA<SpinaApiException>().having((e) => e.statusCode, 'status', 409),
      ),
    );
  });
}
