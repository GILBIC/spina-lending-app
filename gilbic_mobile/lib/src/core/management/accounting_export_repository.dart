import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/config/api_config.dart';
import 'package:gilbic_mobile/src/core/documents/client_document_repository.dart';
import 'package:gilbic_mobile/src/core/network/spina_api.dart';
import 'package:http/http.dart' as http;

class AccountingExportRepository {
  AccountingExportRepository({http.Client? client})
    : _client = client ?? http.Client();
  final http.Client _client;

  Future<ClientDocumentFile> download(
    UserSession session, {
    required String deviceId,
    required String startDate,
    required String endDate,
  }) async {
    DateTime? date(String value) {
      if (!RegExp(r'^\d{4}-\d{2}-\d{2}$').hasMatch(value)) return null;
      final parsed = DateTime.tryParse('${value}T00:00:00Z');
      return parsed != null &&
              parsed.year > 0 &&
              parsed.toIso8601String().substring(0, 10) == value
          ? parsed
          : null;
    }

    final start = date(startDate), end = date(endDate);
    if (start == null ||
        end == null ||
        end.isBefore(start) ||
        end.difference(start).inDays >= 366) {
      throw const SpinaApiException(
        'Choose valid period dates covering up to 366 days.',
      );
    }
    late final http.Response response;
    try {
      response = await _client.get(
        ApiConfig.endpoint(
          '/api/mobile/v1/management/financial-accounting/export',
        ).replace(
          queryParameters: {
            'start_date': startDate,
            'end_date': endDate,
            'include_reporting': 'true',
          },
        ),
        headers: {
          'Authorization': 'Bearer ${session.accessToken}',
          'X-Device-Id': deviceId,
          'Accept': 'application/zip',
        },
      );
    } on Exception {
      throw const SpinaApiException(
        'Reporting download could not reach the server.',
      );
    }
    if (response.statusCode != 200) {
      throw SpinaApiException(switch (response.statusCode) {
        401 || 403 || 426 =>
          'Accounting download access is unavailable. Refresh your session and permissions.',
        422 =>
          'Choose the complete dates of consecutive configured accounting periods, up to 366 days.',
        413 => 'The reporting package is too large. Choose a shorter range.',
        409 =>
          'The accounting records need review before this download can be prepared.',
        _ => 'The reporting download is unavailable. Try again later.',
      }, statusCode: response.statusCode);
    }
    final bytes = response.bodyBytes;
    if (response.headers['content-type']
                ?.split(';')
                .first
                .trim()
                .toLowerCase() !=
            'application/zip' ||
        bytes.length < 4 ||
        bytes.length > 64 * 1024 * 1024 ||
        bytes[0] != 0x50 ||
        bytes[1] != 0x4b ||
        bytes[2] != 3 ||
        bytes[3] != 4) {
      throw const SpinaApiException(
        'The server did not return a valid reporting package.',
      );
    }
    return ClientDocumentFile(
      filename: 'spina-accounting-$startDate-to-$endDate.zip',
      bytes: bytes,
      mediaType: 'application/zip',
    );
  }
}
