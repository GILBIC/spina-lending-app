import 'dart:io';

/// Check every artifact before creating any asynchronous font-loading work.
List<File> androidFixtureFontFiles(Map<String, dynamic> configuration) {
  final root = configuration['flutterRoot'];
  if (root is! String || root.isEmpty) {
    throw StateError('Flutter SDK path unavailable in package_config.json');
  }
  final directory = Uri.parse(
    root.endsWith('/') ? root : '$root/',
  ).resolve('bin/cache/artifacts/material_fonts/');
  final files = [
    'Roboto-Regular.ttf',
    'Roboto-Medium.ttf',
    'Roboto-Bold.ttf',
    'Roboto-Black.ttf',
    'Roboto-Light.ttf',
    'MaterialIcons-Regular.otf',
  ].map((name) => File.fromUri(directory.resolve(name))).toList();
  final missing = files.where((file) => !file.existsSync()).toList();
  if (missing.isNotEmpty) {
    throw StateError(
      'Android fixture fonts unavailable: ${missing.map((file) => file.path).join(', ')}. '
      'Run flutter precache --universal with the pinned Flutter SDK before testing.',
    );
  }
  return files;
}
