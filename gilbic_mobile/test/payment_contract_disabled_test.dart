import 'dart:io';

import 'package:flutter_test/flutter_test.dart';

void main() {
  test('payment repository is not wired into the application shell', () {
    final appSource = File('lib/src/app.dart').readAsStringSync();
    final dashboardSource =
        File('lib/src/features/dashboard/role_dashboard.dart').readAsStringSync();

    expect(appSource, isNot(contains('SpinaPaymentSubmissionRepository')));
    expect(appSource, isNot(contains('PaymentSubmissionRepository')));
    expect(dashboardSource, isNot(contains('RecordPaymentPage')));
    expect(dashboardSource, isNot(contains('paymentSubmissionRepository')));
  });
}
