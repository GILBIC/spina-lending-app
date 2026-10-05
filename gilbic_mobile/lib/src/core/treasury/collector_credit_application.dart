import 'package:gilbic_mobile/src/core/treasury/treasury_models.dart';

void creditCheck(bool valid) {
  if (!valid) {
    throw const FormatException(
      'The approved Collector credit does not match this count. Review its current approval.',
    );
  }
}

Map<String, dynamic> collectorCreditCoordinates(Map value) {
  final approval = value['credit_application'] as Map?;
  final id = value['credit_application_id'] ?? approval?['id'];
  final version = value['credit_application_version'] ?? approval?['version'];
  creditCheck((id == null) == (version == null));
  if (id != null) {
    creditCheck(treasuryUuid(id) && version is int && version > 0);
  }
  return {'credit_application_id': id, 'credit_application_version': version};
}

void validateCollectorCreditPreview(
  Map raw,
  String? selectedId,
  int? selectedVersion,
) {
  creditCheck((selectedId == null) == (selectedVersion == null));
  if (raw['can_count'] != true && raw['credit_application'] == null) return;
  if (selectedId == null) {
    creditCheck(
      raw['authorized_credit_application'] == '0.00' &&
          raw['credit_application'] == null,
    );
    return;
  }
  final approval = treasuryObject(raw['credit_application']);
  creditCheck(
    approval['id'] == selectedId &&
        approval['version'] == selectedVersion &&
        approval['kind'] == 'application' &&
        approval['status'] == 'reserved' &&
        approval['event_id'] == null &&
        approval['remittance_id'] == raw['remittance_id'] &&
        approval['account_id'] == raw['account_id'] &&
        approval['recipient_user_id'] == raw['recipient_user_id'] &&
        approval['collector_user_id'] == raw['collector_user_id'],
  );
  TreasuryMoney(approval['amount'], positive: true);
  BigInt cents(Object? value) =>
      BigInt.parse((value as String).replaceAll('.', ''));
  creditCheck(
    approval['amount'] == raw['authorized_credit_application'] &&
        raw['refund_due_total'] == '0.00' &&
        cents(raw['gross_obligation']) ==
            cents(raw['physical_cash_required']) + cents(approval['amount']) &&
        approval['source_digest'] == raw['remittance_source_digest'],
  );
}

void validateCollectorCreditOutcome(Map result, Map body, Map held) {
  final records = held['surplus_records'] as Map? ?? {};
  if (body['action'] == 'collector_surplus_application_prepare') {
    final row = treasuryObject(result['action_record']);
    creditCheck(
      row['kind'] == 'application' &&
          row['status'] == 'reserved' &&
          row['event_id'] == null &&
          row['event_version'] == null &&
          row['acknowledgment_id'] == null &&
          row['remittance_id'] == body['remittance_id'] &&
          row['source_digest'] == body['source_digest'] &&
          row['amount'] == body['amount'] &&
          row['collector_request_id'] == body['collector_request_id'] &&
          row['recipient_user_id'] == held['actor_user_id'],
    );
  }
  if (![
    'collector_count_record',
    'collector_count_accept',
  ].contains(body['action'])) {
    return;
  }
  final reference =
      records[body['action'] == 'collector_count_record'
              ? 'count_review'
              : 'count']
          as Map?;
  final submitted = collectorCreditCoordinates(body);
  if (reference == null) {
    creditCheck(submitted['credit_application_id'] == null);
    return;
  }
  final expected = collectorCreditCoordinates(reference);
  creditCheck(canonicalTreasury(expected) == canonicalTreasury(submitted));
  if (body['action'] == 'collector_count_record') {
    final count = treasuryObject(result['count']);
    creditCheck(
      canonicalTreasury(collectorCreditCoordinates(count)) ==
          canonicalTreasury(expected),
    );
    if (expected['credit_application_id'] != null) {
      creditCheck(
        canonicalTreasury(count['credit_application']) ==
                canonicalTreasury(reference['credit_application']) &&
            count['authorized_credit_application'] ==
                reference['authorized_credit_application'] &&
            count['remittance_source_digest'] ==
                reference['remittance_source_digest'],
      );
    }
  } else if (expected['credit_application_id'] != null) {
    final approval = treasuryObject(reference['credit_application']),
        action = treasuryObject(result['action_record']),
        entry = treasuryObject(result['application_entry']),
        settlement = treasuryObject(result['settlement']),
        credit = treasuryObject(result['credit']);
    final count = treasuryObject(result['count']);
    creditCheck(
      canonicalTreasury(count['credit_application']) ==
              canonicalTreasury(approval) &&
          canonicalTreasury(collectorCreditCoordinates(count)) ==
              canonicalTreasury(expected),
    );
    creditCheck(
      action['id'] == approval['id'] &&
          action['version'] == (approval['version'] as int) + 1 &&
          action['status'] == 'applied' &&
          action['kind'] == 'application' &&
          action['event_id'] == null &&
          action['amount'] == approval['amount'],
    );
    creditCheck(
      entry['kind'] == 'application' &&
          treasuryUuid(entry['id']) &&
          entry['action_id'] == action['id'] &&
          entry['credit_id'] == action['credit_id'] &&
          entry['amount'] == action['amount'] &&
          entry['settlement_id'] == settlement['id'] &&
          entry['accepted_at'] == settlement['accepted_at'],
    );
    creditCheck(
      credit['id'] == action['credit_id'] &&
          settlement['authorized_credit_amount'] == approval['amount'] &&
          result['source_account_id'] == approval['origin_account_id'],
    );
  } else {
    creditCheck(result['application_entry'] == null);
  }
}
