import 'package:flutter_test/flutter_test.dart';
import 'package:gilbic_mobile/src/core/management/contract_collection_activation.dart';

void main() {
  test(
    'native initial reconciliation is available but not reported complete',
    () {
      final loan = ContractCollectionActivationLoan.fromPayload({
        'loan_id': 'native-loan',
        'can_activate': true,
        'balance_reconciled': false,
        'native_reconciliation_available': true,
      });
      expect(loan.canActivate, isTrue);
      expect(loan.nativeReconciliationAvailable, isTrue);
      expect(loan.balanceReconciled, isFalse);
      expect(loan.readinessLabel, 'Ready for reconciliation');
    },
  );

  test('older preview payloads do not infer native reconciliation', () {
    final loan = ContractCollectionActivationLoan.fromPayload({
      'loan_id': 'legacy-loan',
      'can_activate': false,
      'balance_reconciled': false,
    });
    expect(loan.nativeReconciliationAvailable, isFalse);
    expect(loan.canActivate, isFalse);
  });
}
