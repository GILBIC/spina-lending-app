import 'package:flutter_test/flutter_test.dart';
import 'package:gilbic_mobile/src/core/payments/collection_device_sequence.dart';

void main() {
  test('memory collection sequence increases once per new draft', () async {
    final sequence = MemoryCollectionDeviceSequence(initialValue: 40);

    expect(await sequence.next(), 41);
    expect(await sequence.next(), 42);
    expect(await sequence.next(), 43);
  });

  test('reserve atomically assigns disjoint consecutive blocks', () async {
    final sequence = MemoryCollectionDeviceSequence(initialValue: 40);

    final starts = await Future.wait<int>(<Future<int>>[
      sequence.reserve(3),
      sequence.reserve(2),
      sequence.next(),
    ]);

    expect(starts, <int>[41, 44, 46]);
    expect(await sequence.next(), 47);
  });

  test('reserve rejects empty blocks', () async {
    final sequence = MemoryCollectionDeviceSequence();

    await expectLater(sequence.reserve(0), throwsArgumentError);
  });
}
