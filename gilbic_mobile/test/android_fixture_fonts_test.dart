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
        'Roboto-Regular.ttf',
        'Roboto-Medium.ttf',
        'Roboto-Bold.ttf',
        'Roboto-Black.ttf',
        'Roboto-Light.ttf',
        'MaterialIcons-Regular.otf',
      ]) {
        await File('${folder.path}/$name').writeAsBytes([1]);
      }
      final files = androidFixtureFontFiles({
        'flutterRoot': sdk.uri.toString(),
      });
      expect(files.length, 6);
      expect(files.first.path.endsWith('Roboto-Regular.ttf'), isTrue);
      expect(files.last.path.endsWith('MaterialIcons-Regular.otf'), isTrue);
      await files[3].delete();
      expect(
        () => androidFixtureFontFiles({'flutterRoot': sdk.uri.toString()}),
        throwsStateError,
      );
    },
  );
}
