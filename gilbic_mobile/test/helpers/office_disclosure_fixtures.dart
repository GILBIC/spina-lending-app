import 'package:gilbic_mobile/src/core/office/office_repository.dart';

const disclosureId = '88888888-8888-4888-8888-888888888888';
final disclosureDigest = List.filled(64, 'd').join();

OfficeRecord savedDisclosure(String applicationVersion, String cifVersion, {bool ready = true}) => {
  'id': disclosureId,
  'application_version_id': applicationVersion,
  'cif_version_id': cifVersion,
  'review_digest': disclosureDigest,
  'approval_ready': ready,
  'blockers': ready ? <String>[] : ['private readiness detail'],
  'internal_tax_rule': 'PRIVATE_SOURCE_METADATA',
  'financial_snapshot': {
    'private_evidence': 'PRIVATE_EVIDENCE',
    'components': {
      'principal': '1000.01', 'contractual_interest': '100.00',
      'dst_upfront': '10.00', 'grt_in_repayments': '5.00',
      'renewal_offset': '0.00', 'other_upfront_deductions': '0.00',
      'other_scheduled_charges': '0.00', 'total_upfront_deductions': '10.00',
      'net_proceeds': '990.01', 'total_scheduled_payable': '1105.01',
      'private_component': 'PRIVATE_COMPONENT',
    },
    'disclosure_values': {
      'amount_financed': '990.01', 'finance_charge_total': '115.00',
      'non_finance_charge_total': '0.00', 'effective_interest_rate': ready ? '1.23' : null,
      'rate_period': 'month', 'calculation_method': 'Approved saved method',
    },
    'charge_items': [
      {'item_id': 'DST', 'kind': 'dst', 'timing': 'upfront', 'amount': '10.00',
       'private_reference': 'PRIVATE_ITEM'},
    ],
  },
};
