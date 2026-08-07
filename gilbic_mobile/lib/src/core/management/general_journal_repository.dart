import 'dart:convert';

import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/config/api_config.dart';
import 'package:gilbic_mobile/src/core/management/general_journal.dart';
import 'package:gilbic_mobile/src/core/network/spina_api.dart';
import 'package:http/http.dart' as http;

abstract interface class GeneralJournalRepository {
  Future<GeneralJournalSnapshot> loadJournals(
    UserSession session, {
    required String deviceId,
  });

  Future<AccountingTrialBalance> loadTrialBalance(
    UserSession session, {
    required String deviceId,
    String? periodId,
  });

  Future<AccountingJournalEntry> createDraft(
    UserSession session, {
    required String deviceId,
    required DateTime postingDate,
    required String description,
    required List<JournalLineDraft> lines,
  });

  Future<AccountingJournalEntry> updateDraft(
    UserSession session, {
    required String deviceId,
    required String entryId,
    required DateTime postingDate,
    required String description,
    required List<JournalLineDraft> lines,
  });

  Future<void> cancelDraft(
    UserSession session, {
    required String deviceId,
    required String entryId,
  });

  Future<AccountingJournalEntry> postJournal(
    UserSession session, {
    required String deviceId,
    required String entryId,
  });

  Future<AccountingJournalEntry> createReversalDraft(
    UserSession session, {
    required String deviceId,
    required String entryId,
    required DateTime postingDate,
    required String description,
  });
}

class SpinaGeneralJournalRepository implements GeneralJournalRepository {
  SpinaGeneralJournalRepository({http.Client? client})
      : _client = client ?? http.Client();

  final http.Client _client;

  Map<String, String> _headers(UserSession session, String deviceId) =>
      <String, String>{
        'Accept': 'application/json',
        'Content-Type': 'application/json',
        'Authorization': 'Bearer ${session.accessToken}',
        'X-Session-Id': session.accessToken,
        'X-Device-Id': deviceId,
      };

  @override
  Future<GeneralJournalSnapshot> loadJournals(
    UserSession session, {
    required String deviceId,
  }) async {
    final response = await _send(
      () => _client.get(
        ApiConfig.endpoint('/api/mobile/v1/management/financial-accounting/journals'),
        headers: _headers(session, deviceId),
      ),
    );
    return GeneralJournalSnapshot.fromPayload(
      stringMap(unwrapSpinaData(response, statusCode: 200)),
    );
  }

  @override
  Future<AccountingTrialBalance> loadTrialBalance(
    UserSession session, {
    required String deviceId,
    String? periodId,
  }) async {
    final base = ApiConfig.endpoint(
      '/api/mobile/v1/management/financial-accounting/trial-balance',
    );
    final endpoint = periodId == null
        ? base
        : base.replace(queryParameters: <String, String>{'period_id': periodId});
    final response = await _send(
      () => _client.get(endpoint, headers: _headers(session, deviceId)),
    );
    final data = stringMap(unwrapSpinaData(response, statusCode: 200));
    return AccountingTrialBalance.fromPayload(
      stringMap(data['trial_balance']),
    );
  }

  @override
  Future<AccountingJournalEntry> createDraft(
    UserSession session, {
    required String deviceId,
    required DateTime postingDate,
    required String description,
    required List<JournalLineDraft> lines,
  }) async {
    final response = await _send(
      () => _client.post(
        ApiConfig.endpoint('/api/mobile/v1/management/financial-accounting/journals'),
        headers: _headers(session, deviceId),
        body: jsonEncode(_journalBody(postingDate, description, lines)),
      ),
      expectedStatus: 201,
    );
    return _entryFromResponse(response, statusCode: 201);
  }

  @override
  Future<AccountingJournalEntry> updateDraft(
    UserSession session, {
    required String deviceId,
    required String entryId,
    required DateTime postingDate,
    required String description,
    required List<JournalLineDraft> lines,
  }) async {
    final response = await _send(
      () => _client.put(
        ApiConfig.endpoint(
          '/api/mobile/v1/management/financial-accounting/journals/$entryId',
        ),
        headers: _headers(session, deviceId),
        body: jsonEncode(_journalBody(postingDate, description, lines)),
      ),
    );
    return _entryFromResponse(response);
  }

  @override
  Future<void> cancelDraft(
    UserSession session, {
    required String deviceId,
    required String entryId,
  }) async {
    await _send(
      () => _client.delete(
        ApiConfig.endpoint(
          '/api/mobile/v1/management/financial-accounting/journals/$entryId',
        ),
        headers: _headers(session, deviceId),
        body: jsonEncode(<String, Object>{'confirm': true}),
      ),
    );
  }

  @override
  Future<AccountingJournalEntry> postJournal(
    UserSession session, {
    required String deviceId,
    required String entryId,
  }) async {
    final response = await _send(
      () => _client.post(
        ApiConfig.endpoint(
          '/api/mobile/v1/management/financial-accounting/journals/$entryId/post',
        ),
        headers: _headers(session, deviceId),
        body: jsonEncode(<String, Object>{'confirm': true}),
      ),
    );
    return _entryFromResponse(response);
  }

  @override
  Future<AccountingJournalEntry> createReversalDraft(
    UserSession session, {
    required String deviceId,
    required String entryId,
    required DateTime postingDate,
    required String description,
  }) async {
    final response = await _send(
      () => _client.post(
        ApiConfig.endpoint(
          '/api/mobile/v1/management/financial-accounting/journals/$entryId/reverse',
        ),
        headers: _headers(session, deviceId),
        body: jsonEncode(<String, Object>{
          'posting_date': _date(postingDate),
          'description': description,
        }),
      ),
    );
    return _entryFromResponse(response);
  }

  Map<String, Object> _journalBody(
    DateTime postingDate,
    String description,
    List<JournalLineDraft> lines,
  ) =>
      <String, Object>{
        'posting_date': _date(postingDate),
        'description': description,
        'lines': lines.map((line) => line.toPayload()).toList(growable: false),
      };

  AccountingJournalEntry _entryFromResponse(
    Map<String, dynamic> response, {
    int statusCode = 200,
  }) {
    final data = stringMap(unwrapSpinaData(response, statusCode: statusCode));
    return AccountingJournalEntry.fromPayload(stringMap(data['entry']));
  }

  Future<Map<String, dynamic>> _send(
    Future<http.Response> Function() request, {
    int expectedStatus = 200,
  }) async {
    late final http.Response response;
    try {
      response = await request();
    } on Exception {
      throw const SpinaApiException(
        'General Journal could not reach the SPINA server.',
        code: 'network_unavailable',
      );
    }

    late final Map<String, dynamic> payload;
    try {
      payload = decodeJsonObject(response.body);
    } on Object {
      throw SpinaApiException(
        'The SPINA server returned unreadable General Journal data.',
        statusCode: response.statusCode,
        code: 'invalid_server_response',
      );
    }

    if (response.statusCode == expectedStatus) {
      return payload;
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

String _date(DateTime value) {
  final month = value.month.toString().padLeft(2, '0');
  final day = value.day.toString().padLeft(2, '0');
  return '${value.year}-$month-$day';
}
