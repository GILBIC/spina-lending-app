import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/collector/collector_route.dart';
import 'package:gilbic_mobile/src/core/config/api_config.dart';
import 'package:gilbic_mobile/src/core/network/spina_api.dart';
import 'package:http/http.dart' as http;

abstract interface class CollectorRouteRepository {
  Future<CollectorRoute> fetchToday(UserSession session);
}

class SpinaCollectorRouteRepository implements CollectorRouteRepository {
  SpinaCollectorRouteRepository({
    http.Client? client,
    Uri? routeUri,
  })  : _client = client ?? http.Client(),
        _routeUri = routeUri ?? ApiConfig.collectorRouteEndpoint;

  final http.Client _client;
  final Uri _routeUri;

  @override
  Future<CollectorRoute> fetchToday(UserSession session) async {
    late final http.Response response;
    try {
      response = await _client.get(
        _routeUri,
        headers: <String, String>{
          'Accept': 'application/json',
          'Authorization': 'Bearer ${session.accessToken}',
          'X-Session-Id': session.accessToken,
        },
      );
    } on Exception {
      throw const SpinaApiException(
        'The assigned route could not be downloaded. Check the connection.',
      );
    }

    Map<String, dynamic> payload;
    try {
      payload = decodeJsonObject(response.body);
    } on FormatException {
      throw SpinaApiException(
        'The SPINA server returned unreadable route data.',
        statusCode: response.statusCode,
      );
    }

    if (response.statusCode < 200 || response.statusCode >= 300) {
      throw SpinaApiException(
        apiErrorMessage(payload, statusCode: response.statusCode),
        statusCode: response.statusCode,
      );
    }

    return CollectorRoute.fromPayload(
      unwrapSpinaData(payload, statusCode: response.statusCode),
    );
  }
}
