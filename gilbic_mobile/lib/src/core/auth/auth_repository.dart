import 'dart:convert';

import 'package:gilbic_mobile/src/core/auth/app_role.dart';
import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/config/api_config.dart';
import 'package:gilbic_mobile/src/core/device/device_identity.dart';
import 'package:gilbic_mobile/src/core/network/spina_api.dart';
import 'package:http/http.dart' as http;

abstract interface class AuthRepository {
  Future<UserSession> signIn({
    required String username,
    required String password,
  });

  Future<void> signOut(UserSession session);
}

abstract interface class SessionRefreshRepository {
  Future<UserSession> refresh(UserSession session);
}

class SpinaAuthRepository implements AuthRepository, SessionRefreshRepository {
  SpinaAuthRepository({
    http.Client? client,
    Uri? loginUri,
    Uri? refreshUri,
    Uri? logoutUri,
    DeviceIdentityProvider? deviceIdentityProvider,
  })  : _client = client ?? http.Client(),
        _loginUri = loginUri ?? ApiConfig.loginEndpoint,
        _refreshUri = refreshUri ?? ApiConfig.refreshEndpoint,
        _logoutUri = logoutUri ?? ApiConfig.logoutEndpoint,
        _deviceIdentityProvider =
            deviceIdentityProvider ?? DeviceIdentityProvider();

  final http.Client _client;
  final Uri _loginUri;
  final Uri _refreshUri;
  final Uri _logoutUri;
  final DeviceIdentityProvider _deviceIdentityProvider;

  @override
  Future<UserSession> signIn({
    required String username,
    required String password,
  }) async {
    final normalizedUsername = username.trim();
    if (normalizedUsername.isEmpty || password.isEmpty) {
      throw const SpinaApiException('Enter your username and password.');
    }

    final deviceIdentity = await _loadDeviceIdentity();
    late final http.Response response;
    try {
      response = await _client.post(
        _loginUri,
        headers: const <String, String>{
          'Accept': 'application/json',
          'Content-Type': 'application/json',
        },
        body: jsonEncode(<String, Object?>{
          'username': normalizedUsername,
          'password': password,
          'device_id': deviceIdentity.installationId,
          'platform': deviceIdentity.platform,
          'app_version': deviceIdentity.appVersion,
        }),
      );
    } on Exception {
      throw const SpinaApiException(
        'Gilbic could not reach the SPINA server. Check the API address and connection.',
      );
    }

    return _sessionFromResponse(
      response,
      fallbackUsername: normalizedUsername,
      unreadableMessage: 'The SPINA server returned unreadable login data.',
      authenticationFailureMessage: 'Invalid username or password.',
    );
  }

  @override
  Future<UserSession> refresh(UserSession session) async {
    final refreshToken = session.refreshToken?.trim() ?? '';
    if (refreshToken.isEmpty) {
      throw const SpinaApiException(
        'Your login session expired. Sign in again.',
        statusCode: 401,
      );
    }

    final deviceIdentity = await _loadDeviceIdentity();
    late final http.Response response;
    try {
      response = await _client.post(
        _refreshUri,
        headers: <String, String>{
          'Accept': 'application/json',
          'Content-Type': 'application/json',
          'X-Device-Id': deviceIdentity.installationId,
        },
        body: jsonEncode(<String, Object?>{
          'refresh_token': refreshToken,
        }),
      );
    } on Exception {
      throw const SpinaApiException(
        'Gilbic could not renew the login session. Check the connection and try again.',
      );
    }

    return _sessionFromResponse(
      response,
      fallbackUsername: session.username,
      unreadableMessage: 'The SPINA server returned unreadable session data.',
      authenticationFailureMessage:
          'Your login session expired. Sign in again.',
    );
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

  UserSession _sessionFromResponse(
    http.Response response, {
    required String fallbackUsername,
    required String unreadableMessage,
    required String authenticationFailureMessage,
  }) {
    Map<String, dynamic> payload;
    try {
      payload = decodeJsonObject(response.body);
    } on FormatException {
      throw SpinaApiException(
        unreadableMessage,
        statusCode: response.statusCode,
      );
    }

    if (response.statusCode < 200 || response.statusCode >= 300) {
      throw SpinaApiException(
        response.statusCode == 401 || response.statusCode == 403
            ? authenticationFailureMessage
            : apiErrorMessage(payload, statusCode: response.statusCode),
        statusCode: response.statusCode,
      );
    }

    final data = stringMap(
      unwrapSpinaData(payload, statusCode: response.statusCode),
    );
    final user = stringMap(
      data['user'] ?? data['account'] ?? data['profile'],
    );
    final session = stringMap(data['session']);
    final source = user.isEmpty ? data : user;

    final token = firstNonEmptyString(<Object?>[
      data['access_token'],
      data['token'],
      data['session_token'],
      data['session_id'],
      session['access_token'],
      session['token'],
      session['session_token'],
      session['session_id'],
      payload['access_token'],
      payload['token'],
      payload['session_id'],
    ]);
    if (token == null) {
      throw const SpinaApiException(
        'Login succeeded, but the server did not return a session token.',
      );
    }

    final rawRole = firstNonEmptyString(<Object?>[
      source['role'],
      source['user_role'],
      source['account_role'],
      data['role'],
      data['user_role'],
    ]);
    final role = rawRole == null ? null : AppRole.fromValue(rawRole);
    if (role == null) {
      throw SpinaApiException(
        rawRole == null
            ? 'The server did not return an account role.'
            : 'The role "$rawRole" is not enabled in Gilbic yet.',
      );
    }
    final authenticatedRoleName = rawRole!;

    final userId = firstNonEmptyString(<Object?>[
          source['id'],
          source['user_id'],
          source['account_id'],
          data['user_id'],
          data['account_id'],
        ]) ??
        fallbackUsername;
    final displayName = firstNonEmptyString(<Object?>[
          source['display_name'],
          source['full_name'],
          source['name'],
          source['username'],
          data['display_name'],
          data['full_name'],
          data['username'],
        ]) ??
        fallbackUsername;
    final returnedUsername = firstNonEmptyString(<Object?>[
          source['username'],
          data['username'],
        ]) ??
        fallbackUsername;
    final permissions = stringList(
      source['permissions'] ?? data['permissions'],
    );
    final refreshToken = firstNonEmptyString(<Object?>[
      data['refresh_token'],
      session['refresh_token'],
      payload['refresh_token'],
    ]);
    final expiresAt = DateTime.tryParse(
      firstNonEmptyString(<Object?>[
            data['expires_at'],
            session['expires_at'],
            payload['expires_at'],
          ]) ??
          '',
    );

    return UserSession(
      userId: userId,
      username: returnedUsername,
      displayName: displayName,
      role: role,
      rawRole: authenticatedRoleName,
      accessToken: token,
      refreshToken: refreshToken,
      permissions: permissions,
      expiresAt: expiresAt,
    );
  }

  @override
  Future<void> signOut(UserSession session) async {
    try {
      await _client.post(
        _logoutUri,
        headers: <String, String>{
          'Accept': 'application/json',
          'Authorization': 'Bearer ${session.accessToken}',
          'X-Session-Id': session.accessToken,
        },
      );
    } on Exception {
      // Local secure-session removal is still required when the server is offline.
    }
  }
}
