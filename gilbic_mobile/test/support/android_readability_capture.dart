import 'dart:convert';
import 'dart:io';
import 'dart:ui' as ui;
import 'package:flutter/material.dart';
import 'package:flutter/rendering.dart';
import 'package:flutter_test/flutter_test.dart';

Future<void> captureAndroidReadability(
  WidgetTester tester,
  String state,
) async {
  final output = Platform.environment['SPINA_ANDROID_A3_EVIDENCE_DIR'];
  if (output == null) return;
  final context = tester.element(find.byKey(const Key('android-role-capture')));
  final boundary = tester.renderObject<RenderRepaintBoundary>(
    find.byKey(const Key('android-role-capture')),
  );
  final query = MediaQuery.of(context);
  await tester.runAsync(() async {
    final picture = await boundary.toImage(pixelRatio: 1);
    final bytes = await picture.toByteData(format: ui.ImageByteFormat.png);
    picture.dispose();
    await Directory(output).create(recursive: true);
    final filename = '${state.replaceAll(' ', '-')}.png';
    await File('$output/$filename').writeAsBytes(bytes!.buffer.asUint8List());
    await File('$output/a3-captures.jsonl').writeAsString(
      '${jsonEncode({
        'state': state,
        'size': [query.size.width, query.size.height],
        'observedScale': query.textScaler.scale(10) / 10,
        'viewInsets': [query.viewInsets.left, query.viewInsets.top, query.viewInsets.right, query.viewInsets.bottom],
        'fonts': ['Roboto', 'MaterialIcons'],
        'sourceSHA': Platform.environment['SPINA_ANDROID_SOURCE_SHA'],
        'sourceState': 'base SHA plus uncommitted A3 source and tests',
        'fileHashManifest': '../a3-final-source-hashes.json',
        'flutterRevision': '84fc5cbb22',
        'screenshot': filename,
        'scope': 'synthetic production Flutter widgets; widget test, no device',
      })}\n',
      mode: FileMode.append,
    );
  });
}
