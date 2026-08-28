const managementStaffRoles = <String>{'collector', 'employee', 'management'};

const managementAccountStatuses = <String>{
  'active',
  'inactive',
  'locked',
  'pending',
};

const managementDeviceStatuses = <String>{'pending', 'active', 'revoked'};

final _uuidPattern = RegExp(
  r'^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-5][0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}$',
);

final class ManagementStaffAccount {
  const ManagementStaffAccount({
    required this.id,
    required this.username,
    required this.email,
    required this.fullName,
    required this.status,
    required this.roles,
    required this.deviceCount,
    required this.createdAt,
    required this.updatedAt,
  });

  factory ManagementStaffAccount.fromPayload(Object? payload) {
    final data = _requiredMap(payload);
    final id = _requiredUuid(data, 'id');
    final username = _requiredString(data, 'username');
    final email = _optionalString(data, 'email');
    final fullName = _requiredString(data, 'full_name');
    final status = _requiredAllowedString(
      data,
      'status',
      managementAccountStatuses,
    );
    final rawRoles = data['roles'];
    if (rawRoles is! List || rawRoles.isEmpty) {
      throw const FormatException('Invalid roles.');
    }
    final roles = rawRoles
        .map((value) {
          if (value is! String || !managementStaffRoles.contains(value)) {
            throw const FormatException('Invalid role.');
          }
          return value;
        })
        .toList(growable: false);
    final deviceCount = data['device_count'];
    if (deviceCount is! int || deviceCount < 0) {
      throw const FormatException('Invalid device count.');
    }

    return ManagementStaffAccount(
      id: id,
      username: username,
      email: email,
      fullName: fullName,
      status: status,
      roles: List<String>.unmodifiable(roles),
      deviceCount: deviceCount,
      createdAt: _requiredTimestamp(data, 'created_at'),
      updatedAt: _requiredTimestamp(data, 'updated_at'),
    );
  }

  final String id;
  final String username;
  final String? email;
  final String fullName;
  final String status;
  final List<String> roles;
  final int deviceCount;
  final DateTime createdAt;
  final DateTime updatedAt;
}

final class ManagementDevice {
  const ManagementDevice({
    required this.id,
    required this.platform,
    required this.appVersion,
    required this.status,
    required this.registeredAt,
    required this.lastSeenAt,
  });

  factory ManagementDevice.fromPayload(Object? payload) {
    final data = _requiredMap(payload);
    return ManagementDevice(
      id: _requiredUuid(data, 'id'),
      platform: _requiredString(data, 'platform'),
      appVersion: _optionalString(data, 'app_version'),
      status: _requiredAllowedString(data, 'status', managementDeviceStatuses),
      registeredAt: _requiredTimestamp(data, 'registered_at'),
      lastSeenAt: _optionalTimestamp(data, 'last_seen_at'),
    );
  }

  final String id;
  final String platform;
  final String? appVersion;
  final String status;
  final DateTime registeredAt;
  final DateTime? lastSeenAt;
}

final class ManagementStaffPage {
  const ManagementStaffPage({
    required this.items,
    required this.nextOffset,
    required this.hasMore,
  });

  final List<ManagementStaffAccount> items;
  final int nextOffset;
  final bool hasMore;
}

Map<String, Object?> _requiredMap(Object? value) {
  if (value is! Map) {
    throw const FormatException('Expected an object.');
  }
  return value.map((key, item) => MapEntry(key.toString(), item));
}

String _requiredString(Map<String, Object?> data, String key) {
  final value = data[key];
  if (value is! String || value.trim().isEmpty) {
    throw FormatException('Invalid $key.');
  }
  return value.trim();
}

String? _optionalString(Map<String, Object?> data, String key) {
  final value = data[key];
  if (value == null) {
    return null;
  }
  if (value is! String || value.trim().isEmpty) {
    throw FormatException('Invalid $key.');
  }
  return value.trim();
}

String _requiredUuid(Map<String, Object?> data, String key) {
  final value = _requiredString(data, key);
  if (!_uuidPattern.hasMatch(value)) {
    throw FormatException('Invalid $key.');
  }
  return value;
}

String _requiredAllowedString(
  Map<String, Object?> data,
  String key,
  Set<String> allowed,
) {
  final value = _requiredString(data, key);
  if (!allowed.contains(value)) {
    throw FormatException('Invalid $key.');
  }
  return value;
}

DateTime _requiredTimestamp(Map<String, Object?> data, String key) {
  final value = _requiredString(data, key);
  final parsed = DateTime.tryParse(value);
  if (parsed == null) {
    throw FormatException('Invalid $key.');
  }
  return parsed;
}

DateTime? _optionalTimestamp(Map<String, Object?> data, String key) {
  if (data[key] == null) {
    return null;
  }
  return _requiredTimestamp(data, key);
}
