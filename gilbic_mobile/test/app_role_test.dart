import 'package:flutter_test/flutter_test.dart';
import 'package:gilbic_mobile/src/core/auth/app_role.dart';

void main() {
  test('parses only canonical server roles', () {
    expect(AppRole.fromValue('Client'), AppRole.client);
    expect(AppRole.fromValue('collector'), AppRole.collector);
    expect(AppRole.fromValue('Employee'), AppRole.employee);
    expect(AppRole.fromValue('Management'), AppRole.management);
  });

  test('rejects aliases and unknown roles', () {
    expect(AppRole.fromValue('Office Staff'), isNull);
    expect(AppRole.fromValue('encoder'), isNull);
    expect(AppRole.fromValue('Manager'), isNull);
    expect(AppRole.fromValue('Supervisor'), isNull);
    expect(AppRole.fromValue('system_admin'), isNull);
    expect(AppRole.fromValue('temporary guest'), isNull);
  });
}
