import 'package:gilbic_mobile/src/core/network/spina_api.dart';

final taxUuidPattern = RegExp(
  r'^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-5][0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}$',
);
final taxMoneyPattern = RegExp(r'^(0|[1-9][0-9]*)\.[0-9]{2}$');
final taxDigestPattern = RegExp(r'^[0-9a-f]{64}$');
final taxDatePattern = RegExp(r'^\d{4}-\d{2}-\d{2}$');
final taxRatePattern = RegExp(r'^(?:0(?:\.[0-9]{1,10})?|1(?:\.0{1,10})?)$');
final taxZeroRatePattern = RegExp(r'^0(?:\.0{1,10})?$');

SpinaApiException invalidTaxPayload(String field) => SpinaApiException(
  'The SPINA server returned incomplete protected tax $field.',
  code: 'invalid_tax_payload',
);

String taxText(Map<String, dynamic> payload, String key) {
  final value = payload[key];
  if (value is! String || value.trim().isEmpty) throw invalidTaxPayload(key);
  return value.trim();
}

String? taxOptionalText(Map<String, dynamic> payload, String key) {
  if (payload[key] == null) return null;
  return taxText(payload, key);
}

String taxUuid(Map<String, dynamic> payload, String key) {
  final value = taxText(payload, key);
  if (!taxUuidPattern.hasMatch(value)) throw invalidTaxPayload(key);
  return value.toLowerCase();
}

String? taxOptionalUuid(Map<String, dynamic> payload, String key) {
  if (payload[key] == null) return null;
  return taxUuid(payload, key);
}

String taxMoney(Map<String, dynamic> payload, String key) {
  final value = taxText(payload, key);
  if (!taxMoneyPattern.hasMatch(value)) throw invalidTaxPayload(key);
  return value;
}

String taxPositiveMoney(Map<String, dynamic> payload, String key) {
  final value = taxMoney(payload, key);
  if (value == '0.00') throw invalidTaxPayload(key);
  return value;
}

String? taxOptionalMoney(Map<String, dynamic> payload, String key) {
  if (payload[key] == null) return null;
  return taxMoney(payload, key);
}

String taxDigest(Map<String, dynamic> payload, String key) {
  final value = taxText(payload, key);
  if (!taxDigestPattern.hasMatch(value)) throw invalidTaxPayload(key);
  return value;
}

String? taxOptionalDigest(Map<String, dynamic> payload, String key) {
  if (payload[key] == null) return null;
  return taxDigest(payload, key);
}

String taxDate(Map<String, dynamic> payload, String key) {
  final value = taxText(payload, key);
  final parsed = DateTime.tryParse(value);
  if (!taxDatePattern.hasMatch(value) ||
      parsed == null ||
      taxDateText(parsed) != value) {
    throw invalidTaxPayload(key);
  }
  return value;
}

String? taxOptionalDate(Map<String, dynamic> payload, String key) {
  if (payload[key] == null) return null;
  return taxDate(payload, key);
}

DateTime taxDateTime(Map<String, dynamic> payload, String key) {
  final parsed = DateTime.tryParse(taxText(payload, key));
  if (parsed == null) throw invalidTaxPayload(key);
  return parsed;
}

DateTime? taxOptionalDateTime(Map<String, dynamic> payload, String key) {
  if (payload[key] == null) return null;
  return taxDateTime(payload, key);
}

int taxNonNegativeInt(Map<String, dynamic> payload, String key) {
  final value = payload[key];
  if (value is! int || value < 0) throw invalidTaxPayload(key);
  return value;
}

int taxPositiveInt(Map<String, dynamic> payload, String key) {
  final value = taxNonNegativeInt(payload, key);
  if (value == 0) throw invalidTaxPayload(key);
  return value;
}

int? taxOptionalPositiveInt(Map<String, dynamic> payload, String key) {
  if (payload[key] == null) return null;
  return taxPositiveInt(payload, key);
}

bool taxBool(Map<String, dynamic> payload, String key) {
  final value = payload[key];
  if (value is! bool) throw invalidTaxPayload(key);
  return value;
}

String taxEnum(Map<String, dynamic> payload, String key, Set<String> allowed) {
  final value = taxText(payload, key);
  if (!allowed.contains(value)) throw invalidTaxPayload(key);
  return value;
}

String taxTypeValue(Map<String, dynamic> payload, String key) => taxEnum(
  payload,
  key,
  const <String>{'documentary_stamp_tax', 'percentage_tax_lending'},
);

String taxDateText(DateTime value) =>
    '${value.year.toString().padLeft(4, '0')}-'
    '${value.month.toString().padLeft(2, '0')}-'
    '${value.day.toString().padLeft(2, '0')}';

int taxCents(String value) {
  if (!taxMoneyPattern.hasMatch(value)) {
    throw ArgumentError('Expected exact currency cents.');
  }
  final parts = value.split('.');
  return int.parse(parts.first) * 100 + int.parse(parts.last);
}
