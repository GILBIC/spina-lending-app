import 'dart:convert';

import 'package:flutter/foundation.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:image_picker/image_picker.dart';
import 'package:path/path.dart' as paths;

class ImagePickContext {
  const ImagePickContext({
    required this.purpose,
    required this.target,
    required this.label,
  });

  final String purpose;
  final String target;
  final String label;

  bool matches(ImagePickContext other) =>
      purpose == other.purpose && target == other.target;
}

class RecoveredImagePick {
  const RecoveredImagePick({required this.context, required this.file});

  final ImagePickContext context;
  final XFile file;
}

abstract interface class ImageRecoveryStore {
  Future<String?> read();
  Future<void> write(String value);
  Future<void> delete();
}

class SecureImageRecoveryStore implements ImageRecoveryStore {
  SecureImageRecoveryStore({FlutterSecureStorage? storage})
    : _storage = storage ?? const FlutterSecureStorage();

  static const _key = 'gilbic.image_picker_recovery.v1';
  final FlutterSecureStorage _storage;

  @override
  Future<String?> read() => _storage.read(key: _key);

  @override
  Future<void> write(String value) => _storage.write(key: _key, value: value);

  @override
  Future<void> delete() => _storage.delete(key: _key);
}

/// Coordinates the Android plugin's single, destructively read lost-data slot.
/// This holds a photo selection only; callers still validate it and ask the user
/// to submit it. It never uploads, changes financial records, or deletes files.
class ImageRecoveryController extends ChangeNotifier {
  ImageRecoveryController({
    ImageRecoveryStore? store,
    Future<LostDataResponse> Function()? retrieveLostData,
    bool? enabled,
    DateTime Function()? now,
  }) : _store = store ?? SecureImageRecoveryStore(),
       _retrieveLostData = retrieveLostData ?? ImagePicker().retrieveLostData,
       _enabled =
           enabled ??
           (!kIsWeb && defaultTargetPlatform == TargetPlatform.android),
       _now = now ?? DateTime.now;

  final ImageRecoveryStore _store;
  final Future<LostDataResponse> Function() _retrieveLostData;
  final bool _enabled;
  final DateTime Function() _now;
  Future<void> _operations = Future<void>.value();
  Future<void>? _initializing;
  String? _owner;
  bool _ownerSet = false;
  bool _ready = false;
  bool _busy = false;
  bool _retrieved = false;
  bool _disposed = false;
  int _revision = 0;
  String? _error;
  RecoveredImagePick? _recovered;
  DateTime? _recoveredCreatedAt;

  bool get ready => _ready;
  bool get busy => _busy;
  String? get error => _error;
  RecoveredImagePick? get recovered => _recovered;

  /// Invalidates the previous scope immediately while the host resolves the
  /// current device/session. Does not consume Android data or erase a journal
  /// that may still belong to the account being restored after process death.
  void suspend() {
    if (_disposed) return;
    _revision++;
    _ownerSet = false;
    _owner = null;
    _ready = false;
    _initializing = null;
    _recovered = null;
    _recoveredCreatedAt = null;
    _error = null;
    _changed();
  }

  Future<void> initialize(String? owner) {
    if (_disposed) return Future<void>.value();
    if (_ownerSet && _owner == owner && (_ready || _initializing != null)) {
      return _initializing ?? Future<void>.value();
    }
    // Invalidate synchronously, before asynchronous storage/plugin calls. A
    // previous account must disappear even while an external picker is open.
    final revision = ++_revision;
    _ownerSet = true;
    _owner = owner;
    _ready = false;
    _recovered = null;
    _recoveredCreatedAt = null;
    _error = null;
    _changed();
    final initializing = _enqueue(() async {
      try {
        if (_enabled) await _restore(owner, revision);
        if (_current(revision)) _ready = true;
      } catch (_) {
        if (_current(revision)) {
          _error =
              'Photo recovery is unavailable. Please restart Spina and try again.';
        }
      } finally {
        if (_current(revision)) {
          _initializing = null;
          _changed();
        }
      }
    });
    _initializing = initializing;
    return initializing;
  }

  Future<void> _restore(String? owner, int revision) async {
    final raw = await _store.read();
    LostDataResponse? lost;
    if (!_retrieved) {
      _retrieved = true;
      try {
        lost = await _retrieveLostData();
      } catch (_) {
        if (_current(revision)) {
          _error =
              'The previous photo could not be recovered. Please choose it again.';
        }
      }
    }
    if (!_current(revision)) return;
    final journal = _ImagePickJournal.parse(raw, _now());
    if (journal == null || owner == null || journal.owner != owner) {
      if (raw != null) await _store.delete();
      return;
    }

    XFile? file;
    if (journal.path != null) {
      file = XFile(journal.path!);
    } else if (lost != null && !lost.isEmpty) {
      final files =
          lost.files ?? (lost.file == null ? <XFile>[] : [lost.file!]);
      if (lost.exception == null &&
          lost.type == RetrieveType.image &&
          files.length == 1) {
        file = files.single;
      } else {
        _error =
            'The previous photo could not be recovered. Please choose it again.';
      }
    }
    if (file == null || !await _readable(file)) {
      if (_current(revision)) await _store.delete();
      return;
    }
    if (!_current(revision)) return;
    // Persist the recovered path before showing it: the plugin cache is already
    // consumed, and another restart must not silently lose this selection.
    await _store.write(journal.withPath(file.path).encode());
    if (_current(revision)) {
      _recovered = RecoveredImagePick(context: journal.context, file: file);
      _recoveredCreatedAt = journal.createdAt;
    }
  }

