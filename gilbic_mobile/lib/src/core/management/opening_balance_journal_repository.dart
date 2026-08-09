import 'dart:convert';

import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/config/api_config.dart';
import 'package:gilbic_mobile/src/core/management/opening_balance_journal.dart';
import 'package:gilbic_mobile/src/core/network/spina_api.dart';
import 'package:http/http.dart' as http;

abstract interface class OpeningBalanceJournalRepository {
  Future<OpeningBalanceJournalDraftStatus> load(
    UserSession session, {
    required String deviceId,
    required String workbookId,
  });

  Future<OpeningBalanceJournalDraftStatus> prepare(
    UserSession session, {
    required String deviceId,
    required String workbookId,
  });

  Future<OpeningBalanceJournalDraftStatus> post(
    UserSession session, {
    required String deviceId,
    required String workbookId,
    required String journalEntryId,
    required String totalDebit,
    required String totalCredit,
  });
}

class SpinaOpeningBalanceJournalRepository
    implements OpeningBalanceJournalRepository {
  SpinaOpeningBalanceJournalRepository({http.Client? client})
      : _client = client ?? http.Client();

  final http.Client _client;

  @override
  Future<OpeningBalanceJournalDraftStatus> load(
    UserSession session, {
    required String deviceId,
    required String workbookId,
  }) async {
    final endpoint = ApiConfig.endpoint(
      '/api/mobile/v1/management/financial-accounting/opening-balance-workbook/$workbookId/journal-draft',
    );
    return _parse(
      await _request(
        () => _client.get(endpoint, headers: _headers(session, deviceId)),
      ),
    );
  }

  @override
  Future<OpeningBalanceJournalDraftStatus> prepare(
    UserSession session, {
    required String deviceId,
    required String workbookId,
  }) async {
    final endpoint = ApiConfig.endpoint(
      '/api/mobile/v1/management/financial-accounting/opening-balance-workbook/$workbookId/journal-draft',
    );
    return _parse(
      await _request(
        () => _client.post(
          endpoint,
          headers: _headers(session, deviceId, jsonBody: true),
          body: jsonEncode(<String, Object>{'confirm': true}),
        ),
      ),
    );
  }

  @override
  Future<OpeningBalanceJournalDraftStatus> post(
    UserSession session, {
    required String deviceId,
    required String workbookId,
    required String journalEntryId,
    required String totalDebit,
    required String totalCredit,
  }) async {
    final endpoint = ApiConfig.endpoint(
      '/api/mobile/v1/management/financial-accounting/opening-balance-workbook/$workbookId/journal-draft/post',
    );
    return _parse(
      await _request(
        () => _client.post(
          endpoint,
          headers: _headers(session, deviceId, jsonBody: true),
          body: jsonEncode(<String, Object>{
            'confirm': true,
            'journal_entry_id': journalEntryId,
            'total_debit': totalDebit,
            'total_credit': totalCredit,
          }),
        ),
      ),
    );
  }

  OpeningBalanceJournalDraftStatus _parse(_JournalResponse response) {
    final data = stringMap(
      unwrapSpinaData(response.data, statusCode: response.statusCode),
    );
    return OpeningBalanceJournalDraftStatus.fromPayload(
      stringMap(data['journal_draft']),
    );
  }

  Map<String, String> _headers(
    UserSession session,
    String deviceId, {
    bool jsonBody = false,
  }) {
    return <String, String>{
      'Accept': 'application/json',
      if (jsonBody) 'Content-Type': 'application/json',
      'Authorization': 'Bearer ${session.accessToken}',
      'X-Session-Id': session.accessToken,
      'X-Device-Id': deviceId,
    };
  }

  Future<_JournalResponse> _request(
    Future<http.Response> Function() request,
  ) async {
    late final http.Response response;
    try {
      response = await request();
    } on Exception {
      throw const SpinaApiException(
        'Opening Balance Journal could not reach the SPINA server.',
        code: 'network_unavailable',
      );
    }

    late final Map<String, dynamic> payload;
    try {
      payload = decodeJsonObject(response.body);
    } on Object {
      throw SpinaApiException(
        'The SPINA server returned unreadable opening-balance journal data.',
        statusCode: response.statusCode,
        code: 'invalid_server_response',
      );
    }

    if (response.statusCode >= 200 && response.statusCode < 300) {
      return _JournalResponse(response.statusCode, payload);
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

class _JournalResponse {
  const _JournalResponse(this.statusCode, this.data);

  final int statusCode;
  final Map<String, dynamic> data;
}
