import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/collector/other_area_client.dart';
import 'package:gilbic_mobile/src/core/config/api_config.dart';
import 'package:gilbic_mobile/src/core/device/device_identity.dart';
import 'package:gilbic_mobile/src/core/network/spina_api.dart';
import 'package:http/http.dart' as http;

abstract interface class OtherAreaClientRepository {
  Future<List<OtherAreaClient>> search(
    UserSession session,
    String query,
  );
}

class SpinaOtherAreaClientRepository implements OtherAreaClientRepository {
  SpinaOtherAreaClientRepository({
    http.Client? client,
    Uri? endpoint,
    DeviceIdentityProvider? deviceIdentityProvider,
  })  : _client = client ?? http.Client(),
        _endpoint = endpoint ?? ApiConfig.otherAreaSearchEndpoint,
        _deviceIdentityProvider =
            deviceIdentityProvider ?? DeviceIdentityProvider();

  final http.Client _client;
  final Uri _endpoint;
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

    late final DeviceIdentity identity;
    try {
      identity = await _deviceIdentityProvider.load();
    } on Exception {
      throw const SpinaApiException(
        'Gilbic could not access this installation identity. Restart the app and try again.',
      );
    }

    final uri = _endpoint.replace(
      queryParameters: <String, String>{
        ..._endpoint.queryParameters,
        'q': normalized,
        'limit': '25',
      },
    );

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
      throw const SpinaApiException(
        'Other-area clients could not be searched. Check the connection.',
      );
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
