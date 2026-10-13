import 'package:flutter_test/flutter_test.dart';
import 'package:gilbic_mobile/src/core/auth/app_role.dart';
import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/network/spina_api.dart';
import 'package:gilbic_mobile/src/core/renewals/management_renewal_workflow.dart';
import 'package:gilbic_mobile/src/core/renewals/management_renewal_workflow_repository.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

void main() {
  test('new terms serialize one borrower and preserve unverified identity', () {
    final payload = _draft([_signer('borrower')]).toJson();
    expect(payload['office_processing_required'], isTrue);
    expect(payload['signers'], [
      {
        'party_role': 'borrower',
        'full_name': 'TEST BORROWER',
        'user_id': 'borrower-user-1',
        'government_id_verified': false,
        'selfie_verified': false,
      },
    ]);
  });

  for (final role in ['guarantor', 'surety', 'solidary_co_maker', 'unknown']) {
    for (final officeProcessing in [true, false]) {
      test(
        'rejects stale $role draft before sending (office=$officeProcessing)',
        () async {
          var requests = 0;
          final repository = SpinaManagementRenewalWorkflowRepository(
            client: MockClient((_) async {
              requests += 1;
              return http.Response('{}', 200);
            }),
          );

          await expectLater(
            () => repository.submitTerms(
              _session,
              deviceId: 'management-device',
              requestId: 'request-1',
              draft: _draft([
                _signer('borrower'),
                _signer(role),
              ], officeProcessing: officeProcessing),
            ),
            throwsA(
              isA<SpinaApiException>().having(
                (error) => error.code,
                'code',
                'invalid_renewal_signers',
              ),
            ),
          );
          expect(requests, 0);
        },
      );
    }
  }

  for (final officeProcessing in [true, false]) {
    test('rejects duplicate borrowers (office=$officeProcessing)', () {
      expect(
        () => _draft([
          _signer('borrower'),
          _signer('borrower'),
        ], officeProcessing: officeProcessing).toJson(),
        throwsA(isA<SpinaApiException>()),
      );
    });
  }

  for (final entry in <String, List<ManagementRenewalSignerDraft>>{
    'absent signer': [],
    'null account': [_signer('borrower', userId: null)],
    'blank account': [_signer('borrower', userId: '   ')],
  }.entries) {
    test('remote approval rejects ${entry.key}', () {
      expect(
        () => _draft(entry.value, officeProcessing: false).toJson(),
        throwsA(isA<SpinaApiException>()),
      );
    });
  }

  test('office approval allows physical borrower without an app account', () {
    expect(_draft([]).toJson()['signers'], isEmpty);
    final payload = _draft([_signer('borrower', userId: null)]).toJson();
    expect((payload['signers'] as List).single['user_id'], isNull);
  });

  test('rejection without signers remains available', () {
    const draft = ManagementRenewalTermsDraft(
      decision: 'rejected',
      reviewNote: 'Current capacity is insufficient',
      overrideReason: '',
      officeProcessingRequired: true,
      signers: [],
    );
    expect(draft.toJson()['decision'], 'rejected');
  });

  test('remote draft retains linked borrower for server evidence checks', () {
    final payload = _draft([
      _signer('borrower'),
    ], officeProcessing: false).toJson();
    expect(payload['office_processing_required'], isFalse);
    expect((payload['signers'] as List).single['user_id'], 'borrower-user-1');
    expect(
      (payload['signers'] as List).single['government_id_verified'],
      isFalse,
    );
    expect((payload['signers'] as List).single['selfie_verified'], isFalse);
  });
}

ManagementRenewalTermsDraft _draft(
  List<ManagementRenewalSignerDraft> signers, {
  bool officeProcessing = true,
}) => ManagementRenewalTermsDraft(
  decision: 'approved',
  approvedPrincipal: '6000.00',
  reviewNote: '',
  overrideReason: '',
  officeProcessingRequired: officeProcessing,
  signers: signers,
);

ManagementRenewalSignerDraft _signer(
  String role, {
  String? userId = 'borrower-user-1',
}) => ManagementRenewalSignerDraft(
  partyRole: role,
  fullName: 'TEST BORROWER',
  userId: userId,
  governmentIdVerified: false,
  selfieVerified: false,
);

const _session = UserSession(
  userId: 'management-1',
  username: 'manager',
  displayName: 'Management',
  role: AppRole.management,
  rawRole: 'Management',
  accessToken: 'management-token',
  permissions: ['renewal.manage'],
);
