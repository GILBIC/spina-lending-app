import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gilbic_mobile/src/core/auth/app_role.dart';
import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/management/management_dashboard_overview.dart';
import 'package:gilbic_mobile/src/core/network/spina_api.dart';
import 'support/android_role_fixture.dart';
import 'support/role_homes.dart';

class _Overview extends SyntheticOverview {
  int calls = 0;
  int? failure;

  @override
  Future<ManagementDashboardOverview> loadOverview(
    UserSession session, {
    required String deviceId,
  }) async {
    calls++;
    if (failure != null) {
      throw SpinaApiException('private_overview_detail', statusCode: failure);
    }
    return super.loadOverview(session, deviceId: deviceId);
  }
}

void main() {
  for (final status in [401, 403, 426]) {
    testWidgets(
      'Management $status blocks pull and retained refresh callbacks',
      (tester) async {
        final repository = _Overview();
        await pumpAndroidRoleFixture(
          tester,
          home: roleHome(AppRole.management, overview: repository),
          size: const Size(412, 915),
          textScaler: TextScaler.linear(1),
        );
        await tester.pumpAndSettle();
        final refresh = tester
            .widget<RefreshIndicator>(find.byType(RefreshIndicator))
            .onRefresh;
        repository.failure = status;
        await refresh();
        await tester.pumpAndSettle();
        expect(
          find.byKey(const Key('management-overview-facts')),
          findsNothing,
        );
        expect(find.textContaining('private_'), findsNothing);
        await tester.drag(
          find.byType(SingleChildScrollView),
          const Offset(0, 400),
        );
        await tester.pumpAndSettle();
        await refresh();
        await tester.pumpAndSettle();
        expect(repository.calls, 2);
        expect(
          find.byKey(const Key('management-overview-retry')),
          findsNothing,
        );
        expect(
          status != 403
              ? find.byKey(const Key('management-overview-sign-in'))
              : find.textContaining('Access unavailable'),
          findsOneWidget,
        );
      },
    );
  }
}
