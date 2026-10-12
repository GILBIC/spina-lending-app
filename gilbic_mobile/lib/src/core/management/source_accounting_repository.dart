import 'dart:convert';

import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/config/api_config.dart';
import 'package:gilbic_mobile/src/core/network/spina_api.dart';
import 'package:gilbic_mobile/src/core/treasury/treasury_models.dart';
import 'package:http/http.dart' as http;

const sourceAccountingBase = '/api/mobile/v1/management/financial-accounting';
const sourceTreasuryBase = '/api/mobile/v1/treasury';
const liabilityKinds = <String, (String, String)>{
  '2000': ('trade_payable', 'Trade payable'),
  '2300': ('borrowing_external', 'External borrowing'),
  '2310': ('borrowing_owner', 'Owner borrowing'),
  '2320': ('interest', 'Interest payable'),
  '2330': ('wages', 'Wages payable'),
  '2340': ('contrib', 'Contributions payable'),
};

void accountingCheck(
  bool valid, [
  String message =
      'These accounting records are incomplete. Reload before continuing.',
]) {
  if (!valid) throw FormatException(message);
}

bool accountingDigest(Object? value) =>
    value is String && RegExp(r'^[0-9a-f]{64}$').hasMatch(value);
bool accountingDate(Object? value) =>
    value is String &&
    RegExp(r'^\d{4}-\d{2}-\d{2}$').hasMatch(value) &&
    DateTime.tryParse(value)?.toIso8601String().substring(0, 10) == value;
Map<String, dynamic> accountingObject(Object? value) => treasuryObject(value);
List<Map<String, dynamic>> accountingRows(Object? value) {
  accountingCheck(value is List);
  return (value as List).map(accountingObject).toList(growable: false);
}

Map<String, dynamic> validateReceiptReview(
  Map<String, dynamic> value, {
  required String bookId,
  required String accountId,
  required String receiptId,
  required String mappingId,
}) {
  accountingCheck(
    value['book_id'] == bookId &&
        value['treasury_account_id'] == accountId &&
        value['receipt_id'] == receiptId &&
        value['mapping_id'] == mappingId &&
        treasuryUuid(value['event_id']) &&
        treasuryUuid(value['fiscal_period_id']) &&
        accountingDate(value['posting_date']) &&
        accountingDigest(value['source_digest']),
  );
  TreasuryMoney(value['amount'], positive: true);
  final mapping = accountingObject(value['mapping']);
  accountingCheck(
    [
          '1010',
          '1030',
        ].contains(accountingObject(mapping['cash_snapshot'])['code']) &&
        accountingObject(mapping['liability_snapshot'])['code'] == '2200' &&
        accountingDigest(accountingObject(value['evidence'])['sha256']),
  );
  return accountingObject(immutableTreasury(value));
}

Map<String, dynamic> validateLiabilitySchedule(
  Map<String, dynamic> value,
  String bookId,
) {
  accountingCheck(
    accountingObject(value['book'])['book_id'] == bookId &&
        accountingDate(value['as_of']) &&
        value['comprehensive_source_coverage'] == false &&
        value['registered_controls_reconciled'] is bool,
  );
  for (final row in accountingRows(value['obligations'])) {
    accountingCheck(
      treasuryUuid(row['obligation_id']) &&
          row['book_id'] == bookId &&
          liabilityKinds[row['account_code']]?.$1 == row['kind'] &&
          row['counterparty'] is String &&
          (row['due_date'] == null || accountingDate(row['due_date'])),
    );
    TreasuryMoney(row['recognized_amount']);
    TreasuryMoney(row['outstanding_amount']);
  }
  for (final row in accountingRows(value['movements'])) {
    accountingCheck(
      [
            row['claim_id'],
            row['obligation_id'],
            row['journal_line_id'],
          ].every(treasuryUuid) &&
          ['recognition', 'settlement', 'reversal'].contains(row['kind']) &&
          accountingDate(row['posting_date']) &&
          (row['reverses_claim_id'] == null ||
              treasuryUuid(row['reverses_claim_id'])),
    );
    TreasuryMoney(row['signed_amount'], signed: true);
  }
  for (final row in accountingRows(value['reconciliation'])) {
    accountingCheck(
      liabilityKinds.containsKey(row['account_code']) &&
          row['unregistered_line_count'] is int &&
          (row['unregistered_line_count'] as int) >= 0,
    );
    for (final key in ['ledger_balance', 'schedule_balance', 'difference']) {
      TreasuryMoney(row[key], signed: true);
    }
  }
  for (final row in accountingRows(value['unregistered_lines'])) {
    accountingCheck(
      treasuryUuid(row['journal_line_id']) &&
          treasuryUuid(row['journal_entry_id']) &&
          liabilityKinds.containsKey(row['account_code']) &&
          accountingDate(row['posting_date']) &&
          row['source_type'] is String &&
          (row['source_reference'] == null ||
              row['source_reference'] is String) &&
          (row['reversal_of_entry_id'] == null ||
              treasuryUuid(row['reversal_of_entry_id'])),
    );
    TreasuryMoney(row['debit']);
    TreasuryMoney(row['credit']);
  }
  return accountingObject(immutableTreasury(value));
}

abstract interface class SourceAccountingRepository {
  Future<Map<String, dynamic>> read(
    UserSession session, {
    required String deviceId,
    required String path,
  });
  Future<Map<String, dynamic>> write(
    UserSession session, {
    required String deviceId,
    required String path,
    required Map<String, dynamic> body,
  });
}

class SpinaSourceAccountingRepository implements SourceAccountingRepository {
  SpinaSourceAccountingRepository({http.Client? client})
    : _client = client ?? http.Client();
  final http.Client _client;

  @override
  Future<Map<String, dynamic>> read(
    UserSession session, {
    required String deviceId,
    required String path,
  }) => _request(session, deviceId, path);
  @override
  Future<Map<String, dynamic>> write(
    UserSession session, {
    required String deviceId,
    required String path,
    required Map<String, dynamic> body,
  }) => _request(session, deviceId, path, body);

  Future<Map<String, dynamic>> _request(
    UserSession session,
    String deviceId,
    String path, [
    Map<String, dynamic>? body,
  ]) async {
    final headers = {
      'Accept': 'application/json',
      'Content-Type': 'application/json',
      'Authorization': 'Bearer ${session.accessToken}',
      'X-Device-Id': deviceId,
    };
    late final http.Response response;
    try {
      response = body == null
          ? await _client.get(ApiConfig.endpoint(path), headers: headers)
          : await _client.post(
              ApiConfig.endpoint(path),
              headers: headers,
              body: jsonEncode(body),
            );
    } on Exception {
      throw const SpinaApiException(
        'Accounting could not be reached. Retry the unchanged request if it was submitted.',
        code: 'network_unavailable',
      );
    }
    final payload = decodeJsonObject(response.body);
    if (response.statusCode < 200 || response.statusCode >= 300) {
      throw SpinaApiException(
        apiErrorMessage(payload, statusCode: response.statusCode),
        statusCode: response.statusCode,
      );
    }
    return stringMap(unwrapSpinaData(payload, statusCode: response.statusCode));
  }
}
