import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/collector/other_area_client.dart';
import 'package:gilbic_mobile/src/core/config/api_config.dart';
import 'package:gilbic_mobile/src/core/device/device_identity.dart';
import 'package:gilbic_mobile/src/core/network/spina_api.dart';
import 'package:gilbic_mobile/src/core/time/spina_business_time.dart';
import 'package:http/http.dart' as http;

abstract interface class OtherAreaClientRepository {
  Future<List<OtherAreaClient>> search(
    UserSession session,
    String query,
  );

  Future<List<OtherAreaClient>> listWork(
    UserSession session,
    DateTime workDate, {
    String? assignedCollectorUserId,
  });
}

class SpinaOtherAreaClientRepository implements OtherAreaClientRepository {
  SpinaOtherAreaClientRepository({
    http.Client? client,
    Uri? endpoint,
    Uri? workEndpoint,
    DeviceIdentityProvider? deviceIdentityProvider,
  })  : _client = client ?? http.Client(),
        _endpoint = endpoint ?? ApiConfig.otherAreaSearchEndpoint,
        _workEndpoint = workEndpoint ?? ApiConfig.delegatedAreaWorkEndpoint,
        _deviceIdentityProvider =
            deviceIdentityProvider ?? DeviceIdentityProvider();

  final http.Client _client;
  final Uri _endpoint;
  final Uri _workEndpoint;
  final DeviceIdentityProvider _deviceIdentityProvider;

  @override
  Future<List<OtherAreaClient>> search(
    UserSession session,
    String query,
  ) async {
    final normalized = query.trim().split(RegExp(r'\s+')).join(' ');
    if (normalized.length < 2) {
      return const <OtherAreaClient>[];
    }

    final uri = _endpoint.replace(
      queryParameters: <String, String>{
        ..._endpoint.queryParameters,
        'q': normalized,
        'limit': '25',
      },
    );
    return _load(
      session,
      uri,
      connectionMessage:
          'Other-area clients could not be searched. Check the connection.',
    );
  }

  @override
  Future<List<OtherAreaClient>> listWork(
    UserSession session,
    DateTime workDate, {
    String? assignedCollectorUserId,
  }) async {
    final ownerId = assignedCollectorUserId?.trim() ?? '';
    final uri = _workEndpoint.replace(
      queryParameters: <String, String>{
        ..._workEndpoint.queryParameters,
        'date': formatSpinaBusinessDate(workDate),
        'limit': '500',
        if (ownerId.isNotEmpty) 'assigned_collector_user_id': ownerId,
      },
    );
    return _load(
      session,
      uri,
      connectionMessage:
          'Other-area work could not be loaded. Check the connection.',
    );
  }

  Future<List<OtherAreaClient>> _load(
    UserSession session,
    Uri uri, {
    required String connectionMessage,
  }) async {
    late final DeviceIdentity identity;
    try {
      identity = await _deviceIdentityProvider.load();
    } on Exception {
      throw const SpinaApiException(
        'Gilbic could not access this installation identity. Restart the app and try again.',
      );
    }

    late final http.Response response;
    try {
      response = await _client.get(
        uri,
        headers: <String, String>{
          'Accept': 'application/json',
          'Authorization': 'Bearer ${session.accessToken}',
          'X-Session-Id': session.accessToken,
          'X-Device-Id': identity.installationId,
        },
      );
    } on Exception {
      throw SpinaApiException(connectionMessage);
    }

    Map<String, dynamic> payload;
    try {
      payload = decodeJsonObject(response.body);
    } on FormatException {
      throw SpinaApiException(
        'The SPINA server returned unreadable other-area client data.',
        statusCode: response.statusCode,
      );
    }

    if (response.statusCode < 200 || response.statusCode >= 300) {
      throw SpinaApiException(
        apiErrorMessage(payload, statusCode: response.statusCode),
        statusCode: response.statusCode,
      );
    }

    final data = unwrapSpinaData(payload, statusCode: response.statusCode);
    if (data is! Iterable) {
      return const <OtherAreaClient>[];
    }
    return data
        .map(OtherAreaClient.fromPayload)
        .whereType<OtherAreaClient>()
        .toList(growable: false);
  }
}
