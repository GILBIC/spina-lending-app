import 'dart:convert';

import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/collector/delegated_area_access.dart';
import 'package:gilbic_mobile/src/core/config/api_config.dart';
import 'package:gilbic_mobile/src/core/device/device_identity.dart';
import 'package:gilbic_mobile/src/core/network/spina_api.dart';
import 'package:http/http.dart' as http;

abstract interface class DelegatedAreaRepository {
  Future<List<DelegatedAreaScope>> availableScopes(UserSession session);

  Future<List<DelegatedAreaRequest>> incomingRequests(UserSession session);

  Future<List<DelegatedAreaRequest>> outgoingRequests(UserSession session);

  Future<List<DelegatedAreaGrant>> activeGrants(UserSession session);

  Future<DelegatedAreaRequest> createRequest(
    UserSession session, {
    required String ownerUserId,
    required List<DelegatedAreaScope> scopes,
    required bool allOwnerAreas,
    required String reason,
    required DateTime expiresAt,
  });

  Future<DelegatedAreaGrant> approveRequest(
    UserSession session,
    String requestId, {
    String reason = '',
  });

  Future<DelegatedAreaRequest> declineRequest(
    UserSession session,
    String requestId, {
    String reason = '',
  });

  Future<DelegatedAreaRequest> cancelRequest(
    UserSession session,
    String requestId, {
    String reason = '',
  });

  Future<DelegatedAreaGrant> revokeGrant(
    UserSession session,
    String grantId, {
    required String reason,
  });
}

class SpinaDelegatedAreaRepository implements DelegatedAreaRepository {
  SpinaDelegatedAreaRepository({
    http.Client? client,
    DeviceIdentityProvider? deviceIdentityProvider,
  })  : _client = client ?? http.Client(),
        _deviceIdentityProvider =
            deviceIdentityProvider ?? DeviceIdentityProvider();

  final http.Client _client;
  final DeviceIdentityProvider _deviceIdentityProvider;

  @override
  Future<List<DelegatedAreaScope>> availableScopes(UserSession session) async {
    final data = await _get(session, ApiConfig.delegatedAreaAvailableScopesEndpoint);
    return _list(data, DelegatedAreaScope.fromPayload);
  }

  @override
  Future<List<DelegatedAreaRequest>> incomingRequests(UserSession session) async {
    final data = await _get(session, ApiConfig.delegatedAreaIncomingRequestsEndpoint);
    return _list(data, DelegatedAreaRequest.fromPayload);
  }

  @override
  Future<List<DelegatedAreaRequest>> outgoingRequests(UserSession session) async {
    final data = await _get(session, ApiConfig.delegatedAreaOutgoingRequestsEndpoint);
    return _list(data, DelegatedAreaRequest.fromPayload);
  }

  @override
  Future<List<DelegatedAreaGrant>> activeGrants(UserSession session) async {
    final data = await _get(session, ApiConfig.delegatedAreaActiveGrantsEndpoint);
    return _list(data, DelegatedAreaGrant.fromPayload);
  }

  @override
  Future<DelegatedAreaRequest> createRequest(
    UserSession session, {
    required String ownerUserId,
    required List<DelegatedAreaScope> scopes,
    required bool allOwnerAreas,
    required String reason,
    required DateTime expiresAt,
  }) async {
    final data = await _post(
      session,
      ApiConfig.delegatedAreaRequestsEndpoint,
      <String, Object?>{
        'requested_owner_user_id': ownerUserId,
        'scope_mode': allOwnerAreas ? 'all_owner_areas' : 'selected_paths',
        'scopes': allOwnerAreas
            ? const <Object?>[]
            : scopes
                .map(
                  (scope) => <String, Object?>{
                    'assignment_id': scope.assignmentId,
                    'include_descendants': scope.includeDescendants,
                  },
                )
                .toList(growable: false),
        'reason': reason.trim(),
        'requested_expires_at': expiresAt.toUtc().toIso8601String(),
      },
    );
    final record = DelegatedAreaRequest.fromPayload(data);
    if (record == null) {
      throw const SpinaApiException(
        'SPINA returned an invalid delegated-area request.',
      );
    }
    return record;
  }

