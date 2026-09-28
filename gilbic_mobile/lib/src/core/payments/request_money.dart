import 'package:gilbic_mobile/src/core/management/general_journal.dart';

/// Keep request amounts as decimal text. Legacy numeric callers are supported
/// only while adjacent cents can still be represented by a double.
String requestMoney(Object? value) {
  if (value is num && (!value.isFinite || value.abs() >= 70368744177664)) {
    throw const FormatException('Enter the amount as decimal text.');
  }
  if (value is! String && value is! num) {
    throw const FormatException('Enter a peso amount.');
  }
  final text = value.toString().trim().replaceAll(',', '');
  final normalized = text.replaceFirst(RegExp(r'^0+(?=\d)'), '');
  return journalMoney(normalized, forInput: true);
}

String? tryRequestMoney(Object? value) {
  try {
    return requestMoney(value);
  } on FormatException {
    return null;
  }
}

BigInt? requestMoneyCents(Object? value) {
  final text = tryRequestMoney(value);
  return text == null ? null : journalCents(text);
}
