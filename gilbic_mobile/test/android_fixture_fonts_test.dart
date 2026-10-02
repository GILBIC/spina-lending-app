import 'dart:io';
import 'package:flutter_test/flutter_test.dart';
import 'support/android_fixture_fonts.dart';

void main() {
  late Directory sdk;
  setUp(() async {
    sdk = await Directory.systemTemp.createTemp('synthetic-flutter-fonts-');
  });
  tearDown(() async {
    await sdk.delete(recursive: true);
  });
  test(
    'fresh SDK without material fonts fails before creating asynchronous font futures',
    () {
      expect(
        () => androidFixtureFontFiles({'flutterRoot': sdk.uri.toString()}),
        throwsA(
          isA<StateError>().having(
            (e) => e.toString(),
            'action',
            contains('flutter precache --universal'),
          ),
        ),
      );
    },
  );
  test(
    'all expected pinned SDK font files are verified before loading',
    () async {
      final folder = Directory(
        '${sdk.path}/bin/cache/artifacts/material_fonts',
      );
      await folder.create(recursive: true);
      for (final name in [
        'roboto-regular.ttf',
        'roboto-medium.ttf',
        'roboto-bold.ttf',
        'roboto-black.ttf',
        'roboto-light.ttf',
        'materialicons-regular.otf',
      ]) {
        await File('${folder.path}/$name').writeAsBytes([1]);
      }
      final files = androidFixtureFontFiles({
        'flutterRoot': sdk.uri.toString(),
      });
      expect(files.length, 6);
      expect(files.first.path.endsWith('roboto-regular.ttf'), isTrue);
      expect(files.last.path.endsWith('materialicons-regular.otf'), isTrue);
      await files[3].delete();
      expect(
        () => androidFixtureFontFiles({'flutterRoot': sdk.uri.toString()}),
        throwsStateError,
      );
    },
  );
}
