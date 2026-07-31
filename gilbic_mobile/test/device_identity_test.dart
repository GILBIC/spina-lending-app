import 'package:flutter_test/flutter_test.dart';
import 'package:gilbic_mobile/src/core/device/device_identity.dart';

void main() {
  test('creates and reuses one persistent installation id', () async {
    final store = MemoryDeviceIdentityStore();
    var randomCalls = 0;
    final provider = DeviceIdentityProvider(
      store: store,
      platformResolver: () => 'ios',
      appVersionResolver: () async => '0.4.0+4',
      randomByteGenerator: (length) {
        randomCalls += 1;
        return List<int>.generate(length, (index) => index);
      },
    );

    final first = await provider.load();
    final second = await provider.load();

    expect(
      first.installationId,
      'gilbic-000102030405060708090a0b0c0d0e0f1011121314151617',
    );
    expect(second.installationId, first.installationId);
    expect(first.platform, 'ios');
    expect(first.appVersion, '0.4.0+4');
    expect(randomCalls, 1);
  });

  test('reuses an existing installation id without regeneration', () async {
    final store = MemoryDeviceIdentityStore()
      ..value = 'gilbic-existing-installation';
    var randomCalls = 0;
    final provider = DeviceIdentityProvider(
      store: store,
      platformResolver: () => 'android',
      appVersionResolver: () async => '0.4.0+4',
      randomByteGenerator: (length) {
        randomCalls += 1;
        return List<int>.filled(length, 1);
      },
    );

    final identity = await provider.load();

    expect(identity.installationId, 'gilbic-existing-installation');
    expect(identity.platform, 'android');
    expect(randomCalls, 0);
  });
}
