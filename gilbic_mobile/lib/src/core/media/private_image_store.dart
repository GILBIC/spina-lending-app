import 'dart:convert';
import 'dart:io';

import 'package:image_picker/image_picker.dart';
import 'package:path/path.dart' as paths;
import 'package:path_provider/path_provider.dart';

/// Owns only copies created here, never picker, gallery, or download paths.
/// Reads and cleanup share a queue so an active consumer finishes first.
class PrivateImageStore {
  PrivateImageStore({Future<Directory> Function()? directory})
    : _directory = directory ?? _defaultDirectory;

  final Future<Directory> Function() _directory;
  Future<void> _operations = Future<void>.value();

  static Future<Directory> _defaultDirectory() async => Directory(
    paths.join((await getApplicationSupportDirectory()).path,
        'spina_recovered_images_v1'),
  );

  Future<Directory> _root() async {
    final root = await _directory();
    await root.create(recursive: true);
    if (await FileSystemEntity.type(root.path, followLinks: false) !=
            FileSystemEntityType.directory ||
        !paths.equals(paths.normalize(root.absolute.path),
            paths.normalize(await root.resolveSymbolicLinks()))) {
      throw StateError('Private photo storage is unavailable.');
    }
    return root;
  }

  Future<XFile> retain(XFile source) => _enqueue(() async {
    final root = await _root();
    final existing = await _owned(root, Directory(paths.dirname(source.path)));
    if (existing != null && paths.equals(existing.path, source.path)) {
      return existing;
    }
    final folder = await root.createTemp('pick_');
    final photo = File(paths.join(folder.path, 'photo'));
    // Write ownership first. An interrupted copy can then be cleaned safely.
    await File(paths.join(folder.path, 'owner.json')).writeAsString(
      jsonEncode({
        'owner': 'spina-image-recovery',
        'version': 1,
        'name': paths.basename(source.name),
        'mimeType': source.mimeType,
      }),
      flush: true,
    );
    await source.saveTo(photo.path);
    return _PrivateImage(photo.path, name: paths.basename(source.name),
        mimeType: source.mimeType);
  });

  Future<T> use<T>(XFile file, Future<T> Function(XFile) read) =>
      _enqueue(() => read(file));

  Future<void> cleanup({String? keepPath}) => _enqueue(() async {
    final root = await _root();
    await for (final entry in root.list(followLinks: false)) {
      if (entry is! Directory) continue;
      final owned = await _owned(root, entry);
      if (owned == null ||
          (keepPath != null && paths.equals(owned.path, keepPath))) {
        continue;
      }
      final photo = File(owned.path);
      if (await photo.exists()) await photo.delete();
      await File(paths.join(entry.path, 'owner.json')).delete();
      // Never recurse: an unexpected entry must prevent directory removal.
      await entry.delete();
    }
  });

  Future<XFile?> _owned(Directory root, Directory folder) async {
    if (!paths.equals(paths.dirname(folder.path), root.path) ||
        !RegExp(r'^pick_[a-zA-Z0-9]+$').hasMatch(paths.basename(folder.path)) ||
        await FileSystemEntity.type(folder.path, followLinks: false) !=
            FileSystemEntityType.directory) {
      return null;
    }
    final photo = paths.join(folder.path, 'photo');
    final marker = paths.join(folder.path, 'owner.json');
    await for (final entry in folder.list(followLinks: false)) {
      if (entry is! File || (entry.path != photo && entry.path != marker)) {
        return null;
      }
    }
    if (await FileSystemEntity.type(marker, followLinks: false) !=
        FileSystemEntityType.file) return null;
    try {
      final value = jsonDecode(await File(marker).readAsString());
      if (value is! Map<String, dynamic> ||
          value['owner'] != 'spina-image-recovery' ||
          value['version'] != 1 || value['name'] is! String ||
          (value['mimeType'] != null && value['mimeType'] is! String)) {
        return null;
      }
      return _PrivateImage(photo, name: paths.basename(value['name'] as String),
          mimeType: value['mimeType'] as String?);
    } on FormatException {
      return null;
    }
  }

  Future<T> _enqueue<T>(Future<T> Function() action) {
    final next = _operations.then((_) => action());
    _operations = next.then<void>((_) {}, onError: (Object _, StackTrace __) {});
    return next;
  }
}

// Native XFile ignores its name argument for disk-backed files.
class _PrivateImage extends XFile {
  _PrivateImage(super.path, {required this.name, super.mimeType});
  @override
  final String name;
}
