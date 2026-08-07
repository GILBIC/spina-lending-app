import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/config/api_config.dart';
import 'package:gilbic_mobile/src/core/management/management_loan.dart';
import 'package:gilbic_mobile/src/core/network/spina_api.dart';
import 'package:http/http.dart' as http;

abstract interface class ManagementLoanRepository {
  Future<ManagementLoanPortfolio> loadPortfolio(
    UserSession session, {
    required String deviceId,
    required String query,
    required String status,
  });
}

class SpinaManagementLoanRepository implements ManagementLoanRepository {
  SpinaManagementLoanRepository({http.Client? client})
      : _client = client ?? http.Client();

  final http.Client _client;

  @override
  Future<ManagementLoanPortfolio> loadPortfolio(
    UserSession session, {
    required String deviceId,
    required String query,
    required String status,
  }) async {
    final endpoint = ApiConfig.endpoint('/api/mobile/v1/management/loans').replace(
      queryParameters: <String, String>{
        'q': query.trim(),
        'status': status,
        'limit': '100',
        'offset': '0',
      },
    );
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
        'Loan Management could not reach the SPINA server.',
        code: 'network_unavailable',
      );
    }

    late final Map<String, dynamic> payload;
    try {
      payload = decodeJsonObject(response.body);
    } on Object {
      throw SpinaApiException(
        'The SPINA server returned unreadable Loan Management data.',
        statusCode: response.statusCode,
        code: 'invalid_server_response',
      );
    }

    if (response.statusCode >= 200 && response.statusCode < 300) {
      return ManagementLoanPortfolio.fromPayload(
        stringMap(unwrapSpinaData(payload, statusCode: response.statusCode)),
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
