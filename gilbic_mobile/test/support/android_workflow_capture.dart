import 'dart:convert';
import 'dart:io';
import 'dart:ui' as ui;
import 'package:flutter/material.dart';
import 'package:flutter/rendering.dart';
import 'package:flutter_test/flutter_test.dart';

// Actual Navigator pixels, including pushed pages, menus and dialogs. This is
// test evidence only and never controls the product or initiates a command.
Future<void> captureAndroidWorkflow(WidgetTester tester, String state) async {
  expect(tester.takeException(), isNull, reason: state);
  final output = Platform.environment['SPINA_ANDROID_EVIDENCE_DIR'];
  if (output == null) return;
  final finder = find.byKey(const Key('android-role-capture'));
  final query = MediaQuery.of(tester.element(finder));
  final boundary = tester.renderObject<RenderRepaintBoundary>(finder);
  final visibleText = <String>[];
  final contentScaleSamples = <Map<String, Object>>[];
  final appBarScaleSamples = <Map<String, Object>>[];
  final textFinder = find.byWidgetPredicate(
    (widget) => widget is Text || widget is SelectableText,
  );
  final dialog = find.byType(AlertDialog);
  final activeText = dialog.evaluate().isEmpty
      ? textFinder
      : find.descendant(of: dialog, matching: textFinder);
  for (final element in activeText.evaluate()) {
    final render = element.renderObject;
    if (render is RenderBox && render.hasSize && render.attached) {
      final bounds = render.localToGlobal(Offset.zero) & render.size;
      if (bounds.overlaps(Offset.zero & query.size)) {
        final widget = element.widget;
        final text = widget is Text
            ? (widget.data ?? widget.textSpan!.toPlainText())
            : ((widget as SelectableText).data ??
                  widget.textSpan!.toPlainText());
        visibleText.add(text);
        final scale = MediaQuery.textScalerOf(element).scale(10) / 10;
        // Material AppBar titles use a local scaler clamp. Measure the actual
        // workflow body/control descendants without changing that behavior.
        if (element.findAncestorWidgetOfExactType<AppBar>() != null) {
          appBarScaleSamples.add({'text': text, 'scale': scale});
        } else {
          contentScaleSamples.add({'text': text, 'scale': scale});
          expect(
            scale,
            query.textScaler.scale(10) / 10,
            reason: '$state actual content/control descendant scale',
          );
        }
      }
    }
  }
  final scrolls = [
    for (final element in _activeScrollables().evaluate())
      if ((element as StatefulElement).state is ScrollableState)
        {
          'pixels': ((element).state as ScrollableState).position.pixels,
          'maxScrollExtent':
              ((element).state as ScrollableState).position.maxScrollExtent,
          'extentAfter':
              ((element).state as ScrollableState).position.extentAfter,
          'viewportDimension':
              ((element).state as ScrollableState).position.viewportDimension,
        },
  ];
  expect(
    contentScaleSamples,
    isNotEmpty,
    reason: '$state measures visible workflow content/control descendants',
  );
  await tester.runAsync(() async {
    final picture = await boundary.toImage(pixelRatio: 1);
    final bytes = await picture.toByteData(format: ui.ImageByteFormat.png);
    picture.dispose();
    await Directory(output).create(recursive: true);
    final filename = '${state.replaceAll(RegExp(r'[^a-zA-Z0-9_.-]'), '-')}.png';
    expect(
      File('$output/$filename').existsSync(),
      isFalse,
      reason: 'Capture names must be unique: $filename',
    );
    await File('$output/$filename').writeAsBytes(bytes!.buffer.asUint8List());
    await File('$output/workflows.jsonl').writeAsString(
      '${jsonEncode({
        'state': state,
        'size': [query.size.width, query.size.height],
        'observedScale': query.textScaler.scale(10) / 10,
        'viewInsetsBottom': query.viewInsets.bottom,
        'visibleText': visibleText,
        'contentScaleSamples': contentScaleSamples,
        'materialAppBarScaleSamples': appBarScaleSamples,
        'scrollBounds': scrolls,
        'scrollScope': dialog.evaluate().isEmpty ? 'active workflow' : 'AlertDialog descendants only',
        'fonts': ['Roboto', 'MaterialIcons'],
        'sourceBaseSHA': Platform.environment['SPINA_ANDROID_SOURCE_SHA'],
        'sourceState': 'base plus capture-time raw/canonical manifest; uncommitted Task8',
        'sourceManifest': Platform.environment['SPINA_ANDROID_SOURCE_MANIFEST'],
        'flutterRevision': '84fc5cbb22',
        'screenshot': filename,
        'outcome': 'clean widget layout; test outcome in scoped receipt',
        'scope': 'synthetic actual production widgets; native gate pending root',
      })}\n',
      mode: FileMode.append,
    );
  });
}

