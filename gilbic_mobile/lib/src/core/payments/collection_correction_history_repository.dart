import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/config/api_config.dart';
import 'package:gilbic_mobile/src/core/network/spina_api.dart';
import 'package:http/http.dart' as http;

class CollectionCorrectionHistoryEntry {
  const CollectionCorrectionHistoryEntry({
    required this.editVersion,
    required this.reason,
    required this.previousSnapshot,
    required this.replacementSnapshot,
    required this.previousCoveredDates,
    required this.replacementCoveredDates,
    required this.editedByName,
    required this.editedAt,
  });

  final int editVersion;
  final String reason;
  final Map<String, dynamic> previousSnapshot;
  final Map<String, dynamic> replacementSnapshot;
  final List<DateTime> previousCoveredDates;
  final List<DateTime> replacementCoveredDates;
  final String editedByName;
  final DateTime? editedAt;

  static CollectionCorrectionHistoryEntry fromPayload(Object? value) {
    final data = stringMap(value);
    return CollectionCorrectionHistoryEntry(
      editVersion: firstNumber(<Object?>[data['edit_version']])?.toInt() ?? 0,
      reason: firstNonEmptyString(<Object?>[data['reason']]) ?? '',
      previousSnapshot: stringMap(data['previous_snapshot']),
      replacementSnapshot: stringMap(data['replacement_snapshot']),
      previousCoveredDates: _dateList(data['previous_covered_dates']),
      replacementCoveredDates: _dateList(data['replacement_covered_dates']),
      editedByName:
          firstNonEmptyString(<Object?>[data['edited_by_name']]) ?? 'SPINA staff',
      editedAt: DateTime.tryParse(
        firstNonEmptyString(<Object?>[data['edited_at']]) ?? '',
      ),
    );
  }
}

abstract interface class CollectionCorrectionHistoryRepository {
  Future<List<CollectionCorrectionHistoryEntry>> list(
    UserSession session, {
    required String deviceId,
    required String transactionId,
  });
}

class SpinaCollectionCorrectionHistoryRepository
    implements CollectionCorrectionHistoryRepository {
  SpinaCollectionCorrectionHistoryRepository({http.Client? client})
      : _client = client ?? http.Client();

  final http.Client _client;

  @override
  Future<List<CollectionCorrectionHistoryEntry>> list(
    UserSession session, {
    required String deviceId,
    required String transactionId,
  }) async {
    final endpoint = ApiConfig.endpoint(
      '/api/mobile/v1/collector/collections/$transactionId/corrections',
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
        'Correction history could not reach the SPINA server.',
        code: 'network_unavailable',
      );
    }

    final payload = _decodeResponse(response);
    if (response.statusCode >= 200 && response.statusCode < 300) {
      final data = stringMap(
        unwrapSpinaData(payload, statusCode: response.statusCode),
      );
      final corrections = data['corrections'];
      if (corrections is! Iterable) {
        return const <CollectionCorrectionHistoryEntry>[];
      }
      return corrections
          .map(CollectionCorrectionHistoryEntry.fromPayload)
          .toList(growable: false);
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

  Map<String, dynamic> _decodeResponse(http.Response response) {
    try {
      return decodeJsonObject(response.body);
    } on Object {
      throw SpinaApiException(
        'The SPINA server returned unreadable correction history.',
        statusCode: response.statusCode,
        code: 'invalid_server_response',
      );
    }
  }
}

List<DateTime> _dateList(Object? value) {
  if (value is! Iterable) {
    return const <DateTime>[];
  }
  final dates = value
      .map((item) => DateTime.tryParse(item.toString()))
      .whereType<DateTime>()
      .map((item) => DateTime(item.year, item.month, item.day))
      .toSet()
      .toList(growable: false)
    ..sort((left, right) => left.compareTo(right));
  return dates;
}
