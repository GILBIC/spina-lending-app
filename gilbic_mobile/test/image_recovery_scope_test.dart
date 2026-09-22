import 'dart:io';
import 'dart:async';
import 'dart:convert';
import 'dart:typed_data';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gilbic_mobile/src/core/media/image_recovery_controller.dart';
import 'package:gilbic_mobile/src/features/shared/image_recovery_scope.dart';
import 'package:image_picker/image_picker.dart';

const target = ImagePickContext(
  purpose: 'proof',
  target: 'loan-a',
  label: 'Loan A payment proof',
);
const other = ImagePickContext(
  purpose: 'proof',
  target: 'loan-b',
  label: 'Loan B payment proof',
);

// UI-only fake; durable owner and plugin behavior is exercised by controller tests.
class FakeRecovery extends ImageRecoveryController {
  FakeRecovery(this.file) : super(enabled: false);
  final XFile file;
  bool available = true;
  int taken = 0;
  int discarded = 0;
  @override
  bool get ready => true;
  @override
  bool get busy => false;
  @override
  RecoveredImagePick? get recovered =>
      available ? RecoveredImagePick(context: target, file: file) : null;
  @override
  XFile? recoveredFor(ImagePickContext value) =>
      available &&
          value.purpose == target.purpose &&
          value.target == target.target
      ? file
      : null;
  @override
  Future<XFile?> takeRecovered(ImagePickContext value) async {
    taken++;
    available = false;
    notifyListeners();
    return file;
  }

  @override
  Future<void> discard() async {
    discarded++;
    available = false;
    notifyListeners();
  }

  @override
  Future<XFile?> pick(
    ImagePickContext value,
    Future<XFile?> Function() launch,
  ) => launch();
}

