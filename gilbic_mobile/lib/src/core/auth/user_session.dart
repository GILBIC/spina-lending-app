import 'package:gilbic_mobile/src/core/auth/app_role.dart';

class UserSession {
  const UserSession({
    required this.userId,
    required this.username,
    required this.displayName,
    required this.role,
    required this.rawRole,
    required String accessToken,
    String? refreshToken,
    this.permissions = const <String>[],
    DateTime? expiresAt,
  })  : _accessToken = accessToken,
        _refreshToken = refreshToken,
        _expiresAt = expiresAt;

  final String userId;
  final String username;
  final String displayName;
  final AppRole role;
  final String rawRole;
  final String _accessToken;
  final String? _refreshToken;
  final DateTime? _expiresAt;
  final List<String> permissions;

  static final Map<String, _SessionTokenOverride> _tokenOverrides =
      <String, _SessionTokenOverride>{};

  String get accessToken =>
      _tokenOverrides[userId]?.accessToken ?? _accessToken;

  String? get refreshToken =>
      _tokenOverrides[userId]?.refreshToken ?? _refreshToken;

  DateTime? get expiresAt =>
      _tokenOverrides[userId]?.expiresAt ?? _expiresAt;

  bool get isExpired {
    final expiry = expiresAt;
    return expiry != null && !expiry.isAfter(DateTime.now().toUtc());
  }

  void applyRefresh(UserSession refreshed) {
    if (refreshed.userId != userId) {
      throw ArgumentError('The refreshed session belongs to another user.');
    }
    _tokenOverrides[userId] = _SessionTokenOverride(
      accessToken: refreshed.accessToken,
      refreshToken: refreshed.refreshToken,
      expiresAt: refreshed.expiresAt,
    );
  }

  void clearRefreshOverride() {
    _tokenOverrides.remove(userId);
  }

  Map<String, Object?> toJson() {
    return <String, Object?>{
      'user_id': userId,
      'username': username,
      'display_name': displayName,
      'role': role.name,
      'raw_role': rawRole,
      'access_token': accessToken,
      'refresh_token': refreshToken,
      'permissions': permissions,
      'expires_at': expiresAt?.toUtc().toIso8601String(),
    };
  }

  static UserSession? fromJson(Map<String, dynamic> json) {
    final role = AppRole.fromValue(json['role']?.toString() ?? '');
    final userId = json['user_id']?.toString().trim() ?? '';
    final username = json['username']?.toString().trim() ?? '';
    final displayName = json['display_name']?.toString().trim() ?? '';
    final accessToken = json['access_token']?.toString().trim() ?? '';
    if (role == null ||
        userId.isEmpty ||
        username.isEmpty ||
        displayName.isEmpty ||
        accessToken.isEmpty) {
      return null;
    }

    final permissionValue = json['permissions'];
    final permissions = permissionValue is Iterable
        ? permissionValue
            .map((item) => item?.toString().trim() ?? '')
            .where((item) => item.isNotEmpty)
            .toList(growable: false)
        : const <String>[];

    return UserSession(
      userId: userId,
      username: username,
      displayName: displayName,
      role: role,
      rawRole: json['raw_role']?.toString().trim().isNotEmpty == true
          ? json['raw_role'].toString().trim()
          : role.label,
      accessToken: accessToken,
      refreshToken: json['refresh_token']?.toString(),
      permissions: permissions,
      expiresAt: DateTime.tryParse(json['expires_at']?.toString() ?? ''),
    );
  }
}

class _SessionTokenOverride {
  const _SessionTokenOverride({
    required this.accessToken,
    required this.refreshToken,
    required this.expiresAt,
  });

  final String accessToken;
  final String? refreshToken;
  final DateTime? expiresAt;
}
