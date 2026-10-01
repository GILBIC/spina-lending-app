import 'dart:async';
import 'dart:typed_data';
import 'package:flutter/material.dart';
import 'package:gilbic_mobile/src/core/auth/app_role.dart';
import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gilbic_mobile/src/core/mirror/mirror_controller.dart';
import 'package:gilbic_mobile/src/core/mirror/mirror_repository.dart';
import 'package:gilbic_mobile/src/features/mirror/mirror_host.dart';
import 'mirror_controller_test.dart'
    show FakeMirrorRepository, holder, manager, grant;

class ReadinessRepository extends FakeMirrorRepository {
  int readyCalls = 0;
  bool failStop = false;
  Completer<List<MirrorSession>>? pendingResult;
  List<MirrorSession>? pendingItems;
  @override
  Future<List<MirrorSession>> pending() async => pendingResult != null
      ? pendingResult!.future
      : pendingItems ?? [grant('pending')];
  @override
  Future<MirrorSession> action(MirrorSession session, String action) async {
    if (action == 'ready') readyCalls++;
    if (action == 'stop' && failStop) {
      throw StateError('Synthetic stop failure');
    }
    return super.action(session, action);
  }
}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  testWidgets(
    'auto readiness paints named indicator before first frame without consent button',
    (tester) async {
      tester.view.physicalSize = const Size(320, 640);
      tester.view.devicePixelRatio = 1;
      addTearDown(tester.view.resetPhysicalSize);
      addTearDown(tester.view.resetDevicePixelRatio);
      final api = ReadinessRepository();
      final controller = MirrorController(api, automatic: false)
        ..attach(holder);
      var captures = 0;
      controller.surfaceChanged(() async {
        captures++;
        return Uint8List(1);
      });
      await tester.pumpWidget(
        MaterialApp(
          builder: (context, child) => MediaQuery(
            data: MediaQuery.of(
              context,
            ).copyWith(textScaler: TextScaler.linear(2)),
            child: child!,
          ),
          home: MirrorHost(
            controller: controller,
            onOpenViewer: () {},
            child: const SizedBox.expand(),
          ),
        ),
      );
      await controller.tick();
      expect(api.readyCalls, 1);
      expect(captures, 0);
      await controller
          .tick(); // Even another tick before paint cannot expose pixels.
      expect(captures, 0);
      await tester.pump();
      expect(find.text('Management Viewer is viewing'), findsOneWidget);
      expect(
        tester.getBottomRight(find.text('Management Viewer is viewing')).dy,
        lessThan(640),
      );
      expect(tester.takeException(), isNull);
      expect(find.text('Allow viewing'), findsNothing);
      expect(find.text('Decline'), findsNothing);
      await controller.tick();
      expect(captures, 1);
      expect(find.text('Stop sharing'), findsNothing);
      api.failStop = true;
      controller.foreground(false);
      controller.foreground(true);
      await tester.pump();
      await controller.checkIncoming();
      expect(api.readyCalls, 1);
      expect(controller.sharing, isNull);
      await tester.pumpWidget(const SizedBox());
      controller.dispose();
    },
  );
  for (final boundary in ['unsafe', 'background']) {
    test(
      '$boundary cannot auto-ready and stopped pending replay cannot resume',
      () async {
        final api = ReadinessRepository();
        final controller = MirrorController(api, automatic: false)
          ..attach(holder);
        if (boundary == 'background') {
          controller.surfaceChanged(() async => Uint8List(1));
          controller.foreground(false);
        }
        await controller.tick();
        expect(api.readyCalls, 0);
        controller.foreground(true);
        controller.surfaceChanged(() async => Uint8List(1));
        await controller.checkIncoming();
        expect(api.readyCalls, 1);
        if (boundary == 'background') {
          controller.foreground(false);
          controller.foreground(true);
        } else {
          controller.navigating(eligible: false);
          controller.surfaceChanged(() async => Uint8List(1));
        }
        await controller.checkIncoming();
        expect(api.readyCalls, 1);
        expect(controller.sharing, isNull);
        controller.dispose();
      },
    );
  }
  test(
    'Stop during readiness suppresses a late active reply and pending replay',
    () async {
      final api = ReadinessRepository()..accepting = Completer();
      final controller = MirrorController(api, automatic: false)
        ..attach(holder);
      controller.surfaceChanged(() async => Uint8List(1));
      final pending = controller.tick();
      await Future<void>.delayed(Duration.zero);
      controller.stop();
      api.accepting!.complete(grant('active'));
      await pending;
      await controller.checkIncoming();
      expect(api.readyCalls, 1);
      expect(controller.sharing, isNull);
      controller.dispose();
    },
  );
  testWidgets('Stop belongs to viewer, not a Management-role holder', (
    tester,
  ) async {
    final held = MirrorController(ReadinessRepository(), automatic: false)
      ..attach(
        const UserSession(
          userId: 'holder',
          username: 'holder',
          displayName: 'Holder',
          role: AppRole.management,
          rawRole: 'management',
          accessToken: 'synthetic',
          permissions: ['screen_share.view'],
        ),
      );
    held.surfaceChanged(() async => Uint8List(1));
    await tester.pumpWidget(
      MaterialApp(
        home: MirrorHost(
          controller: held,
          onOpenViewer: () {},
          child: const SizedBox.expand(),
        ),
      ),
    );
    await held.tick();
    await tester.pump();
    expect(find.text('Management Viewer is viewing'), findsOneWidget);
    expect(find.text('Stop sharing'), findsNothing);
    expect(held.mayView, isTrue);
    expect(held.viewing, isFalse);
    await tester.pumpWidget(const SizedBox());
    held.dispose();
    final api = ReadinessRepository();
    final viewer = MirrorController(api, automatic: false)..attach(manager);
    await tester.pumpWidget(
      MaterialApp(
        home: MirrorHost(
          controller: viewer,
          onOpenViewer: () {},
          child: const SizedBox.expand(),
        ),
      ),
    );
    await viewer.request(
      const MirrorTarget(
        userId: 'holder',
        deviceId: 'core-device',
        name: 'Holder',
        deviceName: 'Phone',
      ),
    );
    await tester.pump();
    expect(find.text('Stop sharing'), findsOneWidget);
    await tester.tap(find.text('Stop sharing'));
    await tester.pump();
    expect(viewer.sharing, isNull);
    expect(api.stops, 1);
    await tester.pumpWidget(const SizedBox());
    viewer.dispose();
  });
  test(
    'pending reply after logout cannot auto-ready when the account returns',
    () async {
      final api = ReadinessRepository()..pendingResult = Completer();
      final controller = MirrorController(api, automatic: false)
        ..attach(holder);
      controller.surfaceChanged(() async => Uint8List(1));
      final polling = controller.tick();
      await Future<void>.delayed(Duration.zero);
      controller.attach(null);
      api.pendingResult!.complete([grant('pending')]);
      await polling;
      controller.attach(holder);
      controller.surfaceChanged(() async => Uint8List(1));
      await controller.checkIncoming();
      expect(api.readyCalls, 0);
      expect(controller.sharing, isNull);
      controller.dispose();
    },
  );
  test(
    'newest valid pending request is selected independently of response order',
    () async {
      MirrorSession pending(String id, int day) => MirrorSession(
        id: id,
        state: 'pending',
        generation: 1,
        viewerUserId: 'viewer',
        holderUserId: 'holder',
        viewerName: 'Viewer',
        holderName: 'Holder',
        expiresAt: DateTime.utc(2030),
        createdAt: DateTime.utc(2026, 10, day),
      );
      final api = ReadinessRepository()
        ..pendingItems = [pending('older', 1), pending('newer', 2)];
      final controller = MirrorController(api, automatic: false)
        ..attach(holder);
      controller.surfaceChanged(() async => Uint8List(1));
      await controller.tick();
      expect(controller.sharing?.id, 'newer');
      expect(api.readyCalls, 1);
      controller.dispose();
    },
  );
}
