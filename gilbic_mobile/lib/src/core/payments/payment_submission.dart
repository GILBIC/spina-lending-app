import 'dart:math';

import 'package:gilbic_mobile/src/core/network/spina_api.dart';

enum CollectionEntryType {
  payment('payment'),
  advance('advance'),
  pass('pass');

  const CollectionEntryType(this.apiValue);

  final String apiValue;

  static CollectionEntryType? fromValue(Object? value) {
    final normalized = value?.toString().trim().toLowerCase();
    for (final type in CollectionEntryType.values) {
      if (type.apiValue == normalized || type.name == normalized) {
        return type;
      }
    }
    return null;
  }
}

class PaymentSubmissionDraft {
  const PaymentSubmissionDraft({
    required this.idempotencyKey,
    required this.routeEntryId,
    required this.clientId,
    required this.loanId,
    required this.collectionDate,
    required this.entryType,
    required this.recordedAt,
    required this.deviceId,
    required this.deviceSequence,
    this.amount,
    this.advanceFrom,
    this.advanceUntil,
    this.note = '',
    this.routeRevision,
  });

  final String idempotencyKey;
  final String routeEntryId;
  final String clientId;
  final String loanId;
  final DateTime collectionDate;
  final CollectionEntryType entryType;
  final DateTime recordedAt;
  final String deviceId;
  final int deviceSequence;
  final double? amount;
  final DateTime? advanceFrom;
  final DateTime? advanceUntil;
  final String note;
  final String? routeRevision;

  String? validate() {
    if (idempotencyKey.trim().isEmpty) {
      return 'A payment idempotency key is required.';
    }
    if (routeEntryId.trim().isEmpty ||
        clientId.trim().isEmpty ||
        loanId.trim().isEmpty) {
      return 'The route entry, client, and loan are required.';
    }
    if (deviceId.trim().isEmpty || deviceSequence < 1) {
      return 'A valid device identity and sequence are required.';
    }

    switch (entryType) {
      case CollectionEntryType.payment:
        if (amount == null || amount! <= 0) {
          return 'A payment amount greater than zero is required.';
        }
        if (advanceFrom != null || advanceUntil != null) {
          return 'A normal payment cannot contain ADV coverage dates.';
        }
        break;
      case CollectionEntryType.advance:
        if (amount == null || amount! <= 0) {
          return 'An ADV amount greater than zero is required.';
        }
        if (advanceFrom == null || advanceUntil == null) {
          return 'ADV coverage start and end dates are required.';
        }
        if (advanceUntil!.isBefore(advanceFrom!)) {
          return 'ADV coverage cannot end before it starts.';
        }
        break;
      case CollectionEntryType.pass:
        if (amount != null && amount != 0) {
          return 'A PASS entry cannot contain a payment amount.';
        }
        if (advanceFrom != null || advanceUntil != null) {
          return 'A PASS entry cannot contain ADV coverage dates.';
        }
        break;
    }
    return null;
  }

  Map<String, Object?> toJson() {
    return <String, Object?>{
      'client_transaction_id': idempotencyKey,
      'route_entry_id': routeEntryId,
      'client_id': clientId,
      'loan_id': loanId,
      'collection_date': _date(collectionDate),
      'entry_type': entryType.apiValue,
      'amount': amount,
      'advance_from': advanceFrom == null ? null : _date(advanceFrom!),
      'advance_until': advanceUntil == null ? null : _date(advanceUntil!),
      'recorded_at': recordedAt.toUtc().toIso8601String(),
      'device_id': deviceId,
      'device_sequence': deviceSequence,
      'note': note.trim(),
      'route_revision': routeRevision,
    };
  }
}

enum PaymentSubmissionDisposition {
  accepted,
  duplicate,
  conflict,
  rejected,
}

class PaymentSubmissionResult {
  const PaymentSubmissionResult({
    required this.disposition,
    required this.idempotencyKey,
    required this.message,
    this.serverTransactionId,
    this.receiptNumber,
    this.officialBalance,
    this.acceptedAt,
    this.code,
    this.routeRevision,
  });

  final PaymentSubmissionDisposition disposition;
  final String idempotencyKey;
  final String message;
  final String? serverTransactionId;
  final String? receiptNumber;
  final double? officialBalance;
  final DateTime? acceptedAt;
  final String? code;
  final String? routeRevision;

  bool get isFinalSuccess =>
      disposition == PaymentSubmissionDisposition.accepted ||
      disposition == PaymentSubmissionDisposition.duplicate;

