import 'dart:convert';

import 'package:gilbic_mobile/src/core/auth/app_role.dart';
import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/config/api_config.dart';
import 'package:gilbic_mobile/src/core/network/spina_api.dart';
import 'package:http/http.dart' as http;

abstract interface class AuthRepository {
  Future<UserSession> signIn({
    required String username,
    required String password,
  });

  Future<void> signOut(UserSession session);
}

class SpinaAuthRepository implements AuthRepository {
  SpinaAuthRepository({
    http.Client? client,
    Uri? loginUri,
    Uri? logoutUri,
  })  : _client = client ?? http.Client(),
        _loginUri = loginUri ?? ApiConfig.loginEndpoint,
        _logoutUri = logoutUri ?? ApiConfig.logoutEndpoint;

  final http.Client _client;
  final Uri _loginUri;
  final Uri _logoutUri;

  @override
  Future<UserSession> signIn({
    required String username,
    required String password,
  }) async {
    final normalizedUsername = username.trim();
    if (normalizedUsername.isEmpty || password.isEmpty) {
      throw const SpinaApiException('Enter your username and password.');
    }

    late final http.Response response;
    try {
      response = await _client.post(
        _loginUri,
        headers: const <String, String>{
          'Accept': 'application/json',
          'Content-Type': 'application/json',
        },
        body: jsonEncode(<String, String>{
          'username': normalizedUsername,
          'password': password,
        }),
      );
    } on Exception {
      throw const SpinaApiException(
        'Gilbic could not reach the SPINA server. Check the API address and connection.',
      );
    }

    Map<String, dynamic> payload;
    try {
      payload = decodeJsonObject(response.body);
    } on FormatException {
      throw SpinaApiException(
        'The SPINA server returned unreadable login data.',
        statusCode: response.statusCode,
      );
    }

    if (response.statusCode < 200 || response.statusCode >= 300) {
      throw SpinaApiException(
        apiErrorMessage(payload, statusCode: response.statusCode),
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
        normalizedUsername;
    final displayName = firstNonEmptyString(<Object?>[
          source['display_name'],
          source['full_name'],
          source['name'],
          source['username'],
          data['display_name'],
          data['full_name'],
          data['username'],
        ]) ??
        normalizedUsername;
    final returnedUsername = firstNonEmptyString(<Object?>[
          source['username'],
          data['username'],
        ]) ??
        normalizedUsername;
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
