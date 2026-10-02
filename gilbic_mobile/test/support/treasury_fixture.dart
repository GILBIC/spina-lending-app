import 'dart:convert';
import 'package:gilbic_mobile/src/core/auth/app_role.dart';
import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/treasury/treasury_models.dart';
import 'package:http/http.dart' as http;

const user = '11111111-1111-4111-8111-111111111111';
const device = '22222222-2222-4222-8222-222222222222';
const account = '33333333-3333-4333-8333-333333333333';
const ledger = '44444444-4444-4444-8444-444444444444';
const requestId = '55555555-5555-4555-8555-555555555555';
const event = '66666666-6666-4666-8666-666666666666';
UserSession session() => const UserSession(
  userId: user,
  username: 'synthetic',
  displayName: 'Test',
  role: AppRole.management,
  rawRole: 'Management',
  accessToken: 'synthetic',
  permissions: ['treasury.view', 'treasury.adjust'],
);
Map<String, dynamic> workspace({bool private = true, bool enabled = true}) => {
  'contract_version': 1,
  'actor': {'user_id': user, 'device_id': device},
  'enabled': enabled,
  'owner_configured': true,
  'blockers': [],
  'capabilities': {
    'movement_classify': enabled,
    'claim_submit': enabled,
    'evidence_upload': enabled,
  },
  'claims': [],
  'accounts': [
    {
      'id': account,
      'ledger_context_id': ledger,
      'context': 'synthetic',
      'kind': 'gcash',
      'currency': 'PHP',
      'alias': 'Synthetic wallet',
      'version': 1,
      'active': true,
      'actions': enabled
          ? ['movement_classify', 'claim_submit', 'evidence_upload']
          : [],
      'balance': private
          ? {
              'available': false,
              'expected_balance': null,
              'message': 'Opening required',
            }
          : null,
      'payment_instructions': 'Synthetic instructions',
    },
  ],
};
Map<String, dynamic> outcome({
  String actor = user,
  String action = 'movement_classify',
}) => {
  'contract_version': 1,
  'request_id': requestId,
  'action': action,
  'status': 'saved',
  'target_id': event,
  'version': 2,
  'result': {
    'actor_user_id': actor,
    'device_id': device,
    'account_id': account,
    'ledger_context_id': ledger,
    'event': {'id': event, 'version': 2},
  },
};
TreasuryCommand command() => TreasuryCommand(
  TreasuryAction.movementClassify,
  requestId: requestId,
  accountId: account,
  expectedVersion: 1,
  fields: {
    'event_id': event,
    'event_version': 1,
    'classification': 'personal',
    'reason': 'Synthetic reason',
  },
);
http.Response jsonResponse(Object? data) => http.Response(
  jsonEncode({'success': true, 'data': data}),
  200,
  headers: {'content-type': 'application/json'},
);
