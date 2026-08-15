import 'dart:convert';

import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/config/api_config.dart';
import 'package:gilbic_mobile/src/core/device/device_identity.dart';
import 'package:gilbic_mobile/src/core/network/spina_api.dart';
import 'package:http/http.dart' as http;

class AccountProfile {
  const AccountProfile({
    required this.id,
    required this.username,
    required this.fullName,
    required this.role,
    required this.status,
    this.email,
  });

  final String id;
  final String username;
  final String fullName;
  final String role;
  final String status;
  final String? email;
}

class AccountDevice {
  const AccountDevice({
    required this.id,
    required this.platform,
    required this.status,
    required this.registeredAt,
    required this.isCurrent,
    this.appVersion,
    this.lastSeenAt,
  });

  final String id;
  final String platform;
  final String? appVersion;
  final String status;
  final DateTime registeredAt;
  final DateTime? lastSeenAt;
  final bool isCurrent;

  AccountDevice copyWith({String? status}) {
    return AccountDevice(
      id: id,
      platform: platform,
      appVersion: appVersion,
      status: status ?? this.status,
      registeredAt: registeredAt,
      lastSeenAt: lastSeenAt,
      isCurrent: isCurrent,
    );
  }
}

class AccountOverview {
  const AccountOverview({
    required this.profile,
    required this.devices,
  });

  final AccountProfile profile;
  final List<AccountDevice> devices;

  AccountOverview replaceDevice(AccountDevice replacement) {
    return AccountOverview(
      profile: profile,
      devices: devices
          .map((device) => device.id == replacement.id ? replacement : device)
          .toList(growable: false),
    );
  }
}

abstract interface class AccountRepository {
  Future<AccountOverview> fetch(UserSession session);

  Future<AccountDevice> revokeDevice(
    UserSession session,
    String deviceId,
  );
}

class SpinaAccountRepository implements AccountRepository {
  SpinaAccountRepository({
    http.Client? client,
    DeviceIdentityProvider? deviceIdentityProvider,
    Uri? accountUri,
  })  : _client = client ?? http.Client(),
        _deviceIdentityProvider =
            deviceIdentityProvider ?? DeviceIdentityProvider(),
        _accountUri = accountUri ?? ApiConfig.endpoint('/api/mobile/v1/account');

  final http.Client _client;
  final DeviceIdentityProvider _deviceIdentityProvider;
  final Uri _accountUri;

  @override
  Future<AccountOverview> fetch(UserSession session) async {
    final identity = await _loadDeviceIdentity();
    final response = await _send(
      () => _client.get(
        _accountUri,
        headers: _headers(session, identity),
      ),
      offlineMessage:
          'Gilbic could not load your account. Check the connection and try again.',
    );
    final data = _data(response);
    final profile = stringMap(data['profile']);
    final devices = data['devices'];
    if (profile.isEmpty || devices is! Iterable) {
      throw const SpinaApiException(
        'The SPINA server returned incomplete account information.',
      );
    }
    return AccountOverview(
      profile: _profile(profile),
      devices: devices
          .map((item) => _device(stringMap(item)))
          .toList(growable: false),
    );
  }

  @override
  Future<AccountDevice> revokeDevice(
    UserSession session,
    String deviceId,
  ) async {
    final normalized = deviceId.trim();
    if (normalized.isEmpty) {
      throw const SpinaApiException('A registered device is required.');
    }
    final identity = await _loadDeviceIdentity();
    final response = await _send(
      () => _client.post(
        ApiConfig.endpoint(
          '/api/mobile/v1/account/devices/${Uri.encodeComponent(normalized)}/revoke',
        ),
        headers: _headers(session, identity),
      ),
      offlineMessage:
          'Gilbic could not revoke that device. Check the connection and try again.',
    );
    final data = _data(response);
    final device = stringMap(data['device']);
    if (device.isEmpty) {
      throw const SpinaApiException(
        'The SPINA server returned incomplete device information.',
      );
    }
    return _device(device);
  }

  Future<DeviceIdentity> _loadDeviceIdentity() async {
    try {
      return await _deviceIdentityProvider.load();
    } on Exception {
      throw const SpinaApiException(
        'Gilbic could not access this installation identity. Restart the app and try again.',
      );
    }
  }

  Map<String, String> _headers(
    UserSession session,
    DeviceIdentity identity,
  ) {
    return <String, String>{
      'Accept': 'application/json',
      'Authorization': 'Bearer ${session.accessToken}',
      'X-Device-Id': identity.installationId,
    };
  }

  Future<http.Response> _send(
    Future<http.Response> Function() request, {
    required String offlineMessage,
  }) async {
    try {
      return await request();
    } on Exception {
      throw SpinaApiException(offlineMessage);
    }
  }

  Map<String, dynamic> _data(http.Response response) {
    Map<String, dynamic> payload;
    try {
      payload = decodeJsonObject(response.body);
    } on Object {
      throw SpinaApiException(
        'The SPINA server returned unreadable account data.',
        statusCode: response.statusCode,
      );
    }
    if (response.statusCode < 200 || response.statusCode >= 300) {
      throw SpinaApiException(
        apiErrorMessage(payload, statusCode: response.statusCode),
        statusCode: response.statusCode,
      );
    }
    return stringMap(
      unwrapSpinaData(payload, statusCode: response.statusCode),
    );
  }

  AccountProfile _profile(Map<String, dynamic> source) {
    final id = firstNonEmptyString(<Object?>[source['id']]);
    final username = firstNonEmptyString(<Object?>[source['username']]);
    final fullName = firstNonEmptyString(<Object?>[source['full_name']]);
    final role = firstNonEmptyString(<Object?>[source['role']]);
    final status = firstNonEmptyString(<Object?>[source['status']]);
    if (id == null ||
        username == null ||
        fullName == null ||
        role == null ||
        status == null) {
      throw const SpinaApiException(
        'The SPINA server returned incomplete profile information.',
      );
    }
    return AccountProfile(
      id: id,
      username: username,
      fullName: fullName,
      role: role,
      status: status,
      email: firstNonEmptyString(<Object?>[source['email']]),
    );
  }

  AccountDevice _device(Map<String, dynamic> source) {
    final id = firstNonEmptyString(<Object?>[source['id']]);
    final platform = firstNonEmptyString(<Object?>[source['platform']]);
    final status = firstNonEmptyString(<Object?>[source['status']]);
    final registeredAt = DateTime.tryParse(
      firstNonEmptyString(<Object?>[source['registered_at']]) ?? '',
    );
    if (id == null || platform == null || status == null || registeredAt == null) {
      throw const SpinaApiException(
        'The SPINA server returned incomplete device information.',
      );
    }
    return AccountDevice(
      id: id,
      platform: platform,
      appVersion: firstNonEmptyString(<Object?>[source['app_version']]),
      status: status,
      registeredAt: registeredAt,
      lastSeenAt: DateTime.tryParse(
        firstNonEmptyString(<Object?>[source['last_seen_at']]) ?? '',
      ),
      isCurrent: source['is_current'] == true,
    );
  }
}
