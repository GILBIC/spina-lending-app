import 'package:flutter/foundation.dart';

enum CollectorRouteCacheMode { encryptedSqlCipher, onlineMemory }

CollectorRouteCacheMode collectorRouteCacheMode({
  required bool isWeb,
  required TargetPlatform platform,
}) {
  if (!isWeb &&
      (platform == TargetPlatform.android ||
          platform == TargetPlatform.iOS)) {
    return CollectorRouteCacheMode.encryptedSqlCipher;
  }
  return CollectorRouteCacheMode.onlineMemory;
}
