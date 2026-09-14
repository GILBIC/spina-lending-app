import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/collector/collector_schedule.dart';
import 'package:gilbic_mobile/src/core/config/api_config.dart';
import 'package:gilbic_mobile/src/core/device/device_identity.dart';
import 'package:gilbic_mobile/src/core/network/spina_api.dart';
import 'package:http/http.dart' as http;

abstract interface class CollectorScheduleRepository {
  Future<CollectorSchedule> fetchSchedule(
    UserSession session, {
    required String loanId,
  });
}

class SpinaCollectorScheduleRepository implements CollectorScheduleRepository {
  SpinaCollectorScheduleRepository({
    http.Client? client,
    DeviceIdentityProvider? deviceIdentityProvider,
  })  : _client = client ?? http.Client(),
        _deviceIdentityProvider =
            deviceIdentityProvider ?? DeviceIdentityProvider();

  final http.Client _client;
  final DeviceIdentityProvider _deviceIdentityProvider;

  @override
  Future<CollectorSchedule> fetchSchedule(
    UserSession session, {
    required String loanId,
  }) async {
    late final DeviceIdentity deviceIdentity;
    try {
      deviceIdentity = await _deviceIdentityProvider.load();
    } on Exception {
      throw const SpinaApiException(
        'Gilbic could not access this installation identity. Restart the app and try again.',
      );
    }

    final scheduleUri = ApiConfig.endpoint(
      '/api/mobile/v1/collector/loans/'
      '${Uri.encodeComponent(loanId)}/schedule',
    );

    late final http.Response response;
    try {
      response = await _client.get(
        scheduleUri,
        headers: <String, String>{
          'Accept': 'application/json',
          'Authorization': 'Bearer ${session.accessToken}',
          'X-Session-Id': session.accessToken,
          'X-Device-Id': deviceIdentity.installationId,
        },
      );
    } on Exception {
      throw const SpinaApiException(
        'The Client schedule could not be downloaded. Check the connection.',
      );
    }

    Map<String, dynamic> payload;
    try {
      payload = decodeJsonObject(response.body);
    } on FormatException {
      throw SpinaApiException(
        'The SPINA server returned unreadable schedule data.',
        statusCode: response.statusCode,
      );
    }

    if (response.statusCode < 200 || response.statusCode >= 300) {
      throw SpinaApiException(
        apiErrorMessage(payload, statusCode: response.statusCode),
        statusCode: response.statusCode,
      );
    }

    return CollectorSchedule.fromPayload(
      unwrapSpinaData(payload, statusCode: response.statusCode),
    );
  }
}
