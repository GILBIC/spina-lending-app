import 'dart:async';
import 'dart:typed_data';
import 'dart:ui' as ui;
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gilbic_mobile/src/core/mirror/mirror_controller.dart';
import 'package:gilbic_mobile/src/features/mirror/safe_mirror_surface.dart';
import 'package:gilbic_mobile/src/features/mirror/mirror_viewer_page.dart';
import 'package:gilbic_mobile/src/features/mirror/mirror_host.dart';
import 'package:gilbic_mobile/src/core/mirror/mirror_repository.dart';
import 'mirror_controller_test.dart'
    show FakeMirrorRepository, holder, manager, grant;

class TargetRepository extends FakeMirrorRepository {
  @override
  Future<List<MirrorTarget>> targets() async => [
    const MirrorTarget(
      userId: 'holder',
      deviceId: 'core-device',
      name: 'Holder target',
      deviceName: 'Phone',
    ),
  ];
}

void main() {
  testWidgets(
    'viewer request and pop clears sharing through real host teardown',
    (tester) async {
      final controller = MirrorController(TargetRepository(), automatic: false)
        ..attach(manager);
      final navigator = GlobalKey<NavigatorState>();
      await tester.pumpWidget(
        MaterialApp(
          navigatorKey: navigator,
          navigatorObservers: [MirrorNavigationObserver(controller)],
          builder: (context, child) => MirrorHost(
            controller: controller,
            onOpenViewer: () => navigator.currentState!.push(
              MaterialPageRoute<void>(
                builder: (_) => MirrorViewerPage(controller: controller),
              ),
            ),
            child: child!,
          ),
          home: const SafeMirrorSurface(
            child: Scaffold(body: Text('Daily work')),
          ),
        ),
      );
      await tester.pump();
      await tester.tap(find.text('Request screen view'));
      await tester.pumpAndSettle();
      await tester.tap(find.text('Holder target'));
      await tester.pumpAndSettle();
      expect(controller.sharing, isNotNull);
      navigator.currentState!.pop();
      expect(controller.sharing, isNull);
      await tester.pumpAndSettle();
      expect(tester.takeException(), isNull);
      await controller.accept(
        grant('pending'),
      ); // viewer cannot accept another holder's request
      expect(controller.sharing, isNull);
      await tester.pumpWidget(const SizedBox());
      controller.dispose();
    },
  );
  testWidgets(
    'unknown route and dialog stop consent before new content appears',
    (tester) async {
      final controller = MirrorController(
        FakeMirrorRepository(),
        automatic: false,
      )..attach(holder);
      final navigator = GlobalKey<NavigatorState>();
      await tester.pumpWidget(
        MaterialApp(
          navigatorKey: navigator,
          navigatorObservers: [MirrorNavigationObserver(controller)],
          builder: (context, child) => MirrorHost(
            controller: controller,
            onOpenViewer: () {},
            child: child!,
          ),
          home: const SafeMirrorSurface(
            child: Scaffold(body: Text('Daily work')),
          ),
        ),
      );
      await tester.pump();
      expect(controller.canAccept, isTrue);
      await controller.accept(grant('pending'));
      navigator.currentState!.push(
        MaterialPageRoute<void>(
          builder: (_) => const Scaffold(body: Text('Account credentials')),
        ),
      );
      expect(controller.sharing, isNull);
      await tester.pumpAndSettle();
      expect(controller.canAccept, isFalse);
      await controller.tick();
      await tester.pump();
      navigator.currentState!.pop();
      await tester.pumpAndSettle();
      expect(controller.canAccept, isTrue);
      expect(
        tester
            .widget<TextButton>(
              find.widgetWithText(TextButton, 'Allow viewing'),
            )
            .onPressed,
        isNotNull,
      );
      await controller.accept(grant('pending'));
      unawaited(
        showDialog<void>(
          context: navigator.currentContext!,
          builder: (_) => const AlertDialog(content: Text('Private dialog')),
        ),
      );
      expect(controller.sharing, isNull);
      await tester.pumpAndSettle();
      expect(controller.canAccept, isFalse);
      await tester.pumpWidget(const SizedBox());
      controller.dispose();
    },
  );

  testWidgets('unknown route stays excluded even if mistakenly wrapped', (
    tester,
  ) async {
    final controller = MirrorController(
      FakeMirrorRepository(),
      automatic: false,
    )..attach(holder);
    await tester.pumpWidget(
      MaterialApp(
        initialRoute: '/unknown',
        onGenerateRoute: (settings) => MaterialPageRoute<void>(
          settings: settings,
          builder: (_) =>
              const SafeMirrorSurface(child: Scaffold(body: Text('Unknown'))),
        ),
        builder: (_, child) => MirrorHost(
          controller: controller,
          onOpenViewer: () {},
          child: child!,
        ),
      ),
    );
    await tester.pump();
    expect(controller.canAccept, isFalse);
    await tester.pumpWidget(const SizedBox());
    controller.dispose();
  });

  testWidgets(
    'late decoder image disposed after unmount and never globally cached',
    (tester) async {
      final completion = Completer<ui.Image>();
      final recorder = ui.PictureRecorder();
      Canvas(recorder).drawColor(Colors.blue, BlendMode.src);
      final picture = recorder.endRecording();
      final decoded = picture.toImageSync(2, 2);
      picture.dispose();
      final cache = PaintingBinding.instance.imageCache;
      final initial = cache.currentSize;
      await tester.pumpWidget(
        MirrorFrameView(
          bytes: Uint8List(1),
          onInvalid: () => fail('Unexpected decode failure'),
          decoder: (_) => completion.future,
        ),
      );
      await tester.pumpWidget(const SizedBox());
      completion.complete(decoded);
      await tester.pump();
      expect(decoded.debugDisposed, isTrue);
      expect(cache.currentSize, initial);
    },
  );
}
