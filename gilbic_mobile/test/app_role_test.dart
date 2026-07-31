import 'package:flutter_test/flutter_test.dart';
import 'package:gilbic_mobile/src/core/auth/app_role.dart';

void main() {
  test('parses supported Gilbic and SPINA roles', () {
    expect(AppRole.fromValue('Client'), AppRole.client);
    expect(AppRole.fromValue('collector'), AppRole.collector);
    expect(AppRole.fromValue('Office Staff'), AppRole.employee);
    expect(AppRole.fromValue('encoder'), AppRole.employee);
    expect(AppRole.fromValue('Manager'), AppRole.management);
    expect(AppRole.fromValue('Supervisor'), AppRole.management);
    expect(AppRole.fromValue('system_admin'), AppRole.management);
  });

  test('rejects unknown roles', () {
    expect(AppRole.fromValue('temporary guest'), isNull);
  });
}
