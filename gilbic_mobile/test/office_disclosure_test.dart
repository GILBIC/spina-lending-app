import 'dart:convert';
import 'package:flutter_test/flutter_test.dart';
import 'package:gilbic_mobile/src/core/auth/app_role.dart';
import 'package:gilbic_mobile/src/core/network/spina_api.dart';
import 'package:gilbic_mobile/src/core/office/office_repository.dart';
import 'package:http/testing.dart';
import 'helpers/office_disclosure_fixtures.dart';
import 'office_lifecycle_test.dart' as fixture;

void main() {
  test(
    'malformed saved packet disclosure fails during protected read',
    () async {
      final returned = fixture.loan();
      returned['packet']['tax_disclosure'] = {
        'calculation_id': disclosureId,
        'review_digest': disclosureDigest,
        'financial_snapshot': {'components': {}},
      };
      final repository = OfficeRepository(
        client: MockClient(
          (_) async => fixture.json({
            'loans': [returned],
            'decisions': [],
          }),
        ),
      );
      await expectLater(
        repository.firstLoans(fixture.identity(), fixture.application()),
        throwsA(isA<SpinaApiException>()),
      );
    },
  );

  test(
    'saved disclosure read binds application/CIF and strips nonpublic fields',
    () async {
      final repository = OfficeRepository(
        client: MockClient((request) async {
          expect(
            request.url.path.endsWith('/disclosure-calculations/$disclosureId'),
            isTrue,
          );
          expect(request.url.queryParameters, {
            'application_version_id': fixture.versionId,
          });
          expect(request.headers['X-Device-Id'], 'device');
          return fixture.json(
            savedDisclosure(fixture.versionId, fixture.cifId),
          );
        }),
      );
      final selected = await repository.loadDisclosure(
        fixture.identity(role: AppRole.management),
        fixture.application(),
        disclosureId,
      );
      expect(selected['approval_ready'], isTrue);
      expect(selected['review_digest'], disclosureDigest);
      expect(jsonEncode(selected), isNot(contains('PRIVATE')));
      expect(jsonEncode(selected), contains('990.01'));
    },
  );

  test(
    'wrong source, malformed breakdown and contradictory readiness fail closed',
    () async {
      for (final change in <void Function(OfficeRecord)>[
        (row) => row['id'] = fixture.loanId,
        (row) => row['application_version_id'] = fixture.loanId,
        (row) => row['cif_version_id'] = fixture.loanId,
        (row) => row['review_digest'] = 'invalid',
        (row) => row['blockers'] = ['blocked'],
        (row) => (row['financial_snapshot']['components'] as Map)['principal'] =
            1000.01,
        (row) =>
            (row['financial_snapshot']['disclosure_values']
                    as Map)['amount_financed'] =
                null,
      ]) {
        final payload = savedDisclosure(fixture.versionId, fixture.cifId);
        change(payload);
        final repository = OfficeRepository(
          client: MockClient((_) async => fixture.json(payload)),
        );
        await expectLater(
          repository.loadDisclosure(
            fixture.identity(role: AppRole.management),
            fixture.application(),
            disclosureId,
          ),
          throwsA(isA<SpinaApiException>()),
        );
      }
    },
  );

  test(
    'approval requires ready source and response binds the selected ID and digest',
    () async {
      for (final wrongField in [null, 'calculation_id', 'review_digest']) {
        final selected = savedDisclosure(fixture.versionId, fixture.cifId);
        final returned = fixture.loan();
        final packet = returned['packet'] as Map;
        packet['application'] = {
          'application_id': fixture.applicationId,
          'id': fixture.versionId,
          'version_number': 1,
        };
        packet['cif_version_id'] = fixture.cifId;
        packet['template'] = {'version': 'T1'};
        packet['tax_disclosure'] = {
          'calculation_id': disclosureId,
          'review_digest': disclosureDigest,
          'financial_snapshot': selected['financial_snapshot'],
        };
        if (wrongField != null) {
          packet['tax_disclosure'][wrongField] = wrongField == 'calculation_id'
              ? fixture.loanId
              : fixture.hash;
        }
        var writes = 0;
        final repository = OfficeRepository(
          client: MockClient((request) async {
            writes++;
            final body = jsonDecode(request.body);
            expect(body['disclosure_calculation_id'], disclosureId);
            expect(body['expected_disclosure_digest'], disclosureDigest);
            expect(body.containsKey('financial_snapshot'), isFalse);
            return fixture.json(returned);
          }),
        );
        final result = repository.approveLoan(
          fixture.identity(role: AppRole.management),
          fixture.application(),
          {},
          'T1',
          fixture.authorizationId,
          disclosure: selected,
        );
        if (wrongField == null) {
          expect((await result)['loan_id'], fixture.loanId);
        } else {
          await expectLater(result, throwsA(isA<SpinaApiException>()));
        }
        expect(writes, 1);
        await expectLater(
          repository.approveLoan(
            fixture.identity(role: AppRole.management),
            fixture.application(),
            {},
            'T1',
            fixture.authorizationId,
            disclosure: {...selected, 'approval_ready': false},
          ),
          throwsA(isA<SpinaApiException>()),
        );
        expect(writes, 1);
      }
    },
  );
}
