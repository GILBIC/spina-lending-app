import 'dart:async';
import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gilbic_mobile/src/core/auth/app_role.dart';
import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/device/device_identity.dart';
import 'package:gilbic_mobile/src/core/collector/collector_residence_visit_repository.dart';
import 'package:gilbic_mobile/src/core/network/spina_api.dart';
import 'package:gilbic_mobile/src/core/network/staff_operations_client.dart';
import 'package:gilbic_mobile/src/features/collector/collector_residence_visit_page.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

const collector = UserSession(
  userId: 'collector',
  username: 'collector',
  displayName: 'Collector',
  role: AppRole.collector,
  rawRole: 'Collector',
  accessToken: 'synthetic-token',
  permissions: ['client_onboarding.visit.record'],
);
const applicant = '00000000-0000-4000-8000-000000000123';
Map<String, Object?> visitCase({
  String status = 'pending',
  String reference = 'APP-123',
  String? note,
  String? evidence,
}) => {
  'applicant_id': applicant,
  'application_reference': reference,
  'status': 'under_verification',
  'full_name': 'Synthetic Applicant',
  'phone_number': '09123456789',
  'present_address': 'Synthetic address',
  'collector_visit': {
    'status': status,
    'note': note,
    'evidence_reference': evidence,
  },
};
DeviceIdentityProvider device() => DeviceIdentityProvider(
  store: MemoryDeviceIdentityStore()..value = 'installation',
  appVersionResolver: () async => 'test',
);
CollectorResidenceVisitRepository repository(
  Future<http.Response> Function(http.Request) handler,
) => CollectorResidenceVisitRepository(
  StaffOperationsClient(
    deviceIdentityProvider: device(),
    client: MockClient(handler),
  ),
);

