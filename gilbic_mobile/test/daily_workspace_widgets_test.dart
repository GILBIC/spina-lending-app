import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gilbic_mobile/src/core/auth/app_role.dart';
import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/device/device_identity.dart';
import 'package:gilbic_mobile/src/features/offline/mobile_offline_policy_page.dart';
import 'package:gilbic_mobile/src/features/office/office_widgets.dart';
import 'package:gilbic_mobile/src/features/shared/daily_workspace_widgets.dart';
import 'package:gilbic_mobile/src/theme/spina_theme.dart';

void main() {
  testWidgets(
    'account tools open offline help without changing session or signing out',
    (tester) async {
      var signsOut = 0;
      final session = UserSession(
        userId: 'one',
        username: 'one',
        displayName: 'One',
        role: AppRole.employee,
        rawRole: 'Employee',
        accessToken: 'test',
        permissions: const ['employee.portal.view'],
      );
      await tester.pumpWidget(
        MaterialApp(
          theme: SpinaTheme.light,
          home: Scaffold(
            appBar: AppBar(
              actions: [
                WorkspaceAccountMenu(
                  session: session,
                  deviceIdentityProvider: DeviceIdentityProvider(
                    store: MemoryDeviceIdentityStore(),
                  ),
                  onSignOut: () async {
                    signsOut++;
                  },
                ),
              ],
            ),
          ),
        ),
      );
      await tester.tap(find.byTooltip('Account & tools'));
      await tester.pumpAndSettle();
      expect(signsOut, 0);
      await tester.tap(find.text('Offline & sync'));
      await tester.pumpAndSettle();
      expect(find.byType(MobileOfflinePolicyPage), findsOneWidget);
      expect(signsOut, 0);
      expect(session.permissions, ['employee.portal.view']);
      await tester.pageBack();
      await tester.pumpAndSettle();
      await tester.tap(find.byTooltip('Account & tools'));
      await tester.pumpAndSettle();
      await tester.tap(find.text('Sign out'));
      await tester.pumpAndSettle();
      expect(signsOut, 1);
    },
  );

  testWidgets('office errors are announced and wide forms remain readable', (
    tester,
  ) async {
    await tester.binding.setSurfaceSize(const Size(1200, 800));
    addTearDown(() => tester.binding.setSurfaceSize(null));
    await tester.pumpWidget(
      MaterialApp(theme: SpinaTheme.light, home: const _OfficeHarness()),
    );
    expect(tester.getSize(find.byType(ListView)).width, lessThanOrEqualTo(720));
    final announcement = find.ancestor(
      of: find.byKey(const Key('office-error')),
      matching: find.byType(Semantics),
    );
    expect(
      announcement.evaluate().any(
        (e) => (e.widget as Semantics).properties.liveRegion == true,
      ),
      isTrue,
    );
    expect(tester.takeException(), isNull);
  });
}

class _OfficeHarness extends StatefulWidget {
  const _OfficeHarness();
  @override
  State<_OfficeHarness> createState() => _OfficeHarnessState();
}

class _OfficeHarnessState extends OfficeScreenState<_OfficeHarness> {
  @override
  void clearPrivate() {}
  @override
  Widget build(BuildContext context) {
    operation.error = 'Please check the required fields.';
    return screen('Application', [
      const TextField(decoration: InputDecoration(labelText: 'Name')),
    ]);
  }
}
