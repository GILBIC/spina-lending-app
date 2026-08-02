import 'package:flutter_test/flutter_test.dart';
import 'package:gilbic_mobile/src/core/payments/collection_device_sequence.dart';

void main() {
  test('memory collection sequence increases once per new draft', () async {
    final sequence = MemoryCollectionDeviceSequence(initialValue: 40);

    expect(await sequence.next(), 41);
    expect(await sequence.next(), 42);
    expect(await sequence.next(), 43);
  });
}
