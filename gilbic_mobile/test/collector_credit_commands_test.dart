import 'package:flutter_test/flutter_test.dart';
import 'package:gilbic_mobile/src/core/treasury/treasury_models.dart';
import 'management_protected_accounting_page_test.dart' show id;

void main() {
  test('credit selection is paired in count recording and acceptance', () {
    for (final action in [
      TreasuryAction.collectorCountRecord,
      TreasuryAction.collectorCountAccept,
    ]) {
      final fields = <String, dynamic>{
        'source_digest': 'a' * 64,
        if (action == TreasuryAction.collectorCountRecord) ...{
          'remittance_id': id(3),
          'counted_amount': '96.00',
          'counted_at': '2026-10-05T10:00:00+08:00',
          'evidence_id': id(4),
          'recipient_attestation': 'Exact counted cash',
          'review_acknowledged': true,
        } else ...{
          'count_id': id(5),
          'count_version': 1,
          'physical_receipt_acknowledged': true,
        },
      };
      TreasuryCommand build(Map<String, dynamic> input) => TreasuryCommand(
        action,
        requestId: id(1),
        accountId: id(2),
        expectedVersion: 1,
        fields: input,
      );
      expect(
        build({
          ...fields,
          'credit_application_id': id(6),
          'credit_application_version': 2,
        }).toJson()['credit_application_version'],
        2,
      );
      expect(
        () => build({...fields, 'credit_application_id': id(6)}),
        throwsFormatException,
      );
      expect(
        () => build({...fields, 'credit_application_version': 2}),
        throwsFormatException,
      );
      expect(
        build(fields).toJson().containsKey('credit_application_id'),
        false,
      );
    }
  });
}