  XFile? recoveredFor(ImagePickContext context) {
    if (!_ready || _owner == null || _disposed) return null;
    final recovered = _recovered;
    return recovered != null && recovered.context.matches(context)
        ? recovered.file
        : null;
  }

  Future<XFile?> takeRecovered(ImagePickContext context) {
    final revision = _revision;
    return _enqueue(() async {
      if (!_current(revision)) return null;
      final file = recoveredFor(context);
      if (file == null) return null;
      // A failed delete must not give the same photo to a second restart.
      if (_enabled) await _store.delete();
      if (!_current(revision)) return null;
      final createdAt = _recoveredCreatedAt;
      final now = _now();
      final fresh =
          createdAt != null &&
          !createdAt.isAfter(now) &&
          now.difference(createdAt) < const Duration(hours: 24);
      _recovered = null;
      _recoveredCreatedAt = null;
      if (!fresh) {
        _error = 'The recovered photo has expired. Please choose it again.';
      }
      _changed();
      return fresh ? file : null;
    });
  }

  Future<void> discard() {
    final revision = _revision;
    return _enqueue(() async {
      if (!_current(revision)) return;
      if (_enabled) await _store.delete();
      if (!_current(revision)) return;
      _recovered = null;
      _recoveredCreatedAt = null;
      _error = null;
      _changed();
    });
  }

  Future<XFile?> pick(
    ImagePickContext context,
    Future<XFile?> Function() launch,
  ) async {
    if (!_ready || _owner == null || _disposed) {
      throw StateError('Please sign in and wait for photo recovery to finish.');
    }
    if (_busy) throw StateError('A photo selection is already open.');
    if (_recovered != null) {
      throw StateError('Review or discard the recovered photo first.');
    }
    if (!_ImagePickJournal.validContext(context)) {
      throw StateError('This photo selection has no valid destination.');
    }
    final revision = _revision;
    final owner = _owner!;
    _busy = true;
    _error = null;
    _changed();
    try {
      if (_enabled) {
        await _enqueue(() async {
          if (!_current(revision)) return;
          try {
            await _store.write(
              _ImagePickJournal(
                owner: owner,
                context: context,
                createdAt: _now().toUtc(),
              ).encode(),
            );
          } catch (_) {
            if (_current(revision)) {
              _error =
                  'The photo could not be prepared safely. Please try again.';
            }
            throw StateError(
              'The photo could not be prepared safely. Please try again.',
            );
          }
        });
      }
      if (!_current(revision)) return null;
      XFile? file;
      try {
        file = await launch();
      } finally {
        if (_enabled) {
          await _enqueue(() async {
            if (_current(revision)) await _store.delete();
          });
        }
      }
      return _current(revision) ? file : null;
    } finally {
      _busy = false;
      _changed();
    }
  }

  Future<T> _enqueue<T>(Future<T> Function() action) {
    final next = _operations.then((_) => action());
    // A failed storage operation must not poison every subsequent operation.
    _operations = next.then<void>(
      (_) {},
      onError: (Object _, StackTrace __) {},
    );
    return next;
  }

  bool _current(int revision) => !_disposed && _revision == revision;

  void _changed() {
    if (!_disposed) notifyListeners();
  }

  static Future<bool> _readable(XFile file) async {
    if (!_ImagePickJournal.validPath(file.path)) return false;
    try {
      return await file.length() > 0;
    } catch (_) {
      return false;
    }
  }

  @override
  void dispose() {
    _disposed = true;
    _revision++;
    super.dispose();
  }
}

class _ImagePickJournal {
  const _ImagePickJournal({
    required this.owner,
    required this.context,
    required this.createdAt,
    this.path,
  });

  final String owner;
  final ImagePickContext context;
  final DateTime createdAt;
  final String? path;

  _ImagePickJournal withPath(String value) => _ImagePickJournal(
    owner: owner,
    context: context,
    createdAt: createdAt,
    path: value,
  );

  String encode() => jsonEncode({
    'version': 1,
    'owner': owner,
    'purpose': context.purpose,
    'target': context.target,
    'label': context.label,
    'createdAt': createdAt.toIso8601String(),
    'path': path,
  });

  static bool validContext(ImagePickContext context) =>
      _nonempty(context.purpose, 128) &&
      _nonempty(context.target, 1024) &&
      _nonempty(context.label, 512);

  static bool validPath(String value) =>
      _nonempty(value, 4096) &&
      !value.contains('\u0000') &&
      !value.contains('://') &&
      (paths.posix.isAbsolute(value) || paths.windows.isAbsolute(value));

  static bool _nonempty(Object? value, int maxLength) =>
      value is String && value.trim().isNotEmpty && value.length <= maxLength;

  static _ImagePickJournal? parse(String? raw, DateTime now) {
    if (raw == null) return null;
    try {
      final value = jsonDecode(raw);
      if (value is! Map<String, dynamic> ||
          value['version'] != 1 ||
          !_nonempty(value['owner'], 32768) ||
          value['purpose'] is! String ||
          value['target'] is! String ||
          value['label'] is! String ||
          value['createdAt'] is! String) {
        return null;
      }
      final context = ImagePickContext(
        purpose: value['purpose'] as String,
        target: value['target'] as String,
        label: value['label'] as String,
      );
      final created = DateTime.tryParse(value['createdAt'] as String);
      final filePath = value['path'];
      if (!validContext(context) ||
          created == null ||
          created.isAfter(now) ||
          now.difference(created) >= const Duration(hours: 24) ||
          (filePath != null && (filePath is! String || !validPath(filePath)))) {
        return null;
      }
      return _ImagePickJournal(
        owner: value['owner'] as String,
        context: context,
        createdAt: created,
        path: filePath as String?,
      );
    } on FormatException {
      return null;
    }
  }
}
