import 'package:flutter_test/flutter_test.dart';
import 'package:gilbic_mobile/src/core/auth/app_role.dart';
import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/office/office_repository.dart';
import 'package:gilbic_mobile/src/core/network/staff_operations_client.dart';
import 'package:gilbic_mobile/src/core/network/spina_api.dart';

void main() {
  test(
    'verified Employee membership opens assigned office work without granting Management review',
    () {
      const combined = UserSession(
        userId: 'a',
        username: 'a',
        displayName: 'A',
        role: AppRole.collector,
        rawRole: 'Collector',
        accessToken: 'token',
        roles: ['Collector', 'Employee'],
        permissions: [
          'client_onboarding.requirement.review',
          'lending.first_loan.release',
          'lending.first_loan.approve',
          'area.manage',
        ],
      );
      final office = OfficeIdentity(combined, 'device');
      expect(office.allowed, isTrue);
      expect(office.releaser, isTrue);
      expect(office.manager, isFalse);
      requireStaffPermission(combined, ['area.manage']);
      expect(
        () => requireStaffPermission(combined, [
          'area.manage',
        ], managementOnly: true),
        throwsA(isA<SpinaApiException>()),
      );
    },
  );
  const collector = UserSession(
    userId: 'a',
    username: 'a',
    displayName: 'A',
    role: AppRole.collector,
    rawRole: 'Collector',
    accessToken: 'token',
    roles: ['Collector', 'Employee', 'employee_manager'],
    permissions: ['client_onboarding.requirement.review'],
  );
  test(
    'combined membership survives secure-session serialization without changing primary role',
    () {
      final restored = UserSession.fromJson(collector.toJson())!;
      expect(restored.role, AppRole.collector);
      expect(restored.hasRole(AppRole.employee), isTrue);
      expect(restored.hasRole(AppRole.management), isFalse);
      expect(restored.workspaceRoles, [AppRole.collector, AppRole.employee]);
    },
  );
  test('permissions do not manufacture an office or management membership', () {
    const session = UserSession(
      userId: 'b',
      username: 'b',
      displayName: 'B',
      role: AppRole.collector,
      rawRole: 'Collector',
      accessToken: 'token',
      permissions: [
        'client_onboarding.requirement.review',
        'management.dashboard.view',
      ],
    );
    expect(session.hasRole(AppRole.employee), isFalse);
    expect(session.hasRole(AppRole.management), isFalse);
  });
}
