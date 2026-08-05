import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/config/api_config.dart';
import 'package:gilbic_mobile/src/core/loans/client_loan.dart';
import 'package:gilbic_mobile/src/core/network/spina_api.dart';
import 'package:http/http.dart' as http;

abstract interface class ClientLoanRepository {
  Future<ClientLoanPortfolio> loadPortfolio(
    UserSession session, {
    required String deviceId,
  });
}

class SpinaClientLoanRepository implements ClientLoanRepository {
  SpinaClientLoanRepository({http.Client? client})
      : _client = client ?? http.Client();

  final http.Client _client;

  @override
  Future<ClientLoanPortfolio> loadPortfolio(
    UserSession session, {
    required String deviceId,
  }) async {
    final endpoint = ApiConfig.endpoint('/api/mobile/v1/client/loans');
    late final http.Response response;
    try {
      response = await _client.get(
        endpoint,
        headers: <String, String>{
          'Accept': 'application/json',
          'Authorization': 'Bearer ${session.accessToken}',
          'X-Session-Id': session.accessToken,
          'X-Device-Id': deviceId,
        },
      );
    } on Exception {
      throw const SpinaApiException(
        'My Loans could not reach the SPINA server.',
        code: 'network_unavailable',
      );
    }

    late final Map<String, dynamic> payload;
    try {
      payload = decodeJsonObject(response.body);
    } on Object {
      throw SpinaApiException(
        'The SPINA server returned unreadable loan data.',
        statusCode: response.statusCode,
        code: 'invalid_server_response',
      );
    }

    if (response.statusCode >= 200 && response.statusCode < 300) {
      return ClientLoanPortfolio.fromPayload(
        stringMap(
          unwrapSpinaData(payload, statusCode: response.statusCode),
        ),
      );
    }

    final detail = payload['detail'];
    final detailMap = stringMap(detail);
    throw SpinaApiException(
      firstNonEmptyString(<Object?>[
            detailMap['message'],
            detail is String ? detail : null,
            payload['message'],
          ]) ??
          apiErrorMessage(payload, statusCode: response.statusCode),
      statusCode: response.statusCode,
      code: firstNonEmptyString(<Object?>[
        detailMap['code'],
        stringMap(payload['error'])['code'],
        payload['code'],
      ]),
    );
  }
}
