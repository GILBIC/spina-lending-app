import 'package:gilbic_mobile/src/core/network/spina_api.dart';

final RegExp _moneyPattern = RegExp(r'^\d+(?:\.\d{1,2})?$');

class ClientGcashCapability {
  const ClientGcashCapability({
    required this.provider,
    required this.mode,
    required this.checkoutAvailable,
    required this.settlementVerificationReady,
    required this.paymentAvailable,
    required this.message,
    required this.officialPaymentRule,
  });

  final String provider;
  final String mode;
  final bool checkoutAvailable;
  final bool settlementVerificationReady;
  final bool paymentAvailable;
  final String message;
  final String officialPaymentRule;

  bool get isSandbox => mode.toLowerCase() == 'sandbox';
  bool get isLive => mode.toLowerCase() == 'live';

  factory ClientGcashCapability.fromPayload(Map<String, dynamic> payload) {
    return ClientGcashCapability(
      provider: _requiredString(payload, 'provider'),
      mode: _requiredString(payload, 'mode'),
      checkoutAvailable: _requiredBool(payload, 'checkout_available'),
      settlementVerificationReady:
          _requiredBool(payload, 'settlement_verification_ready'),
      paymentAvailable: _requiredBool(payload, 'payment_available'),
      message: _requiredString(payload, 'message'),
      officialPaymentRule: _requiredString(payload, 'official_payment_rule'),
    );
  }
}

class ClientGcashAllocation {
  const ClientGcashAllocation({
    required this.loanId,
    required this.amount,
  });

  final String loanId;
  final String amount;

  Map<String, dynamic> toPayload() => <String, dynamic>{
        'loan_id': loanId,
        'amount': amount,
      };

  factory ClientGcashAllocation.fromPayload(Map<String, dynamic> payload) {
    return ClientGcashAllocation(
      loanId: _requiredString(payload, 'loan_id'),
      amount: _requiredMoneyText(payload, 'amount'),
    );
  }
}

class ClientGcashIntent {
  const ClientGcashIntent({
    required this.intentId,
    required this.provider,
    required this.mode,
    required this.status,
    required this.currency,
    required this.amount,
    required this.officialPaymentPosted,
    required this.allocations,
    this.providerReference,
    this.checkoutUrl,
    this.qrValue,
    this.expiresAt,
    this.verifiedPaidAt,
    this.officialCollectionTransactionId,
  });

  final String intentId;
  final String provider;
  final String mode;
  final String? providerReference;
  final String status;
  final String currency;
  final String amount;
  final String? checkoutUrl;
  final String? qrValue;
  final DateTime? expiresAt;
  final DateTime? verifiedPaidAt;
  final bool officialPaymentPosted;
  final String? officialCollectionTransactionId;
  final List<ClientGcashAllocation> allocations;

  bool get isPending => status.toLowerCase() == 'provider_pending';
  bool get isVerified => status.toLowerCase() == 'paid_verified';

  factory ClientGcashIntent.fromPayload(Map<String, dynamic> payload) {
    final rawAllocations = payload['allocations'];
    if (rawAllocations is! List) {
      throw const SpinaApiException(
        'The SPINA server returned incomplete GCash allocation data.',
        code: 'invalid_client_gcash_payload',
      );
    }
    return ClientGcashIntent(
      intentId: _requiredString(payload, 'intent_id'),
      provider: _requiredString(payload, 'provider'),
      mode: _requiredString(payload, 'mode'),
      providerReference: _optionalString(payload['provider_reference']),
      status: _requiredString(payload, 'status'),
      currency: _requiredString(payload, 'currency'),
      amount: _requiredMoneyText(payload, 'amount'),
      checkoutUrl: _optionalString(payload['checkout_url']),
      qrValue: _optionalString(payload['qr_value']),
      expiresAt: _optionalDate(payload['expires_at']),
      verifiedPaidAt: _optionalDate(payload['verified_paid_at']),
      officialPaymentPosted: _requiredBool(payload, 'official_payment_posted'),
      officialCollectionTransactionId:
          _optionalString(payload['official_collection_transaction_id']),
      allocations: rawAllocations
          .map(
            (item) => ClientGcashAllocation.fromPayload(stringMap(item)),
          )
          .toList(growable: false),
    );
  }
}

String _requiredString(Map<String, dynamic> payload, String key) {
  final value = _optionalString(payload[key]);
  if (value == null) {
    throw SpinaApiException(
      'The SPINA server omitted $key from the GCash response.',
      code: 'invalid_client_gcash_payload',
    );
  }
  return value;
}

String? _optionalString(Object? value) {
  final text = value?.toString().trim() ?? '';
  return text.isEmpty ? null : text;
}

String _requiredMoneyText(Map<String, dynamic> payload, String key) {
  final text = payload[key]?.toString().trim() ?? '';
  final match = _moneyPattern.firstMatch(text);
  if (match == null) {
    throw SpinaApiException(
      'The SPINA server omitted $key from the GCash response.',
      code: 'invalid_client_gcash_payload',
    );
  }
  final parts = text.split('.');
  final whole = BigInt.parse(parts.first);
  final fraction = parts.length == 2 ? parts.last.padRight(2, '0') : '00';
  final cents = whole * BigInt.from(100) + BigInt.parse(fraction);
  if (cents <= BigInt.zero) {
    throw SpinaApiException(
      'The SPINA server omitted $key from the GCash response.',
      code: 'invalid_client_gcash_payload',
    );
  }
  return text;
}

bool _requiredBool(Map<String, dynamic> payload, String key) {
  final value = payload[key];
  if (value is bool) {
    return value;
  }
  if (value is String) {
    final normalized = value.trim().toLowerCase();
    if (normalized == 'true') {
      return true;
    }
    if (normalized == 'false') {
      return false;
    }
  }
  throw SpinaApiException(
    'The SPINA server omitted $key from the GCash response.',
    code: 'invalid_client_gcash_payload',
  );
}

DateTime? _optionalDate(Object? value) {
  final text = _optionalString(value);
  return text == null ? null : DateTime.tryParse(text);
}
