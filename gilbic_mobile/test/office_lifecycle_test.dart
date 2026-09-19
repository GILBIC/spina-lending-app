import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gilbic_mobile/src/core/auth/app_role.dart';
import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/network/spina_api.dart';
import 'package:gilbic_mobile/src/core/office/office_repository.dart';
import 'package:gilbic_mobile/src/features/office/office_application_page.dart';
import 'package:gilbic_mobile/src/features/office/office_first_loan_page.dart';
import 'package:gilbic_mobile/src/features/office/office_intake_page.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

const clientId = '11111111-1111-4111-8111-111111111111';
const cifId = '22222222-2222-4222-8222-222222222222';
const applicationId = '33333333-3333-4333-8333-333333333333';
const versionId = '44444444-4444-4444-8444-444444444444';
const loanId = '55555555-5555-4555-8555-555555555555';
const packetId = '66666666-6666-4666-8666-666666666666';
const authorizationId = '77777777-7777-4777-8777-777777777777';
final hash = List.filled(64, 'a').join();
OfficeIdentity identity({AppRole role = AppRole.employee}) => OfficeIdentity(
  UserSession(
    userId: 'staff',
    username: 'staff',
    displayName: 'Staff',
    role: role,
    rawRole: role.name,
    accessToken: 'token',
    permissions: const [
      'client_onboarding.requirement.review',
      'lending.first_loan.approve',
      'lending.first_loan.release',
      'client.credential.manage',
    ],
  ),
  'device',
);
OfficeRecord application({OfficeRecord? information}) => {
  'client_id': clientId,
  'cif_version_id': cifId,
  'application_id': applicationId,
  'application_version_id': versionId,
  'application_reference': 'APP-1',
  'version_number': 1,
  'review_scope': 'loan_application_information_only',
  'information':
      information ??
      {
        'request': {'requested_amount': '1000.00'},
        'repayment': {},
      },
  'missing_fields': [],
};
OfficeRecord loan({bool released = false}) => {
  'client_id': clientId,
  'loan_id': loanId,
  'packet_id': packetId,
  'packet_hash': hash,
  'loan_number': 'LOAN-1',
  'status': released ? 'released' : 'approved_pending_release',
  'packet': {
    'client_id': clientId,
    'loan_id': loanId,
    'packet_id': packetId,
    'application': {'application_id': applicationId},
    'borrower': {'full_name': 'Named Borrower'},
    'net_cash': '1000.00',
    'terms': {'principal': '1000.00', 'product_code': 'regular'},
    'schedule': [
      {
        'installment_number': 1,
        'due_date': '2026-10-01',
        'contractual_amount': '1100.00',
        'principal_component': '1000.00',
        'interest_component': '100.00',
      },
    ],
  },
  'document': {'id': packetId, 'content_sha256': hash},
  'authorization': {'id': authorizationId, 'revoked': false},
  'evidence': released
      ? {}
      : {
          'borrower_contract_signed': {
            'evidence_reference': 'office-evidence:$cifId',
          },
          'borrower_cash_received': {
            'evidence_reference': 'office-evidence:$versionId',
          },
        },
  'release': released
      ? {
          'released_at': '2026-09-19T12:00:00Z',
          'receipt': {
            'receipt_reference': 'RELEASE-1',
            'actual_cash_received': '1000.00',
            'loan_id': loanId,
            'client_id': clientId,
            'packet_id': packetId,
            'packet_hash': hash,
            'releasing_staff_id': 'staff',
            'contract_evidence_reference': 'office-evidence:$cifId',
            'cash_evidence_reference': 'office-evidence:$versionId',
          },
        }
      : null,
  'credential_intent': released ? {'status': 'completed'} : null,
};
http.Response json(Object? value, [int status = 200]) => http.Response(
  jsonEncode(value),
  status,
  headers: {'content-type': 'application/json'},
);
Future<void> reveal(WidgetTester tester, Finder finder) async {
  await tester.scrollUntilVisible(
    finder,
    300,
    scrollable: find.byType(Scrollable).first,
  );
  await tester.pumpAndSettle();
}

