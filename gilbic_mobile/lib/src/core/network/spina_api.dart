import 'dart:convert';

class SpinaApiException implements Exception {
  const SpinaApiException(
    this._message, {
    this.statusCode,
    this.code,
  });

  final String _message;
  final int? statusCode;
  final String? code;

  /// Keep legacy/internal SPINA identifiers out of user-facing mobile errors.
  /// Internal class and protocol names remain unchanged to avoid risky churn.
  String get message => _message.replaceAll('SPINA', 'Gilbic');

  @override
  String toString() => message;
}

Map<String, dynamic> decodeJsonObject(String body) {
  if (body.trim().isEmpty) {
    return <String, dynamic>{};
  }

  final decoded = jsonDecode(body);
  if (decoded is! Map) {
    throw const SpinaApiException('The server returned an invalid response.');
  }
  return decoded.map((key, value) => MapEntry(key.toString(), value));
}

Map<String, dynamic> stringMap(Object? value) {
  if (value is! Map) {
    return <String, dynamic>{};
  }
  return value.map((key, item) => MapEntry(key.toString(), item));
}

Object? unwrapSpinaData(
  Map<String, dynamic> payload, {
  int? statusCode,
}) {
  if (payload['success'] == false) {
    final error = stringMap(payload['error']);
    throw SpinaApiException(
      firstNonEmptyString(<Object?>[
            payload['message'],
            error['details'],
            error['message'],
          ]) ??
          'The request could not be completed.',
      statusCode: statusCode,
      code: firstNonEmptyString(<Object?>[error['code'], payload['code']]),
    );
  }
  return payload.containsKey('data') ? payload['data'] : payload;
}

String? firstNonEmptyString(Iterable<Object?> values) {
  for (final value in values) {
    final text = value?.toString().trim() ?? '';
    if (text.isNotEmpty && text.toLowerCase() != 'null') {
      return text;
    }
  }
  return null;
}

num? firstNumber(Iterable<Object?> values) {
  for (final value in values) {
    if (value is num) {
      return value;
    }
    final parsed = num.tryParse(value?.toString().replaceAll(',', '').trim() ?? '');
    if (parsed != null) {
      return parsed;
    }
  }
  return null;
}

List<String> stringList(Object? value) {
  if (value is! Iterable) {
    return const <String>[];
  }
  return value
      .map((item) => item?.toString().trim() ?? '')
      .where((item) => item.isNotEmpty)
      .toList(growable: false);
}

String apiErrorMessage(
  Map<String, dynamic> payload, {
  required int statusCode,
}) {
  final error = stringMap(payload['error']);
  return firstNonEmptyString(<Object?>[
        payload['message'],
        payload['detail'],
        error['details'],
        error['message'],
      ]) ??
      (statusCode == 401 || statusCode == 403
          ? 'Invalid username or password.'
          : 'The server could not complete the request.');
}