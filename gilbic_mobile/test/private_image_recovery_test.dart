import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:gilbic_mobile/src/core/media/image_recovery_controller.dart';
import 'package:gilbic_mobile/src/core/media/private_image_store.dart';
import 'package:image_picker/image_picker.dart';
import 'package:path/path.dart' as paths;

import 'image_recovery_controller_test.dart' show MemoryRecoveryStore;

const target = ImagePickContext(
  purpose: 'proof',
  target: 'loan',
  label: 'Proof',
);

class FailingCleanupImages extends PrivateImageStore {
  FailingCleanupImages({required super.directory});
  bool failCleanup = false;
  @override
  Future<void> cleanup({String? keepPath}) {
    if (failCleanup) {
      throw const FileSystemException('Synthetic delete failure');
    }
    return super.cleanup(keepPath: keepPath);
  }
}

void main() {
  late Directory temp;
  late File source;
  late PrivateImageStore images;
  late MemoryRecoveryStore journal;
  late DateTime now;

  setUp(() async {
    temp = await Directory.systemTemp.createTemp(
      'spina-private-recovery-test-',
    );
    source = await File(
      paths.join(temp.path, 'gallery.jpg'),
    ).writeAsBytes([1, 2, 3]);
    images = PrivateImageStore(
      directory: () async => Directory(paths.join(temp.path, 'private')),
    );
    now = DateTime.utc(2026, 9, 27, 12);
    journal = MemoryRecoveryStore()
      ..value = jsonEncode({
        'version': 1,
        'owner': 'account-a',
        'purpose': target.purpose,
        'target': target.target,
        'label': target.label,
        'createdAt': now.toIso8601String(),
        'path': null,
      });
  });
  tearDown(() => temp.delete(recursive: true));

  ImageRecoveryController controller({bool lost = true}) =>
      ImageRecoveryController(
        store: journal,
        images: images,
        enabled: true,
        now: () => now,
        retrieveLostData: () async => lost
            ? LostDataResponse(
                type: RetrieveType.image,
                files: [XFile(source.path)],
              )
            : LostDataResponse.empty(),
      );

  test('recovery survives another restart using the private copy', () async {
    final first = controller();
    await first.initialize('account-a');
    final ownedPath = first.recovered!.file.path;
    expect(ownedPath, isNot(source.path));
    await source.delete(); // Android/plugin may clear its unowned cache.
    final second = controller(lost: false);
    await second.initialize('account-a');
    expect(second.recovered!.file.path, ownedPath);
    expect(await second.recovered!.file.readAsBytes(), [1, 2, 3]);
  });

  test(
    'accepted bytes outlive cleanup and an uncertain upload retry',
    () async {
      final recovery = controller();
      await recovery.initialize('account-a');
      final owned = File(recovery.recovered!.file.path);
      final accepted = await recovery.takeRecovered(target);
      expect(await owned.exists(), isFalse);
      expect(journal.value, isNull);
      expect(accepted!.name, 'gallery.jpg');
      await recovery.initialize(null);
      expect(await accepted.readAsBytes(), [1, 2, 3]);
      expect(await accepted.readAsBytes(), [1, 2, 3]);
      expect(await source.exists(), isTrue);
    },
  );

  for (final action in ['discard', 'logout', 'account change', 'expiry']) {
    test('$action removes only the private recovered copy', () async {
      final recovery = controller();
      await recovery.initialize('account-a');
      final owned = File(recovery.recovered!.file.path);
      switch (action) {
        case 'discard':
          await recovery.discard();
        case 'logout':
          await recovery.initialize(null);
        case 'account change':
          await recovery.initialize('account-b');
        case 'expiry':
          now = now.add(const Duration(hours: 24));
          expect(await recovery.takeRecovered(target), isNull);
      }
      expect(recovery.recovered, isNull);
      expect(journal.value, isNull);
      expect(await owned.exists(), isFalse);
      expect(await source.exists(), isTrue);
    });
  }

  test(
    'failed journal invalidation preserves the only private evidence',
    () async {
      final recovery = controller();
      await recovery.initialize('account-a');
      final owned = File(recovery.recovered!.file.path);
      journal.failDeletes = true;
      await expectLater(recovery.takeRecovered(target), throwsStateError);
      expect(await owned.readAsBytes(), [1, 2, 3]);
      expect(journal.value, isNotNull);
    },
  );

  test(
    'logout queued during consumption never returns prior account bytes',
    () async {
      final recovery = controller();
      await recovery.initialize('account-a');
      final owned = File(recovery.recovered!.file.path);
      final entered = Completer<void>();
      final release = Completer<void>();
      journal.beforeDelete = () async {
        if (!entered.isCompleted) entered.complete();
        await release.future;
      };
      final accepting = recovery.takeRecovered(target);
      await entered.future;
      final logout = recovery.initialize(null);
      release.complete();
      expect(await accepting, isNull);
      await logout;
      expect(await owned.exists(), isFalse);
      expect(await source.exists(), isTrue);
    },
  );

  test(
    'cleanup failure is visible and retried without losing accepted bytes',
    () async {
      final failing = FailingCleanupImages(
        directory: () async => Directory(paths.join(temp.path, 'private')),
      );
      images = failing;
      final recovery = controller();
      await recovery.initialize('account-a');
      final owned = File(recovery.recovered!.file.path);
      failing.failCleanup = true;
      final accepted = await recovery.takeRecovered(target);
      expect(recovery.error, contains('could not be removed'));
      expect(journal.value, isNull);
      expect(await owned.exists(), isTrue);
      expect(await accepted!.readAsBytes(), [1, 2, 3]);
      failing.failCleanup = false;
      await controller(lost: false).initialize('account-a');
      expect(await owned.exists(), isFalse);
      expect(await accepted.readAsBytes(), [1, 2, 3]);
    },
  );

  test('discard waits for a preview read before removing its copy', () async {
    final recovery = controller();
    await recovery.initialize('account-a');
    final file = recovery.recovered!.file;
    final started = Completer<void>();
    final release = Completer<void>();
    // Hold the store's read queue so preview and discard overlap deterministically.
    final held = images.use(file, (_) async {
      started.complete();
      await release.future;
    });
    await started.future;
    final preview = recovery.preview(file);
    final discard = recovery.discard();
    release.complete();
    await held;
    expect(await preview, [1, 2, 3]);
    await discard;
    expect(await File(file.path).exists(), isFalse);
    expect(await source.exists(), isTrue);
  });
}