  static PaymentSubmissionResult fromPayload(
    Object? value, {
    required String idempotencyKey,
    required PaymentSubmissionDisposition fallbackDisposition,
  }) {
    final outer = stringMap(value);
    final transaction = stringMap(
      outer['transaction'] ?? outer['payment'] ?? outer['collection'],
    );
    final source = transaction.isEmpty ? outer : transaction;
    final rawDisposition = firstNonEmptyString(<Object?>[
      outer['disposition'],
      outer['result'],
      outer['status'],
      source['disposition'],
      source['result'],
      source['status'],
    ]);
    final duplicate = outer['duplicate'] == true ||
        source['duplicate'] == true ||
        rawDisposition?.toLowerCase() == 'duplicate';
    final disposition = duplicate
        ? PaymentSubmissionDisposition.duplicate
        : _dispositionFromValue(rawDisposition) ?? fallbackDisposition;

    return PaymentSubmissionResult(
      disposition: disposition,
      idempotencyKey: firstNonEmptyString(<Object?>[
            outer['client_transaction_id'],
            outer['idempotency_key'],
            source['client_transaction_id'],
            source['idempotency_key'],
          ]) ??
          idempotencyKey,
      message: firstNonEmptyString(<Object?>[
            outer['message'],
            source['message'],
          ]) ??
          _defaultMessage(disposition),
      serverTransactionId: firstNonEmptyString(<Object?>[
        source['transaction_id'],
        source['payment_id'],
        source['collection_id'],
        source['id'],
        outer['transaction_id'],
      ]),
      receiptNumber: firstNonEmptyString(<Object?>[
        source['receipt_number'],
        source['receipt_no'],
        outer['receipt_number'],
      ]),
      officialBalance: firstNumber(<Object?>[
        source['official_balance'],
        source['remaining_balance'],
        source['balance'],
        outer['official_balance'],
      ])?.toDouble(),
      acceptedAt: DateTime.tryParse(
        firstNonEmptyString(<Object?>[
              source['accepted_at'],
              source['posted_at'],
              source['created_at'],
              outer['accepted_at'],
            ]) ??
            '',
      ),
      code: firstNonEmptyString(<Object?>[
        outer['code'],
        stringMap(outer['error'])['code'],
        source['code'],
      ]),
      routeRevision: firstNonEmptyString(<Object?>[
        source['route_revision'],
        outer['route_revision'],
      ]),
    );
  }
}

abstract interface class IdempotencyKeyGenerator {
  String generate();
}

class SecureIdempotencyKeyGenerator implements IdempotencyKeyGenerator {
  SecureIdempotencyKeyGenerator({Random? random})
      : _random = random ?? Random.secure();

  final Random _random;

  @override
  String generate() {
    final bytes = List<int>.generate(16, (_) => _random.nextInt(256));
    bytes[6] = (bytes[6] & 0x0f) | 0x40;
    bytes[8] = (bytes[8] & 0x3f) | 0x80;
    final hex = bytes.map((byte) => byte.toRadixString(16).padLeft(2, '0')).join();
    return '${hex.substring(0, 8)}-'
        '${hex.substring(8, 12)}-'
        '${hex.substring(12, 16)}-'
        '${hex.substring(16, 20)}-'
        '${hex.substring(20)}';
  }
}

PaymentSubmissionDisposition? _dispositionFromValue(String? value) {
  return switch (value?.trim().toLowerCase()) {
    'accepted' || 'success' || 'posted' =>
      PaymentSubmissionDisposition.accepted,
    'duplicate' || 'replayed' => PaymentSubmissionDisposition.duplicate,
    'conflict' => PaymentSubmissionDisposition.conflict,
    'rejected' || 'invalid' || 'failed' =>
      PaymentSubmissionDisposition.rejected,
    _ => null,
  };
}

String _defaultMessage(PaymentSubmissionDisposition disposition) {
  return switch (disposition) {
    PaymentSubmissionDisposition.accepted => 'The collection was accepted.',
    PaymentSubmissionDisposition.duplicate =>
      'This collection was already accepted.',
    PaymentSubmissionDisposition.conflict =>
      'The collection conflicts with newer server data.',
    PaymentSubmissionDisposition.rejected =>
      'The collection was rejected by the server.',
  };
}

String _date(DateTime value) {
  return '${value.year.toString().padLeft(4, '0')}-'
      '${value.month.toString().padLeft(2, '0')}-'
      '${value.day.toString().padLeft(2, '0')}';
}