void main() {
  test(
    'case lookup rejects a response for a different intake reference',
    () async {
      final repo = repository(
        (_) async =>
            http.Response(jsonEncode(visitCase(reference: 'APP-OTHER')), 200),
      );
      await expectLater(
        repo.load(collector, 'APP-123'),
        throwsA(isA<SpinaApiException>()),
      );
    },
  );
  test(
    'Collector permission is required before sending private case requests',
    () async {
      var requests = 0;
      final repo = repository((_) async {
        requests++;
        return http.Response('{}', 200);
      });
      const denied = UserSession(
        userId: 'employee',
        username: 'employee',
        displayName: 'Employee',
        role: AppRole.employee,
        rawRole: 'Employee',
        accessToken: 'token',
        permissions: ['client_onboarding.visit.record'],
      );
      await expectLater(
        repo.load(denied, 'APP-123'),
        throwsA(isA<SpinaApiException>()),
      );
      expect(requests, 0);
    },
  );
  testWidgets(
    'recording a visit submits once, then shows the saved outcome without pending entry controls',
    (tester) async {
      await tester.binding.setSurfaceSize(const Size(1000, 1500));
      addTearDown(() => tester.binding.setSurfaceSize(null));
      final posts = <http.Request>[];
      final pending = Completer<http.Response>();
      final repo = repository((request) async {
        expect(request.headers['authorization'], 'Bearer synthetic-token');
        expect(request.headers['x-device-id'], 'installation');
        if (request.method == 'POST') {
          posts.add(request);
          return pending.future;
        }
        return http.Response(
          jsonEncode(
            visitCase(
              status: posts.isEmpty ? 'pending' : 'passed',
              note: posts.isEmpty ? null : 'Residence checked',
            ),
          ),
          200,
        );
      });
      await tester.pumpWidget(
        MaterialApp(
          home: CollectorResidenceVisitPage(
            session: collector,
            deviceIdentityProvider: device(),
            repository: repo,
          ),
        ),
      );
      await tester.enterText(
        find.byKey(const Key('visit-reference')),
        'APP-123',
      );
      await tester.tap(find.byKey(const Key('visit-load')));
      await tester.pumpAndSettle();
      expect(find.text('Synthetic Applicant'), findsOneWidget);
      await tester.tap(find.byKey(const Key('visit-result')));
      await tester.pumpAndSettle();
      await tester.tap(find.text('Passed').last);
      await tester.pumpAndSettle();
      await tester.enterText(
        find.byKey(const Key('visit-note')),
        'Residence checked',
      );
      await tester.tap(find.byKey(const Key('visit-submit')));
      await tester.pump();
      expect(
        tester
            .widget<FilledButton>(find.byKey(const Key('visit-submit')))
            .onPressed,
        isNull,
      );
      expect(posts.length, 1);
      expect(
        posts.single.url.path,
        '/api/v1/collector/onboarding/applicants/$applicant/visit',
      );
      expect(jsonDecode(posts.single.body), {
        'result': 'passed',
        'note': 'Residence checked',
        'evidence_reference': null,
      });
      pending.complete(http.Response('{"status":"under_verification"}', 200));
      await tester.pumpAndSettle();
      expect(find.byKey(const Key('visit-submit')), findsNothing);
      expect(find.text('Recorded visit: Passed'), findsOneWidget);
    },
  );
  testWidgets(
    'an uncertain visit is locked until the authoritative case is reloaded',
    (tester) async {
      await tester.binding.setSurfaceSize(const Size(1000, 1500));
      addTearDown(() => tester.binding.setSurfaceSize(null));
      var posts = 0;
      final repo = repository((request) async {
        if (request.method == 'POST') {
          posts++;
          throw http.ClientException('interrupted');
        }
        return http.Response(
          jsonEncode(visitCase(status: posts == 0 ? 'pending' : 'passed')),
          200,
        );
      });
      await tester.pumpWidget(
        MaterialApp(
          home: CollectorResidenceVisitPage(
            session: collector,
            deviceIdentityProvider: device(),
            repository: repo,
          ),
        ),
      );
      await tester.enterText(
        find.byKey(const Key('visit-reference')),
        'APP-123',
      );
      await tester.tap(find.byKey(const Key('visit-load')));
      await tester.pumpAndSettle();
      await tester.tap(find.byKey(const Key('visit-result')));
      await tester.pumpAndSettle();
      await tester.tap(find.text('Passed').last);
      await tester.pumpAndSettle();
      await tester.tap(find.byKey(const Key('visit-submit')));
      await tester.pumpAndSettle();
      expect(posts, 1);
      expect(
        tester
            .widget<FilledButton>(find.byKey(const Key('visit-submit')))
            .onPressed,
        isNull,
      );
      await tester.tap(find.byKey(const Key('visit-reload')));
      await tester.pumpAndSettle();
      expect(posts, 1);
      expect(find.byKey(const Key('visit-submit')), findsNothing);
      expect(find.text('Recorded visit: Passed'), findsOneWidget);
    },
  );
  for (final status in ['pending', 'failed', 'passed']) {
    testWidgets(
      'same applicant with mismatched saved $status result stays uncertain',
      (tester) async {
        await tester.binding.setSurfaceSize(const Size(1000, 1500));
        addTearDown(() => tester.binding.setSurfaceSize(null));
        var posts = 0;
        final repo = repository((request) async {
          if (request.method == 'POST') {
            posts++;
            return http.Response('{"status":"under_verification"}', 200);
          }
          return http.Response(
            jsonEncode(
              visitCase(
                status: posts == 0 ? 'pending' : status,
                note: posts == 0 ? null : 'Different visit evidence',
              ),
            ),
            200,
          );
        });
        await tester.pumpWidget(
          MaterialApp(
            home: CollectorResidenceVisitPage(
              session: collector,
              deviceIdentityProvider: device(),
              repository: repo,
            ),
          ),
        );
        await tester.enterText(
          find.byKey(const Key('visit-reference')),
          'APP-123',
        );
        await tester.tap(find.byKey(const Key('visit-load')));
        await tester.pumpAndSettle();
        await tester.tap(find.byKey(const Key('visit-result')));
        await tester.pumpAndSettle();
        await tester.tap(find.text('Passed').last);
        await tester.pumpAndSettle();
        await tester.enterText(
          find.byKey(const Key('visit-note')),
          'Residence checked',
        );
        await tester.tap(find.byKey(const Key('visit-submit')));
        await tester.pumpAndSettle();
        expect(posts, 1);
        expect(
          find.text('Residence visit recorded. It does not approve a loan.'),
          findsNothing,
        );
        expect(find.byKey(const Key('visit-reload')), findsOneWidget);
        expect(
          tester
              .widget<FilledButton>(find.byKey(const Key('visit-submit')))
              .onPressed,
          isNull,
        );
      },
    );
  }
}
