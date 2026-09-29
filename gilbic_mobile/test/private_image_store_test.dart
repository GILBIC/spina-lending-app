import 'dart:async';
import 'dart:io';

import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gilbic_mobile/src/core/media/private_image_store.dart';
import 'package:image_picker/image_picker.dart';
import 'package:path/path.dart' as paths;

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  late Directory temp;
  late Directory root;
  late File original;
  late PrivateImageStore images;

  setUp(() async {
    temp = await Directory.systemTemp.createTemp('spina-owned-images-test-');
    root = Directory(paths.join(temp.path, 'private'));
    original = await File(
      paths.join(temp.path, 'gallery.jpg'),
    ).writeAsBytes([0xff, 0xd8, 0xff, 42]);
    images = PrivateImageStore(directory: () async => root);
  });
  tearDown(() async => temp.delete(recursive: true));

  test('default storage accepts a platform support-directory alias', () async {
    final support = await Directory(paths.join(temp.path, 'support')).create();
    final alias = Directory(paths.join(temp.path, 'android-user-alias'));
    await _directoryAlias(alias, support);
    const channel = MethodChannel('plugins.flutter.io/path_provider');
    TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
        .setMockMethodCallHandler(channel, (call) async {
          expect(call.method, 'getApplicationSupportDirectory');
          return alias.path;
        });
    addTearDown(() async {
      TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
          .setMockMethodCallHandler(channel, null);
      await Link(alias.path).delete();
    });

    final defaultStore = PrivateImageStore();
    final owned = await defaultStore.retain(XFile(original.path));
    expect(await owned.readAsBytes(), await original.readAsBytes());
    final restarted = PrivateImageStore();
    expect((await restarted.retain(owned)).path, owned.path);
    await restarted.cleanup();
    expect(await File(owned.path).exists(), isFalse);
    expect(await original.exists(), isTrue);
  });

  test('a redirected recovery root cannot authorize deletion', () async {
    final outside = await Directory(paths.join(temp.path, 'outside')).create();
    final outsideFile = await File(
      paths.join(outside.path, 'photo'),
    ).writeAsBytes([7, 8, 9]);
    await _directoryAlias(root, outside);
    addTearDown(() => Link(root.path).delete());
    await expectLater(images.cleanup(), throwsStateError);
    expect(await outsideFile.readAsBytes(), [7, 8, 9]);
  });

  test(
    'keeps only private copies and never removes the gallery source',
    () async {
      final owned = await images.retain(XFile(original.path));
      expect(owned.path, isNot(original.path));
      expect(owned.name, 'gallery.jpg');
      expect(await owned.readAsBytes(), [0xff, 0xd8, 0xff, 42]);
      await images.cleanup(keepPath: owned.path);
      expect(await File(owned.path).exists(), isTrue);
      await images.cleanup();
      expect(await File(owned.path).exists(), isFalse);
      expect(await original.readAsBytes(), [0xff, 0xd8, 0xff, 42]);
    },
  );

  test(
    'a second process preserves the retained copy without recopying',
    () async {
      final owned = await images.retain(XFile(original.path));
      final restarted = PrivateImageStore(directory: () async => root);
      final restored = await restarted.retain(XFile(owned.path));
      expect(restored.path, owned.path);
      expect(restored.name, 'gallery.jpg');
      await restarted.cleanup(keepPath: owned.path);
      expect(await restored.readAsBytes(), [0xff, 0xd8, 0xff, 42]);
    },
  );

  test('cleanup waits for an active consumer to finish reading', () async {
    final owned = await images.retain(XFile(original.path));
    final started = Completer<void>();
    final release = Completer<void>();
    final reading = images.use(owned, (file) async {
      started.complete();
      await release.future;
      return file.readAsBytes();
    });
    await started.future;
    final clearing = images.cleanup();
    expect(await File(owned.path).exists(), isTrue);
    release.complete();
    expect(await reading, [0xff, 0xd8, 0xff, 42]);
    await clearing;
    expect(await File(owned.path).exists(), isFalse);
  });

  test('unowned and malformed paths cannot authorize deletion', () async {
    await root.create();
    final unowned = await File(
      paths.join(root.path, 'downloads.jpg'),
    ).writeAsBytes([7]);
    final fake = await Directory(
      paths.join(root.path, 'pick_unknown'),
    ).create();
    final fakePhoto = await File(
      paths.join(fake.path, 'photo'),
    ).writeAsBytes([8]);
    await File(paths.join(fake.path, 'owner.json')).writeAsString('{bad');
    await images.cleanup(keepPath: '../gallery.jpg');
    expect(await unowned.readAsBytes(), [7]);
    expect(await fakePhoto.readAsBytes(), [8]);
    expect(await original.exists(), isTrue);
  });

  test('does not follow symbolic links when removing owned files', () async {
    final owned = await images.retain(XFile(original.path));
    await File(owned.path).delete();
    try {
      await Link(owned.path).create(original.path);
    } on FileSystemException {
      // Windows may deny link creation without Developer Mode/elevation.
      markTestSkipped(
        'Host does not permit symbolic links. Linux CI covers this.',
      );
      return;
    }
    await images.cleanup();
    expect(await original.readAsBytes(), [0xff, 0xd8, 0xff, 42]);
    expect(await Link(owned.path).exists(), isTrue);
  });
}

Future<void> _directoryAlias(Directory alias, Directory target) async {
  if (Platform.isWindows) {
    // Junctions model Android's directory alias without elevated link privileges.
    final result = await Process.run('cmd', [
      '/c',
      'mklink',
      '/J',
      alias.path,
      target.path,
    ]);
    expect(result.exitCode, 0, reason: '${result.stdout}${result.stderr}');
  } else {
    await Link(alias.path).create(target.path);
  }
}
