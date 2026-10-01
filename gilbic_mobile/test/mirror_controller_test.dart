import 'dart:convert';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'dart:async';
import 'dart:typed_data';
import 'package:flutter_test/flutter_test.dart';
import 'package:gilbic_mobile/src/core/auth/app_role.dart';
import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/mirror/mirror_controller.dart';
import 'package:gilbic_mobile/src/core/mirror/mirror_repository.dart';

const holder = UserSession(
  userId: 'holder',
  username: 'holder',
  displayName: 'Holder',
  role: AppRole.collector,
  rawRole: 'collector',
  accessToken: 'synthetic',
);
const manager = UserSession(
  userId: 'viewer',
  username: 'viewer',
  displayName: 'Viewer',
  role: AppRole.management,
  rawRole: 'management',
  accessToken: 'synthetic',
  permissions: ['screen_share.view'],
);

MirrorSession grant(String state) => MirrorSession(
  id: 'share',
  state: state,
  generation: 1,
  viewerUserId: 'viewer',
  holderUserId: 'holder',
  viewerName: 'Viewer',
  holderName: 'Holder',
  expiresAt: DateTime.utc(2030),
  leaseExpiresAt: DateTime.utc(2030),
);

class FakeMirrorRepository implements MirrorRepository {
  int uploads = 0, stops = 0;
  Completer<MirrorSession>? accepting;
  Completer<MirrorFrame?>? reading;
  Completer<void>? uploading;
  @override
  Future<List<MirrorTarget>> targets() async => [];
  @override
  Future<List<MirrorSession>> pending() async => [grant('pending')];
  @override
  Future<MirrorSession> request(MirrorTarget target) async => grant('pending');
  @override
  Future<MirrorSession> status(String id) async => grant('active');
  @override
  Future<MirrorSession> action(MirrorSession session, String action) async {
    if (action == 'stop') {
      stops++;
      return grant('stopped');
    }
    return accepting == null ? grant('active') : accepting!.future;
  }

  @override
  Future<void> publish(
    MirrorSession session,
    int sequence,
    Uint8List bytes, {
    required bool Function() stillCurrent,
  }) async {
    uploads++;
    await uploading?.future;
  }

