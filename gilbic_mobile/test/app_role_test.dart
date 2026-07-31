import 'package:flutter_test/flutter_test.dart';
import 'package:gilbic_mobile/src/core/auth/app_role.dart';

void main() {
  test('parses supported Gilbic roles', () {
    expect(AppRole.fromValue('Client'), AppRole.client);
    expect(AppRole.fromValue('collector'), AppRole.collector);
    expect(AppRole.fromValue(' EMPLOYEE '), AppRole.employee);
    expect(AppRole.fromValue('Management'), AppRole.management);
  });

  test('rejects unknown roles', () {
    expect(AppRole.fromValue('administrator'), isNull);
  });
}
