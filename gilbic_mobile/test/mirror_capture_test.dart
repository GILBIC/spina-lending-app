import 'package:gilbic_mobile/src/features/mirror/mirror_host.dart';
import 'dart:typed_data';
import 'dart:ui' as ui;
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gilbic_mobile/src/core/mirror/mirror_controller.dart';
import 'package:gilbic_mobile/src/core/mirror/mirror_repository.dart';
import 'package:gilbic_mobile/src/features/mirror/safe_mirror_surface.dart';
import 'mirror_controller_test.dart' show FakeMirrorRepository, holder;

class CapturingRepository extends FakeMirrorRepository {
  Uint8List? captured;
  @override
  Future<void> publish(
    MirrorSession session,
    int sequence,
    Uint8List bytes, {
    required bool Function() stillCurrent,
  }) async {
    if (stillCurrent()) captured = Uint8List.fromList(bytes);
  }
}

void main() {
  testWidgets('real capture encodes only permitted subtree within PNG bounds', (
    tester,
  ) async {
    tester.binding.handleAppLifecycleStateChanged(AppLifecycleState.resumed);
    final api = CapturingRepository();
    final controller = MirrorController(api, automatic: false)..attach(holder);
    await tester.pumpWidget(
      MaterialApp(
        navigatorObservers: [MirrorNavigationObserver(controller)],
        builder: (_, child) => MirrorHost(
          controller: controller,
          onOpenViewer: () {},
          child: child!,
        ),
        home: Scaffold(
          body: Column(
            children: [
              const SizedBox(
                height: 80,
                width: double.infinity,
                child: ColoredBox(
                  color: Color(0xffff00ff),
                  child: Text('PRIVATE OUTSIDE CONTROL'),
                ),
              ),
              const Expanded(
                child: SafeMirrorSurface(
                  child: ColoredBox(
                    color: Color(0xff0000ff),
                    child: Center(child: Text('Synthetic permitted work')),
                  ),
                ),
              ),
            ],
          ),
        ),
      ),
    );
    await tester.pumpAndSettle();
    expect(controller.canReady, isTrue);
    await controller.tick();
    await tester.pump();
    final safeSize = tester.getSize(find.byType(SafeMirrorSurface));
    await tester.runAsync(() async {
      await controller.tick();
      expect(api.captured, isNotNull);
      final bytes = api.captured!;
      expect(bytes.length, lessThanOrEqualTo(524288));
      expect(bytes.take(8), [137, 80, 78, 71, 13, 10, 26, 10]);
      final codec = await ui.instantiateImageCodec(bytes);
      final frame = await codec.getNextFrame();
      try {
        expect(frame.image.width, 720);
        expect(
          frame.image.height,
          (safeSize.height * 720 / safeSize.width).ceil(),
        ); // Only the permitted subtree; excludes the private80px control and indicator.
        final pixels = await frame.image.toByteData(
          format: ui.ImageByteFormat.rawRgba,
        );
        expect(pixels!.buffer.asUint8List().take(4), [0, 0, 255, 255]);
      } finally {
        frame.image.dispose();
        codec.dispose();
        bytes.fillRange(0, bytes.length, 0);
      }
    });
    await tester.pumpWidget(const SizedBox());
    controller.dispose();
  });
}