  @override
  Future<DelegatedAreaGrant> approveRequest(
    UserSession session,
    String requestId, {
    String reason = '',
  }) async {
    final data = await _post(
      session,
      ApiConfig.delegatedAreaRequestActionEndpoint(requestId, 'approve'),
      <String, Object?>{'reason': reason.trim()},
    );
    final record = DelegatedAreaGrant.fromPayload(data);
    if (record == null) {
      throw const SpinaApiException(
        'SPINA returned an invalid delegated-area grant.',
      );
    }
    return record;
  }

  @override
  Future<DelegatedAreaRequest> declineRequest(
    UserSession session,
    String requestId, {
    String reason = '',
  }) async {
    return _requestAction(session, requestId, 'decline', reason);
  }

  @override
  Future<DelegatedAreaRequest> cancelRequest(
    UserSession session,
    String requestId, {
    String reason = '',
  }) async {
    return _requestAction(session, requestId, 'cancel', reason);
  }

  @override
  Future<DelegatedAreaGrant> revokeGrant(
    UserSession session,
    String grantId, {
    required String reason,
  }) async {
    final data = await _post(
      session,
      ApiConfig.delegatedAreaGrantRevokeEndpoint(grantId),
      <String, Object?>{'reason': reason.trim()},
    );
    final record = DelegatedAreaGrant.fromPayload(data);
    if (record == null) {
      throw const SpinaApiException(
        'SPINA returned an invalid delegated-area grant.',
      );
    }
    return record;
  }

  Future<DelegatedAreaRequest> _requestAction(
    UserSession session,
    String requestId,
    String action,
    String reason,
  ) async {
    final data = await _post(
      session,
      ApiConfig.delegatedAreaRequestActionEndpoint(requestId, action),
      <String, Object?>{'reason': reason.trim()},
    );
    final record = DelegatedAreaRequest.fromPayload(data);
    if (record == null) {
      throw const SpinaApiException(
        'SPINA returned an invalid delegated-area request.',
      );
    }
    return record;
  }

  Future<Object?> _get(UserSession session, Uri uri) async {
    final headers = await _headers(session);
    late final http.Response response;
    try {
      response = await _client.get(uri, headers: headers);
    } on Exception {
      throw const SpinaApiException(
        'Temporary area access could not be loaded. Check the connection.',
      );
    }
    return _decode(response);
  }

  Future<Object?> _post(
    UserSession session,
    Uri uri,
    Map<String, Object?> body,
  ) async {
    final headers = await _headers(session);
    late final http.Response response;
    try {
      response = await _client.post(
        uri,
        headers: <String, String>{
          ...headers,
          'Content-Type': 'application/json',
        },
        body: jsonEncode(body),
      );
    } on Exception {
      throw const SpinaApiException(
        'Temporary area access could not be updated. Check the connection.',
      );
    }
    return _decode(response);
  }

  Future<Map<String, String>> _headers(UserSession session) async {
    late final DeviceIdentity identity;
    try {
      identity = await _deviceIdentityProvider.load();
    } on Exception {
      throw const SpinaApiException(
        'SPINA could not access this installation identity. Restart the app and try again.',
      );
    }
    return <String, String>{
      'Accept': 'application/json',
      'Authorization': 'Bearer ${session.accessToken}',
      'X-Session-Id': session.accessToken,
      'X-Device-Id': identity.installationId,
    };
  }

  Object? _decode(http.Response response) {
    Map<String, dynamic> payload;
    try {
      payload = decodeJsonObject(response.body);
    } on Object {
      throw SpinaApiException(
        'The SPINA server returned unreadable delegated-area data.',
        statusCode: response.statusCode,
      );
    }
    if (response.statusCode < 200 || response.statusCode >= 300) {
      final detail = stringMap(payload['detail']);
      throw SpinaApiException(
        firstNonEmptyString(<Object?>[
              detail['message'],
              payload['message'],
              detail['detail'],
            ]) ??
            apiErrorMessage(payload, statusCode: response.statusCode),
        statusCode: response.statusCode,
        code: firstNonEmptyString(<Object?>[
          detail['code'],
          payload['code'],
        ]),
      );
    }
    return unwrapSpinaData(payload, statusCode: response.statusCode);
  }
}

List<T> _list<T>(Object? value, T? Function(Object?) parser) {
  if (value is! Iterable) {
    return <T>[];
  }
  return value.map(parser).whereType<T>().toList(growable: false);
}
