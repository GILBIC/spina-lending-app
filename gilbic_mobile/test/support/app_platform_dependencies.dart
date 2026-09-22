import 'package:flutter_test/flutter_test.dart';
import 'package:gilbic_mobile/src/core/device/device_identity.dart';
import 'package:gilbic_mobile/src/core/media/image_recovery_controller.dart';

DeviceIdentityProvider testAppDeviceIdentity() => DeviceIdentityProvider(
  store: MemoryDeviceIdentityStore()..value = 'test-app-installation',
  appVersionResolver: () async => 'test',
);

/// App-shell tests still exercise owner binding without native plugin I/O.
ImageRecoveryController testAppImageRecovery() {
  final controller = ImageRecoveryController(enabled: false);
  addTearDown(controller.dispose);
  return controller;
}