class _RecoveryStore implements ImageRecoveryStore {
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

void main() {
  late Directory temp;
  late XFile file;
  setUp(() async {
    temp = await Directory.systemTemp.createTemp('spina-recovery-ui-');
    final image = File('${temp.path}/proof.png');
    // A valid one-pixel transparent PNG for actual preview decoding.
    await image.writeAsBytes(
      Uint8List.fromList([
        137,
        80,
        78,
        71,
        13,
        10,
        26,
        10,
        0,
        0,
        0,
        13,
        73,
        72,
        68,
        82,
        0,
        0,
        0,
        1,
        0,
        0,
        0,
        1,
        8,
        6,
        0,
        0,
        0,
        31,
        21,
        196,
        137,
        0,
        0,
        0,
        11,
        73,
        68,
        65,
        84,
        120,
        156,
        99,
        96,
        0,
        2,
        0,
        0,
        5,
        0,
        1,
        165,
        246,
        69,
        64,
        0,
        0,
        0,
        0,
        73,
        69,
        78,
        68,
        174,
        66,
        96,
        130,
      ]),
    );
    file = XFile.fromData(
      await image.readAsBytes(),
      path: image.path,
      name: 'proof.png',
    );
  });
  tearDown(() => temp.delete(recursive: true));

  testWidgets(
    'another form cannot replace an empty pending selection without discard',
    (tester) async {
      final store = _RecoveryStore()
        ..value = jsonEncode({
          'version': 1,
          'owner': 'actor-a',
          'purpose': 'proof',
          'target': 'loan-a',
          'label': 'Loan A payment proof',
          'createdAt': DateTime.now().toUtc().toIso8601String(),
          'path': null,
        });
      final controller = ImageRecoveryController(
        store: store,
        enabled: true,
        retrieveLostData: () async => LostDataResponse.empty(),
      );
      await controller.initialize('actor-a');
      var launches = 0;
      Object? failure;
      await tester.pumpWidget(
        MaterialApp(
          home: ImageRecoveryScope(
            controller: controller,
            child: Builder(
              builder: (context) => Scaffold(
                body: TextButton(
                  onPressed: () async {
                    try {
                      await pickRecoverableImage(
                        context,
                        recoveryContext: other,
                        pick: () async {
                          launches++;
                          return null;
                        },
                      );
                    } catch (error) {
                      failure = error;
                    }
                  },
                  child: const Text('Choose image'),
                ),
              ),
            ),
          ),
        ),
      );
      await tester.tap(find.text('Choose image'));
      await tester.pumpAndSettle();
      expect(find.text('Photo selection interrupted'), findsOneWidget);
      expect(find.textContaining('Loan A payment proof'), findsOneWidget);
      expect(launches, 0);
      await tester.tap(find.text('Keep for later'));
      await tester.pumpAndSettle();
      expect(controller.pending?.target, 'loan-a');
      expect(launches, 0);
      await tester.tap(find.text('Choose image'));
      await tester.pumpAndSettle();
      await tester.tap(find.text('Discard and choose another'));
      await tester.pumpAndSettle();
      expect(launches, 1);
      expect(failure, isNull);
      expect(controller.pending, isNull);
    },
  );

  testWidgets(
    'form action recovers a photo that arrived after an empty resume check',
    (tester) async {
      final store = _RecoveryStore()
        ..value = jsonEncode({
          'version': 1,
          'owner': 'actor-a',
          'purpose': 'proof',
          'target': 'loan-a',
          'label': 'Loan A payment proof',
          'createdAt': DateTime.now().toUtc().toIso8601String(),
          'path': null,
        });
      var response = LostDataResponse.empty();
      final controller = ImageRecoveryController(
        store: store,
        enabled: true,
        retrieveLostData: () async => response,
      );
      await controller.initialize('actor-a');
      await controller.recoverPending();
      expect(controller.recovered, isNull);
      response = LostDataResponse(type: RetrieveType.image, files: [file]);
      final recovered = Completer<void>();
      controller.addListener(() {
        if (controller.recovered != null && !recovered.isCompleted) {
          recovered.complete();
        }
      });
      var launches = 0;
      Object? failure;
      XFile? accepted;
      await tester.pumpWidget(
        MaterialApp(
          home: ImageRecoveryScope(
            controller: controller,
            child: Builder(
              builder: (context) => Scaffold(
                body: TextButton(
                  onPressed: () async {
                    try {
                      accepted = await pickRecoverableImage(
                        context,
                        recoveryContext: target,
                        pick: () async {
                          launches++;
                          return null;
                        },
                      );
                    } catch (error) {
                      failure = error;
                    }
                  },
                  child: const Text('Choose image'),
                ),
              ),
            ),
          ),
        ),
      );
      await tester.tap(find.text('Choose image'));
      await tester.runAsync(() => recovered.future);
      await tester.pumpAndSettle();
      expect(find.text('Recover photo?'), findsOneWidget);
      expect(failure, isNull);
      expect(launches, 0);
      expect(accepted, isNull);
      await tester.tap(find.text('Use photo'));
      await tester.pumpAndSettle();
      expect(accepted?.path, file.path);
      expect(store.value, isNull);
    },
  );

  testWidgets(
    'recovered photo waits for review and does not launch the picker',
    (tester) async {
      final recovery = FakeRecovery(file);
      var launches = 0;
      XFile? accepted;
      await tester.pumpWidget(
        MaterialApp(
          home: ImageRecoveryScope(
            controller: recovery,
            child: Builder(
              builder: (context) => Scaffold(
                body: TextButton(
                  onPressed: () async {
                    accepted = await pickRecoverableImage(
                      context,
                      recoveryContext: target,
                      pick: () async {
                        launches++;
                        return null;
                      },
                    );
                  },
                  child: const Text('Choose image'),
                ),
              ),
            ),
          ),
        ),
      );
      await tester.tap(find.text('Choose image'));
      await tester.pumpAndSettle();
      expect(find.text('Recover photo?'), findsOneWidget);
      expect(launches, 0);
      expect(accepted, isNull);
      await tester.tap(find.text('Keep for later'));
      await tester.pumpAndSettle();
      expect(recovery.taken, 0);
      await tester.tap(find.text('Choose image'));
      await tester.pumpAndSettle();
      await tester.tap(find.text('Use photo'));
      await tester.pumpAndSettle();
      expect(accepted?.path, file.path);
      expect(recovery.taken, 1);
      expect(launches, 0);
    },
  );

  testWidgets(
    'another loan cannot claim or silently replace the recovered photo',
    (tester) async {
      final recovery = FakeRecovery(file);
      var launches = 0;
      await tester.pumpWidget(
        MaterialApp(
          home: ImageRecoveryScope(
            controller: recovery,
            child: Builder(
              builder: (context) => Scaffold(
                body: TextButton(
                  onPressed: () async {
                    await pickRecoverableImage(
                      context,
                      recoveryContext: other,
                      pick: () async {
                        launches++;
                        return null;
                      },
                    );
                  },
                  child: const Text('Choose image'),
                ),
              ),
            ),
          ),
        ),
      );
      await tester.tap(find.text('Choose image'));
      await tester.pumpAndSettle();
      expect(
        find.text('A different form has a recovered photo'),
        findsOneWidget,
      );
      expect(recovery.taken, 0);
      expect(launches, 0);
      await tester.tap(find.text('Keep for later'));
      await tester.pumpAndSettle();
      expect(recovery.discarded, 0);
      await tester.tap(find.text('Choose image'));
      await tester.pumpAndSettle();
      await tester.tap(find.text('Discard and choose another'));
      await tester.pumpAndSettle();
      expect(recovery.discarded, 1);
      expect(launches, 1);
    },
  );
}
