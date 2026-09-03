import 'dart:async';

import 'package:flutter_secure_storage/flutter_secure_storage.dart';

abstract interface class CollectionDeviceSequence {
  Future<int> next();

  /// Atomically reserve [count] consecutive values and return the first.
  Future<int> reserve(int count);
}

class SecureCollectionDeviceSequence implements CollectionDeviceSequence {
  SecureCollectionDeviceSequence({FlutterSecureStorage? storage})
    : _storage = storage ?? FlutterSecureStorage();

  static const String _sequenceKey = 'gilbic.collection_device_sequence.v1';

  final FlutterSecureStorage _storage;
  Future<void> _reservationTail = Future<void>.value();

  @override
  Future<int> next() => reserve(1);

  @override
  Future<int> reserve(int count) {
    if (count <= 0) {
      return Future<int>.error(
        ArgumentError.value(count, 'count', 'must be greater than zero'),
      );
    }
    final previous = _reservationTail;
    final reservationComplete = Completer<void>();
    _reservationTail = reservationComplete.future;
    return () async {
      await previous;
      try {
        final stored = await _storage.read(key: _sequenceKey);
        final current = int.tryParse(stored?.trim() ?? '') ?? 0;
        final firstValue = current + 1;
        await _storage.write(
          key: _sequenceKey,
          value: (current + count).toString(),
        );
        return firstValue;
      } finally {
        reservationComplete.complete();
      }
    }();
  }
}

class MemoryCollectionDeviceSequence implements CollectionDeviceSequence {
  MemoryCollectionDeviceSequence({int initialValue = 0})
    : _value = initialValue;

  int _value;

  @override
  Future<int> next() => reserve(1);

  @override
  Future<int> reserve(int count) async {
    if (count <= 0) {
      throw ArgumentError.value(count, 'count', 'must be greater than zero');
    }
    final firstValue = _value + 1;
    _value += count;
    return firstValue;
  }
}
