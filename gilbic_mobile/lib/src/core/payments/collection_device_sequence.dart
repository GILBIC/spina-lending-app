import 'package:flutter_secure_storage/flutter_secure_storage.dart';

abstract interface class CollectionDeviceSequence {
  Future<int> next();
}

class SecureCollectionDeviceSequence implements CollectionDeviceSequence {
  SecureCollectionDeviceSequence({FlutterSecureStorage? storage})
      : _storage = storage ?? FlutterSecureStorage();

  static const String _sequenceKey = 'gilbic.collection_device_sequence.v1';

  final FlutterSecureStorage _storage;

  @override
  Future<int> next() async {
    final stored = await _storage.read(key: _sequenceKey);
    final current = int.tryParse(stored?.trim() ?? '') ?? 0;
    final nextValue = current + 1;
    await _storage.write(key: _sequenceKey, value: nextValue.toString());
    return nextValue;
  }
}

class MemoryCollectionDeviceSequence implements CollectionDeviceSequence {
  MemoryCollectionDeviceSequence({int initialValue = 0}) : _value = initialValue;

  int _value;

  @override
  Future<int> next() async {
    _value += 1;
    return _value;
  }
}