  @override
  Future<MirrorFrame?> frame(MirrorSession session) async => reading?.future;
  @override
  void close() {}
}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  test(
    'no capture without consent; Stop discards delayed accepted consent',
    () async {
      final api = FakeMirrorRepository()..accepting = Completer();
      final controller = MirrorController(api, automatic: false)
        ..attach(holder);
      var captures = 0;
      controller.surfaceChanged(() async {
        captures++;
        return Uint8List(8);
      });
      await controller.tick();
      expect(captures, 0);
      final accepting = controller.accept(grant('pending'));
      controller.stop();
      api.accepting!.complete(grant('active'));
      await accepting;
      expect(controller.sharing, isNull);
      expect(api.stops, greaterThanOrEqualTo(1));
      controller.dispose();
    },
  );

  for (final boundary in ['navigation', 'dialog', 'background', 'logout']) {
    test('$boundary discards a delayed capture without upload', () async {
      final api = FakeMirrorRepository();
      final controller = MirrorController(api, automatic: false)
        ..attach(holder);
      final capture = Completer<Uint8List?>();
      controller.surfaceChanged(() => capture.future);
      await controller.accept(grant('pending'));
      final running = controller.tick();
      if (boundary == 'background') {
        controller.foreground(false);
      } else if (boundary == 'logout') {
        controller.attach(null);
      } else {
        controller.surfaceChanged(null);
      }
      final bytes = Uint8List.fromList([1, 2, 3]);
      capture.complete(bytes);
      await running;
      expect(api.uploads, 0);
      expect(bytes, everyElement(0));
      expect(controller.sharing, isNull);
      controller.dispose();
    });
  }

  test('one in-flight capture/upload and no continuation after Stop', () async {
    final api = FakeMirrorRepository()..uploading = Completer();
    final controller = MirrorController(api, automatic: false)..attach(holder);
    var captures = 0;
    controller.surfaceChanged(() async {
      captures++;
      return Uint8List.fromList([1]);
    });
    await controller.accept(grant('pending'));
    final running = controller.tick();
    await Future<void>.delayed(Duration.zero);
    await controller.tick();
    expect(captures, 1);
    controller.stop();
    api.uploading!.complete();
    await running;
    expect(controller.sharing, isNull);
    controller.dispose();
  });

  test('viewer late response after Stop cannot repopulate image', () async {
    final api = FakeMirrorRepository()..reading = Completer();
    final controller = MirrorController(api, automatic: false)..attach(manager);
    await controller.request(
      const MirrorTarget(
        userId: 'holder',
        deviceId: 'device',
        name: 'Holder',
        deviceName: 'Phone',
      ),
    );
    final running = controller.tick();
    await Future<void>.delayed(Duration.zero);
    controller.stop();
    final bytes = Uint8List.fromList([1, 2]);
    api.reading!.complete(MirrorFrame(bytes, 1, 1));
    await running;
    expect(controller.viewerBytes, isNull);
    expect(bytes, everyElement(0));
    controller.dispose();
  });

  test('viewer clears image three seconds after last new sequence', () async {
    var now = DateTime.utc(2026);
    final api = FakeMirrorRepository()..reading = Completer();
    final controller = MirrorController(api, automatic: false, now: () => now)
      ..attach(manager);
    await controller.request(
      const MirrorTarget(
        userId: 'holder',
        deviceId: 'device',
        name: 'Holder',
        deviceName: 'Phone',
      ),
    );
    api.reading!.complete(MirrorFrame(Uint8List.fromList([1]), 1, 1));
    await controller.tick();
    expect(controller.viewerBytes, isNotNull);
    now = now.add(const Duration(seconds: 3));
    controller.expireImage();
    expect(controller.viewerBytes, isNull);
    controller.dispose();
  });
  test(
    'publish cadence starts after completion, including variable capture delay',
    () async {
      var now = DateTime.utc(2026);
      final api = FakeMirrorRepository();
      final controller = MirrorController(api, automatic: false, now: () => now)
        ..attach(holder);
      controller.surfaceChanged(() async {
        now = now.add(const Duration(milliseconds: 750));
        return Uint8List(1);
      });
      await controller.accept(grant('pending'));
      await controller.tick();
      now = now.add(const Duration(milliseconds: 250));
      await controller.tick();
      expect(api.uploads, 1);
      now = now.add(const Duration(milliseconds: 750));
      await controller.tick();
      expect(api.uploads, 2);
      controller.dispose();
    },
  );

  test(
    'same sequence cannot extend freshness; permission/device changes stop',
    () async {
      var now = DateTime.utc(2026);
      final api = FakeMirrorRepository()..reading = Completer();
      final controller = MirrorController(api, automatic: false, now: () => now)
        ..attach(manager);
      controller.deviceChanged('raw-installation-a');
      await controller.request(
        const MirrorTarget(
          userId: 'holder',
          deviceId: 'core-device-uuid',
          name: 'Holder',
          deviceName: 'Phone',
        ),
      );
      api.reading!.complete(MirrorFrame(Uint8List.fromList([1]), 1, 1));
      await controller.tick();
      now = now.add(const Duration(seconds: 2));
      api.reading = Completer()
        ..complete(MirrorFrame(Uint8List.fromList([2]), 1, 1));
      await controller.tick();
      now = now.add(const Duration(seconds: 1));
      controller.expireImage();
      expect(controller.viewerBytes, isNull);
      expect(controller.deviceChanged('raw-installation-b'), isFalse);
      expect(controller.sharing, isNull);
      await controller.request(
        const MirrorTarget(
          userId: 'holder',
          deviceId: 'core-device-uuid',
          name: 'Holder',
          deviceName: 'Phone',
        ),
      );
      controller.attach(
        const UserSession(
          userId: 'viewer',
          username: 'viewer',
          displayName: 'Viewer',
          role: AppRole.management,
          rawRole: 'management',
          accessToken: 'synthetic',
        ),
      );
      expect(controller.sharing, isNull);
      expect(controller.mayView, isFalse);
      controller.dispose();
    },
  );
  test(
    'eligible navigation during upload preserves completed-publish cadence',
    () async {
      var now = DateTime.utc(2026);
      final api = FakeMirrorRepository()..uploading = Completer();
      final controller = MirrorController(api, automatic: false, now: () => now)
        ..attach(holder);
      controller.surfaceChanged(() async => Uint8List(1));
      await controller.accept(grant('pending'));
      final upload = controller.tick();
      await Future<void>.delayed(Duration.zero);
      controller.navigating(eligible: true);
      controller.surfaceChanged(() async => Uint8List(1));
      now = now.add(const Duration(milliseconds: 800));
      api.uploading!.complete();
      await upload;
      now = now.add(const Duration(milliseconds: 200));
      await controller.tick();
      expect(api.uploads, 1);
      now = now.add(const Duration(milliseconds: 800));
      await controller.tick();
      expect(api.uploads, 2);
      controller.dispose();
    },
  );

  test(
    'Stop during device resolution prevents a not-yet-sent frame request',
    () async {
      final resolving = Completer<String>();
      var devices = 0;
      var uploads = 0;
      final api = SpinaMirrorRepository(
        session: () => holder,
        deviceId: () {
          devices++;
          return devices == 2
              ? resolving.future
              : Future.value('raw-installation');
        },
        client: MockClient((request) async {
          if (request.method == 'PUT') {
            uploads++;
            return http.Response(
              '',
              204,
              headers: {'cache-control': 'no-store'},
            );
          }
          return http.Response(
            jsonEncode({
              'id': 'share',
              'state': request.url.path.endsWith('/stop')
                  ? 'stopped'
                  : 'active',
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
      final controller = MirrorController(api, automatic: false)
        ..attach(holder);
      controller.surfaceChanged(() async => Uint8List(1));
      await controller.accept(grant('pending'));
      final upload = controller.tick();
      await Future<void>.delayed(Duration.zero);
      expect(devices, 2);
      controller.stop();
      resolving.complete('raw-installation');
      await upload;
      expect(uploads, 0);
      controller.dispose();
    },
  );
}
