class RemittanceSettlementSplit {
  RemittanceSettlementSplit.fromPayload(Object? value, Object? total) {
    if (value is! Map) {
      throw const FormatException(
        'Retained settlement amounts are unavailable.',
      );
    }
    final amounts = <String, String>{};
    for (final key in [
      'gross_obligation',
      'authorized_credit_amount',
      'physical_cash_required',
      'physical_amount',
      'excess_amount',
    ]) {
      final amount = value[key];
      if (amount is! String ||
          !RegExp(r'^(0|[1-9][0-9]{0,15})\.[0-9]{2}$').hasMatch(amount)) {
        throw const FormatException(
          'Retained settlement amounts must be exact cents.',
        );
      }
      amounts[key] = amount;
    }
    BigInt cents(String key) => BigInt.parse(amounts[key]!.replaceAll('.', ''));
    if (amounts['gross_obligation'] != total ||
        cents('authorized_credit_amount') <= BigInt.zero ||
        cents('gross_obligation') !=
            cents('authorized_credit_amount') +
                cents('physical_cash_required') ||
        cents('physical_amount') !=
            cents('physical_cash_required') + cents('excess_amount')) {
      throw const FormatException(
        'Retained cash and credit do not match the remittance.',
      );
    }
    gross = amounts['gross_obligation']!;
    credit = amounts['authorized_credit_amount']!;
    physical = amounts['physical_amount']!;
    excess = amounts['excess_amount']!;
  }
  late final String gross, credit, physical, excess;
  String get description =>
      'Actual cash received: PHP $physical · Credit applied: PHP $credit · Cash excess: PHP $excess';
}
