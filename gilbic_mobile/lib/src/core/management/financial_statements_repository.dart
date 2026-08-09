import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/config/api_config.dart';
import 'package:gilbic_mobile/src/core/management/financial_statements.dart';
import 'package:gilbic_mobile/src/core/network/spina_api.dart';
import 'package:http/http.dart' as http;

abstract interface class FinancialStatementsRepository {
  Future<AccountingFinancialStatements> loadStatements(
    UserSession session, {
    required String deviceId,
    String? periodId,
  });
}

class SpinaFinancialStatementsRepository implements FinancialStatementsRepository {
  SpinaFinancialStatementsRepository({http.Client? client})
      : _client = client ?? http.Client();

  final http.Client _client;

  @override
  Future<AccountingFinancialStatements> loadStatements(
    UserSession session, {
    required String deviceId,
    String? periodId,
  }) async {
    final base = ApiConfig.endpoint(
      '/api/mobile/v1/management/financial-accounting/statements',
    );
    final endpoint = periodId == null
        ? base
        : base.replace(queryParameters: <String, String>{'period_id': periodId});

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
        'Financial Statements could not reach the SPINA server.',
        code: 'network_unavailable',
      );
    }

    late final Map<String, dynamic> payload;
    try {
      payload = decodeJsonObject(response.body);
    } on Object {
      throw SpinaApiException(
        'The SPINA server returned unreadable Financial Statement data.',
        statusCode: response.statusCode,
        code: 'invalid_server_response',
      );
    }

    if (response.statusCode != 200) {
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

    final data = stringMap(unwrapSpinaData(payload, statusCode: 200));
    return AccountingFinancialStatements.fromPayload(
      stringMap(data['statements']),
    );
  }
}
