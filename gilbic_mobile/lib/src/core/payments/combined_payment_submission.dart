import 'package:gilbic_mobile/src/core/network/spina_api.dart';

class CombinedPaymentLegDraft {
  const CombinedPaymentLegDraft({
    required this.routeEntryId,
    required this.loanId,
    required this.routeRevision,
    required this.amount,
  });

  final String routeEntryId;
  final String loanId;
  final String routeRevision;
  final double amount;

  Map<String, Object?> toJson() => <String, Object?>{
        'route_entry_id': routeEntryId,
        'loan_id': loanId,
        'route_revision': routeRevision,
        'amount': amount,
      };
}

class CombinedPaymentSubmissionDraft {
  const CombinedPaymentSubmissionDraft({
    required this.idempotencyKey,
    required this.clientId,
    required this.collectionDate,
    required this.recordedAt,
    required this.deviceId,
    required this.deviceSequence,
    required this.legs,
  });

  final String idempotencyKey;
  final String clientId;
  final DateTime collectionDate;
  final DateTime recordedAt;
  final String deviceId;
  final int deviceSequence;
  final List<CombinedPaymentLegDraft> legs;

  String? validate() {
    if (idempotencyKey.trim().isEmpty || clientId.trim().isEmpty) {
      return 'A combined payment identifier and client are required.';
    }
    if (deviceId.trim().isEmpty || deviceSequence < 1) {
      return 'A valid device identity and sequence are required.';
    }
    if (legs.length != 2) {
      return 'Combined Pay requires exactly one Regular loan and one 7x7 loan.';
    }
    final ids = <String>{};
    for (final leg in legs) {
      if (leg.routeEntryId.trim().isEmpty ||
          leg.loanId.trim().isEmpty ||
          leg.routeRevision.trim().isEmpty ||
          leg.amount <= 0) {
        return 'Every combined payment leg needs a valid route, loan, revision and amount.';
      }
      if (!ids.add(leg.loanId)) {
        return 'Combined payment loans must be different.';
      }
    }
    return null;
  }

  Map<String, Object?> toJson() => <String, Object?>{
        'client_transaction_id': idempotencyKey,
        'client_id': clientId,
        'collection_date': _date(collectionDate),
        'recorded_at': recordedAt.toUtc().toIso8601String(),
        'device_id': deviceId,
        'device_sequence': deviceSequence,
        'legs': legs.map((leg) => leg.toJson()).toList(growable: false),
      };
}

class CombinedPaymentLegResult {
  const CombinedPaymentLegResult({
    required this.loanId,
    required this.transactionId,
    required this.receiptNumber,
    required this.officialBalance,
    this.routeRevision,
  });

  final String loanId;
  final String transactionId;
  final String receiptNumber;
  final double officialBalance;
  final String? routeRevision;

  factory CombinedPaymentLegResult.fromPayload(Map<String, dynamic> payload) {
    return CombinedPaymentLegResult(
      loanId: _requiredString(payload, 'loan_id'),
      transactionId: _requiredString(payload, 'transaction_id'),
      receiptNumber: _requiredString(payload, 'receipt_number'),
      officialBalance: _requiredDouble(payload, 'official_balance'),
      routeRevision: firstNonEmptyString(<Object?>[payload['route_revision']]),
    );
  }
}

class CombinedPaymentSubmissionResult {
  const CombinedPaymentSubmissionResult({
    required this.status,
    required this.duplicate,
    required this.idempotencyKey,
    required this.clientId,
    required this.totalAmount,
    required this.legs,
    required this.message,
  });

  final String status;
  final bool duplicate;
  final String idempotencyKey;
  final String clientId;
  final double totalAmount;
  final List<CombinedPaymentLegResult> legs;
  final String message;

  bool get isFinalSuccess => status == 'accepted' || status == 'duplicate';

  List<String> get receiptNumbers =>
      legs.map((leg) => leg.receiptNumber).toList(growable: false);

  factory CombinedPaymentSubmissionResult.fromPayload(Object? value) {
    final payload = stringMap(value);
    final rawLegs = payload['legs'];
    if (rawLegs is! List) {
      throw const SpinaApiException(
        'The SPINA server returned incomplete combined payment data.',
        code: 'invalid_combined_payment_payload',
      );
    }
    return CombinedPaymentSubmissionResult(
      status: _requiredString(payload, 'status').toLowerCase(),
      duplicate: payload['duplicate'] == true,
      idempotencyKey: _requiredString(payload, 'client_transaction_id'),
      clientId: _requiredString(payload, 'client_id'),
      totalAmount: _requiredDouble(payload, 'total_amount'),
      legs: rawLegs
          .map((item) => CombinedPaymentLegResult.fromPayload(stringMap(item)))
          .toList(growable: false),
      message: firstNonEmptyString(<Object?>[payload['message']]) ??
          'Regular + 7x7 payments saved.',
    );
  }
}

String _requiredString(Map<String, dynamic> payload, String key) {
  final value = firstNonEmptyString(<Object?>[payload[key]]);
  if (value == null) {
    throw SpinaApiException(
      'The SPINA server omitted $key.',
      code: 'invalid_combined_payment_payload',
    );
  }
  return value;
}

double _requiredDouble(Map<String, dynamic> payload, String key) {
  final value = payload[key];
  if (value is num) {
    return value.toDouble();
  }
  final parsed = double.tryParse(value?.toString() ?? '');
  if (parsed == null) {
    throw SpinaApiException(
      'The SPINA server omitted $key.',
      code: 'invalid_combined_payment_payload',
    );
  }
  return parsed;
}

String _date(DateTime value) {
  return '${value.year.toString().padLeft(4, '0')}-'
      '${value.month.toString().padLeft(2, '0')}-'
      '${value.day.toString().padLeft(2, '0')}';
}