void main() {
  testWidgets(
    'Management exact approval remains usable on a phone with large text',
    (tester) async {
      tester.view.physicalSize = const Size(360, 640);
      tester.view.devicePixelRatio = 1;
      addTearDown(tester.view.resetPhysicalSize);
      addTearDown(tester.view.resetDevicePixelRatio);
      var approvals = 0;
      final approved = loan();
      (approved['packet'] as Map)['application'] = {
        'application_id': applicationId,
        'id': versionId,
        'version_number': 1,
      };
      (approved['packet'] as Map)['cif_version_id'] = cifId;
      (approved['packet'] as Map)['template'] = {'version': 'T1'};
      final repository = OfficeRepository(
        client: MockClient((request) async {
          if (request.url.path.endsWith('/review-summary')) {
            return json(application());
          }
          if (request.url.path.endsWith('/context')) {
            return json({
              'server_business_date': '2026-09-19',
              'products': [
                {
                  'id': packetId,
                  'name': 'Regular office loan',
                  'calculation_mode': 'fixed_total',
                },
              ],
              'templates': [
                {
                  'version': 'T1',
                  'content_sha256': hash,
                  'approved_for_execution': true,
                },
              ],
            });
          }
          if (request.url.path.contains('/by-application/')) {
            return json({
              'loans': approvals == 0 ? [] : [approved],
              'decisions': [],
            });
          }
          expect(request.url.path.endsWith('/approve'), isTrue);
          approvals++;
          final body = jsonDecode(request.body);
          expect(body['application_version_id'], versionId);
          expect(body['template_version'], 'T1');
          expect(officeUuid(body['request_id']), isTrue);
          expect(body['terms']['principal'], '1000.01');
          expect(body['terms']['contractual_interest'], '100.00');
          expect(body['terms']['interest_rate_percent'], '10.0000');
          expect(body['terms']['installment_amount'], '1100.01');
          expect(body['terms']['installment_count'], 1);
          return json(approved);
        }),
      );
      await tester.pumpWidget(
        MaterialApp(
          builder: (context, child) => MediaQuery(
            data: MediaQuery.of(
              context,
            ).copyWith(textScaler: const TextScaler.linear(1.3)),
            child: child!,
          ),
          home: OfficeFirstLoanPage(
            actor: identity(role: AppRole.management),
            repository: repository,
            clientId: clientId,
            applicationReference: 'APP-1',
          ),
        ),
      );
      await tester.pumpAndSettle();
      final product = find.text('Approved product');
      await reveal(tester, product);
      await tester.tap(product);
      await tester.pumpAndSettle();
      await tester.tap(find.text('Regular office loan').last);
      await tester.pumpAndSettle();
      for (final entry in {
        'principal': '1000.01',
        'interest_rate': '10.0000',
        'interest': '100.00',
        'installment': '1100.01',
        'count': '1',
        'first_date': '2026-10-01',
        'pricing_reference': 'pricing:approved',
        'account_email': 'borrower@example.test',
      }.entries) {
        final field = find.byKey(Key('office-${entry.key}'));
        await reveal(tester, field);
        await tester.enterText(field, entry.value);
      }
      final template = find.text('Controlled contractual template');
      await reveal(tester, template);
      await tester.tap(template);
      await tester.pumpAndSettle();
      await tester.tap(find.text('T1').last);
      await tester.pumpAndSettle();
      final approve = find.text('Approve exact terms');
      await reveal(tester, approve);
      await tester.tap(approve);
      await tester.pumpAndSettle();
      expect(approvals, 1);
      expect(tester.takeException(), isNull);
      expect(find.text('Approve exact terms'), findsNothing);
    },
  );
  test(
    'release response must bind selected loan packet authorization evidence and exact cash',
    () async {
      for (final change in <void Function(OfficeRecord)>[
        (record) {
          record['loan_id'] = versionId;
          stringMap(record['packet']);
          (record['packet'] as Map)['loan_id'] = versionId;
        },
        (record) => record['packet_hash'] = List.filled(64, 'b').join(),
        (record) => (record['authorization'] as Map)['id'] = versionId,
        (record) =>
            ((record['release'] as Map)['receipt']
                    as Map)['actual_cash_received'] =
                '999.99',
        (record) =>
            ((record['release'] as Map)['receipt']
                    as Map)['contract_evidence_reference'] =
                'office-evidence:$packetId',
      ]) {
        final returned = loan(released: true);
        change(returned);
        final repository = OfficeRepository(
          client: MockClient((_) async => json(returned)),
        );
        await expectLater(
          repository.releaseLoan(
            identity(),
            loan(),
            application(),
            contractEvidence: 'office-evidence:$cifId',
            cashEvidence: 'office-evidence:$versionId',
            cashAmount: '1000.00',
            requestId: authorizationId,
          ),
          throwsA(isA<SpinaApiException>()),
        );
      }
    },
  );
  test(
    'approval response rejects a different application version despite same application',
    () async {
      final returned = loan();
      (returned['packet'] as Map)['application'] = {
        'application_id': applicationId,
        'id': loanId,
        'version_number': 1,
      };
      (returned['packet'] as Map)['cif_version_id'] = cifId;
      (returned['packet'] as Map)['template'] = {'version': 'T1'};
      final repository = OfficeRepository(
        client: MockClient((_) async => json(returned)),
      );
      await expectLater(
        repository.approveLoan(
          identity(role: AppRole.management),
          application(),
          {},
          'T1',
          authorizationId,
        ),
        throwsA(isA<SpinaApiException>()),
      );
    },
  );
  testWidgets(
    'failed intake refresh removes stale facts and blocks new writes',
    (tester) async {
      var reads = 0;
      final repository = OfficeRepository(
        client: MockClient((request) async {
          reads++;
          if (reads > 1) return json({'detail': 'Unavailable'}, 500);
          return json({
            'application_reference': 'INT-1',
            'applicant_id': applicationId,
            'status': 'eligible_for_cif',
            'full_name': 'Private Borrower',
            'requirements': {
              for (final name in [
                'national_id',
                'tin_id',
                'meralco_bill',
                'collector_visit',
              ])
                name: {'status': 'passed'},
            },
          });
        }),
      );
      await tester.pumpWidget(
        MaterialApp(
          home: OfficeIntakePage(
            actor: identity(),
            repository: repository,
            reference: 'INT-1',
          ),
        ),
      );
      await tester.pumpAndSettle();
      expect(find.text('Private Borrower'), findsOneWidget);
      await tester.tap(find.byTooltip('Reload saved record'));
      await tester.pumpAndSettle();
      expect(find.text('Private Borrower'), findsNothing);
      await reveal(tester, find.text('Record office intake'));
      expect(
        tester
            .widget<FilledButton>(
              find.ancestor(
                of: find.text('Record office intake'),
                matching: find.byType(FilledButton),
              ),
            )
            .onPressed,
        isNull,
      );
      expect(reads, 2);
    },
  );
  test(
    'Employee cannot approve or issue a packet despite assigned approval permission',
    () async {
      var calls = 0;
      final repository = OfficeRepository(
        client: MockClient((_) async {
          calls++;
          return json({});
        }),
      );
      await expectLater(
        repository.approveLoan(
          identity(),
          application(),
          {},
          'template',
          versionId,
        ),
        throwsA(isA<SpinaApiException>()),
      );
      await expectLater(
        repository.packetAction(identity(), loan(), 'documents', {
          'packet_hash': hash,
        }),
        throwsA(isA<SpinaApiException>()),
      );
      expect(calls, 0);
    },
  );
  test(
    'successor CIF preserves exact original information and does not implicitly confirm it',
    () async {
      final original = {
        'client_id': clientId,
        'cif_version_id': cifId,
        'version_number': 1,
        'review_scope': 'cif_information_only',
        'full_name': 'Old Name',
        'phone_number': '09123456789',
        'email': null,
        'present_address': 'Old address',
        'identity_information': {
          'birth_date': '1990-01-01',
          'birth_place': null,
          'civil_status': null,
          'citizenship': null,
        },
      };
      final corrected = {
        ...cifInformation(original),
        'full_name': 'Correct Name',
      };
      final repository = OfficeRepository(
        client: MockClient((request) async {
          expect(request.url.path.endsWith('/cif/review-cycles'), isTrue);
          final body = jsonDecode(request.body);
          expect(body['expected_information'], cifInformation(original));
          expect(body['reason'], 'Correct spelling');
          return json({
            ...original,
            ...corrected,
            'cif_version_id': versionId,
            'version_number': 2,
          });
        }),
      );
      final result = await repository.correctCif(
        identity(),
        original,
        corrected,
        'Correct spelling',
        successor: true,
      );
      expect(result['version_number'], 2);
    },
  );
  test('exact review refuses mismatched linked application snapshot', () async {
    final repository = OfficeRepository(
      client: MockClient(
        (_) async => json({
          'client_id': clientId,
          'cif_version_id': cifId,
          'application_id': applicationId,
          'application_version_id': versionId,
          'purpose': 'application_review',
          'snapshot_sha256': hash,
          'review_snapshot': {
            'client_id': clientId,
            'cif_version_id': cifId,
            'application_id': applicationId,
            'application_version_id': loanId,
            'information': {},
            'cif_information': {},
          },
        }),
      ),
    );
    await expectLater(
      repository.reviewContext(identity(), clientId, {
        'purpose': 'application_review',
        'cif_version_id': cifId,
        'application_id': applicationId,
        'application_version_id': versionId,
      }),
      throwsA(isA<SpinaApiException>()),
    );
  });
  testWidgets(
    'uncertain intake is not resubmitted and preserves an explicit reconciliation path',
    (tester) async {
      var writes = 0;
      final repository = OfficeRepository(
        client: MockClient((request) async {
          if (request.method == 'POST') {
            writes++;
            return json({'detail': 'Service temporarily unavailable'}, 503);
          }
          return json({'detail': 'Unavailable'}, 404);
        }),
      );
      await tester.pumpWidget(
        MaterialApp(
          home: OfficeIntakePage(actor: identity(), repository: repository),
        ),
      );
      await tester.pumpAndSettle();
      for (final entry in {
        'full_name': 'Named Borrower',
        'phone_number': '09123456789',
        'present_address': 'Test address',
        'national_id_egov_evidence_reference': 'external:national',
        'tin_id_egov_evidence_reference': 'external:tin',
        'meralco_bill_evidence_reference': 'external:bill',
      }.entries) {
        final field = find.byKey(Key('office-${entry.key}'));
        await reveal(tester, field);
        await tester.enterText(field, entry.value);
      }
      final privacy = find.text(
        'The applicant’s required privacy consent has been recorded.',
      );
      await reveal(tester, privacy);
      await tester.tap(privacy);
      await tester.pumpAndSettle();
      final accuracy = find.text(
        'The applicant declared the intake information accurate.',
      );
      await reveal(tester, accuracy);
      await tester.tap(accuracy);
      await tester.pumpAndSettle();
      final submit = find.text('Record office intake');
      await reveal(tester, submit);
      await tester.tap(submit);
      await tester.pumpAndSettle();
      expect(writes, 1);
      expect(
        tester
            .widget<FilledButton>(
              find.ancestor(of: submit, matching: find.byType(FilledButton)),
            )
            .onPressed,
        isNull,
      );
      expect(writes, 1);
      await tester.drag(find.byType(Scrollable).first, const Offset(0, 10000));
      await tester.pumpAndSettle();
      expect(
        find.textContaining('outcome may already be recorded'),
        findsOneWidget,
      );
    },
  );
  testWidgets('new application saves exact money without local approval', (
    tester,
  ) async {
    OfficeRecord? saved;
    var creates = 0;
    final repository = OfficeRepository(
      client: MockClient((request) async {
        if (request.url.path.endsWith('/entry-context')) {
          return json({
            'client_id': clientId,
            'cif_version_id': cifId,
            'cif_version_number': 1,
            'loan_types': [
              {'id': packetId, 'code': 'REG', 'name': 'Regular'},
            ],
          });
        }
        if (request.method == 'POST') {
          creates++;
          expect(request.url.path.endsWith('/drafts'), isTrue);
          final body = jsonDecode(request.body);
          expect(body['information']['request']['requested_amount'], '1000.01');
          expect(body.containsKey('approved'), isFalse);
          saved = application(information: stringMap(body['information']));
          return json(saved, 201);
        }
        return saved == null ? json({'detail': 'Not found'}, 404) : json(saved);
      }),
    );
    await tester.pumpWidget(
      MaterialApp(
        home: OfficeApplicationPage(
          actor: identity(),
          repository: repository,
          clientId: clientId,
          applicationReference: 'APP-1',
        ),
      ),
    );
    await tester.pumpAndSettle();
    await tester.tap(find.text('Create application draft'));
    await tester.pumpAndSettle();
    final amount = find.byKey(const Key('office-request.requested_amount'));
    await reveal(tester, amount);
    await tester.enterText(amount, '1000.01');
    final save = find.text('Save application draft');
    await reveal(tester, save);
    await tester.tap(save);
    await tester.pumpAndSettle();
    expect(creates, 1);
    expect(tester.takeException(), isNull);
    await reveal(tester, find.textContaining('Application information saved'));
    expect(
      find.textContaining('Application information saved'),
      findsOneWidget,
    );
  });
  testWidgets(
    'Employee release binds packet and evidence, masks credentials, and retry never releases again',
    (tester) async {
      var released = false;
      var releaseCount = 0;
      var credentialCount = 0;
      final repository = OfficeRepository(
        client: MockClient((request) async {
          if (request.url.path.endsWith('/review-summary')) {
            return json(application());
          }
          if (request.url.path.endsWith('/context')) {
            return json({
              'server_business_date': '2026-09-19',
              'products': [],
              'templates': [],
            });
          }
          if (request.url.path.contains('/by-application/')) {
            return json({
              'loans': [loan(released: released)],
              'decisions': [],
            });
          }
          if (request.url.path.endsWith('/release')) {
            final body = jsonDecode(request.body);
            expect(body['packet_hash'], hash);
            expect(body['authorization_id'], authorizationId);
            expect(
              body['contract_evidence_reference'],
              'office-evidence:$cifId',
            );
            expect(
              body['cash_evidence_reference'],
              'office-evidence:$versionId',
            );
            expect(body['cash_amount'], '1000.00');
            expect(body['borrower_confirmed'], isTrue);
            released = true;
            releaseCount++;
            return json({
              ...loan(released: true),
              'credentials': {
                'status': 'completed',
                'credentials': {
                  'username': 'borrower',
                  'password': 'one-time-secret',
                },
                'delivery': {'detail': 'Hand to borrower'},
              },
            });
          }
          if (request.url.path.endsWith('/credentials')) {
            credentialCount++;
            return json({
              'status': 'already_completed',
              'detail': 'Account already set up.',
            });
          }
          throw StateError(request.url.path);
        }),
      );
      await tester.pumpWidget(
        MaterialApp(
          home: OfficeFirstLoanPage(
            actor: identity(),
            repository: repository,
            clientId: clientId,
            applicationReference: 'APP-1',
          ),
        ),
      );
      await tester.pumpAndSettle();
      expect(find.text('Authorize exact office release'), findsNothing);
      expect(find.text('Generate locked PDF packet'), findsNothing);
      final cash = find.byKey(const Key('office-cash_amount'));
      await reveal(tester, cash);
      await tester.enterText(cash, '1000.00');
      final confirm = find.text(
        'The named borrower confirmed receiving this exact cash at the office.',
      );
      await reveal(tester, confirm);
      await tester.tap(confirm);
      await tester.pumpAndSettle();
      final release = find.text('Record completed office release');
      await reveal(tester, release);
      await tester.tap(release);
      await tester.pumpAndSettle();
      expect(releaseCount, 1);
      expect(find.text('one-time-secret'), findsNothing);
      final show = find.byTooltip('Show password');
      await reveal(tester, show);
      await tester.tap(show);
      await tester.pumpAndSettle();
      expect(find.text('one-time-secret'), findsOneWidget);
      final retry = find.text('Retry account setup');
      await reveal(tester, retry);
      await tester.tap(retry);
      await tester.pumpAndSettle();
      expect(credentialCount, 1);
      expect(releaseCount, 1);
      expect(find.text('one-time-secret'), findsNothing);
      expect(tester.takeException(), isNull);
    },
  );
}
