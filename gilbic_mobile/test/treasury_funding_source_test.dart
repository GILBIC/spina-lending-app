import 'package:flutter_test/flutter_test.dart';
import 'package:gilbic_mobile/src/core/collector/collector_route.dart';
import 'package:gilbic_mobile/src/core/management/management_operations.dart';
import 'package:gilbic_mobile/src/core/remittance/cross_remittance.dart';

void main() {
  test(
    'recipient funds applied is distinct from unremitted Collector cash',
    () {
      final entry = ManagementOperationEntry.fromPayload({
        'transaction_id': 'transaction',
        'receipt_number': 'receipt',
        'collection_date': '2026-10-02',
        'accepted_at': '2026-10-02T01:00:00Z',
        'client_code': 'C',
        'client_name': 'Synthetic',
        'loan_number': 'L',
        'loan_type_name': 'Regular',
        'collector_name': 'Staff recorder',
        'entry_type': 'payment',
        'amount': '20.00',
        'official_balance': '30.00',
        'covered_dates': [],
        'edit_version': 0,
        'status': 'wallet_applied',
      });
      expect(entry.statusLabel, 'Recipient funds applied');
      expect(
        CrossCollectionCustodyStatus.fromValue('wallet_applied').label,
        'Recipient funds applied; no Collector cash',
      );
    },
  );
  test(
    'wallet route receipt keeps typed funding identity across encrypted cache',
    () {
      final receipt = CollectorRouteReceipt.fromPayload({
        'transaction_id': 't',
        'receipt_number': 'r',
        'amount': '20.00',
        'entry_type': 'payment',
        'collector_user_id': 'recorder',
        'collector_name': 'Office staff',
        'is_locked': false,
        'funding_source': 'treasury_receipt',
        'funding_receipt_id': 'verified-receipt',
        'funding_account_id': 'recipient-wallet',
      })!;
      expect(receipt.isTreasuryFunded, isTrue);
      expect(receipt.fundingReceiptId, 'verified-receipt');
      expect(receipt.fundingAccountId, 'recipient-wallet');
      expect(
        CollectorRouteReceipt.fromPayload(receipt.toJson())!.isTreasuryFunded,
        isTrue,
      );
      expect(
        CollectorRouteReceipt.fromPayload({
          'transaction_id': 'cash',
          'receipt_number': 'cash',
        })!.isTreasuryFunded,
        isFalse,
      );
    },
  );
}
