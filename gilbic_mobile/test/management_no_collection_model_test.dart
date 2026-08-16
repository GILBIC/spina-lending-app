import 'package:flutter_test/flutter_test.dart';
import 'package:gilbic_mobile/src/core/management/management_no_collection.dart';
import 'package:gilbic_mobile/src/core/management/management_no_collection_preview.dart';

void main() {
  test('loan state keeps contractual and effective dates separate', () {
    final state = ManagementNoCollectionLoanState.fromPayload(
      <String, Object?>{
        'loan_id': 'loan-1',
        'loan_number': 'SPN-001',
        'client_id': 'client-1',
        'client_name': 'Ana Client',
        'loan_type': 'Regular',
        'schedule_id': 'schedule-1',
        'schedule_version': 2,
        'payment_frequency': 'daily',
        'contract_reference': 'CTR-001',
        'operational_version': 3,
        'installments': <Object?>[
          <String, Object?>{
            'installment_id': 10,
            'installment_number': 5,
            'contractual_due_date': '2026-08-16',
            'effective_due_date': '2026-08-17',
            'contractual_amount': '200.00',
            'allocated_amount': '0.00',
            'remaining_amount': '200.00',
            'is_paid': false,
            'is_partly_paid': false,
            'last_adjustment_id': 'adjustment-1',
          },
        ],
        'active_no_collection': <Object?>[],
      },
    );

    expect(state.operationalVersion, 3);
    expect(state.installments.single.contractualDueDate, DateTime(2026, 8, 16));
    expect(state.installments.single.effectiveDueDate, DateTime(2026, 8, 17));
    expect(state.installments.single.isShifted, isTrue);
  });

  test('preview parses exact server old-to-new schedule shifts', () {
    final preview = ManagementNoCollectionPreview.fromPayload(
      <String, Object?>{
        'loan_id': 'loan-1',
        'operational_version': 3,
        'no_collection_date': '2026-08-17',
        'payment_frequency': 'daily',
        'shifts': <Object?>[
          <String, Object?>{
            'installment_id': 11,
            'installment_number': 6,
            'contractual_due_date': '2026-08-17',
            'prior_effective_due_date': '2026-08-17',
            'new_effective_due_date': '2026-08-18',
            'contractual_amount': '200.00',
          },
        ],
      },
    );

    expect(preview.operationalVersion, 3);
    expect(preview.shifts.single.priorEffectiveDueDate, DateTime(2026, 8, 17));
    expect(preview.shifts.single.newEffectiveDueDate, DateTime(2026, 8, 18));
  });
}