Future<void> captureAndroidWorkflowScroll(
  WidgetTester tester,
  String state,
) async {
  await captureAndroidWorkflow(tester, '$state-initial');
  final scrolls = _activeScrollables().evaluate().toList();
  for (var index = 0; index < scrolls.length; index++) {
    if (!scrolls[index].mounted) continue;
    final scroll = (scrolls[index] as StatefulElement).state as ScrollableState;
    final initial = scroll.position.pixels;
    scroll.position.jumpTo(0);
    await _pumpActiveWorkflow(tester);
    await captureAndroidWorkflow(tester, '$state-scroll$index-top');
    for (var step = 0; step < 60 && scroll.position.extentAfter > .5; step++) {
      scroll.position.jumpTo(
        (scroll.position.pixels + scroll.position.viewportDimension * .7).clamp(
          0,
          scroll.position.maxScrollExtent,
        ),
      );
      await _pumpActiveWorkflow(tester);
      await captureAndroidWorkflow(tester, '$state-scroll$index-${step + 1}');
    }
    expect(
      scroll.position.extentAfter,
      lessThan(1),
      reason: '$state reaches scroll end',
    );
    scroll.position.jumpTo(initial.clamp(0, scroll.position.maxScrollExtent));
    await _pumpActiveWorkflow(tester);
  }
}

Finder _activeScrollables() {
  final dialog = find.byType(AlertDialog);
  return dialog.evaluate().isEmpty
      ? find.byType(Scrollable)
      : find.descendant(of: dialog, matching: find.byType(Scrollable));
}

Future<void> _pumpActiveWorkflow(WidgetTester tester) async {
  if (find.byType(AlertDialog).evaluate().isNotEmpty) {
    // A saved-result modal can cover the submitting spinner while its caller
    // awaits dismissal. Finish modal entrance/scroll frames without waiting for
    // that underlying indeterminate animation to stop.
    await tester.pump(const Duration(milliseconds: 300));
  } else {
    await tester.pumpAndSettle();
  }
}

Future<void> checkAndroidWorkflowSemantics(WidgetTester tester) async {
  await expectLater(tester, meetsGuideline(androidTapTargetGuideline));
  await expectLater(tester, meetsGuideline(labeledTapTargetGuideline));
  await expectLater(tester, meetsGuideline(textContrastGuideline));
}

// A long Text being in the tree does not prove its final consequence is visible.
Future<void> expectAndroidDialogConsequenceVisible(
  WidgetTester tester,
  String finalWords,
) async {
  final dialog = find.byType(AlertDialog);
  final scroll = find.descendant(of: dialog, matching: find.byType(Scrollable));
  expect(scroll, findsOneWidget);
  final position = tester.state<ScrollableState>(scroll).position;
  position.jumpTo(position.maxScrollExtent);
  await _pumpActiveWorkflow(tester);
  final content = find.descendant(
    of: dialog,
    matching: find.textContaining(finalWords),
  );
  final rich = find.descendant(of: content, matching: find.byType(RichText));
  final paragraph = tester.renderObject<RenderParagraph>(rich);
  final text = paragraph.text.toPlainText();
  final boxes = paragraph.getBoxesForSelection(
    TextSelection(
      baseOffset: text.lastIndexOf(finalWords),
      extentOffset: text.length,
    ),
  );
  expect(boxes, isNotEmpty);
  final last = boxes.last.toRect().shift(paragraph.localToGlobal(Offset.zero));
  final viewport = tester.getRect(scroll);
  expect(
    viewport.contains(last.center),
    isTrue,
    reason: 'Final dialog consequence is visible inside its own viewport',
  );
  expect(last.bottom, lessThanOrEqualTo(viewport.bottom + .5));
}
