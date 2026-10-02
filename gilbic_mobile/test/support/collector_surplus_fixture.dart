import 'treasury_fixture.dart' as t;
import 'package:gilbic_mobile/src/core/treasury/collector_surplus_models.dart';

const surplusCollector = '88888888-8888-4888-8888-888888888888';
const surplusRemittance = '99999999-9999-4999-8999-999999999999';
const surplusCount = '77777777-7777-4777-8777-777777777777';
const surplusRequest = 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa';
const surplusAction = 'bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb';
const surplusAck = 'cccccccc-cccc-4ccc-8ccc-cccccccccccc';
Map<String, dynamic> surplusCredit({bool own = true}) => {
  'id': t.event,
  'version': 1,
  'case_id': null,
  'opening_anchor_id': null,
  'account_id': t.account,
  'origin_account_id': t.account,
  'ledger_context_id': t.ledger,
  'collector_user_id': own ? t.user : surplusCollector,
  'recognized_amount': '100.00',
  'reclassified_amount': '0.00',
  'returned_amount': '0.00',
  'applied_amount': '0.00',
  'outstanding_amount': '100.00',
  'reserved_amount': '40.00',
  'available_amount': '60.00',
  'frozen': false,
  'status': 'outstanding',
  'created_at': '2026-10-02T00:00:00Z',
  'entries': [],
};
Map<String, dynamic> surplusCountRow({bool short = false}) => {
  'id': surplusCount,
  'version': 1,
  'remittance_id': surplusRemittance,
  'account_id': t.account,
  'ledger_context_id': t.ledger,
  'collector_user_id': surplusCollector,
  'recipient_user_id': t.user,
  'source_digest': 'a' * 64,
  'gross_obligation': '10000.00',
  'refund_due_total': '0.00',
  'physical_cash_required': '10000.00',
  'counted_amount': short ? '9900.00' : '10100.00',
  'difference': short ? '-100.00' : '100.00',
  'counted_at': '2026-10-02T00:00:00Z',
  'recorded_at': '2026-10-02T00:01:00Z',
  'disposition': short ? 'counted_short_rejected' : 'counted_ready',
  'source_snapshot': {'remittance': {}, 'items': [], 'refund_due_releases': []},
  'evidence_id': t.ledger,
};
Map<String, dynamic> surplusActionRow({
  bool own = true,
  String status = 'debited_confirmation_pending',
}) => {
  'id': surplusAction,
  'version': 2,
  'kind': 'return',
  'credit_id': t.event,
  'exception_id': null,
  'collector_request_id': surplusRequest,
  'origin_account_id': t.account,
  'account_id': t.account,
  'paying_account_id': t.account,
  'ledger_context_id': t.ledger,
  'collector_user_id': own ? t.user : surplusCollector,
  'amount': '40.00',
  'destination': {'kind': 'physical_cash', 'recipient_reference': null},
  'status': status,
  'event_id': status == 'reserved' ? null : t.ledger,
  'event_version': status == 'reserved' ? null : 1,
  'acknowledgment_id': null,
  'acknowledgment': null,
  'created_at': '2026-10-02T00:00:00Z',
};
Map<String, dynamic> surplusWorkspace({
  bool own = true,
  CollectorSurplusKind kind = CollectorSurplusKind.credits,
  List<Map<String, dynamic>>? rows,
  bool enabled = true,
  int offset = 0,
}) => {
  'collector_surplus_contract_version': 1,
  'actor': {'user_id': t.user, 'device_id': t.device},
  'mode': own ? 'own' : 'staff',
  'readiness': {
    'enabled': enabled,
    'treasury_ready': true,
    'application_enabled': false,
    'application_supported': false,
    'historical_correction_supported': false,
    'gl_supported': false,
    'blockers': [
      {
        'code': 'unsupported_adapter',
        'message':
            'Historical correction and application execution remain blocked.',
      },
    ],
  },
  'capabilities': {
    'view': true,
    for (final key in [
      'count_record',
      'count_accept',
      'recognize',
      'return_prepare',
      'return_record',
      'action_cancel',
      'return_request',
      'return_acknowledge',
      'application_request',
      'application_prepare',
      'resolve_source',
      'opening_prepare',
      'opening_activate',
      'exception_record',
      'exception_return_prepare',
      'exception_acknowledge',
    ])
      key: enabled,
  },
  'accounts': own
      ? []
      : [
          {
            'id': t.account,
            'ledger_context_id': t.ledger,
            'kind': 'physical_cash',
            'alias': 'Synthetic receiving cash',
            'version': 1,
            'custodian_user_id': t.user,
            'actions': [
              'count_record',
              'count_accept',
              'recognize',
              'return_prepare',
              'return_record',
              'action_cancel',
              'opening_prepare',
              'opening_activate',
              'exception_record',
              'exception_return_prepare',
              'evidence_upload',
            ],
          },
        ],
  'collector_choices': own
      ? []
      : [
          {'id': surplusCollector, 'full_name': 'Synthetic Collector'},
        ],
  'kind': kind.name,
  'items': rows ?? [],
  'total_count': rows?.length ?? 0,
  'totals': kind == CollectorSurplusKind.credits
      ? {
          'outstanding_amount': '100.00',
          'reserved_amount': '40.00',
          'available_amount': '60.00',
        }
      : {},
  'has_more': false,
  'limit': 50,
  'offset': offset,
};
Map<String, dynamic> surplusPreview() => {
  'collector_surplus_contract_version': 1,
  'actor_user_id': t.user,
  'device_id': t.device,
  'account_id': t.account,
  'account_version': 1,
  'ledger_context_id': t.ledger,
  'remittance_id': surplusRemittance,
  'remittance_number': 'Synthetic REM-1',
  'collector_user_id': surplusCollector,
  'recipient_user_id': t.user,
  'status': 'submitted',
  'collection_date': '2026-10-02',
  'source_digest': 'a' * 64,
  'gross_obligation': '10000.00',
  'refund_due_total': '0.00',
  'authorized_credit_application': '0.00',
  'physical_cash_required': '10000.00',
  'source_items': [],
  'refund_due_releases': [],
  'remittance_snapshot': {},
  'can_count': true,
  'blockers': [],
};
Map<String, dynamic> surplusOutcome({
  required String action,
  required String slot,
  required Map<String, dynamic> principal,
  required String disposition,
  String status = 'saved',
  Map<String, dynamic> extra = const {},
}) => {
  'contract_version': 1,
  'request_id': t.requestId,
  'action': action,
  'status': status,
  'target_id': principal['id'],
  'version': principal['version'],
  'result': {
    'collector_surplus_contract_version': 1,
    'disposition': disposition,
    'actor_user_id': t.user,
    'device_id': t.device,
    'account_id': t.account,
    'ledger_context_id': t.ledger,
    'source_account_id': null,
    'blockers': [],
    for (final key in [
      'count',
      'settlement',
      'case',
      'credit',
      'request',
      'action_record',
      'acknowledgment',
      'exception',
      'opening_anchor',
    ])
      key: null,
    slot: principal,
    ...extra,
  },
};
