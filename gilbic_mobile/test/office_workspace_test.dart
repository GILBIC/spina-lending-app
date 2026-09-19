import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gilbic_mobile/src/core/auth/app_role.dart';
import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/device/device_identity.dart';
import 'package:gilbic_mobile/src/core/office/office_repository.dart';
import 'package:gilbic_mobile/src/features/office/office_workspace_page.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

UserSession session({
  List<String> permissions = const ['client_onboarding.requirement.review'],
}) => UserSession(
  userId: 'employee',
  username: 'employee',
  displayName: 'Employee',
  role: AppRole.employee,
  rawRole: 'employee',
  accessToken: 'token',
  permissions: permissions,
);
DeviceIdentityProvider device() => DeviceIdentityProvider(
  store: MemoryDeviceIdentityStore(),
  platformResolver: () => 'android',
  appVersionResolver: () async => 'test',
);

void main() {
  testWidgets('denied Employee cannot start office reads or writes', (
    tester,
  ) async {
    var calls = 0;
    await tester.pumpWidget(
      MaterialApp(
        home: OfficeWorkspacePage(
          session: session(permissions: []),
          deviceIdentityProvider: device(),
          repository: OfficeRepository(
            client: MockClient((request) async {
              calls++;
              return http.Response('{}', 200);
            }),
          ),
        ),
      ),
    );
    await tester.pumpAndSettle();
    expect(find.textContaining('Authorized office'), findsOneWidget);
    expect(find.text('New office intake'), findsNothing);
    expect(calls, 0);
  });
  testWidgets(
    'office access is checked again after launcher permission changes',
    (tester) async {
      var calls = 0;
      final permissions = ['client_onboarding.requirement.review'];
      await tester.pumpWidget(
        MaterialApp(
          home: OfficeWorkspacePage(
            session: session(permissions: permissions),
            deviceIdentityProvider: device(),
            repository: OfficeRepository(
              client: MockClient((request) async {
                calls++;
                return http.Response('{}', 200);
              }),
            ),
          ),
        ),
      );
      await tester.pumpAndSettle();
      permissions.clear();
      await tester.tap(find.text('New office intake'));
      await tester.pumpAndSettle();
      expect(find.textContaining('Authorized office'), findsOneWidget);
      expect(calls, 0);
    },
  );
  testWidgets(
    'Employee opens authoritative CIF and never sees Management activation',
    (tester) async {
      const client = '11111111-1111-4111-8111-111111111111';
      const version = '22222222-2222-4222-8222-222222222222';
      await tester.pumpWidget(
        MaterialApp(
          home: OfficeWorkspacePage(
            session: session(),
            deviceIdentityProvider: device(),
            repository: OfficeRepository(
              client: MockClient((request) async {
                if (request.url.path.endsWith('/cif-client')) {
                  return http.Response(
                    jsonEncode({
                      'client_id': client,
                      'application_reference': 'INT-1',
                    }),
                    200,
                  );
                }
                if (request.url.path.endsWith('/review-summary')) {
                  return http.Response(
                    jsonEncode({
                      'client_id': client,
                      'cif_version_id': version,
                      'version_number': 1,
                      'status': 'draft',
                      'liveness_status': 'not_recorded',
                      'review_scope': 'cif_information_only',
                      'full_name': 'Named Borrower',
                      'phone_number': '09123456789',
                      'email': null,
                      'present_address': 'Address',
                      'can_correct_information': true,
                    }),
                    200,
                  );
                }
                return http.Response('{"detail":"No context"}', 409);
              }),
            ),
          ),
        ),
      );
      await tester.pumpAndSettle();
      await tester.enterText(
        find.byKey(const Key('office-intake-reference')),
        'INT-1',
      );
      await tester.tap(find.text('CIF review'));
      await tester.pumpAndSettle();
      expect(find.text('Named Borrower'), findsOneWidget);
      expect(find.text('Activate verified CIF'), findsNothing);
      expect(find.text('Correct information'), findsOneWidget);
    },
  );
  testWidgets(
    'denial during capture clears private CIF and workspace when returning',
    (tester) async {
      const client = '11111111-1111-4111-8111-111111111111';
      const version = '22222222-2222-4222-8222-222222222222';
      await tester.pumpWidget(
        MaterialApp(
          home: OfficeWorkspacePage(
            session: session(),
            deviceIdentityProvider: device(),
            repository: OfficeRepository(
              client: MockClient((request) async {
                if (request.url.path.endsWith('/cif-client')) {
                  return http.Response(
                    jsonEncode({
                      'client_id': client,
                      'application_reference': 'INT-1',
                    }),
                    200,
                  );
                }
                if (request.url.path.endsWith('/review-summary')) {
                  return http.Response(
                    jsonEncode({
                      'client_id': client,
                      'cif_version_id': version,
                      'version_number': 1,
                      'status': 'draft',
                      'review_scope': 'cif_information_only',
                      'full_name': 'Private Borrower',
                      'phone_number': '09123456789',
                      'email': null,
                      'present_address': 'Private Address',
                      'can_correct_information': true,
                    }),
                    200,
                  );
                }
                return http.Response('{"detail":"Device revoked"}', 403);
              }),
            ),
          ),
        ),
      );
      await tester.pumpAndSettle();
      await tester.enterText(
        find.byKey(const Key('office-intake-reference')),
        'INT-1',
      );
      await tester.tap(find.text('CIF review'));
      await tester.pumpAndSettle();
      await tester.scrollUntilVisible(
        find.text('Capture signed CIF review'),
        250,
      );
      await tester.tap(find.text('Capture signed CIF review'));
      await tester.pumpAndSettle();
      expect(find.textContaining('Office access is no longer'), findsOneWidget);
      await tester.pageBack();
      await tester.pumpAndSettle();
      expect(find.text('Private Borrower'), findsNothing);
      await tester.pageBack();
      await tester.pumpAndSettle();
      expect(find.byKey(const Key('office-intake-reference')), findsNothing);
      expect(find.textContaining('Office access is no longer'), findsWidgets);
    },
  );
}
