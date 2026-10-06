import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gilbic_mobile/src/core/auth/app_role.dart';
import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/office/office_repository.dart';
import 'package:http/http.dart' as http;

const clientId = '11111111-1111-4111-8111-111111111111';
const cifId = '22222222-2222-4222-8222-222222222222';
const applicantId = '33333333-3333-4333-8333-333333333333';
const staff = UserSession(
  userId: 'employee',
  username: 'employee',
  displayName: 'Employee',
  role: AppRole.employee,
  rawRole: 'employee',
  accessToken: 'token',
  permissions: ['client_onboarding.requirement.review'],
);
OfficeIdentity actor() => OfficeIdentity(staff, 'device');
final cif = <String, dynamic>{
  'client_id': clientId,
  'cif_version_id': cifId,
  'version_number': 1,
  'status': 'draft',
  'liveness_status': 'not_recorded',
  'review_scope': 'cif_information_only',
  'full_name': 'Sample Applicant',
  'phone_number': '09123456789',
  'present_address': 'Sample address',
  'email': null,
  'can_correct_information': true,
};
final intake = <String, dynamic>{
  'applicant_id': applicantId,
  'application_reference': 'INT-1',
  'full_name': 'Sample Applicant',
  'phone_number': '09123456789',
  'status': 'eligible_for_cif',
  'requirements': {
    for (final name in [
      'national_id',
      'tin_id',
      'meralco_bill',
      'collector_visit',
    ])
      name: {'status': 'passed'},
  },
};
http.Response response(Object value, [int status = 200]) =>
    http.Response(jsonEncode(value), status);
Future<void> reveal(WidgetTester tester, String text) async {
  await tester.scrollUntilVisible(
    find.text(text),
    180,
    scrollable: find.byType(Scrollable).first,
  );
  await tester.pumpAndSettle();
}
