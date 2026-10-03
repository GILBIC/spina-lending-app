import 'dart:convert';
import 'dart:io';
import 'dart:ui' as ui;
import 'package:flutter/material.dart';
import 'package:flutter/rendering.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gilbic_mobile/src/core/auth/app_role.dart';
import 'package:gilbic_mobile/src/theme/spina_theme.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'support/android_role_fixture.dart';
import 'support/role_homes.dart';

void main() {
  for (final role in [
    AppRole.management,
    AppRole.employee,
    AppRole.collector,
    AppRole.client,
  ]) {
    for (final size in [
      const Size(320, 640),
      const Size(360, 640),
      const Size(412, 915),
      const Size(640, 360),
      const Size(800, 1280),
    ]) {
      for (final scale in size.width >= 640 ? [2.0] : [1.0, 1.3, 2.0]) {
        testWidgets(
          '${role.name} ${size.width.toInt()}x${size.height.toInt()} scale $scale all content',
          (tester) async {
            final requests = <String>[];
            await http.runWithClient(
              () async {
                await pumpAndroidRoleFixture(
                  tester,
                  size: size,
                  textScaler: TextScaler.linear(scale),
                  disableAnimations: size.width >= 640,
                  home: roleHome(role),
                );
                await tester.pumpAndSettle();
                final context = tester.element(find.byType(Scaffold).last);
                expect(
                  MediaQuery.textScalerOf(context).scale(10),
                  closeTo(scale * 10, .001),
                );
                expect(
                  Theme.of(context).colorScheme.primary,
                  SpinaTheme.light.colorScheme.primary,
                );
                expect(tester.takeException(), isNull);
                expect(
                  MediaQuery.disableAnimationsOf(context),
                  size.width >= 640,
                );
                expect(find.byType(FittedBox), findsNothing);
                await capture(tester, role, size, scale, 0);
                final scrollable = find.byType(Scrollable).last;
                for (var step = 0; step < 60; step++) {
                  final state = tester.state<ScrollableState>(scrollable);
                  if (state.position.pixels >= state.position.maxScrollExtent) {
                    break;
                  }
                  final before = state.position.pixels;
                  final viewport = state.position.viewportDimension;
                  state.position.jumpTo(
                    (before + viewport * .7).clamp(
                      0,
                      state.position.maxScrollExtent,
                    ),
                  );
                  await tester.pumpAndSettle();
                  expect(
                    state.position.pixels - before,
                    lessThan(viewport),
                    reason: 'Consecutive captures overlap actual viewport',
                  );
                  expect(
                    tester.takeException(),
                    isNull,
                    reason: 'scroll step $step',
                  );
                  await capture(tester, role, size, scale, step + 1);
                }
                expect(
                  tester
                      .state<ScrollableState>(scrollable)
                      .position
                      .extentAfter,
                  lessThan(1),
                );
                final requiredKeys = switch (role) {
                  AppRole.management => ['management-my-account-devices'],
                  AppRole.employee => ['employee-account'],
                  AppRole.collector => ['record-client-client'],
                  AppRole.client => ['client-home-support'],
                };
                for (final key in requiredKeys) {
                  final action = find.byKey(Key(key));
                  final position = tester
                      .state<ScrollableState>(scrollable)
                      .position;
                  position.jumpTo(0);
                  await tester.pumpAndSettle();
                  await tester.scrollUntilVisible(
                    action,
                    180,
                    scrollable: scrollable,
                  );
                  await tester.pumpAndSettle();
                  expect(
                    action.hitTestable(),
                    findsOneWidget,
                    reason: '${role.name} $key reachable',
                  );
                  expect(
                    tester.getSize(action).width,
                    greaterThanOrEqualTo(48),
                  );
                  expect(
                    tester.getSize(action).height,
                    greaterThanOrEqualTo(48),
                  );
                  expect(tester.takeException(), isNull);
                }
              },
              () => MockClient((request) async {
                requests.add('${request.method} ${request.url.path}');
                return http.Response('{}', 500);
              }),
            );
            expect(
              requests,
              isEmpty,
              reason: 'The fixture forbids unexpected reads and mutations',
            );
          },
        );
      }
    }
  }
}

Future<void> capture(
  WidgetTester tester,
  AppRole role,
  Size size,
  double scale,
  int step,
) async {
  for (final element in find.byType(Text).evaluate()) {
    final widget = element.widget as Text;
    final text = widget.data ?? widget.textSpan?.toPlainText() ?? '';
    if (text.contains('₱')) {
      final paragraph = find.descendant(
        of: find.byWidget(widget),
        matching: find.byType(RichText),
      );
      for (final rich in paragraph.evaluate()) {
        final render = rich.renderObject;
        if (render is RenderParagraph) {
          expect(
            render.didExceedMaxLines,
            isFalse,
            reason: 'Exact money must not truncate: $text',
          );
        }
      }
    }
  }
  final output = Platform.environment['SPINA_ANDROID_EVIDENCE_DIR'];
  if (output == null) return;
  final boundary = tester.renderObject<RenderRepaintBoundary>(
    find.byKey(const Key('android-role-capture')),
  );
  await tester.runAsync(() async {
    final picture = await boundary.toImage(pixelRatio: 1);
    final bytes = await picture.toByteData(format: ui.ImageByteFormat.png);
    picture.dispose();
    final directory = Directory(output);
    await directory.create(recursive: true);
    final filename =
        '${role.name}-${size.width.toInt()}-${scale.toStringAsFixed(1)}-$step.png';
    expect(
      File('$output/$filename').existsSync(),
      isFalse,
      reason: 'Capture names must be unique: $filename',
    );
    await File('$output/$filename').writeAsBytes(bytes!.buffer.asUint8List());
    await File('$output/matrix.jsonl').writeAsString(
      '${jsonEncode({
        'role': role.name,
        'size': [size.width, size.height],
        'textScale': scale,
        'observedScale': MediaQuery.textScalerOf(tester.element(find.byType(Scaffold).last)).scale(10) / 10,
        'fonts': ['Roboto', 'MaterialIcons'],
        'devicePixelRatio': 1,
        'disableAnimations': size.width >= 640,
        'state': 'synthetic authorized home',
        'scrollStep': step,
        'sourceBaseSHA': Platform.environment['SPINA_ANDROID_SOURCE_SHA'] ?? 'unrecorded',
        'sourceState': 'base plus capture-time raw/canonical manifest; uncommitted Task8',
        'sourceManifest': Platform.environment['SPINA_ANDROID_SOURCE_MANIFEST'],
        'scrollPixels': tester.state<ScrollableState>(find.byType(Scrollable).last).position.pixels,
        'viewportDimension': tester.state<ScrollableState>(find.byType(Scrollable).last).position.viewportDimension,
        'scrollMaxExtent': tester.state<ScrollableState>(find.byType(Scrollable).last).position.maxScrollExtent,
        'extentAfter': tester.state<ScrollableState>(find.byType(Scrollable).last).position.extentAfter,
        'flutterRevision': '84fc5cbb22',
        'screenshot': filename,
        'outcome': 'captured after clean layout check',
      })}\n',
      mode: FileMode.append,
    );
  });
}
