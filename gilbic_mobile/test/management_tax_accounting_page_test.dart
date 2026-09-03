import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gilbic_mobile/src/core/auth/app_role.dart';
import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/device/device_identity.dart';
import 'package:gilbic_mobile/src/features/management/management_tax_accounting_page.dart';

void main() {
  testWidgets(
    'tax accounting exposes settlement, correction, additional and recoverable rows',
    (tester) async {
      await tester.binding.setSurfaceSize(const Size(390, 844));
      addTearDown(() async => tester.binding.setSurfaceSize(null));
      await tester.pumpWidget(
        MaterialApp(
          home: ManagementTaxAccountingPage(
            session: _session,
            deviceIdentityProvider: _deviceProvider(),
          ),
        ),
      );

      expect(find.byKey(const Key('tax-settlement-workspace')), findsOneWidget);
      expect(find.text('Tax returns & settlements'), findsOneWidget);
      await tester.scrollUntilVisible(
        find.byKey(const Key('tax-adjustment-workspace')),
        250,
      );
      expect(find.byKey(const Key('tax-adjustment-workspace')), findsOneWidget);
      expect(find.text('Tax corrections'), findsOneWidget);
      await tester.scrollUntilVisible(
        find.byKey(const Key('additional-tax-workspace')),
        250,
      );
      expect(find.byKey(const Key('additional-tax-workspace')), findsOneWidget);
      expect(find.text('Additional tax'), findsOneWidget);
      await tester.scrollUntilVisible(
        find.byKey(const Key('tax-recoverable-workspace')),
        250,
      );
      expect(
        find.byKey(const Key('tax-recoverable-workspace')),
        findsOneWidget,
      );
      expect(find.text('Tax Recoverable'), findsOneWidget);
    },
  );
}

DeviceIdentityProvider _deviceProvider() {
  final store = MemoryDeviceIdentityStore()..value = 'management-device';
  return DeviceIdentityProvider(
    store: store,
    platformResolver: () => 'android',
    appVersionResolver: () async => '1.0.0',
  );
}

const _session = UserSession(
  userId: 'management-1',
  username: 'manager',
  displayName: 'Management',
  role: AppRole.management,
  rawRole: 'Management',
  accessToken: 'management-token',
  permissions: <String>[],
);
