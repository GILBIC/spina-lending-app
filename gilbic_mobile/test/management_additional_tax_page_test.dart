import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gilbic_mobile/src/core/auth/app_role.dart';
import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/device/device_identity.dart';
import 'package:gilbic_mobile/src/core/management/additional_tax.dart';
import 'package:gilbic_mobile/src/core/management/additional_tax_repository.dart';
import 'package:gilbic_mobile/src/features/management/management_additional_tax_page.dart';

void main() {
  testWidgets('additional-tax workspace shows authoritative empty queues', (
    tester,
  ) async {
    await tester.binding.setSurfaceSize(const Size(390, 844));
    addTearDown(() async => tester.binding.setSurfaceSize(null));
    await tester.pumpWidget(
      MaterialApp(
        home: ManagementAdditionalTaxPage(
          session: _session,
          deviceIdentityProvider: _deviceProvider(),
          repository: _Repository(),
        ),
      ),
    );
    await tester.pumpAndSettle();
    expect(find.text('Additional Tax'), findsOneWidget);
    expect(find.byKey(const Key('additional-tax-summary')), findsOneWidget);
    expect(
      find.text('No exact upward-amendment candidates are eligible.'),
      findsOneWidget,
    );
    expect(
      find.text('No retained additional-tax amendments yet.'),
      findsOneWidget,
    );
  });
}

class _Repository extends Fake implements AdditionalTaxRepository {
  @override
  Future<AdditionalTaxOverview> load(
    UserSession session, {
    required String deviceId,
    String amendmentStatus = 'all',
    int limit = 100,
    int offset = 0,
  }) async => const AdditionalTaxOverview(
    summary: AdditionalTaxSummary(
      amendmentEvidenceCount: 0,
      amendmentReadyCount: 0,
      liabilityPreparedCount: 0,
      awaitingPaymentCount: 0,
      paymentReadyCount: 0,
      settlementPreparedCount: 0,
      settledCount: 0,
      reviewCount: 0,
      blockedCount: 0,
      recognizedAdditionalTaxTotal: '0.00',
      settledPaymentTotal: '0.00',
    ),
    items: <AdditionalTaxItem>[],
    candidates: <AdditionalTaxCandidate>[],
    permissions: AdditionalTaxPermissions(
      amendmentEvidenceRecord: false,
      liabilityPrepare: false,
      liabilityPost: false,
      paymentEvidenceRecord: false,
      settlementPrepare: false,
      settlementPost: false,
    ),
    amendmentStatus: 'all',
    limit: 100,
    offset: 0,
    notice: 'Original return and settlement history remains immutable.',
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
